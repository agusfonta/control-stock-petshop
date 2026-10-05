# Proposal

## Why

La dueña necesita gestionar distribuidoras y comparar costos por origen para decidir a quién comprar (US-005, Épica 3). Los modelos `Distribuidora` y `ListaPrecio` ya existen en la base (C-02/C-04), pero no hay ninguna API que los exponga: hoy el costo por lista y el precio sugerido por origen son invisibles. Sin este change, C-07 (pedidos/entradas) no tiene sobre qué operar.

## What Changes

- `CRUD /api/distribuidoras` con schemas Pydantic estrictos: escritura solo `duena` (guards C-03), lectura cualquier usuario activo; borrado = soft-delete (`activo=False`), nunca físico.
- `CRUD /api/distribuidoras/{id}/listas`: alta/edición/baja de costos por (distribuidora, producto); par único `(distribuidora_id, producto_id)` — duplicado responde `409`.
- `GET /api/distribuidoras/comparar?producto_id=`: devuelve costos por distribuidora para un producto más `precio_sugerido = costo × (1 + margen_pct)` recalculado por origen (RN-PR-01/RN-PR-03), ordenado por costo ascendente.
- Schemas nuevos en `backend/app/schemas.py`: `DistribuidoraCreate/Update/Response`, `ListaPrecioCreate` anidada (sin `distribuidora_id` en body — va en path), `ListaPrecioUpdate`, `ListaPrecioResponse`, `CompararResponse`.
- Migración `0005` (solo si el diseño lo confirma): índice `ix_lista_precio_producto_id` sobre `lista_precio(producto_id)` para el query de comparar; sin cambios de columnas — los modelos ya están completos.
- Tests TDD (RED-first) para RN-PR-01/03 por origen: CRUD, costo por lista, precio sugerido por origen, 403 mostrador en escritura.

## Capabilities

### New Capabilities

- `distribuidoras`: ABM de distribuidoras, CRUD de listas de precios por distribuidora y comparación de costos con precio sugerido por origen (US-005, RN-PR-01/RN-PR-03).

### Modified Capabilities

- (vacío — ninguna requirement existente cambia: `core-models` y `catalogo-productos` ya persisten `Distribuidora`/`ListaPrecio`; este change agrega comportamiento nuevo en una capability nueva, no modifica comportamiento especificado).

## Impact

- Nuevo: `backend/app/routers/distribuidoras.py` + registro en `main.py`; schemas nuevos; tests `test_distribuidoras*.py`; opcional migración `0005` (índice, sin downtime).
- Sin breaking changes: ningún endpoint existente se toca; `ListaPrecioCreate` plana de C-04 se conserva (el anidado es un schema nuevo).
- Non-goals explícitos: pedidos/entradas/pagos (C-07), migración Excel (C-08), reportes (C-14).
