# Proposal

## Why

El sistema todavía no puede vender: hoy el stock solo baja por ajuste manual (C-05) y sube por recepción de pedidos (C-07). US-001 y el Flujo 1 exigen que el mostrador cobre una venta que **descuente stock en la misma transacción que crea líneas y pagos** (RN-VT-02), que **bloquee duro** si alguna línea supera el stock (RN-VT-01, DD-03), que **no confirme si los pagos no igualan el total** (RN-VT-04) y que solo la dueña pueda **anular** devolviendo stock con un movimiento auditable (RN-VT-03), todo idempotente por `idempotency_key` (Excepciones globales). Es el núcleo del camino crítico: C-11 (FE ARCA), C-12 (Mercado Pago), C-13 (POS) y C-14 (reportes) dependen de que exista `Venta`. C-04, C-05 y C-09 ya están archivados (catálogo con `precio_venta`, núcleo transaccional de stock `aplicar_movimiento()`, clientes).

## What Changes

- Modelos nuevos: `Venta` (cliente nullable, vendedor, `total`, estado `borrador`/`confirmada`/`anulada`, `idempotency_key`, auditoría de confirmación y anulación), `LineaVenta` (producto, `cantidad > 0`, `precio_unit` congelado, `subtotal`) y `PagoVenta` (método `efectivo`/`transferencia`/`mp`/`tarjeta`, `monto > 0`, `ref_mp` opcional solo para `mp`). Líneas y pagos son inmutables.
- `POST /api/ventas` (dueña y mostrador): crea una venta en `borrador` con sus líneas; el precio de cada línea y el total los calcula el servidor desde `precio_venta` (el cliente nunca envía precios). Valida productos (existentes, activos, con stock suficiente) y `cliente_id` (inexistente ⇒ `404`, dado de baja ⇒ `422`). Idempotente por `idempotency_key`: repetir el mismo pedido devuelve la misma venta sin crear otra; reutilizar la clave con otro contenido se rechaza.
- `POST /api/ventas/{id}/confirmar` (dueña y mostrador, este último solo sobre sus ventas): en **una sola transacción** revalida stock con bloqueo de filas, valida que los pagos igualen el total, descuenta stock de cada línea creando un `MovimientoStock` tipo `venta`, registra los pagos, marca `confirmada` y deja registrado el evento para la facturación electrónica. Cualquier fallo revierte todo. Repetir la confirmación no descuenta stock dos veces.
- `POST /api/ventas/{id}/anular` (solo dueña, con motivo obligatorio): pasa una venta `confirmada` a `anulada` y devuelve el stock de cada línea con un movimiento inverso auditable, en una transacción. Sin devolución de dinero en v1.
- Lecturas: `GET /api/ventas/{id}` (detalle para ticket/reintento) y `GET /api/ventas` (paginado y filtrable); el mostrador solo ve sus propias ventas, la dueña ve todas.
- `GET /api/clientes/{id}/ventas`: historial de ventas por cliente (movido desde C-09), agregado como requirement nuevo de la capability `clientes`.
- Bandeja de eventos transaccional (outbox) mínima: confirmar y anular registran un evento en la misma transacción para que C-11 (FE) y C-14 (cache de reportes) lo consuman. C-10 no emite facturas, no usa Redis y no crea `ComprobanteFE`.
- Migración Alembic `0007` (hija de `0006_compras`): tablas `venta`, `linea_venta`, `pago_venta`, `evento_outbox` + enums `estado_venta` y `metodo_pago_venta`, checks, uniques e índices. Sin cambios al enum `tipo_movimiento`.
- Tests TDD RED-first para RN-VT-01..04, atomicidad, idempotencia, concurrencia por la última unidad, RBAC y propiedad de ventas, e historial por cliente.

## Capabilities

### New Capabilities

- `ventas`: venta de mostrador transaccional — borrador con precios congelados por el servidor, confirmación atómica con bloqueo duro sin stock y pagos que igualan el total, anulación solo por dueña con movimiento inverso, idempotencia por clave, lecturas con propiedad por vendedor y registro de eventos para facturación (US-001, RN-VT-01..04).

### Modified Capabilities

- `clientes`: se agrega el requirement "Historial de ventas por cliente" (`GET /api/clientes/{id}/ventas`), diferido explícitamente desde C-09 (D2 de C-09). Los requirements existentes no cambian.
- (`stock-alertas` no se modifica: la venta usa el tipo `venta` ya reservado y la anulación se registra como movimiento `venta` de cantidad positiva con referencia a la venta, ver design D1; `auth-rbac` ya especifica "solo dueña anula ventas" y "mostrador crea y ve sus ventas".)

## Impact

- Nuevo: `backend/app/services/ventas.py`, `backend/app/services/outbox.py`, `backend/app/routers/ventas.py` (+ registro en `main.py`), endpoint de historial en `backend/app/routers/clientes.py`, modelos y schemas nuevos, migración `0007`, tests `test_ventas_*.py`, `test_outbox.py`, `test_clientes_historial.py`, `test_migration_0007.py` y casos nuevos en `test_migration_pg.py`.
- Sin cambios: `backend/app/services/stock.py` (se reutiliza `aplicar_movimiento()` tal cual), enum `tipo_movimiento`, endpoints existentes. Sin breaking changes. Sin frontend (C-13).
- Governance **CRÍTICO**: el apply requiere aprobación humana explícita de las decisiones listadas en `design.md` §"Decisiones a revisar".
- Non-goals: emisión de FE/ARCA y `ComprobanteFE` (C-11), flujo real de Mercado Pago/QR/webhook (C-12), ticket e impresión (C-13), descuentos/promociones, devoluciones parciales y devolución de dinero, cuenta corriente de clientes, edición de borradores, numeración fiscal.
