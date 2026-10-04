# Tasks

## 1. Migración 0003 + Modelo ListaPrecio

- [x] 1.1 Crear migración `0003_lista_precio.py` (hija de `0002`) con `upgrade()` que crea tabla `lista_precio` (id uuid PK, distribuidora_id FK, producto_id FK, costo Numeric(10,2), unique constraint en par (distribuidora_id, producto_id)) y `downgrade()` que la elimina. Verificar: `alembic upgrade head` y `alembic downgrade 0002` ejecutan sin error.
- [x] 1.2 Agregar modelo `ListaPrecio` en `backend/app/models.py` con relaciones a `Distribuidora` y `Producto`. Verificar: test de modelo que crea y lee un registro ListaPrecio en SQLite.

## 2. Schemas Pydantic

- [x] 2.1 Crear schemas `ProductoCreate`, `ProductoUpdate`, `ProductoResponse`, `ListaPrecioCreate`, `MargenMinimoRequest`, `BusquedaResponse`, `PaginacionResponse` en `backend/app/schemas.py` con `extra="forbid"` y `strict=True`. Verificar: tests de validación que payloads malformados retornan 422.
- [x] 2.2 Agregar tests de schemas en `backend/tests/test_productos_schemas.py` cubriendo: campos requeridos, tipos correctos, valores negativos rechazados, SKU pattern. Verificar: `pytest tests/test_productos_schemas.py` pasa.

## 3. CRUD de Productos (TDD)

- [x] 3.1 Escribir tests TDD en `backend/tests/test_productos_crud.py` para: crear producto (201 + precio_venta calculado), crear con SKU duplicado (409), crear sin auth (401), crear como mostrador (403), actualizar producto (200 + precio recalculado), eliminar producto (204 + activo=False), obtener por ID (200), listar paginado (200 + metadata). Verificar: tests FALLEAN (router no existe).
- [x] 3.2 Implementar `backend/app/routers/productos.py` con endpoints `POST /api/productos`, `GET /api/productos`, `GET /api/productos/{id}`, `PUT /api/productos/{id}`, `DELETE /api/productos/{id}`. Usar `Depends(require_duena)` para escritura y `Depends(get_current_user)` para lectura. Verificar: `pytest tests/test_productos_crud.py` pasa.
- [x] 3.3 Registrar router en `backend/app/main.py`. Verificar: `pytest tests/test_productos_crud.py` sigue pasando.

## 4. Búsqueda de Productos (TDD)

- [x] 4.1 Escribir tests TDD en `backend/tests/test_productos_busqueda.py` para: búsqueda por SKU exacto, búsqueda por nombre parcial, búsqueda sin resultados (lista vacía), búsqueda sin query param (422). Verificar: tests FALLEAN (endpoint no existe).
- [x] 4.2 Implementar `GET /api/productos/buscar?q=&page=&page_size=` en `productos.py` con `OR(sku == q, nombre % q)` y paginado. Verificar: `pytest tests/test_productos_busqueda.py` pasa.

## 5. Configuración de Margen y Stock Mínimo (TDD)

- [x] 5.1 Escribir tests TDD en `backend/tests/test_productos_margen.py` para: dueña actualiza margen (200 + precio recalculado), dueña actualiza stock mínimo (200), dueña actualiza ambos (200), mostrador intenta actualizar (403), margen negativo (422), stock mínimo negativo (422). Verificar: tests FALLEAN (endpoint no existe).
- [x] 5.2 Implementar `PATCH /api/productos/{id}/margen-minimo` en `productos.py` con `Depends(require_duena)`. Verificar: `pytest tests/test_productos_margen.py` pasa.

## 6. Integración y Verificación Final

- [x] 6.1 Ejecutar suite completa: `pytest backend/tests/ -v`. Verificar: todos los tests pasan (incluyendo los de C-01/C-02/C-03).
- [x] 6.2 Ejecutar `npm run lint` en frontend (si aplica). Verificar: sin errores de lint. (No aplica: el frontend no tiene script `lint` en package.json.)
- [x] 6.3 Verificar que la migración `0003` es hija de `0002` y no rompe la cadena. Verificar: `alembic history` muestra 0001 → 0002 → 0003.
