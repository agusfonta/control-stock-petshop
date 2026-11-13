# Design

> Governance **ALTO** (config de seguridad + seed). Cada decisión marcada **[REVISAR]** necesita el OK humano antes de `/opsx:apply`.

## Context

Ver `proposal.md` (Why). Estado observado en el código:

- `app/core/config.py`: `env: str` sin default ni conjunto cerrado. Las validaciones fail-closed se aplican a "todo lo que no sea `dev`/`test`": `SECRET_KEY` ≥ 32 y ≠ `changeme`, `REDIS_URL` ≠ `memory://`, `BCRYPT_ROUNDS` ≥ 12. O sea, `ENV=staging` **ya** hoy se valida como entorno real; lo que falta es nombrarlo y cerrar el conjunto.
- `scripts/seed_demo.py`: `ENVS_PERMITIDOS = ("dev", "test")`, contraseñas solo por `SEED_OWNER_PASSWORD`/`SEED_MOSTRADOR_PASSWORD`, idempotente por SKU ancla `RC-MINI-3KG` (si se corta a mitad, hay que reiniciar la base).
- `app/modules/auth/router.py::_secure_cookie`: `Secure` solo si `env == "prod"` o el esquema es `https`. Detrás del proxy de Render uvicorn ve `http` (no usamos `--proxy-headers`), así que con `staging` la cookie saldría **sin** `Secure`. El spec `auth-rbac` ya exige `Secure` fuera de localhost.
- Rate limit de login: clave `ip + email`, 5 fallos / 60 s, IP desde `request.client.host`.
- `backend/Dockerfile`: etapas `deps` → `dev` → `runtime`; `runtime` **ya es la última** (target por defecto) pero no copia `scripts/` y arranca uvicorn fijo en 8000 sin migrar.
- Frontend: `shared/api/client.ts` usa `VITE_API_BASE_URL` o, por defecto, `/api` relativo, con `credentials: "include"`. Cookie de refresh: `SameSite=lax`, `path=/api/auth`.
- Render (docs verificadas 2026-10-21): el Blueprint **no tiene campo de build target** Docker; Free web service se duerme a los 15 min y tarda ~1 min en despertar; **sin shell ni one-off jobs** en Free; Postgres Free vence a los 30 días (+14 de gracia), uno por workspace; Key Value Free solo en memoria (se pierde al reiniciar), uno por workspace; un rewrite de Static Site puede apuntar a una URL pública completa; los rewrites no aplican si existe un archivo en esa ruta; `generateValue: true` = valor aleatorio base64 de 256 bits; `sync: false` = se pide solo al crear el Blueprint.

## Goals / Non-Goals

**Goals:**
- Una demo funcional en Render Free creada con un solo Blueprint y la carga manual de 2 contraseñas.
- Cambios de código mínimos y cubiertos por tests RED-first.
- Ningún secreto en el repo; `seed_demo` sigue imposible en `prod`.

**Non-Goals:**
- Health con chequeo de DB/Redis, `--proxy-headers`, seed de producción, revisión de seguridad completa (C-15a).
- `preDeployCommand`, planes pagos, CI que construya la imagen, `.env.example` de producción (C-15b).
- Backups (C-15c), dominio propio, monitoreo (C-15d).
- Cambios de código en el frontend.

## Decisions

### D1 — `ENV` como conjunto cerrado `dev | test | staging | prod` **[REVISAR]**
`env: Literal["dev", "test", "staging", "prod"]` en `Settings`. Un typo (`ENV=produccion`, `ENV=Prod`) hoy pasa como "entorno real" sin que nadie se entere y, peor, quedaría fuera de cualquier `env == "prod"`; con el conjunto cerrado aborta el arranque nombrando los valores válidos.
- `staging` hereda **todas** las validaciones fail-closed existentes sin tocarlas (ya aplican a `env not in ("dev","test")`). No se agrega ninguna excepción a favor de staging en `config.py`.
- Alternativa descartada: dejar `env: str` y solo sumar `staging` en el seed. Funciona, pero no da test RED genuino en config y deja abierta la clase de error del typo.
- Alternativa descartada: reusar `ENV=prod` + un flag `ALLOW_DEMO_SEED`. Mezcla datos demo con el entorno que custodia datos reales; un flag olvidado en prod cargaría datos falsos. Se prefiere que la frontera sea el valor de `ENV`.
- BREAKING teórico: nadie usa hoy otro valor (revisado repo, compose, CI, README).

### D2 — `seed_demo` admite `staging`, nunca `prod` **[REVISAR]**
`ENVS_PERMITIDOS = ("dev", "test", "staging")`. El mensaje de rechazo nombra los tres. Contraseñas y lógica de idempotencia sin cambios. El test existente `test_aborta_con_env_prod_y_no_modifica_la_base` sigue (ajustando solo la aserción del mensaje si cambia), y se suma uno para `staging`.
- El seed en staging solo corre si se pide (D4); `ENV=staging` solo no carga nada.

### D3 — Cookie de refresh `Secure` en `staging` **[REVISAR]**
`_secure_cookie` → `settings.env in ("prod", "staging") or request.url.scheme == "https"`. Sin esto, en la demo la cookie viajaría sin `Secure` (uvicorn ve `http` detrás del proxy), en contra del spec `auth-rbac`.
- Alternativa descartada: `uvicorn --proxy-headers --forwarded-allow-ips='*'` para que el esquema sea `https`. Con `'*'` uvicorn confía en `X-Forwarded-For` enviado por el cliente → la IP del rate limit se vuelve falsificable. Configurarlo bien (IPs de confianza de Render) es trabajo de C-15a.
- Consecuencia aceptada para la demo: todas las solicitudes llegan con la IP del proxy, así que el rate limit de login es efectivamente por email (5 fallos/60 s bloquean ese email para todos durante un minuto). Con 2 usuarias demo es tolerable; se documenta.

### D4 — Arranque por script: migrar → seed opcional → uvicorn **[REVISAR]**
Nuevo `backend/scripts/start.sh` (POSIX `sh`, `set -eu`):
1. `alembic upgrade head`
2. si `SEED_DEMO_AL_ARRANCAR=true` → `python -m scripts.seed_demo` (si falla, el contenedor no arranca: `set -e`)
3. `exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"`

`runtime` pasa a `COPY ./scripts ./scripts` y `CMD ["sh", "scripts/start.sh"]`.
- Por qué al arrancar y no `preDeployCommand`: en Free no hay shell ni one-off jobs, y no está claro que pre-deploy exista en Free; el arranque funciona en cualquier plan. C-15b puede mover las migraciones a pre-deploy en plan pago.
- Por qué el seed en cada arranque: es idempotente (sale rápido si existe el SKU ancla y no pisa contraseñas) y es la **única** forma de cargarlo en Free sin shell. Costo: un poco más de tiempo al despertar (dos get-or-create de usuario y una consulta del SKU ancla; no re-hashea contraseñas existentes).
- Por qué un flag explícito y no "si ENV=staging": así un staging futuro puede existir sin datos demo, y en `prod` el flag puesto por error **aborta** el arranque (el seed se niega) en vez de ignorarse en silencio — fail-closed visible.
- `PORT`: el Blueprint fija `PORT=8000` (coincide con el `HEALTHCHECK` del Dockerfile y con el default); el script igual respeta `PORT` si Render lo cambia.
- Varias instancias migrando a la vez: no aplica (Free = 1 instancia).

### D5 — El Dockerfile no necesita target **(informativo)**
Render no permite elegir target, pero `runtime` ya es la última etapa (target por defecto). Se agrega un test que lo fija como invariante (última etapa = `runtime`, usuario no root, copia `scripts/`, CMD usa `start.sh`). `docker-compose.yml` sigue usando `target: dev` sin cambios.

### D6 — Ruteo de `/api`: rewrite del Static Site al backend (mismo origen) **[REVISAR]**
`routes` del Static Site, en este orden:
1. `rewrite /api/* → https://<backend>.onrender.com/api/*`
2. `rewrite /* → /index.html`

El navegador habla solo con el origen del frontend: `/api` relativo (sin `VITE_API_BASE_URL`), cookie `SameSite=Lax` de primera parte, sin CORS. Cero cambios de frontend.
- Alternativa descartada: `VITE_API_BASE_URL=https://<backend>.onrender.com/api`. `onrender.com` está en la Public Suffix List → frontend y backend serían **sitios distintos**, la cookie `SameSite=Lax` no viajaría en el `fetch` de refresh y habría que pasar a `SameSite=None` + CORS con credenciales (cambio de auth, governance CRÍTICO). Más invasivo.
- Limitación: la URL de destino es literal (los `routes` no aceptan `fromService`). Se usa el nombre de servicio `animall-demo-api` → `https://animall-demo-api.onrender.com`. Si Render asigna otro subdominio (nombre ocupado), la guía indica corregir la regla en el panel o en `render.yaml`.
- `CORS_ORIGINS`: no lo necesita el flujo (mismo origen), pero `Settings` lo tiene con default `localhost:5173`; se fija a `https://animall-demo.onrender.com` para que no quede un origen de desarrollo en la nube.
- Riesgo a verificar en el primer deploy: que el proxy de rewrite pase `Set-Cookie` y `Authorization` sin tocarlos (las docs no lo detallan). Si no, plan B = la alternativa descartada, como change aparte con revisión de auth.

### D7 — Contenido de `render.yaml` **[REVISAR]**
- Región `virginia` para los tres recursos (la más cercana a Argentina; no se puede cambiar después). Static Site no lleva región.
- `services`:
  - `animall-demo-api`: `type: web`, `runtime: docker`, `plan: free`, `dockerfilePath: ./backend/Dockerfile`, `dockerContext: ./backend`, `healthCheckPath: /api/health`, `autoDeploy: true`. envVars: `ENV=staging`, `PORT=8000`, `SEED_DEMO_AL_ARRANCAR=true`, `CORS_ORIGINS=https://animall-demo.onrender.com`, `DATABASE_URL` ← `fromDatabase: animall-demo-db / connectionString`, `REDIS_URL` ← `fromService: keyvalue animall-demo-kv / connectionString`, `SECRET_KEY` ← `generateValue: true` (base64 de 256 bits ≈ 44 caracteres ≥ 32), `SEED_OWNER_PASSWORD` y `SEED_MOSTRADOR_PASSWORD` ← `sync: false`.
  - `animall-demo-kv`: `type: keyvalue`, `plan: free`, `ipAllowList: []` (solo red interna de Render).
  - `animall-demo`: `type: web`, `runtime: static`, `rootDir: frontend`, `buildCommand: npm ci && npm run build`, `staticPublishPath: ./dist`, env `NODE_VERSION=24` (igual que CI), `routes` de D6.
- `databases`: `animall-demo-db`, `plan: free`, `ipAllowList: []`.
- `DATABASE_URL` de Render es `postgresql://…`: con `psycopg2-binary` instalado SQLAlchemy lo usa sin cambiar el esquema de URL.
- Key Value Free pierde datos al reiniciar: solo se pierden sesiones de refresh y contadores de rate limit → la usuaria vuelve a iniciar sesión. Aceptable.

### D8 — Test del Blueprint con PyYAML
`tests/infra/test_render_blueprint.py` parsea `../render.yaml` y `backend/Dockerfile` (lectura de texto). Verifica: los cuatro recursos y sus tipos/plan free/misma región; `ENV=staging`; `SECRET_KEY` con `generateValue`; seeds con `sync: false`; `DATABASE_URL`/`REDIS_URL` desde recursos; ninguna `envVar` con `value` literal cuya clave contenga `PASSWORD`, `SECRET`, `TOKEN` o `KEY`, ni `DATABASE_URL`/`REDIS_URL` literales; rewrite `/api/*` antes de `/*`; Dockerfile con `runtime` última etapa. `pyyaml==6.0.3` se suma a `requirements-dev.txt` (ya está instalado como transitiva; se fija para CI).
- Alternativa descartada: validar contra el JSON Schema oficial de Render (dependencia de red/versionado; desproporcionado para la demo).

## Risks / Trade-offs

- [El subdominio `.onrender.com` no coincide con el nombre del servicio] → la guía explica cómo leer la URL real y corregir la regla de rewrite y `CORS_ORIGINS`.
- [El rewrite no pasa cookies/headers como se espera] → verificación explícita de login + recarga en la guía y en tasks; plan B documentado en D6 (change aparte).
- [Primer request tras dormir tarda ~1 min y el frontend muestra error] → documentado en la guía ("esperá y recargá"); no se cambia el frontend.
- [Seed interrumpido a mitad (p. ej. redeploy durante el primer arranque)] → idempotencia por SKU ancla no repara; la guía explica reiniciar la base (borrar y recrear la DB del Blueprint).
- [Postgres Free vence a los 30 días y se borra a los 44] → la guía lo advierte; recrear = borrar la DB y volver a sincronizar el Blueprint (el seed se recarga solo).
- [Alguien carga datos reales en la demo] → advertencia explícita en la guía y en el `README`; la demo usa usuarios `@petshop.local`.
- [`/docs` (Swagger) expuesto en la demo] → aceptado para la demo; ocultarlo en prod es C-15a.
- [Rate limit por email compartido (D3)] → aceptado y documentado.
- [`ENV` cerrado rompe un entorno con otro valor] → ninguno conocido; el error al arrancar nombra los valores válidos.

## Migration Plan

1. Aplicar el change (tests en verde, suite completa).
2. La usuaria crea la cuenta de Render y sigue `docs/demo-render.md` (New → Blueprint, rama `main` o la rama del change).
3. Verificación: `GET /api/health` 200, login dueña y mostrador, recarga mantiene sesión, reportes con datos.
4. Rollback: borrar el Blueprint/recursos desde el panel de Render (no afecta el repo ni el entorno local). En el repo, revertir el change no tiene efecto en datos (no hay migraciones nuevas).

## Open Questions

- Si Render asigna exactamente `animall-demo-api.onrender.com` y `animall-demo.onrender.com` solo se sabe al crear el Blueprint (la guía cubre ambos casos).
- Si conviene mantener la demo viva más de 30 días (renovar la DB gratis o pasar a plan pago) se decide cuando la dueña termine de probar; no cambia este change.
