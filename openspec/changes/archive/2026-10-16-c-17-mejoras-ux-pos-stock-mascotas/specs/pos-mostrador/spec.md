## MODIFIED Requirements

### Requirement: Cobro con pagos divididos y vuelto

The system SHALL abrir, al pulsar "Cobrar" con un carrito no vacío, un panel de cobro que ofrece únicamente los medios **efectivo**, **transferencia** y **tarjeta** (el medio Mercado Pago no se ofrece) y propone un pago en efectivo por el total. Cada medio SHALL poder usarse a lo sumo una vez en la misma venta: un medio ya elegido en una fila no está disponible en las demás y "Agregar otro medio" se deshabilita cuando ya están los tres. La persona SHALL poder dividir el total entre hasta 3 pagos de medios distintos; la app SHALL mostrar en todo momento cuánto falta o sobra y SHALL habilitar "Confirmar venta" solo cuando la suma de los pagos es exactamente igual al total y cada monto es mayor a 0 con a lo sumo dos decimales. La fila de efectivo SHALL tener un único campo de entrada, "Paga con" (lo que entrega el cliente, con botones de montos rápidos): el efectivo a cobrar NO se tipea sino que se calcula como el total menos los montos de los otros medios, se muestra como "Efectivo a cobrar" y el vuelto = paga con − efectivo a cobrar. Si "Paga con" queda vacío se asume pago exacto y no hay vuelto. Los demás medios tienen su campo de monto. NO SHALL existir una sección "Paga con" separada de las filas de pago. El vuelto es solo informativo y no se envía al servidor; los pagos enviados a `POST /api/ventas/{id}/confirmar` (medio y monto de cada uno) y el cálculo del total NO SHALL cambiar.

#### Scenario: Pago en efectivo con vuelto

- **WHEN** el total es $ 3.800 y el cliente paga con $ 5.000 en efectivo
- **THEN** la app muestra "Efectivo a cobrar $ 3.800,00" y vuelto "$ 1.200,00", y habilita "Confirmar venta" con un pago efectivo de 3800

#### Scenario: Un solo campo para el efectivo

- **WHEN** se abre el panel de cobro con el medio efectivo seleccionado
- **THEN** la fila de efectivo tiene un único campo, "Paga con", sin campo de monto aparte, y no existe una tarjeta "Paga con" separada

#### Scenario: Pago mixto con vuelto solo sobre el efectivo

- **WHEN** el total es $ 38.500, se agrega transferencia con $ 18.500 y el cliente paga con $ 25.000 en efectivo
- **THEN** el efectivo a cobrar es "$ 20.000,00", el vuelto es "$ 5.000,00", la fila de transferencia no tiene "Paga con" y se confirma con pagos efectivo 20000 y transferencia 18500

#### Scenario: Segundo medio se autocompleta con lo que falta

- **WHEN** el total es $ 10.000, el cliente entrega $ 9.000 en "Paga con" y se pulsa "Agregar otro medio"
- **THEN** el nuevo medio aparece con el monto "1000" ya cargado (total menos lo entregado en efectivo), editable; el efectivo a cobrar pasa a $ 9.000,00 y no hay vuelto. Si "Paga con" está vacío o cubre el total, el monto del nuevo medio arranca vacío

#### Scenario: Un medio no se repite

- **WHEN** ya hay una fila de efectivo
- **THEN** ninguna otra fila puede elegir efectivo, y cuando hay filas de los tres medios "Agregar otro medio" está deshabilitado

#### Scenario: Pago dividido incompleto

- **WHEN** el total es $ 3.800 y se cargan transferencia $ 1.800 y tarjeta $ 1.500 sin efectivo
- **THEN** la app muestra "Faltan $ 500,00" y "Confirmar venta" queda deshabilitado

#### Scenario: Sin Mercado Pago

- **WHEN** se abre el panel de cobro
- **THEN** los únicos medios disponibles son efectivo, transferencia y tarjeta
