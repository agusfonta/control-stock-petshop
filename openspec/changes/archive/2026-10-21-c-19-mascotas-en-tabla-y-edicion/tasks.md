# Tasks

Strict TDD (RED antes de GREEN), TypeScript sin `any`, shadcn, mínimo necesario. Sin commits/PR. Cada grupo deja sus tests y docs en verde. Backend: pytest desde `backend/` con `python -m pytest`. Sin migraciones.

## 1. Backend: la lista y la búsqueda incluyen las mascotas

- [x] 1.1 Safety net: correr `tests/clientes` y anotar el baseline en verde.
- [x] 1.2 RED/GREEN schemas: `ClienteListItem(ClienteResponse)` con `mascotas: list[MascotaResponse]` y `ClienteListResponse.items: list[ClienteListItem]`; `ClienteResponse` no cambia. Tests en `test_clientes_schemas.py`. Verificación: en verde.
- [x] 1.3 RED/GREEN servicio+router: helper `_mascotas_activas_por_cliente(db, ids)` con **una sola consulta extra** por página (`IN (ids)`, solo activas, orden `created_at, id`) usado por lista y `/buscar`; POST/PUT/GET por id no incluyen `mascotas`. Tests en `test_clientes.py`/`test_clientes_busqueda.py`: cliente con activa + dada de baja → solo la activa; sin mascotas → `[]`; la búsqueda también las trae; una página de N clientes ejecuta una consulta de mascotas (contar consultas). Verificación: en verde.

## 2. Backend: edición atómica de mascotas en `PUT /api/clientes/{id}`

- [x] 2.1 RED/GREEN schemas: `ClienteUpdate.mascotas: list[MascotaEdicion] | None` (`{id?, nombre, tipo}`, `extra=forbid`), `null` → 422, máximo 20, `id` repetidos → 422; tests en `test_clientes_schemas.py` (ausente vs `[]` vs lista, límites). Verificación: en verde.
- [x] 2.2 Refactor sin cambio de comportamiento: extraer helpers de mascota sin `commit` y dejar `crear_mascota`/`actualizar_mascota`/`desactivar_mascota` como wrappers con `commit`; los tests de mascotas existentes siguen verdes. Verificación: `tests/clientes` en verde.
- [x] 2.3 RED/GREEN servicio: `actualizar_cliente` aplica datos + mascotas en una transacción (`try/except rollback`): con `id` actualiza, sin `id` crea, las activas no incluidas se dan de baja, `[]` da de baja todas, ausente no toca; `id` ajeno/inexistente/dado de baja → `MascotaNoEncontrada` con rollback total (los datos del cliente tampoco cambian); `mascotas` sobre cliente de baja → `ClienteInactivo`; sin `mascotas` el cliente de baja sigue editable. Test de atomicidad con `monkeypatch` como en C-18. Verificación: en verde.
- [x] 2.4 RED/GREEN API: tests en `test_clientes.py`/`test_mascotas.py` — escenarios del spec (edición sin mascotas no las toca, reemplazo mixto, `[]`, id ajeno → 404 sin cambios, `null`/tipo inválido/duplicados/>20 → 422, cliente de baja → 409, mostrador → 403) y `GET /clientes` refleja el resultado. Verificación: en verde.
- [x] 2.5 Suite completa de backend en background y `ruff check app tests/clientes`. Verificación: todo en verde.

## 3. Frontend: columna "Mascotas" en la tabla y coherencia de cachés

- [x] 3.1 Safety net: correr `src/features/clientes` y `src/features/ventas`/`src/features/pos` que usan clientes (baseline en verde).
- [x] 3.2 RED/GREEN tipos y columna: `ClienteListItem` (`Cliente & { mascotas: Mascota[] }`) en `shared/api/types.ts`, `useClientes` tipado con él, fixture `makeClienteLista` y columna `mascotas` en `ClientesPage` ("Nombre (Tipo)" separadas por coma, "—" si no tiene, también en búsqueda). Tests en `ClientesPage.test.tsx`: varias mascotas, ninguna, búsqueda con resultados. Verificación: en verde y `tsc`.
- [x] 3.3 RED/GREEN coherencia: `useCrearMascota`/`useEditarMascota`/`useBajaMascota` invalidan `queryKeys.clientes.all`; test: agregar una mascota desde la ficha y volver a la lista muestra la mascota nueva. Verificación: en verde.

## 4. Frontend: editar mascotas en "Editar cliente"

- [x] 4.1 RED/GREEN `clienteForm.ts`: campo `mascotas: {id?, nombre, tipo}[]` en modo edición, validación por fila con `mascotaSchema`, `aPayloadCliente` incluye `mascotas` completo solo si se cargaron y no incluye `mascota` (singular) en edición; actualizar `clienteForm.test.ts` (los casos de round-trip y payload). Verificación: unit tests en verde.
- [x] 4.2 RED/GREEN `ClienteSheet`: en edición cargar `useMascotasCliente(id)`; mientras carga mostrar `Skeleton` etiquetado; si falla, aviso y guardar sin `mascotas`; con datos, `useFieldArray` con filas `MascotaFila` (reusa `MascotaFields` con prefijo por fila y labels numerados), botones "Agregar mascota" y "Quitar mascota N". Mapear `422` `mascotas.N.*` a su fila y distinguir el `409` "cliente dado de baja" (toast) del 409 de email. Tests en `ClientesPage.test.tsx` (reemplazar el que dice que la edición no muestra mascotas): ver mascotas existentes, renombrar y guardar (payload con `id`), agregar, quitar, nombre vacío sin enviar, carga fallida guarda sin `mascotas`, mostrador sin edición, cliente de baja. Verificación: en verde, `tsc` y `knip`.
- [x] 4.3 Que la edición funcione también abriendo "Editar" desde la ficha (`ClienteDetallePage`): test de que usa la misma query y que tras guardar la sección Mascotas de la ficha y la tabla se actualizan. Verificación: en verde.

## 5. Cierre

- [x] 5.1 Suite completa de frontend (`npx vitest run`), `npx tsc --noEmit -p .` y `npm run knip`. Verificación: todo en verde.
- [x] 5.2 Verificación manual en el navegador con el backend de Docker: la tabla muestra las mascotas; editar renombrando/agregando/quitando desde "Editar cliente" se ve en la tabla y en la ficha; agregar desde la ficha se ve en la tabla; cliente de baja. Verificación: observación reportada a la usuaria.
- [x] 5.3 Documentar: actualizar `knowledge-base/06_funcionalidades.md` (US-007) y registrar C-19 en `CHANGES.md`. Verificación: archivos actualizados.
