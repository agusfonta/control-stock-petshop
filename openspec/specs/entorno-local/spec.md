# entorno-local Specification

## Purpose
Forma documentada y reproducible de levantar Animall completo en una máquina local (base, API y frontend) con datos de demostración y usuarios de prueba, con Docker o sin él, sin introducir secretos reales ni debilitar la configuración de producción.

## Requirements

### Requirement: Levantar todo con Docker Compose

The system SHALL permitir levantar base de datos, Redis, API y frontend con un único `docker compose up` desde la raíz del repo. Al arrancar, la API SHALL aplicar las migraciones pendientes y ejecutar el seed demo (idempotente) antes de aceptar solicitudes, y el frontend SHALL quedar accesible en `http://localhost:5173` reenviando `/api` a la API. La base del compose SHALL ser independiente de cualquier PostgreSQL instalado en el sistema.

#### Scenario: Primer arranque con Docker

- **WHEN** se ejecuta `docker compose up` en un clon limpio
- **THEN** tras el arranque `http://localhost:5173` muestra el login y se puede ingresar con el usuario dueña de prueba y ver el catálogo demo

#### Scenario: Segundo arranque no duplica datos

- **WHEN** se detiene y se vuelve a ejecutar `docker compose up` conservando el volumen de la base
- **THEN** el seed no duplica productos, usuarios ni ventas

### Requirement: Alternativa sin Docker

The system SHALL permitir correr API y frontend sin Docker usando una base SQLite local y un Redis en memoria, solo cuando `ENV` es `dev` o `test`. Con `REDIS_URL=memory://` la API SHALL usar un almacén en memoria compartido por el proceso (login, refresh y rate limit funcionan mientras el proceso vive); con cualquier otro `ENV` ese valor SHALL rechazarse al arrancar. Con una URL SQLite la API SHALL poder atender solicitudes concurrentes del servidor de desarrollo. Un comando de inicialización SHALL crear el esquema (en SQLite a partir de los modelos; en PostgreSQL aplicando las migraciones) y otro SHALL cargar el seed demo.

#### Scenario: Correr sin Docker

- **WHEN** se configuran `ENV=dev`, `DATABASE_URL=sqlite:///./dev.db` y `REDIS_URL=memory://`, se inicializa la base, se carga el seed y se levantan API y frontend
- **THEN** se puede iniciar sesión en `http://localhost:5173`, vender y ver reportes

#### Scenario: Redis en memoria rechazado en producción

- **WHEN** la API arranca con `ENV=prod` y `REDIS_URL=memory://`
- **THEN** el arranque falla con un mensaje que indica que `memory://` solo se admite en dev/test

### Requirement: Seed de demostración

The system SHALL incluir un seed demo idempotente, ejecutable solo con `ENV` `dev` o `test`, que crea: usuario dueña y usuario mostrador; al menos 15 productos activos de distintas categorías con costo, margen, stock y mínimo (incluyendo algunos bajo mínimo y uno sin stock); al menos 3 distribuidoras con listas de precios que se superponen en algunos productos; al menos 6 clientes; un pedido recibido y uno pendiente; y ventas confirmadas distribuidas en los últimos 7 días (incluida al menos una hoy y una anulada) con pagos en efectivo, transferencia y tarjeta, de modo que todos los reportes muestren datos. Todo cambio de stock del seed SHALL quedar registrado con su movimiento. Las contraseñas de los usuarios SHALL leerse de variables de entorno (sin valores por defecto en el código) y los valores de prueba SHALL figurar solo en archivos de ejemplo de configuración y en el compose de desarrollo.

#### Scenario: Seed con datos para reportes

- **WHEN** se ejecuta el seed demo sobre una base vacía y la dueña abre Reportes
- **THEN** Ventas del día, Más vendidos, Reposición y Márgenes muestran datos no vacíos

#### Scenario: Seed sin contraseña configurada

- **WHEN** se ejecuta el seed demo sin las variables de contraseña definidas
- **THEN** falla con un mensaje que nombra las variables faltantes y no crea usuarios

#### Scenario: Seed bloqueado fuera de desarrollo

- **WHEN** se ejecuta el seed demo con `ENV=prod`
- **THEN** se niega a correr y no modifica la base

### Requirement: CORS para el frontend de desarrollo

The system SHALL permitir configurar por variable de entorno los orígenes admitidos por CORS (por defecto el origen de Vite `http://localhost:5173`), admitiendo credenciales para que la cookie de refresh funcione si el frontend se sirve desde otro origen. Orígenes no listados NO SHALL recibir encabezados CORS de permiso.

#### Scenario: Origen de Vite permitido

- **WHEN** el navegador envía una solicitud preflight desde `http://localhost:5173` a la API
- **THEN** la respuesta incluye `Access-Control-Allow-Origin: http://localhost:5173` y `Access-Control-Allow-Credentials: true`

#### Scenario: Origen desconocido

- **WHEN** llega una solicitud desde `http://evil.example`
- **THEN** la respuesta no incluye `Access-Control-Allow-Origin` para ese origen

### Requirement: Documentación de cómo correr

The system SHALL documentar en el `README.md` raíz una sección "Cómo correr" con: requisitos, arranque con Docker, arranque sin Docker (PowerShell de Windows), usuarios de prueba y dónde se configuran, URLs (frontend, API, documentación OpenAPI), cómo correr los tests de backend y frontend, cómo reiniciar los datos demo y problemas conocidos (incluido que un PostgreSQL del sistema con contraseña desconocida no afecta al compose, que usa su propia base).

#### Scenario: README guía el primer arranque

- **WHEN** una persona sin contexto sigue la sección "Cómo correr" con Docker
- **THEN** llega al login, ingresa con el usuario de prueba documentado y ve el POS
