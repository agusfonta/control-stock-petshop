# Tasks

## 1. Safety net y núcleo transaccional del servicio de stock (D3)

- [x] 1.1 Ejecutar suite actual (`pytest backend/tests -x -q`) y registrar baseline "N tests passing" (en especial `test_stock_ajuste.py` y `test_stock_movimientos.py`); si algo falla, reportarlo como pre-existente y no tocarlo
- [x] 1.2 RED: escribir `backend/tests/test_stock_nucleo.py` con tests failing de `aplicar_movimiento()`: no hace commit (tras `rollback()` del llamador ni stock ni movimiento persisten), dos llamadas + un solo commit persisten ambas, persiste `ref_id` y `tipo="entrada"`, `delta=0` y `stock_nuevo<0` levantan `StockError`/`StockNegativo`, producto inexistente levanta `ProductoNoEncontrado`; verificar que fallan por función inexistente
- [x] 1.3 GREEN + REFACTOR: extraer `aplicar_movimiento(db, producto_id, cantidad_delta, tipo, usuario, motivo=None, ref_id=None)` en `backend/app/services/stock.py` (lock `FOR UPDATE` salvo SQLite, valida, muta, agrega movimiento, `flush()` sin commit/rollback) y reescribir `ajustar()` como envoltorio con la misma firma, validaciones, excepciones y commit/rollback; verificar `test_stock_nucleo.py` verde y `test_stock_ajuste.py` + `test_stock_movimientos.py` verdes SIN modificarlos (mismo conteo que el baseline de 1.1)

## 2. Modelos de compras y migración 0006 (D1, D2)

- [x] 2.1 RED: escribir `backend/tests/test_compras_modelos.py` con tests failing: `LineaPedido` con `cantidad=0` y `costo_unitario<=0` rechazados por check, producto repetido en un pedido rechazado por unique, `EntradaStock` duplicada `(pedido_id, producto_id)` rechazada, update/delete de `EntradaStock` bloqueados (`InvalidRequestError`), `PagoDistribuidora` con `monto<=0` rechazado, `PedidoCompra.estado` default `pendiente`; verificar que fallan por modelos inexistentes
- [x] 2.2 GREEN: agregar `PedidoCompra`, `LineaPedido`, `EntradaStock` (listeners append-only como `MovimientoStock`) y `PagoDistribuidora` a `backend/app/models.py` (+ `__all__`, enums `ESTADO_PEDIDO`/`METODO_PAGO_DISTRIBUIDORA`, tipos de D2) y verificar `pytest backend/tests/test_compras_modelos.py` verde
- [x] 2.3 Crear `backend/alembic/versions/0006_compras.py` manual (`down_revision="0005"`, 4 tablas, FKs, checks, uniques, índices de D2, enums auto-creados y dropeados con `checkfirst` como `0004`) y agregar a `backend/tests/test_migration_pg.py` un test de que `0006` crea las 4 tablas y rechaza `cantidad=0`; verificar `alembic upgrade head` → `downgrade -1` → `upgrade head` sin residuos en SQLite y Postgres

## 3. Schemas Pydantic de compras (D11)

- [x] 3.1 RED: escribir `backend/tests/test_compras_schemas.py` con validación failing de `PedidoCreate` (líneas vacías / >100 → error, `cantidad` 0 / negativa / float / bool → error, `producto_id` repetido → error, `costo_unitario` presente → error por `extra=forbid`) y `PagoCreate` (`monto` 0 / negativo → error, `metodo` fuera de lista → error, `pedido_id` presente → error, `fecha` omitida ok); verificar que fallan por schemas inexistentes
- [x] 3.2 GREEN: agregar a `backend/app/schemas.py` `LineaPedidoCreate`, `PedidoCreate`, `LineaPedidoResponse` (con `subtotal`), `EntradaStockResponse`, `PedidoResponse` (con `total_estimado`, `lineas`, `entradas`), `PedidoListResponse(PaginacionResponse)`, `PagoCreate`, `PagoResponse`, `PagoListResponse`, `CuentaDistribuidoraResponse` (estrictos + `_coerce_decimal` + serializador Decimal) y verificar `test_compras_schemas.py` verde

## 4. Crear y consultar pedidos (RN-CP-02)

- [x] 4.1 RED: escribir `backend/tests/test_compras_pedidos.py` con tests failing: crear-201-sin-mover-stock-ni-movimientos, costo-de-línea-desde-lista (800 con costo base 1000), costo-sin-lista-usa-producto (1000), mostrador-201-como-creador, anónimo-401, distribuidora/producto-inexistente-404, distribuidora/producto-inactivo-422, listar-filtra-`estado=pendiente`, `estado` inválido-422, detalle-con-subtotales-y-total (10×800 + 5×200 = 9000), detalle-inexistente-404; verificar que fallan (router inexistente)
- [x] 4.2 GREEN: crear `backend/app/services/compras.py::crear_pedido` (valida referencias D11, snapshot de costo D6, sin tocar stock) y `backend/app/routers/compras.py` con `POST/GET /compras/pedidos` y `GET /compras/pedidos/{id}` (`require_role("duena","mostrador")` en escritura, `get_current_user` en lectura, paginado 20/100, errores de dominio → HTTP), registrarlo en `backend/app/main.py`; verificar `test_compras_pedidos.py` verde
- [x] 4.3 TRIANGULATE: agregar casos filtro-por-`distribuidora_id`, pedido-de-dos-líneas-con-costos-de-orígenes-distintos (una con lista, otra sin) y cambio-posterior-de-lista-no-altera-snapshot; verificar que pasan (o generalizar si rompen)

## 5. Recibir pedido en una transacción (RN-CP-01/02, TDD estricto, D3/D4/D6)

- [x] 5.1 RED: escribir `backend/tests/test_compras_recibir.py` con tests failing: recibir-suma-stock-de-todas-las-líneas (A 3→13, B 0→4), un-movimiento-`entrada`-por-línea-con-previo/nuevo-y-`ref_id`-a-su-entrada, entrada-registra-cantidad/costo/usuario, pedido-queda-`recibido`-con-`recibido_at`/`recibido_por`, actualiza-costo-y-precio (1000→1200, margen 0.5 ⇒ `precio_venta` 1800), mostrador-200, anónimo-401, inexistente-404-sin-cambios; verificar que fallan
- [x] 5.2 GREEN: implementar `services/compras.py::recibir_pedido` (lock pedido, chequeo `pendiente`, líneas ordenadas por `producto_id`, `EntradaStock` + `aplicar_movimiento(tipo="entrada", ref_id=entrada.id)` + costo si difiere, estado `recibido`, UN solo commit, rollback + re-raise ante error) y `POST /compras/pedidos/{id}/recibir` (`require_role("duena","mostrador")`, `200` con detalle); verificar `test_compras_recibir.py` verde
- [x] 5.3 TRIANGULATE: agregar casos fallo-en-2ª-línea-revierte-todo (monkeypatch de `aplicar_movimiento` en `app.services.compras` que levanta en la 2ª llamada ⇒ stock, costo, entradas, movimientos y estado intactos), costo-igual-no-modifica-`updated_at`-del-producto, producto-dado-de-baja-después-del-pedido-igual-se-recibe y `comparar` de C-06 sigue devolviendo el sugerido por lista sin cambios; verificar que pasan

## 6. Transiciones de estado, idempotencia y cancelación (D7)

- [x] 6.1 RED: escribir `backend/tests/test_compras_transiciones.py` con tests failing: recibir-dos-veces ⇒ 200 luego 409 con stock/entradas/movimientos idénticos a tras la primera, recibir-cancelado-409-sin-cambios, dueña-cancela-pendiente-200-sin-mover-stock, cancelar-recibido-409, cancelar-cancelado-409, mostrador-cancelar-403, cancelar-inexistente-404; verificar que fallan
- [x] 6.2 GREEN: implementar `services/compras.py::cancelar_pedido` + `POST /compras/pedidos/{id}/cancelar` (`require_duena`), mapear `EstadoInvalido` e `IntegrityError` del unique de `entrada_stock` a `409`; verificar `test_compras_transiciones.py` verde
- [x] 6.3 TRIANGULATE: agregar caso barrera-de-base (insertar a mano una `EntradaStock` para el pedido pendiente y luego recibir ⇒ `409` y rollback total, sin stock sumado); verificar que pasa

## 7. Pagos a distribuidoras (RN-CP-03, solo dueña, D9)

- [x] 7.1 RED: escribir `backend/tests/test_compras_pagos.py` con tests failing: pago-201-sin-pedidos-con-`fecha`-de-hoy-y-sin-tocar-pedidos-ni-stock, `monto`-0/negativo-422, `metodo`-inválido-422, `pedido_id`-presente-422, distribuidora-inexistente-404, distribuidora-inactiva-201, mostrador-403-en-POST-y-GET, anónimo-401, listar-filtra-por-`distribuidora_id`, anular-204-con-`activo=False`-y-deja-de-listarse, anular-inexistente-404; verificar que fallan
- [x] 7.2 GREEN: implementar `services/compras.py::registrar_pago/anular_pago` + `POST/GET /compras/pagos` y `DELETE /compras/pagos/{id}` con `require_duena`; verificar `test_compras_pagos.py` verde
- [x] 7.3 TRIANGULATE: agregar casos `fecha` explícita pasada se respeta y pago-con-pedido-pendiente-existente-no-cambia-su-estado; verificar que pasan

## 8. Cuenta simple por distribuidora (D10)

- [x] 8.1 RED: escribir `backend/tests/test_compras_cuenta.py` con tests failing: recibido 9000 + pendiente 4000 + pagos activos 5000 + anulado 1000 ⇒ `total_recibido=9000`, `total_pagado=5000`, `saldo=4000`; sin movimientos ⇒ todo 0; inexistente-404; mostrador-403; anónimo-401; verificar que fallan
- [x] 8.2 GREEN: implementar `services/compras.py::cuenta_distribuidora` (agregados `SUM` en `Decimal`, solo entradas y pagos activos) + `GET /compras/distribuidoras/{id}/cuenta` con `require_duena`; verificar `test_compras_cuenta.py` verde
- [x] 8.3 TRIANGULATE: agregar caso pedido-cancelado-no-suma y saldo-negativo-cuando-se-pagó-de-más (pago 10000 vs recibido 9000 ⇒ `saldo=-1000`); verificar que pasan

## 9. Integración y cierre

- [x] 9.1 Verificación integral: `pytest backend/tests -q` todo verde (incluye baseline de 1.1 sin regresiones en C-03/C-04/C-05/C-06), linter del backend (`ruff`) limpio, y smoke manual pedido → recibir → `GET /api/stock` y `GET /api/productos/{id}` con stock y `precio_venta` actualizados → pago → cuenta
- [x] 9.2 Verificar matriz escenario→test: cada `#### Scenario` de `specs/compras/spec.md` tiene al menos un test que lo cubre; registrar evidencia TDD (Safety Net/RED/GREEN/TRIANGULATE/REFACTOR por grupo) en el resumen de apply
- [x] 9.3 Corregir en `CHANGES.md` §[C-07] "Migración 005" → "Migración 0006 (0005 ya existe: índice de C-06)" y verificar con `git diff CHANGES.md` que solo cambia esa línea; el tilde `[x]` del estado se hace en archive
