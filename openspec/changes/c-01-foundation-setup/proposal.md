# Proposal

## Why

Sin cimientos no hay C-02→C-15. Hoy el repo solo tiene KB + CHANGES + README de 1 línea; el demo Animall no es reutilizable (DD-01). Se necesita arranque limpio que deje `docker compose up` + CI verde en <10 min para un dev nuevo.

## What Changes

- Scaffolding BE: `backend/app/{routers,services,models.py,schemas.py,deps.py,core/}` + `main.py`; `GET /api/health`; Alembic init (migración `0001` vacía de anclaje, cero tablas); `core/{config,security,db}`; `Dockerfile` multi-stage; `backend/.env.example`; pytest smoke.
- Scaffolding FE: `frontend/src/{features,shared,pages/}`; Vite 8 + React 19 + TS estricto + Tailwind + Zustand + React Query + react-router; `components.json` shadcn; `frontend/.env.example`.
- Infra local: `docker-compose.yml` (api + db Postgres 16 + redis 7, healthchecks, volúmenes nombrados); `data/plantilla_productos.csv` con headers canónicos y 3 filas ejemplo.
- CI: `.github/workflows/ci.yml` con jobs paralelos `backend` (pytest) y `frontend` (tsc + build).
- Fuera de alcance: modelos de dominio (C-02), auth JWT (C-03), cualquier RN de negocio, despliegue prod (C-15), frontend Dockerfile, `vercel.json`/`render.yaml` (van en C-15).
- Excepción documentada a la regla "NUNCA código de RN sin test failing previo": C-01 no contiene RN; el único test es smoke de `GET /api/health`.

## Capabilities

### New Capabilities

- `foundation`: arranque del proyecto — health check, compose local (api+db+redis), CI paralela BE/FE y plantilla CSV canónica.

### Modified Capabilities

- Ninguna (no existen specs previas; `openspec list --specs` vacío).

## Impact

- **Afecta**: layout nuevo `backend/`, `frontend/`, `docker-compose.yml`, `.github/workflows/ci.yml`, `data/plantilla_productos.csv`. Sin impacto en código existente (no hay BE/FE previos).
- **APIs**: nuevo `GET /api/health → 200 {"status":"ok","version":"0.1.0"}` sin auth ni dependencias de DB/Redis.
- **Dependencias**: pins exactos — Python 3.12-slim, FastAPI 0.116, SQLAlchemy 2.0, Postgres 16, Redis 7, React 19, Vite 8.
- **Non-goals**: tablas, JWT, POS, FE ARCA, Mercado Pago, reportes, despliegue prod.
- **Acceptance**:
  1. `docker compose up --build` levanta 3 servicios sanos; `curl localhost:8000/api/health` → `{"status":"ok","version":"0.1.0"}`.
  2. `pytest backend` verde; `tsc --noEmit && vite build` verde en `frontend/`.
  3. CI en PR con 2 jobs paralelos en verde.
  4. `plantilla_productos.csv` con headers canónicos y 3 filas ejemplo.
- **Riesgos**:
  - Preguntas Altas abiertas (despliegue, ARCA, MP) → mitigado: C-01 solo usa placeholders, no bloquea.
  - Divergencia de versiones FE/BE → mitigado: pines exactos en design.
