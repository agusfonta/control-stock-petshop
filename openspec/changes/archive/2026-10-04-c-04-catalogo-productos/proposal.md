# Proposal

## Why

El catálogo de productos existe como modelo de datos (C-02) pero no hay endpoints para gestionarlo ni lógica de precios expuesta via API. Sin este change, la dueña no puede cargar productos, buscarlos por código/nombre, ni configurar márgenes y stock mínimo — requisito para US-005 (gestión de distribuidoras y listas) y US-008 (configurar márgenes y mínimos). C-04 desbloquea C-05 (stock/alertas), C-06 (distribuidoras) y C-08 (migración Excel).

## What Changes

- **Modelo `ListaPrecio`**: nueva entidad N—1 con `Distribuidora` y N—1 con `Producto`, campo `costo` (Numeric). Permite costos diferenciados por distribuidora (RN-PR-03).
- **Migración Alembic `0003`**: crea tabla `lista_precio` (id uuid PK, distribuidora_id FK, producto_id FK, costo Numeric, unique constraint en par (distribuidora_id, producto_id)). Hija de `0002`.
- **CRUD `/api/productos`**: endpoints `POST`, `GET` (listado paginado), `GET /{id}`, `PUT /{id}`, `DELETE /{id}` (soft-delete via `activo=False`). Todos con schemas Pydantic estrictos.
- **Búsqueda `GET /api/productos/buscar?q=`**: búsqueda por SKU exacto o nombre parcial (trgm), paginado. Reutiliza índice `ix_productos_nombre_trgm` de C-02.
- **PATCH `/api/productos/{id}/margen-minimo`**: actualiza `margen_pct` y/o `stock_minimo`. Solo dueña (RN-PR-02, RN-ST-02). Recalcula `precio_venta` automáticamente (RN-PR-01).
- **Lógica de precios**: `precio_venta = costo × (1 + margen_pct)` ya implementado como `column_property` en C-02. C-04 expone la recálculo via API sin tocar histórico (RN-PR-04).
- **Tests TDD**: CRUD completo, búsqueda por código/nombre, recálculo de precio al cambiar costo/margen, 403 mostrador en margen-minimo, validación de schemas.

## Capabilities

### New Capabilities

- `catalogo-productos`: Gestión del catálogo de productos con precios calculados, búsqueda por código/nombre, y configuración de márgenes y stock mínimo. Incluye el modelo `ListaPrecio` para costos diferenciados por distribuidora.

### Modified Capabilities

<!-- Ningún spec existente cambia sus requerimientos: core-models ya cubre Producto con margen_pct/stock_minimo y precio_venta calculado. C-04 construye encima sin modificar. -->

## Impact

- **Modelos**: nuevo `ListaPrecio` en `backend/app/models.py`.
- **Migración**: `0003_lista_precio.py` en `backend/alembic/versions/`.
- **Routers**: nuevo `backend/app/routers/productos.py` con CRUD + búsqueda + margen-minimo.
- **Schemas**: nuevos schemas Pydantic en `backend/app/schemas.py` (ProductoCreate, ProductoUpdate, ProductoResponse, ListaPrecioCreate, MargenMinimoRequest, BusquedaResponse).
- **Tests**: nuevo `backend/tests/test_productos.py` con cobertura completa.
- **Dependencias**: reutiliza `deps.require_duena` (C-03), `deps.get_db`, `deps.get_current_user`. No modifica auth ni modelos existentes.
- **Frontend**: no aplica en este change (C-13 cubre UI).
