# Proposal

## Why

La dueña todavía no probó Animall: hoy solo corre en local. Antes de endurecer producción (C-15a) conviene que la use de verdad y pida cambios, así que se necesita un **despliegue de demo** en el plan gratis de Render (decisiones D1, D6 y D7 de `docs/plan-produccion.md`). Hoy no se puede: no hay `render.yaml`, la imagen `runtime` no migra ni trae los scripts de seed, y `seed_demo` se niega a correr fuera de `ENV=dev|test`, que en la nube no son aceptables (piden secretos demo y Redis en memoria).

## What Changes

- **Nuevo entorno explícito `ENV=staging`**: se valida como un entorno real (SECRET_KEY ≥ 32, Redis real, BCRYPT_ROUNDS ≥ 12, cookie de refresh `Secure`), pero admite cargar el seed demo. `ENV` pasa a ser un conjunto cerrado (`dev`, `test`, `staging`, `prod`): un valor desconocido aborta el arranque. **BREAKING** solo para quien use hoy otro valor de `ENV` (no hay ninguno en el repo).
- **`seed_demo` admite `ENV=staging`** y sigue negándose con `ENV=prod`; sigue siendo idempotente y sin contraseñas en el código.
- **Imagen `runtime` desplegable**: un script de arranque aplica `alembic upgrade head`, carga el seed demo solo si una variable lo pide explícitamente y luego arranca uvicorn en `$PORT`. La imagen incluye `scripts/`.
- **`render.yaml` (Blueprint)** en la raíz: web service Docker (plan free), Postgres free, Key Value (Redis) free y el frontend como Static Site con rewrite de SPA y reenvío de `/api/*` al backend (mismo origen: la cookie de refresh y el frontend no cambian). Secretos con `generateValue: true` (SECRET_KEY) o `sync: false` (contraseñas del seed); ningún secreto literal.
- **Guía `docs/demo-render.md`** (español): pasos New → Blueprint, qué valores cargar, límites del plan gratis (el backend se duerme, Postgres vence a ~30 días, sin backups, **nunca datos reales**), cómo reiniciar o borrar la demo.
- **Guardas anti-regresión**: tests de config para `staging`, test de que el seed rechaza `prod`, y un test que parsea `render.yaml` (servicios esperados, sin secretos literales) y el `Dockerfile` (`runtime` es la última etapa y copia `scripts/`).

Fuera de alcance: backups (C-15c), hardening de producción y health con chequeos (C-15a), planes pagos, dominio propio, ARCA y Mercado Pago, CI que construya la imagen (C-15b).

## Capabilities

### New Capabilities
- `despliegue-demo`: despliegue de demostración de Animall en Render plan gratis mediante Blueprint versionado, con entorno `staging`, migraciones y seed demo al arrancar, frontend estático con `/api` reenviado al backend y guía de uso para la usuaria.

### Modified Capabilities
- `entorno-local`: el requisito "Seed de demostración" pasa de "solo `ENV` `dev` o `test`" a "`dev`, `test` o `staging`", manteniendo el rechazo con `ENV=prod`.

## Impact

- Backend: `app/core/config.py` (ENV cerrado), `app/modules/auth/router.py` (`_secure_cookie` considera `staging`), `scripts/seed_demo.py` (`ENVS_PERMITIDOS`), nuevo `scripts/start.sh`, `Dockerfile` (etapa `runtime`), `requirements-dev.txt` (`pyyaml` para el test del Blueprint).
- Tests: `tests/infra/test_config_auth.py`, `tests/infra/test_seed_demo.py`, `tests/auth/test_cookie_flags.py`, nuevo `tests/infra/test_render_blueprint.py`.
- Infra/docs: nuevo `render.yaml`, nuevo `docs/demo-render.md`, `README.md` (enlace a la guía), `docs/plan-produccion.md` (estado del paso demo).
- Frontend: sin cambios de código (usa `/api` relativo, que el rewrite del Static Site reenvía).
- Sin cambios de schema ni migraciones nuevas.
- Governance ALTO (config de seguridad y seed): las decisiones quedan marcadas en `design.md` para revisión humana antes de aplicar.
