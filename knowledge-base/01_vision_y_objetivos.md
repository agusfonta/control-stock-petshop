# Visión y Objetivos — Control Stock Petshop

## Propósito del sistema

Sistema web de mostrador para un petshop de un solo local que reemplaza papel/Excel por un circuito ordenado de ventas, stock y compras a distribuidoras, sin frenar la atención en tablet.

## Objetivos por actor

| Actor | Objetivo principal | Objetivos secundarios |
|---|---|---|
| Dueña/admin | Saber qué hay, qué falta y qué deja margen | Configurar mínimos y márgenes, ver reportes, gestionar distribuidoras y clientes |
| Mostrador/vendedor | Cobrar rápido y dejar stock siempre consistente | Buscar por código/nombre, vender con ticket/FE, registrar entradas |

## Alcance v1

- Ventas rápidas con buscador + lector de código, ticket y factura electrónica ARCA.
- Stock en tiempo real con mínimos configurables, alertas y bloqueo de venta sin stock.
- Distribuidoras: altas, listas de precios por distribuidora, entradas de stock, pedidos y pagos.
- Precio de venta = costo × (1 + % margen configurable).
- Clientes: registro e historial básico.
- Auth JWT con 2 roles (dueña, mostrador), auditoría básica de movimientos.
- UI parecida al demo Animall actual pero producto final (no demo).

## Fuera de alcance

- Granel por peso y control por lote/vencimiento → v2 (decisión explícita).
- Turnos/veterinaria e historia clínica → fase 2.
- Offline total ante corte de internet → v2 (diseñar teniéndolo en cuenta).
- Ecommerce, promociones/cupones avanzados, analytics predictivo.
- Multi-local y multi-tenant.

## Métricas de éxito

- Venta promedio en mostrador < 60 segundos desde búsqueda hasta ticket.
- Cero ventas con stock negativo (bloqueo efectivo).
- Alertas de mínimo disparadas antes del quiebre en productos top.
- Migración papel/Excel completada sin pérdida de catálogo.
