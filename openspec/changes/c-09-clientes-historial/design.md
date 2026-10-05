# Design

## Context

Ver `proposal.md` (Why) y `specs/clientes/spec.md` (contrato de comportamiento).
Estado verificado en código:

- `backend/app/models.py` ya define `Cliente(Base, AuditMixin)` con `id`
  (String(36) uuid), `nombre` (NOT NULL), `telefono`, `email`, `direccion`
  (nullable) y `saldo_cc Numeric(10,2) NOT NULL default 0`. La tabla `clientes`
  la crea la migración `0002_core_models.py` (C-02) con esas mismas columnas
  y **sin índices** aparte de la PK. La última migración es `0006_compras`.
- No existe router ni schemas de clientes. `Venta` no existe (llega en C-10).
- Patrones a reutilizar: `backend/app/routers/distribuidoras.py` y
  `productos.py` (`_to_response`, `_get_or_404`, soft-delete, pre-check +
  `409`, ruta fija `/comparar`/`/buscar` declarada antes de `/{id}`,
  paginado `page`/`page_size` 20/100 con `PaginacionResponse`);
  `backend/app/deps.py` (`get_current_user`, `require_role`, `require_duena`);
  `backend/app/schemas.py` (`extra="forbid"`, `strict=True`, `EMAIL_PATTERN`,
  `_nombre_no_vacio`).
- `email-validator` **no** es dependencia (`backend/requirements.txt`); los
  emails de usuarios se validan con `EMAIL_PATTERN`.
- Matriz RBAC (`knowledge-base/03_actores_y_roles.md`): Clientes → dueña
  CRUD, mostrador "ver + crear". La spec `auth-rbac` ya lo prevé.
- KB `10_preguntas_abiertas.md`: "¿Cuenta corriente de clientes en v1 o solo
  historial?" sigue abierta (Media).
- `CHANGES.md` §[C-09] dice "Migración 006: tabla cliente": está desactualizado
  (la tabla existe desde `0002`; `0006` es compras).

## Goals / Non-Goals

**Goals:**

- Exponer clientes con los mismos guards, envelope y convenciones que C-04/C-06.
- Búsqueda útil en el mostrador (sin acentos, por fragmento de teléfono) que
  se comporte igual en SQLite (tests) y Postgres (prod).
- Dejar a C-10 un contrato claro: `cliente_id` nullable y un dueño explícito
  del historial.

**Non-Goals:**

- Cambios de schema de base (ni columnas ni índices); cuenta corriente;
  historial de ventas; UI del selector (C-13); deduplicación/merge de clientes;
  reactivar clientes dados de baja.

## Decisions

- **D1 — Sin migración en C-09.** La tabla `clientes` ya tiene todas las
  columnas que pide la KB. No se agrega índice: un petshop maneja del orden de
  cientos a pocos miles de clientes, y la búsqueda de D6 usa una expresión
  normalizada que un índice trgm sobre la columna cruda no aprovecharía; un
  scan secuencial es de milisegundos a esa escala. Tampoco se agrega
  constraint de unicidad (ver D5). Alternativas: (a) `0007` con índice trgm
  sobre `clientes.nombre` — descartada, no sirve para la expresión sin
  acentos; (b) `0007` con columna normalizada `busqueda` + índice trgm —
  diferida hasta que el volumen lo justifique (cambio interno, no altera la
  spec). Consecuencia: `0007` queda libre para C-10, y la línea
  "Migración 006: tabla cliente" de `CHANGES.md` se corrige al archivar
  (tarea 6.2).

- **D2 — El historial `GET /api/clientes/{id}/ventas` se difiere a C-10.**
  Depende de `Venta`, que es de C-10 (governance CRITICO). Opciones:
  (a) **diferir a C-10 (recomendada)**: C-09 entrega CRUD + búsqueda; C-10,
  que crea `Venta.cliente_id`, agrega en su delta un requirement ADDED
  "Historial de ventas por cliente" sobre la capability `clientes`, junto con
  el endpoint y sus tests; (b) publicar ahora el endpoint devolviendo lista
  vacía — descartada: contrato engañoso que parece funcionar y no puede
  testear nada real; (c) crear un stub de `Venta` en C-09 — descartada: invade
  los modelos de un change CRITICO y fuerza una migración que C-10 tendría que
  rehacer. Con (a), al archivar C-09 se mueven en `CHANGES.md` el endpoint y
  el test "historial por cliente" de §[C-09] a §[C-10] (tarea 6.2). El nombre
  del change conserva "historial" por trazabilidad con el roadmap.

- **D3 — Router `routers/clientes.py` clonando `distribuidoras.py`; RBAC por
  matriz.** `POST` → `require_role("duena", "mostrador")` (explícito, aunque
  hoy equivale a cualquier autenticado: si aparece un rol nuevo no hereda el
  alta); `PUT`/`DELETE` → `require_duena`; `GET` (listar, buscar, por id) →
  `get_current_user`. Handlers sync con `Session`, como el resto del backend
  (la consistencia con el código existente prima sobre el estilo async /
  `Annotated` de la plantilla del registry). Sin capa de servicio: es CRUD
  más un filtro de búsqueda. Alternativa: mostrador también edita (ver
  "Decisiones a revisar").

- **D4 — Schemas estrictos con normalización en el borde.**
  `ClienteCreate {nombre, telefono?, email?, direccion?}`,
  `ClienteUpdate` (todos opcionales, parcial vía `exclude_unset`),
  `ClienteResponse {id, nombre, telefono, email, direccion, activo,
  created_at, updated_at}` y `ClienteListResponse(PaginacionResponse)`.
  `extra="forbid"`, `strict=True`. Validadores `mode="before"`: opcional en
  blanco → `None`; `nombre` con `_nombre_no_vacio` + trim (máx. 200);
  `email` trim + minúsculas y luego `EMAIL_PATTERN` (máx. 320);
  `telefono` normalizado (quita espacios, `-`, `.`, `(`, `)`; conserva `+`
  inicial) y luego patrón `^\+?\d{6,20}$`; `direccion` máx. 300. En
  `ClienteUpdate`, `nombre: null` explícito → `422` (a diferencia de
  `DistribuidoraUpdate`, que lo dejaría pasar hasta la base). Las funciones
  puras `sin_acentos`, `solo_digitos` y `normalizar_telefono` viven en
  `backend/app/core/texto.py`, con tests unitarios propios, y las usan tanto
  los schemas como la búsqueda. No se agrega `email-validator`: el patrón
  existente alcanza para v1 y evita una dependencia nueva.

- **D5 — Email único entre clientes activos, a nivel aplicación.** Pre-check
  en alta y edición: si existe otro cliente con `activo=True` y el mismo
  email (se guarda en minúsculas; la comparación igual usa `lower()`) →
  `409 "email ya registrado"`; en edición se excluye al propio cliente.
  Teléfono no es único (familias y comercios comparten número) y el nombre
  tampoco. El email de un cliente dado de baja se puede reutilizar, coherente
  con soft-delete. Alternativas: (a) índice único parcial
  `ON clientes (lower(email)) WHERE activo AND email IS NOT NULL` en `0007`
  (Postgres y SQLite lo soportan) — cierra la carrera, pero agrega migración
  por un riesgo despreciable con uno o dos puestos de venta; (b) sin
  unicidad — descartada: el alta inline en el mostrador tiende a duplicar
  clientes y el email es el único dato con identidad fuerte.

- **D6 — Búsqueda portable sin acentos con expresiones SQL estándar.** Del
  lado Python, `q` se recorta, se colapsan espacios, se pasa a minúsculas y se
  le quitan acentos (`unicodedata` NFKD sin marcas combinantes; `ñ→n`). Del
  lado SQL, la columna `nombre` se pliega con `replace()` anidados para
  `á é í ó ú ü ñ` y sus mayúsculas, y después `lower()` (SQLite solo baja
  ASCII, por eso se reemplazan también las mayúsculas acentuadas). Filtro:
  `activo AND (nombre_plegado LIKE %q% OR lower(email) LIKE %q% OR
  telefono LIKE %digitos(q)%)`; la rama de teléfono se agrega **solo** si
  `q` tiene dígitos (si no, `%%` matchearía todo). Se usa
  `contains(..., autoescape=True)` para que `%` y `_` escritos por la
  usuaria no sean comodines. Orden `nombre, id`; paginado 20/100 como
  productos. Alternativas: extensión `unaccent` de Postgres — descartada, no
  existe en SQLite y los tests divergirían de prod; columna normalizada
  persistida (D1-b) — diferida.

- **D7 — Ruta `/buscar` antes de `/{cliente_id}` y `q` validada.** Igual que
  `/comparar` en C-06 y `/buscar` en C-04: declaración en orden. `q`
  obligatoria (`min_length=1`, `max_length=100`); si queda vacía tras el trim
  → `422`. Un test verifica que `/buscar` no se resuelve como id (`404`).

- **D8 — `saldo_cc` reservado: fuera de todos los schemas.** No está en
  `ClienteCreate`/`ClienteUpdate`, así que enviarlo da `422` por
  `extra="forbid"`; tampoco está en `ClienteResponse`. Se mantiene el default
  0 de la base (spec `core-models`). Agregar el campo más adelante es un
  cambio no-breaking; quitarlo una vez expuesto sería breaking, y exponer un
  "saldo" siempre en 0 invita a la UI a mostrar una cuenta corriente que no
  existe. Alternativa: exponerlo de solo lectura (ver "Decisiones a revisar").

- **D9 — Soft-delete y lecturas.** `DELETE` → `activo=False`. `GET /{id}` no
  filtra inactivos (como productos/distribuidoras: sirve para el futuro
  historial de una venta vieja); listado y búsqueda sí. `PUT` sobre un
  cliente inactivo está permitido para la dueña (corregir datos), y la
  unicidad de email solo se evalúa contra activos. Sin endpoint de
  reactivación en v1. Contrato para C-10: rechazar `cliente_id` inexistente
  o inactivo al crear una venta (el código de error lo define C-10).

## Risks / Trade-offs

- [Shadowing de `/buscar` por `/{id}`] → Mitigación: orden de declaración + test dedicado (D7).
- [Carrera en la unicidad de email (dos altas simultáneas)] → Se acepta: uno o dos puestos de venta; si pasa, la dueña da de baja el duplicado. La alternativa D5-a la cierra si hiciera falta.
- [El plegado de acentos solo cubre el castellano (`á é í ó ú ü ñ`)] → Suficiente para el dominio; la lista de reemplazos es una constante extensible. Un test fija que Python y SQL pliegan igual.
- [Scan secuencial en búsqueda] → Despreciable con miles de filas; D1-b es el camino si el volumen crece.
- [Orden por nombre con acentos difiere entre SQLite y Postgres (collation)] → Los tests no dependen del orden entre nombres que solo difieren en acentos.
- [La normalización de teléfono rechaza internos o texto ("int. 23")] → Se responde `422` con mensaje claro; el dato extra va en `direccion`. Se acepta para v1.
- [Contrato historial pendiente] → Queda escrito en D2 y en la tarea 6.2 para que C-10 lo levante; no se pierde al archivar.

## Migration Plan

1. Sin migración de base (D1): `alembic upgrade head` no cambia.
2. Desplegar la API (router nuevo registrado en `main.py`, sin tocar
   endpoints existentes). Rollback: revertir el router; ningún dato depende
   de C-09 (los clientes creados quedan en una tabla que ya existía).
3. Verificar: `GET /api/health`, alta con solo nombre como mostrador, búsqueda
   `q=jose` encontrando "José".

## Decisiones a revisar por la usuaria

Tomadas con un default recomendado; cambiarlas modifica spec y tareas:

- **D2** historial diferido a C-10 (alternativas: endpoint vacío ahora; stub
  de `Venta` en C-09 — ambas desaconsejadas).
- **D5** email único entre activos con `409`, teléfono no único (alternativas:
  sin unicidad; unicidad también por teléfono; constraint en base con `0007`).
- **D3** mostrador solo ve y crea, según la matriz de la KB (alternativa:
  mostrador también edita, para corregir un teléfono mal cargado en la
  venta; la baja seguiría siendo solo de la dueña).
- **D8** `saldo_cc` oculto y no editable en v1 (alternativa: exponerlo de
  solo lectura). Si la dueña decide tener cuenta corriente en v1, eso es un
  change propio (movimientos de saldo y cobros), no un campo editable.

## Open Questions

- Ninguna bloqueante. Deferible sin cambiar specs ni tareas: el tamaño de
  página default (se adopta 20 / máx. 100 como C-04/C-06).
