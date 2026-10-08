# Spec Delta

## Purpose

Permitir a la dueña cargar su catálogo inicial (productos, costos, márgenes, stock y distribuidoras) desde una planilla Excel o CSV de forma segura: primero se previsualiza un reporte por fila sin escribir nada y solo después se confirma, sin duplicar datos si se repite la importación.

## ADDED Requirements

### Requirement: Formatos de planilla admitidos

The system SHALL aceptar planillas `.xlsx` (primera hoja salvo que se indique otra) y `.csv` (separador `,` o `;`, codificación UTF-8 con o sin BOM, o Windows-1252). La fila de encabezados SHALL ser la primera fila no vacía. Las filas completamente vacías SHALL ignorarse sin reportarse como error. El system SHALL rechazar otros formatos y archivos que superen 5 MB o 5000 filas de datos con un error global, sin analizar filas. Para celdas con fórmula SHALL usarse el valor calculado guardado; si no lo hay, la fila SHALL reportarse con error en esa columna.

#### Scenario: Importar xlsx de prueba limpio
- **WHEN** se analiza `docs/ejemplos/productos_prueba.xlsx`
- **THEN** todas sus filas de datos se reportan `ok` con acción `crear` y no hay errores globales

#### Scenario: CSV con punto y coma en Windows-1252
- **WHEN** se analiza un `.csv` separado por `;` y codificado en Windows-1252 con nombres acentuados
- **THEN** las columnas se detectan y los nombres se leen con sus acentos correctos

#### Scenario: Formato no admitido
- **WHEN** se analiza un archivo `.xls` o `.pdf`
- **THEN** el reporte trae un error global de formato no admitido y ninguna fila analizada

#### Scenario: Filas vacías intercaladas
- **WHEN** la planilla tiene filas totalmente vacías entre productos
- **THEN** esas filas no aparecen en el reporte y las demás conservan su número de fila real del Excel

#### Scenario: Fórmula sin valor calculado
- **WHEN** la celda de costo es una fórmula sin valor guardado
- **THEN** esa fila se reporta `error` indicando que se abra y guarde el archivo en Excel

### Requirement: Mapeo tolerante de columnas

The system SHALL reconocer cada campo canónico (`sku`, `nombre`, `categoria`, `marca`, `distribuidora`, `costo`, `margen_pct`, `precio_venta`, `stock_inicial`, `stock_minimo`, `unidad`) por una lista de alias de encabezado comparados sin acentos, sin mayúsculas, ignorando espacios repetidos, `_`, `-`, `.` y `%` (por ejemplo "Código", "Precio Costo", "Proveedor", "Stock actual"). SHALL aceptar además un mapeo explícito `{campo: encabezado}` que tiene prioridad sobre los alias. `sku`, `nombre` y `costo` son obligatorios: si falta alguno, o si dos encabezados mapean al mismo campo, el reporte SHALL traer un error global y ninguna fila analizada. Las columnas no reconocidas SHALL listarse como ignoradas sin bloquear.

#### Scenario: Encabezados con alias y acentos
- **WHEN** la planilla tiene encabezados `Código`, `Descripción`, `Proveedor`, `Precio Costo`, `Ganancia %`, `Stock`
- **THEN** se mapean a `sku`, `nombre`, `distribuidora`, `costo`, `margen_pct`, `stock_inicial`

#### Scenario: Plantilla canónica del proyecto
- **WHEN** se analiza `data/plantilla_productos.csv`
- **THEN** `stock_actual` se mapea a `stock_inicial` y sus 3 filas se reportan `ok`

#### Scenario: Falta columna obligatoria
- **WHEN** la planilla no tiene ninguna columna reconocible como costo
- **THEN** el reporte trae un error global "falta columna obligatoria: costo" y ninguna fila

#### Scenario: Mapeo explícito
- **WHEN** se pasa el mapeo `{"costo": "Valor compra"}` y la planilla tiene esa columna
- **THEN** `Valor compra` se usa como costo aunque no sea un alias conocido

#### Scenario: Columna desconocida
- **WHEN** la planilla tiene una columna `Observaciones`
- **THEN** el reporte la lista como ignorada y las filas se analizan igual

### Requirement: Normalización de valores

The system SHALL normalizar antes de validar: recortar y colapsar espacios en textos; SKU sin espacios extremos, en mayúsculas y con espacios internos reemplazados por `-` (con advertencia si hubo reemplazo); números en formato argentino (`$`, espacios, `.` de miles, `,` decimal, por ejemplo `$ 18.500,50` = 18500.50); números enteros provenientes de Excel sin sufijo `.0`. El margen SHALL interpretarse en puntos porcentuales (`35`, `35%`, `35,5`) y convertirse a fracción (0.35); una celda xlsx con formato porcentaje SHALL tomarse como fracción directa. Un margen menor a 1% SHALL generar advertencia. Un valor `1.500` sin decimales SHALL interpretarse como miles (1500) con advertencia.

#### Scenario: Costo con signo pesos y miles
- **WHEN** la celda de costo dice `$ 18.500,50`
- **THEN** el costo normalizado es 18500.50

#### Scenario: Margen en puntos porcentuales
- **WHEN** la celda de margen dice `35%` o `35`
- **THEN** el margen guardado es 0.35 y el precio de venta resultante es costo × 1.35

#### Scenario: Margen en celda con formato porcentaje
- **WHEN** una celda xlsx con formato `0%` vale 0.35
- **THEN** el margen guardado es 0.35

#### Scenario: Margen sospechosamente bajo
- **WHEN** la celda de margen (sin formato porcentaje) dice `0,35`
- **THEN** la fila se reporta `advertencia` preguntando si quiso decir 35%

#### Scenario: SKU numérico de Excel
- **WHEN** la celda SKU contiene el número 7790001234567
- **THEN** el SKU normalizado es `7790001234567` (sin `.0` ni notación científica)

### Requirement: Validación por fila con reporte

The system SHALL validar cada fila con las mismas reglas que el alta de productos (SKU con formato válido, nombre no vacío, costo > 0, margen ≥ 0, stock inicial y mínimo enteros ≥ 0, unidad `unidad`/`bolsa`/`caja` o vacía = `unidad`) y SHALL devolver por cada fila de datos: número de fila del Excel (contando el encabezado), SKU normalizado, estado `ok` / `advertencia` / `error`, acción prevista (`crear`, `actualizar`, `sin_cambios`, o ninguna si hay error) y la lista de motivos (campo y mensaje en castellano). El reporte SHALL incluir totales por estado y por acción, distribuidoras a crear y unidades de stock de apertura. Si falta el margen pero hay precio de venta, el margen SHALL derivarse como `precio_venta / costo − 1` con advertencia; si faltan ambos, el margen es 0 con advertencia. Un SKU repetido dentro del mismo archivo SHALL marcar `error` en todas sus apariciones, citando las otras filas.

#### Scenario: Costo cero o vacío
- **WHEN** una fila tiene costo `0` o vacío
- **THEN** esa fila se reporta `error` con motivo en el campo `costo` y su número de fila

#### Scenario: Stock con decimales
- **WHEN** una fila tiene stock inicial `2,5`
- **THEN** esa fila se reporta `error` (solo se admiten unidades enteras en v1)

#### Scenario: SKU duplicado en el archivo
- **WHEN** las filas 4 y 9 tienen el mismo SKU
- **THEN** ambas se reportan `error` y cada una menciona la otra fila

#### Scenario: Margen derivado del precio de venta
- **WHEN** una fila no tiene margen pero tiene costo 1000 y precio de venta 1350
- **THEN** la fila es `advertencia` con margen derivado 0.35

#### Scenario: Precio de venta menor al costo
- **WHEN** una fila sin margen tiene precio de venta menor al costo
- **THEN** la fila se reporta `error` (margen negativo)

### Requirement: Dry-run sin escritura

The system SHALL ofrecer un modo de análisis (dry-run), que es el modo por defecto de todas las interfaces, que produce el reporte completo sin crear, modificar ni bloquear ningún producto, movimiento ni distribuidora.

#### Scenario: Analizar no escribe
- **WHEN** se analiza una planilla válida con 10 productos nuevos sin confirmar
- **THEN** la cantidad de productos, movimientos de stock y distribuidoras en la base no cambia y el reporte indica 10 a crear

### Requirement: Confirmación todo-o-nada por lote

The system SHALL aplicar una importación confirmada en una única transacción: si el análisis tiene al menos una fila `error` o un error global, SHALL rechazar la confirmación sin escribir nada y devolver el reporte; si no, SHALL aplicar todas las filas (`ok` y `advertencia`) o, ante cualquier falla durante la aplicación, ninguna. La confirmación SHALL re-analizar el archivo recibido (no reutiliza un análisis previo) y devolver el reporte con un identificador de lote.

#### Scenario: Confirmar con errores
- **WHEN** se confirma una planilla con 20 filas válidas y 1 con costo inválido
- **THEN** no se crea ningún producto ni movimiento y el reporte señala la fila con error

#### Scenario: Falla a mitad de la aplicación
- **WHEN** la base rechaza la escritura de un producto durante una importación confirmada
- **THEN** ningún producto, movimiento ni distribuidora del lote queda persistido

#### Scenario: Confirmar con solo advertencias
- **WHEN** se confirma una planilla cuyas filas son `ok` o `advertencia`
- **THEN** se aplican todas y el reporte trae el identificador de lote

### Requirement: Upsert idempotente por SKU

The system SHALL identificar productos por SKU sin distinguir mayúsculas. Un SKU inexistente SHALL crear el producto. Un SKU de un producto activo SHALL actualizar `nombre`, `categoria`, `marca`, `costo`, `margen_pct`, `stock_minimo`, `unidad` y distribuidora por defecto solo con los valores presentes en la fila (celdas vacías no borran datos), reportando `actualizar` con los campos que cambian, o `sin_cambios` si no cambia nada; el precio de venta se recalcula solo (RN-PR-01). Un SKU de un producto dado de baja SHALL reportarse `error`. Re-confirmar el mismo archivo SHALL dejar la base igual que tras la primera confirmación.

#### Scenario: Re-importar el mismo archivo
- **WHEN** se confirma dos veces la misma planilla válida
- **THEN** la segunda vez todas las filas son `sin_cambios` y no se crean productos, movimientos ni distribuidoras nuevas

#### Scenario: Actualizar costo de producto existente
- **WHEN** se confirma una fila cuyo SKU existe con costo 1000 y la fila trae costo 1200
- **THEN** el producto queda con costo 1200, su precio de venta se recalcula y la fila reportó `actualizar` con el campo `costo`

#### Scenario: SKU en distinta caja
- **WHEN** existe el producto `bal-adu-15` y la planilla trae `BAL-ADU-15`
- **THEN** se trata como el mismo producto y no se crea uno nuevo

#### Scenario: SKU de producto dado de baja
- **WHEN** la planilla trae el SKU de un producto con `activo=false`
- **THEN** la fila se reporta `error` indicando que el producto está dado de baja

### Requirement: Stock inicial como movimiento de apertura

The system SHALL registrar el stock inicial de cada producto creado por la importación mediante un `MovimientoStock` tipo `apertura` (cantidad = stock inicial, `stock_previo` 0, usuario que confirma, `ref_id` = identificador de lote), en la misma transacción que el producto; nunca SHALL asignar `stock_actual` sin su movimiento. Un stock inicial vacío o 0 no genera movimiento. Para productos existentes el stock de la planilla SHALL ignorarse y, si difiere del actual, la fila SHALL llevar una advertencia que sugiera un ajuste de stock.

#### Scenario: Producto nuevo con stock
- **WHEN** se confirma una fila nueva con stock inicial 20
- **THEN** el producto queda con `stock_actual` 20 y existe un movimiento `apertura` de +20 con previo 0 y nuevo 20

#### Scenario: Producto existente con stock distinto
- **WHEN** se confirma una fila de un SKU existente con stock actual 5 y la planilla dice 12
- **THEN** el stock sigue en 5, no se crea movimiento y la fila tiene advertencia de ajuste

### Requirement: Distribuidoras y categorías faltantes

The system SHALL resolver la distribuidora de cada fila por nombre sin acentos ni mayúsculas; si no existe, SHALL crearla al confirmar (una sola vez aunque aparezca en varias filas) y el dry-run SHALL listarla como "a crear". Si coincide con más de una distribuidora o solo con una dada de baja, la fila SHALL reportarse `error`. La categoría SHALL reutilizar la grafía de una categoría ya existente en el catálogo cuando coincida sin acentos ni mayúsculas; si no, la grafía de su primera aparición en el archivo.

#### Scenario: Distribuidora nueva repetida
- **WHEN** 5 filas traen `Distribuidora Sur` y no existe
- **THEN** al confirmar se crea una sola distribuidora y los 5 productos la tienen por defecto

#### Scenario: Distribuidora existente con otra grafía
- **WHEN** existe `Distribuidora Sur` y la fila trae `distribuidora  sur`
- **THEN** se usa la existente y no se crea otra

#### Scenario: Categoría con otra grafía
- **WHEN** el catálogo ya tiene la categoría `Alimentos` y la fila trae `ALIMENTOS`
- **THEN** el producto queda con categoría `Alimentos`

### Requirement: Endpoint de importación solo dueña

The system SHALL exponer `POST /api/migracion/productos` (multipart: `archivo` obligatorio, `confirmar` booleano por defecto `false`, `mapeo` JSON opcional), accesible solo por rol `duena`, con respuesta validada por un schema estricto del reporte. Análisis: `200` con el reporte aunque tenga errores. Confirmación exitosa: `200` con identificador de lote. Confirmación con errores: `422` con el reporte y sin escrituras. Formato no admitido: `415`. Archivo mayor a 5 MB: `413`. `mapeo` inválido: `422`. Catálogo modificado en paralelo durante la confirmación (SKU creado por otra vía): `409` sin escrituras.

#### Scenario: Mostrador intenta importar
- **WHEN** un usuario `mostrador` envía una planilla
- **THEN** el sistema responde `403` y no analiza el archivo

#### Scenario: Sin autenticación
- **WHEN** un cliente anónimo envía una planilla
- **THEN** el sistema responde `401`

#### Scenario: Dueña analiza y luego confirma
- **WHEN** la dueña envía la planilla sin `confirmar` y después la misma con `confirmar=true`
- **THEN** la primera respuesta no escribe nada y la segunda crea los productos y devuelve el identificador de lote

#### Scenario: Confirmación rechazada por errores
- **WHEN** la dueña confirma una planilla con una fila inválida
- **THEN** el sistema responde `422` con el reporte por fila y no escribe nada

### Requirement: CLI de importación

The system SHALL proveer un comando `python -m scripts.importar_productos <archivo>` que por defecto solo analiza e imprime el reporte (resumen y filas con advertencia o error), y aplica únicamente con `--confirmar`. SHALL aceptar `--mapeo <json>`, `--hoja <nombre>` y `--usuario <email de dueña>` (por defecto, la única dueña activa). Código de salida: `0` sin errores, `1` con errores de datos, `2` por uso inválido o usuario no resoluble.

#### Scenario: CLI en modo análisis
- **WHEN** se corre el comando sobre la planilla sucia de ejemplo sin `--confirmar`
- **THEN** imprime las filas con error y advertencia, sale con código 1 y la base no cambia

#### Scenario: CLI confirma planilla limpia
- **WHEN** se corre con `--confirmar` sobre la planilla limpia de ejemplo
- **THEN** crea los productos con sus movimientos de apertura y sale con código 0

#### Scenario: Dueña ambigua
- **WHEN** hay dos dueñas activas y no se pasa `--usuario`
- **THEN** el comando sale con código 2 sin analizar ni escribir

### Requirement: Planillas de ejemplo reproducibles

The system SHALL versionar un generador determinístico que produce `docs/ejemplos/productos_prueba.xlsx` (todas las filas válidas, al menos 15 productos, 2 o más distribuidoras y categorías) y `docs/ejemplos/productos_prueba_sucio.xlsx` (encabezados con alias, `$` y miles, coma decimal, margen con `%`, espacios sobrantes, filas vacías, un SKU duplicado, un costo inválido y un stock con decimales), de modo que regenerarlos produzca el mismo contenido.

#### Scenario: Regenerar planillas
- **WHEN** se ejecuta el generador dos veces
- **THEN** ambas ejecuciones producen planillas con exactamente las mismas celdas

#### Scenario: Planilla sucia ejercita el dry-run
- **WHEN** se analiza `docs/ejemplos/productos_prueba_sucio.xlsx`
- **THEN** el reporte contiene al menos una fila `ok`, una `advertencia` y errores por SKU duplicado, costo inválido y stock con decimales
