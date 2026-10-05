# distribuidoras

## Purpose

Permitir a la dueña gestionar distribuidoras con sus listas de precios por producto y comparar costos por origen con el precio sugerido recalculado, para decidir a quién comprar (US-005, RN-PR-01/RN-PR-03).

## Requirements

### Requirement: CRUD de distribuidoras

The system SHALL exponer endpoints CRUD para distribuidoras bajo `/api/distribuidoras` con schemas Pydantic estrictos (`nombre` obligatorio no vacío; `contacto`, `cuit`, `condiciones` opcionales). Crear, editar y eliminar requieren rol `duena`. Eliminar es soft-delete (`activo=False`), nunca borrado físico. Leer (listar u obtener) requiere solo usuario autenticado activo.

#### Scenario: Crear distribuidora exitosamente

- **WHEN** una dueña envía `{"nombre": "Distri Sur", "cuit": "30-12345678-9"}` a `POST /api/distribuidoras`
- **THEN** el sistema responde `201` con la distribuidora creada incluyendo `activo=true` y timestamps

#### Scenario: Crear distribuidora sin nombre

- **WHEN** una dueña envía `{}` o `{"nombre": "  "}` a `POST /api/distribuidoras`
- **THEN** el sistema responde `422` y no crea el registro

#### Scenario: Crear distribuidora sin autenticación

- **WHEN** un cliente anónimo envía un payload válido a `POST /api/distribuidoras`
- **THEN** el sistema responde `401`

#### Scenario: Crear distribuidora como mostrador

- **WHEN** un usuario `mostrador` envía un payload válido a `POST /api/distribuidoras`
- **THEN** el sistema responde `403` y no crea el registro

#### Scenario: Listar distribuidoras

- **WHEN** un usuario autenticado llama a `GET /api/distribuidoras`
- **THEN** el sistema responde `200` con las distribuidoras activas y metadata de paginación

#### Scenario: Obtener distribuidora por ID inexistente

- **WHEN** un usuario autenticado llama a `GET /api/distribuidoras/{id-inexistente}`
- **THEN** el sistema responde `404`

#### Scenario: Actualizar distribuidora

- **WHEN** una dueña envía `{"condiciones": "pago a 30 días"}` a `PUT /api/distribuidoras/{id}`
- **THEN** el sistema responde `200` con la distribuidora actualizada

#### Scenario: Eliminar distribuidora (soft-delete)

- **WHEN** una dueña envía `DELETE /api/distribuidoras/{id}`
- **THEN** el sistema responde `204` y la distribuidora queda con `activo=False` sin borrarse físicamente

### Requirement: CRUD de listas de precios por distribuidora

The system SHALL exponer `CRUD /api/distribuidoras/{id}/listas` para gestionar el costo de cada producto en esa distribuidora. Cada entrada lleva `producto_id` (debe existir) y `costo > 0`. El par (distribuidora, producto) SHALL ser único: un duplicado responde `409`. Solo `duena` puede escribir; lectura para cualquier usuario activo. La baja de una entrada es física sobre la fila de costo (no afecta al producto ni a la distribuidora).

#### Scenario: Agregar costo a la lista exitosamente

- **WHEN** una dueña envía `{"producto_id": "<p>", "costo": 800}` a `POST /api/distribuidoras/{d}/listas`
- **THEN** el sistema responde `201` con la entrada creada

#### Scenario: Costo duplicado para el mismo par

- **WHEN** una dueña envía un `producto_id` ya cargado en esa distribuidora a `POST /api/distribuidoras/{id}/listas`
- **THEN** el sistema responde `409` y no crea el registro

#### Scenario: Costo inválido es rechazado

- **WHEN** una dueña envía `{"producto_id": "<p>", "costo": 0}` o costo negativo a `POST /api/distribuidoras/{id}/listas`
- **THEN** el sistema responde `422`

#### Scenario: Producto inexistente en lista

- **WHEN** una dueña envía un `producto_id` que no existe a `POST /api/distribuidoras/{id}/listas`
- **THEN** el sistema responde `404`

#### Scenario: Distribuidora inexistente en lista

- **WHEN** una dueña envía un costo a `POST /api/distribuidoras/{id-inexistente}/listas`
- **THEN** el sistema responde `404`

#### Scenario: Actualizar costo de una entrada

- **WHEN** una dueña envía `{"costo": 850}` a `PUT /api/distribuidoras/{d}/listas/{producto_id}`
- **THEN** el sistema responde `200` con el costo actualizado

#### Scenario: Quitar producto de la lista

- **WHEN** una dueña envía `DELETE /api/distribuidoras/{d}/listas/{producto_id}`
- **THEN** el sistema responde `204` y la entrada deja de existir; el producto y la distribuidora no se ven afectados

#### Scenario: Mostrador intenta escribir una lista

- **WHEN** un usuario `mostrador` envía un costo válido a `POST /api/distribuidoras/{id}/listas`
- **THEN** el sistema responde `403`

### Requirement: Comparar costos por distribuidora con precio sugerido

The system SHALL exponer `GET /api/distribuidoras/comparar?producto_id=` que devuelve, para un producto existente, todos sus costos por distribuidora activa ordenados por costo ascendente, cada uno con su `precio_sugerido = costo × (1 + margen_pct)` recalculado con el margen vigente del producto (RN-PR-01, RN-PR-03). Es solo lectura (cualquier usuario activo) y no persiste nada: cambiar un costo actualiza el sugerido sin tocar ventas históricas (RN-PR-04).

#### Scenario: Comparar producto con dos orígenes

- **WHEN** un usuario autenticado llama a `GET /api/distribuidoras/comparar?producto_id=<p>` existiendo costos 800 (A) y 1000 (B) con `margen_pct = 0.5`
- **THEN** el sistema responde `200` con dos filas ordenadas (800, luego 1000) y `precio_sugerido` 1200 y 1500 respectivamente

#### Scenario: Comparar refleja cambio de costo

- **WHEN** se actualiza el costo de una lista y luego se llama a `GET /api/distribuidoras/comparar?producto_id=<p>`
- **THEN** el `precio_sugerido` de esa fila refleja el nuevo costo según la fórmula, sin crear registros históricos

#### Scenario: Comparar producto inexistente

- **WHEN** un usuario autenticado llama a `GET /api/distribuidoras/comparar?producto_id=<inexistente>`
- **THEN** el sistema responde `404`

#### Scenario: Comparar sin producto_id

- **WHEN** un usuario autenticado llama a `GET /api/distribuidoras/comparar` sin query param
- **THEN** el sistema responde `422`

#### Scenario: Comparar producto sin listas devuelve vacío

- **WHEN** un usuario autenticado compara un producto existente que no figura en ninguna lista
- **THEN** el sistema responde `200` con lista vacía

#### Scenario: Comparar sin autenticación

- **WHEN** un cliente anónimo llama a `GET /api/distribuidoras/comparar?producto_id=<p>`
- **THEN** el sistema responde `401`
