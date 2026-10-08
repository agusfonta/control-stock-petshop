# Ventas Specification

## Purpose

Permitir cobrar ventas de mostrador que descuentan stock en una única transacción con sus líneas y pagos, con bloqueo duro sin stock, pagos que igualan el total, anulación auditable solo por la dueña e idempotencia por clave, de modo que el stock y el dinero registrados sean siempre consistentes (US-001, RN-VT-01, RN-VT-02, RN-VT-03, RN-VT-04).

## Requirements

### Requirement: Crear venta en borrador con precios del servidor

The system SHALL exponer `POST /api/ventas`, para los roles `duena` y `mostrador`, que acepta `{idempotency_key, cliente_id?, lineas: [{producto_id, cantidad}]}` con schema Pydantic estricto y crea una venta en estado `borrador` registrando al usuario como vendedor. `idempotency_key` SHALL ser un UUID en formato canónico. Cada línea SHALL tener `cantidad` entera `> 0` y un `producto_id` no repetido dentro de la venta; la venta SHALL tener entre 1 y 100 líneas. El `precio_unit` de cada línea SHALL ser el `precio_venta` vigente del producto al crear el borrador redondeado a centavos (mitad hacia arriba), el `subtotal` SHALL ser `cantidad × precio_unit` y el `total` de la venta SHALL ser la suma de los subtotales, todos calculados por el servidor; el cliente no envía precios, subtotales ni total. Los productos SHALL existir (sino `404`) y estar activos (sino `422`). Si viene `cliente_id`, el cliente SHALL existir (sino `404`) y estar activo (sino `422`); sin `cliente_id` la venta queda sin cliente. Crear un borrador NO SHALL modificar `stock_actual`, crear movimientos de stock ni registrar pagos. Responde `201` con el detalle de la venta.

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

#### Scenario: Alta sin autenticación

- **WHEN** un cliente anónimo envía una venta a `POST /api/ventas`
- **THEN** el sistema responde `401` y no crea la venta

### Requirement: Bloqueo duro por stock insuficiente

The system SHALL rechazar la creación de un borrador y la confirmación de una venta cuando alguna línea tenga `cantidad` mayor al `stock_actual` de su producto en ese momento (RN-VT-01). El rechazo SHALL responder `409` con un detalle que liste, por cada línea faltante, el `producto_id`, la cantidad solicitada y el stock disponible, y NO SHALL modificar stock, movimientos, pagos ni el estado de la venta. En la confirmación el stock SHALL revalidarse dentro de la misma transacción que lo descuenta, de modo que un borrador creado antes no pueda vender stock que ya no existe.

#### Scenario: Borrador con cantidad mayor al stock

- **WHEN** un usuario autenticado crea un borrador con 3 unidades de un producto con `stock_actual = 2`
- **THEN** el sistema responde `409` con el faltante (solicitado 3, disponible 2) y no crea la venta

#### Scenario: Stock consumido entre borrador y confirmación

- **WHEN** se crea un borrador con 2 unidades de un producto con stock 2, luego otra venta confirma 1 unidad de ese producto, y después se intenta confirmar el primer borrador
- **THEN** la confirmación responde `409` con el faltante (solicitado 2, disponible 1), el stock queda en 1 y el borrador sigue en `borrador` sin pagos

#### Scenario: Dos ventas compiten por la última unidad

- **WHEN** existen dos borradores de 1 unidad cada uno para un producto con `stock_actual = 1` y ambos se confirman, en secuencia o concurrentemente
- **THEN** exactamente una confirmación responde `200`, la otra responde `409`, el stock final es 0 y existe un solo movimiento de venta para ese producto

### Requirement: Alta idempotente por idempotency_key

The system SHALL garantizar que la `idempotency_key` identifica de forma única una venta por vendedor. Un `POST /api/ventas` que repite una `idempotency_key` ya usada por el mismo usuario con el mismo contenido (mismo `cliente_id` y mismo conjunto de líneas `producto_id`/`cantidad`) SHALL responder `200` con la venta existente, en el estado en que se encuentre, sin crear otra venta. Si el contenido difiere SHALL responder `422` sin crear ni modificar nada. La misma clave usada por usuarios distintos SHALL tratarse como claves independientes y nunca exponer la venta de otro usuario.

#### Scenario: Reintento con la misma clave devuelve la misma venta

- **WHEN** un usuario envía dos veces el mismo `POST /api/ventas` con la misma `idempotency_key`
- **THEN** la primera respuesta es `201`, la segunda es `200` con el mismo `id` de venta y existe una sola venta con esa clave

#### Scenario: Reintento después de confirmar

- **WHEN** un usuario confirma una venta y luego repite el `POST /api/ventas` original con la misma `idempotency_key` y el mismo contenido
- **THEN** el sistema responde `200` con esa venta en estado `confirmada` y el stock no cambia

#### Scenario: Misma clave con otro contenido

- **WHEN** un usuario reutiliza una `idempotency_key` propia con líneas distintas a las de la venta original
- **THEN** el sistema responde `422` y no crea ni modifica ninguna venta

#### Scenario: Misma clave de otro usuario

- **WHEN** un usuario `mostrador` envía una `idempotency_key` que ya usó la dueña para otra venta
- **THEN** el sistema crea una venta nueva para el mostrador (`201`) y no devuelve ni modifica la venta de la dueña

#### Scenario: Clave con formato inválido

- **WHEN** un usuario envía una venta sin `idempotency_key` o con un valor que no es un UUID
- **THEN** el sistema responde `422`

### Requirement: Confirmar venta en una transacción

The system SHALL exponer `POST /api/ventas/{id}/confirmar`, para los roles `duena` y `mostrador`, que acepta `{pagos: [{metodo, monto, ref_mp?}]}` y, para una venta en `borrador` y en una única transacción atómica: revalida el stock de todas las líneas (RN-VT-01), valida los pagos (RN-VT-04), resta la `cantidad` de cada línea al `stock_actual` de su producto creando por línea un `MovimientoStock` tipo `venta` con `cantidad` negativa, `stock_previo`, `stock_nuevo`, el usuario que confirma y `ref_id` igual al id de la venta, registra los pagos, marca la venta `confirmada` con fecha y usuario de confirmación y registra el evento de venta confirmada (ver "Evento de venta para facturación electrónica"). Si cualquier paso falla, nada de lo anterior SHALL persistir (RN-VT-02). Responde `200` con el detalle de la venta confirmada. Un `mostrador` solo puede confirmar ventas propias; la venta de otro usuario SHALL responder `404` para él. La dueña puede confirmar cualquier venta.

#### Scenario: Venta confirmada descuenta stock y crea movimientos

- **WHEN** un usuario `mostrador` confirma su borrador de 2 unidades del producto A (stock 5) y 1 unidad del producto B (stock 1), con total 3800, enviando un pago `efectivo` de 3800
- **THEN** el sistema responde `200` con la venta `confirmada`, el stock de A queda en 3 y el de B en 0, existe un movimiento `venta` por línea con `cantidad` −2 y −1, `stock_previo`/`stock_nuevo` correctos y `ref_id` igual al id de la venta, y existe un pago de 3800

#### Scenario: Fallo durante la confirmación revierte todo

- **WHEN** la confirmación de una venta con dos líneas falla al procesar la segunda línea
- **THEN** el stock de ambos productos conserva sus valores previos, no existen movimientos ni pagos de esa venta y la venta sigue en `borrador`

#### Scenario: Mostrador no confirma ventas ajenas

- **WHEN** un usuario `mostrador` intenta confirmar un borrador creado por otro usuario
- **THEN** el sistema responde `404` y la venta, el stock y los pagos no cambian

#### Scenario: Dueña confirma venta de un mostrador

- **WHEN** una dueña confirma un borrador creado por un usuario `mostrador` con pagos que igualan el total
- **THEN** el sistema responde `200`, la venta conserva al mostrador como vendedor y registra a la dueña como usuaria de confirmación

#### Scenario: Confirmar venta inexistente

- **WHEN** un usuario autenticado llama a `POST /api/ventas/{id-inexistente}/confirmar`
- **THEN** el sistema responde `404` y no se modifica ningún stock

#### Scenario: Confirmar sin autenticación

- **WHEN** un cliente anónimo llama a `POST /api/ventas/{id}/confirmar`
- **THEN** el sistema responde `401` y nada cambia

### Requirement: Pagos que igualan el total

The system SHALL exigir en la confirmación entre 1 y 5 pagos, cada uno con `metodo` en (`efectivo`, `transferencia`, `mp`, `tarjeta`) y `monto` decimal `> 0` con a lo sumo dos decimales, cuya suma SHALL ser exactamente igual al `total` de la venta (RN-VT-04); se admiten varios pagos de métodos distintos o iguales en una misma venta. `ref_mp` SHALL ser opcional y solo admitido en pagos con `metodo = mp`; un mismo `ref_mp` no SHALL registrarse en más de un pago del sistema. Un incumplimiento SHALL rechazarse antes de tocar stock: suma distinta del total, monto inválido, método fuera de la lista, cantidad de pagos fuera de rango o `ref_mp` en un método distinto de `mp` responden `422`; un `ref_mp` ya registrado responde `409`. En todos los casos la venta sigue en `borrador` sin cambios de stock.

#### Scenario: Pago incompleto no confirma

- **WHEN** un usuario intenta confirmar una venta de total 3800 con un único pago de 3000
- **THEN** el sistema responde `422`, la venta sigue en `borrador`, el stock no cambia y no se registran pagos

#### Scenario: Pago excedente no confirma

- **WHEN** un usuario intenta confirmar una venta de total 3800 con pagos que suman 4000
- **THEN** el sistema responde `422` y nada cambia

#### Scenario: Pago dividido entre métodos

- **WHEN** un usuario confirma una venta de total 3800 con un pago `efectivo` de 1800 y un pago `mp` de 2000 con `ref_mp = "MP-123"`
- **THEN** el sistema responde `200` y la venta queda con ambos pagos registrados

#### Scenario: Referencia de Mercado Pago en otro método

- **WHEN** un usuario intenta confirmar con un pago `efectivo` que incluye `ref_mp`
- **THEN** el sistema responde `422` y nada cambia

#### Scenario: Referencia de Mercado Pago repetida

- **WHEN** ya existe un pago registrado con `ref_mp = "MP-123"` y un usuario intenta confirmar otra venta con un pago `mp` con esa misma referencia
- **THEN** el sistema responde `409` y la segunda venta sigue en `borrador` sin cambios de stock

#### Scenario: Monto o método inválido

- **WHEN** un usuario intenta confirmar con un pago de `monto` 0, negativo o con tres decimales, con un `metodo` fuera de la lista, o con una lista de pagos vacía
- **THEN** el sistema responde `422` y nada cambia

### Requirement: Transiciones de estado válidas e idempotentes

The system SHALL permitir solo las transiciones `borrador → confirmada` y `confirmada → anulada`; `anulada` es estado final y no existe edición ni borrado de ventas. Repetir una transición ya realizada SHALL ser idempotente y no producir ningún efecto adicional: confirmar una venta ya `confirmada` con los mismos pagos (mismo conjunto de `metodo`, `monto` y `ref_mp`) responde `200` con la venta sin cambios, y anular una venta ya `anulada` responde `200` con la venta sin cambios. Confirmar una venta `confirmada` con pagos distintos, confirmar una venta `anulada` o anular una venta en `borrador` SHALL responder `409` sin efectos. En ningún caso una venta descuenta o devuelve stock más de una vez, aunque la operación se solicite repetida o concurrentemente.

#### Scenario: Confirmar dos veces no descuenta stock dos veces

- **WHEN** un usuario llama dos veces a `POST /api/ventas/{id}/confirmar` con los mismos pagos sobre la misma venta
- **THEN** ambas respuestas son `200` con la venta `confirmada`, y el stock, los movimientos y los pagos quedan exactamente como tras la primera llamada

#### Scenario: Reconfirmar con pagos distintos

- **WHEN** un usuario confirma una venta y luego vuelve a confirmarla con otros pagos
- **THEN** la segunda llamada responde `409` y los pagos registrados son los de la primera confirmación

#### Scenario: Confirmar una venta anulada

- **WHEN** un usuario intenta confirmar una venta en estado `anulada`
- **THEN** el sistema responde `409` y el stock no cambia

#### Scenario: Anular un borrador

- **WHEN** una dueña intenta anular una venta en estado `borrador`
- **THEN** el sistema responde `409` y la venta sigue en `borrador`

### Requirement: Anular venta solo por dueña con movimiento inverso

The system SHALL exponer `POST /api/ventas/{id}/anular`, exclusivo del rol `duena`, que acepta `{motivo}` (texto obligatorio no vacío, máximo 300 caracteres) y, para una venta `confirmada` y en una única transacción atómica: suma la `cantidad` de cada línea al `stock_actual` de su producto creando por línea un `MovimientoStock` tipo `venta` con `cantidad` positiva, `stock_previo`, `stock_nuevo`, la dueña como usuaria, `ref_id` igual al id de la venta y un motivo que identifica la anulación; marca la venta `anulada` con fecha, usuaria y motivo de anulación; y registra el evento de venta anulada (RN-VT-03). Los movimientos originales de la venta no se modifican ni se borran. Los pagos registrados se conservan sin cambios (la anulación no registra devolución de dinero). Productos dados de baja después de la venta no impiden anularla. Si cualquier paso falla, nada SHALL persistir. Responde `200` con el detalle de la venta anulada.

#### Scenario: Anulación devuelve stock con movimiento inverso

- **WHEN** una dueña anula con motivo "cliente se arrepintió" una venta confirmada de 2 unidades del producto A, cuyo stock actual es 3
- **THEN** el sistema responde `200` con la venta `anulada` y el motivo, el stock de A queda en 5, existe un movimiento `venta` de `cantidad` +2 con `ref_id` igual al id de la venta, y el movimiento original de −2 sigue intacto

#### Scenario: Mostrador no puede anular

- **WHEN** un usuario `mostrador` llama a `POST /api/ventas/{id}/anular` sobre una venta confirmada propia
- **THEN** el sistema responde `403` y la venta y el stock no cambian

#### Scenario: Anular sin motivo

- **WHEN** una dueña llama a `POST /api/ventas/{id}/anular` sin `motivo` o con un motivo en blanco
- **THEN** el sistema responde `422` y la venta sigue `confirmada`

#### Scenario: Anular dos veces no devuelve stock dos veces

- **WHEN** una dueña anula dos veces la misma venta confirmada
- **THEN** ambas respuestas son `200`, y el stock y los movimientos quedan exactamente como tras la primera anulación

#### Scenario: Anular venta inexistente

- **WHEN** una dueña llama a `POST /api/ventas/{id-inexistente}/anular`
- **THEN** el sistema responde `404`

### Requirement: Consultar ventas con propiedad por vendedor

The system SHALL exponer `GET /api/ventas/{id}` con el detalle de la venta (estado, cliente, vendedor, total, líneas con `producto_id`, nombre del producto, `cantidad`, `precio_unit` y `subtotal`, pagos con `metodo`, `monto` y `ref_mp`, fechas de creación, confirmación y anulación y motivo de anulación) y `GET /api/ventas` paginado (metadata `total`, `page`, `page_size`, `total_pages`) ordenado por fecha de creación descendente, filtrable por `estado`, `cliente_id` y rango `desde`/`hasta` (fechas-hora ISO 8601 con zona horaria, intervalo `[desde, hasta)` sobre la fecha de creación). Sin filtro de `estado`, el listado SHALL incluir solo ventas `confirmada` y `anulada`. Un `mostrador` SHALL ver únicamente sus propias ventas: el detalle de una venta ajena responde `404` y el listado se restringe siempre a sus ventas. La dueña ve todas y puede filtrar además por `usuario_id`.

#### Scenario: Mostrador ve el detalle de su venta

- **WHEN** un usuario `mostrador` consulta `GET /api/ventas/{id}` de una venta propia confirmada
- **THEN** el sistema responde `200` con líneas, pagos, total y estado

#### Scenario: Mostrador no ve ventas ajenas

- **WHEN** un usuario `mostrador` consulta `GET /api/ventas/{id}` de una venta de otro usuario, o lista `GET /api/ventas` existiendo ventas de otros usuarios
- **THEN** el detalle responde `404` y el listado contiene solo sus propias ventas

#### Scenario: Dueña lista ventas confirmadas de un período

- **WHEN** una dueña llama a `GET /api/ventas?estado=confirmada&desde=<inicio del día>&hasta=<inicio del día siguiente>`
- **THEN** el sistema responde `200` solo con ventas confirmadas creadas en ese intervalo, de todos los vendedores, con metadata de paginación

#### Scenario: Listado por defecto excluye borradores

- **WHEN** una dueña llama a `GET /api/ventas` sin filtro de estado existiendo ventas en `borrador`, `confirmada` y `anulada`
- **THEN** el listado contiene solo las ventas `confirmada` y `anulada`

#### Scenario: Filtros inválidos

- **WHEN** un usuario autenticado llama a `GET /api/ventas?estado=pagada` o con un `desde` sin zona horaria
- **THEN** el sistema responde `422`

#### Scenario: Lectura anónima rechazada

- **WHEN** un cliente sin token llama a `GET /api/ventas` o a `GET /api/ventas/{id}`
- **THEN** el sistema responde `401`

### Requirement: Evento de venta para facturación electrónica

The system SHALL registrar, en la misma transacción que confirma una venta, exactamente un evento pendiente `venta.confirmada` que referencia a esa venta, y en la misma transacción que la anula, exactamente un evento pendiente `venta.anulada`. Los eventos SHALL persistir si y solo si la transición persiste, nunca duplicarse para la misma venta y transición aunque la operación se repita, y quedar pendientes de procesar hasta que un consumidor posterior (facturación electrónica, C-11) los marque como procesados. Confirmar o anular una venta NO SHALL depender de la disponibilidad de servicios externos (ARCA, Redis): la venta se confirma aunque no exista ningún consumidor.

#### Scenario: Confirmar registra un evento pendiente

- **WHEN** se confirma una venta
- **THEN** existe exactamente un evento `venta.confirmada` pendiente que referencia a esa venta

#### Scenario: Confirmación fallida no deja evento

- **WHEN** la confirmación de una venta es rechazada por stock insuficiente o falla a mitad de la transacción
- **THEN** no existe ningún evento para esa venta

#### Scenario: Reintentos no duplican eventos

- **WHEN** una venta se confirma dos veces con los mismos pagos y luego se anula dos veces
- **THEN** existe exactamente un evento `venta.confirmada` y exactamente un evento `venta.anulada` para esa venta

### Requirement: Migración 0007 crea las tablas de ventas

The system SHALL incluir la migración Alembic `0007` (hija de `0006`) que crea las tablas de ventas, líneas de venta, pagos de venta y eventos pendientes con sus claves foráneas, restricciones (`cantidad > 0`, `precio_unit > 0`, `monto > 0`, `total > 0`, un producto por venta, una clave de idempotencia por vendedor, un `ref_mp` por pago, `ref_mp` solo en pagos `mp`, fechas de confirmación y anulación presentes según el estado, un evento por venta y tipo) e índices para el historial por cliente, el listado por vendedor y por fecha, y cuyo downgrade elimina esas tablas y sus tipos sin residuos. Las líneas y los pagos de venta SHALL ser inmutables: no se modifican ni se borran.

#### Scenario: Upgrade y downgrade limpios

- **WHEN** se ejecuta `alembic upgrade head`, luego `alembic downgrade -1` y de nuevo `alembic upgrade head`
- **THEN** las cuatro tablas existen tras cada upgrade y no quedan tablas ni tipos residuales tras el downgrade

#### Scenario: La base rechaza datos inválidos

- **WHEN** se intenta persistir saltando la API una línea de venta con `cantidad = 0`, un pago con `monto = 0` o un pago `efectivo` con `ref_mp`
- **THEN** la base rechaza la fila por su restricción

#### Scenario: Línea y pago de venta inmutables

- **WHEN** se intenta modificar o borrar una línea o un pago de venta ya registrados
- **THEN** la operación es rechazada y la fila conserva sus valores
