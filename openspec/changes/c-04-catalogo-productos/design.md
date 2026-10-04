# Design

## Context

C-02 (core-models) ya creó el modelo `Producto` con `margen_pct`, `stock_minimo` y `precio_venta` como `column_property` (calculado en read-time). C-03 (auth-rbac) provee los guards `require_duena` y `get_current_user`. C-04 construye encima de ambos sin modificar auth ni modelos existentes. Ver proposal.md para motivación.

## Goals / Non-Goals

**Goals:**
- Exponer CRUD completo de productos via API REST con validación estricta.
- Búsqueda eficiente por SKU exacto y nombre parcial (trgm).
- Configuración de margen y stock mínimo solo por dueña.
- Modelo `ListaPrecio` para costos diferenciados por distribuidora.
- Migración Alembic `0003` para la nueva tabla.

**Non-Goals:**
- CRUD de distribuidoras (C-06).
- Movimientos de stock y alertas (C-05).
- Ventas y líneas (C-10).
- Frontend (C-13).
- Lógica de negocio de `ListaPrecio` más allá de la persistencia (el cálculo de precio por distribuidora se implementa en C-06/C-07).

## Decisions

### D1: `precio_venta` sigue como `column_property` (sin trigger ni columna física)

**Decisión**: Mantener `precio_venta` como `column_property` en `Producto` (ya implementado en C-02). No agregar trigger ni columna materializada.

**Racional**: El cálculo es determinístico y barato (`costo * (1 + margen_pct)`). Un `column_property` se evalúa en read-time y siempre refleja los valores vigentes. No hay riesgo de inconsistencia.

**Alternativa considerada**: Trigger de DB que actualiza una columna `precio_venta` física. Rechazada porque agrega complejidad sin beneficio — el cálculo es trivial y no hay queries que necesiten el valor materializado para índices o joins.

### D2: Soft-delete para productos (no borrado físico)

**Decisión**: `DELETE /api/productos/{id}` marca `activo=False`. Nunca borra físicamente.

**Racional**: Los productos pueden tener ventas asociadas (futuro C-10). El soft-delete preserva la integridad referencial y permite auditoría. Los listados filtran por `activo=True` por defecto.

**Alternativa considerada**: Borrado físico. Rechazado por riesgo de perder datos históricos.

### D3: Búsqueda con `OR` de SKU exacto + nombre trgm

**Decisión**: `GET /api/productos/buscar?q=` usa `OR(sku == q, nombre % q)` con el índice trgm existente.

**Racional**: El caso de uso principal es el mostrador buscando por código de barras (SKU exacto) o por nombre parcial. El índice `ix_productos_nombre_trgm` de C-02 ya soporta la búsqueda por similitud. El SKU exacto usa el índice único.

**Alternativa considerada**: Dos endpoints separados (`/buscar-sku` y `/buscar-nombre`). Rechazado porque complica el frontend y el caso de uso es uno solo: "encontrar un producto rápido".

### D4: `ListaPrecio` sin lógica de cálculo en este change

**Decisión**: `ListaPrecio` se persiste con `distribuidora_id`, `producto_id`, `costo`. No se implementa lógica de "precio según distribuidora" ni endpoints de consulta de listas.

**Racional**: El cálculo de precio por distribuidora (RN-PR-03) requiere el CRUD de distribuidoras (C-06) y el flujo de compras (C-07). En C-04 solo se crea la tabla y el modelo para que C-06 pueda usarla.

**Alternativa considerada**: Implementar endpoints de listas de precios ahora. Rechazado porque sin el CRUD de distribuidoras no hay forma de crear distribuidoras a las que asociar listas.

### D5: Paginado con `page`/`page_size` (no cursor-based)

**Decisión**: Paginado offset-based con `page` (default 1) y `page_size` (default 20, max 100).

**Racional**: El catálogo del local no va a superar los miles de productos. El offset es suficiente y más simple de implementar y testear. El cursor-based sería over-engineering para este volumen.

### D6: Reutilizar `require_duena` de C-03 para endpoints sensibles

**Decisión**: `POST /api/productos`, `PUT /api/productos/{id}`, `DELETE /api/productos/{id}` y `PATCH /api/productos/{id}/margen-minimo` usan `Depends(require_duena)`. Los endpoints de lectura (`GET`, `buscar`) usan `Depends(get_current_user)`.

**Racional**: La matriz RBAC (C-03) define que solo la dueña crea/edita productos y configura márgenes. El mostrador solo lee. Reutilizar el guard existente evita duplicar lógica de auth.

## Risks / Trade-offs

- **[Riesgo] `column_property` no funciona en instancias transient** → Mitigación: el router siempre hace `commit` + `refresh` antes de leer `precio_venta`. Los tests verifican el valor calculado después del commit.

- **[Riesgo] Búsqueda trgm en SQLite (tests) no usa el índice GIN** → Mitigación: los tests de búsqueda verifican resultados correctos, no el plan de query. El índice GIN solo existe en Postgres (producción). Los tests de migración (`test_migration_pg.py`) ya verifican la creación del índice en PG.

- **[Riesgo] `ListaPrecio` sin endpoints de consulta** → Mitigación: C-06 implementa el CRUD de distribuidoras y listas. C-04 solo crea la tabla y el modelo. No hay bloqueo.

- **[Trade-off] No se implementa margen global** → RN-PR-02 menciona "margen configurable global y por producto". C-04 implementa solo el margen por producto. El margen global queda como deuda técnica para C-06 o C-14.

## Migration Plan

1. Crear migración `0003_lista_precio.py` (hija de `0002`).
2. `upgrade()`: crea tabla `lista_precio` con FKs a `distribuidoras` y `productos`, unique constraint en `(distribuidora_id, producto_id)`.
3. `downgrade()`: elimina la tabla.
4. No hay data migration (tabla nueva, vacía).
5. Rollback: `alembic downgrade 0002` elimina la tabla sin afectar datos existentes.
