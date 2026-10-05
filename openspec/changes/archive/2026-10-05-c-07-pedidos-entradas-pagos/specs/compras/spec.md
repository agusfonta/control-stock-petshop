# Spec Delta

## Purpose

Permitir pedir mercadería a distribuidoras, registrar su recepción como entrada de stock con el costo de la lista vigente y llevar una cuenta corriente simple de pagos por distribuidora, de modo que el stock entre solo cuando la mercadería llega (US-006, RN-CP-01, RN-CP-02, RN-CP-03).

## ADDED Requirements

### Requirement: Crear pedido de compra sin mover stock

The system SHALL exponer `POST /api/compras/pedidos` que acepta `{distribuidora_id, lineas: [{producto_id, cantidad}], notas?}` con schema Pydantic estricto y crea un pedido en estado `pendiente` registrando el usuario creador. Cada línea SHALL tener `cantidad` entera `> 0` y un `producto_id` no repetido dentro del pedido; el pedido SHALL tener al menos una línea. El `costo_unitario` de cada línea SHALL tomarse del costo vigente de la lista de esa distribuidora para ese producto (RN-CP-01) y, si el producto no figura en esa lista, del costo actual del producto; el cliente no envía costos. La distribuidora y los productos SHALL existir (sino `404`) y estar activos (sino `422`). Crear un pedido NO SHALL modificar `stock_actual` ni crear movimientos de stock (RN-CP-02). Pueden crear pedidos los roles `duena` y `mostrador`.

#### Scenario: Pedido creado no mueve stock

- **WHEN** una dueña envía un pedido válido con una línea de `cantidad = 10` para un producto con `stock_actual = 3`
- **THEN** el sistema responde `201` con el pedido en estado `pendiente`, el `stock_actual` del producto sigue en 3 y no se crea ningún movimiento de stock

#### Scenario: Costo de línea tomado de la lista vigente

- **WHEN** se crea un pedido a la distribuidora A para un producto que figura en la lista de A con costo 800 y cuyo costo base es 1000
- **THEN** la línea del pedido queda con `costo_unitario = 800`

#### Scenario: Costo de línea sin lista usa el costo del producto

- **WHEN** se crea un pedido a una distribuidora para un producto que no figura en su lista y cuyo costo base es 1000
- **THEN** la línea del pedido queda con `costo_unitario = 1000`

#### Scenario: Mostrador puede crear pedidos

- **WHEN** un usuario `mostrador` envía un pedido válido a `POST /api/compras/pedidos`
- **THEN** el sistema responde `201` y el pedido registra a ese usuario como creador

#### Scenario: Pedido sin líneas o con cantidad inválida

- **WHEN** un usuario autenticado envía un pedido con `lineas` vacío, una `cantidad` de 0 o negativa, o un `producto_id` repetido
- **THEN** el sistema responde `422` y no crea el pedido

#### Scenario: Pedido con costo enviado por el cliente

- **WHEN** un usuario autenticado envía una línea con un campo `costo_unitario`
- **THEN** el sistema responde `422` (campo no permitido) y no crea el pedido

#### Scenario: Pedido a distribuidora o producto inexistente

- **WHEN** un usuario autenticado envía un pedido con un `distribuidora_id` o un `producto_id` que no existen
- **THEN** el sistema responde `404` y no crea el pedido

#### Scenario: Pedido a distribuidora o producto inactivo

- **WHEN** un usuario autenticado envía un pedido a una distribuidora dada de baja o con un producto dado de baja
- **THEN** el sistema responde `422` y no crea el pedido

#### Scenario: Pedido sin autenticación

- **WHEN** un cliente anónimo envía un pedido a `POST /api/compras/pedidos`
- **THEN** el sistema responde `401`

### Requirement: Consultar pedidos de compra

The system SHALL exponer `GET /api/compras/pedidos` paginado (con metadata `total`, `page`, `page_size`, `total_pages`), filtrable por `estado` y `distribuidora_id`, y `GET /api/compras/pedidos/{id}` con el detalle del pedido: estado, distribuidora, líneas con `costo_unitario` y subtotal, total estimado y, si fue recibido, sus entradas. Ambas lecturas requieren cualquier usuario autenticado activo.

#### Scenario: Listar pedidos pendientes

- **WHEN** un usuario autenticado llama a `GET /api/compras/pedidos?estado=pendiente`
- **THEN** el sistema responde `200` solo con pedidos en estado `pendiente` y metadata de paginación

#### Scenario: Filtro de estado inválido

- **WHEN** un usuario autenticado llama a `GET /api/compras/pedidos?estado=enviado`
- **THEN** el sistema responde `422`

#### Scenario: Detalle de pedido con subtotales

- **WHEN** un usuario autenticado consulta un pedido con líneas 10 × 800 y 5 × 200
- **THEN** el sistema responde `200` con subtotales 8000 y 1000 y total estimado 9000

#### Scenario: Detalle de pedido inexistente

- **WHEN** un usuario autenticado llama a `GET /api/compras/pedidos/{id-inexistente}`
- **THEN** el sistema responde `404`

#### Scenario: Lectura anónima rechazada

- **WHEN** un cliente sin token llama a `GET /api/compras/pedidos`
- **THEN** el sistema responde `401`

### Requirement: Recibir pedido genera entradas de stock en una transacción

The system SHALL exponer `POST /api/compras/pedidos/{id}/recibir` (roles `duena` y `mostrador`) que, para un pedido `pendiente` y en una única transacción atómica: suma la `cantidad` de cada línea al `stock_actual` de su producto, crea por cada línea una entrada de stock (producto, cantidad, `costo_unitario` de la línea, usuario) y un `MovimientoStock` tipo `entrada` con `cantidad` positiva, `stock_previo`, `stock_nuevo`, el usuario y `ref_id` apuntando a esa entrada, actualiza el `costo` del producto al `costo_unitario` recibido (el `precio_venta` se recalcula según RN-PR-01 sin reescribir ventas históricas, RN-PR-04) y marca el pedido `recibido` con fecha y usuario de recepción (RN-CP-01, RN-CP-02). La recepción SHALL ser total: todas las líneas se reciben con la cantidad pedida. Si cualquier paso falla, nada de lo anterior SHALL persistir. Responde `200` con el detalle del pedido recibido. Productos o distribuidora dados de baja después de crear el pedido no impiden recibirlo.

#### Scenario: Recibir suma stock y crea movimientos de entrada

- **WHEN** un usuario autenticado recibe un pedido pendiente con líneas 10 unidades del producto A (stock 3) y 4 unidades del producto B (stock 0)
- **THEN** el sistema responde `200`, el stock de A queda en 13 y el de B en 4, existe un movimiento `entrada` por cada línea con `stock_previo`/`stock_nuevo` correctos y `ref_id` a su entrada, y el pedido queda `recibido`

#### Scenario: Recibir actualiza costo y precio sugerido

- **WHEN** se recibe un pedido cuya línea tiene `costo_unitario = 1200` para un producto con `costo = 1000` y `margen_pct = 0.5`
- **THEN** el producto queda con `costo = 1200` y `precio_venta = 1800`

#### Scenario: Mostrador puede registrar la entrada

- **WHEN** un usuario `mostrador` llama a `POST /api/compras/pedidos/{id}/recibir` sobre un pedido pendiente
- **THEN** el sistema responde `200` y las entradas y movimientos registran a ese usuario

#### Scenario: Fallo durante la recepción revierte todo

- **WHEN** la recepción de un pedido con dos líneas falla al procesar la segunda línea
- **THEN** el stock y el costo de ambos productos conservan sus valores previos, no existen entradas ni movimientos de ese pedido y el pedido sigue `pendiente`

#### Scenario: Recibir pedido inexistente

- **WHEN** un usuario autenticado llama a `POST /api/compras/pedidos/{id-inexistente}/recibir`
- **THEN** el sistema responde `404` y no se modifica ningún stock

#### Scenario: Recibir sin autenticación

- **WHEN** un cliente anónimo llama a `POST /api/compras/pedidos/{id}/recibir`
- **THEN** el sistema responde `401` y nada cambia

### Requirement: Transiciones de estado válidas y recepción idempotente

The system SHALL permitir solo las transiciones `pendiente → recibido` y `pendiente → cancelado`; `recibido` y `cancelado` son estados finales. Recibir o cancelar un pedido que no está `pendiente` SHALL responder `409` sin ningún efecto: en particular, un pedido nunca suma stock más de una vez, aunque la recepción se solicite repetida o concurrentemente.

#### Scenario: Recibir dos veces no duplica stock

- **WHEN** un usuario autenticado llama dos veces a `POST /api/compras/pedidos/{id}/recibir` sobre el mismo pedido
- **THEN** la primera llamada responde `200`, la segunda responde `409` y el stock, las entradas y los movimientos quedan exactamente como tras la primera

#### Scenario: Recibir un pedido cancelado

- **WHEN** un usuario autenticado intenta recibir un pedido en estado `cancelado`
- **THEN** el sistema responde `409` y no se modifica ningún stock

#### Scenario: Cancelar un pedido ya recibido

- **WHEN** una dueña intenta cancelar un pedido en estado `recibido`
- **THEN** el sistema responde `409` y el pedido, el stock y los costos no cambian

### Requirement: Cancelar pedido pendiente

The system SHALL exponer `POST /api/compras/pedidos/{id}/cancelar`, exclusivo del rol `duena`, que pasa un pedido `pendiente` a `cancelado` sin modificar stock, costos ni movimientos. Los pedidos no se borran físicamente.

#### Scenario: Dueña cancela pedido pendiente

- **WHEN** una dueña llama a `POST /api/compras/pedidos/{id}/cancelar` sobre un pedido pendiente
- **THEN** el sistema responde `200` con el pedido en estado `cancelado` y el stock de sus productos no cambia

#### Scenario: Mostrador no puede cancelar

- **WHEN** un usuario `mostrador` llama a `POST /api/compras/pedidos/{id}/cancelar`
- **THEN** el sistema responde `403` y el pedido sigue `pendiente`

#### Scenario: Cancelar pedido inexistente

- **WHEN** una dueña llama a `POST /api/compras/pedidos/{id-inexistente}/cancelar`
- **THEN** el sistema responde `404`

### Requirement: Pagos a distribuidoras independientes de pedidos

The system SHALL exponer, exclusivamente para el rol `duena`, `POST /api/compras/pagos` que acepta `{distribuidora_id, monto, metodo, fecha?, nota?}` con `monto > 0`, `metodo` en (`efectivo`, `transferencia`, `cheque`, `otro`) y `fecha` por defecto el día actual; `GET /api/compras/pagos` paginado y filtrable por `distribuidora_id`; y `DELETE /api/compras/pagos/{id}` que anula el pago por soft-delete (`activo=False`), nunca borrado físico. Un pago NO SHALL referenciar ni modificar pedidos, entradas ni stock (RN-CP-03). La distribuidora SHALL existir (sino `404`); se admiten pagos a distribuidoras dadas de baja.

#### Scenario: Registrar pago sin pedido asociado

- **WHEN** una dueña envía `{"distribuidora_id": "<d>", "monto": 5000, "metodo": "transferencia"}` a `POST /api/compras/pagos` sin existir pedidos de esa distribuidora
- **THEN** el sistema responde `201` con el pago creado, `fecha` del día y `activo=true`, y ningún pedido ni stock cambia

#### Scenario: Pago con monto inválido

- **WHEN** una dueña envía un pago con `monto` 0 o negativo, o un `metodo` fuera de la lista
- **THEN** el sistema responde `422` y no crea el pago

#### Scenario: Pago con campo pedido_id rechazado

- **WHEN** una dueña envía un pago que incluye `pedido_id`
- **THEN** el sistema responde `422` (campo no permitido)

#### Scenario: Pago a distribuidora inexistente

- **WHEN** una dueña envía un pago con un `distribuidora_id` que no existe
- **THEN** el sistema responde `404`

#### Scenario: Mostrador no gestiona pagos

- **WHEN** un usuario `mostrador` llama a `POST /api/compras/pagos` o `GET /api/compras/pagos`
- **THEN** el sistema responde `403` y no se crea ni expone ningún pago

#### Scenario: Anular pago

- **WHEN** una dueña llama a `DELETE /api/compras/pagos/{id}` sobre un pago activo
- **THEN** el sistema responde `204`, el pago queda con `activo=False` sin borrarse físicamente y deja de listarse

### Requirement: Cuenta simple por distribuidora

The system SHALL exponer `GET /api/compras/distribuidoras/{id}/cuenta`, exclusivo del rol `duena`, que devuelve `total_recibido` (suma de `cantidad × costo_unitario` de todas las entradas de pedidos recibidos de esa distribuidora), `total_pagado` (suma de pagos activos) y `saldo = total_recibido − total_pagado` (positivo = deuda con la distribuidora), calculados al vuelo sin persistir. Pedidos pendientes o cancelados no suman al total recibido.

#### Scenario: Saldo con entradas y pagos

- **WHEN** una distribuidora tiene un pedido recibido por 9000, un pedido pendiente por 4000 y pagos activos por 5000 y uno anulado por 1000
- **THEN** `GET /api/compras/distribuidoras/{id}/cuenta` responde `200` con `total_recibido = 9000`, `total_pagado = 5000` y `saldo = 4000`

#### Scenario: Distribuidora sin movimientos

- **WHEN** una dueña consulta la cuenta de una distribuidora sin entradas ni pagos
- **THEN** el sistema responde `200` con los tres valores en 0

#### Scenario: Cuenta de distribuidora inexistente

- **WHEN** una dueña consulta la cuenta de un id de distribuidora que no existe
- **THEN** el sistema responde `404`

#### Scenario: Mostrador no ve la cuenta

- **WHEN** un usuario `mostrador` llama a `GET /api/compras/distribuidoras/{id}/cuenta`
- **THEN** el sistema responde `403`

### Requirement: Migración 0006 crea las tablas de compras

The system SHALL incluir la migración Alembic `0006` (hija de `0005`) que crea las tablas de pedidos, líneas de pedido, entradas de stock y pagos a distribuidoras con sus claves foráneas, restricciones (`cantidad > 0`, `costo_unitario > 0`, `monto > 0`, un producto por pedido en líneas y en entradas) e índices sobre las claves foráneas consultadas, y cuyo downgrade elimina esas tablas y sus tipos sin residuos. Las entradas de stock SHALL ser append-only: no se modifican ni se borran.

#### Scenario: Upgrade y downgrade limpios

- **WHEN** se ejecuta `alembic upgrade head`, luego `alembic downgrade -1` y de nuevo `alembic upgrade head`
- **THEN** las cuatro tablas existen tras cada upgrade y no quedan tablas ni tipos residuales tras el downgrade

#### Scenario: La base rechaza cantidades no positivas

- **WHEN** se intenta persistir una línea de pedido con `cantidad = 0` saltando la API
- **THEN** la base rechaza la fila por su restricción de chequeo

#### Scenario: Entrada de stock inmutable

- **WHEN** se intenta modificar o borrar una entrada de stock ya registrada
- **THEN** la operación es rechazada y la entrada conserva sus valores
