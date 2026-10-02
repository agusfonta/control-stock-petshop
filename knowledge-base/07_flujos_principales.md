# Flujos Principales

## Flujo 1: Venta de mostrador con FE
**Disparador**: cliente en caja. **Actor**: mostrador.

**Pasos**:
1. Frontend busca producto (código/nombre).
2. Agrega líneas, valida stock en memoria.
3. Registra pagos (efectivo/MP), verifica total = total venta.
4. Backend en transacción: revalida stock, crea venta + líneas + pagos, descuenta stock, crea movimientos, encola job FE.
5. Worker emite FE ARCA, guarda CAE; si falla queda pendiente con reintento.
6. Frontend muestra ticket e imprime.

**Casos de error**:
- Sin stock → bloqueo con mensaje y sugerencia (RN-VT-01).
- FE error → venta queda confirmada, comprobante pendiente + alerta.
- Pago incompleto → no confirma (RN-VT-04).

## Flujo 2: Reposición por alerta
**Disparador**: stock <= mínimo. **Actor**: dueña.

**Pasos**:
1. Job/lista marca productos bajo mínimo.
2. Dueña crea pedido a distribuidora.
3. Al recibir, registra entrada → suma stock + actualiza costo.
4. Precio sugerido se recalcula (RN-PR-01).

## Flujo 3: Carga inicial desde Excel
**Disparador**: migración. **Actor**: dueña.

**Pasos**:
1. Sube plantilla_productos.csv del local.
2. Sistema valida duplicados y costos.
3. Crea productos con stock inicial + movimientos de apertura.
