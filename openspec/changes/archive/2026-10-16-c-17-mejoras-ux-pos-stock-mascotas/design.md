# Design

## Context

Hallazgos del código actual (ver proposal.md para la motivación):

- **POS**: `CheckoutForm.tsx` mantiene `rows: PagoRow[]` y un único `pagaCon`; la tarjeta "Paga con" (`#paga-con`, atajos `quickCashOptions`, bloque "Vuelto") se renderiza aparte si hay efectivo > 0. `PagoRowEditor.tsx` renderiza por fila el selector de medio, el input "Monto {medio}", "Completar" y "Quitar". El vuelto nunca viaja al backend (`PagoVentaIn` no tiene `paga_con`/`vuelto`); solo se pasa por `onSuccess(venta, vueltoCents, clienteNombre)` al comprobante. Se permiten varias filas con el mismo medio (hasta 5).
- **Productos / Stock**: `/productos` (`ProductosPage`) y `/stock` (`StockPage`) son páginas separadas, ambas visibles para los dos roles. `GET /api/stock` ya devuelve `StockItem` con costo, margen, precio de venta, stock, mínimo y `bajo_minimo`, y soporta `bajo_minimo` y `orden=rotacion`; la búsqueda usa `GET /productos/buscar`. No hay enlaces entrantes a `/stock` salvo la nav. No existe hoy un historial de movimientos en la UI de stock, así que no hay nada que preservar de eso.
- **Clientes**: módulo `backend/app/modules/clientes/` con soft-delete (`AuditMixin.activo`), RBAC alta=ambos / edición y baja=dueña. Cabeza de migraciones: `0009`.

## Goals / Non-Goals

**Goals:**
- Un solo lugar para cargar el efectivo y el "paga con" en el POS, sin cambiar el contrato de venta.
- Una sola sección/tabla de productos+stock sin perder ninguna acción.
- Mascotas 1—N por cliente con alta/edición/baja desde la ficha.

**Non-Goals:**
- Tocar `ventas` (schemas, servicio, totales) o persistir "paga con"/vuelto.
- Historial de movimientos de stock en la UI (no existe hoy), mascotas en la venta/comprobante, raza/edad/notas de mascota, tipos libres.
- Cambios de backend para la fusión (la API actual alcanza).

## Decisions

**D1 — Un change con tres bloques independientes** (vs tres changes). No comparten código ni tablas; un solo ciclo de propuesta/archivo ahorra tiempo. Orden: Fusión → Mascotas → POS (el CRÍTICO al final, con puerta de aprobación propia). Alternativa: tres changes, más trazabilidad por riesgo pero 3× overhead; descartada por prioridad de velocidad.

**D2 — POS: "Paga con" por fila de efectivo.** Estado `pagaCon: Record<rowId, string>` en lugar de un string global. Dentro de `PagoRowEditor`, si `metodo === "efectivo"` y el monto es válido > 0, debajo del input de monto se muestran: input "Paga con", atajos `quickCashOptions(montoDeLaFila)` y el vuelto de esa fila (`vueltoCents(pagaCon, monto)`) con el texto "Vuelto" y el aviso "Lo que recibís es menos que el efectivo a cobrar." si corresponde. El vuelto total que se pasa a `onSuccess` es la suma de los vueltos de las filas de efectivo (`null` si ninguna informó "paga con"), por lo que el comprobante no cambia. Al quitar una fila o cambiarla a otro medio se descarta su entrada de `pagaCon`. Se reutilizan `payments.ts`/`pagoRows.ts` sin cambiar sus firmas. Alternativa: prohibir dos filas de efectivo (cambia reglas de cobro → descartada); alternativa: un "paga con" global sobre la suma de efectivo (mantiene ambigüedad en mixtos → descartada).
  - Foco inicial: `CheckoutSheet.onOpenAutoFocus` pasa de buscar `#paga-con` a un atributo estable (`[data-paga-con]`) del primer "Paga con" habilitado, para conservar el comportamiento ("Paga con" recibe el foco y Enter confirma).
  - Compatibilidad de tests: se conservan los `aria-label` "Monto {medio}", el label "Paga con", el texto "Vuelto", y los botones "Agregar otro medio", "Confirmar venta", "Completar", "Reintentar".

**D2b — POS (revisión tras prueba manual, reemplaza lo de varias filas de efectivo de D2).** La usuaria probó D2 y pidió: (a) un único campo en efectivo y (b) que un medio no se repita. Resultado: máximo 3 pagos, uno por medio (opciones ya usadas deshabilitadas en las otras filas; "Agregar otro medio" deshabilitado con 3). La fila de efectivo solo tiene "Paga con" (más atajos y vuelto); el **efectivo a cobrar se deriva**: `max(0, total − suma de los otros medios)`, se muestra como texto y alimenta los drafts que se envían, así que el contrato de pagos (medio + monto) no cambia. `pagaCon` vuelve a ser un único valor (hay una sola fila de efectivo). "Paga con" vacío = pago exacto, sin vuelto (`null` hacia `onSuccess`). Si los otros medios suman ≥ total, el efectivo derivado es 0 y no se puede confirmar ("Sobran"). Riesgo: es el único punto donde un monto enviado deja de ser tipeado → tests de importes exactos (mixto 38.500 → efectivo 20.000) y de no-regresión del payload.

**D3 — Fusión: `/productos` es la ruta canónica; `/stock` redirige.** Una sola tabla alimentada por `useStockList` (`GET /api/stock`, que ya trae precio, costo, margen y `bajo_minimo`) cuando no hay búsqueda y por `/productos/buscar` cuando la hay (igual que hoy). Columnas: SKU, Producto (nombre + marca · categoría), [dueña: Costo, Margen], Precio, Stock, Mínimo, Estado (`StockBadge`), Acciones (dueña: Editar, Margen y mínimo, Ajustar stock, Dar de baja). Se incorporan el banner de alertas (`useAlertasStock`) y el toggle "Solo bajo mínimo" con paginación. Se reutilizan `ProductoSheet`, `MargenMinimoDialog`, `AjusteStockDialog`, `StockBadge`, `DataTable`; `StockPage.tsx` se elimina y la carpeta `features/stock` conserva lo que se reutilice (`ajuste.ts`, `AjusteStockDialog`, `StockBadge`, `api.ts`). Nav: una entrada "Productos y stock" con badge (`alertas: true`). Redirect de `/stock` a `/productos` con `<Navigate replace>`, conservando el query string. Alternativa: nueva ruta `/inventario` (rompe marcadores sin ganancia → descartada).

**D4 — Mascotas dentro del módulo `clientes`, no un módulo propio.** Una mascota no existe sin cliente y no tiene reglas propias; el CLAUDE.md prohíbe que un módulo importe el router de otro, así que un módulo nuevo solo sumaría fricción. Modelo `Mascota(Base, AuditMixin)` en `clientes/models.py`: `id` String(36) uuid, `cliente_id` FK `clientes.id` (índice), `nombre` String(100) no nulo, `tipo` String(10) no nulo. Soft-delete por `activo` (consistente con Cliente).

**D5 — `tipo` como enum cerrado `perro|gato|otro`** (Pydantic `Literal`, columna String con `CheckConstraint`), no texto libre ni enum nativo de Postgres: cumple lo pedido ("perro, gato, otro...") con validación estricta y sin la fragilidad de alterar un tipo ENUM en migraciones futuras. Si luego hace falta más detalle, se agrega un campo opcional sin romper nada.

**D6 — RBAC de mascotas = el de cliente**: alta `duena`+`mostrador`; editar/baja `duena`; listar autenticado. Es una suposición (la dueña no lo especificó) y es de bajo costo cambiarla. Endpoints en el router de clientes: `POST/GET /clientes/{id}/mascotas`, `PUT/DELETE /clientes/{id}/mascotas/{mascota_id}`. Listado sin paginación (pocas por cliente), orden por `created_at`.

**D7 — Frontend de mascotas**: sección `<section aria-labelledby="mascotas-titulo">` en `ClienteDetallePage` entre datos e historial, con lista simple, `MascotaSheet` (react-hook-form + zod, patrón de `ClienteSheet`, `Select` shadcn para el tipo) y `ConfirmDialog` para la baja. Hooks nuevos en `clientes/api.ts` y clave `queryKeys.clientes.mascotas(id)`.

## Risks / Trade-offs

- [POS es dinero] → No se toca `checkout.ts`, `payments.ts`, `useCheckout.ts` ni backend; los tests existentes de cobro se mantienen y se agregan los nuevos primero (TDD). Puerta de aprobación antes del bloque 3.
- [Selectores de tests/foco dependen de `#paga-con`] → atributo `data-paga-con` y test explícito de foco inicial y de Enter en `PosCheckoutFlow`.
- [Dos filas de efectivo con "Paga con" duplica el label] → el nombre accesible incluye el medio/posición solo cuando hay más de una; con una sola fila queda "Paga con".
- [Fusión: `useStockList` no pagina al buscar y busca con `page_size=100`] → se mantiene el comportamiento actual de la búsqueda; no se amplía alcance.
- [Mostrador veía Productos y Stock sin acciones] → se mantiene: sin costo/margen/acciones.
- [Cambio de ruta `/stock`] → redirect con `replace`; tests de nav y badge actualizados.

## Migration Plan

Migración Alembic `0010_mascotas` (crear tabla `mascotas` + índice por `cliente_id` + check de `tipo`), `down_revision = "0009"`, con `downgrade` que elimina la tabla. Actualizar `tests/infra/test_migration_0009.py` (cabeza `0010`) o su sucesor. Despliegue: migrar antes de levantar el backend; rollback: `alembic downgrade 0009` (pierde solo mascotas cargadas). Registrar `Mascota` en `app/modules/models.py` (después de `clientes`). Actualizar `knowledge-base/04_modelo_de_datos.md` (entidad y ERD) y `CHANGES.md` (C-17).
