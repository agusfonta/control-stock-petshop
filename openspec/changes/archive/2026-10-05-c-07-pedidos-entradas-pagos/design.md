# Design

## Context

Ver `proposal.md` (Why) y `specs/compras/spec.md` (contrato de comportamiento).
Estado verificado en código:

- `backend/app/models.py` define `Distribuidora`, `ListaPrecio` (unique
  `(distribuidora_id, producto_id)`), `Producto` (`costo Numeric(10,2)`,
  `margen_pct Numeric(5,4)`, `precio_venta` como `column_property`
  `costo × (1 + margen_pct)`) y `MovimientoStock` append-only con `tipo`
  `entrada` ya reservado y `ref_id String(36)` nullable (C-05 D6). PKs
  `String(36)` uuid; `AuditMixin` (`activo` + timestamps) en todo modelo de
  dominio salvo el ledger.
- `backend/app/services/stock.py::ajustar()` es la única vía de mutación de
  stock (C-05 D1): valida motivo, lockea el producto (`FOR UPDATE` salvo
  SQLite), crea el movimiento y **hace `commit()` por llamada** (con
  `rollback()` propio ante error). No acepta `ref_id`. Lo usan
  `routers/productos.py::ajustar_producto` y `tests/test_stock_ajuste.py`.
- `precio_venta` se calcula en lectura; C-06 (`routers/distribuidoras.py`
  `comparar`) lo recalcula en Python para costos de lista sin persistir. No
  hay ningún precio sugerido persistido que actualizar.
- Guards: `deps.require_duena` y `deps.require_role(*roles)`; patrón de
  router con `_get_or_404`, `IntegrityError → 409`, envelope
  `PaginacionResponse`, schemas `extra="forbid", strict=True` +
  `_coerce_decimal` + serializador Decimal.
- Cadena Alembic en `0005_lista_precio_producto_idx`; la nueva revisión es
  `0006`. Tests sobre SQLite en memoria (`tests/conftest.py`) + test de
  migración real en Postgres (`tests/test_migration_pg.py`).

## Goals / Non-Goals

**Goals:**

- Recibir un pedido es atómico: N líneas → N entradas + N movimientos +
  costos + estado, todo o nada, sin duplicar stock jamás.
- Reutilizar el servicio de stock como única vía de mutación sin cambiar el
  contrato ni el comportamiento observable del ajuste manual de C-05.
- Ningún costo lo introduce mostrador: los costos salen de listas/productos,
  que solo edita la dueña.

**Non-Goals:**

- Recepción parcial / backorder, edición de pedidos pendientes, costo
  promedio ponderado, vínculo pago↔pedido, adjuntos de factura, reportes de
  compras (C-14), frontend (C-13), `Idempotency-Key` por header.

## Decisions

- **D1 — Migración `0006` (no `005`), hija de `0005`.** *(fijada por la
  orquestación)* CHANGES.md §C-07 dice "Migración 005" pero
  `0005_lista_precio_producto_idx` ya existe (C-06). Se crea
  `0006_compras.py` manual (no autogenerate ciego), espejando `0004`: enums
  nativos auto-creados por `create_table` y dropeados con `checkfirst` en el
  downgrade. Corregir la línea de CHANGES.md es una tarea de apply/archive,
  no de este propose.

- **D2 — Cuatro tablas; `EntradaStock` es una fila por producto recibido.**
  El ERD de la KB es `PedidoCompra 1—N EntradaStock N—1 Producto`, así que la
  entrada no es una cabecera sino el registro por producto:
  - `pedido_compra`: `id`, `distribuidora_id` FK, `estado` enum
    `estado_pedido` (`pendiente`/`recibido`/`cancelado`, default
    `pendiente`), `usuario_id` FK (creador), `notas` nullable,
    `recibido_at` / `recibido_por_id` nullable + `AuditMixin`. `activo`
    queda en `true` siempre: la "baja" de un pedido es el estado
    `cancelado`, no hay DELETE.
  - `linea_pedido`: `id`, `pedido_id` FK (`ON DELETE CASCADE`),
    `producto_id` FK, `cantidad Integer CHECK > 0`,
    `costo_unitario Numeric(10,2) CHECK > 0`, unique
    `(pedido_id, producto_id)`.
  - `entrada_stock`: `id`, `pedido_id` FK, `producto_id` FK, `cantidad
    CHECK > 0`, `costo_unitario Numeric(10,2) CHECK > 0`, `usuario_id` FK,
    `created_at`; unique `(pedido_id, producto_id)`; append-only con los
    mismos listeners `before_update/before_delete` que `MovimientoStock`.
  - `pago_distribuidora`: `id`, `distribuidora_id` FK, `monto
    Numeric(12,2) CHECK > 0`, `metodo` enum `metodo_pago_distribuidora`
    (`efectivo`/`transferencia`/`cheque`/`otro`), `fecha Date` (default
    hoy), `nota` nullable, `usuario_id` FK + `AuditMixin` (soft-delete).
  - Índices manuales sobre FKs consultadas: `pedido_compra(distribuidora_id)`,
    `pedido_compra(estado)`, `linea_pedido(pedido_id)` (cubierto por el
    unique), `entrada_stock(pedido_id)` (cubierto por el unique),
    `pago_distribuidora(distribuidora_id)`.
  - Tipos: `costo_unitario Numeric(10,2)` igual que `Producto.costo` (se
    copia a él al recibir: misma precisión, sin truncado); `monto
    Numeric(12,2)` con más headroom porque un pago agrupa varias compras.
    PKs `String(36)` uuid por consistencia con el resto del esquema (el
    skill sugiere BIGINT identity; se prioriza homogeneidad de FKs).
  Alternativa (una cabecera `entrada` + `linea_entrada`): descartada, agrega
  una tabla sin información nueva mientras la recepción sea total (D5).

- **D3 — Recibir en UNA transacción: núcleo sin commit en el servicio de
  stock.** *(problema fijado por la orquestación; resolución propuesta)*
  `ajustar()` hace commit por llamada, así que llamarlo N veces deja stock a
  medias si falla la línea k. Se extrae de `services/stock.py`:
  `aplicar_movimiento(db, producto_id, cantidad_delta, tipo, usuario,
  motivo=None, ref_id=None) -> (Producto, MovimientoStock)` que lockea la
  fila (`FOR UPDATE` salvo SQLite), valida `delta != 0` y `stock_nuevo >= 0`,
  muta `stock_actual`, agrega el movimiento y hace `flush()` — **sin
  `commit()` ni `rollback()`**: el dueño de la transacción es el llamador.
  `ajustar()` queda como envoltorio con la **misma firma, validaciones,
  excepciones y commit/rollback** que hoy (valida motivo → núcleo → commit →
  `IntegrityError` ⇒ `StockNegativo`), por lo que `test_stock_ajuste.py` y
  `test_stock_movimientos.py` pasan sin tocarse (es un REFACTOR con la suite
  C-05 como red de seguridad). Alternativas:
  - `ajustar(..., commit: bool = True)`: descartada — parámetro bandera, y el
    `rollback()` interno de `ajustar` desharía la transacción externa entera
    ante un error esperado, mezclando dos responsabilidades.
  - Savepoints (`begin_nested`) por línea: descartada — complejidad y
    quirks de savepoints con pysqlite en los tests, sin beneficio (no
    queremos éxito parcial).
  - N llamadas a `ajustar()` + compensación manual: descartada — viola
    RN-ST-03 (ventana con stock sin su par consistente) y es frágil.
  - Mutar `stock_actual` inline en el servicio de compras: descartada —
    rompe C-05 D1 (única vía de mutación) y duplicaría el invariante.
  C-10 (ventas) reutilizará el mismo núcleo para su transacción multi-línea.

- **D4 — Servicio `services/compras.py` + router delgado `routers/compras.py`.**
  El servicio expone `crear_pedido`, `recibir_pedido`, `cancelar_pedido`,
  `registrar_pago`, `anular_pago`, `cuenta_distribuidora` y levanta errores
  de dominio (`PedidoNoEncontrado` → 404, `EstadoInvalido` → 409,
  `ReferenciaInactiva` → 422, etc.) que el router mapea a HTTP, igual que
  `ajustar_producto` mapea `StockError`. `recibir_pedido`:
  1. lockea el pedido (`FOR UPDATE` salvo SQLite) y verifica `pendiente`;
  2. ordena las líneas por `producto_id` (orden de lock determinístico);
  3. por línea: crea `EntradaStock` (id generado antes para usarlo de
     `ref_id`), llama `aplicar_movimiento(+cantidad, tipo="entrada",
     ref_id=entrada.id, motivo="recepción pedido <id>")` y, si
     `producto.costo != costo_unitario`, lo actualiza (D6);
  4. marca `recibido`, `recibido_at`, `recibido_por_id`;
  5. **un único `commit()`**; ante cualquier excepción `rollback()` y
     re-raise. El `ref_id` del movimiento apunta a la entrada, y la entrada
     al pedido: trazabilidad movimiento → entrada → pedido → distribuidora.

- **D5 — Recepción total en v1 (sin parcial).** *(pregunta abierta resuelta;
  revisar)* `recibir` no lleva body: todas las líneas entran con la cantidad
  pedida y el pedido pasa a `recibido`. Si llega distinto de lo pedido: la
  dueña cancela y recrea el pedido con lo real, o corrige luego con un ajuste
  auditable (C-05). Rationale: una sola transición, un estado final, sin
  backorder ni estado `parcial`, y habilita el unique `(pedido_id,
  producto_id)` en `entrada_stock` como barrera de doble recepción (D7).
  Alternativas: (a) recepción única con cantidades reales por línea (body
  opcional, sin backorder) — primer upgrade natural, cambia spec + 1 grupo
  de tareas; (b) parcial con estado `parcial` y saldo pendiente — descartada
  para v1 (máquina de estados y unique más complejos).

- **D6 — Costo: snapshot de lista vigente al pedir; al recibir se copia al
  producto (último costo).** *(pregunta abierta resuelta; revisar)*
  - Al crear el pedido, `costo_unitario` de cada línea = costo de
    `ListaPrecio(distribuidora, producto)` si existe; si no, `Producto.costo`
    actual. El cliente **no** envía costos (`extra="forbid"` ⇒ 422): así
    mostrador, que puede crear pedidos y recibir, nunca introduce un costo;
    los costos los fija la dueña vía listas (C-06) o `PUT /productos`.
  - Al recibir, la entrada registra el `costo_unitario` de la línea y se
    asigna `Producto.costo = costo_unitario` cuando difiere (si es igual, no
    se escribe: mismo resultado observable, sin `updated_at` espurio).
  - Precio sugerido: **no se toca nada más**. `precio_venta` es
    `column_property` sobre `costo`, así que se recalcula solo (RN-PR-01,
    Flujo 2 paso 4) y `comparar` de C-06 sigue calculando por lista sin
    cambios. No se duplica la fórmula. Ventas históricas no se reescriben
    (RN-PR-04; C-10 guardará `precio_unit` por línea).
  - Alternativas: (a) releer la lista al recibir (literal "lista vigente" en
    la entrada) — descartada: el costo pactado es el del momento del pedido y
    un snapshot hace predecible el total del pedido; (b) costo promedio
    ponderado — descartada para v1 (requiere valorizar stock existente pre-C-05
    sin costo histórico); (c) no tocar `Producto.costo` — descartada: Flujo 2
    exige que la entrada actualice costo y precio sugerido.

- **D7 — Transiciones con `409` e idempotencia por lock + unique.** El chequeo
  de estado ocurre con el pedido lockeado dentro de la transacción; un
  segundo `recibir` (doble click, reintento de red, concurrencia) ve
  `recibido` y responde `409` sin efectos. Defensa en profundidad: el unique
  `(pedido_id, producto_id)` de `entrada_stock` hace que la base rechace una
  segunda recepción aun si el lock fallara (SQLite no soporta `FOR UPDATE`
  pero serializa writers); ese `IntegrityError` también se mapea a `409`. Se
  eligió `409` (no `200` con el pedido ya recibido) por consistencia con la
  convención del proyecto de `409` en transiciones inválidas; en ambos casos
  el stock nunca se suma dos veces. Mismo patrón para `cancelar`.

- **D8 — RBAC.** *(pagos solo dueña: propuesto; revisar)*

  | Endpoint | duena | mostrador | Base |
  |---|---|---|---|
  | `POST /compras/pedidos` | ✓ | ✓ | matriz: "crear pedido" |
  | `GET /compras/pedidos`, `GET /compras/pedidos/{id}` | ✓ | ✓ | matriz: "ver" |
  | `POST /compras/pedidos/{id}/recibir` | ✓ | ✓ | matriz: "registrar entrada" |
  | `POST /compras/pedidos/{id}/cancelar` | ✓ | 403 | no es "crear" ni "registrar entrada" |
  | `POST/GET/DELETE /compras/pagos` | ✓ | 403 | dinero/cuenta corriente |
  | `GET /compras/distribuidoras/{id}/cuenta` | ✓ | 403 | dinero/cuenta corriente |

  Pagos y cuenta solo dueña: son información financiera (cuánto se le debe a
  cada proveedor) y la matriz solo le da a mostrador "ver + crear pedido" y
  "registrar entrada"; ninguna incluye pagos. Se usa
  `require_role("duena", "mostrador")` explícito (no `get_current_user`) en
  las escrituras compartidas para que la intención quede en el código y un
  rol futuro no herede permisos por omisión.

- **D9 — Pagos independientes, anulables por soft-delete.** Sin `pedido_id`
  (RN-CP-03; enviarlo ⇒ 422 por `extra="forbid"`). Anular = `DELETE` →
  `activo=False` (convención soft-delete del proyecto) para corregir errores
  de tipeo sin borrar historia; los anulados no se listan ni suman en la
  cuenta. Se admiten pagos a distribuidoras inactivas (se puede seguir
  saldando deuda con un proveedor dado de baja), a diferencia de los pedidos
  nuevos (D11). `fecha` opcional (default hoy) para registrar pagos hechos
  días antes.

- **D10 — Cuenta simple incluida en v1, calculada al vuelo.** *(pregunta
  abierta resuelta; revisar)* `GET /compras/distribuidoras/{id}/cuenta` =
  `SUM(entrada.cantidad × entrada.costo_unitario)` de entradas de pedidos de
  esa distribuidora − `SUM(pago.monto)` de pagos activos, en `Decimal`. Sin
  columna `saldo` persistida (evita drift, como C-05 D3 con `bajo_minimo`).
  Rationale: CHANGES.md define el alcance como "US-006 + cuenta simple" y
  RN-CP-03 habla de cuenta corriente; sin esta lectura los pagos serían datos
  write-only. Es un grupo de tareas aislado: si la usuaria prefiere
  diferirlo a C-14, se quita el grupo y su requirement sin tocar el resto.
  Ruta bajo `/compras` (no `/distribuidoras/{id}/...`) para no tocar el
  router de C-06 ni su orden de rutas (C-06 D5).

- **D11 — Validaciones.** Schemas estrictos (`extra="forbid"`,
  `strict=True`): `cantidad` int `> 0`, `lineas` entre 1 y 100, `producto_id`
  sin repetir en el pedido (422), `monto` Decimal `> 0` con `_coerce_decimal`,
  `metodo`/`estado` como `Literal`. Referencias: id inexistente ⇒ `404`
  (precedente C-06 listas); distribuidora o producto inactivo al **crear**
  pedido ⇒ `422`. Al **recibir** no se revalida actividad: la mercadería ya
  llegó físicamente y el stock debe reflejarlo.

- **D12 — Router `/api/compras` nuevo, rutas fijas antes que parametrizadas.**
  Declaración: `/pedidos`, `/pedidos/{id}`, `/pedidos/{id}/recibir`,
  `/pedidos/{id}/cancelar`, `/pagos`, `/pagos/{id}`,
  `/distribuidoras/{id}/cuenta`. Respuestas: crear pedido/pago `201`,
  recibir/cancelar `200` con el detalle, anular pago `204`.

## Risks / Trade-offs

- [Refactor de `ajustar()` rompe C-05] → Mitigación: baseline de la suite
  antes de tocar `services/stock.py`; el núcleo se extrae como REFACTOR con
  `test_stock_ajuste.py`/`test_stock_movimientos.py` verdes sin editarlos.
- [Deadlock al recibir dos pedidos con productos en común en Postgres] →
  Mitigación: locks de productos en orden determinístico (`producto_id`
  ascendente) después del lock del pedido.
- [SQLite no soporta `FOR UPDATE`] → Mitigación: igual que C-05 (SQLite
  serializa writers) + unique `(pedido_id, producto_id)` en `entrada_stock`
  como barrera en ambas bases; test de doble recepción secuencial.
- [Atomicidad no probada] → Mitigación: test que fuerza fallo en la 2ª línea
  (monkeypatch del núcleo) y verifica stock, costo, entradas, movimientos y
  estado intactos.
- [Snapshot de costo desactualizado si la lista cambia entre pedido y
  recepción] → Aceptado (D6): la dueña cancela y recrea, o ajusta el costo
  del producto luego. Registrado, no deuda oculta.
- [Recibir cambia `precio_venta` visible en mostrador inmediatamente] →
  Comportamiento buscado (Flujo 2); ventas confirmadas no se reescriben
  (RN-PR-04).
- [Enums nativos duplicados en Postgres al migrar] → Mitigación: patrón de
  `0004` (auto-create en `create_table`, `drop(checkfirst=True)` en
  downgrade) + test en `test_migration_pg.py`.
- [Numeración] CHANGES.md dice "Migración 005" → usar `0006`; tarea de
  corrección en el grupo final.

## Migration Plan

1. Rama `change/c-07-pedidos-entradas-pagos`; merge solo vía PR con checks.
2. Deploy: `alembic upgrade head` (0006 crea 4 tablas vacías + enums; sin
   backfill, sin downtime: ningún endpoint existente las lee).
3. Desplegar API (router nuevo + refactor interno del servicio de stock sin
   cambio de contrato).
4. Rollback: revert del deploy + `alembic downgrade -1` (drop de tablas y
   enums). Si ya hubo recepciones, sus `MovimientoStock` tipo `entrada`
   quedan con `ref_id` huérfano (columna sin FK): el stock sigue
   consistente con el ledger; documentado.
5. Verificar: `GET /api/health`, smoke pedido → recibir → stock y costo
   actualizados → pago → cuenta.

## Decisiones a revisar por la usuaria

Tomadas con un default recomendado; cambiarlas modifica spec + tareas:

- **D5** recepción total (alternativa: cantidades reales en una sola
  recepción, sin backorder).
- **D6** costo snapshot de lista al pedir + "último costo" al recibir
  (alternativas: releer lista al recibir; costo promedio).
- **D8** pagos y cuenta solo dueña (alternativa: mostrador ve pagos).
- **D10** cuenta/saldo incluido en v1 (alternativa: diferir a C-14).

## Open Questions

- Ninguna bloqueante. Deferibles sin cambiar specs ni tareas: tamaño de página
  default de listados (se adopta 20 / máx. 100 como C-04/C-05/C-06) y texto
  exacto del `motivo` automático de los movimientos de entrada.
