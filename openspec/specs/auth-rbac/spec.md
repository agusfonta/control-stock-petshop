# auth-rbac

## Purpose

Proveer autenticación JWT con refresh rotativo y autorización por roles dueña/mostrador, de modo que solo usuarios creados por la dueña operen la API y cada endpoint sensible exija el rol correspondiente.

## Requirements

### Requirement: Login emite access corto + refresh

The system SHALL exponer `POST /api/auth/login` que, ante email + password válidos de un usuario `activo`, responde `200` con un JWT access de corta duración y un refresh token de larga duración, sin exponer jamás el hash ni distinguir si falló el email o el password.

#### Scenario: Login exitoso devuelve ambos tokens

- **WHEN** un usuario activo envía credenciales correctas a `POST /api/auth/login`
- **THEN** el sistema responde `200` con `access_token` (tipo bearer) y entrega el refresh en cookie HttpOnly

#### Scenario: Credenciales inválidas no distinguen causa

- **WHEN** se envía email inexistente o password incorrecto a `POST /api/auth/login`
- **THEN** el sistema responde `401` con mensaje genérico y no emite ningún token

#### Scenario: Usuario desactivado no puede loguearse

- **WHEN** un usuario con `activo == false` envía credenciales correctas a `POST /api/auth/login`
- **THEN** el sistema responde `401` (o `403`) y no emite ningún token

### Requirement: Rate limiting de login por IP+email

The system SHALL limitar `POST /api/auth/login` a 5 intentos fallidos por ventana de 60 segundos por par IP+email, respondiendo `429` al excederse, con contadores en Redis.

#### Scenario: Sexto intento fallido bloqueado

- **WHEN** una misma IP+email falla 5 logins dentro de 60 segundos
- **THEN** el sexto intento recibe `429` aunque las credenciales fueran correctas, hasta que expire la ventana

#### Scenario: Login exitoso resetea el contador

- **WHEN** un login exitoso ocurre antes de agotar la ventana
- **THEN** el sistema resetea el contador de fallos para ese par IP+email

### Requirement: Refresh rotativo con revocación en Redis

The system SHALL exponer `POST /api/auth/refresh` que acepta el refresh vigente (cookie HttpOnly), lo rota emitiendo un par nuevo e invalida el anterior en Redis, de modo que la reutilización de un refresh ya rotado revoca la cadena y se rechaza.

#### Scenario: Refresh válido rota el par

- **WHEN** se presenta un refresh vigente a `POST /api/auth/refresh`
- **THEN** el sistema responde `200` con un access nuevo y un refresh nuevo, y el refresh anterior queda invalidado

#### Scenario: Reúso de refresh rotado es rechazado

- **WHEN** se reintenta usar un refresh ya rotado en `POST /api/auth/refresh`
- **THEN** el sistema responde `401` y no emite tokens nuevos

#### Scenario: Refresh expirado o revocado es rechazado

- **WHEN** se presenta un refresh expirado o explícitamente revocado a `POST /api/auth/refresh`
- **THEN** el sistema responde `401` sin emitir tokens

### Requirement: Refresh viaja en cookie HttpOnly

The system SHALL entregar el refresh exclusivamente en cookie `HttpOnly` con flags `Secure` (salvo localhost/dev documentado) y `SameSite=lax`, y SHALL aceptar el refresh desde esa cookie sin exigirlo en el body JSON.

#### Scenario: Login setea cookie segura

- **WHEN** un login es exitoso
- **THEN** la respuesta incluye `Set-Cookie` con el refresh marcado `HttpOnly`, `SameSite=Lax` (y `Secure` fuera de localhost)

### Requirement: Sesión actual expone identidad y rol

The system SHALL exponer `GET /api/auth/me` que, con access vigente, responde `200` con `id`, `email`, `rol` y `activo` del usuario actual.

#### Scenario: Me con token vigente

- **WHEN** un cliente autenticado llama a `GET /api/auth/me` con access vigente
- **THEN** el sistema responde `200` con su `id`, `email`, `rol` y `activo`

#### Scenario: Me sin token es rechazado

- **WHEN** se llama a `GET /api/auth/me` sin token o con token expirado/manipulado
- **THEN** el sistema responde `401` sin exponer datos de usuario

### Requirement: Usuarios solo creados por dueña, sin registro público

The system SHALL exponer `POST /api/usuarios` que exige rol `duena` y crea usuarios con password hasheado con bcrypt; no existe ningún endpoint de registro público y el password nunca se devuelve ni se persiste en claro.

#### Scenario: Dueña crea usuario mostrador

- **WHEN** una dueña autenticada envía email + password + rol `mostrador` a `POST /api/usuarios`
- **THEN** el sistema responde `201` con el usuario creado (sin password) y el login posterior con ese password funciona

#### Scenario: Mostrador no puede crear usuarios

- **WHEN** un usuario `mostrador` autenticado llama a `POST /api/usuarios`
- **THEN** el sistema responde `403` y no crea ningún usuario

#### Scenario: Sin registro público

- **WHEN** un cliente anónimo intenta crear un usuario por cualquier ruta
- **THEN** el sistema responde `401` (o `403`) y no existe ruta pública que cree usuarios

### Requirement: RBAC dueña/mostrador en endpoints sensibles

The system SHALL proteger todo endpoint sensible con guard de rol: solo `duena` puede anular ventas, editar márgenes/mínimos y gestionar usuarios/configuración; `mostrador` solo accede a ver/buscar catálogo, crear y ver sus ventas, registrar entradas, ver/crear pedidos y ver/crear clientes según la matriz RBAC.

#### Scenario: Mostrador bloqueado en acción de dueña

- **WHEN** un usuario `mostrador` autenticado invoca una acción reservada a dueña (crear usuario, anular venta, editar margen)
- **THEN** el sistema responde `403` y el estado no cambia

#### Scenario: Anónimo bloqueado en endpoint protegido

- **WHEN** un cliente sin token invoca cualquier endpoint protegido
- **THEN** el sistema responde `401` sin ejecutar la acción

#### Scenario: Token expirado es rechazado

- **WHEN** se presenta un access expirado en cualquier endpoint protegido
- **THEN** el sistema responde `401` y no ejecuta la acción

### Requirement: Validación estricta y secretos solo por env

The system SHALL validar todo input/output de auth con schemas Pydantic estrictos (payloads malformados → `422` sin ejecutar lógica) y SHALL tomar `SECRET_KEY` y TTLs de variables de entorno, negándose a arrancar con el valor demo en entornos no-dev y sin hardcodear credenciales reales en repo ni tests (fixtures con passwords `test-only`).

#### Scenario: Payload de login malformado rechazado

- **WHEN** se envía a `POST /api/auth/login` un body sin email válido o sin password
- **THEN** el sistema responde `422` y no toca Redis ni emite tokens

#### Scenario: Sin credenciales reales en el repo

- **WHEN** se inspeccionan código, tests y docs del change
- **THEN** no existe password ni `SECRET_KEY` real hardcodeado y toda credencial de prueba usa fixtures `test-only`
