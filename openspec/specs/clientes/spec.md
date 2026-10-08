# Clientes Specification

## Purpose

Permitir registrar, editar, dar de baja, listar y buscar clientes de mostrador con RBAC dueña/mostrador, para poder asociarlos a una venta y llevar un historial básico (US-007). El historial de ventas por cliente se incorpora con C-10.

## Requirements

### Requirement: Alta de clientes por dueña o mostrador

The system SHALL exponer `POST /api/clientes` con schema estricto: `nombre` obligatorio; `telefono`, `email` y `direccion` opcionales. Tanto `duena` como `mostrador` pueden crear clientes (matriz RBAC "ver + crear"); un anónimo recibe `401`. Un alta con solo `nombre` SHALL ser válida, para permitir el alta inline desde la venta. El cliente creado queda `activo=true`.

#### Scenario: Dueña crea cliente completo

- **WHEN** una dueña envía `{"nombre": "Ana Pérez", "telefono": "11 5555-1234", "email": "Ana@Mail.com", "direccion": "Calle 1"}` a `POST /api/clientes`
- **THEN** el sistema responde `201` con el cliente creado, `activo=true`, timestamps, `telefono` = `"1155551234"` y `email` = `"ana@mail.com"`

#### Scenario: Mostrador crea cliente con solo nombre

- **WHEN** un usuario `mostrador` envía `{"nombre": "Juan"}` a `POST /api/clientes`
- **THEN** el sistema responde `201` con el cliente creado y `telefono`, `email` y `direccion` en `null`

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

The system SHALL permitir a cualquier usuario autenticado activo listar clientes con `GET /api/clientes` (solo activos, ordenados por nombre, con metadata de paginación) y obtener uno con `GET /api/clientes/{id}` (incluye clientes dados de baja, con su `activo`). Un id inexistente responde `404`; un anónimo, `401`.

#### Scenario: Listar clientes activos paginados

- **WHEN** un usuario `mostrador` llama a `GET /api/clientes?page=1&page_size=2` existiendo tres clientes activos y uno dado de baja
- **THEN** el sistema responde `200` con dos clientes ordenados por nombre, `total=3` y `total_pages=2`

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

The system SHALL permitir editar (`PUT /api/clientes/{id}`, actualización parcial) y dar de baja (`DELETE /api/clientes/{id}`) solo a `duena`. La baja es soft-delete (`activo=False`), nunca borrado físico, y responde `204`. Un `mostrador` recibe `403` y nada cambia; un id inexistente responde `404`. En la edición, `nombre` no puede quedar nulo ni vacío.

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

### Requirement: Búsqueda de clientes

The system SHALL exponer `GET /api/clientes/buscar?q=` para cualquier usuario autenticado activo. Devuelve clientes activos cuyo nombre o email contiene `q` sin distinguir mayúsculas ni acentos, o cuyo teléfono contiene los dígitos de `q` (solo cuando `q` tiene dígitos), ordenados por nombre y paginados como el listado. `q` ausente o en blanco responde `422`. La ruta `/buscar` nunca se interpreta como un id de cliente.

#### Scenario: Búsqueda por nombre sin acentos ni mayúsculas

- **WHEN** existe el cliente activo "José Núñez" y un usuario autenticado llama a `GET /api/clientes/buscar?q=jose nun`
- **THEN** el sistema responde `200` incluyendo a "José Núñez"

#### Scenario: Búsqueda por fragmento de teléfono con separadores

- **WHEN** existe un cliente activo con teléfono `1155551234` y se busca `q=5555-12`
- **THEN** el sistema responde `200` incluyendo a ese cliente

#### Scenario: Búsqueda por email

- **WHEN** existe un cliente activo con email `ana@mail.com` y se busca `q=ANA@`
- **THEN** el sistema responde `200` incluyendo a ese cliente

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
