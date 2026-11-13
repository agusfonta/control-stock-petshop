# Spec Delta

## Purpose

Permitir publicar una demo de Animall en el plan gratis de Render, a partir de un Blueprint versionado, para que la dueña la pruebe con datos de demostración, sin debilitar la configuración de seguridad ni cargar datos reales.

## ADDED Requirements

### Requirement: Entorno staging validado como entorno real

The system SHALL aceptar como valores de `ENV` únicamente `dev`, `test`, `staging` y `prod`, y SHALL rechazar al arrancar cualquier otro valor. Con `ENV=staging` el sistema SHALL aplicar las mismas validaciones fail-closed que fuera de desarrollo: `SECRET_KEY` real (al menos 32 caracteres y distinta de `changeme`), `REDIS_URL` distinta de `memory://` y `BCRYPT_ROUNDS` mayor o igual a 12. Con `ENV=staging` la cookie de refresh SHALL emitirse con el flag `Secure`.

#### Scenario: Staging con configuración real arranca

- **WHEN** la API arranca con `ENV=staging`, una `SECRET_KEY` de 32 caracteres o más, una `REDIS_URL` real y `BCRYPT_ROUNDS` por defecto
- **THEN** la configuración se acepta

#### Scenario: Staging con secreto demo o corto no arranca

- **WHEN** la API arranca con `ENV=staging` y `SECRET_KEY=changeme` o una clave de menos de 32 caracteres
- **THEN** el arranque falla y la API no atiende solicitudes

#### Scenario: Staging con Redis en memoria no arranca

- **WHEN** la API arranca con `ENV=staging` y `REDIS_URL=memory://`
- **THEN** el arranque falla indicando que hace falta un Redis real

#### Scenario: Valor de ENV desconocido no arranca

- **WHEN** la API arranca con `ENV=produccion` (o cualquier valor fuera de `dev`, `test`, `staging`, `prod`)
- **THEN** el arranque falla nombrando los valores admitidos

#### Scenario: Cookie de refresh segura en staging

- **WHEN** un login es exitoso con `ENV=staging`, aunque la API reciba la solicitud por http detrás del proxy de la plataforma
- **THEN** la cookie de refresh incluye `Secure`, `HttpOnly` y `SameSite=Lax`

### Requirement: Arranque de la imagen desplegable

The system SHALL proveer una imagen de backend de producción (la etapa por defecto del Dockerfile, sin herramientas de desarrollo y con usuario no root) que al arrancar aplique todas las migraciones pendientes antes de aceptar solicitudes, escuche en el puerto indicado por la variable `PORT` (8000 si no está definida) y cargue el seed demo solo cuando una variable de entorno lo pida explícitamente. Si las migraciones o el seed pedido fallan, la API NO SHALL arrancar.

#### Scenario: Migraciones antes de atender

- **WHEN** la imagen arranca contra una base vacía
- **THEN** el esquema queda en la última migración antes de que `GET /api/health` responda

#### Scenario: Seed demo solo a pedido

- **WHEN** la imagen arranca sin la variable que pide el seed demo
- **THEN** no se crean usuarios ni datos demo

#### Scenario: Seed pedido en producción aborta el arranque

- **WHEN** la imagen arranca con `ENV=prod` y la variable que pide el seed demo activada
- **THEN** el seed se niega a correr, la base no se modifica y la API no arranca

### Requirement: Blueprint de demo en Render

The system SHALL versionar en la raíz del repo un Blueprint de Render (`render.yaml`) que, en plan gratis y en una misma región, defina: el backend como web service Docker con `ENV=staging`, health check en `/api/health` y seed demo activado; una base PostgreSQL; un Key Value (Redis); y el frontend como Static Site construido desde `frontend/`. Las variables `DATABASE_URL` y `REDIS_URL` SHALL tomarse de los recursos del propio Blueprint, `SECRET_KEY` SHALL generarse en la plataforma, y las contraseñas del seed SHALL pedirse a la usuaria al crear el Blueprint. El Blueprint NO SHALL contener ningún secreto literal.

#### Scenario: Recursos esperados en plan gratis

- **WHEN** se lee `render.yaml`
- **THEN** contiene un web service Docker, un Static Site, una base PostgreSQL y un Key Value, todos en plan gratis y en la misma región

#### Scenario: Sin secretos literales

- **WHEN** se revisan las variables de entorno declaradas en `render.yaml`
- **THEN** `SECRET_KEY` se genera en la plataforma, `SEED_OWNER_PASSWORD` y `SEED_MOSTRADOR_PASSWORD` se completan a mano, `DATABASE_URL` y `REDIS_URL` vienen de los recursos, y ningún valor literal es una contraseña o clave

### Requirement: Frontend estático con API en el mismo origen

The system SHALL servir el frontend como sitio estático que reenvía (rewrite, no redirect) toda solicitud `/api/*` al backend, de modo que el navegador use un único origen y la cookie de refresh funcione sin cambios de CORS ni de `SameSite`. Las rutas del frontend que no correspondan a un archivo SHALL devolver `index.html` (SPA), y esa regla NO SHALL capturar `/api/*`.

#### Scenario: Recarga en una ruta interna

- **WHEN** la usuaria recarga el navegador en `/stock` en la URL de la demo
- **THEN** recibe la aplicación y no un 404

#### Scenario: Login y refresh en la demo

- **WHEN** la usuaria inicia sesión en la URL del frontend y luego recarga la página
- **THEN** la sesión se mantiene porque el refresh viaja por `/api/auth/refresh` en el mismo origen

### Requirement: Guía de la demo

The system SHALL incluir una guía en español (`docs/demo-render.md`) con: los pasos para crear la demo desde el Blueprint (New → Blueprint, repositorio y rama), qué valores cargar y cuáles genera la plataforma, cómo verificar que funciona y con qué usuarios entrar, los límites del plan gratis (el backend se duerme tras unos 15 minutos sin uso y tarda en despertar, la base gratis vence a los ~30 días, no hay backups), la advertencia explícita de no cargar nunca datos reales, y cómo reiniciar los datos o borrar la demo.

#### Scenario: La usuaria crea la demo siguiendo la guía

- **WHEN** la usuaria, con una cuenta de Render, sigue la guía paso a paso
- **THEN** obtiene una URL pública donde puede entrar como dueña o mostrador con las contraseñas que eligió y ver los datos demo
