## MODIFIED Requirements

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
