# Design

> Governance **CRÍTICO** (dinero + stock). Este documento es solo análisis:
> cada decisión no obvia está numerada, con alternativas, y las que cambian
> comportamiento observable están listadas en "Decisiones a revisar". El
> apply requiere aprobación humana explícita.

## Context

Ver `proposal.md` (Why) y `specs/ventas/spec.md` + `specs/clientes/spec.md`
(contrato). Estado verificado en código y artefactos:

- `alembic heads` → `0006 (head)` (`0006_compras.py`, C-07). La nueva
  revisión es `0007`, coincide con CHANGES.md §[C-10] "Migración 007".
- `backend/app/models.py`: `TIPO_MOVIMIENTO = ("venta", "entrada", "ajuste",
  "apertura")`, reservados desde `0004` como enum nativo `tipo_movimiento`
  ("venta/entrada for C-07/C-10"); la spec `stock-alertas` enumera esos
  cuatro tipos. `MovimientoStock` es append-only (listeners
  `before_update/before_delete`), tiene `ref_id String(36)` sin FK, `motivo`
  nullable y `CHECK stock_nuevo >= 0`. `Producto.precio_venta` es un
  `column_property` `costo × (1 + margen_pct)` sin redondeo (`Numeric(10,2) ×
  Numeric(5,4)` ⇒ hasta 6 decimales; `ProductoResponse` lo expone tal cual).
  `Producto.costo > 0` y `margen_pct >= 0` por schema ⇒ `precio_venta > 0`.
  `Cliente` tiene `activo` (soft-delete) y `saldo_cc` reservado (C-09 D8).
- `backend/app/services/stock.py::aplicar_movimiento(db, producto_id,
  cantidad_delta, tipo, usuario, motivo=None, ref_id=None)` es el núcleo
  **sin commit** (C-07 D3): lockea el producto (`FOR UPDATE` salvo SQLite),
  valida `delta != 0` y `stock_nuevo >= 0` (`StockNegativo`), muta y hace
  `flush()`. C-07 lo dejó documentado para reutilizarse en ventas.
- `services/compras.py::recibir_pedido` es el patrón de transacción única:
  lock de la cabecera, líneas en orden de `producto_id`, un solo `commit()`,
  `rollback()` + re-raise ante cualquier error, `IntegrityError` de una
  barrera de base mapeado a `409`. Errores de dominio (`NoEncontrado` 404,
  `ReferenciaInactiva` 422, `EstadoInvalido` 409) mapeados en el router.
- Schemas: `ConfigDict(extra="forbid", strict=True)`, `_coerce_decimal`,
  `_serialize_money`, `PaginacionResponse`; listados 20/100.
  `deps.require_role(*roles)`, `require_duena`, `get_current_user`.
  Handlers sync con `Session` (la consistencia con el código existente prima
  sobre el estilo async de las plantillas del registry, como en C-09 D3).
- `routers/clientes.py` (C-09): `/buscar` antes de `/{cliente_id}`; C-09 D2
  difirió `GET /api/clientes/{id}/ventas` a C-10 y C-09 D9 fijó el contrato
  "rechazar `cliente_id` inexistente o inactivo al crear la venta".
- Redis existe (`deps.get_redis`, fakeredis en tests) pero ningún job
  transaccional lo usa; `app/workers/stock_alerts.py` es el único worker.
  No existe `ComprobanteFE` (C-11) ni nada de Mercado Pago (C-12).
- KB: Flujo 1 paso 4 ("en transacción: revalida stock, crea venta + líneas +
  pagos, descuenta stock, crea movimientos, encola job FE"); RBAC "mostrador:
  crear + ver propias; dueña: CRUD + anular"; Excepciones globales
  ("operaciones de dinero y stock idempotentes por `idempotency_key`");
  `10_preguntas_abiertas.md` Media "¿Anulación con devolución de dinero o
  solo nota?" (abierta); DD-05 offline en v2 (diseñar sin implementar);
  seed "métodos de pago base".
- Entorno: `alembic upgrade` contra el Postgres local falla con un
  `UnicodeDecodeError` de conexión preexistente (locale del servidor); C-07
  validó su migración en SQLite real + `--sql` offline + Postgres en CI.

## Goals / Non-Goals

**Goals:**

- Ninguna venta confirmada puede dejar stock negativo ni vender stock que no
  existe, aun con borradores viejos o dos puestos compitiendo por la última
  unidad.
- Todo o nada: stock, movimientos, pagos, estado y evento de una venta
  persisten juntos o no persisten.
- Ningún reintento (doble click, red de la tablet, reenvío) duplica una
  venta, un descuento de stock, una devolución o un evento.
- El precio y el total los fija el servidor; el mostrador no introduce
  precios.
- Reutilizar `aplicar_movimiento()` **sin modificarlo** (suite C-05/C-07 como
  red de seguridad intacta).

**Non-Goals:**

- Emitir FE, `ComprobanteFE`, worker o reintentos ARCA (C-11); QR/link,
  webhook o verificación de pagos MP (C-12); ticket/impresión y carrito (C-13);
  agregados de reportes (C-14).
- Descuentos, promociones, precios manuales, devoluciones parciales,
  devolución de dinero, notas de crédito, cuenta corriente de clientes,
  vuelto persistido, numeración de comprobantes, edición o descarte de
  borradores, `Idempotency-Key` por header.

## Decisions

- **D1 — Migración `0007_ventas.py`, hija de `0006`.** Verificado con
  `alembic heads`. Manual (no autogenerate ciego), espejando `0006`: enums
  nativos auto-creados por `create_table` y dropeados con
  `drop(checkfirst=True)` en el downgrade. **No** altera `tipo_movimiento`
  (ver D3). Validación: test SQLite real (patrón `test_migration_0006.py`:
  esquema previo por metadata, `stamp 0006`, upgrade → downgrade -1 →
  upgrade), revisión del SQL offline (`alembic upgrade 0006:0007 --sql`) y
  tests `pg_only` en `test_migration_pg.py` que CI ejecuta. El
  `UnicodeDecodeError` local se documenta, no se arregla en este change.

- **D2 — Cuatro tablas.** PKs `String(36)` uuid (homogeneidad de FKs con el
  resto del esquema, como C-07 D2). Sin `ON DELETE CASCADE`: las ventas nunca
  se borran.
  - `venta`: `id`, `cliente_id` FK `clientes` nullable, `usuario_id` FK
    (vendedor/creador), `estado` enum `estado_venta`
    (`borrador`/`confirmada`/`anulada`, default `borrador`), `total
    Numeric(12,2)`, `idempotency_key String(36)`, `confirmada_at` /
    `confirmada_por_id` FK nullable, `anulada_at` / `anulada_por_id` FK /
    `motivo_anulacion` nullable + `AuditMixin` (`activo` queda siempre
    `true`: no hay baja de ventas). Checks: `total > 0`;
    `estado = 'borrador' OR confirmada_at IS NOT NULL`;
    `estado <> 'anulada' OR (anulada_at IS NOT NULL AND motivo_anulacion IS
    NOT NULL)`. Unique `(usuario_id, idempotency_key)` (D8). Índices
    `(cliente_id, created_at)` (historial), `(usuario_id, created_at)`
    (listado del mostrador), `(created_at)` (listado de la dueña por fecha).
  - `linea_venta`: `id`, `venta_id` FK, `producto_id` FK, `cantidad Integer
    CHECK > 0`, `precio_unit Numeric(10,2) CHECK > 0`, `subtotal
    Numeric(12,2) CHECK > 0`; unique `(venta_id, producto_id)` (cubre el
    índice por `venta_id`); índice `(producto_id)` (FK; lo usará C-14 "más
    vendidos"). Append-only con listeners como `MovimientoStock`.
  - `pago_venta`: `id`, `venta_id` FK, `metodo` enum `metodo_pago_venta`
    (`efectivo`/`transferencia`/`mp`/`tarjeta`), `monto Numeric(12,2) CHECK >
    0`, `ref_mp String(100)` nullable, `created_at`. Check `ref_mp IS NULL OR
    metodo = 'mp'`; unique `(ref_mp)` (NULLs múltiples permitidos en Postgres
    y SQLite); índice `(venta_id)`. Append-only.
  - `evento_outbox`: ver D11.
  - Tipos de dinero: `precio_unit Numeric(10,2)` (misma precisión que
    `Producto.costo`); `subtotal`, `total`, `monto` `Numeric(12,2)` con
    headroom, como `PagoDistribuidora.monto` (C-07). `subtotal` y `total` se
    persisten (KB los lista): son snapshots inmutables, no derivados vivos.
    No se agrega `CHECK subtotal = cantidad × precio_unit` porque SQLite
    compara NUMERIC como float y el check daría falsos rechazos; el
    invariante lo garantiza el servicio y lo fija un test.
  - Seed "métodos de pago base" (KB): queda cubierto por el enum
    `metodo_pago_venta`; no hay tabla de métodos.

- **D3 — Anulación = movimiento tipo `venta` con cantidad positiva.**
  *(punto 1 de la orquestación; revisar)* Al anular, por cada línea se llama
  `aplicar_movimiento(+cantidad, tipo="venta", ref_id=venta.id,
  motivo="anulacion venta <id>: <motivo>")`. Las ventas siempre generan
  `cantidad < 0`, así que el signo distingue venta de anulación sin
  ambigüedad, y `ref_id` + `motivo` hacen la anulación auditable (RN-VT-03).
  El ledger sigue append-only (los movimientos originales no se tocan) y
  `stock_nuevo >= 0` se cumple trivialmente con delta positivo. Ventajas: sin
  `ALTER TYPE`, sin cambiar la spec `stock-alertas` ni el `Literal` de
  `MovimientoResponse`, downgrade trivial. Además la suma de movimientos
  `venta` por producto da las unidades netas vendidas.
  Alternativa: nuevo valor `anulacion` en `tipo_movimiento` — más explícito
  en el ledger, pero `ALTER TYPE ... ADD VALUE` en Postgres no es reversible
  (el downgrade exige recrear el tipo y reescribir la columna), el valor
  nuevo no puede usarse en la misma transacción que lo agrega, y obliga a un
  MODIFIED de la spec `stock-alertas` + cambio del schema de lectura de
  movimientos. Se descarta para v1; si la dueña quiere ver "anulación" como
  tipo en la UI, C-13 puede rotularlo por signo.

- **D4 — Borrador = carrito congelado con líneas; confirmar recibe los
  pagos.** *(revisar)* `POST /api/ventas` persiste cabecera + líneas con
  precio y total calculados por el servidor (D5), sin tocar stock;
  `POST /confirmar` recibe solo `pagos` y hace todo el efecto en una
  transacción (D6). Rationale: el POS necesita conocer el **total autoritativo
  del servidor** antes de registrar los pagos que deben igualarlo (RN-VT-04);
  el borrador lo entrega. CHANGES.md dice que confirmar "crea líneas+pagos":
  se interpreta como que las líneas *toman efecto* (descuentan stock) al
  confirmar; persistirlas antes no cambia ningún efecto observable de stock
  ni dinero. Alternativas: (a) borrador solo cabecera y confirmar con líneas
  + pagos — el borrador quedaría vacío salvo la clave, y el cliente debería
  calcular el total por su cuenta (precio sin redondear de catálogo, D5); (b)
  un único `POST /api/ventas` que crea y confirma — contradice el contrato de
  CHANGES.md y deja al POS sin total previo. Flujo POS resultante: carrito en
  memoria (C-13) → "Cobrar" crea el borrador → registra pagos por el total
  devuelto → confirmar. Dos requests, compatibles con < 60 s.

- **D5 — Precio congelado al crear el borrador, redondeado a centavos.**
  *(punto 4; revisar)* `precio_unit = quantize(precio_venta, 0.01,
  ROUND_HALF_UP)` leído al crear el borrador; `subtotal = cantidad ×
  precio_unit`; `total = Σ subtotales`; todo en `Decimal` (los valores que
  vienen de SQLite se convierten vía `str`, como `_a_decimal` de C-07). La
  confirmación usa los precios del borrador y no re-cotiza (es el precio que
  se le dijo al cliente; mismo criterio de snapshot que C-07 D6 y RN-PR-04).
  El cliente nunca envía precios (`extra="forbid"` ⇒ 422). Alternativas: (a)
  re-cotizar al confirmar y responder 409 si cambió — más correcto ante
  borradores viejos, pero agrega un rechazo poco comprensible en caja por un
  caso raro (los borradores viven segundos, D14); (b) redondeo a pesos
  enteros — habitual en comercios, pero ninguna RN lo pide; cambiarlo es una
  constante + tests; (c) aceptar precio del cliente — descartado (el
  mostrador no fija precios: RN-PR-02 los deja a la dueña).

- **D6 — Confirmar en una transacción: CAS de estado + locks ordenados +
  `aplicar_movimiento()` sin cambios.** *(punto 2)* Servicio
  `services/ventas.py::confirmar_venta(db, venta_id, data, usuario)`:
  1. Carga la venta; inexistente o ajena para un mostrador ⇒ `NoEncontrada`
     (404, D12). Valida pagos contra `venta.total` (inmutable, así que puede
     validarse antes del lock) ⇒ `PagosInvalidos` (422) sin escribir nada.
  2. **Compare-and-set**: `UPDATE venta SET estado='confirmada',
     confirmada_at=now, confirmada_por_id=:u WHERE id=:id AND
     estado='borrador'`. `rowcount == 1` ⇒ esta request es dueña de la
     transición (en Postgres el UPDATE toma el lock de fila; una segunda
     confirmación concurrente espera y, al re-evaluar el `WHERE` tras el
     commit de la primera, obtiene `rowcount 0`). `rowcount == 0` ⇒ rama de
     replay (D9). El CAS es además la barrera de base en SQLite, que no tiene
     `FOR UPDATE` pero serializa escritores: reemplaza al unique de
     `entrada_stock` que usó C-07 D7.
  3. Lockea **todos** los productos de la venta en una sola consulta
     `WHERE id IN (...) ORDER BY id FOR UPDATE` (salvo SQLite) — orden
     determinístico igual al de C-07, sin ciclos de deadlock entre ventas,
     recepciones y ajustes — y calcula los faltantes de **todas** las líneas;
     si hay alguno ⇒ `StockInsuficiente(faltantes)` (409, D7).
  4. Por línea, en orden de `producto_id`: `aplicar_movimiento(-cantidad,
     "venta", usuario, motivo="venta <id>", ref_id=venta.id)` (re-lockea una
     fila ya lockeada en la misma transacción: no-op; vuelve a validar
     `stock_nuevo >= 0` como segunda defensa). `ref_id` apunta a la venta (no
     a la línea): `(ref_id, producto_id)` identifica la línea por el unique
     `(venta_id, producto_id)`, y la anulación usa la misma referencia.
  5. Inserta los `PagoVenta`, registra el evento `venta.confirmada` (D11).
  6. **Un único `commit()`**. Ante cualquier excepción: `rollback()` (que
     deshace también el CAS) y re-raise. `IntegrityError` mapeado: unique de
     `ref_mp` ⇒ `RefMpDuplicada` (409); check `stock_nuevo >= 0` ⇒
     `StockInsuficiente` (409); cualquier otro se propaga (500).
  `services/stock.py` no se modifica. Alternativas: `SELECT ... FOR UPDATE`
  de la venta + chequeo de estado (C-07) — equivalente en Postgres, pero sin
  barrera real en SQLite; savepoints por línea — descartados (no se quiere
  éxito parcial); N llamadas a `ajustar()` — viola RN-VT-02.

- **D7 — Bloqueo por stock en borrador (temprano) y en confirmación
  (autoritativo), con `409` y faltantes.** *(revisar el código HTTP)* Al
  crear el borrador se compara `cantidad` contra `stock_actual` sin lock
  (feedback inmediato en caja, nada se escribe si falla); al confirmar se
  revalida con lock (D6.3), que es la única garantía. Respuesta `409` con
  `detail = {"mensaje": "stock insuficiente", "faltantes": [{"producto_id",
  "solicitado", "disponible"}]}`: el POS puede mostrar el "mensaje y
  sugerencia" del Flujo 1 (bajar a `disponible`). Se elige `409` (conflicto
  con el estado actual del recurso, reintentable cuando cambia el stock) y no
  el `422` de `StockNegativo` del ajuste manual (C-05), que valida un delta
  pedido por la dueña. Al confirmar **no** se revalida que productos o
  cliente sigan activos: la mercadería está en el mostrador y la asociación
  al cliente es informativa (mismo criterio que C-07 D11).

- **D8 — Idempotencia del alta: clave UUID por vendedor.** *(punto 3;
  revisar)* `idempotency_key` en el body (CHANGES.md), UUID canónico generado
  por el POS al iniciar el cobro (compatible con offline v2, DD-05). Unique
  `(usuario_id, idempotency_key)`: alcance por usuario, así una clave ajena
  nunca devuelve la venta de otro (no hay fuga de información) y no hace
  falta comparar dueños. Comportamiento:
  - clave nueva ⇒ `201` + venta nueva;
  - clave repetida por el mismo usuario con el mismo contenido (mismo
    `cliente_id` y mismo multiconjunto `(producto_id, cantidad)`, comparado
    contra las líneas persistidas, sin columna de hash) ⇒ `200` con la venta
    existente **en su estado actual** (aunque ya esté confirmada), sin
    re-validar stock ni re-cotizar;
  - mismo usuario, misma clave, otro contenido ⇒ `422` (semántica del draft
    IETF `Idempotency-Key`: reutilización de clave con otro payload);
  - carrera de dos POST simultáneos con la misma clave: el segundo choca con
    el unique ⇒ `rollback()`, relee y aplica las reglas anteriores (200 o
    422). Alternativas: unique global de la clave (fuga/confusión entre
    usuarios); `409` en vez de `422` para el payload distinto (convención
    interna de conflictos, pero se prefiere el estándar); header
    `Idempotency-Key` (diferido; CHANGES.md lo pide en el body).

- **D9 — Transiciones idempotentes: replay `200`, incompatibles `409`.**
  *(punto 3/8; revisar — difiere de C-07 D7)* Rama `rowcount == 0` del CAS:
  - `confirmar` sobre `confirmada` con el mismo multiconjunto de pagos
    `(metodo, monto, ref_mp)` ⇒ `200` con la venta, sin efectos; con pagos
    distintos ⇒ `409`; sobre `anulada` ⇒ `409`.
  - `anular` sobre `anulada` ⇒ `200` sin efectos (sin comparar motivo); sobre
    `borrador` ⇒ `409`.
  C-07 eligió `409` para "recibir dos veces"; aquí se elige replay porque es
  una operación de dinero con un cliente en caja y la KB exige idempotencia:
  si la tablet pierde la respuesta del confirmar, el reintento debe decir
  "confirmada" y no un error que invite a cobrar de nuevo. El stock nunca se
  aplica dos veces en ningún caso (CAS + `rowcount`). Alternativa: `409` como
  C-07 con un código en `detail` para que el POS lo interprete como éxito —
  consistente con el proyecto pero empuja la idempotencia al cliente.

- **D10 — Pagos: 1–5, mixtos, suma exacta, sin vuelto persistido, `ref_mp`
  mínimo.** *(punto 5; revisar)* Schema `PagoVentaIn {metodo: Literal[...],
  monto: Decimal (gt=0, max_digits=12, decimal_places=2), ref_mp: str | None
  (1–100, recortado)}`; `pagos` con `min_length=1, max_length=5`. Se admite
  más de un pago, de métodos iguales o distintos (ERD `Venta 1—N PagoVenta`,
  Flujo 1 "registra pagos (efectivo/MP)"); el "split" que la KB 11 deja fuera
  de v1 se interpreta como split de Mercado Pago (reparto entre cuentas), no
  como pago mixto en caja. `Σ monto == total` exacto en `Decimal` (RN-VT-04);
  si no ⇒ `422` antes de tocar nada. **Vuelto**: el pago `efectivo` se
  registra por el monto aplicado a la venta; el vuelto (efectivo entregado −
  aplicado) lo calcula y muestra el POS (C-13) y no se persiste. `ref_mp`:
  opcional para `mp` (en C-10 el cobro MP es manual, la mostradora verifica
  en la app), prohibido en otros métodos (422 + check de base) y único en
  todo el sistema (409) para que un mismo pago MP no se acredite en dos
  ventas (KB 11 "conciliar por ref"). C-12 podrá volverlo obligatorio y
  verificado. `tarjeta` y `transferencia` sin referencia en v1.
  Alternativas: un solo pago por venta (rompe el caso real efectivo + MP);
  persistir `monto_recibido`/`vuelto` (dato sin consumidor en v1; agregable
  luego sin romper); `ref_mp` obligatorio para `mp` (bloquea cobrar MP hasta
  C-12).

- **D11 — Hook de FE: outbox transaccional mínimo, sin consumidor.** *(punto
  6; revisar)* Tabla `evento_outbox`: `id`, `tipo String(50)`
  (`venta.confirmada` | `venta.anulada`), `agregado_id String(36)` (id de la
  venta), `created_at`, `procesado_at` nullable; unique `(tipo,
  agregado_id)` (un evento por venta y transición: ningún reintento lo
  duplica); índice parcial `WHERE procesado_at IS NULL` (Postgres y SQLite lo
  soportan). `services/outbox.py::registrar_evento(db, tipo, agregado_id)`
  hace `add` + `flush` **sin commit**: el evento vive o muere con la
  transacción de la venta (sin pérdida ni duplicado). C-10 no usa Redis ni
  crea `ComprobanteFE`; la venta se confirma aunque no haya consumidor ni
  ARCA (Flujo 1 "FE error ⇒ venta confirmada"). **Contrato para C-11**:
  agregar `ComprobanteFE` (unique `venta_id`) y un worker que tome eventos
  pendientes (`ORDER BY created_at FOR UPDATE SKIP LOCKED` en Postgres), cree
  el comprobante, emita y marque `procesado_at`; puede sumar un aviso Redis
  post-commit como "despertador" best-effort, pero la fuente de verdad es la
  tabla; decidir qué hace con `venta.anulada` (nota de crédito). C-14 puede
  usar los mismos eventos para invalidar cache. Alternativas: (a) encolar en
  Redis desde la request — no transaccional: antes del commit crea jobs
  fantasma si la transacción falla, después del commit los pierde si Redis
  cae o el proceso muere; (b) diferir todo a C-11, que detectaría ventas
  confirmadas sin comprobante o insertaría `ComprobanteFE` pendiente dentro
  de `confirmar_venta` — sin tabla extra en C-10, pero obliga a C-11
  (governance ALTO) a modificar la transacción CRÍTICA de confirmación; (c)
  crear `ComprobanteFE` ya en C-10 — invade el modelo de C-11. Si se prefiere
  (b), se quitan la tabla, el requirement "Evento de venta para facturación
  electrónica" y el grupo de tareas 4 sin tocar el resto.

- **D12 — RBAC y propiedad.** *(punto 7; historial del mostrador: revisar)*

  | Endpoint | duena | mostrador | Base |
  |---|---|---|---|
  | `POST /api/ventas` | ✓ | ✓ | matriz "crear" |
  | `POST /api/ventas/{id}/confirmar` | ✓ (cualquiera) | ✓ solo propias (ajena ⇒ 404) | "crear" incluye cobrar |
  | `POST /api/ventas/{id}/anular` | ✓ | 403 | RN-VT-03 |
  | `GET /api/ventas/{id}` | ✓ | solo propias (ajena ⇒ 404) | "ver propias" |
  | `GET /api/ventas` | ✓ (+ filtro `usuario_id`) | forzado a propias | "ver propias" |
  | `GET /api/clientes/{id}/ventas` | ✓ | solo sus ventas del cliente | "ver propias" |

  "Propia" = `venta.usuario_id == usuario actual` (creador). Ajena ⇒ `404` y
  no `403`, para no revelar la existencia de ventas de otros. Escrituras con
  `require_role("duena", "mostrador")` explícito (un rol futuro no hereda
  permisos), anular con `require_duena`. Historial por cliente: se aplica la
  matriz ("ver propias") también ahí. Alternativa: el mostrador ve el
  historial completo del cliente (US-007 tiene al mostrador como actor y el
  dato es útil en caja); se deja como decisión de la dueña.

- **D13 — Anulación: motivo obligatorio, sin devolución de dinero.**
  *(revisar; pregunta abierta Media de la KB)* Body `{motivo}` 1–300 chars
  recortado (auditable, como el ajuste de C-05). Servicio `anular_venta`:
  carga + 404, CAS `confirmada → anulada` con `anulada_at/por/motivo`, lock de
  productos ordenado, `aplicar_movimiento(+cantidad, "venta", ref_id=venta.id)`
  por línea (D3), evento `venta.anulada`, un commit. Los `PagoVenta` quedan
  intactos y la venta `anulada` deja de contar como venta; **no** se registra
  egreso de caja, devolución ni nota de crédito (la KB lo tiene abierto:
  "¿anulación con devolución de dinero o solo nota?"). Sin límite de tiempo y
  sin anulación parcial en v1. Una venta ya facturada (C-11) requerirá nota
  de crédito: lo resolverá C-11 consumiendo `venta.anulada`.

- **D14 — Sin edición ni descarte de borradores en v1.** *(punto 8; revisar)*
  El carrito vive en memoria en el POS; el borrador se crea al tocar
  "Cobrar" y se confirma segundos después. Para cambiar el carrito, el POS
  crea otro borrador con otra clave. Un borrador abandonado es inerte: no
  reserva stock, no tiene pagos, no aparece en el historial ni en el listado
  por defecto. Sin numeración propia de venta: el número fiscal lo da ARCA
  (C-11) y el ticket puede usar `id`/fecha. Alternativas: `PUT` de líneas en
  borrador (más superficie en un dominio CRÍTICO sin necesidad en el flujo
  POS); `POST /{id}/descartar` o job de limpieza (agregables sin romper el
  contrato si los borradores muertos molestan).

- **D15 — Lecturas mínimas.** *(puntos 9/10)* `GET /api/ventas/{id}` (detalle
  para ticket y para confirmar el estado tras un error de red) y
  `GET /api/ventas` (la matriz da "ver propias" y no hay otra forma de
  cumplirla): paginado 20/100, orden `created_at DESC, id`, filtros `estado`
  (`Literal`), `cliente_id`, `usuario_id` (solo efectivo para la dueña; para
  el mostrador el filtro por dueño propio siempre se aplica, y un
  `usuario_id` ajeno da lista vacía), `desde`/`hasta` como datetimes ISO 8601
  **con zona** (naive ⇒ 422), intervalo `[desde, hasta)` sobre `created_at`:
  el cliente calcula los bordes del día local (Argentina, UTC−3), evitando
  asumir zona en el servidor. Sin `estado`, solo `confirmada` y `anulada`.
  El nombre del producto en las líneas se resuelve por join al leer (no se
  congela; la KB no lo pide). `GET /api/clientes/{id}/ventas` en
  `routers/clientes.py` (path de dos segmentos, no colisiona con `/buscar`
  ni `/{id}`), resumen de venta sin líneas, 404 si el cliente no existe,
  incluye clientes dados de baja (coherente con C-09 D9).

- **D16 — Capas, schemas y códigos.** `services/ventas.py` (`crear_venta`,
  `confirmar_venta`, `anular_venta`, `obtener_venta`, `listar_ventas`,
  `ventas_de_cliente`) con errores de dominio `VentaNoEncontrada`/
  `NoEncontrado` 404, `ReferenciaInactiva` 422, `IdempotenciaConflicto` 422,
  `PagosInvalidos` 422, `StockInsuficiente` 409, `EstadoInvalido` 409,
  `RefMpDuplicada` 409; router delgado `routers/ventas.py` (`/api/ventas`,
  rutas fijas antes de `/{venta_id}`). Schemas estrictos: `VentaCreate
  {idempotency_key: UUID canónico (pattern), cliente_id?: str,
  lineas: list[LineaVentaIn] (1–100, sin producto repetido)}`, `LineaVentaIn
  {producto_id, cantidad: int > 0}`, `ConfirmarVentaRequest {pagos}`,
  `AnularVentaRequest {motivo}`, `VentaResponse`, `VentaResumen`,
  `VentaListResponse(PaginacionResponse)`; dinero con `_coerce_decimal` y
  `_serialize_money`. Códigos: alta `201` (nueva) / `200` (replay);
  confirmar y anular `200`.

## Risks / Trade-offs

- [Oversell por carrera entre dos puestos] → Locks de producto ordenados
  dentro de la transacción + revalidación bajo lock + `CHECK stock_nuevo >=
  0` en `movimiento_stock` y `productos`; test secuencial en SQLite y test
  concurrente con dos sesiones/hilos en Postgres (`pg_only`, CI).
- [Doble confirmación/anulación concurrente] → CAS de estado con
  `rowcount`; en Postgres el segundo UPDATE espera y no matchea; en SQLite
  los escritores se serializan. Test de reintento secuencial + test `pg_only`
  concurrente.
- [Deadlocks] → Orden global: fila de cabecera (venta/pedido) primero,
  productos por `id` ascendente después, igual que C-07; ajustes lockean un
  solo producto.
- [Atomicidad no probada] → Test con monkeypatch de `aplicar_movimiento` en
  `app.services.ventas` que falla en la 2ª línea: stock, movimientos, pagos,
  evento y estado intactos.
- [Redondeo/float] → Precio redondeado `ROUND_HALF_UP` en `Decimal`; SQLite
  devuelve NUMERIC vía float ⇒ conversión por `str` + `quantize`; caso
  `15.045 → 15.05` fija que no se usa redondeo bancario ni float.
- [El catálogo muestra `precio_venta` sin redondear y el borrador redondeado]
  → El POS debe mostrar el total del borrador; C-13 lo toma de ahí. Diferencia
  máxima medio centavo por unidad.
- [Borrador con precio viejo] → Aceptado (D5): los borradores viven segundos;
  si se confirma uno viejo se cobra el precio cotizado. Revisable con D5-a.
- [Borradores abandonados acumulan filas] → Inertes y excluidos de lecturas
  por defecto; limpieza diferida (D14).
- [Eventos outbox sin consumidor hasta C-11] → Volumen mínimo (uno o dos
  por venta); quedan pendientes y C-11 los procesa desde el inicio (emitirá
  FE de ventas previas a C-11 o las marcará: decisión de C-11).
- [Anulación sin registro de dinero devuelto] → Pregunta abierta de la KB;
  documentado en D13, no deuda oculta.
- [`ref_id` sin FK en `movimiento_stock`] → Igual que C-07; tras un
  downgrade quedarían movimientos `venta` con `ref_id` huérfano, el stock
  sigue consistente con el ledger.
- [Migración no ejecutable en el Postgres local] → SQLite real + SQL
  offline + `test_migration_pg.py` en CI (como C-07).
- [Mostrador con token robado anula] → No puede: `require_duena`; test 403.

## Migration Plan

1. Rama `change/c-10-ventas-mostrador`; merge solo vía PR con checks.
2. Deploy: `alembic upgrade head` (0007 crea 4 tablas vacías + 2 enums; sin
   backfill ni downtime: ningún endpoint existente las lee).
3. Desplegar API (router `ventas` nuevo + endpoint de historial en
   `clientes`; `services/stock.py` sin cambios).
4. Rollback: revert del deploy + `alembic downgrade -1` (drop de tablas y
   enums). Si ya hubo ventas, sus `MovimientoStock` tipo `venta` quedan con
   `ref_id` huérfano; el stock sigue consistente con el ledger; documentado.
5. Verificar: `GET /api/health`; smoke crear borrador → confirmar con
   efectivo → `GET /api/stock` con stock descontado y movimientos → anular
   como dueña → stock devuelto → historial del cliente.

## Decisiones a revisar por la usuaria

Governance CRÍTICO: el apply no arranca sin aprobación explícita. Cada una
tiene un default recomendado; cambiarla modifica spec y tareas:

1. **D4** borrador con líneas y total del servidor; confirmar recibe solo
   pagos (alternativa: confirmar con líneas + pagos; o un único POST).
2. **D5** precio congelado al crear el borrador, redondeo a centavos mitad
   hacia arriba, sin re-cotizar al confirmar (alternativas: re-cotizar y 409;
   redondear a pesos enteros).
3. **D3** anulación como movimiento `venta` de cantidad positiva, sin tocar
   el enum (alternativa: tipo `anulacion` nuevo, con `ALTER TYPE`
   irreversible).
4. **D7** stock insuficiente responde `409` con faltantes, chequeado también
   al crear el borrador (alternativa: `422` como el ajuste manual; o chequear
   solo al confirmar).
5. **D8** idempotencia por vendedor; replay `200`; misma clave con otro
   contenido `422` (alternativa: `409`; clave global).
6. **D9** reintentar confirmar/anular ya hechos devuelve `200` sin efectos
   (alternativa: `409` como C-07).
7. **D10** hasta 5 pagos mixtos, suma exacta, vuelto solo en el POS,
   `ref_mp` opcional/único (alternativas: un solo pago; persistir vuelto;
   `ref_mp` obligatorio).
8. **D11** outbox transaccional mínimo como hook de FE (alternativa: diferir
   todo a C-11).
9. **D12** el mostrador ve solo sus propias ventas también en el historial
   del cliente; ajenas ⇒ 404 (alternativa: historial completo del cliente
   para el mostrador).
10. **D13** anular exige motivo, conserva pagos, sin devolución de dinero ni
    límite de tiempo (responde la pregunta abierta Media de la KB por
    defecto; alternativa: registrar devolución/egreso).
11. **D14** sin edición ni descarte de borradores (alternativa: endpoint de
    descarte).

## Open Questions

- Ninguna bloqueante. Deferibles sin cambiar specs ni tareas: texto exacto de
  los `motivo` automáticos de los movimientos; tamaño de página (se adopta
  20 / máx. 100); si C-11 emitirá FE para ventas confirmadas antes de su
  despliegue (decisión de C-11 sobre eventos pendientes).
