# Design

## Context

Ver `proposal.md` (Why). Estado actual relevante (observado en el código):

- `Producto` (`app/models.py`): `sku` único **case-sensitive**, `categoria`/`marca` texto libre (no hay entidad Categoría), `costo Numeric(10,2)`, `margen_pct Numeric(5,4)` como **fracción** (0.35 = 35%, máx. 9.9999), `stock_actual` con check ≥ 0, `distribuidora_default_id` FK nullable. `precio_venta` es `column_property` (RN-PR-01): no se escribe nunca.
- `Distribuidora.nombre` **no es único** en la base (puede haber homónimos).
- `app/services/stock.aplicar_movimiento()` es el núcleo sin commit (lock `FOR UPDATE` salvo SQLite) que ya usan compras, ventas y `seed_demo` para el tipo `apertura`; el enum `tipo_movimiento` ya incluye `apertura` → no hace falta migración.
- `ProductoCreate` (`app/schemas.py`) concentra las reglas de alta (SKU_PATTERN, longitudes, costo > 0, margen ≥ 0, stock ≥ 0) con `strict=True` y `_coerce_decimal`.
- `app/core/texto.sin_acentos()` ya pliega acentos/mayúsculas/espacios.
- `data/plantilla_productos.csv` (C-01) tiene headers `sku,nombre,categoria,costo,margen_pct,stock_actual,stock_minimo,distribuidora` con margen en puntos porcentuales (`35`).
- `openpyxl 3.1.5` y `python-multipart 0.0.20` están instalados en el entorno local pero **no** en `backend/requirements.txt`.
- Tests: SQLite en memoria (`conftest.db_session_factory`), cliente httpx async con `seed_users` (dueña/mostrador); tests `pg_only` para Postgres real.

## Goals / Non-Goals

**Goals:**
- Un único núcleo de importación que sirva igual a CLI y endpoint (las interfaces solo traducen entrada/salida).
- Etapas puras (lectura, columnas, normalización) testeables sin base; la base solo en análisis (lecturas) y aplicación (escrituras).
- Reutilizar reglas existentes (ProductoCreate, aplicar_movimiento, sin_acentos) en vez de duplicarlas.
- Que migrar el Excel real más adelante sea, en el peor caso, escribir un `mapeo.json` o sumar alias.

**Non-Goals:**
- Persistir historial de importaciones (tabla de lotes): la trazabilidad es el `ref_id` del movimiento de apertura + el reporte devuelto.
- Guardar el archivo subido entre dry-run y confirmación (el flujo es stateless: se re-sube).
- Corregir el alta manual `POST /api/productos`, que hoy acepta `stock_actual` sin movimiento (ver Riesgos).
- Pantalla de frontend.

## Decisions

### D1 — Interfaces: CLI + endpoint delgados sobre un servicio
Se implementan ambos, pero son adaptadores finos (≈50–80 líneas cada uno) sobre `importar(db, contenido, nombre_archivo, usuario, *, confirmar, mapeo, hoja)`.
- **CLI** es el camino real para migrar el Excel desordenado: lo corre quien asiste a la dueña, itera dry-runs y ajusta `mapeo.json` sin depender de UI.
- **Endpoint** porque `CHANGES.md` lo define en el alcance de C-08 y deja lista la futura pantalla (subir → ver reporte → confirmar) sin tocar backend.
- *Alternativas*: solo CLI (más chico, pero obliga a un change de backend para la UI); solo endpoint (la migración asistida queda atada a curl/UI). El costo marginal del segundo adaptador es bajo porque toda la lógica está en el servicio.

### D2 — Estructura del paquete `app/services/migracion/`
| Módulo | Responsabilidad | Base |
|---|---|---|
| `lectura.py` | bytes + nombre → `Planilla` (encabezados, filas crudas con número de fila real, flags por celda: `es_porcentaje`, `formula_sin_valor`) | no |
| `columnas.py` | `ALIAS` por campo canónico + mapeo explícito → índice campo→columna, ignoradas, errores globales | no |
| `normalizar.py` | `decimal_ar`, `entero`, `margen`, `sku`, `texto`, `clave` (= `sin_acentos`) | no |
| `analisis.py` | filas crudas → `Plan` (filas normalizadas, acción, motivos) usando una foto de la base | lee |
| `aplicar.py` | `Plan` → escrituras en una transacción | escribe |
| `__init__.py` | `importar()` orquesta y arma el `ReporteImportacion`; excepciones `ArchivoNoAdmitido`, `ArchivoDemasiadoGrande`, `CatalogoCambio` | — |

Los modelos del reporte (`ReporteImportacion`, `FilaReporte`, `MotivoReporte`, `TotalesImportacion`, `ColumnasReporte`, `MapeoColumnas`) van en `app/schemas.py` con `extra="forbid", strict=True` (regla dura). El `Plan` interno son dataclasses congeladas (no cruza el borde HTTP).

### D3 — Dry-run = análisis puro; confirmar = re-analizar + aplicar
El análisis nunca escribe ni toma locks: hace una foto de la base (productos indexados por `upper(sku)`, distribuidoras por `clave(nombre)`, categorías distintas por `clave`) y decide la acción de cada fila. Confirmar vuelve a analizar **el archivo recibido** y, sin errores, aplica.
- *Alternativa descartada*: ejecutar todo y hacer rollback en dry-run (garantiza fidelidad pero toma locks `FOR UPDATE` y ensucia secuencias). La fidelidad se cubre con tests que comparan el reporte del dry-run con el resultado de la confirmación.
- *Alternativa descartada*: dry-run que guarda un token/plan para confirmar después: requiere persistencia o caché y expiración; re-subir el archivo es trivial y siempre consistente.

### D4 — Todo-o-nada por lote (⚠ revisar)
Una fila con `error` (o un error global) bloquea la confirmación completa; sin errores se aplica todo en **una** transacción y cualquier excepción hace rollback total.
- *Por qué no fila por fila*: con dry-run obligatorio la usuaria ya ve todos los problemas antes; una importación parcial deja el catálogo a medias, complica razonar sobre la re-ejecución y mezcla productos migrados con faltantes en las alertas de stock. "Corregir el archivo y volver a correr" es simple gracias a la idempotencia (D5).
- Tamaño: catálogo esperado 1–3 mil filas, tope 5000 → una transacción es razonable.
- Las **advertencias no bloquean**.

### D5 — Upsert idempotente por SKU (⚠ revisar)
- Búsqueda por `upper(sku)`. Si hay dos productos que difieren solo en mayúsculas → `error` ambiguo.
- **Nuevo**: se crea con SKU normalizado (mayúsculas) y `stock_actual=0`; luego apertura (D6).
- **Existente activo**: se actualizan solo los campos con celda **no vacía**; si ningún valor cambia → `sin_cambios`. Cambiar `costo`/`margen_pct` cambia el precio de venta (RN-PR-01): el reporte lista los campos que cambian para que la dueña lo vea antes de confirmar.
- **Existente dado de baja** → `error` (no se reactiva en silencio; la dueña decide).
- Comparación con valores cuantizados (`costo` 0.01, `margen` 0.0001) para que re-importar no genere falsos `actualizar`.

### D6 — Stock inicial solo para productos nuevos, vía `aplicar_movimiento` (⚠ revisar)
Por cada producto **creado** con stock > 0: `aplicar_movimiento(db, id, stock, "apertura", usuario, motivo="Migración inicial: <archivo>", ref_id=lote_id)` dentro de la misma transacción (el servicio no hace commit; lo hace `aplicar.py` al final). En productos existentes el stock de la planilla se **ignora** (advertencia si difiere): pisarlo sería un ajuste encubierto y rompería la idempotencia; para eso está el ajuste auditable de C-05.
- *Alternativa descartada*: llevar el stock al valor de la planilla con un movimiento de `ajuste` por la diferencia → re-importar un archivo viejo después de vender revertiría ventas.
- `lote_id` = UUID4 generado al confirmar (cabe en `ref_id String(36)`).

### D7 — Normalización argentina y margen en puntos porcentuales (⚠ revisar)
- Números: quitar `$`, `ARS`, espacios y NBSP. Si hay `.` y `,`, el último es el decimal. Solo `,` → decimal. Solo `.`: si matchea `^\d{1,3}(\.\d{3})+$` es separador de miles (`18.500` → 18500, con advertencia si es ambiguo como `1.500`); si no, decimal (`18.5`). Valores numéricos nativos de xlsx se convierten con `Decimal(str(v))`; enteros sin `.0`.
- Margen: en la planilla se expresa en **puntos porcentuales** (como la plantilla C-01: `35`) → ÷100. Excepción: celda xlsx con `number_format` que contiene `%` → el valor ya es fracción. Margen < 0.01 resultante → advertencia "¿quisiste decir X%?". Margen > 9.9999 (límite de la columna) → error.
- Margen faltante: derivar de `precio_venta` (`precio/costo − 1`, cuantizado a 4 decimales, advertencia porque el precio final puede diferir en centavos); si tampoco hay precio → 0 con advertencia. Si hay ambos y difieren más de 1% → advertencia, gana el margen.
- SKU: `strip`, mayúsculas, espacios internos → `-` (advertencia). SKU vacío → error (sin SKU no hay upsert idempotente).
- Textos: `strip` + colapsar espacios. `unidad` se mapea por `clave` a `unidad`/`bolsa`/`caja`; vacía → `unidad`.

### D8 — Validación reutilizando `ProductoCreate`
Tras normalizar, cada fila se valida con `ProductoCreate.model_validate({...})` (con `stock_actual=0`, `distribuidora_default_id=None`): las reglas de SKU, longitudes y rangos quedan en un solo lugar. Los `ValidationError` se traducen a motivos en castellano por `type` de Pydantic (`string_pattern_mismatch`, `greater_than`, `string_too_long`, …) con fallback al mensaje original. Las reglas propias de la importación (duplicados en archivo, decimales en stock, fórmulas, distribuidora ambigua, SKU dado de baja) viven en `analisis.py`.

### D9 — Distribuidoras y categorías
- Distribuidora: match por `clave(nombre)` contra **todas** las distribuidoras. 1 activa → se usa; 0 → se planifica crear (una por clave, con la grafía de la primera aparición); >1 o solo inactiva → `error` de fila. Se crean en `aplicar.py` antes de los productos (`flush` para obtener ids).
- Categoría: no hay tabla; "crear" = usar el texto. Se reutiliza la grafía existente en `productos.categoria` con la misma `clave`; si no hay, la primera grafía del archivo (así `ALIMENTOS` y `Alimentos` no conviven).
- `ListaPrecio` no se toca (non-goal; C-06 la gestiona).

### D10 — Lectura de archivos
- `.xlsx`: `openpyxl.load_workbook(BytesIO, read_only=True, data_only=True)`. Para detectar fórmulas sin valor guardado se carga una segunda vez con `data_only=False` solo si hay celdas obligatorias vacías (el valor `None` no distingue "vacía" de "fórmula sin caché"). Hoja: la primera o `hoja` explícita (inexistente → error global).
- `.csv`: decodificar `utf-8-sig`, fallback `cp1252`; separador `;` si el encabezado tiene más `;` que `,`.
- Número de fila = fila real de Excel (1-based, encabezado incluido); filas totalmente vacías se saltean.
- Límites: 5 MB (el router lee `limite+1` bytes y corta → 413) y 5000 filas de datos (error global). Otras extensiones (`.xls`, `.xlsm`, `.pdf`…) → `ArchivoNoAdmitido` (415).

### D11 — Contrato HTTP y CLI
- `POST /api/migracion/productos`, `Depends(deps.require_duena)`, multipart `archivo: UploadFile`, `confirmar: bool = Form(False)`, `mapeo: str | None = Form(None)` (JSON validado con `MapeoColumnas`; inválido → 422). Respuestas según spec; `CatalogoCambio` (IntegrityError por SKU creado en paralelo) → `409` sin escrituras.
- CLI `backend/scripts/importar_productos.py` con `argparse`, sesión vía `app.core.db` como los scripts de seed, imprime resumen + filas no-ok; códigos 0/1/2.
- Generador `backend/scripts/generar_excel_prueba.py --salida <dir>` (default `docs/ejemplos/`), datos fijos en el módulo, `wb.properties.created/modified` fijos.

## Risks / Trade-offs

- [El Excel real tiene formas no previstas (celdas combinadas, varias hojas, encabezado en fila 3 tras un título, sin SKU)] → la detección de encabezado toma la primera fila no vacía; casos fuera de eso se resuelven al migrar el real (alias nuevos, `--hoja`, o un change acotado). El dry-run evita escrituras malas.
- [`1.500` ambiguo (¿1500 o 1,5?)] → se asume convención argentina (miles) con advertencia visible en el reporte.
- [Upper-case de SKU nuevos distinto de SKUs cargados a mano en minúsculas] → el match es case-insensitive, no se duplican; solo cambia la grafía de los nuevos.
- [Actualizar costo/margen de productos existentes cambia precios de venta] → solo celdas no vacías, el reporte lista campos cambiados y la confirmación es explícita.
- [Transacción grande con 5000 filas + `FOR UPDATE` en Postgres] → los locks son sobre filas recién creadas; volumen esperado 1–3 mil; test `pg_only` de confirmación.
- [Hallazgo fuera de alcance: `POST /api/productos` acepta `stock_actual>0` sin crear movimiento (contradice RN-ST-03)] → no se toca aquí; se reporta para un fix aparte.
- [openpyxl y archivos maliciosos (zip bomb)] → tope de 5 MB, `read_only=True`, sin ejecutar macros (no se aceptan `.xlsm`).

## Migration Plan

Sin migración de base. Deploy = nuevas dependencias en `requirements.txt` + router registrado. Rollback = quitar el router; los datos importados son productos/movimientos normales (los movimientos de apertura se identifican por `ref_id` = lote si hiciera falta auditarlos).

## Open Questions

Diferibles hasta migrar el Excel real (no cambian specs ni tareas de este change):
- Si el Excel real no tiene SKU: ¿se generan SKUs determinísticos desde el nombre o se completan a mano? (hoy: error por fila).
- Si trae precio de venta y no margen: confirmar que derivar el margen (D7) es lo que la dueña espera.
- Si está repartido en varias hojas (una por categoría/distribuidora): hoy se corre una vez por hoja con `--hoja`.
