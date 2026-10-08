# Spec Delta

## Purpose

Dar a la dueña reportes de solo lectura para decidir compras —ventas del día, productos más vendidos, reposición por mínimo y rotación, y márgenes con el costo vigente al vender— calculados sobre ventas confirmadas e imputados al día local del negocio, con una vista básica para el mostrador (US-009).

## ADDED Requirements

### Requirement: Ventas computables e imputación por día local

Todos los reportes SHALL computar únicamente ventas en estado `confirmada`; los borradores nunca cuentan y las ventas `anuladas` no suman en ningún agregado (solo aparecen como contador separado en ventas del día). Cada venta SHALL imputarse al día calendario de su confirmación en la zona horaria del negocio, configurable por entorno y por defecto `America/Argentina/Buenos_Aires`. Los parámetros de fecha SHALL ser días calendario en formato `YYYY-MM-DD` interpretados en esa zona; un período `desde`/`hasta` incluye ambos días completos. "Hoy" SHALL ser la fecha actual en la zona del negocio. Una venta confirmada y luego anulada deja de contar en el día de su confirmación (los reportes reflejan el estado actual).

#### Scenario: Venta cerca de la medianoche se imputa al día local

- **WHEN** una venta se confirma a las `2026-10-06T02:30:00Z` (23:30 del 5 de octubre en Argentina) y la dueña pide las ventas del día `2026-10-05` y luego del día `2026-10-06`
- **THEN** la venta cuenta en el reporte del `2026-10-05` y no en el del `2026-10-06`

#### Scenario: Hoy se calcula en la zona del negocio

- **WHEN** son las `2026-10-07T01:00:00Z` (22:00 del 6 de octubre en Argentina) y la dueña pide ventas del día sin `fecha`
- **THEN** el reporte corresponde al día `2026-10-06`

#### Scenario: Borradores y anuladas no suman

- **WHEN** en un día hay una venta confirmada de total 3800, un borrador de total 800 y una venta confirmada ese día y luego anulada de total 1500
- **THEN** los totales del día, los más vendidos y los márgenes de ese período solo incluyen la venta de 3800, y la rotación de reposición solo cuenta sus unidades

### Requirement: Reporte de ventas del día

The system SHALL exponer `GET /api/reportes/ventas-dia` con parámetro opcional `fecha` (default hoy) que responde `200` con: `fecha`, `alcance` (`todas` para la dueña, `propias` para el mostrador), `cantidad_ventas`, `total_vendido` (suma de los totales), `ticket_promedio` (total vendido / cantidad de ventas, redondeado a centavos mitad hacia arriba, `0` sin ventas), `unidades_vendidas` (suma de cantidades de las líneas), `por_metodo` con una entrada por cada método de pago (`efectivo`, `transferencia`, `mp`, `tarjeta`, en ese orden y siempre presentes) con `monto` y `cantidad_pagos`, y `anuladas` con `cantidad` y `total` de las ventas confirmadas ese día que hoy están anuladas. Los importes SHALL expresarse con a lo sumo dos decimales.

#### Scenario: Día con ventas en efectivo y pago mixto

- **WHEN** el día tiene una venta confirmada de 2 unidades a 1500 y 1 unidad a 800 pagada con 3800 en efectivo, y otra de 1 unidad a 1500 pagada con 500 en efectivo y 1000 por `mp`
- **THEN** el reporte responde `cantidad_ventas = 2`, `total_vendido = 5300`, `ticket_promedio = 2650`, `unidades_vendidas = 4`, `efectivo` con `monto = 4300` y `cantidad_pagos = 2`, `mp` con `monto = 1000` y `cantidad_pagos = 1`, `transferencia` y `tarjeta` en `0`, y `anuladas` con `cantidad = 0`

#### Scenario: Anulada se informa aparte

- **WHEN** una venta de total 1500 confirmada en el día es anulada por la dueña
- **THEN** el reporte de ese día la excluye de `cantidad_ventas`, `total_vendido`, `unidades_vendidas` y `por_metodo`, y muestra `anuladas` con `cantidad = 1` y `total = 1500`

#### Scenario: Día sin ventas

- **WHEN** la dueña pide un día sin ventas confirmadas
- **THEN** el sistema responde `200` con `cantidad_ventas = 0`, `total_vendido = 0`, `ticket_promedio = 0`, `unidades_vendidas = 0` y los cuatro métodos en `0`

#### Scenario: Ticket promedio redondeado

- **WHEN** el día tiene tres ventas confirmadas de totales 100, 100 y 100.01
- **THEN** `ticket_promedio = 100` (100.003… redondeado a centavos)

### Requirement: Reporte de productos más vendidos

The system SHALL exponer `GET /api/reportes/mas-vendidos` con parámetros opcionales `desde`, `hasta`, `orden` (`cantidad` por defecto, o `monto`) y `limite` (entero de 1 a 50, default 10), que responde `200` con `desde`, `hasta`, `orden` y una lista de a lo sumo `limite` productos con `producto_id`, `sku`, `nombre`, `activo`, `unidades` (suma de cantidades) y `monto` (suma de subtotales) en el período. El orden SHALL ser descendente por la métrica elegida, luego descendente por la otra métrica y luego por `producto_id` ascendente. Los productos dados de baja que tuvieron ventas en el período SHALL aparecer con `activo = false`. Sin `desde` ni `hasta`, el período SHALL ser los últimos 30 días incluido hoy.

#### Scenario: Ranking por unidades

- **WHEN** en el período se vendieron 8 unidades del producto B por un monto de 2400 y 5 unidades del producto A por un monto de 7500
- **THEN** con `orden` por defecto la lista es B (8 unidades, 2400) y luego A (5 unidades, 7500)

#### Scenario: Ranking por monto

- **WHEN** con los mismos datos la dueña pide `orden=monto`
- **THEN** la lista es A y luego B

#### Scenario: Empate en la métrica principal

- **WHEN** dos productos vendieron 5 unidades cada uno, uno por 7500 y otro por 2000
- **THEN** con `orden=cantidad` aparece primero el de 7500

#### Scenario: Límite de resultados

- **WHEN** se vendieron 12 productos distintos en el período y la dueña pide `limite=3`
- **THEN** la lista tiene exactamente los 3 primeros del ranking

#### Scenario: Período por defecto

- **WHEN** hoy es `2026-10-06` y la dueña pide el reporte sin `desde` ni `hasta`
- **THEN** la respuesta tiene `desde = 2026-09-07` y `hasta = 2026-10-06` y solo cuenta ventas confirmadas en ese período

#### Scenario: Producto dado de baja con ventas

- **WHEN** un producto con ventas en el período fue dado de baja después
- **THEN** aparece en el ranking con `activo = false`

### Requirement: Reporte de reposición por mínimo y rotación

The system SHALL exponer `GET /api/reportes/reposicion` con parámetros opcionales `dias` (ventana de rotación, entero de 7 a 180, default 30) y `cobertura_max_dias` (entero de 1 a 90, default 7), que responde `200` con `dias`, `cobertura_max_dias` y la lista de productos **activos** que cumplen al menos una condición: (a) `stock_actual <= stock_minimo` (mismo criterio que la alerta de bajo mínimo), o (b) tuvieron ventas en la ventana y sus días de cobertura son `<= cobertura_max_dias`. La ventana SHALL ser los últimos `dias` días locales incluido hoy. Cada ítem SHALL incluir `producto_id`, `sku`, `nombre`, `stock_actual`, `stock_minimo`, `bajo_minimo`, `unidades_vendidas` (en la ventana), `venta_diaria` (unidades vendidas / `dias`, a centavos mitad hacia arriba), `cobertura_dias` (parte entera de `stock_actual / (unidades_vendidas / dias)`, o `null` sin ventas en la ventana) y `distribuidora_default_id`. El orden SHALL ser `cobertura_dias` ascendente con los `null` al final, luego `stock_actual - stock_minimo` ascendente y luego `producto_id`. El reporte NO SHALL incluir costos, precios ni importes.

#### Scenario: Bajo mínimo sin ventas

- **WHEN** un producto activo tiene `stock_actual = 2`, `stock_minimo = 3` y ninguna venta en la ventana
- **THEN** aparece con `bajo_minimo = true`, `unidades_vendidas = 0`, `venta_diaria = 0` y `cobertura_dias = null`

#### Scenario: Rotación alta sobre el mínimo

- **WHEN** un producto activo tiene `stock_actual = 10`, `stock_minimo = 2` y vendió 60 unidades en los últimos 30 días
- **THEN** aparece con `bajo_minimo = false`, `venta_diaria = 2`, `cobertura_dias = 5`

#### Scenario: Rotación baja sobre el mínimo

- **WHEN** un producto activo tiene `stock_actual = 10`, `stock_minimo = 2` y vendió 3 unidades en los últimos 30 días (cobertura de 100 días)
- **THEN** no aparece en el reporte

#### Scenario: Sin ventas y sobre el mínimo

- **WHEN** un producto activo está sobre su mínimo y no tuvo ventas en la ventana
- **THEN** no aparece en el reporte

#### Scenario: Ventas fuera de la ventana o anuladas no cuentan

- **WHEN** un producto vendió 40 unidades hace 45 días y 20 en una venta de esta semana que luego fue anulada, y la dueña pide `dias=30`
- **THEN** su `unidades_vendidas` es 0

#### Scenario: Coincide con las alertas de bajo mínimo

- **WHEN** hay productos activos bajo mínimo
- **THEN** cada producto que lista `GET /api/stock/alertas` aparece en el reporte de reposición con `bajo_minimo = true`, y los productos dados de baja no aparecen

#### Scenario: Orden por cobertura

- **WHEN** el reporte incluye un producto con cobertura 5, otro con cobertura 0 (stock agotado con ventas) y otro bajo mínimo sin ventas
- **THEN** el orden es cobertura 0, cobertura 5 y al final el de cobertura `null`

### Requirement: Reporte de márgenes con costo histórico

The system SHALL exponer `GET /api/reportes/margenes` con parámetros opcionales `desde`, `hasta` (mismos defaults y límites que más vendidos), `page` y `page_size` (default 20, máximo 100), que responde `200` con `desde`, `hasta`, `totales` y una página de productos. Para cada producto, sobre las líneas de ventas confirmadas del período que tienen costo congelado: `unidades`, `ingresos` (suma de subtotales), `costo` (suma de `cantidad × costo unitario congelado`), `margen_bruto` (`ingresos − costo`) y `margen_pct` (`margen_bruto / costo`, el mismo sentido que el `margen_pct` del catálogo, con 4 decimales). `totales` SHALL sumar `ingresos`, `costo`, `margen_bruto` y `margen_pct` sobre todas esas líneas, e informar aparte `lineas_sin_costo` e `ingresos_sin_costo` de las líneas sin costo congelado, que no entran en ningún otro número. Sin líneas con costo, `margen_pct` SHALL ser `null`. El orden SHALL ser `margen_bruto` descendente y luego `producto_id`, con metadata de paginación. El margen SHALL usar siempre el costo congelado en la línea, nunca el costo actual del producto.

#### Scenario: Margen por producto y total

- **WHEN** en el período se vendieron 2 unidades del producto A a 1500 con costo congelado 1000
- **THEN** A aparece con `unidades = 2`, `ingresos = 3000`, `costo = 2000`, `margen_bruto = 1000`, `margen_pct = 0.5`, y los totales coinciden

#### Scenario: Cambio de costo posterior no altera márgenes pasados

- **WHEN** después de esa venta una recepción sube el costo de A a 1200 y luego se vende 1 unidad de A a 1800
- **THEN** A aparece con `unidades = 3`, `ingresos = 4800`, `costo = 3200`, `margen_bruto = 1600`, `margen_pct = 0.5`

#### Scenario: Líneas sin costo congelado se informan aparte

- **WHEN** el período incluye una línea de venta confirmada registrada sin costo congelado, con subtotal 900
- **THEN** esa línea no suma en `ingresos`, `costo` ni `margen_bruto` de ningún producto ni de los totales, y `totales` informa `lineas_sin_costo = 1` e `ingresos_sin_costo = 900`

#### Scenario: Período sin ventas

- **WHEN** la dueña pide márgenes de un período sin ventas confirmadas
- **THEN** el sistema responde `200` con lista vacía, `total = 0`, totales en `0` y `margen_pct = null`

### Requirement: Acceso a reportes por rol

Los cuatro reportes SHALL requerir autenticación (`401` anónimo). La dueña SHALL acceder a los cuatro con todas las ventas. El mostrador ("ver básico") SHALL acceder solo a ventas del día, restringido a las ventas de las que es vendedor (`alcance = propias`), y a reposición; `mas-vendidos` y `margenes` SHALL responder `403` al mostrador. Ningún reporte accesible al mostrador SHALL exponer costos ni márgenes.

#### Scenario: Mostrador ve solo sus ventas del día

- **WHEN** en el día el mostrador M1 confirmó una venta de 3800 y el mostrador M2 una de 1500, y M1 pide ventas del día
- **THEN** el reporte responde `alcance = propias`, `cantidad_ventas = 1` y `total_vendido = 3800`, mientras que la dueña ve `alcance = todas`, `cantidad_ventas = 2` y `total_vendido = 5300`

#### Scenario: Mostrador accede a reposición

- **WHEN** un usuario `mostrador` pide el reporte de reposición
- **THEN** el sistema responde `200` con los mismos ítems que ve la dueña y sin campos de costo o precio

#### Scenario: Mostrador bloqueado en más vendidos y márgenes

- **WHEN** un usuario `mostrador` pide `mas-vendidos` o `margenes`
- **THEN** el sistema responde `403`

#### Scenario: Reportes anónimos rechazados

- **WHEN** un cliente sin token pide cualquiera de los cuatro reportes
- **THEN** el sistema responde `401`

### Requirement: Reportes siempre actualizados

Los reportes SHALL reflejar el estado de las ventas al momento de la consulta: una venta confirmada o anulada SHALL verse en la siguiente consulta, sin esperar recálculos ni expiración de caché.

#### Scenario: Venta confirmada visible de inmediato

- **WHEN** la dueña consulta ventas del día, se confirma una venta de 1500 y la dueña vuelve a consultar
- **THEN** la segunda consulta muestra una venta más y 1500 más de `total_vendido`

#### Scenario: Anulación visible de inmediato

- **WHEN** la dueña consulta márgenes, anula una venta del período y vuelve a consultar
- **THEN** la segunda consulta ya no incluye las líneas de la venta anulada

### Requirement: Validación estricta de parámetros de reportes

Los parámetros de los reportes SHALL validarse estrictamente: fechas que no sean `YYYY-MM-DD` (incluidas fechas con hora), `desde` posterior a `hasta`, períodos de más de 366 días, `orden` fuera de (`cantidad`, `monto`), `limite`, `dias`, `cobertura_max_dias`, `page` o `page_size` fuera de rango y parámetros desconocidos SHALL responder `422`. Con solo `desde`, `hasta` SHALL ser hoy; con solo `hasta`, `desde` SHALL ser 29 días antes de `hasta`.

#### Scenario: Fecha mal formada

- **WHEN** la dueña pide ventas del día con `fecha=06/10/2026` o `fecha=2026-10-06T10:00:00`
- **THEN** el sistema responde `422`

#### Scenario: Período invertido o demasiado largo

- **WHEN** la dueña pide más vendidos con `desde=2026-10-06&hasta=2026-10-01`, o con un período de 367 días
- **THEN** el sistema responde `422`

#### Scenario: Parámetros fuera de rango o desconocidos

- **WHEN** la dueña pide `orden=ganancia`, `limite=0`, `limite=51`, `dias=6`, `cobertura_max_dias=91`, `page_size=101` o un parámetro `vendedor=x` no definido
- **THEN** el sistema responde `422`

#### Scenario: Período con un solo borde

- **WHEN** hoy es `2026-10-06` y la dueña pide más vendidos solo con `desde=2026-10-01`, y luego solo con `hasta=2026-09-30`
- **THEN** la primera respuesta tiene `hasta = 2026-10-06` y la segunda `desde = 2026-09-01`
