# Proposal

## Why

Al usar la sección de clientes la dueña notó que hay que cargar las mascotas aparte después de crear un cliente, y una auditoría de toda la página (código + prueba en el navegador) encontró problemas reales: la sección "Mascotas" se ve vacía mientras carga o falla, una página fuera de rango muestra "Todavía no hay clientes" aunque haya, los errores de teléfono salen en inglés con prefijo técnico, y un cliente dado de baja sigue aceptando mascotas.

## What Changes

- **Alta de cliente con mascota opcional**: el formulario de "Nuevo cliente" suma "Mascota (opcional)" con nombre y tipo (perro/gato/otro). Vacío = no se crea mascota; si se completa solo uno de los dos campos, se valida. El backend acepta `mascota` opcional en `POST /api/clientes` y crea cliente y mascota en **una sola transacción** (si falla la mascota no queda el cliente). El alta inline del POS **no** pide mascota (sigue solo con nombre).
- **Sección Mascotas robusta** en la ficha: mientras carga muestra un indicador con etiqueta accesible; si la carga falla muestra un error con "Reintentar" (también cuando el refetch falla con datos viejos en pantalla); "Agregar mascota" siempre visible; el tipo se muestra con mayúscula ("Perro").
- **Cliente dado de baja**: la ficha oculta "Editar" y las acciones de mascotas, y el backend rechaza (`409`) crear o editar mascotas de un cliente dado de baja.
- **Paginación**: si la página actual queda vacía pero hay resultados (baja del último de la última página, búsqueda estando en otra página), la lista vuelve a la última página con datos en vez de mostrar el vacío falso. Aplica a la lista de clientes y al historial.
- **Validaciones y mensajes**: el teléfono se valida también en el formulario (mismo criterio que el servidor, mensaje en español); los `422` del servidor se muestran sin el prefijo técnico "Value error,"; los errores de servidor llevan el foco al campo; la búsqueda limita a 100 caracteres.
- **Textos**: el 404 de la ficha deja de sugerir que "pudo haber sido dado de baja" (un cliente de baja sí se muestra).

Fuera de alcance (anotado, no se hace): collation del orden por nombre, doble request al buscar, constraint único de email en BD, texto genérico "Revisá tu conexión" de `ErrorState`, búsqueda por teléfono con guiones del seed, cliente de baja que sigue en el carrito del POS (a verificar aparte).

Sin cambios BREAKING (`mascota` es opcional; el payload actual del POS sigue válido). Sin migración Alembic (no cambia el schema).

## Capabilities

### New Capabilities
<!-- ninguna -->

### Modified Capabilities
- `clientes`: "Alta de clientes por dueña o mostrador" (mascota opcional atómica) y "Mascotas de un cliente" (rechazo para cliente dado de baja).
- `gestion-ui`: "Clientes" (paginación, validaciones, foco y mensajes) y "Mascotas en la ficha del cliente" (estados de carga/error, cliente dado de baja, formato del tipo, mascota opcional en el alta).

## Impact

- Backend: `modules/clientes/{schemas,service,router}.py` y `tests/clientes/`.
- Frontend: `features/clientes/{ClientesPage,ClienteDetallePage,ClienteSheet,MascotasSection,MascotaSheet,clienteForm,mascotaForm,api}.ts(x)` y tests; `shared/api/errors.ts` (prefijo "Value error,"); posiblemente un componente de campos de mascota compartido entre `ClienteSheet` y `MascotaSheet`.
- Specs: `clientes`, `gestion-ui`. KB: `06_funcionalidades.md` (US-007, mascotas en el alta). Gobernanza MEDIA.
