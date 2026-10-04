# stock-alertas

## Purpose

Dar a la dueña visibilidad en tiempo real del stock con alertas de reposición y una vía auditable para corregir existencias, de modo que ningún cambio de stock ocurra sin trazabilidad antes de que las ventas empiecen a descontar existencias.

## Requirements

### Requirement: MovimientoStock append-only con previo y nuevo

The system SHALL persistir un registro `MovimientoStock` por cada cambio de stock con `producto_id`, `tipo` (`venta`/`entrada`/`ajuste`/`apertura`), `cantidad` con signo, `stock_previo`, `stock_nuevo`, `ref_id` nullable, `usuario_id` y `created_at`, y SHALL rechazar cualquier update o delete sobre esos registros (solo inserts).

#### Scenario: Ajuste genera movimiento con previo y nuevo
- **WHEN** una dueña ajusta un producto con `stock_actual = 10` en `+5`
- **THEN** el sistema persiste un movimiento tipo `ajuste` con `cantidad = 5`, `stock_previo = 10`, `stock_nuevo = 15` y el `usuario_id` de la dueña

#### Scenario: Movimiento con cantidad negativa
- **WHEN** una dueña ajusta un producto con `stock_actual = 10` en `-3`
- **THEN** el sistema persiste un movimiento tipo `ajuste` con `cantidad = -3`, `stock_previo = 10`, `stock_nuevo = 7`

#### Scenario: Historial ordenado por creación
- **WHEN** un usuario autenticado consulta los movimientos de un producto con varios ajustes
- **THEN** el sistema los devuelve ordenados por `created_at` ascendente con `producto_id`, `tipo`, `cantidad`, `stock_previo` y `stock_nuevo` visibles

### Requirement: Lectura de stock con badge de bajo mínimo

The system SHALL exponer `GET /api/stock` paginado que devuelve productos activos con `stock_actual`, `stock_minimo` y el derivado `bajo_minimo = (stock_actual <= stock_minimo)` (RN-ST-01), con filtro `bajo_minimo=true` y orden `orden=rotacion` (menor cobertura `stock_actual - stock_minimo` primero); requiere autenticación y responde `401` sin token.

#### Scenario: Alerta al llegar exactamente al mínimo
- **WHEN** un producto tiene `stock_actual == stock_minimo` y se lista `GET /api/stock`
- **THEN** el item incluye `bajo_minimo = true`

#### Scenario: Sin alerta por encima del mínimo
- **WHEN** un producto tiene `stock_actual > stock_minimo` y se lista `GET /api/stock`
- **THEN** el item incluye `bajo_minimo = false`

#### Scenario: Filtro solo bajo stock
- **WHEN** un usuario autenticado llama a `GET /api/stock?bajo_minimo=true`
- **THEN** el sistema responde `200` solo con productos donde `stock_actual <= stock_minimo`

#### Scenario: Orden por rotación
- **WHEN** un usuario autenticado llama a `GET /api/stock?orden=rotacion`
- **THEN** los items vienen ordenados por cobertura ascendente (el más negativo primero)

#### Scenario: Lectura anónima rechazada
- **WHEN** un cliente sin token llama a `GET /api/stock`
- **THEN** el sistema responde `401` sin devolver datos

### Requirement: Ajuste de stock auditable solo por dueña

The system SHALL exponer `POST /api/productos/{id}/ajustar` que exige rol `duena`, acepta `{cantidad_delta, motivo}` con `motivo` obligatorio no vacío, aplica el delta sobre `stock_actual` en la misma transacción que crea el movimiento tipo `ajuste`, y responde `200` con el producto actualizado más el movimiento creado (RN-ST-02, RN-ST-03).

#### Scenario: Ajuste positivo exitoso
- **WHEN** una dueña envía `{"cantidad_delta": 5, "motivo": "conteo físico"}` sobre un producto con stock 10
- **THEN** el sistema responde `200`, `stock_actual` queda en 15 y existe un movimiento `ajuste` con ese motivo y su usuario

#### Scenario: Mostrador bloqueado en ajustar
- **WHEN** un usuario `mostrador` autenticado llama a `POST /api/productos/{id}/ajustar`
- **THEN** el sistema responde `403` y ni el stock ni los movimientos cambian

#### Scenario: Ajuste anónimo rechazado
- **WHEN** un cliente sin token llama a `POST /api/productos/{id}/ajustar`
- **THEN** el sistema responde `401` y nada cambia

#### Scenario: Motivo vacío rechazado
- **WHEN** una dueña envía `{"cantidad_delta": 5, "motivo": "  "}` a `POST /api/productos/{id}/ajustar`
- **THEN** el sistema responde `422` y ni el stock ni los movimientos cambian

#### Scenario: Ajuste que deja stock negativo rechazado
- **WHEN** una dueña envía un delta que dejaría `stock_nuevo < 0`
- **THEN** el sistema responde `422` y ni el stock ni los movimientos cambian

#### Scenario: Producto inexistente
- **WHEN** una dueña llama a `POST /api/productos/{id}/ajustar` con un id que no existe
- **THEN** el sistema responde `404` y no crea ningún movimiento

### Requirement: Prohibido editar stock sin movimiento

The system SHALL garantizar que toda mutación de `stock_actual` ocurre junto a la creación de su `MovimientoStock` en la misma transacción (RN-ST-03): no existe ningún endpoint que modifique `stock_actual` sin generar movimiento, y `PUT /api/productos/{id}` con campo de stock es rechazado o ignorado sin alterar existencias.

#### Scenario: PUT con stock no mueve existencias
- **WHEN** una dueña envía `stock_actual` dentro de `PUT /api/productos/{id}`
- **THEN** el sistema responde `422` (o ignora el campo) y `stock_actual` permanece igual sin crear movimientos

#### Scenario: Fallo del movimiento revierte el stock
- **WHEN** la creación del movimiento falla durante un ajuste
- **THEN** `stock_actual` conserva su valor previo (rollback total, sin stock a medias)

### Requirement: Job de bajo-mínimo y resumen de alertas

The system SHALL mantener un job Redis que recalcula el conjunto de productos bajo mínimo con TTL corto y exponer `GET /api/stock/alertas` (autenticado) con `{total_bajo_minimo, items}` para reposición; si Redis no está disponible, el endpoint cae de forma degradada al cómputo directo sin responder `500`.

#### Scenario: Resumen de alertas coincide con el filtro
- **WHEN** hay 3 productos con `stock_actual <= stock_minimo` y se llama a `GET /api/stock/alertas`
- **THEN** el sistema responde `200` con `total_bajo_minimo = 3` y esos 3 items

#### Scenario: Sin productos bajo mínimo
- **WHEN** ningún producto está bajo mínimo y se llama a `GET /api/stock/alertas`
- **THEN** el sistema responde `200` con `total_bajo_minimo = 0` e `items` vacío

#### Scenario: Alertas sin Redis disponible
- **WHEN** Redis está caído y se llama a `GET /api/stock/alertas`
- **THEN** el sistema responde `200` con datos calculados directo de la base en lugar de `500`

### Requirement: Migración 0004 crea movimiento_stock

The system SHALL proveer la migración Alembic `0004` (hija de `0003`) que crea exactamente la tabla `movimiento_stock` con sus FKs a `productos`/`usuarios`, check `stock_nuevo >= 0` e índices en `producto_id` y `created_at`, y cuyo downgrade la elimina sin residuos.

#### Scenario: Upgrade crea la tabla
- **WHEN** se aplica la migración `0004` sobre una base con `0003`
- **THEN** existe la tabla `movimiento_stock` con sus constraints e índices y el downgrade la elimina sin residuos

#### Scenario: Stock nuevo negativo rechazado a nivel base
- **WHEN** se intenta insertar un movimiento con `stock_nuevo < 0`
- **THEN** la base rechaza la inserción por constraint

### Requirement: Validación estricta y secretos solo por env

The system SHALL validar todo input/output de stock con schemas Pydantic estrictos (payloads malformados → `422` sin ejecutar lógica) y SHALL tomar la conexión Redis y TTLs de variables de entorno, sin hardcodear credenciales reales en repo ni tests.

#### Scenario: Payload de ajuste malformado rechazado
- **WHEN** se envía a `POST /api/productos/{id}/ajustar` un body sin `cantidad_delta` o con tipo inválido
- **THEN** el sistema responde `422` y no toca stock ni movimientos

#### Scenario: Query param inválido rechazado
- **WHEN** se llama a `GET /api/stock?orden=invalido`
- **THEN** el sistema responde `422` sin devolver datos
