# Descripción General

## Stack tecnológico

| Capa | Tecnologías | Versión mínima |
|---|---|---|
| Backend | Python + FastAPI + SQLAlchemy + Alembic | FastAPI 0.116, SQLAlchemy 2.0 |
| Auth | JWT (python-jose) + passlib/bcrypt | — |
| DB | PostgreSQL | 16 |
| Async/colas | Redis (hoy: rate limit y refresh tokens de auth; futuro C-11: tareas asíncronas de FE ARCA) | 7 |
| Frontend | React + TypeScript + Vite | React 19, Vite 8 |
| Infra local | Docker / Docker Compose | — |
| Test | pytest + pytest-asyncio + httpx | — |

Arranque limpio (Enfoque B): mismo stack del demo Animall + TypeScript y Redis explícitos, sin arrastrar su deuda.

## Arquitectura general

Web app clásica FE → API REST → Postgres, con Redis para auth (rate limit, refresh) y, a futuro (C-11), lo asíncrono de la emisión FE ARCA; las alertas de stock y los reportes se calculan directo desde la DB. Monolito modular FastAPI con routers por dominio (ventas, stock, compras, clientes, auth). Frontend SPA en tablet del local + PC. Despliegue separado BE/FE/DB (ver `12_devops_y_despliegue.md`).

```
Tablet/PC (React) → FastAPI REST (JWT) → Postgres
                        └→ Redis (auth hoy; jobs de ARCA a futuro, C-11)
                        └→ ARCA / Mercado Pago (externos)
```

## Integraciones externas

| Servicio | Propósito | Tipo |
|---|---|---|
| ARCA | Facturación electrónica (emisión, certificados) | REST/SOAP vía AFIP SDK, async con reintentos |
| Mercado Pago | Cobros (link/QR, conciliación) | REST SDK + webhooks |
| Lector código barras | Entrada rápida en venta/carga | Hardware HID (teclado) |
| Impresora ticket/térmica | Tickets y comprobantes | Local/USB (a confirmar modelo) |

## API REST (resumen por recurso)

- `/auth`: login, refresh, me.
- `/productos`: CRUD, búsqueda, ajuste stock, mínimos.
- `/ventas`: crear venta (líneas + pagos), anular, ticket/FE.
- `/distribuidoras`: CRUD + listas de precios.
- `/compras`: entradas de stock, pedidos, pagos a distribuidoras.
- `/clientes`: CRUD + historial.
- `/reportes`: ventas, más vendidos, reposición, márgenes.
