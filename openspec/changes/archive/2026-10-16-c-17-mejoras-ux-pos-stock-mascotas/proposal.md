# Proposal

## Why

La dueña usó la app y devolvió tres fricciones: en el cobro en efectivo hay dos lugares donde cargar plata (monto del medio y tarjeta "Paga con"), Productos y Stock muestran casi lo mismo en dos pestañas, y no se pueden registrar las mascotas de un cliente (dato útil para atender en el mostrador).

## What Changes

- **POS (UI, sin tocar backend ni contrato RN-VT)**: en el panel "Cobrar", "Paga con" (con atajos de billetes y vuelto) pasa a vivir dentro de la fila de pago en efectivo; se elimina la tarjeta "Paga con" separada. En pagos mixtos, "paga con" y vuelto aplican solo a la porción en efectivo.
- **Productos + Stock fusionados**: una sola sección y una sola tabla (producto + costo/margen/precio para dueña + stock actual/mínimo/estado) con todas las acciones de ambas (alta, edición, margen/mínimo, baja, ajustar stock), el banner de alertas y el filtro "Solo bajo mínimo". `/stock` redirige a `/productos`. La navegación pasa a una sola entrada con el badge de alertas.
- **Mascotas por cliente (backend + frontend)**: nueva entidad `Mascota` (nombre, tipo `perro|gato|otro`) 1—N por cliente, con alta, edición y baja desde la ficha del cliente. Migración Alembic 0010, schemas estrictos y endpoints bajo `/api/clientes/{id}/mascotas`.
- Se actualiza `knowledge-base/04_modelo_de_datos.md` (Mascota, ERD).

Sin cambios BREAKING en la API existente. Cambio de URL visible: `/stock` → `/productos` (con redirect).

## Capabilities

### New Capabilities
<!-- ninguna: todo extiende capabilities existentes -->

### Modified Capabilities
- `pos-mostrador`: "Cobro con pagos divididos y vuelto" — "Paga con" y vuelto integrados en la fila de efectivo; aplican solo a la porción en efectivo.
- `gestion-ui`: "Catálogo de productos" y "Stock, alertas y ajustes" se unifican en una sola sección/tabla; nuevo requirement de mascotas en la ficha del cliente.
- `frontend-shell`: "Navegación y layout responsive" — una única entrada de inventario con badge de alertas (reemplaza la entrada Stock).
- `clientes`: nuevo requirement de mascotas de un cliente (API).

## Impact

- Frontend: `features/pos/{CheckoutForm,PagoRowEditor,CheckoutSheet}.tsx` (+ helpers y tests), `features/productos` y `features/stock` (fusión), `app/{router,nav}.ts(x)`, `features/clientes/*` (sección mascotas).
- Backend: `modules/clientes/{models,schemas,service,router}.py`, migración `0010`, tests en `tests/clientes/` y `tests/infra/` (test de cabeza de migraciones).
- KB: `04_modelo_de_datos.md`. Sin dependencias nuevas. Sin cambios en `ventas` ni en el cálculo de totales/pagos.

## Recomendación de alcance (un change vs tres)

Un solo change con **tres bloques independientes** (no comparten código ni tablas): evita triplicar el overhead de propuesta/archivo y la prioridad es velocidad. Orden por riesgo ascendente: (1) fusión Productos+Stock, (2) mascotas, (3) POS efectivo, que es gobernanza CRÍTICA y lleva su propia puerta de aprobación antes de escribir código. Cada bloque termina con tests en verde, así que se puede frenar entre bloques.
