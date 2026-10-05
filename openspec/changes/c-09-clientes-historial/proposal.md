# Proposal

## Why

El mostrador necesita registrar y encontrar clientes rápido para asociarlos a una venta (US-007, "registro e historial básico" del alcance v1). El modelo `Cliente` y la tabla `clientes` ya existen desde C-02 (migración `0002`), pero no hay ninguna API que los exponga: hoy no se puede dar de alta ni buscar un cliente. C-10 (ventas) depende de este change para poder elegir un `cliente_id` (nullable) en la venta.

## What Changes

- `CRUD /api/clientes` con schemas Pydantic estrictos: alta para `duena` y `mostrador` (matriz RBAC "ver + crear"), edición y baja solo `duena`, lectura cualquier usuario activo; baja = soft-delete (`activo=False`), nunca física.
- `GET /api/clientes/buscar?q=`: búsqueda parcial, insensible a mayúsculas y acentos, sobre nombre, email y teléfono (por dígitos), paginada como `GET /api/productos/buscar`; excluye clientes inactivos. Declarada antes de `/{id}`.
- Validación: `nombre` obligatorio no vacío (trim); `email` opcional con el `EMAIL_PATTERN` existente, normalizado a minúsculas; `telefono` opcional normalizado a dígitos (con `+` inicial opcional); strings opcionales en blanco → `null`.
- Duplicados: email único (case-insensitive) entre clientes activos → `409`; teléfono y nombre no son únicos (familias comparten teléfono).
- `saldo_cc` queda **reservado**: no se acepta en el input (`422` por `extra="forbid"`) ni se expone en el output — sin cuenta corriente en v1 (pregunta abierta Media de la KB).
- **Historial `GET /api/clientes/{id}/ventas` se difiere a C-10**: depende de `Venta`, que no existe hasta C-10. C-09 no publica un endpoint vacío ni crea modelos de ventas.
- **Sin migración**: la tabla `clientes` ya tiene todas las columnas; la búsqueda no requiere índice nuevo a la escala de un petshop. La línea "Migración 006: tabla cliente" de `CHANGES.md` es obsoleta y se corrige al archivar.
- Schemas nuevos en `backend/app/schemas.py`: `ClienteCreate`, `ClienteUpdate`, `ClienteResponse`, `ClienteListResponse`.
- Tests TDD (RED-first): CRUD, RBAC por rol, búsqueda, normalización y duplicados.

## Capabilities

### New Capabilities

- `clientes`: registro, edición, baja lógica, listado y búsqueda de clientes de mostrador con RBAC dueña/mostrador (US-007). El historial de ventas por cliente se agregará a esta capability en C-10.

### Modified Capabilities

- (vacío — `core-models` ya especifica la persistencia de `Cliente` con `saldo_cc` default 0 y no cambia; `auth-rbac` ya prevé "ver/crear clientes" para mostrador; este change agrega comportamiento nuevo en una capability nueva).

## Impact

- Nuevo: `backend/app/routers/clientes.py` + registro en `backend/app/main.py`; schemas nuevos; tests `backend/tests/test_clientes*.py`. Sin migración, sin dependencias nuevas (no se agrega `email-validator`).
- Sin breaking changes: ningún endpoint ni tabla existente se modifica.
- Contrato para C-10: `cliente_id` nullable en `Venta`; C-10 valida que el cliente exista y esté activo, y suma `GET /api/clientes/{id}/ventas`.
- Contrato para C-13: el selector "crear/buscar cliente inline" del POS consume `GET /api/clientes/buscar` y `POST /api/clientes` (alta mínima con solo `nombre`). La UI no es parte de C-09.
- Non-goals: cuenta corriente / saldo (v2 o decisión de la dueña), historial de ventas (C-10), UI (C-13), importación de clientes desde Excel.
