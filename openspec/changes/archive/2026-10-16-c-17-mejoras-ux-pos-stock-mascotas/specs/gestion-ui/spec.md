## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Mascotas en la ficha del cliente

The system SHALL mostrar en `/clientes/:id` una sección "Mascotas" con las mascotas activas del cliente (nombre y tipo) obtenidas de `GET /api/clientes/{id}/mascotas`. Ambos roles SHALL poder agregar una mascota (nombre obligatorio y tipo `perro`, `gato` u `otro`); editar y dar de baja (con confirmación) SHALL estar disponibles solo para la dueña, igual que los datos del cliente. Los errores de validación (`422`) SHALL marcarse en su campo. Un cliente sin mascotas SHALL mostrar un estado vacío con la acción de agregar.

#### Scenario: Agregar una mascota

- **WHEN** un `mostrador` agrega a un cliente la mascota "Firulais" de tipo perro
- **THEN** la mascota aparece en la sección "Mascotas" del cliente y se informa "Mascota agregada"

#### Scenario: Cliente con varias mascotas

- **WHEN** se abre la ficha de un cliente con las mascotas "Firulais" (perro) y "Mishi" (gato)
- **THEN** ambas se listan con su tipo

#### Scenario: Baja de mascota solo para la dueña

- **WHEN** un `mostrador` abre la ficha de un cliente con mascotas
- **THEN** no ve las acciones de editar ni dar de baja

#### Scenario: Nombre vacío

- **WHEN** se intenta guardar una mascota sin nombre
- **THEN** el campo nombre muestra el error y no se envía la solicitud
