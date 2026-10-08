# Control Stock Petshop (Animall)

Sistema de control de stock y punto de venta (POS) de mostrador para el petshop Animall: catálogo de productos, stock con alertas de mínimo, ventas con cobro en efectivo / transferencia / tarjeta, clientes, distribuidoras, pedidos de reposición y reportes.

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic, JWT (python-jose) + bcrypt.
- **Base de datos:** PostgreSQL 16 (Docker) o SQLite (solo desarrollo sin Docker). **Redis 7** (Docker) o `memory://` (solo desarrollo).
- **Frontend:** React 19 + TypeScript + Vite + Tailwind 4 + shadcn/ui.

> **Pendiente:** la facturación electrónica (ARCA) y los cobros con Mercado Pago todavía no están implementados; el comprobante que imprime el POS no es válido como factura.

## Cómo correr

### Requisitos

| Herramienta | Versión | Para qué |
|---|---|---|
| Docker Desktop | reciente (con Compose v2) | Opción A (opcional) |
| Python | 3.12 | Opción B (backend sin Docker) |
| Node.js | 24 (CI) o 22 (imagen Docker) | Opción B (frontend sin Docker) y tests |

### Opción A: con Docker (recomendada)

Desde la raíz del repo:

```bash
docker compose up --build
```

Levanta cuatro servicios:

| Servicio | Qué es | Puerto en tu máquina |
|---|---|---|
| `db` | PostgreSQL 16 (usuario/clave/base `petshop`) | **5433** (no 5432, para no chocar con un Postgres instalado en el sistema) |
| `redis` | Redis 7 | solo interno |
| `api` | FastAPI con recarga automática | 8000 |
| `frontend` | Vite dev server (`npm ci && npm run dev`) | 5173 |

Al arrancar, `api` ejecuta solo `alembic upgrade head` y el seed demo (idempotente: si ya está cargado no duplica nada). El `frontend` espera a que `api` esté sana.

- App: http://localhost:5173
- API (Swagger): http://localhost:8000/docs

La primera vez tarda unos minutos (build de la imagen y `npm ci`). Código de `backend/` y `frontend/` está montado como volumen: los cambios se recargan solos.

Parar y reiniciar:

```bash
docker compose down        # frena los servicios, conserva los datos
docker compose down -v     # frena y BORRA los datos (base y Redis): el próximo up vuelve a sembrar el demo
```

### Opción B: sin Docker (Windows PowerShell)

Usa SQLite y un Redis en memoria; no hace falta instalar PostgreSQL ni Redis. Desde la raíz del repo:

```powershell
# 1) Backend: entorno virtual y dependencias
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt -r backend/requirements-dev.txt   # -dev solo hace falta para tests y lint

# 2) Variables de entorno (valores de prueba SOLO para desarrollo local; nunca usarlos en producción)
$env:ENV = "dev"
$env:DATABASE_URL = "sqlite:///./dev.db"
$env:REDIS_URL = "memory://"
$env:CORS_ORIGINS = "http://localhost:5173"
$env:SEED_OWNER_PASSWORD = "demo-duena-2026"
$env:SEED_MOSTRADOR_PASSWORD = "demo-mostrador-2026"

# 3) Crear tablas, cargar el demo y arrancar la API (desde backend/)
cd backend
python -m scripts.init_db
python -m scripts.seed_demo
python -m uvicorn app.main:app --reload --port 8000
```

En **otra** terminal PowerShell:

```powershell
cd frontend
npm install
npm run dev
```

Abrí http://localhost:5173 (la API queda en http://localhost:8000/docs). El frontend proxea `/api` a `http://localhost:8000` (se cambia con `VITE_PROXY_TARGET`).

Notas:

- Las variables `$env:` valen solo para esa ventana de PowerShell: si abrís otra, volvé a definirlas.
- `sqlite:///./dev.db` es relativo a la carpeta desde la que se ejecuta, por eso todo se corre desde `backend/`. Para **reiniciar los datos**, frená uvicorn, borrá `backend/dev.db` y repetí `init_db` + `seed_demo`.
- `init_db` y `seed_demo` son idempotentes: correrlos de nuevo sobre una base ya cargada no duplica nada. Si `seed_demo` se interrumpió a mitad de camino, borrá la base y volvé a correrlo.

### Usuarios de demostración

| Rol | Email | Contraseña (solo demo) |
|---|---|---|
| Dueña | `duena@petshop.local` | `demo-duena-2026` |
| Mostrador | `mostrador@petshop.local` | `demo-mostrador-2026` |

> Son valores de prueba **exclusivos para desarrollo local**. Las contraseñas no están en el código: el seed las lee de `SEED_OWNER_PASSWORD` y `SEED_MOSTRADOR_PASSWORD` (en Docker están definidas en `docker-compose.yml`, servicio `api`; sin Docker, las del paso 2 de arriba). El seed se niega a correr si `ENV` no es `dev` o `test`, así que estos usuarios nunca se crean en un entorno real. No las reutilices en producción.

La dueña accede a todo (costos, márgenes, pagos a distribuidoras, anulaciones, reportes completos); el mostrador vende, consulta stock, crea clientes y arma/recibe pedidos, pero no ve costos ni puede anular ventas.

### Qué datos trae el seed

- 19 productos activos en 7 categorías (alimentos, snacks, higiene, juguetes, accesorios, farmacia, cuchas), con algunos bajo el stock mínimo y uno sin stock, para ver las alertas.
- 4 distribuidoras con listas de precios superpuestas (25 precios, para probar el comparador).
- 8 clientes.
- 2 pedidos de reposición: uno ya recibido y uno pendiente.
- 17 ventas repartidas en los últimos 7 días (incluye hoy), con pagos en efectivo, transferencia, tarjeta y pagos divididos; una de ellas anulada. Así los 4 reportes tienen datos.

### Migrar catálogo desde Excel

Carga productos, costos, márgenes, stock inicial y distribuidoras desde una planilla `.xlsx` o `.csv` (hasta 5 MB y 5000 filas). **Siempre analiza primero:** sin `--confirmar` no se escribe nada. Desde `backend/`, con el mismo entorno de la Opción B y la base inicializada (`init_db`) con una dueña activa:

```powershell
# 1) Generar las planillas de ejemplo (limpia y sucia) en docs/ejemplos/
python -m scripts.generar_excel_prueba

# 2) Analizar (dry-run): imprime resumen y las filas con advertencia o error; no escribe
python -m scripts.importar_productos ../docs/ejemplos/productos_prueba.xlsx

# 3) Aplicar, solo si el análisis no tiene errores
python -m scripts.importar_productos ../docs/ejemplos/productos_prueba.xlsx --confirmar
```

Opciones: `--mapeo '{"costo": "Valor compra"}'` (JSON o ruta a un `mapeo.json`; gana sobre el reconocimiento automático de encabezados), `--hoja <nombre>` (por defecto la primera) y `--usuario <email>` (por defecto, la única dueña activa). Códigos de salida: `0` sin errores, `1` errores de datos, `2` uso inválido.

Cómo se comporta:

- **Todo o nada:** una sola fila con error bloquea toda la confirmación; se corrige el archivo y se vuelve a correr. Las advertencias no bloquean.
- **Idempotente por SKU** (sin distinguir mayúsculas): un SKU nuevo crea el producto; uno existente solo se actualiza con las celdas que traen dato (las vacías no borran nada) y, si no cambia nada, queda `sin_cambios`. Un SKU de un producto dado de baja es error. Re-importar el mismo archivo no duplica nada.
- **Stock inicial** solo para productos nuevos, como movimiento de `apertura` (queda trazado con el id de lote). En productos existentes el stock de la planilla se ignora y la fila avisa: para corregirlo usá un ajuste de stock.
- **Margen en puntos porcentuales** (`35` o `35%` = 0,35). Si falta el margen pero hay precio de venta, se deriva con advertencia.
- Las distribuidoras que no existen se crean (una sola vez por nombre); la categoría reutiliza la grafía que ya tenga el catálogo.
- Cambiar `costo` o `margen` de un producto existente cambia su precio de venta: el reporte lista los campos que cambian antes de confirmar.

Por API (solo rol dueña): `POST /api/migracion/productos`, multipart con `archivo`, y opcionales `confirmar` (por defecto `false` = análisis), `mapeo` (JSON) y `hoja`. Responde `200` con el reporte por fila; confirmar con errores devuelve `422` con el reporte y sin escrituras; `415` formato no admitido, `413` más de 5 MB, `409` si el catálogo cambió durante la confirmación. Hoy no hay pantalla: se usa desde `/docs` o con el CLI.

### Tests

```bash
# Backend (desde backend/, con el venv activo)
cd backend
pytest -q
ruff check .   # lint
```

La suite completa tarda unos 2 minutos: el hash bcrypt es lento a propósito, pero `tests/conftest.py` fija `BCRYPT_ROUNDS=4` (el mínimo de bcrypt) para que los tests no paguen el costo de producción. Los tests marcados `pg_only` necesitan una base PostgreSQL accesible por la variable `TEST_PG_URL` y se omiten si no está definida; en CI corren contra un servicio Postgres.

```bash
# Frontend (desde frontend/)
cd frontend
npm test            # vitest, una sola corrida
npm run build       # chequeo de tipos (tsc estricto) + build de producción
npm run knip        # detecta código, exports y dependencias sin uso
```

### Costo del hash de contraseñas (`BCRYPT_ROUNDS`)

Variable de entorno opcional que define el costo (rounds) de bcrypt al hashear contraseñas. Por defecto vale **12**; se acepta entre 4 y 31. Fuera de `ENV=dev` y `ENV=test` el valor mínimo es 12: con un valor menor la API se niega a arrancar. La suite de tests la baja a 4 por sí sola; no hace falta definirla para desarrollar.

### Problemas comunes

- **Puerto 8000 o 5173 ocupado:** cerrá el proceso que lo usa (probablemente otro `uvicorn` o `vite` viejo) y reintentá. Si cambiás el puerto de la API, ajustá `VITE_PROXY_TARGET` del frontend.
- **Postgres del sistema:** el Postgres instalado en tu máquina (por ejemplo la versión 17) no se usa. El de Docker se publica en el puerto **5433** justamente para no pisarlo; para conectarte con un cliente SQL usá `postgresql://petshop:petshop@localhost:5433/petshop`.
- **`REDIS_URL=memory://`** (Redis en memoria) solo se acepta con `ENV=dev` o `ENV=test`; en cualquier otro entorno la API se niega a arrancar. Tampoco hay datos compartidos entre procesos ni persistencia.
- **`seed_demo` dice "Faltan variables de entorno":** definí `SEED_OWNER_PASSWORD` y `SEED_MOSTRADOR_PASSWORD` en la misma terminal (no hay valores por defecto).
- **Cerrar sesión:** el backend todavía no tiene un endpoint de logout; el frontend cierra la sesión borrando el token local y la pista de sesión.
- **Cambios en archivos no se reflejan en Docker sobre Windows:** el frontend ya usa polling (`VITE_USE_POLLING=true`); si aún así no recarga, reiniciá el servicio con `docker compose restart frontend`.

## Estructura del proyecto

### La app

```
backend/            API FastAPI (app/), migraciones (alembic/), scripts (scripts/: init_db, seed, seed_demo, importar_productos, generar_excel_prueba), tests/
frontend/           App React + TypeScript (src/), tests con Vitest
docker-compose.yml  Entorno local completo (db, redis, api, frontend)
```

### Herramientas del agente

No son parte del producto: documentan el dominio y guían el trabajo asistido por agentes (flujo OPSX).

```
CLAUDE.md           Instrucciones para agentes (AGENTS.md solo remite a este archivo)
openspec/           Specs y changes: openspec/specs/ (fuente de verdad) y openspec/changes/
CHANGES.md          Roadmap de changes, dependencias y camino crítico
knowledge-base/     Base de conocimiento: visión, reglas de negocio, modelo de datos, arquitectura
discovery/          Investigación de mercado previa
.atl/               Estado local de los agentes (no versionado)
```

Para entender el dominio, empezá por [`knowledge-base/README.md`](knowledge-base/README.md); para ver qué está hecho y qué falta, por [`CHANGES.md`](CHANGES.md).
