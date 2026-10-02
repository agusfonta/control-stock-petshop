# Tasks

## 1. Backend skeleton + health

- [x] 1.1 Crear `app/main.py + routers/health.py + schemas.HealthResponse + core/config.py` con `GET /api/health` y verificar `uvicorn` local responde 200 `{"status":"ok","version":"0.1.0"}`
- [x] 1.2 Crear `core/db.py + models.Base + core/security.py (stub) + deps.py (get_settings stub)` y verificar `python -c "from app.models import Base"` importa sin tablas

## 2. Base DB / Alembic + packaging

- [x] 2.1 Inicializar Alembic (`alembic.ini + env.py` con `DATABASE_URL` de Settings + migración `0001` vacía de anclaje, cero tablas) y verificar `alembic upgrade head` contra la db del compose — re-verificado 2026-10-02 en imagen (`docker compose exec api alembic upgrade head` → 0001 aplicada, solo tabla `alembic_version`; esta verificación en imagen supersede la verificación host-based previa)
- [x] 2.2 Crear `requirements.txt` pineado + `Dockerfile` multi-stage (`deps → dev → runtime`) + `.dockerignore` + `tests/test_health.py` y verificar `pytest -q` en verde

## 3. Compose + env + CI

- [x] 3.1 Crear `docker-compose.yml` (api + db Postgres 16 + redis 7, healthchecks `pg_isready`/`redis-cli ping`, volúmenes `pgdata`/`redisdata`, `depends_on db healthy`) + `backend/.env.example` + `.gitignore` y verificar `docker compose up --build` + `curl localhost:8000/api/health` 200 (verificado 2026-10-02 en imagen: `docker compose up --build -d` sano + `curl localhost:8000/api/health` 200 `{"status":"ok","version":"0.1.0"}`)
- [ ] 3.2 Crear `.github/workflows/ci.yml` con jobs paralelos `backend` (pytest) y `frontend` (tsc + build) y verificar ambos jobs en verde en un PR

## 4. Frontend scaffold + base UI

- [x] 4.1 Scaffoldear FE (Vite 8 + React 19 + TS estricto + Router `/`,`/pos`,`/stock` placeholders + `vite.config.ts` proxy `/api`) y verificar `npm run dev` carga `/`
- [x] 4.2 Agregar Zustand + React Query providers + Tailwind + `components.json` shadcn + alias `@/` + `frontend/.env.example` (`VITE_API_URL`) y verificar `tsc --noEmit` en verde sin `any`

## 5. Plantilla CSV e integración final

- [x] 5.1 Crear `data/plantilla_productos.csv` con headers `sku,nombre,categoria,costo,margen_pct,stock_actual,stock_minimo,distribuidora` y 3 filas ejemplo y verificar columnas exactas con `head -1`
- [x] 5.2 Verificación global de done: `docker compose up --build` sano + `pytest backend` verde + `tsc --noEmit && vite build` verde + CI paralela verde (criterio §Acceptance de proposal, 4 puntos) — parcial 2026-10-02: compose sano + `alembic upgrade head` 0001 + `pytest` 3/3 verde + health 200 verificados; CI en PR pendiente de 3.2

## Blockers (sesión apply 2026-10-01, rama `change/c-01-foundation-setup`)
- ~~3.1/5.2: archivos creados y `docker compose config` válido, pero `docker compose up --build` NO ejecutable — daemon Docker caído (`docker info` → `failed to connect to the docker API at npipe:////./pipe/docker_engine`). Tampoco `alembic upgrade head` (requiere db del compose). Reintentar con Docker Desktop corriendo.~~ RESUELTO 2026-10-02: Docker Desktop corriendo; causa raíz real del fallo de `alembic upgrade head` era `ModuleNotFoundError: No module named 'psycopg2'` (sin driver postgres en `requirements.txt` con `DATABASE_URL=postgresql://...`). Fix: agregado `psycopg2-binary==2.9.10` a `backend/requirements.txt`, rebuild `docker compose up --build -d` sano, `alembic upgrade head` → 0001 aplicada (solo `alembic_version`), health 200 + `pytest` 3/3 verde.
- 3.2: `ci.yml` creado; pasos espejan comandos verificados en local (pytest 3/3, `tsc --noEmit` + `vite build` verdes), pero el verde "en un PR" requiere commit + push + PR (no autorizado en esta sesión).
