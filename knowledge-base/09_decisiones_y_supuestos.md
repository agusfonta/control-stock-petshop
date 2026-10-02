# Decisiones y Supuestos

## Decisiones documentadas

### DD-01 — Arranque limpio (Enfoque B)
**Decisión**: no evolucionar el demo Animall, reimplementar ordenado con UI parecida.
**Contexto**: demo mal empezado pero con look validado.
**Alternativas**: evolucionar demo / híbrido.
**Justificación**: prioridad mantenibilidad + costo bajo, velocidad secundaria.
**Trade-offs**: más tiempo inicial a cambio de menos deuda.

### DD-02 — Granel y vencimientos a v2
**Decisión**: fuera de v1.
**Contexto**: usuario lo confirma (v2).
**Trade-offs**: v1 más simple; prever modelo para no romper en v2.

### DD-03 — Bloqueo duro sin stock + alerta previa
**Decisión**: impedir confirmar sin stock y alertar al llegar al mínimo configurable.
**Justificación**: pedido explícito de la dueña.

### DD-04 — Stack FastAPI + React TS + Postgres + Redis + Docker
**Decisión**: stack dado por el usuario, con Redis para async.
**Justificación**: continuidad con demo + necesidades ARCA/jobs.

### DD-05 — Offline para v2
**Decisión**: diseñar teniéndolo en cuenta sin implementarlo.
**Trade-offs**: no suma complejidad ahora, evita rediseño después.

## Supuestos inferidos

### SU-01 — Un solo local en v1
**Supuesto**: sin transferencias entre sucursales.
**Origen**: Discovery (dueña+mostrador, escala equipo pequeño).
**Riesgo si es falso**: remodelar stock por depósito.
**Cómo validar**: confirmar antes del roadmap.

### SU-02 — Tablet con navegador moderno e internet estable
**Supuesto**: no se optimiza para hardware viejo.
**Riesgo si es falso**: UI lenta en mostrador.
**Cómo validar**: probar en la tablet real en sprint 1.
