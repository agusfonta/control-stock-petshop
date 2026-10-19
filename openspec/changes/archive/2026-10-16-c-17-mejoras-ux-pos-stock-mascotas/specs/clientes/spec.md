## ADDED Requirements

### Requirement: Mascotas de un cliente

The system SHALL permitir registrar varias mascotas por cliente con schemas estrictos (`extra=forbid`): `nombre` obligatorio (se normaliza recortando espacios; entre 1 y 100 caracteres) y `tipo` obligatorio con valores `perro`, `gato` u `otro`. Endpoints: `POST /api/clientes/{id}/mascotas` (`duena` y `mostrador`, `201`), `GET /api/clientes/{id}/mascotas` (autenticado; solo mascotas activas, orden de creación), `PUT /api/clientes/{id}/mascotas/{mascota_id}` y `DELETE /api/clientes/{id}/mascotas/{mascota_id}` (solo `duena`; la baja es lógica y responde `204`). Un cliente inexistente o una mascota que no pertenece a ese cliente responde `404`; un anónimo recibe `401`; un `mostrador` en editar/baja recibe `403`; un `tipo` fuera de los valores permitidos o un nombre vacío responde `422`. Las mascotas dadas de baja NO SHALL aparecer en el listado.

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
