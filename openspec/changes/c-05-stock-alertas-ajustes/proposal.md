# Proposal

## Why

El catálogo (C-04) deja `stock_actual` como un número mudo: nadie detecta cuándo un producto llega a su mínimo ni existe forma auditable de corregir existencias. La dueña necesita ver alertas de reposición a tiempo (Flujo 2) y ajustar stock con trazabilidad total antes de que las ventas (C-10) empiecen a descontar existencias.

## What Changes

- Nuevo modelo `MovimientoStock` append-only: `producto_id`, `tipo` (`venta`/`entrada`/`ajuste`/`apertura`), `cantidad` (+/-), `stock_previo`, `stock_nuevo`, `ref_id` nullable, `usuario_id`, `created_at`; sin update/delete a nivel ORM ni API.
- `GET /api/stock` (paginado): lista productos activos con campo derivado `bajo_minimo = stock_actual <= stock_minimo`; filtros `bajo_minimo=true` y `orden=rotacion` (orden por menor cobertura primero); requiere auth.
- `POST /api/productos/{id}/ajustar` (solo dueña): body `{cantidad_delta, motivo}` con motivo obligatorio no vacío; aplica el delta en transacción, crea el `MovimientoStock` tipo `ajuste` y devuelve producto + movimiento; rechaza resultado negativo con `422` (check `stock_actual >= 0`).
- Job Redis de bajo-mínimo: contadores/sets con TTL corto para el conteo de alertas + `GET /api/stock/alertas` (resumen para reposición: total bajo mínimo + top por cobertura); la escritura del job nunca bloquea la lectura (fallback a cómputo directo si Redis cae).
- Migración Alembic `0004` (hija de `0003`): crea `movimiento_stock` con FKs, check `stock_nuevo >= 0` e índices (`producto_id`, `created_at`); downgrade la elimina sin residuos.
- Tests RED-first para RN-ST-01/02/03: alerta al llegar a mínimo, ajuste genera movimiento con previo/nuevo correctos, prohibido editar stock sin movimiento (sin endpoint directo de `stock_actual`), 403 mostrador en ajustar, 422 motivo vacío y stock negativo.

## Capabilities

### New Capabilities

- `stock-alertas`: stock en tiempo real con alertas de bajo-mínimo y ajustes auditables append-only (US-003, US-004; RN-ST-01/02/03).

### Modified Capabilities

- Ninguna: `catalogo-productos` y `auth-rbac` no cambian sus REQUIREMENTS (se reutilizan sus guards y el modelo `Producto` sin alterar su contrato).

## Impact

- Backend: `models.py` (+`MovimientoStock`), `schemas.py` (schemas estrictos de stock/ajuste), nuevo `routers/stock.py` + endpoint en `routers/productos.py` (`ajustar`), servicio `services/stock.py`, job `workers/stock_alerts.py`; migración `0004_movimiento_stock.py`.
- API: dos endpoints nuevos + uno de resumen (`GET /api/stock`, `POST /api/productos/{id}/ajustar`, `GET /api/stock/alertas`); sin cambios breaking en rutas C-04.
- Deps: Redis (ya en compose) para contadores de alerta con TTL; sin nuevas dependencias Python.
- Non-goals explícitos: ventas que descuentan stock (C-10), pedidos/entradas (C-07), reportes de reposición (C-14), granel/vencimientos (RN-ST-04 fuera de v1).
