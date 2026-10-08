# Design

> Governance **BAJO** (lectura y agregados). La única excepción es D1, que
> toca la creación de ventas (dominio CRÍTICO de C-10) para congelar el
> costo: está listada primera en "Decisiones para revisión" y conviene
> aprobarla explícitamente antes del apply.

## Context

Ver `proposal.md` (Why) y `specs/reportes/spec.md` + `specs/ventas/spec.md`
(contrato). Estado verificado en código y artefactos:

- `alembic heads` → `0007` (`0007_ventas.py`, C-10). La nueva revisión es
  `0008`.
- `LineaVenta` (`backend/app/models.py`) congela `precio_unit` y `subtotal`
  pero **no el costo**; es append-only (listeners `before_update/delete`).
  `services/ventas.py::crear_venta` calcula `precio_unit` con
  `_precio_unitario(producto)` desde `costo` y `margen_pct` al crear el
  borrador; `confirmar_venta` no re-cotiza (C-10 D5). C-07
  (`services/compras.py`, D6) copia el costo pactado a `Producto.costo` en
  cada recepción, así que el costo actual cambia con cada compra.
  RN-PR-04: "cambio de costo … no reescribe ventas históricas".
- `Venta`: `estado` (`borrador`/`confirmada`/`anulada`), `confirmada_at`
  seteado en el CAS con `datetime.now(timezone.utc)`, `anulada_at`,
  `total Numeric(12,2)`, `usuario_id` (vendedor). Índices existentes:
  `(cliente_id, created_at)`, `(usuario_id, created_at)`, `(created_at)`;
  `linea_venta`: unique `(venta_id, producto_id)` (cubre `venta_id`) e
  índice `(producto_id)` (C-10 D2 lo dejó "para C-14 más vendidos");
  `pago_venta`: índice `(venta_id)`.
- Stock: `routers/stock.py` (`GET /api/stock`, `/api/stock/alertas`) y
  `workers/stock_alerts.py::ids_bajo_minimo(db)` usan el predicado
  `activo AND stock_actual <= stock_minimo` (C-05 D3). `orden=rotacion` de
  C-05 es cobertura sobre el mínimo (no había ventas, C-05 D4).
- Convenciones: handlers sync con `Session`; schemas
  `ConfigDict(extra="forbid", strict=True)`, `_coerce_decimal`,
  `_serialize_money`, `PaginacionResponse`; query params como modelo
  Pydantic (`Annotated[VentaFiltros, Query()]` en `routers/ventas.py`);
  `deps.require_role(...)`, `require_duena`, `get_current_user`; dinero de
  SQLite convertido vía `str` (C-07 `_a_decimal`, C-10 `_precio_unitario`).
- `listar_ventas` (C-10 D15) no asume zona: recibe datetimes aware y los
  lleva a UTC. No hay `tzdata` en `requirements.txt` (en Windows
  `zoneinfo` no tiene base de zonas sin ese paquete).
- Redis: solo lo usan auth y el job de alertas; C-10 dejó `evento_outbox`
  sin consumidor (C-10 D11 mencionó que C-14 podría usarlo para invalidar
  cache). El frontend tiene solo `HomePage`, `PosPage`, `StockPage` de
  scaffold; la SPA real (routing, auth, React Query) es C-13.
- KB: US-009 (dueña: ventas del día, más vendidos, reposición); matriz
  RBAC "Reportes: dueña ver / mostrador ver básico"; `02` lista
  `/reportes` con márgenes; métrica "alertas antes del quiebre en
  productos top".
- Entorno: el Postgres local falla al migrar con `UnicodeDecodeError`
  preexistente; 0006/0007 se validaron con SQLite real + SQL offline +
  `pg_only` en CI (que ahora tiene servicio Postgres).

## Goals / Non-Goals

**Goals:**

- Números verdaderos: cada importe se puede reconstruir a mano desde las
  líneas y pagos de ventas confirmadas; el margen nunca usa un costo que
  no era el del momento de la venta.
- Un único criterio de "qué venta cuenta y en qué día" compartido por los
  cuatro reportes y testeado en el borde de medianoche.
- Reportes siempre frescos, sin infraestructura nueva.
- Tocar el dominio de ventas lo mínimo: una columna y su asignación en
  `crear_venta`; `confirmar_venta`, `anular_venta` y `services/stock.py`
  sin cambios.

**Non-Goals:**

- Exportes CSV/PDF, gráficos, series diarias, reportes programados o por
  email, comisiones por vendedor, impuestos/IVA, arqueo de caja,
  sugerencia automática de cantidades a pedir, costo promedio ponderado o
  FIFO, frontend de reportes (C-13).

## Decisions

- **D1 — Costo congelado en la línea (migración `0008`), tomado al crear
  el borrador.** *(punto 1; revisar — toca C-10)* Columna
  `linea_venta.costo_unit Numeric(10,2) NULL` con `CHECK (costo_unit IS
  NULL OR costo_unit > 0)`. `crear_venta` la completa con
  `Decimal(str(producto.costo))` en el mismo loop donde fija `precio_unit`:
  precio y costo se congelan **juntos** en el borrador (no en `confirmar`,
  que no re-cotiza el precio; congelar el costo en otro momento haría que
  precio y costo de una misma línea provinieran de instantes distintos).
  Consecuencias concretas sobre C-10: (1) `LineaVenta` gana la columna;
  (2) `crear_venta` asigna un campo más; (3) `VentaResponse`/
  `LineaVentaResponse` **no cambian** (el mostrador ve ventas y nunca debe
  ver costos); (4) `confirmar_venta`, `anular_venta`, el replay
  idempotente y la suite de C-10 siguen igual — es la red de seguridad.
  Delta MODIFIED del requirement "Crear venta en borrador…" + ADDED de la
  migración. **Filas históricas**: `NULL`, sin backfill — completarlas con
  el costo actual reintroduciría exactamente el error que se quiere
  evitar. Los reportes las excluyen del margen y las cuentan aparte
  (`lineas_sin_costo`, `ingresos_sin_costo`), así nunca se mezclan números
  reales con estimados. En la práctica no habrá filas históricas: el
  sistema aún no está desplegado (C-15 pendiente), así que el `NULL` es
  defensivo; se mantiene nullable para que la migración no falle sobre
  bases de desarrollo con ventas. Alternativas: (b) margen con el
  `Producto.costo` actual y advertencia documentada — sin migración, pero
  el número es falso en cuanto hay una recepción con otro costo, que es lo
  normal (C-07 actualiza costo en cada entrada); (c) diferir `/margenes` —
  honesto, pero deja fuera un reporte que la KB lista y que con (a) cuesta
  una columna. **Qué costo**: el `Producto.costo` vigente, que tras C-07 es
  el último costo de compra (costo de reposición), no un promedio
  ponderado ni FIFO; suficiente para "decidir compras" y coherente con
  `precio_venta = costo × (1 + margen_pct)`.

- **D2 — Sin Redis ni cache: agregados SQL al vuelo.** *(punto 2;
  revisar — recorta CHANGES.md)* Volumen esperado de un local único: del
  orden de 100–300 ventas/día con ~3 líneas ⇒ ~30–100 k líneas/año. El
  reporte más pesado (márgenes o más vendidos de 366 días) agrega a lo
  sumo ~100 k filas por índice: milisegundos en Postgres. Un cache
  agregaría invalidación tras `confirmar`/`anular` (consumir el outbox o
  hooks post-commit), un modo de falla (Redis caído ⇒ fallback) y números
  viejos durante el TTL, a cambio de nada medible. Sin cache, la frescura
  es trivialmente correcta y se testea ("Reportes siempre actualizados").
  Se descarta de C-14: "Jobs Redis para agregados pesados; cache TTL
  corto" y el test "cache invalidation tras venta" (reemplazado por los
  tests de reflejo inmediato). Si algún día hiciera falta, el outbox de
  C-10 ya emite `venta.confirmada`/`venta.anulada` para invalidar. La
  tarea 9.3 actualiza CHANGES.md al archivar. Alternativa: cache TTL corto
  (30–60 s) en Redis por clave de reporte+parámetros con fallback a DB —
  descartada por lo anterior.

- **D3 — Solo backend; las páginas de reportes pasan a C-13.** *(punto 3;
  revisar)* El frontend no tiene routing, auth con refresh, React Query ni
  guardas por rol: todo eso es el alcance de C-13. Hacer `/reportes/*` en
  C-14 obligaría a construir esa infraestructura acá (o a duplicarla) y
  C-14 dejaría de ser un change BAJO y chico. El contrato HTTP de C-14
  (schemas estrictos, OpenAPI generado por FastAPI) es lo que C-13
  consume. La tarea 9.3 mueve la línea "Frontend: `features/reportes` +
  páginas `/reportes/*` (solo dueña ve completo, mostrador ve básico)" a
  §[C-13] al archivar. Alternativa: un change nuevo `C-16
  reportes-frontend` posterior a C-13 (más limpio si C-13 ya es grande);
  la dueña decide.

- **D4 — Qué venta cuenta y en qué día.** *(punto 4; revisar el
  tratamiento de anuladas)* Solo `estado = 'confirmada'`. Imputación por
  `confirmada_at` (el momento en que salió la mercadería y entró el
  dinero), no por `created_at` del borrador (borrador y confirmación
  suelen distar segundos, pero un borrador de las 23:59:58 confirmado a
  las 00:00:03 pertenece al día siguiente). Anuladas: excluidas de todo
  agregado; en ventas-dia se informan como contador aparte (`anuladas`)
  imputado también por `confirmada_at`, de modo que el día "pierde" la
  venta cuando se anula (los reportes describen el estado actual; una
  anulación de días después cambia el reporte del día original, lo cual
  es lo correcto para decidir compras). Borradores: nunca. Alternativa:
  imputar la anulación al día de `anulada_at` como egreso — es lógica de
  arqueo de caja, fuera de alcance.

- **D5 — Día local: bordes calculados en Python, comparación por rango en
  UTC.** *(punto 4)* Setting `reportes_tz: str =
  "America/Argentina/Buenos_Aires"` (env `REPORTES_TZ`, validado con
  `zoneinfo.ZoneInfo` al cargar settings). Para un día local `d`: `inicio
  = datetime.combine(d, time.min, tz).astimezone(UTC)`, `fin = inicio del
  día siguiente`; filtro `confirmada_at >= inicio AND confirmada_at <
  fin`. Un período `desde..hasta` es `[inicio(desde), inicio(hasta + 1))`.
  Sin funciones de zona en SQL (`AT TIME ZONE` no existe en SQLite): la
  misma consulta corre en Postgres y en los tests SQLite, y usa el índice
  de D11 (un `date_trunc` sobre la columna no lo usaría). Mismo enfoque
  que `listar_ventas` (aware → UTC). "Hoy" =
  `datetime.now(tz).date()` vía una función `hoy()` del servicio que los
  tests reemplazan con monkeypatch. Se agrega `tzdata` a
  `requirements.txt` (paquete de datos puro del proyecto Python;
  necesario en Windows y en imágenes slim sin `/usr/share/zoneinfo`).
  Argentina hoy no tiene horario de verano, pero usar `zoneinfo` (y no un
  offset fijo −3) lo cubre si vuelve.

- **D6 — Parámetros de período.** *(punto 4)* `ventas-dia?fecha=` (un día,
  default hoy). `mas-vendidos` y `margenes`: `desde`/`hasta` como `date`
  (ambos inclusive); default últimos 30 días incluido hoy; con un solo
  borde, el otro es hoy (`hasta`) o `hasta − 29` (`desde`); `desde >
  hasta` ⇒ 422; más de 366 días ⇒ 422 (un año, también bisiesto). Fechas
  futuras se aceptan y dan reportes vacíos (no hay regla que las prohíba).
  El modelo de query usa `date` estricto: un datetime o un formato que no
  sea ISO `YYYY-MM-DD` da 422. Modelos de query con `extra="forbid"`
  (FastAPI ≥ 0.115 lo respeta para modelos de query) ⇒ parámetros
  desconocidos 422, así un typo como `hast=` no se ignora en silencio.

- **D7 — Ventas del día: campos y cálculo.** Ver spec. `total_vendido =
  Σ venta.total`; `unidades = Σ linea.cantidad`; `por_metodo` agrega
  `pago_venta.monto` y cuenta pagos agrupando por método, devolviendo los
  cuatro métodos siempre en orden fijo (el consumidor no tiene que
  rellenar huecos); `ticket_promedio` en `Decimal` `ROUND_HALF_UP`. Por
  RN-VT-04 `Σ por_metodo.monto == total_vendido`; un test lo fija como
  invariante. Tres consultas agregadas simples (ventas, líneas, pagos) con
  el mismo filtro base, más una para anuladas.

- **D8 — Más vendidos: por unidades por defecto, top-N sin paginar.**
  *(revisar el default)* "Más vendido" en un petshop es rotación física
  (qué reponer); por eso `orden=cantidad` por defecto y `orden=monto` como
  opción. Desempate: la otra métrica descendente y `producto_id` (no el
  nombre: la collation difiere entre SQLite y Postgres y los nombres
  pueden repetirse). `limite` 1–50, default 10, sin paginación (es un
  ranking). `GROUP BY linea_venta.producto_id` con join a `productos` para
  `sku`/`nombre`/`activo`; incluye productos dados de baja (vendieron en
  el período; ocultarlos falsearía el ranking).

- **D9 — Reposición = bajo mínimo ∪ cobertura corta.** *(revisar
  umbral)* `rotación` = unidades vendidas en ventas confirmadas de los
  últimos `dias` días locales (default 30, 7–180). `venta_diaria =
  unidades / dias`; `cobertura_dias = floor(stock_actual × dias /
  unidades)` calculado con enteros (sin pasar por `venta_diaria`
  redondeada; `floor` es conservador: 1,9 días se informa como 1). Se
  listan productos activos con (a) el mismo predicado que la alerta de
  C-05 (`stock_actual <= stock_minimo`, reutilizando
  `workers.stock_alerts.ids_bajo_minimo` o una expresión compartida, sin
  duplicar la regla) o (b) ventas en la ventana y `cobertura_dias <=
  cobertura_max_dias` (default 7, 1–90). (b) es lo que agrega valor sobre
  `/stock/alertas`: detecta productos top que se agotan antes de tocar el
  mínimo (métrica de éxito de la KB). La rotación se obtiene de
  `linea_venta` de ventas confirmadas (no del ledger de movimientos), así
  las anuladas no cuentan sin restar signos. Sin paginación (como
  `/stock/alertas`; el conjunto es acotado) y sin costos ni importes (lo
  ve el mostrador, que registra entradas y crea pedidos). No se reemplaza
  `orden=rotacion` de `GET /api/stock` (spec `stock-alertas` intacta).
  Alternativas: solo bajo mínimo + columnas de rotación (pierde el caso
  "agotándose sobre el mínimo"); cantidad sugerida a pedir (`venta_diaria
  × días objetivo + mínimo − stock`) — útil, pero inventa una regla de
  negocio que la KB no define; queda para cuando la dueña la pida.

- **D10 — Márgenes: markup sobre costo, por producto y total, paginado.**
  *(revisar la definición del %)* `margen_bruto = ingresos − costo`;
  `margen_pct = margen_bruto / costo` (4 decimales, `ROUND_HALF_UP`), el
  mismo sentido que `Producto.margen_pct` (RN-PR-01: `precio = costo × (1 +
  margen)`), así la dueña compara el margen realizado con el configurado
  (difieren solo por el redondeo a centavos del precio). Alternativa:
  margen sobre precio (`margen_bruto / ingresos`, "margen comercial") —
  habitual en contabilidad, pero con el mismo nombre que el campo del
  catálogo confundiría; si se quiere, se agrega como campo aparte. Solo
  líneas con `costo_unit` (D1); las demás van a `lineas_sin_costo` /
  `ingresos_sin_costo` en `totales`. Paginado 20/100 (el catálogo puede
  tener cientos de productos vendidos en un año) con `totales` calculados
  sobre todo el período, no sobre la página. Orden `margen_bruto DESC,
  producto_id`.

- **D11 — Índice `(estado, confirmada_at)` en `0008`.** *(punto 6)* Todos
  los reportes filtran `estado = 'confirmada' AND confirmada_at` en rango;
  los índices de C-10 son sobre `created_at`. Con el volumen de D2 un scan
  sería tolerable, pero la migración `0008` ya existe por D1 y el índice
  compuesto (igualdad primero, rango después) mantiene los reportes
  acotados a medida que pasan los años. `linea_venta(producto_id)` y
  `(venta_id, …)` y `pago_venta(venta_id)` ya existen: no se agregan
  más. Migración manual espejando `0007`: `op.add_column` +
  `op.create_check_constraint` dentro de `batch_alter_table` (SQLite no
  agrega checks con `ALTER`), `op.create_index`; downgrade inverso.
  Validación igual que 0006/0007: test SQLite real
  (`test_migration_0008.py`: esquema previo, `stamp 0007`, insertar una
  línea previa, upgrade ⇒ costo `NULL`, check activo, downgrade sin
  residuos, re-upgrade), SQL offline (`alembic upgrade 0007:0008 --sql`)
  y casos `pg_only` en `test_migration_pg.py` que corre CI.

- **D12 — RBAC: "ver básico" = ventas del día propias + reposición.**
  *(punto 5; revisar)*

  | Endpoint | duena | mostrador |
  |---|---|---|
  | `GET /api/reportes/ventas-dia` | todas (`alcance=todas`) | solo sus ventas (`alcance=propias`) |
  | `GET /api/reportes/reposicion` | ✓ | ✓ (sin importes) |
  | `GET /api/reportes/mas-vendidos` | ✓ | 403 |
  | `GET /api/reportes/margenes` | ✓ | 403 |

  Coherente con la matriz de ventas ("mostrador: ver propias", C-10 D12)
  y con que el mostrador ya ve stock y alertas. Más vendidos expone la
  facturación por producto del negocio y márgenes expone costos: solo
  dueña. Lecturas compartidas con `require_role("duena", "mostrador")`
  explícito (un rol futuro no hereda acceso), las de dueña con
  `require_duena`. Sin `404`: los reportes no direccionan recursos.
  Alternativa: mostrador también ve más vendidos por unidades (sin
  `monto`) — útil en el mostrador, pero exige un schema distinto por rol;
  se deja para pedido explícito.

- **D13 — Capas y schemas.** `services/reportes.py` de solo lectura (sin
  `commit`): `hoy()`, `bordes_utc(desde, hasta)`, `ventas_dia`,
  `mas_vendidos`, `reposicion`, `margenes`; funciones puras para los
  cálculos derivados (`ticket_promedio`, `cobertura_dias`, `margen_pct`)
  testeables sin base. Sumas de SQLite (float) convertidas vía `str` +
  `quantize(0.01)`. Router delgado `routers/reportes.py` (`prefix
  "/reportes"`, registrado en `main.py`). Schemas estrictos de respuesta
  (`extra="forbid"`, dinero con `_serialize_money`, `margen_pct` con 4
  decimales, fechas como `date`): `VentasDiaResponse`, `MetodoTotal`,
  `AnuladasResumen`, `MasVendidosResponse`/`ProductoVendido`,
  `ReposicionResponse`/`ReposicionItem`, `MargenesResponse(Paginacion…)`/
  `MargenProducto`/`MargenesTotales`; modelos de query
  `VentasDiaQuery`, `PeriodoQuery` (con la validación de D6 en un
  `model_validator`), `MasVendidosQuery`, `ReposicionQuery`,
  `MargenesQuery`.

## Risks / Trade-offs

- [D1 modifica código de un dominio CRÍTICO] → Cambio mínimo y aditivo (un
  campo asignado en `crear_venta`), sin tocar confirmar/anular; la suite
  completa de C-10 corre como safety net antes y después; aprobación
  explícita pedida.
- [Margen con último costo, no promedio] → Documentado en D1; el reporte
  dice "margen con el costo vigente al vender". Si la dueña necesita costo
  promedio, es otro change (requiere valorizar inventario).
- [Filas sin costo distorsionan márgenes] → Nunca se mezclan: se informan
  aparte (D10) y hoy no existen (sistema sin desplegar).
- [Borde de medianoche / zona mal configurada] → Tests con instantes
  02:30Z y 03:00Z (borde exacto: 00:00 ART es inclusivo en el día nuevo);
  `REPORTES_TZ` inválido falla al arrancar (validación en settings).
- [`tzdata` ausente en algún entorno] → Dependencia explícita en
  `requirements.txt`; un test instancia la zona por defecto.
- [Sumas NUMERIC en SQLite como float] → Conversión `str` + `quantize`; los
  tests usan importes con centavos (100.01) para detectar errores de float.
- [Reportes lentos con años de datos] → Índice D11 + período máximo de 366
  días; si hiciera falta, cache o tablas resumen sobre el outbox (D2).
- [Anular cambia reportes de días pasados] → Intencional (D4); documentado
  en la spec ("los reportes reflejan el estado actual").
- [CHANGES.md promete Redis y frontend en C-14] → Recorte explícito en D2/D3
  y tarea 9.3 que actualiza CHANGES.md al archivar.
- [Migración no ejecutable en el Postgres local] → SQLite real + SQL
  offline + `pg_only` en CI (como C-07/C-10).

## Migration Plan

1. Rama `change/c-14-reportes-basicos`; merge solo vía PR con checks.
2. Deploy: `alembic upgrade head` (0008 agrega una columna nullable y un
   índice; sin backfill; en Postgres `ADD COLUMN` nullable es solo
   metadata y el índice sobre una tabla chica es instantáneo).
3. Desplegar la API (router `reportes` nuevo; `crear_venta` empieza a
   congelar el costo desde ese momento).
4. Rollback: revert del deploy + `alembic downgrade -1` (drop del índice,
   del check y de la columna; los costos congelados mientras tanto se
   pierden, sin efecto en stock ni en ventas).
5. Verificar: `GET /api/health`; smoke crear y confirmar una venta →
   `ventas-dia` la muestra → `margenes` con su costo → `reposicion` → como
   mostrador, `ventas-dia` propias y `mas-vendidos` 403.

## Decisiones para revisión

Governance BAJO: el apply puede avanzar con los defaults, salvo D1, que
conviene aprobar explícitamente porque toca la venta. Cambiar cualquiera
modifica spec y tareas:

1. **D1** congelar `costo_unit` en `linea_venta` al crear el borrador
   (migración 0008, cambio mínimo en `crear_venta` de C-10, sin exponerlo
   en ventas; filas previas `NULL` sin backfill) — alternativas: margen con
   costo actual y advertencia; diferir `/margenes`.
2. **D1** el costo es el último costo de compra (`Producto.costo`), no
   promedio ponderado ni FIFO.
3. **D2** sin Redis ni cache; se quita esa línea de CHANGES.md §[C-14] —
   alternativa: cache TTL corto con invalidación por outbox.
4. **D3** sin frontend; la línea de páginas `/reportes/*` pasa a §[C-13] —
   alternativa: change nuevo C-16 reportes-frontend.
5. **D4** imputación por fecha de confirmación; anuladas excluidas y
   mostradas aparte en el día de su confirmación — alternativa: imputar la
   anulación al día en que se anula.
6. **D8** más vendidos ordena por unidades por defecto, top 10 (máx. 50) —
   alternativa: por monto por defecto.
7. **D9** reposición = bajo mínimo ∪ cobertura ≤ 7 días con ventana de 30
   días, sin cantidad sugerida — alternativas: solo bajo mínimo; agregar
   cantidad sugerida.
8. **D10** `margen_pct` sobre costo (markup, igual que el catálogo) —
   alternativa: sobre precio.
9. **D12** mostrador ve ventas del día propias y reposición; más vendidos y
   márgenes 403 — alternativa: mostrador también ve más vendidos por
   unidades.

## Open Questions

- Ninguna bloqueante. Deferibles sin cambiar specs ni tareas: valores por
  defecto exactos de `dias`/`cobertura_max_dias` (se adoptan 30/7,
  ajustables por parámetro) y si C-13 agrupa las páginas de reportes bajo
  una sola ruta con tabs.
