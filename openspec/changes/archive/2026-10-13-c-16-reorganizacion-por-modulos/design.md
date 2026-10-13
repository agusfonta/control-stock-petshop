# Design — C-16 Reorganización del backend por módulos de dominio

## Context

La motivación está en `proposal.md`. Estado actual relevante, observado en el código:

- `app/core/db.py` ya define `Base`, `SessionLocal` y `build_engine`. `app/core/` contiene config, db, security, rate_limit, refresh_store y texto.
- `app/models.py` tiene 13 modelos (13 `__tablename__`), `AuditMixin`, `_uuid`, 7 tuplas de enums y 8 listeners `@event.listens_for` de inmutabilidad: before_update/delete sobre `MovimientoStock`, `EntradaStock`, `LineaVenta` y `PagoVenta`. Las relaciones usan strings y `backref`: `ListaPrecio` crea `Producto.lista_precios`/`Distribuidora.lista_precios`; `MovimientoStock` crea `Producto.movimientos`/`Usuario.movimientos_stock`; `PedidoCompra` y `PagoDistribuidora` crean backrefs en `Distribuidora`.
- `app/schemas.py` está dividido en secciones `# --- C-0x`. Algunos helpers privados se usan desde varias secciones: `_coerce_decimal` (productos, distribuidoras, compras, ventas), `_nombre_no_vacio` (distribuidoras, clientes) y `_serialize_money` (compras, ventas, reportes). `PaginacionResponse` es la base de 9 envelopes. `StockItem` usa `ProductoResponse` y los schemas de reportes usan `METODO_PAGO_VENTA_LITERAL`.
- `deps.py` importa `Usuario`. `main.py` incluye 11 routers bajo `/api` en un orden fijo.
- Los tests parchean objetos de módulo con `monkeypatch.setattr(modulo, "nombre", ...)` en `services.compras.aplicar_movimiento`, `services.reportes._ahora_utc` (vía `reportes_helpers.fijar_ahora`), `services.migracion.MAX_BYTES`/`analizar`, `services.migracion.aplicar.aplicar_movimiento` y `routers.migracion.importar`.
- Los tests importan helpers como `from tests.<x>_helpers import ...` y `from tests.conftest import ...`. `tests/` es un paquete con `__init__.py`.

## Goals / Non-Goals

**Goals:**
- Un dominio = un paquete `app/modules/<dominio>/` con `models.py`, `schemas.py`, `service.py` y `router.py` según corresponda.
- `Base.metadata` idéntica antes y después: mismas tablas, columnas, constraints, índices y enums nombrados.
- La suite queda en verde y `ruff` limpio al final de **cada** fase. `alembic check` no detecta cambios.

**Non-Goals:**
- Renombrar endpoints, cambiar contratos o mensajes de error, o ajustar la lógica de negocio.
- Introducir repositorios, inyección de services por `Depends` u otra capa nueva.
- Deduplicar `MAX_PAGE_SIZE`, unificar `_to_response`/`_get_or_404` o mejoras similares (queda para otro change).
- Tocar el frontend, `alembic/versions/` o la infra.

## Decisions

### D1. Estructura objetivo y mapa origen → destino

```
backend/app/
├── main.py, deps.py                 (se quedan; cambian imports)
├── core/
│   ├── config.py, db.py, security.py, rate_limit.py, refresh_store.py, texto.py   (sin cambios)
│   ├── base.py        NUEVO: AuditMixin, _uuid
│   └── schemas.py     NUEVO: PaginacionResponse + coerce_decimal, nombre_no_vacio, serialize_money
└── modules/
    ├── models.py      agregador (D3)
    ├── health/        router.py, schemas.py
    ├── auth/          models.py, schemas.py, router.py, usuarios_router.py
    ├── productos/     models.py, schemas.py, service.py (NUEVO, D5), router.py
    ├── stock/         models.py, schemas.py, service.py, router.py
    ├── distribuidoras/ models.py, schemas.py, service.py (NUEVO, D5), router.py
    ├── compras/       models.py, schemas.py, service.py, router.py
    ├── clientes/      models.py, schemas.py, service.py (NUEVO, D5), router.py
    ├── ventas/        models.py, schemas.py, service.py, router.py
    ├── reportes/      schemas.py, service.py, router.py
    └── migracion/     schemas.py, router.py, service/ (paquete)
```

| Origen | Destino |
|---|---|
| `models.py` `AuditMixin`, `_uuid` | `core/base.py` |
| `models.py` `Usuario`, `ROL_USUARIO` | `modules/auth/models.py` |
| `models.py` `Producto`, `UNIDAD_PRODUCTO` | `modules/productos/models.py` |
| `models.py` `Distribuidora`, `ListaPrecio` | `modules/distribuidoras/models.py` |
| `models.py` `Cliente` | `modules/clientes/models.py` |
| `models.py` `MovimientoStock`, `TIPO_MOVIMIENTO` + 2 listeners | `modules/stock/models.py` |
| `models.py` `PedidoCompra`, `LineaPedido`, `EntradaStock`, `PagoDistribuidora`, `ESTADO_PEDIDO`, `METODO_PAGO_DISTRIBUIDORA` + 2 listeners de `EntradaStock` | `modules/compras/models.py` |
| `models.py` `Venta`, `LineaVenta`, `PagoVenta`, `ESTADO_VENTA`, `METODO_PAGO_VENTA` + 4 listeners | `modules/ventas/models.py` |
| `schemas.py` l.1-32 (HealthResponse) | `modules/health/schemas.py` |
| `schemas.py` l.33-83 (auth y usuarios) | `modules/auth/schemas.py` |
| `schemas.py` l.84-221 (sin `PaginacionResponse`) | `modules/productos/schemas.py` |
| `schemas.py` `PaginacionResponse`, `_coerce_decimal`, `_nombre_no_vacio`, `_serialize_money` | `core/schemas.py` |
| `schemas.py` l.222-327 | `modules/stock/schemas.py` |
| `schemas.py` l.328-468 | `modules/distribuidoras/schemas.py` |
| `schemas.py` l.469-651 | `modules/compras/schemas.py` |
| `schemas.py` l.652-766 | `modules/clientes/schemas.py` |
| `schemas.py` l.767-964 | `modules/ventas/schemas.py` |
| `schemas.py` l.965-1194 | `modules/reportes/schemas.py` |
| `schemas.py` l.1195-1332 | `modules/migracion/schemas.py` |
| `routers/health.py` | `modules/health/router.py` |
| `routers/auth.py` | `modules/auth/router.py` |
| `routers/usuarios.py` | `modules/auth/usuarios_router.py` |
| `routers/productos.py` | `modules/productos/router.py` + `service.py` |
| `routers/stock.py`, `services/stock.py` | `modules/stock/router.py`, `service.py` |
| `routers/distribuidoras.py` | `modules/distribuidoras/router.py` + `service.py` |
| `routers/compras.py`, `services/compras.py` | `modules/compras/router.py`, `service.py` |
| `routers/clientes.py` | `modules/clientes/router.py` + `service.py` |
| `routers/ventas.py`, `services/ventas.py` | `modules/ventas/router.py`, `service.py` (recibe `_to_venta_resumen`/`to_venta_list_response`, D6) |
| `routers/reportes.py`, `services/reportes.py` | `modules/reportes/router.py`, `service.py` |
| `routers/migracion.py`, `services/migracion/*` | `modules/migracion/router.py`, `service/*` (se conservan `__init__`, analisis, aplicar, columnas, lectura y normalizar) |

Los números de línea son una guía. La frontera real son los comentarios `# --- C-0x`.

### D2. Dónde viven las piezas transversales

- **`Base`** se queda en `core/db.py`, donde ya está. Moverla obligaría a tocar `db.py` sin ganar nada.
- **`AuditMixin` y `_uuid`** van a `core/base.py`, porque los usan 8 modelos de 6 módulos.
- **Enums (tuplas)** van junto al modelo dueño. Los nombres de tipo en BD (`name="rol_usuario"`, etc.) no cambian.
- **Listeners de inmutabilidad** se quedan pegados a su modelo, en el `models.py` del módulo, y se copian verbatim con el mismo mensaje y la misma excepción. *Alternativa descartada:* juntarlos en `core/base.py` con una fábrica genérica. Cambia código sin necesidad y separa la regla del modelo que protege. El listener se registra cuando se importa su módulo, y el agregador (D3) garantiza ese import.
- **`PaginacionResponse` y los 3 validadores compartidos** van a `core/schemas.py`. Los validadores pierden el `_` porque ahora se importan entre módulos (`coerce_decimal`, `nombre_no_vacio`, `serialize_money`). Los validadores usados en una sola sección se quedan privados en el `schemas.py` de su módulo. *Alternativa descartada:* un módulo `modules/common`, que mezcla dominio con utilidades.

### D3. Agregador `app/modules/models.py` y orden de imports

```python
from app.core.db import Base
from app.modules.auth import models as auth            # noqa: F401  Usuario
from app.modules.productos import models as productos  # noqa: F401  Producto
from app.modules.distribuidoras import models as distribuidoras  # noqa: F401
from app.modules.clientes import models as clientes    # noqa: F401
from app.modules.stock import models as stock          # noqa: F401
from app.modules.compras import models as compras      # noqa: F401
from app.modules.ventas import models as ventas        # noqa: F401
metadata = Base.metadata
```

El orden sigue las dependencias de FK, de raíces a hojas, y replica el orden de declaración actual para que `sorted_tables` y los nombres de constraints salgan iguales. Como las relaciones son por string, el orden no es estrictamente necesario: solo hace falta que **todos** los modelos estén importados antes del primer `configure_mappers()`. Para eso, `alembic/env.py`, `scripts/init_db.py`, `tests/conftest.py`, `deps.py` (vía `auth.models`) y `main.py` importan el agregador. `main.py` lo importa de forma explícita para que los backrefs existan aunque un router no importe todos los modelos.

Los `models.py` de cada módulo importan modelos de otros módulos solo si los necesitan por tipo. Por eso no hay ciclos: las referencias son strings.

### D4. Shims temporales solo para `app/models.py` y `app/schemas.py`

Durante las fases 1 a 4, `app/models.py` y `app/schemas.py` pasan a ser shims que **reexportan por nombre** desde los módulos, incluidas las tuplas de enums (`test_ventas_modelos` importa `TIPO_MOVIMIENTO`). No se usa `import *`, porque `__all__` actual no incluye las tuplas. Así los ~146 imports de tests y scripts siguen andando mientras se mueve código. Los shims se borran en la fase 5.

**`app/services/*` y `app/routers/*` NO llevan shim.** Los tests hacen `monkeypatch.setattr(modulo, ...)`. Si se parcheara un shim, se reemplazaría el nombre en el shim y no en el módulo real: el test seguiría en verde sin probar nada, o fallaría. Por eso, en la misma fase en que se mueve un service o router, se actualizan sus imports en tests y scripts (búsqueda con grep). *Alternativa descartada:* un shim con `sys.modules[__name__] = real`, que funciona pero es frágil y oscuro.

### D5. Extracción de `service.py` en productos, clientes y distribuidoras (TDD)

Es lo único que cambia código además de moverlo.
- **Va al service:** las consultas y escrituras con `Session` (crear, listar/paginar, buscar, obtener, actualizar, soft-delete, verificar email libre, comparar, ABM de lista de precios).
- **Se queda en el router:** el parseo de query params, `Depends`, el armado de la respuesta HTTP y la traducción de excepciones de dominio a `HTTPException`. El mismo `status_code` y el mismo `detail` que hoy.
- **Contrato:** el service lanza excepciones de dominio propias (por ejemplo `ProductoNoEncontrado`, `SkuDuplicado`, `EmailEnUso`), al estilo de `services/ventas.VentasError`. No conoce HTTP. Las funciones `_to_response` quedan en el router, o como helpers del service si las comparte otro módulo.
- **TDD:** (1) Red de seguridad: los tests HTTP existentes de cada dominio (`test_productos_*`, `test_clientes*`, `test_distribuidoras*`) son la caracterización y tienen que estar en verde antes. (2) RED: `tests/test_<dominio>_service.py` (en la raíz; se mueve a `tests/<dominio>/` en la fase 6) llama a funciones del service que todavía no existen (happy path, not-found, conflicto). (3) GREEN: se mueve la lógica del router al service y el router delega. (4) Triangulación: al menos 2 casos por función. (5) Los tests HTTP sin tocar siguen en verde y prueban que el comportamiento se mantiene.

### D6. Acople clientes → ventas

`_to_venta_resumen` y `to_venta_list_response` pasan de `routers/ventas.py` a `modules/ventas/service.py`. `clientes/router.py` usa `ventas.service`, que ya consume como `ventas_svc`. Así el acople queda entre service y service, y ningún módulo importa el router de otro. La dirección de dependencias permitida es: `clientes → ventas.service/schemas`; `ventas → clientes.models, productos.models, stock.service`; `compras → stock.service, distribuidoras/productos.models`; `reportes → ventas/productos.models, stock.service`; `migracion → productos.schemas/models, distribuidoras.models, stock.service`; `stock → productos.models`.

### D7. Auth (CRITICAL)

`routers/auth.py`, `routers/usuarios.py` y los schemas y el modelo de auth se mueven verbatim. Solo cambian las líneas de import. `core/security.py`, `rate_limit.py` y `refresh_store.py` no se tocan. El diff de auth se revisa con `git diff -M` (detección de renombre), para que se vea como movimiento.

### D8. Tests a `tests/<dominio>/` (fase 6)

Subcarpetas `tests/{auth,productos,stock,distribuidoras,compras,clientes,ventas,reportes,migracion,infra}/`, cada una con `__init__.py`. Así los nombres de módulo de pytest siguen siendo únicos (rootdir con `tests` como paquete). `infra` agrupa health, config, seed, init_db, migration_000x/pg, texto, rate_limit y dev_entorno. `conftest.py`, `alembic_helpers.py` y `*_helpers.py` **se quedan en la raíz de `tests/`**. Los imports absolutos `from tests.x_helpers` siguen andando y el conftest raíz aplica a toda la subcarpeta. Se usa `git mv` para conservar el historial.

### D9. Criterios de verificación (gate de cada fase y final)

1. `python -m pytest -q` en `backend/` en verde, con la misma cantidad de tests que la línea base (más los nuevos de service).
2. `ruff check .` limpio.
3. Al final y después de tocar modelos: `alembic check` no detecta operaciones, contra una BD en `head`.
4. Snapshot de metadata: antes de empezar, un script guarda `[(t.name, sorted(c.name for c in t.c), sorted(str(k) for k in t.constraints)) for t in Base.metadata.sorted_tables]` y la lista de enums en el scratchpad. Al final se compara. Tiene que dar igual.
5. Snapshot de OpenAPI: `create_app().openapi()` serializado antes y después debe dar igual. Valida rutas, orden, schemas y nombres de componentes, y detecta un schema renombrado sin querer.
6. Al cierre: `docker compose up` (migrate + seed_demo + uvicorn) arranca y `/api/health` responde 200.
7. `grep -rn "app\.models\|app\.schemas\|app\.routers\|app\.services" backend/` no devuelve nada fuera de `openspec`.

## Risks / Trade-offs

- [Faltan modelos importados cuando arranca un proceso, y entonces backrefs ausentes o `alembic` sin tablas] → El agregador se importa en `env.py`, `init_db`, `conftest` y `main`, y se verifica con los snapshots de metadata (D9.4).
- [Un `monkeypatch` apunta a un módulo viejo o shim y queda inerte] → No hay shims para services y routers (D4). Al final de cada fase, `grep "setattr("` sobre los módulos movidos.
- [Los nombres de componentes OpenAPI cambian porque Pydantic usa el nombre de clase] → Los nombres de clase no cambian. El snapshot OpenAPI (D9.5) lo detecta.
- [Ciclos de import entre módulos de dominio] → Hay una dirección de dependencias explícita (D6), las relaciones son por string y ningún módulo importa el router de otro.
- [La extracción de service introduce un cambio sutil de comportamiento (orden de commit/flush, mensaje de error)] → Hay TDD de caracterización y los tests HTTP existentes no se tocan durante la extracción.
- [Un commit único y grande es difícil de revisar] → Lo decidió la usuaria. Para mitigarlo se usa `git mv` siempre que se pueda, y `git diff -M --stat` en el resumen final.
- [El árbol sucio de hoy se mezcla con el refactor] → Fase 0: cerrar la línea base antes de crear la rama.

## Migration Plan

Es un refactor interno: no hay despliegue especial ni migración de BD. Rollback: como todo queda en un único commit sobre `change/c-16-modulos`, alcanza con descartar la rama o hacer `git revert` de ese commit. En el entorno local no hay datos que migrar.

## Open Questions

- Si las subcarpetas de tests de la fase 6 se llaman igual que los módulos (recomendado) o se agrupan distinto. No cambia el enfoque.
- Nombres exactos de las excepciones de dominio de los 3 services nuevos. Se fijan en RED.
