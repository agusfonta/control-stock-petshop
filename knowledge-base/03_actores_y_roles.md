# Actores y Roles

## Actores del sistema

| Actor | Descripción | Cómo interactúa |
|---|---|---|
| Dueña/admin | Administra catálogo, precios, mínimos, distribuidoras y ve reportes | SPA completa, tablet/PC |
| Mostrador/vendedor | Atiende ventas, registra entradas, consulta stock | SPA mostrador, tablet, flujo rápido |
| Sistema/jobs | Emite FE, dispara alertas, genera reportes | Workers Redis, sin UI |

## RBAC — Matriz de permisos

| Rol | Productos | Ventas | Stock/ajustes | Distribuidoras/compras | Clientes | Reportes | Config |
|---|---|---|---|---|---|---|---|
| dueña | CRUD | CRUD + anular | CRUD | CRUD | CRUD | ver | CRUD |
| mostrador | ver + buscar | crear + ver propias | registrar entrada | ver + crear pedido | ver + crear | ver básico | — |

Regla: solo dueña anula ventas, edita márgenes/mínimos y gestiona usuarios.

## Rutas públicas

- `/login`, `/health`, assets estáticos.
- Todo lo demás requiere JWT. Sin registro público (usuarios creados por dueña).
