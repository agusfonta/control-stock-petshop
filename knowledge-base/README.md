# Control Stock Petshop — Base de Conocimiento

Base de conocimiento del sistema de mostrador para petshop (un local, dueña + mostrador). Arranque limpio con UI parecida al demo Animall.

## Índice de Archivos

| Archivo | Contenido |
|---|---|
| [01_vision_y_objetivos.md](01_vision_y_objetivos.md) | Propósito, alcance v1, fuera de alcance |
| [02_descripcion_general.md](02_descripcion_general.md) | Stack FastAPI+React+Postgres+Redis, integraciones |
| [03_actores_y_roles.md](03_actores_y_roles.md) | Dueña/mostrador, RBAC |
| [04_modelo_de_datos.md](04_modelo_de_datos.md) | Entidades, ERD, seeds |
| [05_reglas_de_negocio.md](05_reglas_de_negocio.md) | RN-VT/ST/PR/CP/AU |
| [06_funcionalidades.md](06_funcionalidades.md) | US por épica con CA |
| [07_flujos_principales.md](07_flujos_principales.md) | Venta, reposición, migración |
| [08_arquitectura_propuesta.md](08_arquitectura_propuesta.md) | Patrones, dirs, seguridad, env |
| [09_decisiones_y_supuestos.md](09_decisiones_y_supuestos.md) | Enfoque B, v2, supuestos |
| [10_preguntas_abiertas.md](10_preguntas_abiertas.md) | Despliegue, ARCA, MP |
| [11_pagos_mercadopago.md](11_pagos_mercadopago.md) | Cobros MP y conciliación |
| [12_devops_y_despliegue.md](12_devops_y_despliegue.md) | Opciones hosting BE/FE/DB |

## Quick Start para Desarrolladores

1. Entender el dominio → [01](01_vision_y_objetivos.md), [03](03_actores_y_roles.md)
2. Entender los datos → [04](04_modelo_de_datos.md)
3. Entender las reglas → [05](05_reglas_de_negocio.md)
4. Entender la arquitectura → [02](02_descripcion_general.md), [08](08_arquitectura_propuesta.md)
5. Implementar → [07](07_flujos_principales.md), [06](06_funcionalidades.md)
6. Antes de codificar → [10](10_preguntas_abiertas.md)

## Resumen Ejecutivo

V1 ordena ventas con FE, stock con bloqueo y alertas, y compras a distribuidoras para un solo local en tablet. Granel, vencimientos, offline total y veterinaria van a v2. Stack mantenido, arranque limpio, costo bajo.
