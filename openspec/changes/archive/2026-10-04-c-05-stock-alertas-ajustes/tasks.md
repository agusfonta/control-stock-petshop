# Tasks

## 1. Modelo MovimientoStock + migración 0004 (append-only)

- [x] 1.1 RED: escribir `backend/tests/test_stock_movimientos.py` con tests failing de insert (previo/nuevo/usuario), update/delete bloqueados y check `stock_nuevo >= 0`, y verificar que fallan (`pytest backend/tests/test_stock_movimientos.py` en rojo)
- [x] 1.2 GREEN: implementar modelo `MovimientoStock` en `backend/app/models.py` + migración manual `0004_movimiento_stock.py` (hija de `0003`, FKs a productos/usuarios, check e índices, downgrade limpio), y verificar `pytest backend/tests/test_stock_movimientos.py` en verde más `alembic upgrade head` / `downgrade -1` / `upgrade head` sin residuos

## 2. Lectura GET /api/stock con badge (RN-ST-01)

- [x] 2.1 RED: escribir `backend/tests/test_stock_lectura.py` con tests failing (badge true en `stock == minimo`, false por encima, filtro `bajo_minimo=true`, `orden=rotacion` por cobertura ascendente, `401` anónimo, `422` orden inválido), y verificar que fallan antes de implementar
- [x] 2.2 GREEN: implementar schemas estrictos (`StockItem` con `bajo_minimo`, envelope paginado) + `routers/stock.py` (`GET /api/stock`, auth `get_current_user`, paginado default 20/max 100) registrado en la app, y verificar `pytest backend/tests/test_stock_lectura.py` en verde

## 3. Ajuste auditable POST /api/productos/{id}/ajustar (RN-ST-02/03, solo dueña)

- [x] 3.1 RED: escribir `backend/tests/test_stock_ajuste.py` con tests failing (ajuste +5 genera movimiento con previo/nuevo/motivo/usuario, delta negativo, `403` mostrador, `401` anónimo, `422` motivo vacío, `422` stock negativo, `404` inexistente, `PUT` con `stock_actual` → `422` sin cambios, rollback si falla el movimiento), y verificar que fallan antes de implementar
- [x] 3.2 GREEN: implementar `services/stock.py::ajustar()` (transacción + `SELECT FOR UPDATE`, valida motivo/stock, crea movimiento `ajuste`) + `POST /api/productos/{id}/ajustar` con `require_duena` + cierre de `stock_actual` en `PUT` (decisión D2), y verificar `pytest backend/tests/test_stock_ajuste.py` en verde

## 4. Job Redis + GET /api/stock/alertas (reposición, Flujo 2)

- [x] 4.1 RED: escribir `backend/tests/test_stock_alertas.py` con tests failing (resumen coincide con filtro bajo-mínimo, caso vacío `total=0`, fallback a DB con Redis caído vía fakeredis, TTL por env `STOCK_ALERT_TTL_S` default 60s), y verificar que fallan antes de implementar
- [x] 4.2 GREEN: implementar `workers/stock_alerts.py` (recálculo `SET stock:bajo_minimo` con TTL) + `GET /api/stock/alertas` con fallback a cómputo directo si Redis falla, y verificar `pytest backend/tests/test_stock_alertas.py` en verde

## 5. Integración y cierre

- [x] 5.1 Ejecutar suite completa `pytest backend/tests` y linter del backend, y verificar todo en verde sin regresiones en C-03/C-04 (auth, productos, márgenes)
- [x] 5.2 Verificar matriz escenario→test: cada `#### Scenario` de `specs/stock-alertas/spec.md` tiene al menos un test que lo cubre, y verificar que no queda código fuera de `backend/` (planning-only, sin frontend en este change)
