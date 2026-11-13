# Tasks

Strict TDD (RED antes de GREEN), mínimo necesario, sin commits/PR salvo pedido. Governance ALTO: no empezar hasta que la usuaria apruebe las decisiones **[REVISAR]** de `design.md` (D1, D2, D3, D4, D6, D7). Backend: pytest desde `backend/` con `python -m pytest`. Sin migraciones ni cambios de frontend.

## 1. Config: `ENV` cerrado y `staging` como entorno real (D1)

- [x] 1.1 Safety net: correr `tests/infra/test_config_auth.py`, `tests/infra/test_dev_entorno.py`, `tests/auth/test_bcrypt_rounds.py` y anotar el baseline en verde.
- [x] 1.2 RED: en `tests/infra/test_config_auth.py` agregar: `ENV=staging` con secreto ≥ 32 y Redis real se acepta; `ENV=staging` con `changeme`/secreto corto falla; `ENV=staging` con `REDIS_URL=memory://` falla; `ENV=staging` con `BCRYPT_ROUNDS=4` falla; `ENV=produccion` (y `Prod`) falla nombrando `dev, test, staging, prod`. Verificación: solo el test del ENV desconocido falla (los de staging ya pasan por la regla "fuera de dev/test" y quedan como guarda anti-regresión).
- [x] 1.3 GREEN: `env: Literal["dev", "test", "staging", "prod"]` en `Settings`, sin tocar las validaciones existentes. Verificación: tests de 1.2 y safety net en verde; suite completa de backend en background en verde (nadie usa otro valor de `ENV`).

## 2. Cookie de refresh `Secure` en staging (D3)

- [x] 2.1 Safety net: `tests/auth/test_cookie_flags.py` en verde.
- [x] 2.2 RED: test en `tests/auth/test_cookie_flags.py` que, con `ENV=staging` (mismo patrón que `test_cookie_secure_en_prod`) y request `http`, el `Set-Cookie` del login incluye `secure`, `httponly` y `samesite=lax`. Verificación: falla.
- [x] 2.3 GREEN: `_secure_cookie` usa `settings.env in ("prod", "staging") or request.url.scheme == "https"`. Verificación: `tests/auth` en verde (el test de dev sin `Secure` sigue pasando).

## 3. Seed demo admite staging y sigue rechazando prod (D2)

- [x] 3.1 Safety net: `tests/infra/test_seed_demo.py` en verde.
- [x] 3.2 RED: test `test_staging_carga_el_demo_y_es_idempotente` (con `env="staging"`: crea usuarios y datos; segunda corrida `datos_creados=False` y no cambia passwords) y ajustar `test_aborta_con_env_prod_y_no_modifica_la_base` para que el mensaje nombre `staging`. Verificación: fallan.
- [x] 3.3 GREEN: `ENVS_PERMITIDOS = ("dev", "test", "staging")`, mensaje de rechazo y docstring actualizados. Verificación: `tests/infra/test_seed_demo.py` en verde, incluido `test_script_sin_passwords_literales`.

## 4. Imagen `runtime` desplegable (D4, D5)

- [x] 4.1 RED: `tests/infra/test_render_blueprint.py` (parte Dockerfile + script): la última etapa `FROM` es `runtime`; `runtime` tiene `USER` no root, `COPY ./scripts ./scripts` y `CMD` que ejecuta `scripts/start.sh`; `scripts/start.sh` existe, usa `set -eu`, corre `alembic upgrade head` antes de uvicorn, corre `python -m scripts.seed_demo` solo bajo `SEED_DEMO_AL_ARRANCAR=true`, y termina en `exec uvicorn ... --port "${PORT:-8000}"`. Verificación: falla.
- [x] 4.2 GREEN: crear `backend/scripts/start.sh` (POSIX sh, finales de línea LF; agregar `*.sh text eol=lf` en `.gitattributes` si no existe la regla) y actualizar la etapa `runtime` del `Dockerfile`. Verificación: test 4.1 en verde; `docker build -t animall-runtime ./backend` OK.
- [x] 4.3 Verificación de integración local: con `docker compose up -d db redis`, correr la imagen `runtime` con `ENV=staging`, `DATABASE_URL`/`REDIS_URL` del compose, `SECRET_KEY` aleatoria de 48 caracteres generada en la terminal, `SEED_DEMO_AL_ARRANCAR=true` y contraseñas de prueba por variable de entorno. Comprobar: migra, siembra, `GET /api/health` 200, login devuelve cookie `Secure`; un segundo arranque no duplica datos; con `ENV=prod` + flag el contenedor sale con error y la base no cambia. Anotar evidencia en el resumen del apply.

## 5. Blueprint `render.yaml` (D6, D7, D8)

- [x] 5.1 RED: completar `tests/infra/test_render_blueprint.py` (parte Blueprint, con `yaml.safe_load`): existen `animall-demo-api` (web, docker, free, `virginia`, `healthCheckPath: /api/health`, `dockerfilePath`/`dockerContext` de `backend`), `animall-demo-kv` (keyvalue, free, `virginia`), `animall-demo` (web, static, `rootDir: frontend`, `staticPublishPath` `dist`) y base `animall-demo-db` (free, `virginia`); env del backend: `ENV=staging`, `SEED_DEMO_AL_ARRANCAR=true`, `SECRET_KEY` con `generateValue: true`, `SEED_OWNER_PASSWORD`/`SEED_MOSTRADOR_PASSWORD` con `sync: false`, `DATABASE_URL` desde `fromDatabase` y `REDIS_URL` desde `fromService`; ninguna variable con `value` literal cuya clave contenga `PASSWORD`, `SECRET`, `TOKEN` o `KEY`; routes del Static Site: rewrite `/api/*` a `https://…/api/*` **antes** del rewrite `/*` → `/index.html`. Agregar `pyyaml==6.0.3` a `requirements-dev.txt`. Verificación: falla porque no existe `render.yaml`.
- [x] 5.2 GREEN: escribir `render.yaml` en la raíz según D7. Verificación: `tests/infra/test_render_blueprint.py` en verde y `ruff check tests/infra`.

## 6. Guía y documentación

- [x] 6.1 Escribir `docs/demo-render.md` (español, para la usuaria): qué es la demo y advertencia de no cargar datos reales; requisitos (cuenta Render conectada a GitHub); pasos New → Blueprint → repo → rama; qué completar (`SEED_OWNER_PASSWORD`, `SEED_MOSTRADOR_PASSWORD`) y qué genera Render (`SECRET_KEY`, URLs de DB/Redis); cómo verificar (`/api/health`, login `duena@petshop.local` / `mostrador@petshop.local`, recargar y seguir logueada); qué hacer si la URL del backend no es `animall-demo-api.onrender.com` (corregir rewrite y `CORS_ORIGINS`); límites Free (se duerme a los 15 min y tarda ~1 min, Postgres vence a 30 días + 14 de gracia, Redis sin persistencia ⇒ volver a iniciar sesión, sin backups, rate limit compartido por email); reiniciar datos (borrar y recrear la DB, el seed se recarga al arrancar) y borrar la demo. Verificación: cubre cada punto del requisito "Guía de la demo" del spec.
- [x] 6.2 Enlazar la guía desde `README.md` (sección corta "Demo en la nube") y marcar el paso C-14.5 en `docs/plan-produccion.md` como implementado (pendiente de que la usuaria cree la cuenta). Verificación: enlaces relativos válidos.

## 7. Cierre

- [x] 7.1 Suite completa de backend en background y `ruff check .` en `backend/`; `npm run build` en `frontend/` (confirma que el build del Static Site funciona sin `VITE_API_BASE_URL`). Verificación: todo en verde.
- [x] 7.2 `openspec validate c-15-demo-render --strict` sin errores. Verificación: salida OK.
