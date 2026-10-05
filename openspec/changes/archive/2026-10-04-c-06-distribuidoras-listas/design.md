# Design

## Context

Ver `proposal.md` (Why) y `specs/distribuidoras/spec.md` (contrato de comportamiento).
Estado verificado en código: `backend/app/models.py` ya define `Distribuidora`
(nombre, contacto, cuit, condiciones + `AuditMixin`) y `ListaPrecio`
(distribuidora_id, producto_id, costo + unique pair) — creadas por migraciones
`0002` (C-02) y `0003` (C-04). No existe router ni schemas de distribuidoras;
`ListaPrecioCreate` plana de C-04 es solo persistencia. Patrones a reutilizar:
`backend/app/routers/productos.py` (CRUD + `_get_or_404` + soft-delete +
`require_duena` en escritura / `get_current_user` en lectura) y
`backend/app/deps.py` (`require_duena`). Próximo número de migración: `0005`.

## Goals / Non-Goals

**Goals:**

- Exponer distribuidoras y listas con los mismos guards y convenciones que C-04/C-05.
- Comparar costos por origen con precio sugerido calculado al vuelo (sin persistir).
- Dejar la base lista para C-07 (pedidos referencian distribuidoras existentes).

**Non-Goals:**

- Cambios de columnas en modelos existentes; frontend (llega en C-13);
  pedidos/entradas/pagos (C-07); validación formal de CUIT contra ARCA.

## Decisions

- **D1 — Sin cambios de schema de columnas; migración `0005` solo-índice.**
  Los modelos están completos. La `0005` crea
  `ix_lista_precio_producto_id` sobre `lista_precio(producto_id)` porque el
  unique `(distribuidora_id, producto_id)` de `0003` no sirve al filtrar solo
  por producto (columna izquierda = distribuidora). Alternativa (no migrar):
  descartada — comparar por producto sería full scan al crecer las listas.
- **D2 — Router `routers/distribuidoras.py` clonando `productos.py`.**
  Mismo esqueleto: `_get_or_404`, `_to_response`, `IntegrityError → 409`,
  `require_duena` en POST/PUT/DELETE, `get_current_user` en GET, soft-delete
  en DELETE. Alternativa (servicio separado): innecesario a este tamaño; la
  lógica es CRUD + un cálculo puro.
- **D3 — Schemas anidados nuevos, plano de C-04 intacto.**
  `ListaPrecioDistribuidoraCreate {producto_id, costo}` (sin distribuidora en
  body — va en el path) y `ListaPrecioUpdate {costo}`; `DistribuidoraCreate /
  Update / Response`, `ListaPrecioResponse`, `CompararFila {distribuidora_id,
  distribuidora_nombre, costo, precio_sugerido}` + `CompararResponse
  {producto_id, filas}`. Estrictos (`extra="forbid"`, `strict=True`,
  `_coerce_decimal` y serializador Decimal como en `schemas.py`).
- **D4 — Comparar calculado en Python con `Decimal`, ordenado por costo.**
  Join `lista_precio → producto` por `margen_pct` vigente;
  `precio_sugerido = costo × (1 + margen_pct)` en Python (no reutilizar el
  `column_property` sobre instancias transient). Filtra distribuidoras
  activas; orden `costo ASC` en la query. Solo lectura, sin transacción de
  escritura.
- **D5 — Orden de rutas: `/comparar` ANTES que `/{id}`.**
  FastAPI matchea en orden de declaración; `/comparar` después de
  `/{distribuidora_id}` sería tragado como un id. El router declara primero
  la ruta fija y luego las parametrizadas (gotcha documentado en tests).
- **D6 — Soft-delete no rompe referencias.**
  Borrar distribuidora = `activo=False`; sus listas siguen legibles pero se
  excluyen de comparar; `producto.distribuidora_default_id` queda intacto
  (como en productos: el GET por id no filtra inactivos). Sin cascadas.

## Risks / Trade-offs

- [Shadowing de `/comparar` por `/{id}`] → Mitigación: orden de declaración + test que llama a comparar con datos reales.
- [Carrera en unique (distribuidora, producto)] → Mitigación: pre-check + `catch IntegrityError → 409`, igual que SKU en `productos.py`.
- [Divergencia de fórmula de precio vs `column_property`] → Mitigación: test que compara `precio_sugerido` de comparar contra `precio_venta` del producto para el mismo costo; una sola constante de fórmula documentada.
- [CUIT free-form en v1] → Se acepta string libre (≤20); la validación formal es de C-11 (ARCA). Registrado como supuesto, no como deuda oculta.

## Migration Plan

1. Aplicar `0005` (solo `CREATE INDEX`, sin datos): `alembic upgrade head`.
2. Desplegar API (router nuevo, sin tocar endpoints existentes) — rollback:
   `alembic downgrade -1` + revert del router; ningún dato depende de C-06.
3. Verificar: `GET /api/health`, CRUD distribuidora smoke, comparar con 2 orígenes.

## Open Questions

- Ninguna bloqueante. Deferrable sin cambiar specs ni tareas: paginado de
  `GET /api/distribuidoras` (se adopta el envelope `BusquedaResponse`-like de
  C-04 por consistencia; tamaño 20 por defecto).
