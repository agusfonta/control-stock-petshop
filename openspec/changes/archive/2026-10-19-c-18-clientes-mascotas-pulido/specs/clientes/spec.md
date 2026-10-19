## MODIFIED Requirements

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
