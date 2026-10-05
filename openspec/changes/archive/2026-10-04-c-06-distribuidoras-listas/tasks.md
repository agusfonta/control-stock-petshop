# Tasks

## 1. Safety net y schemas Pydantic

- [x] 1.1 Ejecutar suite actual (`pytest backend/tests -x -q`) y registrar baseline "N tests passing" como red de seguridad; si algo falla, reportar como pre-existente y no tocarlo
- [x] 1.2 RED: escribir `backend/tests/test_distribuidoras_schemas.py` con validación de `DistribuidoraCreate/Update` (nombre vacío→error, opcionales nulos ok, `extra=forbid`→error) y de `ListaPrecioDistribuidoraCreate` (costo 0/negativo→error) y verificar que fallan por schemas inexistentes
- [x] 1.3 GREEN: agregar a `backend/app/schemas.py` `DistribuidoraCreate/Update/Response`, `ListaPrecioDistribuidoraCreate`, `ListaPrecioUpdate`, `ListaPrecioResponse`, `CompararFila/CompararResponse` (estrictos + `_coerce_decimal` + serializador Decimal) y verificar que los tests de 1.2 pasan

## 2. CRUD de distribuidoras

- [x] 2.1 RED: escribir `backend/tests/test_distribuidoras.py` con crear-201, nombre-vacío-422, anónimo-401, mostrador-403-en-escritura, get-404, put-200, delete-204-con-`activo=False` y verificar que fallan (router inexistente)
- [x] 2.2 GREEN: crear `backend/app/routers/distribuidoras.py` con CRUD + `_get_or_404` + soft-delete + `require_duena` en escritura / `get_current_user` en lectura (patrón `routers/productos.py:40-68,227-236`), registrarlo en `backend/app/main.py` y verificar que los tests de 2.1 pasan
- [x] 2.3 TRIANGULATE: agregar casos listar-paginado-solo-activas y update-parcial-de-contacto/condiciones en `test_distribuidoras.py` y verificar que pasan sin cambiar el router (o generalizar si rompen)

## 3. Listas de precios por distribuidora

- [x] 3.1 RED: escribir `backend/tests/test_distribuidoras_listas.py` con alta-201, duplicado-409, costo-0-422, producto-inexistente-404, distribuidora-inexistente-404, update-costo-200, delete-204-sin-afectar-producto, mostrador-403 y verificar que fallan
- [x] 3.2 GREEN: agregar endpoints anidados `POST/GET/PUT/DELETE /api/distribuidoras/{id}/listas` al router de 2.2 (costo desde path-distribuidora + body `{producto_id, costo}`; pre-check unique + `catch IntegrityError → 409` como `routers/productos.py:97-105`) y verificar que los tests de 3.1 pasan
- [x] 3.3 TRIANGULATE: agregar caso mismo-producto-en-dos-distribuidoras-ok (unicidad es por par, no global) y verificar que pasa

## 4. Comparar costos con precio sugerido (RN-PR-01/RN-PR-03, TDD estricto)

- [x] 4.1 RED: escribir `backend/tests/test_distribuidoras_comparar.py` con dos-orígenes-ordenados-por-costo (800→1200, 1000→1500 con margen 0.5), cambio-de-costo-refleja-sugerido-sin-histórico, producto-inexistente-404, sin-`producto_id`-422, sin-listas-200-vacío, anónimo-401 y verificar que fallan
- [x] 4.2 GREEN: agregar `GET /api/distribuidoras/comparar` DECLARADA ANTES que `/{id}` en el router (diseño D5), join lista→producto por `margen_pct`, `precio_sugerido = costo × (1 + margen)` en `Decimal`, filtro distribuidoras activas, orden `costo ASC`, y verificar que los tests de 4.1 pasan
- [x] 4.3 TRIANGULATE: agregar caso `precio_sugerido == precio_venta` del producto cuando el costo de lista iguala al costo base + caso distribuidora-inactiva-excluida-de-comparar y verificar que pasan

## 5. Migración 0005, cableado e integración

- [x] 5.1 Crear `backend/alembic/versions/0005_lista_precio_producto_idx.py` (hija de `0004`, solo `CREATE INDEX ix_lista_precio_producto_id`; espeja diseño D1) y verificar `alembic upgrade head` + `downgrade -1` sin residuos en SQLite y Postgres
- [x] 5.2 Verificación integral: correr `pytest backend/tests -q` (todo verde incl. baseline de 1.1), `ruff`/`npm run lint` según repo, y smoke manual `GET /api/distribuidoras/comparar?producto_id=` con dos orígenes; registrar evidencia TDD (RED/GREEN/TRIANGULATE por grupo) en el resumen de apply
