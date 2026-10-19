# Tasks — C-16 Reorganización del backend por módulos

> Gate de **cada** fase (salvo la 0 y la 7): en `backend/`, `python -m pytest -q` en verde, con N tests igual a la línea base más los nuevos, y `ruff check .` limpio. No se avanza de fase con rojo.
> Sin commits intermedios: un único commit al final (fase 7).

## 0. Línea base (checkpoint con la usuaria)

- [x] 0.1 Revisar con la usuaria los ~35 archivos modificados y los 2 tests borrados (`test_migracion_helpers_humo.py`, `test_reportes_helpers_humo.py`) en `change/c-13-frontend-reportes-y-limpieza`, más el untracked `tests/alembic_helpers.py`. Ella decide si se commitean (conventional commit) o se stashean. Verificar con `git status --porcelain` vacío.
- [x] 0.2 Crear la rama `change/c-16-modulos` desde el punto acordado y verificar con `git branch --show-current`.
- [x] 0.3 Correr `python -m pytest -q` y `ruff check .` en `backend/`, y anotar la cantidad de tests en verde (N base). Si hay fallas, son preexistentes: STOP y reportarlo.
- [x] 0.4 (alembic check NO verificable: sin PG accesible; sustituido por DDL PG compilado) Correr `alembic upgrade head` + `alembic check` contra la BD local y verificar "No new upgrade operations detected".
- [x] 0.5 Guardar los snapshots de referencia en el scratchpad: la metadata (tablas, columnas, constraints y enums de `Base.metadata.sorted_tables`, D9.4) y `create_app().openapi()` en JSON (D9.5). Verificar que existen los 2 archivos y que la metadata lista 13 tablas.

## 1. Esqueleto

- [x] 1.1 Crear `app/modules/__init__.py` y un subpaquete vacío (`__init__.py`) por dominio: health, auth, productos, stock, distribuidoras, compras, clientes, ventas, reportes, migracion. Verificar con `python -c "import app.modules.ventas"`.
- [x] 1.2 Crear `app/core/base.py` con `AuditMixin` y `_uuid` copiados verbatim y hacer que `app/models.py` los importe de ahí. Gate de la fase en verde.
- [x] 1.3 Crear `app/core/schemas.py` con `PaginacionResponse`, `coerce_decimal`, `nombre_no_vacio` y `serialize_money` (D2). `app/schemas.py` los importa y mantiene alias privados internos hasta vaciarse. Gate en verde y snapshot OpenAPI igual.
- [x] 1.4 Crear `app/modules/models.py` (agregador, D3). Por ahora solo importa `Base` y reexporta los modelos desde `app.models`, y se completa a medida que se mueven los modelos. Verificar con `python -c "from app.modules.models import metadata; print(len(metadata.tables))"`, que debe dar 13.

## 2. Dominios hoja: health, auth, clientes, productos

- [x] 2.1 health: mover `HealthResponse` a `modules/health/schemas.py` y `routers/health.py` a `modules/health/router.py` con `git mv`. Actualizar `main.py` y los imports de tests. Verificar que `test_health.py` pasa.
- [x] 2.2 auth (CRITICAL, verbatim): mover `Usuario`/`ROL_USUARIO` a `modules/auth/models.py`, los schemas de auth/usuarios a `modules/auth/schemas.py`, `routers/auth.py` a `modules/auth/router.py` y `routers/usuarios.py` a `modules/auth/usuarios_router.py`. Actualizar `deps.py`, `main.py` (mismo orden de include), el agregador y el shim de `app/models.py`/`app/schemas.py`. Verificar que `git diff -M` muestra solo cambios de import y que pasan los `test_auth_*`, `test_security_auth`, `test_rbac_matrix`, `test_cookie_flags`, `test_rate_limit` y `test_bcrypt_rounds`.
- [x] 2.3 clientes (mover): `Cliente` a `modules/clientes/models.py`, la sección C-09 a `modules/clientes/schemas.py` (usa `core.schemas.nombre_no_vacio`) y `routers/clientes.py` a `modules/clientes/router.py`. El import de `to_venta_list_response` queda temporalmente desde `app.routers.ventas` hasta la fase 4. Verificar que pasan los `test_clientes*`.
- [x] 2.4 clientes service (TDD, D5): con la red de seguridad de los `test_clientes*` en verde, escribir en RED `tests/test_clientes_service.py` (crear, obtener inexistente, email duplicado, buscar, soft-delete; al menos 2 casos por función). Después, GREEN: extraer `modules/clientes/service.py` con excepciones de dominio, y el router delega y traduce a HTTP con el mismo status y detail. Verificar con el test nuevo y los HTTP existentes en verde, sin editarlos.
- [x] 2.5 productos (mover): `Producto`/`UNIDAD_PRODUCTO` a `modules/productos/models.py`, la sección C-04 a `modules/productos/schemas.py` (usa `core.schemas`) y `routers/productos.py` a `modules/productos/router.py`. El import de `services.stock` queda temporalmente. Verificar que pasan los `test_productos_*`.
- [x] 2.6 productos service (TDD, D5): con la red de seguridad en verde, escribir en RED `tests/test_productos_service.py` (crear, SKU duplicado, obtener inexistente, listar/buscar paginado, actualizar margen mínimo, soft-delete). GREEN: extraer `modules/productos/service.py`; el endpoint `/ajustar` sigue delegando en el service de stock. Verificar los tests nuevos y los HTTP sin editar en verde, y que el snapshot OpenAPI no cambió.
- [x] 2.7 Gate de la fase 2: suite completa, ruff y snapshot OpenAPI igual.

## 3. Núcleo: stock, distribuidoras, compras

- [x] 3.1 stock: `MovimientoStock`/`TIPO_MOVIMIENTO` y sus 2 listeners (verbatim) a `modules/stock/models.py`, la sección C-05 a `modules/stock/schemas.py`, `services/stock.py` a `modules/stock/service.py` y `routers/stock.py` a `modules/stock/router.py`. Actualizar los imports de `services.stock` en productos, compras, ventas, reportes, migración, `seed_demo` y tests (sin shim, D4). Verificar que pasan los `test_stock_*` y que no queda `grep -rn "services.stock" app scripts tests`.
- [x] 3.2 distribuidoras (mover): `Distribuidora` y `ListaPrecio` a `modules/distribuidoras/models.py`, la sección C-06 a `schemas.py` y el router a `router.py`. Verificar que pasan los `test_distribuidoras*`.
- [x] 3.3 distribuidoras service (TDD, D5): con la red de seguridad en verde, escribir en RED `tests/test_distribuidoras_service.py` (crear, nombre vacío o duplicado si aplica, comparar costos, agregar/actualizar/quitar en lista con producto inexistente). GREEN: extraer `modules/distribuidoras/service.py`. Verificar los tests nuevos y los HTTP sin editar en verde.
- [x] 3.4 compras: los 4 modelos, los 2 enums y los 2 listeners de `EntradaStock` a `modules/compras/models.py`, la sección C-07 a `schemas.py` (usa `coerce_decimal`/`serialize_money`), `services/compras.py` a `service.py` y el router a `router.py`. Actualizar `test_compras_recibir` (el `monkeypatch` sobre `svc_compras.aplicar_movimiento` ahora apunta a `app.modules.compras.service`) y `seed_demo`. Verificar que pasan los `test_compras_*` y que el monkeypatch sigue siendo efectivo (el test de rollback falla si se lo neutraliza).
- [x] 3.5 Gate de la fase 3: suite, ruff, snapshot de metadata igual (D9.4) y `alembic check` sin operaciones.

## 4. Dependientes: ventas, reportes, migración

- [x] 4.1 ventas: `Venta`, `LineaVenta`, `PagoVenta`, sus enums y sus 4 listeners a `modules/ventas/models.py`, la sección C-10 a `schemas.py`, `services/ventas.py` a `service.py` y el router a `router.py`. Mover `_to_venta_resumen`/`to_venta_list_response` al service (D6) y hacer que `clientes/router.py` los importe desde `modules.ventas.service`. Verificar que pasan los `test_ventas_*` y `test_clientes_historial`, y que no queda `grep -rn "routers.ventas" app`.
- [x] 4.2 reportes: la sección C-14 a `modules/reportes/schemas.py`, `services/reportes.py` a `service.py` y el router a `router.py`. Actualizar `tests/reportes_helpers.py` (`fijar_ahora` debe parchear `app.modules.reportes.service`) y los ~22 imports de tests. Verificar que pasan los `test_reportes_*` (los de frescura y período dependen del monkeypatch de `_ahora_utc`).
- [x] 4.3 migración: la sección C-08 a `modules/migracion/schemas.py`, `services/migracion/*` a `modules/migracion/service/*` con `git mv` y el router a `router.py`. Actualizar los monkeypatch de `test_migracion_aplicar` (`MAX_BYTES`, `analizar`, `aplicar.aplicar_movimiento`) y de `test_migracion_endpoint` (router `importar`), y `scripts/importar_productos.py`. Verificar que pasan los `test_migracion_*` y `test_importar_productos_cli`.
- [x] 4.4 Gate de la fase 4: suite, ruff, snapshot OpenAPI igual y `app/routers/` y `app/services/` vacíos (borrarlos). Verificar que `ls app/routers app/services` falla.

## 5. Cierre: quitar shims e integración

- [x] 5.1 Migrar todos los `from app.models` / `from app.schemas` de tests, scripts (`seed_demo`, `importar_productos`, `init_db`), `alembic/env.py` (→ `from app.modules.models import Base`) y `conftest.py` a los módulos nuevos o al agregador. Verificar que `grep -rn "app\.models\b\|app\.schemas\b" backend --include=*.py` no devuelve nada.
- [x] 5.2 Borrar los shims `app/models.py` y `app/schemas.py`. Verificar que la suite completa y `ruff check .` pasan.
- [x] 5.3 Verificación final de equivalencia: el snapshot de metadata y el de OpenAPI son idénticos a los de la fase 0 (`diff` vacío) y `alembic check` no tiene operaciones.
- [ ] 5.4 (NO VERIFICADO: Docker no estaba corriendo) `docker compose up --build`: verificar que migrate, `seed_demo` y uvicorn arrancan y que `GET /api/health` devuelve 200. Prueba de humo del frontend: login y una venta en el POS.
- [x] 5.5 Docs: actualizar el árbol de `backend/` en `README.md` (~l.179), la estructura en `knowledge-base/08_arquitectura_propuesta.md` (l.15-20) y la nota de estructura en `CLAUDE.md`, y agregar la entrada C-16 a `CHANGES.md` (fase 4 o mantenimiento). Verificar que las rutas citadas existen.

## 6. Tests a `tests/<dominio>/`

- [x] 6.1 Crear `tests/{auth,productos,stock,distribuidoras,compras,clientes,ventas,reportes,migracion,infra}/__init__.py` y mover cada `test_*.py` con `git mv` según D8. `conftest.py`, `alembic_helpers.py` y `*_helpers.py` quedan en la raíz. Verificar que `python -m pytest -q` recolecta la misma cantidad de tests que antes de mover y que todos pasan.
- [x] 6.2 Verificar que CI (`python -m pytest -q` con `TEST_PG_URL` para los `*_pg`) sigue encontrando los tests de PG: correr `pytest -q -k pg --collect-only` y comparar contra la cantidad de antes.

## 7. Commit único y archive

- [ ] 7.1 Revisión final con la usuaria: `git diff -M --stat` y `git status`. Confirmar que no se cuelan archivos ajenos (pycache, dev.db, logs).
- [ ] 7.2 Un único commit conventional (`refactor(backend): reorganizar por modulos de dominio (C-16)`) en `change/c-16-modulos`, sin PR. Verificar con `git log -1 --stat`.
- [x] 7.3 `/opsx:archive c-16-reorganizacion-por-modulos` y tildar C-16 en `CHANGES.md`.
