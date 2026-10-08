# Proposal

## Why

Con C-10 archivado, el sistema ya registra ventas, pero la dueña no tiene forma de leerlas en conjunto: US-009 pide **ventas del día, más vendidos y reposición para decidir compras**, y la métrica de éxito "alertas de mínimo disparadas antes del quiebre en productos top" (`01_vision_y_objetivos.md`) exige cruzar stock con rotación real, algo que la alerta de C-05 (solo `stock <= mínimo`) no hace. Además, para mostrar márgenes verdaderos hace falta el **costo al momento de la venta**: hoy `LineaVenta` congela `precio_unit` pero no el costo, y C-07 reescribe `Producto.costo` en cada recepción, así que un margen calculado con el costo actual mentiría después de cualquier compra (RN-PR-04: los cambios de costo no reescriben ventas históricas).

## What Changes

- `GET /api/reportes/ventas-dia?fecha=` (dueña y mostrador): cantidad de ventas, total vendido, ticket promedio, unidades, desglose por método de pago y ventas anuladas aparte, para un día local de Argentina. El mostrador ve solo sus propias ventas.
- `GET /api/reportes/mas-vendidos?desde=&hasta=&orden=&limite=` (solo dueña): ranking de productos por unidades o por monto en un período.
- `GET /api/reportes/reposicion?dias=&cobertura_max_dias=` (dueña y mostrador): productos activos bajo mínimo (mismo criterio que la alerta de C-05) más los que, por su rotación de los últimos N días, se quedan sin stock en pocos días; con unidades vendidas, venta diaria y días de cobertura. Sin datos de dinero.
- `GET /api/reportes/margenes?desde=&hasta=` (solo dueña): ingresos, costo, margen bruto y margen % por producto y totales, calculados con el costo congelado en cada línea de venta; las líneas sin costo congelado se informan aparte y no se mezclan.
- Solo cuentan ventas `confirmada`, imputadas al día local de su confirmación; los borradores nunca cuentan y las anuladas solo aparecen como contador separado en ventas del día.
- **Costo congelado en la línea de venta**: al crear el borrador (mismo momento en que se congela el precio) cada línea guarda el costo unitario vigente del producto. No se expone en las respuestas de ventas (el mostrador nunca ve costos). Migración Alembic `0008` (hija de `0007`): columna `costo_unit` nullable en `linea_venta` + índice de reportes sobre `venta (estado, confirmada_at)`.
- Zona horaria del negocio configurable por env (`REPORTES_TZ`, default `America/Argentina/Buenos_Aires`) y dependencia `tzdata` para que funcione en Windows y en imágenes slim.
- **Recorte de alcance respecto de CHANGES.md** (justificado en `design.md`): sin jobs Redis ni cache (agregados SQL al vuelo, siempre frescos tras confirmar o anular); sin frontend (las páginas `/reportes/*` pasan a C-13, que monta la infraestructura de la SPA). El archive actualiza esas líneas de CHANGES.md.
- Tests TDD RED-first: agregados correctos, aislamiento por día local (borde de medianoche Argentina vs UTC), exclusión de borradores y anuladas, reflejo inmediato de una venta o anulación, RBAC, validación de parámetros y migración `0008`.

## Capabilities

### New Capabilities

- `reportes`: reportes de solo lectura para decidir compras (US-009) — ventas del día, más vendidos, reposición por mínimo y rotación, y márgenes con costo histórico — con imputación por día local, RBAC dueña/mostrador ("ver" / "ver básico") y validación estricta de parámetros.

### Modified Capabilities

- `ventas`: el requirement "Crear venta en borrador con precios del servidor" pasa a congelar también el costo unitario del producto en cada línea (no visible en la API de ventas), y se agrega el requirement "Migración 0008 agrega el costo congelado a las líneas de venta". El resto de los requirements de ventas no cambia.
- (`stock-alertas` no se modifica: `reposicion` reutiliza el criterio de bajo mínimo `stock_actual <= stock_minimo` sin cambiar `GET /api/stock` ni `/api/stock/alertas`. `auth-rbac` ya fija "Reportes: dueña ver / mostrador ver básico"; este change concreta qué es "básico" dentro de la spec `reportes`.)

## Impact

- Nuevo: `backend/app/services/reportes.py`, `backend/app/routers/reportes.py` (+ registro en `main.py`), schemas de reportes en `backend/app/schemas.py`, setting `reportes_tz` en `backend/app/core/config.py`, migración `backend/alembic/versions/0008_reportes.py`, tests `test_reportes_*.py`, `test_migration_0008.py` y casos nuevos en `test_migration_pg.py`; `tzdata` en `backend/requirements.txt`.
- Modificado (dominio de ventas, gobernanza CRÍTICA de C-10): `LineaVenta.costo_unit` en `backend/app/models.py` y una línea en `services/ventas.py::crear_venta` que lo completa; `VentaResponse` y el resto del contrato de ventas no cambian. Sin breaking changes.
- Sin cambios: `services/stock.py`, `routers/stock.py`, `workers/stock_alerts.py`, frontend.
- Governance **BAJO** para los reportes; el punto que toca la venta (costo congelado, design D1) se lista en "Decisiones para revisión" para aprobación explícita antes del apply.
- Non-goals: exportes CSV/PDF, gráficos, reportes programados o por email, comisiones por vendedor, impuestos/IVA, cierre de caja (arqueo), sugerencia automática de cantidades a comprar, frontend de reportes (C-13).
