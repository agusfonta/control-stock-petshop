# Tasks

## 1. Safety net y helpers de normalización (D4, D6)

- [x] 1.1 Ejecutar suite actual (`pytest backend/tests -x -q`) y registrar baseline "N tests passing"; si algo falla, reportarlo como pre-existente y no tocarlo
- [x] 1.2 RED: escribir `backend/tests/test_texto.py` con tests failing de `sin_acentos` ("José Núñez" → "jose nunez", "ÁÉÍÓÚÜÑ" → "aeiouun", espacios colapsados y trim), `solo_digitos` ("5555-12" → "555512", "ana" → "") y `normalizar_telefono` ("11 5555-1234" → "1155551234", "+54 (11) 5555.1234" → "+541155551234", "abc"/"12345" → error); verificar que fallan por módulo inexistente
- [x] 1.3 GREEN + REFACTOR: crear `backend/app/core/texto.py` con las tres funciones puras (`unicodedata` NFKD, constante de pares de plegado reutilizable por D6) y verificar `test_texto.py` verde

## 2. Schemas Pydantic de clientes (D4, D8)

- [x] 2.1 RED: escribir `backend/tests/test_clientes_schemas.py` con validación failing de `ClienteCreate` (nombre ausente / en blanco → error; email inválido → error; email "Ana@Mail.com " → "ana@mail.com"; teléfono normalizado y teléfono inválido → error; opcional "" / "  " → `None`; `saldo_cc` o campo desconocido → error por `extra=forbid`) y `ClienteUpdate` (vacío ok; `nombre: null` → error; `saldo_cc` → error) y de que `ClienteResponse` no tiene `saldo_cc`; verificar que fallan por schemas inexistentes
- [x] 2.2 GREEN: agregar a `backend/app/schemas.py` `ClienteCreate`, `ClienteUpdate`, `ClienteResponse`, `ClienteListResponse(PaginacionResponse)` (estrictos, validadores `mode="before"` usando `core/texto.py`, `_nombre_no_vacio` y `EMAIL_PATTERN`, sin `saldo_cc`, sin dependencia nueva) y verificar `test_clientes_schemas.py` verde

## 3. Alta, consulta y RBAC (D3, D5, D9)

- [x] 3.1 RED: escribir `backend/tests/test_clientes.py` con tests failing: dueña crea completo-201 con normalización, mostrador crea solo-nombre-201, anónimo-401, nombre-en-blanco-422, `saldo_cc`-en-alta-422, email-duplicado-case-insensitive-409, teléfono-repetido-201, listar-paginado-solo-activos-ordenado-por-nombre (`total`/`total_pages`), get-por-id-200, get-inexistente-404, listar-anónimo-401, respuesta-sin-`saldo_cc`; verificar que fallan (router inexistente)
- [x] 3.2 GREEN: crear `backend/app/routers/clientes.py` (clon de `routers/distribuidoras.py`: `_to_response`, `_get_or_404`, `POST` con `require_role("duena", "mostrador")`, pre-check de email entre activos → `409`, `GET` listado y por id con `get_current_user`), registrarlo en `backend/app/main.py` y verificar que los tests de 3.1 pasan
- [x] 3.3 TRIANGULATE: agregar casos email-de-cliente-dado-de-baja-reutilizable-201 y get-por-id-de-cliente-inactivo-200-con-`activo=false` y verificar que pasan sin cambiar el router (o generalizar si rompen)

## 4. Edición y baja solo dueña (D3, D5, D8, D9)

- [x] 4.1 RED: agregar a `backend/tests/test_clientes.py` tests failing: dueña edita teléfono-200 normalizado con el resto intacto, `nombre: null`-422, `saldo_cc`-en-edición-422 con saldo persistido en 0, email-de-otro-activo-409, mostrador-PUT-403 sin cambios, dueña DELETE-204 con `activo=False` y fila presente, mostrador-DELETE-403, DELETE-inexistente-404; verificar que fallan
- [x] 4.2 GREEN: agregar `PUT` (parcial vía `exclude_unset`, pre-check de email excluyendo al propio cliente) y `DELETE` (soft-delete) con `require_duena` al router y verificar que los tests de 4.1 pasan
- [x] 4.3 TRIANGULATE: agregar caso editar-manteniendo-el-mismo-email-propio-200 (no es duplicado de sí mismo) y verificar que pasa

## 5. Búsqueda de clientes (D6, D7)

- [x] 5.1 RED: escribir `backend/tests/test_clientes_busqueda.py` con tests failing: "jose nun" encuentra "José Núñez", "5555-12" encuentra teléfono `1155551234`, "ANA@" encuentra `ana@mail.com`, "zzz" devuelve vacío aunque haya teléfonos, cliente-dado-de-baja excluido, sin-`q`-422, `q`-en-blanco-422, anónimo-401, "%" no actúa como comodín, paginado con `total`; verificar que fallan
- [x] 5.2 GREEN: agregar `GET /api/clientes/buscar` DECLARADA ANTES que `/{cliente_id}` (D7): `q` normalizada con `core/texto.py`, `nombre` plegado con `replace()` anidados + `lower()`, `lower(email)`, rama de teléfono solo si `q` tiene dígitos, `contains(..., autoescape=True)`, filtro `activo`, orden `nombre, id`, paginado 20/100; verificar que los tests de 5.1 pasan en SQLite
- [x] 5.3 TRIANGULATE: agregar caso `GET /api/clientes/buscar` no se resuelve como id (con `q` responde 200, nunca 404) y caso nombre en mayúsculas acentuadas ("ÁLVAREZ" encontrado por "alvarez"); verificar que pasan y, si hay Postgres disponible (`test_migration_pg.py`), que la búsqueda pliega igual en Postgres

## 6. Integración y cierre

- [x] 6.1 Verificación integral: `pytest backend/tests -q` todo verde (incluye baseline de 1.1 sin regresiones), linter del backend (`ruff`) limpio, `alembic upgrade head` sin cambios (D1: sin migración), y matriz escenario→test: cada `#### Scenario` de `specs/clientes/spec.md` tiene al menos un test; registrar evidencia TDD (Safety Net/RED/GREEN/TRIANGULATE/REFACTOR por grupo) en el resumen de apply
- [x] 6.2 Corregir `CHANGES.md` (en archive, junto con el tilde `[x]`): en §[C-09] reemplazar "Migración 006: tabla cliente" por "Sin migración: tabla `clientes` existe desde `0002` (C-02)" y mover `GET /api/clientes/{id}/ventas` y el test "historial por cliente" a §[C-10] (que agrega el requirement "Historial de ventas por cliente" a la capability `clientes` y valida `cliente_id` inexistente/inactivo); verificar con `git diff CHANGES.md` que solo cambian esas líneas
