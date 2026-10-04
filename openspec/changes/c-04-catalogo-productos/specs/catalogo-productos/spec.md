# Spec Delta

## Purpose

Gestión del catálogo de productos con precios calculados automáticamente, búsqueda por código/nombre, y configuración de márgenes y stock mínimo por la dueña. Incluye el modelo ListaPrecio para costos diferenciados por distribuidora.

## ADDED Requirements

### Requirement: CRUD de productos

El system SHALL exponer endpoints CRUD para productos bajo `/api/productos` con schemas Pydantic estrictos. Crear y editar requiere rol `duena`. Eliminar es soft-delete (`activo=False`), nunca borrado físico.

#### Scenario: Crear producto exitosamente
- **WHEN** una dueña envía un payload válido a `POST /api/productos`
- **THEN** el sistema responde `201` con el producto creado incluyendo `precio_venta` calculado

#### Scenario: Crear producto con SKU duplicado
- **WHEN** una dueña envía un `sku` ya existente a `POST /api/productos`
- **THEN** el sistema responde `409` y no crea el registro

#### Scenario: Crear producto sin autenticación
- **WHEN** un cliente anónimo envía un payload a `POST /api/productos`
- **THEN** el sistema responde `401`

#### Scenario: Crear producto como mostrador
- **WHEN** un usuario `mostrador` envía un payload válido a `POST /api/productos`
- **THEN** el sistema responde `403`

#### Scenario: Actualizar producto
- **WHEN** una dueña envía un payload válido a `PUT /api/productos/{id}`
- **THEN** el sistema responde `200` con el producto actualizado y `precio_venta` recalculado

#### Scenario: Eliminar producto (soft-delete)
- **WHEN** una dueña envía `DELETE /api/productos/{id}`
- **THEN** el sistema responde `204` y el producto queda con `activo=False`

#### Scenario: Obtener producto por ID
- **WHEN** un usuario autenticado llama a `GET /api/productos/{id}`
- **THEN** el sistema responde `200` con el producto

#### Scenario: Listar productos paginado
- **WHEN** un usuario autenticado llama a `GET /api/productos?page=1&page_size=20`
- **THEN** el sistema responde `200` con la página solicitada y metadata de paginación

### Requirement: Búsqueda de productos por código o nombre

El system SHALL exponer `GET /api/productos/buscar?q=` que busca por SKU exacto o nombre parcial usando el índice trgm, con paginado.

#### Scenario: Búsqueda por SKU exacto
- **WHEN** un usuario autenticado busca con un SKU exacto
- **THEN** el sistema responde `200` con el producto cuyo SKU coincide

#### Scenario: Búsqueda por nombre parcial
- **WHEN** un usuario autenticado busca con un fragmento de nombre
- **THEN** el sistema responde `200` con los productos cuyo nombre contiene el fragmento

#### Scenario: Búsqueda sin resultados
- **WHEN** un usuario autenticado busca un término que no coincide con ningún producto
- **THEN** el sistema responde `200` con lista vacía

#### Scenario: Búsqueda sin query param
- **WHEN** un usuario autenticado llama a `GET /api/productos/buscar` sin `q`
- **THEN** el sistema responde `422` (validación de schema)

### Requirement: Configuración de margen y stock mínimo

El system SHALL exponer `PATCH /api/productos/{id}/margen-minimo` que actualiza `margen_pct` y/o `stock_minimo`. Solo la dueña puede ejecutarlo (RN-PR-02, RN-ST-02). Al cambiar `margen_pct`, `precio_venta` se recalcula automáticamente (RN-PR-01).

#### Scenario: Dueña actualiza margen exitosamente
- **WHEN** una dueña envía `{"margen_pct": 0.35}` a `PATCH /api/productos/{id}/margen-minimo`
- **THEN** el sistema responde `200` con el producto actualizado y `precio_venta` recalculado según `costo × (1 + 0.35)`

#### Scenario: Dueña actualiza stock mínimo exitosamente
- **WHEN** una dueña envía `{"stock_minimo": 5}` a `PATCH /api/productos/{id}/margen-minimo`
- **THEN** el sistema responde `200` con `stock_minimo` actualizado

#### Scenario: Dueña actualiza margen y stock mínimo simultáneamente
- **WHEN** una dueña envía `{"margen_pct": 0.40, "stock_minimo": 10}` a `PATCH /api/productos/{id}/margen-minimo`
- **THEN** el sistema responde `200` con ambos campos actualizados

#### Scenario: Mostrador intenta actualizar margen
- **WHEN** un usuario `mostrador` envía un payload válido a `PATCH /api/productos/{id}/margen-minimo`
- **THEN** el sistema responde `403` y el estado no cambia

#### Scenario: Margen negativo es rechazado
- **WHEN** una dueña envía `{"margen_pct": -0.5}` a `PATCH /api/productos/{id}/margen-minimo`
- **THEN** el sistema responde `422` (validación de schema)

#### Scenario: Stock mínimo negativo es rechazado
- **WHEN** una dueña envía `{"stock_minimo": -1}` a `PATCH /api/productos/{id}/margen-minimo`
- **THEN** el sistema responde `422` (validación de schema)

### Requirement: Modelo ListaPrecio para costos por distribuidora

El system SHALL persistir la entidad `ListaPrecio` con `distribuidora_id`, `producto_id` y `costo`, permitiendo costos diferenciados por distribuidora (RN-PR-03). El par `(distribuidora_id, producto_id)` SHALL ser único.

#### Scenario: Migración crea tabla lista_precio
- **WHEN** se aplica la migración `0003` sobre una base con `0002`
- **THEN** existe la tabla `lista_precio` con sus constraints y el downgrade la elimina sin residuos

#### Scenario: Costo por distribuidora
- **WHEN** se crea un registro `ListaPrecio` con `distribuidora_id`, `producto_id` y `costo`
- **THEN** el sistema lo persiste y puede consultarse por producto o distribuidora

#### Scenario: Par distribuidora-producto único
- **WHEN** se intenta crear un segundo `ListaPrecio` con el mismo par `(distribuidora_id, producto_id)`
- **THEN** el sistema rechaza la operación con error de unicidad

### Requirement: Precio de venta calculado automáticamente

El system SHALL garantizar que `precio_venta = costo × (1 + margen_pct)` (RN-PR-01) se recalcula automáticamente al cambiar `costo` o `margen_pct`, sin crear registros históricos (RN-PR-04).

#### Scenario: Precio recalculado al cambiar margen
- **WHEN** se actualiza `margen_pct` de un producto existente
- **THEN** `precio_venta` refleja el nuevo valor según la fórmula

#### Scenario: Precio recalculado al cambiar costo
- **WHEN** se actualiza `costo` de un producto existente
- **THEN** `precio_venta` refleja el nuevo valor según la fórmula

#### Scenario: Sin reescritura de ventas históricas
- **WHEN** se cambia el costo o margen de un producto
- **THEN** no se crea ningún registro histórico de precio ni se modifica ninguna venta existente
