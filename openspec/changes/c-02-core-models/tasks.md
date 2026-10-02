# Tasks — c-02-core-models

## 1. Modelos base + repository (TDD RED-first)

- [x] 1.1 Escribir `backend/tests/test_models.py` en RED con casos failing de constraints y RN-PR-01 (stock < 0 rechazado, sku duplicado rechazado, email duplicado rechazado, precio == costo×(1+margen) con 1000/0.5 → 1500, segundo caso triangulador costo 200/margen 0.25 → 250, defaults activo=True y saldo_cc=0) y verificar que pytest falla por modelos inexistentes
- [x] 1.2 Implementar `AuditMixin` + `Usuario`, `Producto` (precio como `column_property`), `Distribuidora`, `Cliente` en `backend/app/models.py` con uuid PK, uniques, Checks y FK opcional, y verificar que `pytest backend/tests/test_models.py -q` pasa en verde
- [x] 1.3 Implementar `backend/app/repositories.py` genérico (`get_by_id`, `list_active`, `soft_delete` con `activo=False`) con test de soft-delete (borrado lógico conserva la fila) y verificar que el test nuevo pasa sin romper los de 1.2

## 2. Migración real 0002

- [x] 2.1 Crear `backend/alembic/versions/0002_core_models.py` (down_revision `0001`, crea extensión `pg_trgm`, 4 tablas con constraints e índices sku-unique/nombre-trgm/categoria, downgrade inverso, `0001_anchor.py` intacta) y verificar con `alembic upgrade head` + `alembic downgrade -1` + `alembic upgrade head` en Postgres del compose dejando las 4 tablas creadas
- [x] 2.2 Añadir test `pg_only` de migración (upgrade desde 0001 crea usuarios/productos/distribuidoras/clientes; inserto con stock negativo falla; índice trgm sobre nombre existe) y verificar que pasa contra Postgres local y se saltea en SQLite

## 3. Seed mínimo idempotente (sin secretos hardcodeados)

- [x] 3.1 Implementar `backend/scripts/seed.py` idempotente por claves naturales (roles duena/mostrador, dueña desde `SEED_OWNER_PASSWORD` con error claro si falta, 4 categorías, 4 métodos de pago, sin catálogo) y verificar doble ejecución con `SEED_OWNER_PASSWORD=test-only` no duplicando (1 dueña, 4 categorías, 4 métodos)
- [x] 3.2 Añadir test de seed (idempotencia + ausencia de credenciales reales en el repo vía grep de `SEED_OWNER_PASSWORD` sin valor literal) y verificar que pasa y `rg -i "password\s*=\s*['\"][^'\"]+['\"]" backend/scripts/seed.py` no devuelve secretos

## 4. Verificación de integración del change

- [x] 4.1 Correr suite completa `pytest -q` y `alembic check` (si disponible) y verificar todo verde sin regresiones en `foundation` (health/compose/CI/CSV intactos)
