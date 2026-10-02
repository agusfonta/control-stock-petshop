# Funcionalidades

## Épica 1: Ventas de mostrador

### US-001 — Venta rápida con código
**Como** mostrador **Quiero** buscar por código/nombre y cobrar en <60s **Para** no frenar la fila.

**Criterios de aceptación**:
- [ ] Búsqueda con debounce y lector HID.
- [ ] Bloqueo si `cantidad > stock` (RN-VT-01).
- [ ] Ticket imprimible al confirmar.

**Reglas relacionadas**: RN-VT-01, RN-VT-02, RN-VT-04.

### US-002 — Facturar con ARCA
**Como** dueña **Quiero** emitir ticket/FE desde la venta **Para** cumplir sin salir del flujo.

**Criterios de aceptación**:
- [ ] Emisión async con estados pendiente/emitido/error y reintentos.
- [ ] CAE y número guardados en ComprobanteFE.

**Reglas relacionadas**: RN-VT-02.

## Épica 2: Stock y alertas

### US-003 — Ver stock y alertas
**Como** dueña **Quiero** lista con badge de bajo stock **Para** pedir a tiempo.

**Criterios de aceptación**:
- [ ] Filtro "solo bajo stock", orden por rotación.
- [ ] Alerta cuando `stock <= mínimo` (RN-ST-01).

**Reglas relacionadas**: RN-ST-01, RN-ST-02.

### US-004 — Ajustar stock auditable
**Como** dueña **Quiero** ajustar con motivo **Para** corregir sin perder trazabilidad.

**Criterios de aceptación**:
- [ ] Requiere motivo, genera MovimientoStock.

**Reglas relacionadas**: RN-ST-03.

## Épica 3: Compras a distribuidoras

### US-005 — Gestionar distribuidoras y listas
**Como** dueña **Quiero** ABM + listas por distribuidora **Para** comparar costos.

**Criterios de aceptación**:
- [ ] Costo por lista, precio sugerido recalculado (RN-PR-01).

**Reglas relacionadas**: RN-PR-01, RN-PR-03.

### US-006 — Pedidos y entradas
**Como** dueña **Quiero** pedir y marcar recibido **Para** que entre stock solo cuando llega.

**Criterios de aceptación**:
- [ ] Pedido no mueve stock; entrada sí (RN-CP-02).

**Reglas relacionadas**: RN-CP-01, RN-CP-02, RN-CP-03.

## Épica 4: Clientes y precios

### US-007 — Registro de clientes
**Como** mostrador **Quiero** crear/buscar cliente en la venta **Para** historial básico.

### US-008 — Configurar márgenes y mínimos
**Como** dueña **Quiero** editar margen y mínimo por producto **Para** aplicar RN-PR-02 y RN-ST-02.

## Épica 5: Reportes

### US-009 — Reportes básicos
**Como** dueña **Quiero** ventas del día, más vendidos y reposición **Para** decidir compras.
