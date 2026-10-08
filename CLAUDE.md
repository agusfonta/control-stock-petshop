# Control Stock Petshop — Instrucciones para Agentes

> Reglas globales ya definidas en `~/.claude/CLAUDE.md` (orquestador, governance, TDD, engram): el proyecto las hereda. Acá viven solo las reglas **específicas de este proyecto** + las universales que el global no cubra.

## Stack Tecnológico

| Capa | Tecnologías | Versión mínima |
|---|---|---|
| Backend | Python + FastAPI + SQLAlchemy + Alembic | FastAPI 0.116, SQLAlchemy 2.0 |
| Auth | JWT (python-jose) + passlib/bcrypt | — |
| DB | PostgreSQL | 16 |
| Async/colas | Redis (auth hoy; FE ARCA a futuro, C-11) | 7 |
| Frontend | React + TypeScript + Vite | React 19, Vite 8 |
| Infra local | Docker / Docker Compose | — |
| Test | pytest + pytest-asyncio + httpx | — |

## Base de Conocimiento

Fuente de verdad del dominio. Leer antes de proponer o implementar:

- [knowledge-base/README.md](knowledge-base/README.md) — índice y resumen ejecutivo
- [knowledge-base/01_vision_y_objetivos.md](knowledge-base/01_vision_y_objetivos.md) — alcance v1 / fuera de alcance (granel, vencimientos, offline y vet a v2)
- [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md) — stack e integraciones (ARCA, Mercado Pago)
- [knowledge-base/03_actores_y_roles.md](knowledge-base/03_actores_y_roles.md) — dueña / mostrador, RBAC
- [knowledge-base/04_modelo_de_datos.md](knowledge-base/04_modelo_de_datos.md) — entidades y ERD
- [knowledge-base/05_reglas_de_negocio.md](knowledge-base/05_reglas_de_negocio.md) — RN-VT/ST/PR/CP/AU (bloqueo sin stock, precio=costo×margen)
- [knowledge-base/06_funcionalidades.md](knowledge-base/06_funcionalidades.md) — US por épica
- [knowledge-base/07_flujos_principales.md](knowledge-base/07_flujos_principales.md) — venta, reposición, migración Excel
- [knowledge-base/08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md) — patrones, dirs, env
- [knowledge-base/09_decisiones_y_supuestos.md](knowledge-base/09_decisiones_y_supuestos.md) — enfoque B arranque limpio, UI como el demo
- [knowledge-base/10_preguntas_abiertas.md](knowledge-base/10_preguntas_abiertas.md) — ⚠️ Alta: despliegue BE/FE/DB, datos ARCA, modo Mercado Pago
- [knowledge-base/11_pagos_mercadopago.md](knowledge-base/11_pagos_mercadopago.md) — cobros y conciliación
- [knowledge-base/12_devops_y_despliegue.md](knowledge-base/12_devops_y_despliegue.md) — opción A Vercel+Render/Railway
- [discovery/discovery.md](discovery/discovery.md) + [discovery/sources/](discovery/sources/) — contexto de mercado (Trud techo, Mi Pet Shop piso)

## Skills Disponibles

| Agente | Rol | Skills que carga |
|---|---|---|
| Backend Core | FastAPI, modelos, stock/ventas | `fastapi`, `fastapi-templates`, `postgresql-table-design`, `supabase-postgres-best-practices`, `async-python-patterns` |
| Backend Aux | ARCA, Mercado Pago, contratos | `openapi-spec-generation`, `test-driven-development`, `docker-patterns` |
| Frontend | React TS, POS tablet, stock | `vercel-react-best-practices`, `shadcn`, `frontend-design`, `vite` |
| QA/Local | E2E mostrador, facturación, alertas | `webapp-testing`, `playwright-cli` |
| Infra | Imágenes, compose, despliegue | `multi-stage-dockerfile`, `docker-patterns` |
| Orquestación | OPSX/SDD | skills de `openspec-*` + `kb-creator`, `roadmap-generator`, `agents-md-generator` |

> Los compact rules de cada skill los resuelve el orquestador desde `.atl/skill-registry.md` (generado por `skill-registry`; no versionado — no está en el repo).

## Roadmap de Changes

`CHANGES.md`: 15 changes en 5 fases (F0 cimientos → F4 producción). Camino crítico: C-01 → C-02 → C-03 → C-04 → C-05 → C-10 → C-11 → C-13 → C-15. Primer change: `C-01-foundation-setup` → `/opsx:propose C-01-foundation-setup`.

## Reglas Duras (específicas del proyecto)

- NUNCA cambiar schema sin migración Alembic → crear revisión y migrar.
- NUNCA exponer endpoint sin schema Pydantic estricto → validar todo input/output.
- NUNCA usar `any` en TypeScript → tipar o inferir, `tsconfig` estricto.
- NUNCA crear UI custom si existe en shadcn → buscar/componer primero.
- NUNCA escribir código de RN sin test failing previo → RED antes de GREEN (RN-VT/ST/PR).
- NUNCA hardcodear secrets o credenciales → solo env (`DATABASE_URL`, `ARCA_*`, `MP_ACCESS_TOKEN`).
- NUNCA commitear sin conventional commits ni pushear a main sin PR → rama por change, PR con checks.

## Flujo de Trabajo

1. Leer KB + `CHANGES.md` + pregunta abierta bloqueante si es Alta.
2. `/opsx:propose <change>` (diseño + tareas).
3. `/opsx:apply <change>` (TDD, tests en verde).
4. `/opsx:archive <change>` y tildar `[x]` en `CHANGES.md`.
