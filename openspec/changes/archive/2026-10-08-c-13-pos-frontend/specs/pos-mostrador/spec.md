# Spec Delta

## Purpose

Interfaz de venta de mostrador de Animall: encontrar productos por nombre o código de barras, armar el carrito sin superar el stock, cobrar con uno o varios medios de pago (efectivo, transferencia, tarjeta), confirmar la venta de forma segura ante reintentos y entregar un comprobante imprimible, en menos de 60 segundos por venta.

## ADDED Requirements

### Requirement: Búsqueda de productos en el mostrador

The system SHALL ofrecer en `/pos` un campo de búsqueda con foco inicial que consulta `GET /api/productos/buscar` cuando hay al menos 2 caracteres, esperando a que la persona deje de tipear (debounce) para no consultar por cada tecla, y muestra nombre, SKU, precio de venta y stock disponible de cada resultado. Los productos sin stock SHALL verse deshabilitados con la leyenda "Sin stock". Un atajo de teclado SHALL devolver el foco al buscador desde cualquier punto de la pantalla.

#### Scenario: Buscar por nombre

- **WHEN** el mostrador escribe "royal" en el buscador
- **THEN** tras una breve pausa se listan los productos cuyo nombre contiene "royal" con precio y stock

#### Scenario: Producto sin stock no se puede agregar

- **WHEN** un resultado tiene `stock_actual = 0`
- **THEN** aparece deshabilitado con "Sin stock" y no puede agregarse al carrito

### Requirement: Lector de código de barras

The system SHALL aceptar lecturas de un lector de código de barras que funciona como teclado (caracteres seguidos de Enter). Al recibir Enter en el buscador, si un producto activo tiene SKU exactamente igual al texto, SHALL agregar una unidad al carrito, limpiar el buscador y mantener el foco; si hay un único resultado, SHALL agregarlo; si no hay coincidencias, SHALL avisar "No encontramos el código <texto>" sin modificar el carrito. Una lectura producida mientras el foco no está en un campo de texto SHALL dirigirse al buscador.

#### Scenario: Escaneo de un código existente

- **WHEN** el lector envía "RC-MINI-3KG" seguido de Enter
- **THEN** se agrega 1 unidad de "Royal Canin Mini Adulto 3kg" al carrito y el buscador queda vacío y con foco

#### Scenario: Escaneo repetido suma cantidad

- **WHEN** se escanea dos veces el mismo código
- **THEN** el carrito tiene una sola línea de ese producto con cantidad 2

#### Scenario: Código inexistente

- **WHEN** el lector envía un código sin coincidencias
- **THEN** se muestra "No encontramos el código" y el carrito no cambia

### Requirement: Carrito con validación de stock en memoria

The system SHALL mantener un carrito con una línea por producto (nombre, precio unitario, cantidad, subtotal) y el total, calculados con aritmética exacta en centavos a partir del `precio_venta` mostrado. La cantidad de una línea SHALL poder aumentarse, disminuirse, editarse o quitarse; nunca SHALL superar el `stock_actual` conocido del producto ni ser menor a 1, y al intentar superar el stock SHALL avisar "Solo hay N unidades". El carrito SHALL conservarse si la persona navega a otra pantalla y vuelve durante la misma sesión, y SHALL poder vaciarse con confirmación. Los precios son informativos: el total definitivo es el que devuelve el servidor.

#### Scenario: Total en centavos exactos

- **WHEN** el carrito tiene 2 unidades a $ 1.500 y 3 unidades a $ 0,10
- **THEN** el total mostrado es "$ 3.000,30"

#### Scenario: Tope por stock disponible

- **WHEN** un producto con `stock_actual = 2` está en el carrito con cantidad 2 y se intenta sumar otra unidad
- **THEN** la cantidad queda en 2 y se muestra "Solo hay 2 unidades"

### Requirement: Cliente opcional en la venta

The system SHALL permitir vender sin cliente (opción por defecto) o asociar uno buscándolo con `GET /api/clientes/buscar` por nombre, email o teléfono, o creándolo en el momento con solo el nombre (`POST /api/clientes`) sin salir del POS. El cliente elegido SHALL poder quitarse antes de cobrar.

#### Scenario: Alta inline de cliente

- **WHEN** el mostrador busca "Martina" sin resultados y elige "Crear cliente 'Martina'"
- **THEN** se crea el cliente con ese nombre, queda asociado a la venta y se informa "Cliente creado"

### Requirement: Cobro con pagos divididos y vuelto

The system SHALL abrir, al pulsar "Cobrar" con un carrito no vacío, un panel de cobro que ofrece únicamente los medios **efectivo**, **transferencia** y **tarjeta** (el medio Mercado Pago no se ofrece) y propone un pago en efectivo por el total. La persona SHALL poder dividir el total en hasta 5 pagos de medios iguales o distintos; la app SHALL mostrar en todo momento cuánto falta o sobra y SHALL habilitar "Confirmar venta" solo cuando la suma de los pagos es exactamente igual al total y cada monto es mayor a 0 con a lo sumo dos decimales. Para el pago en efectivo SHALL permitir ingresar "Paga con" (incluyendo botones de montos rápidos) y mostrar el vuelto = paga con − monto en efectivo; el vuelto es solo informativo y no se envía al servidor.

#### Scenario: Pago en efectivo con vuelto

- **WHEN** el total es $ 3.800 y el cliente paga con $ 5.000 en efectivo
- **THEN** la app muestra vuelto "$ 1.200,00" y habilita "Confirmar venta" con un pago efectivo de 3800

#### Scenario: Pago dividido incompleto

- **WHEN** el total es $ 3.800 y se cargan efectivo $ 1.800 y tarjeta $ 1.500
- **THEN** la app muestra "Faltan $ 500,00" y "Confirmar venta" queda deshabilitado

#### Scenario: Sin Mercado Pago

- **WHEN** se abre el panel de cobro
- **THEN** los únicos medios disponibles son efectivo, transferencia y tarjeta

### Requirement: Confirmación de venta en dos pasos e idempotente

The system SHALL registrar la venta con `POST /api/ventas` (borrador con `idempotency_key` UUID, `cliente_id` opcional y líneas `producto_id`/`cantidad`, sin precios) y luego `POST /api/ventas/{id}/confirmar` con los pagos. Un reintento del mismo carrito sin cambios (por ejemplo tras un error de red) SHALL reutilizar la misma `idempotency_key` y los mismos pagos para no duplicar la venta; un carrito modificado SHALL usar una clave nueva. Mientras se confirma, la acción SHALL quedar deshabilitada para evitar dobles envíos. Ante `409` con faltantes (en el borrador o en la confirmación) la app SHALL marcar cada línea afectada con el stock disponible informado y ofrecer "Ajustar a disponible", sin vaciar el carrito. Si el total devuelto por el servidor difiere del mostrado, la app SHALL actualizar el total y los pagos propuestos antes de confirmar. Tras confirmar SHALL vaciar el carrito, refrescar stock y alertas, y mostrar el comprobante.

#### Scenario: Venta confirmada

- **WHEN** el mostrador cobra un carrito válido con pagos que igualan el total
- **THEN** la app crea el borrador, lo confirma, muestra "Venta registrada", vacía el carrito y presenta el comprobante

#### Scenario: Stock insuficiente informado por el servidor

- **WHEN** al confirmar el servidor responde `409` indicando para un producto solicitado 3 y disponible 1
- **THEN** la línea de ese producto se marca "Disponible: 1" con la opción "Ajustar a disponible" y el carrito se conserva

#### Scenario: Reintento tras error de red

- **WHEN** la confirmación falla por error de red y el mostrador pulsa "Reintentar" sin cambiar el carrito
- **THEN** la app reenvía con la misma `idempotency_key` y los mismos pagos y queda registrada una sola venta

### Requirement: Comprobante imprimible

The system SHALL mostrar tras cada venta confirmada, y desde el detalle de cualquier venta, un comprobante con nombre del comercio, fecha y hora, número corto de venta, cliente (si hay), líneas (cantidad, producto, precio unitario, subtotal), total, pagos por medio, vuelto (si corresponde, solo en la venta recién cobrada) y la leyenda "Comprobante no válido como factura". "Imprimir" SHALL imprimir solo el comprobante, con un formato apto para impresora térmica de 80 mm y también para hoja A4. El comprobante NO SHALL incluir datos fiscales (CAE, CUIT, tipo de factura). "Nueva venta" SHALL cerrar el comprobante y devolver el foco al buscador.

#### Scenario: Imprimir comprobante

- **WHEN** el mostrador pulsa "Imprimir" en el comprobante de una venta confirmada
- **THEN** se abre el diálogo de impresión del navegador y la vista de impresión contiene solo el comprobante

#### Scenario: Volver a vender

- **WHEN** el mostrador pulsa "Nueva venta" en el comprobante
- **THEN** el comprobante se cierra, el carrito está vacío y el buscador tiene el foco

### Requirement: Listado, detalle y anulación de ventas

The system SHALL ofrecer `/ventas` con el listado paginado de `GET /api/ventas` (fecha, número corto, cliente, total, estado), filtrable por estado y rango de fechas (por defecto hoy) y `/ventas/:id` con el detalle (líneas, pagos, vendedor, estado, fechas, motivo de anulación) y acceso a reimprimir el comprobante. Un `mostrador` SHALL ver solo sus ventas (lo garantiza el servidor). Solo la dueña SHALL ver la acción "Anular venta" en ventas `confirmada`, que exige un motivo no vacío de hasta 300 caracteres y confirmación, llama a `POST /api/ventas/{id}/anular`, y al terminar muestra la venta como anulada y refresca stock.

#### Scenario: Dueña anula una venta

- **WHEN** la dueña anula una venta confirmada con motivo "cliente se arrepintió"
- **THEN** la venta aparece como "Anulada" con ese motivo y se informa "Venta anulada, stock devuelto"

#### Scenario: Anulación sin motivo

- **WHEN** la dueña intenta anular dejando el motivo vacío
- **THEN** la acción no se envía y el campo muestra "Indicá el motivo"

#### Scenario: Mostrador sin anulación

- **WHEN** un `mostrador` abre el detalle de una venta propia confirmada
- **THEN** no ve la acción "Anular venta"
