## MODIFIED Requirements

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
