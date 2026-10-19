# Design

## Context

Auditoría de `/clientes` y `/clientes/:id` (código + prueba en el navegador; ver proposal.md). Observado:
- Lista, búsqueda, sin resultados, 409 de email y alta funcionan en el navegador.
- `MascotasSection` ya tiene `Skeleton` y `ErrorState`, pero `shouldRetry` (`queryClient.ts`) reintenta una vez ante 5xx con 1 s de demora, y durante ese segundo la sección parece vacía (el `Skeleton` no tiene texto ni `aria-busy`); además, un refetch fallido con datos en caché no muestra error y "Agregar mascota" no se renderiza mientras carga o falla.
- `DataTable` ignora `pagination` al decidir el estado vacío: página fuera de rango con `total > 0` muestra "Todavía no hay clientes".
- El 422 del servidor para teléfono llega como "Value error, telefono invalido…" y se muestra crudo (`shared/api/errors.ts`); el formulario no valida el teléfono.
- `crear_mascota` usa `obtener_cliente`, que no filtra inactivos (por diseño D9: `GET /clientes/{id}` devuelve inactivos), así que acepta mascotas de clientes de baja.
- `ClienteCreate` es `extra="forbid", strict=True`; `crear_cliente` hace `add + commit + refresh`. `MascotaSheet` es un Sheet completo con su `useForm`, no reutilizable como campos. El POS crea clientes inline con `{nombre}` (`ClienteSelector`).

## Goals / Non-Goals

**Goals:** alta de cliente con mascota opcional y atómica; sección Mascotas confiable; cliente de baja coherente; paginación y mensajes correctos. Mínimo necesario, sin migración.

**Non-Goals:** collation del orden, doble request en la búsqueda, unique de email en BD, `ErrorState` genérico, búsqueda por teléfono con guiones del seed, mascota en el alta del POS, cliente de baja en el carrito del POS (anotado para verificar aparte).

## Decisions

**D1 — Atómico en backend.** `ClienteCreate.mascota: MascotaCreate | None = None` (anidado, estricto). `crear_cliente` hace `add(cliente)`, `flush()` para obtener el id, `add(Mascota(...))` y un único `commit`; ante error, `rollback` y no queda nada. Alternativa: dos llamadas desde el frontend (`POST /clientes` y luego `POST /clientes/{id}/mascotas`): deja cliente sin mascota si falla la segunda y obliga a manejar el fallo parcial en la UI, además `useCrearMascota` está atado a un `clienteId` existente → descartada. Es compatible hacia atrás (el POS manda solo `{nombre}`).

**D2 — Campos de mascota compartidos.** Extraer `MascotaFields` (nombre + `Select` de tipo con `TIPO_MASCOTA_LABEL`) de `MascotaSheet`, parametrizado por `control`/`register`/`errors` y un prefijo de nombre (`mascota.` en el alta). `ClienteSheet` lo muestra solo en modo alta bajo el título "Mascota (opcional)". Valores del formulario: `mascotaNombre` y `mascotaTipo` (`""` = sin elegir). `aPayloadCliente` agrega `mascota: {nombre, tipo}` solo si hay nombre (si no, la clave no existe, no `null`). Validación zod: nombre sin tipo → error en tipo; tipo sin nombre → error en nombre. Un `422` con loc `body.mascota.nombre|tipo` se mapea a esos campos.

**D3 — Cliente de baja.** Backend: `crear_mascota`/`actualizar_mascota` rechazan con error de dominio → `409` "cliente dado de baja" (`GET` sigue permitido; no se toca `PUT /clientes/{id}` en backend). Frontend: la ficha recibe `activo` y oculta "Editar", "Agregar mascota" y acciones de cada mascota. Decisión de producto asumida (la dueña no la especificó): es coherente con el aviso "Cliente dado de baja" que ya muestra la ficha.

**D4 — Mascotas: estados.** El `Skeleton` pasa a tener `aria-busy`/etiqueta "Cargando mascotas"; el error se muestra con `isError` (no solo cuando `lista === undefined`): sin datos → `ErrorState` con "Reintentar"; con datos viejos → aviso inline con "Reintentar" encima de la lista. "Agregar mascota" siempre visible (deshabilitado mientras carga). El tipo se muestra con `TIPO_MASCOTA_LABEL`.

**D5 — Paginación fuera de rango.** En `ClientesPage` y en el historial de `ClienteDetallePage`: si `!isLoading && items.length === 0 && total > 0 && page > 1`, `setPage(Math.max(1, Math.ceil(total / pageSize)))`. Se resuelve en cada página, sin cambiar `DataTable` (usado en otras pantallas).

**D6 — Mensajes y foco.** `erroresDeCampo` en `shared/api/errors.ts` quita el prefijo `Value error, ` y el teléfono se valida en `clienteSchema` (`^\+?[0-9]{6,20}$` tras quitar espacios/guiones/paréntesis, mensaje "Ingresá un teléfono válido (6 a 20 dígitos)"); `setError(..., { shouldFocus: true })` en `ClienteSheet` y `MascotaSheet`; `SearchField` de clientes con `maxLength={100}`.

## Risks / Trade-offs

- [Cambiar `errors.ts` afecta a otras pantallas] → solo recorta un prefijo técnico; tests de `errors` y de las pantallas que lo usan.
- [El schema anidado cambia `ClienteCreate`] → tests de schema (campo desconocido sigue rechazado), de servicio (rollback) y de API; el `toEqual` del payload en `ClientesPage.test.tsx` sigue válido porque sin mascota la clave no se envía.
- [Rechazar mascotas de cliente de baja puede sorprender] → solo aplica a clientes ya dados de baja; reversible.
- [Reintento de React Query demora 1 s la aparición del error] → se acepta; el indicador de carga etiquetado evita la sensación de "vacío".

## Migration Plan

Sin cambios de schema ni migración. Despliegue normal; en la base de desarrollo (Docker/Postgres) ya está aplicada la 0010. Rollback: revertir el código (la clave `mascota` es opcional).
