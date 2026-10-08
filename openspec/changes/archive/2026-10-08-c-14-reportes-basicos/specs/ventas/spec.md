# Spec Delta

## MODIFIED Requirements

### Requirement: Crear venta en borrador con precios del servidor

The system SHALL exponer `POST /api/ventas`, para los roles `duena` y `mostrador`, que acepta `{idempotency_key, cliente_id?, lineas: [{producto_id, cantidad}]}` con schema Pydantic estricto y crea una venta en estado `borrador` registrando al usuario como vendedor. `idempotency_key` SHALL ser un UUID en formato canónico. Cada línea SHALL tener `cantidad` entera `> 0` y un `producto_id` no repetido dentro de la venta; la venta SHALL tener entre 1 y 100 líneas. El `precio_unit` de cada línea SHALL ser el `precio_venta` vigente del producto al crear el borrador redondeado a centavos (mitad hacia arriba), el `subtotal` SHALL ser `cantidad × precio_unit` y el `total` de la venta SHALL ser la suma de los subtotales, todos calculados por el servidor; el cliente no envía precios, subtotales ni total. Cada línea SHALL además congelar como costo unitario el `costo` vigente del producto en ese mismo momento; ese costo lo fija el servidor, el cliente no puede enviarlo, no cambia aunque el costo del producto cambie después y NO SHALL exponerse en ninguna respuesta de la API de ventas. Los productos SHALL existir (sino `404`) y estar activos (sino `422`). Si viene `cliente_id`, el cliente SHALL existir (sino `404`) y estar activo (sino `422`); sin `cliente_id` la venta queda sin cliente. Crear un borrador NO SHALL modificar `stock_actual`, crear movimientos de stock ni registrar pagos. Responde `201` con el detalle de la venta.

#### Scenario: Borrador con precio y total calculados por el servidor

- **WHEN** un usuario `mostrador` envía una venta con 2 unidades de un producto con `precio_venta = 1500` y 1 unidad de otro con `precio_venta = 800`
- **THEN** el sistema responde `201` con la venta en `borrador`, líneas con `precio_unit` 1500 y 800, subtotales 3000 y 800, `total = 3800`, el vendedor igual a ese usuario, y el `stock_actual` de ambos productos sin cambios y sin movimientos de stock

#### Scenario: Precio con más de dos decimales se redondea a centavos

- **WHEN** se crea un borrador con 2 unidades de un producto con `costo = 10.03` y `margen_pct = 0.5` (`precio_venta = 15.045`)
- **THEN** la línea queda con `precio_unit = 15.05` (mitad hacia arriba), `subtotal = 30.10` y el `total` es 30.10

#### Scenario: Venta sin cliente

- **WHEN** un usuario autenticado crea un borrador válido sin `cliente_id`
- **THEN** el sistema responde `201` con `cliente_id = null`

#### Scenario: Precio enviado por el cliente rechazado

- **WHEN** un usuario autenticado envía una línea con un campo `precio_unit` o la venta con un campo `total`
- **THEN** el sistema responde `422` (campo no permitido) y no crea la venta

#### Scenario: Líneas inválidas

- **WHEN** un usuario autenticado envía `lineas` vacío, una `cantidad` de 0, negativa o no entera, o un `producto_id` repetido
- **THEN** el sistema responde `422` y no crea la venta

#### Scenario: Producto inexistente o dado de baja

- **WHEN** un usuario autenticado envía una línea con un `producto_id` que no existe, o con un producto dado de baja
- **THEN** el sistema responde `404` en el primer caso y `422` en el segundo, sin crear la venta

#### Scenario: Cliente inexistente o dado de baja

- **WHEN** un usuario autenticado envía un `cliente_id` que no existe, o el de un cliente dado de baja
- **THEN** el sistema responde `404` en el primer caso y `422` en el segundo, sin crear la venta

#### Scenario: Cambio de precio posterior no altera el borrador

- **WHEN** se crea un borrador con un producto a `precio_venta = 1500` y luego la dueña sube el costo del producto
- **THEN** la línea del borrador conserva `precio_unit = 1500` y el `total` no cambia

#### Scenario: Costo congelado al crear el borrador

- **WHEN** se crea un borrador con un producto de `costo = 1000` y luego una recepción de mercadería cambia el costo del producto a 1200
- **THEN** la línea conserva como costo unitario 1000, también después de confirmar la venta

#### Scenario: Costo no visible ni enviable en la API de ventas

- **WHEN** un usuario autenticado crea, confirma, anula o consulta una venta, o envía una línea con un campo `costo_unit`
- **THEN** ninguna respuesta de la API de ventas incluye el costo unitario, y el envío del campo responde `422` (campo no permitido) sin crear la venta

#### Scenario: Alta sin autenticación

- **WHEN** un cliente anónimo envía una venta a `POST /api/ventas`
- **THEN** el sistema responde `401` y no crea la venta

## ADDED Requirements

### Requirement: Migración 0008 agrega el costo congelado a las líneas de venta

The system SHALL incluir la migración Alembic `0008` (hija de `0007`) que agrega a las líneas de venta una columna de costo unitario nullable con la restricción "nulo o mayor que cero", y un índice sobre ventas por estado y fecha de confirmación para los reportes; su downgrade SHALL eliminar la columna y el índice sin residuos. Las líneas existentes antes de la migración SHALL quedar con costo nulo (sin completar con el costo actual del producto). Las líneas de venta siguen siendo inmutables.

#### Scenario: Upgrade y downgrade limpios

- **WHEN** se ejecuta `alembic upgrade head`, luego `alembic downgrade -1` y de nuevo `alembic upgrade head`
- **THEN** la columna de costo y el índice de reportes existen tras cada upgrade y no quedan tras el downgrade, y las líneas de venta conservan sus demás datos

#### Scenario: Líneas previas quedan sin costo

- **WHEN** se aplica la migración sobre una base con líneas de venta ya registradas
- **THEN** esas líneas quedan con costo unitario nulo y el resto de sus valores intactos

#### Scenario: La base rechaza costo no positivo

- **WHEN** se intenta persistir saltando la API una línea de venta con costo unitario 0 o negativo
- **THEN** la base rechaza la fila por su restricción
