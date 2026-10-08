# frontend-shell Specification

## Purpose
Base de la SPA de Animall: sesión con JWT y refresh por cookie, acceso a pantallas según el rol (dueña o mostrador), navegación, estados de carga/vacío/error y feedback consistente, con una interfaz accesible y usable en tablet, PC y teléfono.

## Requirements

### Requirement: Inicio de sesión

The system SHALL ofrecer una pantalla `/login` con email y contraseña que autentica contra `POST /api/auth/login`. Ante credenciales válidas SHALL guardar el access token solo en memoria (nunca en `localStorage`/`sessionStorage`), obtener la identidad con `GET /api/auth/me` y navegar a la pantalla pedida originalmente o, si no había, a `/pos`. Ante `401` SHALL mostrar un mensaje genérico sin indicar si falló el email o la contraseña; ante `429` SHALL indicar que se reintente más tarde; ante `422` SHALL marcar los campos inválidos; ante error de red o `503` SHALL indicar que el servidor no está disponible. Mientras la solicitud está en curso el botón SHALL quedar deshabilitado con indicador de carga.

#### Scenario: Login exitoso lleva a la pantalla pedida

- **WHEN** una persona no autenticada abre `/stock`, es redirigida a `/login`, e ingresa credenciales válidas
- **THEN** la app navega a `/stock` y muestra su email y rol en la navegación

#### Scenario: Credenciales inválidas

- **WHEN** se envían credenciales que el servidor rechaza con `401`
- **THEN** la pantalla muestra "Email o contraseña incorrectos" y permanece en `/login` sin guardar ningún token

#### Scenario: Demasiados intentos

- **WHEN** el servidor responde `429` al login
- **THEN** la pantalla indica que hubo demasiados intentos y que se reintente en unos minutos

### Requirement: Sesión persistente con refresh rotativo

The system SHALL restaurar la sesión al recargar la página llamando a `POST /api/auth/refresh` (la cookie HttpOnly viaja sola) y luego a `GET /api/auth/me`, mostrando un indicador de carga a pantalla completa mientras tanto, siempre que la persona no haya cerrado sesión explícitamente en ese navegador. Cuando cualquier solicitud autenticada reciba `401`, la app SHALL intentar un único refresh (compartido entre solicitudes concurrentes) y reintentar la solicitud original una sola vez; si el refresh falla SHALL limpiar la sesión y llevar a `/login` conservando la ruta actual para volver después.

#### Scenario: Recarga con sesión vigente

- **WHEN** una persona autenticada recarga la página dentro de la vigencia del refresh
- **THEN** la app restaura la sesión sin pedir credenciales y muestra la misma pantalla

#### Scenario: Access vencido se renueva de forma transparente

- **WHEN** dos solicitudes simultáneas reciben `401` por access vencido y el refresh es válido
- **THEN** se hace un solo `POST /api/auth/refresh`, ambas solicitudes se reintentan con el nuevo access y la persona no nota la renovación

#### Scenario: Refresh rechazado cierra la sesión

- **WHEN** una solicitud recibe `401` y el refresh también responde `401`
- **THEN** la app limpia la sesión y navega a `/login` con aviso "Tu sesión expiró"

### Requirement: Cierre de sesión

The system SHALL ofrecer "Cerrar sesión" desde la navegación, que borra el access token y los datos cacheados de la sesión y lleva a `/login`. Tras cerrar sesión, recargar la página NO SHALL restaurar la sesión automáticamente: SHALL requerir un nuevo login en ese navegador.

#### Scenario: Cerrar sesión y recargar

- **WHEN** una persona cierra sesión y luego recarga la página
- **THEN** la app muestra `/login` y no restaura la sesión anterior

### Requirement: Acceso a pantallas según rol

The system SHALL exigir sesión para toda ruta distinta de `/login` y SHALL restringir por rol según la matriz RBAC de la API: las rutas exclusivas de dueña (`/reportes/mas-vendidos`, `/reportes/margenes`) muestran a un `mostrador` una pantalla "Sin permiso" con acceso de vuelta al inicio; y dentro de pantallas compartidas, las acciones exclusivas de dueña (crear/editar/dar de baja productos, distribuidoras y listas, editar/dar de baja clientes, ajustar stock, anular ventas, cancelar pedidos, pagos y cuenta de distribuidoras) NO SHALL mostrarse a un `mostrador`. Si aun así el servidor responde `403`, la app SHALL mostrar "No tenés permiso para esta acción" sin cerrar la sesión. La navegación SHALL ocultar las entradas a las que el rol no tiene acceso.

#### Scenario: Mostrador entra a una ruta de dueña

- **WHEN** un `mostrador` navega directamente a `/reportes/margenes`
- **THEN** la app muestra "Sin permiso" y no consulta el endpoint de márgenes

#### Scenario: Mostrador no ve acciones de dueña

- **WHEN** un `mostrador` abre `/productos`
- **THEN** ve el listado y la búsqueda pero no los botones "Nuevo producto", "Editar" ni "Dar de baja", ni las columnas de costo y margen

#### Scenario: Ruta raíz según sesión

- **WHEN** una persona autenticada abre `/`
- **THEN** la app la lleva a `/pos`

### Requirement: Navegación y layout responsive

The system SHALL mostrar un layout con navegación persistente agrupada por áreas (Vender, Ventas, Inventario, Compras, Clientes, Reportes), identidad de Animall, usuario actual con rol y acceso a cerrar sesión. En pantallas de tablet y PC la navegación SHALL estar siempre visible (con opción compacta de solo íconos); en teléfono SHALL abrirse desde un botón de menú. La entrada de Stock SHALL mostrar la cantidad de productos bajo mínimo cuando sea mayor a cero. Ninguna pantalla SHALL generar scroll horizontal de página entre 360 px y 1440 px de ancho (las tablas anchas hacen scroll dentro de su contenedor).

#### Scenario: Badge de alertas de stock

- **WHEN** existen 3 productos con `stock_actual <= stock_minimo`
- **THEN** la entrada Stock de la navegación muestra el indicador "3"

#### Scenario: Navegación en teléfono

- **WHEN** la app se abre con un ancho de 375 px
- **THEN** la navegación está oculta tras un botón de menú y el contenido ocupa todo el ancho sin scroll horizontal

### Requirement: Estados de carga, vacío y error

The system SHALL mostrar en cada pantalla de datos: un esqueleto o indicador mientras carga; un estado vacío con explicación y, si el rol puede, la acción principal (por ejemplo "Crear el primer producto"); y ante error de red o `5xx` un mensaje entendible con botón "Reintentar". Las listas paginadas SHALL mostrar total de resultados y controles de página.

#### Scenario: Error del servidor con reintento

- **WHEN** el listado de clientes responde `500`
- **THEN** la pantalla muestra "No pudimos cargar los clientes" con un botón "Reintentar" que vuelve a consultar

#### Scenario: Lista vacía

- **WHEN** una dueña abre `/distribuidoras` sin distribuidoras cargadas
- **THEN** ve un estado vacío con el botón "Nueva distribuidora"

### Requirement: Feedback de acciones y errores de validación

The system SHALL confirmar con una notificación breve no bloqueante cada acción exitosa que modifica datos y SHALL mostrar los errores de la API en lenguaje claro: los `422` junto al campo correspondiente cuando sea posible, y los `404`/`409` con un mensaje del caso. Las acciones destructivas o irreversibles (anular venta, cancelar pedido, dar de baja, anular pago) SHALL pedir confirmación explícita antes de ejecutarse. Montos de dinero SHALL mostrarse en pesos argentinos con separador de miles y dos decimales.

#### Scenario: Confirmación antes de dar de baja

- **WHEN** una dueña pulsa "Dar de baja" sobre un cliente
- **THEN** la app pide confirmación y solo llama a `DELETE /api/clientes/{id}` si la confirma, mostrando luego "Cliente dado de baja"

#### Scenario: Formato de dinero

- **WHEN** se muestra un total de 24999.5
- **THEN** se ve como "$ 24.999,50"

### Requirement: Accesibilidad e interacción táctil básicas

The system SHALL asociar cada campo de formulario a una etiqueta visible, mantener foco visible y orden de tabulación lógico, cerrar diálogos con Escape devolviendo el foco al disparador, garantizar contraste de texto de al menos 4.5:1 sobre su fondo y ofrecer objetivos táctiles de al menos 44 × 44 px en dispositivos táctiles.

#### Scenario: Diálogo accesible por teclado

- **WHEN** una persona abre el diálogo de alta de cliente con el teclado y presiona Escape
- **THEN** el diálogo se cierra y el foco vuelve al botón que lo abrió
