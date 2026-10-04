# Design

## Context

C-04 dejó `Producto` con `stock_actual`/`stock_minimo` editables vía `PUT` y `PATCH /margen-minimo`, sin `MovimientoStock` (ver `backend/app/models.py:84-120`, `backend/app/routers/productos.py:175-213`). C-03 aporta `require_duena`/`get_current_user` (`backend/app/deps.py:82-100`) y Redis vía `get_redis` con TTLs por env. La cadena Alembic está en `0003` (`backend/alembic/versions/0003_lista_precio.py:14-16`); la siguiente revisión es `0004`. Este change introduce la primera escritura transaccional stock+movi­miento que C-10 reutilizará para ventas. Ver `proposal.md` (Why) y `specs/stock-alertas/spec.md` (contrato).

## Goals / Non-Goals

**Goals:**

- Cerrar el hueco de auditoría: a partir de este change, `stock_actual` solo cambia junto a un movimiento en la misma transacción.
- Lectura de stock filtrable/ordenable y resumen de alertas con degradación elegante sin Redis.
- Migración `0004` manual (no autogenerate ciego), espejando el patrón de `0003`.

**Non-Goals:**

- Descuento por ventas, anulaciones con inverso (C-10) — solo se deja el tipo `venta` reservado en el enum/check.
- Entradas por pedidos (C-07), reportes de reposición (C-14), frontend de stock (futuro o C-13).
- Backfill de movimientos históricos para el stock cargado en C-04: el stock pre-C-05 queda como saldo inicial sin movimientos (decisión documentada, no deuda oculta).

## Decisions

1. **Servicio `services/stock.py::ajustar()` como única vía de mutación.**
   Rationale: concentra transacción + validaciones en un punto testeable que C-07/C-10 reutilizan. Alternativa (lógica inline en cada router) descartada: duplicaría el invariante previo/nuevo y el rollback.
2. **`PUT /productos/{id}` deja de aceptar `stock_actual` (422 si viene).**
   Rationale: es el único endpoint actual que puede mutar stock sin movimiento; cerrarlo es condición de RN-ST-03. Alternativa (ignorar silenciosamente) descartada: ocultaría errores del cliente. `PATCH /margen-minimo` no toca stock y queda intacto.
3. **`bajo_minimo` derivado en lectura (`stock_actual <= minimo`), no columna.**
   Rationale: evita drift entre columna y realidad; el costo es una comparación por fila. Alternativa (columna + trigger/job) descartada: introduce estado redundante y ventanas de inconsistencia.
4. **`orden=rotacion` = cobertura (`stock_actual - stock_minimo`) ascendente en SQL.**
   Rationale: un solo `ORDER BY (stock_actual - stock_minimo)` usa índices existentes sin agregados. Alternativa (rotación por ventas históricas) descartada: no hay datos de ventas hasta C-10.
5. **Job Redis = `SET stock: bajo_minimo` + `GET /stock/alertas` con fallback a DB.**
   Rationale: reutiliza `get_redis` y TTL por env (patrón C-03 rate-limit); el fallback garantiza que la alerta nunca tumbe la lectura. Alternativa (solo DB sin job) descartada: CHANGES.md exige el job y prepara el worker de C-11/C-14.
6. **Migración `0004` manual con enum/check de 4 tipos desde el día uno.**
   Rationale: `venta`/`entrada`/`apertura` quedan reservados para C-07/C-08/C-10 sin segunda migración. Alternativa (solo `ajuste` hoy) descartada: rompería compatibilidad de los próximos changes.
7. **Sin `updated_at` en `MovimientoStock` (solo `created_at`).**
   Rationale: append-only real: sin updates no hay timestamp de modificación que mantener; cualquier `UPDATE/DELETE` a nivel ORM se bloquea (p. ej. sin métodos de escritura en el repositorio + test que lo prueba).

## Risks / Trade-offs

- [Race] Dos ajustes concurrentes calculan el mismo `stock_previo` → Mitigación: transacción con `SELECT ... FOR UPDATE` del producto dentro de `ajustar()`; test de doble ajuste secuencial como mínimo.
- [Drift] Stock pre-C-05 sin movimientos de apertura → Mitigación: documentado como saldo inicial en design + tasks (no backfill); C-08 crea `apertura` para filas nuevas.
- [Redis] Job caído = resumen potencialmente viejo → Mitigación: TTL corto (env, default 60s) + fallback a cómputo directo; el job nunca escribe stock.
- [Check negativo] `ck stock_nuevo >= 0` + validación Pydantic duplican la regla → Aceptado: defensa en profundidad (API da 422 legible, DB es última barrera).
- [Numeración] CHANGES.md dice "Migración 003" pero `0003_lista_precio` ya existe → Mitigación: usar `0004` (hija de `0003`); anotado en tasks.

## Migration Plan

1. Merge solo con C-04 archivado (GATE 4) y branch por change según AGENTS.md.
2. Deploy: aplicar `alembic upgrade head` (0004 crea tabla vacía; cero backfill, cero downtime — lecturas C-04 siguen funcionando).
3. Job Redis arranca con el worker existente; sin Redis, la API sigue (fallback).
4. Rollback: `alembic downgrade -1` elimina `movimiento_stock`; endpoints nuevos desaparecen con el deploy anterior (sin datos huérfanos: nada más referencia la tabla aún).

## Open Questions

- Ninguna que cambie specs, enfoque o tasks. Detalle menor deferido a apply: valor exacto del TTL default del job (propuesto 60s por env `STOCK_ALERT_TTL_S`) y tamaño de página default de `GET /api/stock` (propuesto 20, igual que `MAX_PAGE_SIZE=100` de productos).
