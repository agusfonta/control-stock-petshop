# Reglas de Negocio

Cada regla tiene código único `RN-{DOMINIO}-{NN}`.

## Dominio: Ventas (RN-VT)

- **RN-VT-01**: No se confirma una venta si alguna línea supera el stock disponible (bloqueo duro).
- **RN-VT-02**: La venta descuenta stock en la misma transacción que crea líneas y pagos; si falla algo, rollback total.
- **RN-VT-03**: Solo dueña puede anular una venta confirmada; la anulación devuelve stock con movimiento inverso auditable.
- **RN-VT-04**: El total de pagos debe igualar el total de la venta antes de confirmar.

## Dominio: Stock (RN-ST)

- **RN-ST-01**: Cuando `stock <= stock_minimo`, el sistema marca alerta de reposición (lista + badge).
- **RN-ST-02**: `stock_minimo` configurable por producto por la dueña.
- **RN-ST-03**: Todo cambio de stock genera un MovimientoStock append-only; prohibido editar stock sin movimiento.
- **RN-ST-04**: Granel por peso y lote/vencimiento NO aplican en v1 (explícitamente fuera).

## Dominio: Precios (RN-PR)

- **RN-PR-01**: `precio_venta = costo × (1 + margen_pct)` calculado automáticamente.
- **RN-PR-02**: `margen_pct` configurable global y por producto; solo dueña lo edita.
- **RN-PR-03**: Precios diferenciados por distribuidora vía listas (costo según origen).
- **RN-PR-04**: Cambio de costo actualiza precio sugerido pero no reescribe ventas históricas.

## Dominio: Compras (RN-CP)

- **RN-CP-01**: Una entrada de stock suma cantidades y registra costo de la lista vigente.
- **RN-CP-02**: Un pedido a distribuidora no mueve stock hasta marcarse recibido (genera entrada).
- **RN-CP-03**: Pagos a distribuidoras independientes de pedidos (cuenta corriente simple).

## Dominio: Auth (RN-AU)

- **RN-AU-01**: JWT corto + refresh; roles dueña/mostrador según matriz RBAC.
- **RN-AU-02**: Usuarios solo creados por dueña; sin registro público.

## Dominio: Excepciones globales

- Operaciones de dinero y stock son idempotentes por `idempotency_key` en ventas y FE.
- Más reglas pendientes del usuario se agregan como RN nuevas sin romper las existentes.
