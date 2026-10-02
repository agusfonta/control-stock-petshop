# Design

## Context

Ver `proposal.md` — Why. Estado actual: repo solo con KB + CHANGES + README; sin BE/FE. Restricciones: arranque limpio (DD-01, demo Animall no reutilizable), `/api/*` sin versionado según KB, hard rules de AGENTS.md (Alembic 0001 vacía, Pydantic estricto, TS estricto, shadcn primero, env en ejemplos). Specs: `specs/foundation/spec.md` (REQ health, compose, CI, CSV).

## Goals / Non-Goals

**Goals:**

- `docker compose up --build` reproducible + CI paralela verde + contrato `GET /api/health` estable.
- Skeletons BE/FE listos para C-02 (modelos) y C-03 (JWT) sin re-trabajo de layout.

**Non-Goals:**

- Tablas, JWT real, POS, FE ARCA, Mercado Pago, reportes, `vercel.json`/`render.yaml`, Dockerfile FE — todo va en changes posteriores (C-02→C-15). Sin `api/v1/`: la KB fija `/api/*` sin versionado.

## Decisions

1. **Python 3.12-slim + FastAPI 0.116 + SQLAlchemy 2.0 + Alembic + pydantic-settings + python-jose + passlib/bcrypt + pytest + httpx.** Pin exacto en `requirements.txt`. *Alt: 3.11 — se elige 3.12 por ser el slim estable actual sin romper FastAPI 0.116.*
2. **Estructura BE:** `backend/app/main.py` (factoriza `create_app`, monta `/api/health`, incluye `/docs`), `routers/health.py` (thin) → sin `services/` con lógica en C-01 (dirs vacíos con `.gitkeep`), `models.py` solo `Base`, `schemas.py` solo `HealthResponse` Pydantic estricto, `deps.py` solo `get_settings` stub, `core/config.py` (Settings por env), `core/db.py` (engine + SessionLocal + Base, sin tablas), `core/security.py` (stub documentado, JWT real en C-03). *Sin `api/v1/`: la KB fija `/api/*` sin versionado.*
3. **Health sin DB (intencional):** `{"status":"ok","version"}` (`version` desde `app.__version__` o Settings) sin chequeos. *Trade-off: menos fidelidad vs CI rápida sin flakiness; checks reales en C-15.*
4. **Alembic:** `alembic.ini` + `alembic/env.py` importando `Base` + `DATABASE_URL` de Settings; migración `0001` vacía de anclaje, cero tablas (hard rule: NUNCA schema sin migración, aquí solo se inicializa).
5. **Docker:** BE `Dockerfile` stages `deps → dev → runtime`; base `python:3.12-slim` pineada; `USER appuser`; `HEALTHCHECK` contra `/api/health`; `.dockerignore`. Compose: `postgres:16-alpine` + `redis:7-alpine` pineadas, `depends_on: db condition: service_healthy`, `DATABASE_URL=postgresql://petshop:petshop@db:5432/petshop`, `REDIS_URL=redis://redis:6379/0`. Sin Dockerfile FE (dev vía `npm run dev` con proxy `/api → localhost:8000`; prod en C-15).
6. **FE:** `vite.config.ts` ESM + proxy `/api`, `VITE_API_URL`; Router con `/`, `/pos`, `/stock` placeholders; Zustand + React Query providers sin lógica; `components.json` + alias `@/` + tokens Tailwind; shadcn compone, no custom. Sin barrel files. `tsconfig` con `strict + noUnusedLocals + noImplicitAny`, NUNCA `any`.
7. **OpenAPI:** sin spec file en C-01; contrato = `HealthResponse` + `/docs` autogenerado.
8. **Env:** `backend/.env.example` (`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY=changeme`, `ARCA_CERT/KEY`, `MP_ACCESS_TOKEN` vacíos), `frontend/.env.example` (`VITE_API_URL=http://localhost:8000`). `.env` reales en `.gitignore`; NUNCA hardcodear secrets.
9. **CSV:** `data/plantilla_productos.csv` (headers del spec; validación real en C-08).

## Contratos

- `GET /api/health → 200 {status: "ok", version: "0.1.0"}`.
- Compose networking: `api → db:5432`, `api → redis:6379`; host: api 8000, db 5432, redis 6379.

## Test plan (smoke, no RN)

`tests/test_health.py`: `GET /api/health == 200` + `status == ok` (httpx AsyncClient). CI: `pytest -q`; FE `tsc --noEmit` + `npm run build`.

## Risks / Trade-offs

- Health sin DB oculta caídas reales → Mitigación: checks con DB/Redis en C-15.
- Placeholders ARCA/MP podrían divergir de APIs reales → Mitigación: solo strings vacíos en `.env.example`, sin código que los consuma.
- Sin Dockerfile FE: paridad dev/prod parcial → Mitigación: prod FE se define en C-15 con `vercel.json`/imagen.

## Migration Plan

Arranque limpio, sin datos que migrar. Rollback: borrar change de apply (no hay tablas: `0001` vacía). Despliegue: solo local + CI; prod en C-15.

## Open Questions

Ninguna bloqueante para C-01. Las Altas (despliegue BE/FE/DB, datos ARCA, modo MP) se responden en sus changes (C-15, FE ARCA, MP) y aquí solo usan placeholders.
