# Design

## Context

Observado en el código actual (ver proposal.md para la motivación):
- `Cliente` y `Mascota` no tienen `relationship` (solo `Mascota.cliente_id`). `ClienteResponse` es `extra="forbid", strict=True` y se usa en POST, PUT, GET por id, lista y `/buscar`; el listado lo arma `router._lista()` con `_to_response` campo por campo. `_paginar` devuelve `(list[Cliente], total)`.
- `ClienteUpdate` es parcial (`exclude_unset`). `actualizar_cliente` hace un único `commit` y hoy edita también clientes de baja. Las funciones de mascota (`crear_mascota`, `actualizar_mascota`, `desactivar_mascota`) hacen `commit` interno, por lo que no se pueden encadenar en una sola transacción; `crear_cliente` (C-18) ya resuelve el alta atómica con `flush` + un `commit` + `rollback` ante error.
- Frontend: la columna de acciones y las columnas de `ClientesPage` se arman en un array; `ClienteSheet` usa react-hook-form + zod con campos planos de mascota solo en alta; `MascotaFields` recibe un `register`/valor puntual (no `control`) y arma ids con un prefijo. Las mutaciones de mascota de la ficha invalidan solo `queryKeys.clientes.mascotas(id)`, por lo que la tabla quedaría desactualizada.
- `useClientesIndex` (ventas) pagina toda la lista de clientes y la reutiliza el POS: recibirá el campo `mascotas` sin usarlo.

## Goals / Non-Goals

**Goals:** ver las mascotas en la tabla; editarlas desde "Editar cliente" en un solo guardado atómico; que ficha, tabla y edición queden coherentes.

**Non-Goals:** cambiar el alta (una mascota opcional), mostrar mascotas en POS/ventas, paginación o búsqueda por nombre de mascota, un límite de cantidad en UI más allá del validado en backend, un schema nuevo en la base.

## Decisions

**D1 — La lista incluye `mascotas` con una consulta agrupada.** `ClienteListItem(ClienteResponse)` agrega `mascotas: list[MascotaResponse]` y se usa **solo** en `ClienteListResponse` (lista y `/buscar`); POST/PUT/GET por id y el POS no cambian de forma. Tras `_paginar`, un helper `_mascotas_activas_por_cliente(db, ids)` hace una sola consulta `Mascota.cliente_id IN (ids) AND activo` ordenada por `created_at, id` y agrupa en un `dict`. Alternativa: `relationship` + `selectinload` con filtro de activas (modifica el modelo y es más invasivo) → descartada; consultar por cliente (N+1) → descartada. `useClientesIndex` (ventas) recibe el campo extra sin cambios (costo: una consulta barata por página de 100).

**D2 — La edición es atómica en `PUT /api/clientes/{id}`.** `ClienteUpdate` suma `mascotas: list[MascotaEdicion] | None` con `MascotaEdicion = {id?: str, nombre, tipo}` (nombre 1–100 recortado, tipo perro|gato|otro, `extra=forbid`). Semántica: ausente → no se tocan (`"mascotas" in cambios` con `exclude_unset`); `null` → 422; lista → **reemplazo**: con `id` de una mascota activa del cliente se actualiza, sin `id` se crea, las activas no incluidas se dan de baja; `[]` da de baja todas. Validaciones en el schema: máximo 20, `id` no repetidos (422). En el servicio: `actualizar_cliente` aplica datos + mascotas en una transacción (`try/commit/except rollback; raise`), con helpers internos **sin commit** (`_aplicar_mascotas`, y los públicos actuales quedan como wrappers que hacen commit). Si el payload trae `mascotas` se exige cliente activo (`_obtener_cliente_activo` → `ClienteInactivo` → 409); sin `mascotas` el comportamiento actual (editar clientes de baja) no cambia. Un `id` ajeno/inexistente/dado de baja → `MascotaNoEncontrada` → 404 con rollback total. El PUT sigue respondiendo `ClienteResponse` (sin mascotas): el frontend invalida y recarga. Alternativa: llamadas por mascota desde el frontend (N+1 requests, commits independientes y fallo parcial difícil de explicar) → descartada.

**D3 — Frontend de la columna.** Nueva columna `mascotas` en `ClientesPage` antes de "Acciones": texto `Nombre (Tipo)` separado por coma con `TIPO_MASCOTA_LABEL`, o "—". Tipo `ClienteListItem = Cliente & { mascotas: Mascota[] }` solo para la lista (`Paginated<ClienteListItem>`); el resto de las pantallas siguen con `Cliente` (la fixture `makeCliente` no cambia, hay un `makeClienteLista`).

**D4 — Frontend de la edición.** `ClienteSheet` en modo edición carga las mascotas del cliente con la query existente de la ficha (`queryKeys.clientes.mascotas(id)`; está en caché si se vino de la ficha, así sirve tanto desde la lista como desde la ficha y siempre trae lo vigente). Mientras carga muestra un `Skeleton` etiquetado y no incluye `mascotas`; si falla muestra un aviso y se guarda **sin** `mascotas` (la edición de datos sigue funcionando). Con datos, el formulario usa `useFieldArray` (`mascotas`: `{id?, nombre, tipo}`) y el `PUT` siempre envía la lista completa. Cada fila es un subcomponente `MascotaFila` (necesita `useController` para el `Select` shadcn) que reusa `MascotaFields` con un prefijo único por fila (`cliente-mascota-${field.id}`) y labels "Nombre de la mascota N"/"Tipo de la mascota N", más un botón "Quitar mascota N" y un botón "Agregar mascota". Validación zod con `mascotaSchema` por fila. Los `422` del servidor `mascotas.N.nombre|tipo` se mapean a la fila N. El `409` se distingue por mensaje: "cliente dado de baja" se informa por toast (no en el campo email).

**D5 — Coherencia de cachés.** Las mutaciones de mascota de la ficha (`useCrearMascota`, `useEditarMascota`, `useBajaMascota`) pasan a invalidar `queryKeys.clientes.all` (prefijo que cubre lista, detalle, historial y mascotas); `useEditarCliente` ya invalida `clientes.all`. Así tabla, ficha y edición no quedan viejas.

## Risks / Trade-offs

- [Reemplazo total: `[]` o un guardado desactualizado puede dar de baja mascotas] → la UI siempre parte de las mascotas vigentes cargadas al abrir; es "lo que ves es lo que queda". Last-write-wins en ediciones simultáneas (una sola dueña): aceptable.
- [Cambiar `ClienteUpdate` y los helpers de mascota] → los wrappers públicos mantienen su contrato y sus tests; se agregan tests de atomicidad (monkeypatch como en C-18), ids ajenos, duplicados, tope y cliente de baja.
- [Más tests de frontend afectados: `ClientesPage.test.tsx` ("la edición no muestra el bloque de mascota" se invierte) y mocks de lista] → se actualizan junto con el cambio; las fixtures de lista suman `mascotas`.
- [`DataTable` solo aplica `className` en el encabezado] → la columna no se oculta en móvil (el scroll horizontal es interno de la tabla); no se cambia `DataTable`.
- [Doble fuente de las mascotas en el sheet (lista vs query)] → se usa solo la query para evitar datos viejos de la lista.

## Migration Plan

Sin cambios de schema ni migración. Despliegue normal; rollback: revertir el código (`mascotas` en el PUT es opcional y el campo extra de la lista es aditivo).
