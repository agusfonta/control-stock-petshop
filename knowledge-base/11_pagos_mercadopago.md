# Pagos con Mercado Pago

Complementa `02` y `06` (US-001/US-002) para el cobro del mostrador.

## Alcance v1

- Cobro con QR/link y registro manual de efectivo/transferencia.
- Conciliación básica por `ref_MP` en PagoVenta.
- Webhook para confirmar pagos async (con firma y reintentos).

## Fuera de v1

- Cuotas/financiación avanzada, devoluciones automáticas, split.

## Datos

- `PagoVenta.metodo`: efectivo | transferencia | mp | tarjeta.
- `ref_MP`: id de pago/intent para conciliar. Idempotencia por `idempotency_key`.

## Riesgos

- Webhook sin validar → solo aceptar con firma MP.
- Doble acreditación → conciliar por ref, no por monto.
