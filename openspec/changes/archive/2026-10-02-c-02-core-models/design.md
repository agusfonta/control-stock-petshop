# Design: c-02-core-models

## Context

C-01 dejó `backend/app/models.py` con solo `Base` (cero tablas por diseño) y una migración anchor `0001` vacía. Ver propuesta (Why) y KB `04` (ERD + atributos/constraints/índices + seed), `05` (RN-PR-01, RN-ST-03) y `08` (monolito modular, routers/dominio, Pydantic estricto, secrets por env). DD-02 excluye granel/vencimientos. La convención del repo es `backend/alembic/versions/0001_anchor.py` con `revision = "0001"`.

## Goals / Non-Goals

**Goals:**

- Definir las 4 entidades base con uuid PK, `AuditMixin` y constraints DB reales (unicidad + checks).
- Primera migración real `0002` encadenada a `0001` con `pg_trgm` y los 3 índices de `04`.
- Seed mínimo idempotente sin secretos en el repo.
- Tests RED-first de constraints y RN-PR-01 que la apply phase debe exigir.

**Non-Goals:**

- Auth JWT, hashing real de passwords más allá del seed, endpoints CRUD, `MovimientoStock`/ventas/compras, frontend, cambios en compose/CI (ver proposal Non-goals).

## Decisions

1. **Un solo módulo `models.py` + `AuditMixin` declarativo.** Modelos `Usuario`, `Producto`, `Distribuidora`, `Cliente` heredan de `Base` + `AuditMixin` (`activo` default True, `created_at`/`updated_at` con server_default `now()` y `onupdate`). Alternativa (paquete `models/` por entidad): descartada por ahora — 4 entidades caben en un módulo; se parte en C-05 cuando lleguen ventas/compras.
2. **UUID PK en Python (`uuid4` string) + `Numeric(10,2)` para dinero.** Evita secuencias predecibles y errores de float en precio/costo. `margen_pct` como `Numeric(5,4)` (0.5000 = 50 %). Alternativa integer-cents: más precisa pero choca con `plantilla_productos.csv` (decimales) de C-01.
3. **`precio_venta` como `column_property` (calculado en lectura) + validación en tests, no columna física.** Cumple RN-PR-01 sin triggers: `precio = costo × (1+margen)` siempre vigente; RN-PR-04 (no reescribir históricos) se vuelve trivial porque no hay columna que congelar. Alternativa columna generada Postgres: atada a un motor y más difícil de testear en SQLite; se reconsidera si el perfilado muestra costo.
4. **Roles como `Enum` nativo (`duena`, `mostrador`) + `CheckConstraint` en migración.** Sin tabla de roles en v1: 2 valores fijos (RN-AU-01), evita join y seed extra. Si v2 necesita permisos finos, se migra a tabla sin romper `Usuario.rol` (misma columna, distinto tipo).
5. **Migración `0002_core_models` manual (no autogenerate ciego), `down_revision = "0001"`.** Incluye `CREATE EXTENSION IF NOT EXISTS pg_trgm`, índices `ix_productos_sku` (unique), `ix_productos_nombre_trgm` (GIN trgm), `ix_productos_categoria`. Downgrade elimina índices/tablas/extensión en orden inverso. Se conserva `0001_anchor.py` intacta.
6. **Base repository genérico en `backend/app/repositories.py`** (`get_by_id`, `list_active`, `soft_delete` que pone `activo=False` en vez de borrar — anticipa la regla dura "nunca borrar con ventas"). Los modelos no exponen queries; C-04+ lo reutiliza.
7. **Seed en `backend/scripts/seed.py` idempotente por `get-or-create` sobre claves naturales** (email dueña, nombre categoría, clave método de pago). Password inicial solo desde `SEED_OWNER_PASSWORD` (falla con mensaje claro si falta); categorías y métodos como constantes versionadas. Sin Pydantic de endpoints; si el seed valida entrada CSV futura, schemas estrictos entonces.
8. **Tests en `backend/tests/test_models.py` con SQLite + `psycopg`-solo-para-migración.** Constraints CHECK/UNIQUE y fórmula de precio corren en SQLite (rápido, RED-first real); la migración `0002` y el índice trgm se validan contra Postgres del compose (test marcado `pg_only`). Evita falsos verdes del dialecto.

## Risks / Trade-offs

- [`column_property` vs filtro/orden por precio en SQL] → Mitigación: en C-04 el listado ordena por `costo` o materializa precio en la query; si el POS necesita ordenar por precio a escala, migrar a columna generada (diseño lo prevé).
- [`pg_trgm` no disponible en SQLite] → Mitigación: tests de similitud marcados `pg_only` y corridos en CI contra Postgres 16; el resto en SQLite.
- [Seed dueña sin password en CI] → Mitigación: `SEED_OWNER_PASSWORD` de mentira solo en entorno test/compose local, documentado; prod exige secreto del host (regla dura AGENTS.md).
- [Enum nativo dificulta añadir roles] → Mitigación: cambio de tipo con migración dedicada en v2; hoy 2 roles fijos.
- [DD-02: columnas futuras (peso/vencimiento)] → Mitigación: no se agregan columnas placeholder; `Producto.unidad` ya distingue `bolsa`/`caja` sin implicar granel.

## Migration Plan

1. Apply: mergea `models.py`, `repositories.py`, `0002_core_models.py`, `seed.py`, `test_models.py` (tests en verde).
2. Deploy local: `alembic upgrade head` (0001 → 0002), luego `python -m backend.scripts.seed` con `SEED_OWNER_PASSWORD` en `.env`.
3. Rollback: `alembic downgrade -1` vuelve a `0001` (cero tablas); el seed es re-ejecutable así que no requiere rollback de datos.
4. Sin impacto en `foundation`: health/compose/CI/CSV intactos.

## Open Questions

- Ninguna que bloquee specs o tareas. Detalle menor para apply: ¿`telefono`/`email` de `Cliente` llevan índice? Propuesta por defecto: no (búsqueda por nombre/saldo en v1); si el mostrador pide buscar por teléfono, índice en C-04.
