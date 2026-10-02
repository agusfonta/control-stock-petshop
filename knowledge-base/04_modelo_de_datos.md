# Modelo de Datos

## Dominios

- Catálogo (productos, precios, distribuidoras).
- Inventario (stock, movimientos, mínimos).
- Ventas (ventas, líneas, pagos, comprobantes).
- Compras (pedidos, entradas, pagos a distribuidoras).
- Clientes y usuarios.

## ERD

```
Distribuidora 1—N ListaPrecio N—1 Producto 1—N MovimientoStock
Producto 1—N LineaVenta N—1 Venta 1—N PagoVenta
Distribuidora 1—N PedidoCompra 1—N EntradaStock N—1 Producto
Cliente 1—N Venta | Usuario N—N Rol
Venta 1—1 ComprobanteFE
```

## Entidades

### Producto
- Atributos: id (uuid), sku/código barras (unique), nombre, marca, categoría, unidad (unidad/bolsa/caja), costo, margen_pct, precio_venta (calculado), stock_actual, stock_minimo, distribuidora_default_id, activo.
- Relaciones: N—1 distribuidora, 1—N movimientos, 1—N líneas.
- Constraints: precio_venta = costo × (1+margen); stock_actual >= 0; sku unique.
- Índices: sku, nombre (trgm), categoría.

### MovimientoStock
- Atributos: id, producto_id, tipo (venta/entrada/ajuste), cantidad (+/-), stock_previo, stock_nuevo, ref_id, usuario_id, created_at.
- Relaciones: N—1 producto, N—1 usuario.
- Constraints: append-only (no update/delete).

### Venta
- Atributos: id, cliente_id (nullable), total, estado (borrador/confirmada/anulada), usuario_id, created_at.
- Relaciones: 1—N líneas, 1—N pagos, 1—1 comprobante.

### LineaVenta
- producto_id, cantidad, precio_unit, subtotal. Constraint: cantidad > 0, stock validado antes de confirmar.

### PagoVenta
- método (efectivo/transferencia/MP/tarjeta), monto, ref_MP.

### Distribuidora
- nombre, contacto, cuit, condiciones. 1—N listas de precios y pedidos.

### PedidoCompra / EntradaStock / PagoDistribuidora
- Pedido: distribuidora_id, estado (pendiente/recibido/cancelado), líneas.
- Entrada: suma stock + actualiza costo si corresponde.
- Pago: distribuidora_id, monto, método, fecha.

### Cliente
- nombre, teléfono, email, dirección, saldo_cc. 1—N ventas.

### Usuario
- email (unique), hash, rol (dueña/mostrador), activo.

### ComprobanteFE
- venta_id, tipo (ticket/FE A/B/C), cae, número, estado (pendiente/emitido/error), payload, intentos.

## Seed data inicial

- Roles y usuario dueña inicial.
- Categorías base (alimentos, accesorios, higiene, farmacia).
- Métodos de pago base. Sin catálogo precargado (migración desde Excel del local).
