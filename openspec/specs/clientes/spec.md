# Clientes Specification

## Purpose

Permitir registrar, editar, dar de baja, listar y buscar clientes de mostrador con RBAC dueña/mostrador, para poder asociarlos a una venta y llevar un historial básico (US-007). El historial de ventas por cliente se incorpora con C-10.

## Requirements

### Requirement: Alta de clientes por dueña o mostrador

The system SHALL exponer `POST /api/clientes` con schema estricto: `nombre` obligatorio; `telefono`, `email`, `direccion` y `mascota` opcionales. `mascota`, si se envía, es un objeto estricto `{nombre, tipo}` con las mismas reglas que una mascota creada por separado (nombre de 1 a 100 caracteres recortado, tipo `perro`, `gato` u `otro`); `mascota: null` equivale a no enviarla. Cuando viene `mascota`, el cliente y la mascota SHALL crearse en una única transacción: si falla cualquiera de los dos no se crea ninguno. Tanto `duena` como `mostrador` pueden crear clientes (matriz RBAC "ver + crear"); un anónimo recibe `401`. Un alta con solo `nombre` SHALL ser válida, para permitir el alta inline desde la venta. El cliente creado queda `activo=true`.

#### Scenario: Dueña crea cliente completo

- **WHEN** una dueña envía `{"nombre": "Ana Pérez", "telefono": "11 5555-1234", "email": "Ana@Mail.com", "direccion": "Calle 1"}` a `POST /api/clientes`
- **THEN** el sistema responde `201` con el cliente creado, `activo=true`, timestamps, `telefono` = `"1155551234"` y `email` = `"ana@mail.com"`

#### Scenario: Mostrador crea cliente con solo nombre

- **WHEN** un usuario `mostrador` envía `{"nombre": "Juan"}` a `POST /api/clientes`
- **THEN** el sistema responde `201` con el cliente creado y `telefono`, `email` y `direccion` en `null`

#### Scenario: Alta con mascota

- **WHEN** se envía `{"nombre": "Ana", "mascota": {"nombre": "Firulais", "tipo": "perro"}}` a `POST /api/clientes`
- **THEN** responde `201` y `GET /api/clientes/{id}/mascotas` del cliente nuevo devuelve la mascota "Firulais" de tipo `perro`

#### Scenario: Alta con mascota inválida no crea nada

- **WHEN** se envía `{"nombre": "Ana", "mascota": {"nombre": "Rex", "tipo": "dragón"}}`
- **THEN** responde `422` y no se crea ni el cliente ni la mascota

#### Scenario: Falla al crear la mascota revierte el cliente

- **WHEN** ocurre un error al guardar la mascota durante un alta con mascota
- **THEN** no queda ningún cliente nuevo registrado

#### Scenario: Alta sin autenticación

- **WHEN** un cliente anónimo envía un payload válido a `POST /api/clientes`
- **THEN** el sistema responde `401` y no crea el registro

### Requirement: Validación y normalización de datos de cliente

The system SHALL validar y normalizar los datos de cliente en alta y edición: `nombre` se recorta y no puede quedar vacío; `email`, si viene, se recorta, se pasa a minúsculas y debe tener formato de email; `telefono`, si viene, se normaliza quitando espacios, guiones, puntos y paréntesis, conservando un `+` inicial, y debe quedar con entre 6 y 20 dígitos; un string opcional en blanco se guarda como `null`. Campos desconocidos se rechazan con `422`. Una entrada inválida responde `422` sin persistir nada.

#### Scenario: Nombre vacío o en blanco

- **WHEN** se envía `{}` o `{"nombre": "   "}` a `POST /api/clientes`
- **THEN** el sistema responde `422` y no crea el registro

#### Scenario: Email con formato inválido

- **WHEN** se envía `{"nombre": "Ana", "email": "no-es-email"}` a `POST /api/clientes`
- **THEN** el sistema responde `422`

#### Scenario: Teléfono inválido

- **WHEN** se envía `{"nombre": "Ana", "telefono": "abc"}` o un teléfono con menos de 6 dígitos a `POST /api/clientes`
- **THEN** el sistema responde `422`

#### Scenario: Teléfono con prefijo internacional

- **WHEN** se envía `{"nombre": "Ana", "telefono": "+54 (11) 5555.1234"}` a `POST /api/clientes`
- **THEN** el sistema responde `201` con `telefono` = `"+541155551234"`

#### Scenario: Opcional en blanco se guarda como nulo

- **WHEN** se envía `{"nombre": "Ana", "email": "", "direccion": "  "}` a `POST /api/clientes`
- **THEN** el sistema responde `201` con `email` y `direccion` en `null`

### Requirement: Email único entre clientes activos

The system SHALL impedir que dos clientes activos compartan el mismo email (comparado sin distinguir mayúsculas). Un alta o edición que repita el email de otro cliente activo responde `409` sin cambios. Teléfono y nombre no son únicos. El email de un cliente dado de baja puede reutilizarse.

#### Scenario: Alta con email duplicado

- **WHEN** existe un cliente activo con email `ana@mail.com` y se envía `{"nombre": "Otra", "email": "ANA@mail.com"}` a `POST /api/clientes`
- **THEN** el sistema responde `409` y no crea el registro

#### Scenario: Teléfono repetido es válido

- **WHEN** existe un cliente activo con teléfono `1155551234` y se crea otro cliente con el mismo teléfono
- **THEN** el sistema responde `201`

#### Scenario: Email de cliente dado de baja puede reutilizarse

- **WHEN** el único cliente con email `ana@mail.com` fue dado de baja y se crea un cliente nuevo con ese email
- **THEN** el sistema responde `201`

#### Scenario: Edición con email de otro cliente activo

- **WHEN** una dueña envía `{"email": "ana@mail.com"}` a `PUT /api/clientes/{id}` y ese email pertenece a otro cliente activo
- **THEN** el sistema responde `409` y el cliente no cambia

### Requirement: Saldo de cuenta corriente reservado

The system SHALL tratar `saldo_cc` como reservado en v1 (sin cuenta corriente de clientes): no se acepta en el input de alta ni de edición, y no se expone en ninguna respuesta de la API de clientes. Su valor persistido permanece en 0.

#### Scenario: Intento de fijar saldo en el alta

- **WHEN** se envía `{"nombre": "Ana", "saldo_cc": 500}` a `POST /api/clientes`
- **THEN** el sistema responde `422` y no crea el registro

#### Scenario: Intento de fijar saldo en la edición

- **WHEN** una dueña envía `{"saldo_cc": 500}` a `PUT /api/clientes/{id}`
- **THEN** el sistema responde `422` y el saldo persistido sigue en 0

#### Scenario: Respuesta sin saldo

- **WHEN** un usuario autenticado obtiene un cliente por `GET /api/clientes/{id}`
- **THEN** la respuesta no contiene el campo `saldo_cc`

### Requirement: Consulta de clientes

The system SHALL permitir a cualquier usuario autenticado activo listar clientes con `GET /api/clientes` (solo activos, ordenados por nombre, con metadata de paginación) y obtener uno con `GET /api/clientes/{id}` (incluye clientes dados de baja, con su `activo`). Cada cliente del listado SHALL incluir `mascotas`: la lista de sus mascotas activas (`id`, `nombre`, `tipo`) en orden de creación, vacía si no tiene, obtenida sin consultar cliente por cliente. El detalle por id y las respuestas de alta y edición no incluyen `mascotas`. Un id inexistente responde `404`; un anónimo, `401`.

#### Scenario: Listar clientes activos paginados

- **WHEN** un usuario `mostrador` llama a `GET /api/clientes?page=1&page_size=2` existiendo tres clientes activos y uno dado de baja
- **THEN** el sistema responde `200` con dos clientes ordenados por nombre, `total=3` y `total_pages=2`

#### Scenario: El listado incluye las mascotas activas

- **WHEN** existe un cliente con las mascotas "MIMI" (activa) y "Rex" (dada de baja) y otro sin mascotas, y se llama a `GET /api/clientes`
- **THEN** el primero trae `mascotas` con solo "MIMI" y el segundo trae `mascotas` vacía

#### Scenario: Obtener cliente por id

- **WHEN** un usuario autenticado llama a `GET /api/clientes/{id}` de un cliente existente
- **THEN** el sistema responde `200` con sus datos

#### Scenario: Obtener cliente inexistente

- **WHEN** un usuario autenticado llama a `GET /api/clientes/{id-inexistente}`
- **THEN** el sistema responde `404`

#### Scenario: Listar sin autenticación

- **WHEN** un cliente anónimo llama a `GET /api/clientes`
- **THEN** el sistema responde `401`

### Requirement: Edición y baja de clientes solo por dueña

The system SHALL permitir editar (`PUT /api/clientes/{id}`, actualización parcial) y dar de baja (`DELETE /api/clientes/{id}`) solo a `duena`. La baja es soft-delete (`activo=False`), nunca borrado físico, y responde `204`. Un `mostrador` recibe `403` y nada cambia; un id inexistente responde `404`. En la edición, `nombre` no puede quedar nulo ni vacío. La edición acepta además `mascotas`, una lista opcional de `{id?, nombre, tipo}` (mismas reglas de nombre y tipo que una mascota normal, máximo 20 elementos, sin `id` repetidos) que representa **las mascotas activas que debe tener el cliente**: las que traen `id` de una mascota activa del cliente se actualizan, las que no traen `id` se crean y las mascotas activas que no aparecen en la lista se dan de baja (baja lógica). Si `mascotas` no viene, las mascotas no se tocan; `mascotas: null` responde `422`; `mascotas: []` da de baja todas las activas. Los datos del cliente y las mascotas se guardan en una única transacción: si algo falla no se aplica nada. Un `id` de mascota inexistente, dado de baja o de otro cliente responde `404`; enviar `mascotas` para un cliente dado de baja responde `409`. Editar solo los datos de un cliente (sin `mascotas`) sigue funcionando como hasta ahora.

#### Scenario: Dueña edita teléfono

- **WHEN** una dueña envía `{"telefono": "11-4444-0000"}` a `PUT /api/clientes/{id}`
- **THEN** el sistema responde `200` con `telefono` = `"1144440000"` y el resto de los campos sin cambios

#### Scenario: Edición con nombre nulo

- **WHEN** una dueña envía `{"nombre": null}` a `PUT /api/clientes/{id}`
- **THEN** el sistema responde `422` y el cliente no cambia

#### Scenario: Mostrador intenta editar

- **WHEN** un usuario `mostrador` envía un payload válido a `PUT /api/clientes/{id}`
- **THEN** el sistema responde `403` y el cliente no cambia

#### Scenario: Dueña da de baja un cliente

- **WHEN** una dueña envía `DELETE /api/clientes/{id}`
- **THEN** el sistema responde `204` y el cliente queda con `activo=False` sin borrarse físicamente

#### Scenario: Mostrador intenta dar de baja

- **WHEN** un usuario `mostrador` envía `DELETE /api/clientes/{id}`
- **THEN** el sistema responde `403` y el cliente sigue activo

#### Scenario: Baja de cliente inexistente

- **WHEN** una dueña envía `DELETE /api/clientes/{id-inexistente}`
- **THEN** el sistema responde `404`

#### Scenario: Edición sin mascotas no las toca

- **WHEN** una dueña envía `{"telefono": "11-4444-0000"}` a un cliente con la mascota "MIMI"
- **THEN** el cliente se actualiza y "MIMI" sigue activa

#### Scenario: Edición de mascotas en el mismo guardado

- **WHEN** una dueña envía `{"nombre": "Ana", "mascotas": [{"id": "<id de MIMI>", "nombre": "Mimi", "tipo": "gato"}, {"nombre": "Toby", "tipo": "perro"}]}` a un cliente que tenía las mascotas "MIMI" y "Rex"
- **THEN** responde `200`, "MIMI" queda renombrada a "Mimi", se crea "Toby" y "Rex" queda dada de baja

#### Scenario: Lista vacía da de baja todas

- **WHEN** una dueña envía `{"mascotas": []}` a un cliente con dos mascotas activas
- **THEN** responde `200` y el cliente queda sin mascotas activas

#### Scenario: Error al guardar mascotas revierte todo

- **WHEN** el payload incluye cambios del cliente y una mascota con un `id` de otra persona
- **THEN** responde `404` y ni los datos del cliente ni ninguna mascota cambian

#### Scenario: Mascotas inválidas

- **WHEN** se envía `"mascotas": null`, un `tipo` fuera de perro/gato/otro, `id` repetidos o más de 20 mascotas
- **THEN** responde `422` y no se modifica nada

#### Scenario: Cliente dado de baja

- **WHEN** se envía `mascotas` a `PUT /api/clientes/{id}` de un cliente dado de baja
- **THEN** responde `409` y no se modifica nada

### Requirement: Búsqueda de clientes

The system SHALL exponer `GET /api/clientes/buscar?q=` para cualquier usuario autenticado activo. Devuelve clientes activos cuyo nombre o email contiene `q` sin distinguir mayúsculas ni acentos, o cuyo teléfono contiene los dígitos de `q` (solo cuando `q` tiene dígitos), ordenados por nombre y paginados como el listado, y con sus `mascotas` activas igual que el listado. `q` ausente o en blanco responde `422`. La ruta `/buscar` nunca se interpreta como un id de cliente.

#### Scenario: Búsqueda por nombre sin acentos ni mayúsculas

- **WHEN** existe el cliente activo "José Núñez" y un usuario autenticado llama a `GET /api/clientes/buscar?q=jose nun`
- **THEN** el sistema responde `200` incluyendo a "José Núñez"

#### Scenario: Búsqueda por fragmento de teléfono con separadores

- **WHEN** existe un cliente activo con teléfono `1155551234` y se busca `q=5555-12`
- **THEN** el sistema responde `200` incluyendo a ese cliente

#### Scenario: Búsqueda por email

- **WHEN** existe un cliente activo con email `ana@mail.com` y se busca `q=ANA@`
- **THEN** el sistema responde `200` incluyendo a ese cliente

#### Scenario: La búsqueda incluye las mascotas

- **WHEN** el cliente "Ana" tiene la mascota "MIMI" y se busca `q=ana`
- **THEN** el resultado de "Ana" trae `mascotas` con "MIMI"

#### Scenario: Búsqueda de texto no matchea por teléfono

- **WHEN** se busca `q=zzz` y ningún nombre ni email contiene "zzz"
- **THEN** el sistema responde `200` con lista vacía aunque existan clientes con teléfono

#### Scenario: Clientes dados de baja excluidos

- **WHEN** el único cliente que coincide con `q` está dado de baja
- **THEN** el sistema responde `200` con lista vacía

#### Scenario: Búsqueda sin q o en blanco

- **WHEN** un usuario autenticado llama a `GET /api/clientes/buscar` sin `q` o con `q` en blanco
- **THEN** el sistema responde `422`

#### Scenario: Búsqueda sin autenticación

- **WHEN** un cliente anónimo llama a `GET /api/clientes/buscar?q=ana`
- **THEN** el sistema responde `401`

### Requirement: Historial de ventas por cliente

The system SHALL exponer `GET /api/clientes/{id}/ventas`, para los roles `duena` y `mostrador`, que devuelve las ventas `confirmada` y `anulada` asociadas a ese cliente (nunca borradores), cada una con su `id`, `estado`, `total`, vendedor, fecha de creación y de confirmación, ordenadas por fecha de creación descendente y paginadas como el resto de los listados (metadata `total`, `page`, `page_size`, `total_pages`). Un `mostrador` SHALL ver solo las ventas de ese cliente que él mismo registró; la dueña ve todas. Un cliente inexistente responde `404`; un cliente dado de baja conserva su historial (`200`). Un anónimo recibe `401`.

#### Scenario: Historial con ventas confirmadas y anuladas

- **WHEN** un cliente tiene una venta confirmada, una venta anulada y un borrador, y una dueña llama a `GET /api/clientes/{id}/ventas`
- **THEN** el sistema responde `200` con las dos ventas confirmada y anulada, la más reciente primero, sin el borrador, con `total=2`

#### Scenario: Cliente sin ventas

- **WHEN** un usuario autenticado consulta el historial de un cliente sin ventas
- **THEN** el sistema responde `200` con lista vacía y `total=0`

#### Scenario: Mostrador ve solo sus ventas del cliente

- **WHEN** un cliente tiene una venta confirmada registrada por la dueña y otra registrada por un usuario `mostrador`, y ese mostrador consulta su historial
- **THEN** el sistema responde `200` solo con la venta registrada por ese mostrador

#### Scenario: Historial de cliente dado de baja

- **WHEN** una dueña consulta el historial de un cliente dado de baja que tiene ventas confirmadas
- **THEN** el sistema responde `200` con esas ventas

#### Scenario: Historial de cliente inexistente

- **WHEN** un usuario autenticado llama a `GET /api/clientes/{id-inexistente}/ventas`
- **THEN** el sistema responde `404`

#### Scenario: Historial sin autenticación

- **WHEN** un cliente anónimo llama a `GET /api/clientes/{id}/ventas`
- **THEN** el sistema responde `401`

### Requirement: Mascotas de un cliente

The system SHALL permitir registrar varias mascotas por cliente con schemas estrictos (`extra=forbid`): `nombre` obligatorio (se normaliza recortando espacios; entre 1 y 100 caracteres) y `tipo` obligatorio con valores `perro`, `gato` u `otro`. Endpoints: `POST /api/clientes/{id}/mascotas` (`duena` y `mostrador`, `201`), `GET /api/clientes/{id}/mascotas` (autenticado; solo mascotas activas, orden de creación), `PUT /api/clientes/{id}/mascotas/{mascota_id}` y `DELETE /api/clientes/{id}/mascotas/{mascota_id}` (solo `duena`; la baja es lógica y responde `204`). Un cliente inexistente o una mascota que no pertenece a ese cliente responde `404`; un anónimo recibe `401`; un `mostrador` en editar/baja recibe `403`; un `tipo` fuera de los valores permitidos o un nombre vacío responde `422`. Crear o editar una mascota de un cliente dado de baja responde `409` y no modifica nada; listar sus mascotas sigue permitido. Las mascotas dadas de baja NO SHALL aparecer en el listado.

#### Scenario: Alta de mascota

- **WHEN** un `mostrador` hace `POST /api/clientes/{id}/mascotas` con `{"nombre": "Firulais", "tipo": "perro"}`
- **THEN** responde `201` con la mascota (id, nombre, tipo, activo) y aparece en `GET /api/clientes/{id}/mascotas`

#### Scenario: Varias mascotas por cliente

- **WHEN** se crean dos mascotas para el mismo cliente
- **THEN** el listado devuelve ambas, en orden de creación

#### Scenario: Tipo inválido

- **WHEN** se envía `{"nombre": "Rex", "tipo": "dragón"}`
- **THEN** responde `422` y no se crea la mascota

#### Scenario: Mascota de otro cliente

- **WHEN** se hace `PUT /api/clientes/{A}/mascotas/{id}` con una mascota que pertenece al cliente B
- **THEN** responde `404`

#### Scenario: Baja lógica solo dueña

- **WHEN** la dueña hace `DELETE` de una mascota
- **THEN** responde `204` y la mascota deja de listarse; un `mostrador` recibe `403`

#### Scenario: Cliente dado de baja

- **WHEN** se hace `POST /api/clientes/{id}/mascotas` de un cliente dado de baja
- **THEN** responde `409` y no se crea la mascota
