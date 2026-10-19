# Tasks

Strict TDD (RED antes de GREEN), TypeScript sin `any`, shadcn, mínimo necesario. Sin commits/PR. Cada grupo deja sus tests y docs en verde. Backend: correr pytest desde `backend/` (`python -m pytest`); la base de desarrollo en Docker ya tiene la migración 0010 (este change no agrega migraciones).

## 1. Backend: alta atómica con mascota y cliente de baja

- [x] 1.1 Safety net: correr `tests/clientes` y anotar el baseline en verde.
- [x] 1.2 RED/GREEN schemas: `ClienteCreate.mascota: MascotaCreate | None = None`; tests en `test_clientes_schemas.py` — con mascota válida, `mascota: null`, mascota inválida (tipo, nombre vacío), campo desconocido dentro de `mascota` y en el cliente sigue rechazado. Verificación: tests en verde.
- [x] 1.3 RED/GREEN servicio: `crear_cliente` con `flush` + mascota + un solo `commit`; tests en `test_clientes_service.py` — crea cliente y mascota juntos; si falla al guardar la mascota (simulado) no queda el cliente (rollback); sin mascota se comporta igual que hoy. Verificación: tests en verde.
- [x] 1.4 RED/GREEN API: tests en `test_clientes.py` — `POST /clientes` con mascota → 201 y `GET /clientes/{id}/mascotas` la devuelve; mascota inválida → 422 y no se crea el cliente; payload actual del POS `{nombre}` sigue 201; mostrador puede crear con mascota. Verificación: en verde.
- [x] 1.5 RED/GREEN cliente de baja: `crear_mascota`/`actualizar_mascota` de cliente inactivo → error de dominio → `409` en el router; `GET` de mascotas sigue 200; tests en `test_mascotas.py` y `test_mascotas_service.py`. Verificación: en verde.
- [x] 1.6 Correr la suite completa de backend en background y `ruff check`. Verificación: todo en verde.

## 2. Frontend: alta con mascota opcional y formulario de cliente

- [x] 2.1 Safety net: correr `src/features/clientes` y `src/shared` (baseline en verde).
- [x] 2.2 RED/GREEN `clienteForm.ts` (+ `clienteForm.test.ts`): campos `mascotaNombre`/`mascotaTipo`; `aPayloadCliente` incluye `mascota` solo si hay nombre; validación nombre sin tipo / tipo sin nombre; teléfono validado con mensaje en español. Verificación: tests unitarios en verde.
- [x] 2.3 Extraer `MascotaFields` de `MascotaSheet` (sin cambiar su comportamiento) y usarlo en `ClienteSheet` solo en modo alta ("Mascota (opcional)", tipo sin elegir al inicio); mapear `422` de `mascota.nombre|tipo` y `shouldFocus` en `setError` de ambos sheets. Tests en `ClientesPage.test.tsx`: alta con mascota envía `mascota`, alta sin mascota no la envía, mascota a medio completar muestra el error y no envía, edición de cliente no muestra el bloque, "Cliente creado" y la mascota visible en la ficha. Verificación: en verde y `tsc`.
- [x] 2.4 `shared/api/errors.ts`: quitar el prefijo `Value error, ` de los mensajes 422 (con test en el archivo de tests de errores). Verificación: en verde junto con las pantallas que lo usan (`npx vitest run src/shared src/features`).
- [x] 2.5 Lista de clientes: `maxLength={100}` en la búsqueda y corrección de página fuera de rango (volver a la última página con datos); tests — baja del único cliente de la página 2 muestra la página 1 sin el vacío falso, búsqueda con más de 100 caracteres limitada. Verificación: en verde.

## 3. Frontend: ficha del cliente y sección Mascotas

- [x] 3.1 RED/GREEN `MascotasSection`: `Skeleton` con `aria-busy`/etiqueta "Cargando mascotas"; error con "Reintentar" cuando `isError` (sin datos → `ErrorState`; con datos viejos → aviso inline); "Agregar mascota" siempre visible (deshabilitado mientras carga); tipo con `TIPO_MASCOTA_LABEL` ("Perro"). Actualizar los tests existentes que esperan "Firulais · perro" a "Perro" (anotar cuáles). Tests nuevos: 500 → mensaje + reintento exitoso, refetch fallido con datos muestra el aviso. Verificación: en verde.
- [x] 3.2 Cliente de baja en `ClienteDetallePage`/`MascotasSection`: pasar `activo`, ocultar "Editar", "Agregar mascota" y acciones por mascota; el 404 dice "El cliente no existe o el enlace es incorrecto"; el historial vuelve a la última página con datos si queda vacío (reset de página al cambiar de cliente). Tests correspondientes. Verificación: en verde.
- [x] 3.3 Cobertura faltante detectada en la auditoría: tests de error con reintento en la lista de clientes, búsqueda sin resultados y baja con confirmación y toast. Verificación: en verde.

## 4. Cierre

- [x] 4.1 Suite completa de frontend (`npx vitest run`), `npx tsc --noEmit -p .` y `npm run knip`. Verificación: todo en verde.
- [x] 4.2 Verificación manual en el navegador (backend Docker): crear cliente con mascota, sin mascota y con mascota a medio completar; teléfono inválido; baja de cliente y ficha de baja; error de mascotas. Verificación: observación reportada a la usuaria.
- [x] 4.3 Documentar: actualizar `knowledge-base/06_funcionalidades.md` (US-007: mascotas opcionales en el alta) y registrar C-18 en `CHANGES.md`. Verificación: archivos actualizados.
