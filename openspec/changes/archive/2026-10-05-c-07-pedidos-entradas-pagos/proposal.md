# Proposal

## Why

Hoy el stock solo entra por ajuste manual (C-05): no hay forma de pedirle mercadería a una distribuidora, registrar que llegó ni llevar la cuenta de lo que se le debe. US-006 y Flujo 2 (reposición por alerta) exigen que el stock entre **solo cuando la mercadería llega** (RN-CP-02), con el costo de la lista vigente (RN-CP-01) y con pagos a distribuidoras independientes de los pedidos (RN-CP-03). C-06 ya dejó distribuidoras y listas operables; sin este change, la alerta de bajo mínimo no tiene circuito de reposición y C-10/C-14 no tienen costos reales sobre los que calcular.

## What Changes

- Modelos nuevos: `PedidoCompra` (estado `pendiente`/`recibido`/`cancelado`) con líneas (`producto`, `cantidad`, `costo_unitario` tomado de la lista vigente), `EntradaStock` (una fila por producto recibido, append-only) y `PagoDistribuidora` (monto, método, fecha; sin vínculo con pedidos).
- `POST /api/compras/pedidos`: crea un pedido pendiente **sin mover stock** (dueña y mostrador). Lecturas `GET /api/compras/pedidos` (paginado, filtro por estado/distribuidora) y `GET /api/compras/pedidos/{id}` (detalle con líneas y entradas) — necesarias para que mostrador encuentre el pedido a recibir.
- `POST /api/compras/pedidos/{id}/recibir`: en **una sola transacción** suma stock de todas las líneas, crea un `MovimientoStock` tipo `entrada` por línea (con `ref_id` a su entrada), actualiza `Producto.costo` (el precio sugerido se recalcula solo, RN-PR-01), crea las `EntradaStock` y marca el pedido `recibido`. Recibir un pedido ya recibido o cancelado responde `409` sin efectos (nunca suma stock dos veces).
- `POST /api/compras/pedidos/{id}/cancelar` (solo dueña): única forma de llegar al estado `cancelado` ya definido en el modelo; no mueve stock.
- `POST /api/compras/pagos`, `GET /api/compras/pagos`, `DELETE /api/compras/pagos/{id}` (anulación = soft-delete) y `GET /api/compras/distribuidoras/{id}/cuenta` (total recibido − total pagado = saldo): cuenta corriente simple, **solo dueña**.
- Refactor interno del servicio de stock: el ajuste manual (C-05) conserva contrato y comportamiento; se separa un núcleo sin commit para que recibir agrupe N movimientos en una transacción.
- Migración Alembic `0006` (hija de `0005`): tablas `pedido_compra`, `linea_pedido`, `entrada_stock`, `pago_distribuidora` + enums, checks e índices. (CHANGES.md dice "Migración 005": `0005` ya existe; se corrige en apply/archive.)
- Tests TDD RED-first para RN-CP-01/02/03: pedido no mueve stock, recibir sí mueve + actualiza costo + es atómico, pagos independientes, RBAC por rol.

## Capabilities

### New Capabilities

- `compras`: circuito de compras a distribuidoras — pedidos con estados, recepción transaccional que genera entradas de stock y actualiza costos, cancelación, pagos independientes y saldo simple por distribuidora (US-006, RN-CP-01..03).

### Modified Capabilities

- (vacío — `stock-alertas` ya especifica `MovimientoStock` con tipo `entrada` y `ref_id`, y la regla "ningún cambio de stock sin movimiento", que este change cumple sin modificarla; el ajuste manual mantiene su contrato. `catalogo-productos` ya especifica `precio_venta = costo × (1 + margen)` calculado: actualizar el costo desde una entrada lo respeta sin cambiar la requirement.)

## Impact

- Nuevo: `backend/app/routers/compras.py` (+ registro en `main.py`), `backend/app/services/compras.py`, modelos y schemas nuevos, migración `0006`, tests `test_compras_*.py`.
- Modificado (sin cambio de contrato): `backend/app/services/stock.py` (extracción de núcleo sin commit + soporte de `ref_id`); suite C-05 debe seguir verde.
- Sin breaking changes en endpoints existentes. Sin frontend (llega en C-13).
- Non-goals explícitos: recepción parcial/backorder, costo promedio ponderado, edición de pedidos pendientes, vínculo pago↔pedido, reportes de compras (C-14).
