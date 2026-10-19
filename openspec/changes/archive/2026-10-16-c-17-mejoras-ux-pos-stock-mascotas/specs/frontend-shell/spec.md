## MODIFIED Requirements

### Requirement: Navegación y layout responsive

The system SHALL mostrar un layout con navegación persistente agrupada por áreas (Vender, Ventas, Inventario, Compras, Clientes, Reportes), identidad de Animall, usuario actual con rol y acceso a cerrar sesión. En pantallas de tablet y PC la navegación SHALL estar siempre visible (con opción compacta de solo íconos); en teléfono SHALL abrirse desde un botón de menú. El área Inventario SHALL tener una única entrada "Productos y stock" (`/productos`) que SHALL mostrar la cantidad de productos bajo mínimo cuando sea mayor a cero; no SHALL existir una entrada separada de Stock, y la ruta antigua `/stock` SHALL redirigir a `/productos`. Ninguna pantalla SHALL generar scroll horizontal de página entre 360 px y 1440 px de ancho (las tablas anchas hacen scroll dentro de su contenedor).

#### Scenario: Badge de alertas de stock

- **WHEN** existen 3 productos con `stock_actual <= stock_minimo`
- **THEN** la entrada "Productos y stock" de la navegación muestra el indicador "3"

#### Scenario: Ruta antigua de stock

- **WHEN** se abre `/stock`
- **THEN** la app redirige a `/productos` y muestra la sección unificada

#### Scenario: Navegación en teléfono

- **WHEN** la app se abre con un ancho de 375 px
- **THEN** la navegación está oculta tras un botón de menú y el contenido ocupa todo el ancho sin scroll horizontal
