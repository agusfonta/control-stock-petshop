# Spec Delta

## Purpose

Pantallas de gestión del negocio sobre la API existente: catálogo de productos, stock y alertas, clientes, distribuidoras con listas de precios, pedidos y pagos de compras, y reportes, respetando la matriz de permisos dueña/mostrador.

## ADDED Requirements

### Requirement: Catálogo de productos

The system SHALL ofrecer `/productos` con el listado paginado de productos activos (SKU, nombre, marca, categoría, precio de venta, stock, mínimo) y búsqueda por SKU o nombre. Para la dueña SHALL mostrar además costo y margen y permitir: crear producto (SKU, nombre, marca, categoría, unidad `unidad`/`bolsa`/`caja`, costo, margen %, stock inicial, stock mínimo, distribuidora por defecto), editarlo (sin modificar el stock, que solo cambia por movimientos), cambiar margen y stock mínimo, y darlo de baja con confirmación. Al cargar costo y margen el formulario SHALL mostrar el precio de venta resultante (`costo × (1 + margen)`) como vista previa; el valor definitivo es el que devuelve el servidor. El margen SHALL ingresarse como porcentaje (35 = 35 %) y enviarse como fracción (0.35). Un SKU repetido (`409`) SHALL marcarse en el campo SKU.

#### Scenario: Vista previa del precio

- **WHEN** la dueña carga costo 18000 y margen 35 en el alta de producto
- **THEN** el formulario muestra precio de venta "$ 24.300,00" antes de guardar

#### Scenario: Edición de margen recalcula el precio

- **WHEN** la dueña cambia el margen de un producto y guarda
- **THEN** el listado muestra el nuevo precio de venta devuelto por el servidor y se informa "Producto actualizado"

#### Scenario: Mostrador consulta el catálogo

- **WHEN** un `mostrador` abre `/productos`
- **THEN** ve precio de venta y stock pero no costo, margen ni acciones de edición

### Requirement: Stock, alertas y ajustes

The system SHALL ofrecer `/stock` con la consulta rápida de `GET /api/stock` (búsqueda, filtro "solo bajo mínimo", orden por menor cobertura) resaltando los productos con `bajo_minimo`, y un resumen de alertas de `GET /api/stock/alertas` con la cantidad bajo mínimo. Solo la dueña SHALL ver "Ajustar stock" por producto, con un diálogo que pide la diferencia (positiva o negativa, distinta de 0) y un motivo obligatorio, muestra el stock resultante antes de confirmar, impide que quede negativo y, tras `POST /api/productos/{id}/ajustar`, informa el movimiento (stock previo → nuevo) y refresca stock, alertas y catálogo.

#### Scenario: Ajuste con motivo

- **WHEN** la dueña ajusta −2 con motivo "rotura" un producto con stock 10
- **THEN** el diálogo muestra "Quedará en 8", al confirmar se informa "Stock ajustado: 10 → 8" y la fila muestra 8

#### Scenario: Ajuste sin motivo

- **WHEN** la dueña intenta confirmar un ajuste sin motivo
- **THEN** el campo motivo muestra "Indicá el motivo" y no se envía la solicitud

#### Scenario: Filtro bajo mínimo

- **WHEN** se activa "Solo bajo mínimo"
- **THEN** la tabla lista solo productos con `stock_actual <= stock_minimo`

### Requirement: Clientes

The system SHALL ofrecer `/clientes` con el listado paginado de clientes activos, búsqueda por nombre, email o teléfono y alta (nombre obligatorio; teléfono, email y dirección opcionales) para ambos roles; edición y baja solo para la dueña; y `/clientes/:id` con los datos del cliente y su historial de ventas paginado (`GET /api/clientes/{id}/ventas`) con acceso al detalle de cada venta. Un email repetido (`409`) SHALL marcarse en el campo email y los errores de formato (`422`) en su campo.

#### Scenario: Alta de cliente desde la lista

- **WHEN** un `mostrador` crea un cliente con nombre "Lucía Herrera" y teléfono "351-8901234"
- **THEN** el cliente aparece en la lista y se informa "Cliente creado"

#### Scenario: Historial de ventas del cliente

- **WHEN** la dueña abre el detalle de un cliente con dos ventas confirmadas
- **THEN** ve ambas ventas con fecha, total y estado, la más reciente primero

### Requirement: Distribuidoras y listas de precios

The system SHALL ofrecer `/distribuidoras` con el listado de distribuidoras activas y, por distribuidora, su lista de precios (producto, costo). La dueña SHALL poder crear, editar y dar de baja distribuidoras y agregar, cambiar o quitar costos de su lista; un producto ya presente en la lista (`409`) SHALL informarse. Ambos roles SHALL poder usar el comparador: elegido un producto, ver sus costos por distribuidora ordenados de menor a mayor con el precio sugerido (`GET /api/distribuidoras/comparar`), destacando el más barato.

#### Scenario: Comparar costos de un producto

- **WHEN** se compara un producto presente en las listas de dos distribuidoras con costos 18000 y 17500
- **THEN** se listan ambas con la de 17500 primero y destacada, cada una con su precio sugerido

#### Scenario: Producto repetido en la lista

- **WHEN** la dueña agrega a una lista un producto que ya figura en ella
- **THEN** se informa "Ese producto ya está en la lista de esta distribuidora" y la lista no cambia

### Requirement: Pedidos de compra

The system SHALL ofrecer `/compras` con el listado paginado de pedidos (fecha, distribuidora, estado, total estimado) filtrable por estado y distribuidora, y el alta de pedido para ambos roles eligiendo distribuidora y agregando productos con cantidad (los costos los fija el servidor; la UI puede sugerir los productos de la lista de esa distribuidora y los bajo mínimo). El detalle SHALL mostrar líneas con costo unitario y subtotal. Ambos roles SHALL poder "Recibir pedido" (`pendiente` → `recibido`) con confirmación que explica que suma todo el stock y actualiza costos; solo la dueña SHALL poder "Cancelar pedido". Tras recibir SHALL refrescar stock, alertas y catálogo. Un `409` por estado no pendiente SHALL informarse y recargar el pedido.

#### Scenario: Recibir un pedido

- **WHEN** un `mostrador` recibe un pedido pendiente de 10 unidades de un producto con stock 4
- **THEN** el pedido queda "Recibido", se informa "Pedido recibido, stock actualizado" y el producto muestra stock 14

#### Scenario: Pedido ya recibido

- **WHEN** se intenta recibir un pedido que otra persona ya recibió y el servidor responde `409`
- **THEN** se informa "El pedido ya no está pendiente" y se muestra su estado actual

### Requirement: Pagos y cuenta con distribuidoras

The system SHALL ofrecer solo a la dueña, dentro de compras, el registro de pagos a distribuidoras (distribuidora, monto > 0, medio `efectivo`/`transferencia`/`cheque`/`otro`, fecha por defecto hoy, nota), su listado filtrable por distribuidora, la anulación de un pago con confirmación, y la cuenta por distribuidora con total recibido, total pagado y saldo (positivo = deuda), resaltando el saldo deudor.

#### Scenario: Registrar pago y ver saldo

- **WHEN** la dueña registra un pago de 50000 a una distribuidora con total recibido 120000 y sin pagos previos
- **THEN** la cuenta muestra pagado "$ 50.000,00" y saldo "$ 70.000,00" como deuda

### Requirement: Reportes

The system SHALL ofrecer `/reportes` con secciones: **Ventas del día** (fecha elegible, por defecto hoy: cantidad de ventas, total vendido, ticket promedio, unidades, totales por medio de pago y anuladas; el mostrador ve solo sus ventas y la pantalla lo aclara), **Reposición** (productos bajo mínimo o con poca cobertura, con stock, mínimo, venta diaria y días de cobertura, y acceso a crear un pedido), **Más vendidos** (período y orden por unidades o monto) y **Márgenes** (período, totales y tabla paginada por producto con ingresos, costo, margen bruto y margen %, más las líneas sin costo informadas aparte). Más vendidos y Márgenes SHALL estar disponibles solo para la dueña. Los reportes SHALL presentarse con tarjetas de indicadores y tablas. El medio `mp` de ventas del día SHALL mostrarse solo si su monto es mayor a 0.

#### Scenario: Ventas del día para la dueña

- **WHEN** la dueña abre Ventas del día con dos ventas confirmadas hoy por 3800 y 1500
- **THEN** ve 2 ventas, total "$ 5.300,00", ticket promedio "$ 2.650,00" y el desglose por medio

#### Scenario: Mostrador ve su alcance

- **WHEN** un `mostrador` abre Ventas del día
- **THEN** la pantalla indica "Tus ventas de hoy" y no ofrece las secciones Más vendidos ni Márgenes

#### Scenario: Reporte sin datos

- **WHEN** se elige una fecha sin ventas
- **THEN** los indicadores muestran 0 y la pantalla dice "No hubo ventas este día"
