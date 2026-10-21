# gestion-ui Specification

## Purpose
Pantallas de gestión del negocio sobre la API existente: catálogo de productos, stock y alertas, clientes, distribuidoras con listas de precios, pedidos y pagos de compras, y reportes, respetando la matriz de permisos dueña/mostrador.

## Requirements

### Requirement: Catálogo de productos

The system SHALL ofrecer `/productos` como sección única de productos y stock, con una sola tabla paginada de productos activos (SKU, nombre, marca, categoría, precio de venta, stock actual, stock mínimo y estado de alerta) y búsqueda por SKU o nombre. Para la dueña SHALL mostrar además costo y margen y permitir: crear producto (SKU, nombre, marca, categoría, unidad `unidad`/`bolsa`/`caja`, costo, margen %, stock inicial, stock mínimo, distribuidora por defecto), editarlo (sin modificar el stock, que solo cambia por movimientos), cambiar margen y stock mínimo, darlo de baja con confirmación y ajustar su stock (ver requirement "Stock, alertas y ajustes"). Al cargar costo y margen el formulario SHALL mostrar el precio de venta resultante (`costo × (1 + margen)`) como vista previa; el valor definitivo es el que devuelve el servidor. El margen SHALL ingresarse como porcentaje (35 = 35 %) y enviarse como fracción (0.35). Un SKU repetido (`409`) SHALL marcarse en el campo SKU.

#### Scenario: Vista previa del precio

- **WHEN** la dueña carga costo 18000 y margen 35 en el alta de producto
- **THEN** el formulario muestra precio de venta "$ 24.300,00" antes de guardar

#### Scenario: Edición de margen recalcula el precio

- **WHEN** la dueña cambia el margen de un producto y guarda
- **THEN** el listado muestra el nuevo precio de venta devuelto por el servidor y se informa "Producto actualizado"

#### Scenario: Mostrador consulta el catálogo

- **WHEN** un `mostrador` abre `/productos`
- **THEN** ve precio de venta, stock y estado de alerta pero no costo, margen ni acciones de edición ni de ajuste

#### Scenario: Una sola tabla con producto y stock

- **WHEN** la dueña abre `/productos`
- **THEN** cada fila muestra los datos del producto junto con su stock actual, mínimo y estado, y desde la misma fila puede editar, cambiar margen y mínimo, ajustar stock o dar de baja

### Requirement: Stock, alertas y ajustes

The system SHALL mostrar dentro de `/productos` la consulta de stock de `GET /api/stock` (búsqueda, filtro "solo bajo mínimo", orden por menor cobertura) resaltando los productos con `bajo_minimo`, y un resumen de alertas de `GET /api/stock/alertas` con la cantidad bajo mínimo. Solo la dueña SHALL ver "Ajustar stock" por producto, con un diálogo que pide la diferencia (positiva o negativa, distinta de 0) y un motivo obligatorio, muestra el stock resultante antes de confirmar, impide que quede negativo y, tras `POST /api/productos/{id}/ajustar`, informa el movimiento (stock previo → nuevo) y refresca stock, alertas y catálogo.

#### Scenario: Ajuste con motivo

- **WHEN** la dueña ajusta −2 con motivo "rotura" un producto con stock 10
- **THEN** el diálogo muestra "Quedará en 8", al confirmar se informa "Stock ajustado: 10 → 8" y la fila muestra 8

#### Scenario: Ajuste sin motivo

- **WHEN** la dueña intenta confirmar un ajuste sin motivo
- **THEN** el campo motivo muestra "Indicá el motivo" y no se envía la solicitud

#### Scenario: Filtro bajo mínimo

- **WHEN** se activa "Solo bajo mínimo" en `/productos`
- **THEN** la tabla lista solo productos con `stock_actual <= stock_minimo`

### Requirement: Clientes

The system SHALL ofrecer `/clientes` con el listado paginado de clientes activos, búsqueda por nombre, email o teléfono (hasta 100 caracteres) y alta (nombre obligatorio; teléfono, email, dirección y mascota opcionales) para ambos roles; edición y baja solo para la dueña; y `/clientes/:id` con los datos del cliente y su historial de ventas paginado (`GET /api/clientes/{id}/ventas`) con acceso al detalle de cada venta. La tabla SHALL tener una columna "Mascotas" con las mascotas activas de cada cliente como "Nombre (Tipo)" separadas por coma (por ejemplo "MIMI (Gato), Toby (Perro)") y "—" si no tiene, también en los resultados de búsqueda. El formulario de alta SHALL incluir "Mascota (opcional)" con nombre y tipo (`perro`, `gato`, `otro`): con ambos vacíos no se crea mascota, con uno solo completo el formulario marca el campo faltante y no se envía (el tipo del bloque arranca sin elegir). El formulario "Editar cliente" SHALL mostrar las mascotas del cliente con nombre y tipo editables, un botón para agregar otra y uno para quitar cada una, y "Guardar cambios" SHALL guardar los datos del cliente y las mascotas juntos; una mascota con el nombre vacío SHALL marcar el campo y no enviar. Mientras se cargan las mascotas en la edición se muestra un indicador, y si no se pueden cargar el formulario permite guardar los datos del cliente sin modificar las mascotas y lo informa. Un email repetido (`409`) SHALL marcarse en el campo email, un `409` por cliente dado de baja se informa como tal, y los errores de formato (`422`) se marcan en su campo, en español y sin prefijos técnicos, llevando el foco a ese campo; el teléfono SHALL validarse también en el formulario antes de enviar. Si la página actual de la lista o del historial queda vacía pero existen resultados (por ejemplo tras dar de baja el último cliente de la última página), la app SHALL volver a la última página con datos en vez de mostrar el estado vacío. Si el cliente de `/clientes/:id` no existe SHALL mostrarse "El cliente no existe o el enlace es incorrecto".

#### Scenario: Alta de cliente desde la lista

- **WHEN** un `mostrador` crea un cliente con nombre "Lucía Herrera" y teléfono "351-8901234"
- **THEN** el cliente aparece en la lista y se informa "Cliente creado"

#### Scenario: Alta de cliente con mascota

- **WHEN** un `mostrador` crea un cliente "Ana" completando la mascota "Firulais" de tipo perro
- **THEN** se informa "Cliente creado" y la fila de Ana muestra "Firulais (Perro)" en la columna Mascotas

#### Scenario: Alta de cliente sin mascota

- **WHEN** se crea un cliente dejando vacía la mascota
- **THEN** el cliente se crea sin mascotas, la solicitud no incluye `mascota` y la columna Mascotas muestra "—"

#### Scenario: Mascota a medio completar

- **WHEN** se completa el nombre de la mascota sin elegir el tipo, o se elige el tipo sin nombre
- **THEN** el campo faltante muestra el error y no se envía la solicitud

#### Scenario: Columna Mascotas en la tabla

- **WHEN** la dueña abre `/clientes` y "Agustina" tiene las mascotas "MIMI" (gato) y "Toby" (perro)
- **THEN** su fila muestra "MIMI (Gato), Toby (Perro)" y las filas sin mascotas muestran "—"

#### Scenario: Editar el nombre de una mascota desde Editar cliente

- **WHEN** la dueña abre "Editar cliente" de Agustina, cambia "MIMI" por "Mimi" y guarda
- **THEN** se informa que el cliente se actualizó y la columna Mascotas muestra "Mimi (Gato), Toby (Perro)"

#### Scenario: Agregar y quitar mascotas al editar

- **WHEN** la dueña agrega la mascota "Luna" (otro), quita "Toby" y guarda
- **THEN** la solicitud incluye las mascotas resultantes y la fila muestra "Mimi (Gato), Luna (Otro)"

#### Scenario: Mascota sin nombre al editar

- **WHEN** la dueña deja vacío el nombre de una mascota en "Editar cliente" y guarda
- **THEN** el campo muestra el error y no se envía la solicitud

#### Scenario: No se pudieron cargar las mascotas

- **WHEN** falla la carga de las mascotas al abrir "Editar cliente"
- **THEN** se informa el problema y al guardar solo se envían los datos del cliente, sin `mascotas`

#### Scenario: Teléfono inválido

- **WHEN** se escribe "abc" como teléfono y se guarda
- **THEN** el campo teléfono muestra un mensaje en español sin enviar la solicitud

#### Scenario: Última página vacía tras una baja

- **WHEN** la dueña da de baja al único cliente de la página 2 de la lista
- **THEN** la lista muestra la página 1 con los clientes restantes y no el estado "Todavía no hay clientes"

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

### Requirement: Mascotas en la ficha del cliente

The system SHALL mostrar en `/clientes/:id` una sección "Mascotas" con las mascotas activas del cliente (nombre y tipo con mayúscula inicial, por ejemplo "Perro") obtenidas de `GET /api/clientes/{id}/mascotas`. Mientras carga SHALL mostrar un indicador con etiqueta accesible; si la carga falla SHALL mostrar un estado de error con "Reintentar", también cuando falla una recarga estando ya datos en pantalla. "Agregar mascota" SHALL estar siempre visible para ambos roles (nombre obligatorio y tipo `perro`, `gato` u `otro`); editar y dar de baja (con confirmación) SHALL estar disponibles solo para la dueña, igual que los datos del cliente. Si el cliente está dado de baja, la ficha SHALL ocultar "Editar" y todas las acciones de mascotas y mostrar las mascotas solo de lectura. Los errores de validación (`422`) SHALL marcarse en su campo. Un cliente sin mascotas SHALL mostrar un estado vacío con la acción de agregar. Los cambios hechos en la ficha (agregar, editar o dar de baja una mascota) y los hechos desde "Editar cliente" SHALL verse reflejados en la otra pantalla y en la columna Mascotas de la tabla sin recargar la página.

#### Scenario: Agregar una mascota

- **WHEN** un `mostrador` agrega a un cliente la mascota "Firulais" de tipo perro
- **THEN** la mascota aparece en la sección "Mascotas" del cliente y se informa "Mascota agregada"

#### Scenario: Cliente con varias mascotas

- **WHEN** se abre la ficha de un cliente con las mascotas "Firulais" (perro) y "Mishi" (gato)
- **THEN** ambas se listan con su tipo ("Perro", "Gato")

#### Scenario: Error al cargar las mascotas

- **WHEN** `GET /api/clientes/{id}/mascotas` responde `500`
- **THEN** la sección muestra un mensaje de error con el botón "Reintentar" y, al reintentar con éxito, la lista

#### Scenario: Cliente dado de baja

- **WHEN** se abre la ficha de un cliente dado de baja
- **THEN** no se ven "Editar", "Agregar mascota" ni acciones de mascotas, y las mascotas existentes se listan sin acciones

#### Scenario: Baja de mascota solo para la dueña

- **WHEN** un `mostrador` abre la ficha de un cliente con mascotas
- **THEN** no ve las acciones de editar ni dar de baja

#### Scenario: Nombre vacío

- **WHEN** se intenta guardar una mascota sin nombre
- **THEN** el campo nombre muestra el error y no se envía la solicitud

#### Scenario: Cambio desde la ficha se ve en la tabla

- **WHEN** la dueña agrega una mascota desde la ficha y vuelve a `/clientes`
- **THEN** la columna Mascotas de ese cliente ya la incluye
