# Proposal

## Why

Hoy las mascotas de un cliente solo se ven dentro de la ficha (`/clientes/:id`), que la dueña no usa: espera verlas directo en la tabla de Clientes y poder editarlas desde "Editar cliente", donde hoy no aparecen. Una mascota cargada al crear el cliente "no se ve" y no se puede corregir desde donde ella trabaja.

## What Changes

- **Columna "Mascotas" en la tabla de clientes**: cada fila muestra las mascotas activas del cliente (por ejemplo "MIMI (Gato), Toby (Perro)", o "—" si no tiene). El listado y la búsqueda de clientes devuelven las mascotas activas de cada cliente en una sola consulta extra por página (sin consultar cliente por cliente).
- **Editar cliente edita también las mascotas**: el formulario "Editar cliente" muestra las mascotas existentes (nombre y tipo editables), permite agregar nuevas y quitar, y todo se guarda junto con "Guardar cambios" en una sola operación atómica (`PUT /api/clientes/{id}` acepta `mascotas`). Solo la dueña edita (el mostrador sigue sin ver la edición).
- **Coherencia**: agregar, editar o dar de baja una mascota desde la ficha actualiza también la tabla; el cliente dado de baja sigue en solo lectura (409 al modificar sus mascotas).
- El alta de cliente (una mascota opcional) no cambia.

Sin cambios BREAKING: `mascotas` es opcional en el PUT (si no viene, no se tocan las mascotas) y la lista solo agrega un campo. Sin migración Alembic (no cambia el schema).

## Capabilities

### New Capabilities
<!-- ninguna -->

### Modified Capabilities
- `clientes`: "Consulta de clientes" y "Búsqueda de clientes" (los items incluyen sus mascotas activas) y "Edición y baja de clientes solo por dueña" (la edición acepta `mascotas` de forma atómica).
- `gestion-ui`: "Clientes" (columna Mascotas y edición de mascotas en "Editar cliente") y "Mascotas en la ficha del cliente" (los cambios se reflejan en la tabla).

## Impact

- Backend: `modules/clientes/{schemas,service,router}.py` y `tests/clientes/`.
- Frontend: `features/clientes/{ClientesPage,ClienteSheet,MascotaFields,api,clienteForm}.ts(x)`, `shared/api/{types,queryKeys}.ts`, fixtures y tests; `features/ventas/api.ts` (`useClientesIndex` carga la lista completa: recibe el campo extra sin usarlo).
- KB: `06_funcionalidades.md` (US-007). Gobernanza MEDIA.
