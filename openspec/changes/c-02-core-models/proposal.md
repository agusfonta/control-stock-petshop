# Proposal: c-02-core-models

## Why

Sin modelos de dominio no existe nada sobre lo que construir: auth (C-03), CRUDs (C-04+) y ventas/compras (C-05+) dependen de `Usuario`, `Producto`, `Distribuidora` y `Cliente` persistidos con constraints reales. C-01 dejó `models.py` con solo `Base` y una migración anchor vacía por diseño; este change crea la primera migración real y el seed mínimo para desbloquear todo FASE 0/1.

## What Changes

- Modelos SQLAlchemy en `backend/app/models.py` (o módulo `models/` si el diseño lo justifica):
  - `Usuario`: id uuid PK, email unique, password_hash, rol (`duena`/`mostrador`), activo — más `AuditMixin`.
  - `Producto`: id uuid PK, sku unique, nombre, marca, categoria, unidad (`unidad`/`bolsa`/`caja`), costo (Numeric), margen_pct (Numeric), precio_venta calculado = costo×(1+margen), stock_actual (Check >= 0), stock_minimo, distribuidora_default_id FK nullable, activo — más `AuditMixin`.
  - `Distribuidora`: id uuid PK, nombre, contacto, cuit, condiciones, activo — más `AuditMixin`.
  - `Cliente`: id uuid PK, nombre, telefono, email, direccion, saldo_cc (default 0), activo — más `AuditMixin`.
  - `AuditMixin`: `activo` (bool default True), `created_at`, `updated_at` (server defaults + onupdate).
  - Base repository genérico (`get_by_id`, `list_active`, `soft_delete`) según patrón de `08_arquitectura_propuesta.md`.
- Migración Alembic `0002_core_models` (down_revision `0001`): crea las 4 tablas + índices (`sku` unique, `nombre` trgm via `pg_trgm`, `categoria`). La `0001_anchor` de C-01 queda intacta como ancestro vacío.
- Seed mínimo idempotente (`backend/app/seed.py` o `backend/scripts/seed.py`): roles `duena`/`mostrador` (tabla o enum según diseño), usuario dueña inicial (password desde env `SEED_OWNER_PASSWORD`, nunca hardcodeado), categorías base (alimentos, accesorios, higiene, farmacia), métodos de pago base (efectivo, transferencia, MP, tarjeta).
- Tests RED-first `backend/tests/test_models.py`: constraints (`stock_actual >= 0`, `sku` unique, `precio = costo×(1+margen)` RN-PR-01), email unique, seed idempotente. Sin tests de endpoints en este change.
- DD-02 se respeta: NO se modelan granel por peso ni lote/vencimiento (v2).

## Capabilities

### New Capabilities

- `core-models`: modelos base persistidos con constraints e índices, migración inicial real, seed mínimo y reglas de cálculo de precio. Cubre ERD `04` §Producto/Distribuidora/Cliente/Usuario + Seed data inicial, RN-PR-01 y RN-ST-03 (a nivel modelo: stock no negativo como precondición del append-only).

### Modified Capabilities

- Ninguna. `foundation` (health/compose/CI/plantilla CSV) no cambia.

## Impact

- Afecta: `backend/app/models.py`, `backend/alembic/versions/0002_*.py`, nuevo seed script, `backend/tests/test_models.py`. Sin cambios en routers, frontend, compose ni CI.
- Dependencias: requiere C-01 mergeado (Base, engine, anchor 0001) — ya cumplido en `main`.
- Riesgos: `pg_trgm` requiere extensión Postgres (disponible en Postgres 16 oficial); la migración debe crearla con `CREATE EXTENSION IF NOT EXISTS pg_trgm`.
- Non-goals explícitos: auth JWT (C-03), CRUD endpoints (C-04+), MovimientoStock/Venta/Compra (C-05+), UI, deploy.
