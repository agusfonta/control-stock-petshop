# Proposal

## Why

El local arranca con el sistema vacío (enfoque B, arranque limpio) y su catálogo real vive en un Excel desordenado; cargarlo a mano producto por producto es lento y propenso a errores (Flujo 3 del KB, objetivo "migración sin pérdida de catálogo"). Como el Excel real está muy mal hecho, primero construimos el importador contra un **Excel de prueba** con formato limpio y lo hacemos tolerante (alias de encabezados, normalización, dry-run con reporte por fila) para migrar el real más adelante sin reescribir nada.

## What Changes

- Nuevo servicio de importación de productos desde `.xlsx` y `.csv` (`app/services/migracion/`), separado en etapas puras y testeables: lectura → mapeo de columnas por alias (más un mapeo explícito opcional) → normalización (espacios, mayúsculas, `$`, separador de miles, coma decimal, `%`) → validación por fila reutilizando el schema `ProductoCreate` → plan → aplicación.
- **Dry-run obligatorio**: analizar nunca escribe; devuelve un reporte por fila (`ok` / `advertencia` / `error`, con número de fila del Excel, acción `crear`/`actualizar`/`sin_cambios` y motivos).
- **Confirmación todo-o-nada por lote**: si hay al menos un error no se escribe nada; si no, todo el lote se aplica en una sola transacción.
- **Idempotencia por SKU**: re-correr el mismo archivo no duplica productos ni stock (upsert por SKU, comparación sin distinguir mayúsculas).
- Stock inicial registrado como `MovimientoStock` tipo `apertura` vía `aplicar_movimiento()` (nunca editando el saldo directo), solo para productos creados por la importación; en productos existentes el stock del archivo se ignora con advertencia.
- Creación de distribuidoras faltantes (match por nombre sin acentos/mayúsculas) y reutilización de la grafía existente de categorías (la categoría es texto libre en `Producto`).
- Interfaces delgadas sobre el mismo servicio:
  - CLI `python -m scripts.importar_productos <archivo> [--confirmar] [--mapeo m.json]` (camino principal para la migración asistida del Excel real).
  - Endpoint `POST /api/migracion/productos` (multipart, solo dueña, `confirmar=false` por defecto) para que una pantalla futura lo use sin tocar el backend.
- Generador determinístico de Excels de ejemplo (`backend/scripts/generar_excel_prueba.py`) → `docs/ejemplos/productos_prueba.xlsx` (limpio) y `docs/ejemplos/productos_prueba_sucio.xlsx` (con los vicios típicos para ejercitar el dry-run).
- Dependencias nuevas en `backend/requirements.txt`: `openpyxl` (lectura xlsx) y `python-multipart` (upload en FastAPI).

**Fuera de alcance**: pantalla de importación en el frontend (queda como change/tarea posterior; el endpoint ya la habilita), migración del Excel real (se hace después con el mismo importador y, si hace falta, un `mapeo.json`), listas de precios por distribuidora (`ListaPrecio`), importar ventas/clientes/históricos, productos a granel (v2), formato `.xls` viejo.

## Capabilities

### New Capabilities
- `migracion-productos`: importación de catálogo desde planilla (xlsx/csv) con mapeo tolerante de columnas, normalización, dry-run con reporte por fila, confirmación todo-o-nada, upsert idempotente por SKU, stock inicial como movimiento `apertura` y alta de distribuidoras faltantes; expuesta por CLI y endpoint de dueña.

### Modified Capabilities
<!-- Ninguna: el importador respeta los requisitos vigentes de catalogo-productos (RN-PR-01), stock-alertas (RN-ST-03, todo cambio de stock con movimiento) y distribuidoras sin alterarlos. -->

## Impact

- **Código nuevo**: `backend/app/services/migracion/` (paquete), `backend/app/routers/migracion.py`, schemas de reporte en `backend/app/schemas.py`, `backend/scripts/importar_productos.py`, `backend/scripts/generar_excel_prueba.py`, `docs/ejemplos/*.xlsx`, tests `backend/tests/test_migracion_*.py`.
- **Código modificado**: `backend/app/main.py` (registrar router), `backend/requirements.txt` (+2 deps), `README.md` (cómo migrar).
- **Reutiliza sin cambios**: `app/services/stock.aplicar_movimiento` (apertura), `ProductoCreate` (reglas de validación), `app/core/texto.sin_acentos` (comparaciones), `deps.require_duena`.
- **Base de datos**: sin cambios de schema → sin migración Alembic (el tipo `apertura` ya existe en `tipo_movimiento`).
- **Governance**: MEDIUM/HIGH — escribe catálogo, precios (vía costo/margen) y stock de la usuaria; el design marca las decisiones no obvias para revisión antes del apply.
