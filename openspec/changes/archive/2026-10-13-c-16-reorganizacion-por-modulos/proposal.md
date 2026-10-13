# Proposal — C-16 Reorganización del backend por módulos de dominio

## Why

El backend creció por capas técnicas: `app/models.py` (628 líneas, 13 modelos), `app/schemas.py` (1332 líneas, 10 dominios), `app/routers/` y `app/services/`. Tocar un dominio obliga a navegar cuatro archivos grandes, los límites entre dominios no se ven y ya aparecieron acoples cruzados (`routers/clientes.py` importa un helper de `routers/ventas.py`). Con C-01…C-15 cerrados es el momento de reorganizar por dominio, antes de sumar FE ARCA / Mercado Pago, siguiendo el patrón `app/modules/<dominio>/{models,schemas,service,router}.py` del proyecto de referencia TP_Libreria.

## What Changes

- Nuevo paquete `backend/app/modules/` con un subpaquete por dominio: `health`, `auth` (incluye usuarios), `productos`, `stock`, `distribuidoras`, `compras`, `clientes`, `ventas`, `reportes`, `migracion`.
- `app/modules/models.py` agregador: importa los `models` de cada módulo y expone `Base`/`metadata` para Alembic y `init_db`.
- Piezas transversales a `app/core/`: `AuditMixin` y `_uuid` (`core/base.py`), `PaginacionResponse` (`core/schemas.py`).
- `app/main.py` incluye el router de cada módulo, en el mismo orden que hoy.
- Se extrae `service.py` en **productos, clientes y distribuidoras** (hoy la lógica vive en el router). Es la única parte que cambia código además de moverlo, y se hace con TDD de caracterización.
- Se corrige el acople `clientes → routers.ventas`: `to_venta_list_response` pasa a `modules/ventas/service.py`.
- Se borran `app/models.py`, `app/schemas.py`, `app/routers/` y `app/services/` cuando terminan las fases. Mientras duran, `models.py`/`schemas.py` quedan como shims temporales. Se migran los imports de tests, scripts y `alembic/env.py`.
- Fase final aparte: los tests pasan a `tests/<dominio>/`. `conftest.py` y los helpers compartidos quedan en la raíz de `tests/`.
- Docs: README, CLAUDE.md, CHANGES.md (agregar C-16) y `knowledge-base/08_arquitectura_propuesta.md`.

**Sin cambio de comportamiento:** las rutas HTTP, los contratos Pydantic, los códigos de error y los mensajes no cambian. `Base.metadata` sale idéntica, así que no hay migración Alembic nueva. El frontend no se toca.

## Capabilities

### New Capabilities
- Ninguna.

### Modified Capabilities
- Ninguna. Es un refactor estructural puro y ningún requisito de spec cambia. El change declara `skip_specs: true`. Ningún spec de `openspec/specs/` referencia rutas de archivos del backend.

## Impact

- **Código:** todo `backend/app/` salvo `core/config.py`, `core/db.py`, `core/security.py`, `core/rate_limit.py`, `core/refresh_store.py` y `core/texto.py`, que no cambian. También `deps.py`, que solo cambia el import de `Usuario`.
- **Alembic:** `alembic/env.py` cambia el import de `Base` y deben seguir registradas las 13 tablas. Las revisiones existentes no se tocan.
- **Tests:** unos 115 imports de `app.models`, unos 31 de `app.schemas` y unos 40 de `app.services.*`/`app.routers.*`. Hay 6 `monkeypatch.setattr` sobre objetos de módulo (services de compras, reportes y migración, y el router de migración) que deben apuntar al módulo real nuevo.
- **Scripts:** `seed_demo`, `importar_productos` e `init_db`.
- **Infra/CI:** sin cambios esperados, porque todo sigue dentro de `app/` (Dockerfile, compose, `ruff check .`, `pytest`). Se verifica con `docker compose up`.
- **Gobernanza:** auth es CRITICAL, así que su lógica se mueve verbatim y sin editarla. Productos, clientes y distribuidoras son MEDIUM, con checkpoints en la extracción de service.
- **Prerrequisito:** el árbol git hoy está sucio (unos 35 archivos modificados y 2 tests borrados). Hay que cerrar la línea base antes de empezar.
