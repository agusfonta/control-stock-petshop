# CHANGES — Secuencia de Implementación

> Índice canónico de todos los changes del proyecto **Control Stock Petshop**.
> Cada change es atómico: un agente puede implementarlo en una sesión (~4-6 horas).
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**

---

## Cómo usar este documento

1. Identificar el change a implementar (verificar que sus dependencias están en `openspec/changes/archive/`).
2. Leer los docs de la knowledge-base indicados en "Leer antes".
3. Ejecutar `/opsx:propose <nombre-del-change>`.
4. Al terminar el change, archivarlo con `/opsx:archive <nombre-del-change>`.
5. Marcar el checkbox `[x]` en este archivo.

---

## Árbol de dependencias

```
C-01 foundation-setup
  └── C-02 core-models
        └── C-03 auth-rbac                        ← desbloquea TODO lo demás
              │
              ├── C-04 catalogo-productos
              │     ├── C-05 stock-alertas-ajustes
              │     │     └── C-10 ventas-mostrador ─┐
              │     ├── C-06 distribuidoras-listas   │ (C-04 + C-05 + C-09)
              │     │     └── C-07 pedidos-entradas-pagos
              │     └── C-08 migracion-excel
              │
              ├── C-09 clientes-historial           ← paralelo con C-04
              │
              └── C-10 ventas-mostrador
                    ├── C-11 facturacion-arca       ← paralelo FE/MP/reportes
                    ├── C-12 cobros-mercadopago     ← paralelo FE/MP/reportes
                    ├── C-14 reportes-basicos       ← + C-05
                    └── C-13 pos-frontend           ← + C-11 + C-12
                          └── C-15 devops-despliegue
```

### Paralelismo por fase

> Cada "gate" es un punto de sincronización. Los changes dentro de un grupo pueden ejecutarse en paralelo.

```
GATE 0: ninguna
  → C-01 foundation-setup (solo)

GATE 1: C-01 ✓
  → C-02 core-models (solo)

GATE 2: C-02 ✓
  → C-03 auth-rbac (solo)

GATE 3: C-03 ✓                     ← PRIMER FORK (2 paralelos)
  → C-04 catalogo-productos        [Agente A]
  → C-09 clientes-historial        [Agente B]

GATE 4: C-04 ✓                     ← FORK (3 paralelos)
  → C-05 stock-alertas-ajustes     [Agente A]
  → C-06 distribuidoras-listas    [Agente B]
  → C-08 migracion-excel           [Agente C]

GATE 5: C-04 + C-06 ✓
  → C-07 pedidos-entradas-pagos    [Agente B]

GATE 6: C-04 + C-05 + C-09 ✓
  → C-10 ventas-mostrador          [Agente A]

GATE 7: C-10 ✓                     ← FORK (3 paralelos)
  → C-11 facturacion-arca          [Agente A]
  → C-12 cobros-mercadopago        [Agente B]
  → C-14 reportes-basicos          [Agente C — si C-05 ✓]

GATE 8: C-10 + C-11 + C-12 ✓
  → C-13 pos-frontend              [Agente C]

GATE 9: todo lo anterior ✓
  → C-15 devops-despliegue         [Agente A]
```

### Camino crítico (9 changes — mínimo irreducible)

```
C-01 → C-02 → C-03 → C-04 → C-05 → C-10 → C-11 → C-13 → C-15
```

> Incluye lo indispensable para vender en mostrador con FE y desplegado. Quedan fuera del camino crítico: C-06/C-07 (compras, operable con ajuste manual), C-08 (migración, puede cargarse manual), C-09 (clientes, venta sin cliente), C-12 (MP, operable con efectivo), C-14 (reportes).

### Plan óptimo con 3 agentes

```
Paso │ Agente A (Backend Core)      │ Agente B (Backend Aux)         │ Agente C (Frontend/Ops)
─────┼──────────────────────────────┼────────────────────────────────┼─────────────────────────
  1  │ C-01 foundation-setup        │ —                              │ —
  2  │ C-02 core-models             │ —                              │ —
  3  │ C-03 auth-rbac               │ —                              │ —
  4  │ C-04 catalogo-productos      │ C-09 clientes-historial        │ —
  5  │ C-05 stock-alertas-ajustes   │ C-06 distribuidoras-listas    │ C-08 migracion-excel
  6  │ C-10 ventas-mostrador        │ C-07 pedidos-entradas-pagos   │ —
  7  │ C-11 facturacion-arca        │ C-12 cobros-mercadopago        │ C-14 reportes-basicos
  8  │ —                            │ —                              │ C-13 pos-frontend
  9  │ C-15 devops-despliegue       │ —                              │ —
```

---

## FASE 0 — Cimientos

### [C-01] `foundation-setup`
- **Estado**: `[x]` pendiente
- **Scope**: Scaffolding completo + infraestructura base (Enfoque B, arranque limpio)
  - Estructura `backend/app/{routers,services,models.py,schemas.py,deps.py,core/}`, `frontend/src/{features,shared,pages/}`
  - `backend/`: FastAPI app mínima con `GET /api/health`, Alembic inicializado, `core/{config,security,db}`, `Dockerfile`
  - `frontend/`: Vite + React 19 + TypeScript estricto, Tailwind, Zustand, React Query
  - `docker-compose.yml`: api + db (Postgres 16) + redis (7); `.env.example` en cada sub-proyecto
  - GitHub Actions CI: jobs paralelos backend (pytest) y frontend (tsc + build)
  - `plantilla_productos.csv` base versionada para futura migración
- **Dependencias**: ninguna
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/01_vision_y_objetivos.md` §Alcance v1
  - `knowledge-base/02_descripcion_general.md` §Stack tecnológico
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura de directorios
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-01, §DD-04

---

### [C-02] `core-models`
- **Estado**: `[x]` pendiente
- **Scope**: Modelos base + migraciones iniciales + seed mínimo
  - Modelos: `Usuario`, `Producto`, `Distribuidora`, `Cliente` (campos según ERD, uuid PK, sku unique, `precio_venta` calculado)
  - Mixins: `AuditMixin` (`activo`, `created_at`, `updated_at`), base repository genérico
  - Migración 001: tablas core + índices (`sku`, `nombre` trgm, `categoria`)
  - Seed mínimo: roles `dueña/mostrador`, usuario dueña inicial, categorías base (alimentos, accesorios, higiene, farmacia), métodos de pago base
  - Tests: constraints (`stock_actual >= 0`, `sku` unique, `precio = costo×(1+margen)`)
- **Dependencias**: C-01
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Entidades, §Seed data inicial
  - `knowledge-base/05_reglas_de_negocio.md` §RN-PR-01, §RN-ST-03
  - `knowledge-base/08_arquitectura_propuesta.md` §Patrones aplicados
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-02

---

## FASE 1 — Autenticación y accesos

### [C-03] `auth-rbac`
- **Estado**: `[x]` pendiente
- **Scope**: Autenticación JWT + RBAC dueña/mostrador
  - `POST /api/auth/login` — JWT access corto + refresh, rate limiting 5/60s por IP+email, bcrypt
  - `POST /api/auth/refresh` — rotación con blacklist en Redis
  - `GET /api/auth/me` — usuario actual + roles
  - `deps.py`: `require_role()`, `require_duena()`; solo dueña crea usuarios (`POST /api/usuarios`), anula ventas y edita márgenes
  - Refresh en cookie HttpOnly (secure, samesite=lax); sin registro público
  - Tests: login ok/ko, token expirado, refresh rotation, matriz RBAC (mostrador bloqueado en config)
- **Dependencias**: C-02
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` §RBAC — Matriz de permisos, §Rutas públicas
  - `knowledge-base/05_reglas_de_negocio.md` §RN-AU-01, §RN-AU-02
  - `knowledge-base/08_arquitectura_propuesta.md` §Seguridad
  - `knowledge-base/07_flujos_principales.md` §Flujo 1 (actor mostrador)

---

## FASE 2 — Catálogo, stock y compras

> C-04 y C-09 pueden proponerse en paralelo. C-04 debe archivarse antes de C-05/C-06/C-08.

### [C-04] `catalogo-productos`
- **Estado**: `[ ]` pendiente
- **Scope**: Catálogo con precios calculados (US-005 parcial, US-008 parcial)
  - Modelos: `ListaPrecio` (distribuidora_id, producto_id, costo), campos `margen_pct`, `stock_minimo` en Producto
  - Endpoints: `CRUD /api/productos`, `GET /api/productos/buscar?q=` (sku exacto + nombre trgm, paginado), `PATCH /api/productos/{id}/margen-minimo` (solo dueña, RN-PR-02/RN-ST-02)
  - Lógica: `precio_venta = costo × (1+margen_pct)` recalculado al cambiar costo/margen (RN-PR-01, RN-PR-04 sin tocar histórico)
  - Migración 002: tablas lista_precio + columnas margen/mínimo
  - Tests: CRUD, búsqueda por código/nombre, recálculo de precio, 403 mostrador en margen
- **Dependencias**: C-03
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Producto
  - `knowledge-base/05_reglas_de_negocio.md` §RN-PR-01 a §RN-PR-04
  - `knowledge-base/06_funcionalidades.md` §US-005, §US-008
  - `knowledge-base/02_descripcion_general.md` §API REST

---

### [C-05] `stock-alertas-ajustes`
- **Estado**: `[ ]` pendiente
- **Scope**: Stock en tiempo real con alertas y ajustes auditables (US-003, US-004)
  - Modelo `MovimientoStock` append-only (tipo venta/entrada/ajuste/apertura, stock_previo/nuevo, ref_id, usuario_id; sin update/delete)
  - Endpoints: `GET /api/stock?bajo_minimo=true&orden=rotacion` con badge `stock <= minimo` (RN-ST-01), `POST /api/productos/{id}/ajustar` con motivo obligatorio (solo dueña, RN-ST-03)
  - Job Redis: marca bajo-mínimo + endpoint de alertas para reposición
  - Migración 003: tabla movimiento_stock
  - Tests: alerta al llegar a mínimo, ajuste genera movimiento, prohibido editar stock sin movimiento
- **Dependencias**: C-04
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §MovimientoStock
  - `knowledge-base/05_reglas_de_negocio.md` §RN-ST-01 a §RN-ST-04
  - `knowledge-base/06_funcionalidades.md` §US-003, §US-004
  - `knowledge-base/07_flujos_principales.md` §Flujo 2

---

### [C-06] `distribuidoras-listas`
- **Estado**: `[ ]` pendiente
- **Scope**: ABM distribuidoras + listas de precios por origen (US-005)
  - Modelos: `Distribuidora` (nombre, contacto, cuit, condiciones), `ListaPrecio` con costo por origen
  - Endpoints: `CRUD /api/distribuidoras`, `CRUD /api/distribuidoras/{id}/listas`, `GET /api/distribuidoras/comparar?producto_id=` (costos por distribuidora, precio sugerido recalculado RN-PR-01/RN-PR-03)
  - Migración 004: tablas distribuidora + lista_precio (si no completa en C-04, aquí el resto)
  - Tests: CRUD, costo por lista, precio sugerido por origen
- **Dependencias**: C-04
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Distribuidora
  - `knowledge-base/05_reglas_de_negocio.md` §RN-PR-03, §RN-CP-01
  - `knowledge-base/06_funcionalidades.md` §US-005
  - `knowledge-base/01_vision_y_objetivos.md` §Alcance v1

---

### [C-07] `pedidos-entradas-pagos`
- **Estado**: `[ ]` pendiente
- **Scope**: Circuito de compras: pedidos, entradas y pagos a distribuidoras (US-006 + cuenta simple)
  - Modelos: `PedidoCompra` (estado pendiente/recibido/cancelado + líneas), `EntradaStock`, `PagoDistribuidora` (independiente de pedidos, RN-CP-03)
  - Endpoints: `POST /api/compras/pedidos`, `POST /api/compras/pedidos/{id}/recibir` → genera Entrada (suma stock + actualiza costo RN-CP-01, pedido no mueve stock RN-CP-02), `POST /api/compras/pagos`
  - Transacción: recibir pedido descuenta/actualiza en una sola transacción + movimientos de entrada
  - Migración 005: tablas pedido, entrada, pago_distribuidora
  - Tests: pedido no mueve stock, recibir sí mueve + actualiza costo, pagos independientes
- **Dependencias**: C-04, C-06
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §PedidoCompra / EntradaStock / PagoDistribuidora
  - `knowledge-base/05_reglas_de_negocio.md` §RN-CP-01 a §RN-CP-03
  - `knowledge-base/06_funcionalidades.md` §US-006
  - `knowledge-base/07_flujos_principales.md` §Flujo 2

---

### [C-08] `migracion-excel`
- **Estado**: `[ ]` pendiente
- **Scope**: Carga inicial desde Excel del local (Flujo 3)
  - Endpoint: `POST /api/migracion/productos` (solo dueña) — sube `plantilla_productos.csv`, valida duplicados (sku) y costos > 0
  - Lógica: crea productos con stock inicial + `MovimientoStock` tipo `apertura` por cada fila válida; reporte de errores por fila
  - Frontend mínimo: página de subida con preview de errores (o CLI `scripts/import_csv.py` si se prefiere)
  - Tests: CSV válido crea productos + movimientos, duplicados rechazados, costos inválidos reportados
- **Dependencias**: C-04
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` §Flujo 3
  - `knowledge-base/04_modelo_de_datos.md` §Seed data inicial
  - `knowledge-base/10_preguntas_abiertas.md` §Pre-carga de catálogo
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura de directorios

---

## FASE 3 — Ventas y dinero

> C-09 puede ir en paralelo con C-04. C-10 requiere C-04 + C-05 + C-09 archivados.

### [C-09] `clientes-historial`
- **Estado**: `[ ]` pendiente
- **Scope**: Registro de clientes e historial básico (US-007)
  - Modelo `Cliente` (nombre, teléfono, email, dirección, saldo_cc reservado — sin cuenta corriente en v1 salvo decisión)
  - Endpoints: `CRUD /api/clientes`, `GET /api/clientes/buscar?q=`, `GET /api/clientes/{id}/ventas` (historial)
  - Integración: selector crear/buscar cliente inline en la venta (nullable)
  - Migración 006: tabla cliente
  - Tests: CRUD, búsqueda, historial por cliente
- **Dependencias**: C-03
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Cliente
  - `knowledge-base/06_funcionalidades.md` §US-007
  - `knowledge-base/10_preguntas_abiertas.md` §Cuenta corriente de clientes
  - `knowledge-base/03_actores_y_roles.md` §RBAC — Matriz de permisos

---

### [C-10] `ventas-mostrador`
- **Estado**: `[ ]` pendiente
- **Scope**: Venta transaccional con bloqueo duro sin stock (US-001, núcleo del sistema)
  - Modelos: `Venta` (cliente nullable, total, estado borrador/confirmada/anulada), `LineaVenta` (cantidad>0), `PagoVenta` (efectivo/transferencia/mp/tarjeta, ref_MP)
  - Endpoints: `POST /api/ventas` (borrador + `idempotency_key`), `POST /api/ventas/{id}/confirmar` (transacción: revalida stock, crea líneas+pagos, descuenta stock, crea movimientos, encola job FE), `POST /api/ventas/{id}/anular` (solo dueña, movimiento inverso RN-VT-03)
  - Reglas: bloqueo si `cantidad > stock` (RN-VT-01), rollback total si falla algo (RN-VT-02), pagos deben igualar total (RN-VT-04)
  - Migración 007: tablas venta, linea_venta, pago_venta
  - Tests: venta ok descuenta + movimientos, sin stock bloquea, pago incompleto no confirma, anulación devuelve stock, idempotencia
- **Dependencias**: C-04, C-05, C-09
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/05_reglas_de_negocio.md` §RN-VT-01 a §RN-VT-04, §Excepciones globales
  - `knowledge-base/06_funcionalidades.md` §US-001
  - `knowledge-base/07_flujos_principales.md` §Flujo 1
  - `knowledge-base/04_modelo_de_datos.md` §Venta, §LineaVenta, §PagoVenta

---

### [C-11] `facturacion-arca`
- **Estado**: `[ ]` pendiente
- **Scope**: Facturación electrónica ARCA async con reintentos (US-002)
  - Modelo `ComprobanteFE` (venta_id, tipo ticket/FE A/B/C, cae, número, estado pendiente/emitido/error, payload, intentos)
  - Worker Redis (outbox): emite FE al confirmar venta, guarda CAE/número; si falla queda pendiente + alerta sin tumbar la venta
  - Endpoints: `POST /api/ventas/{id}/facturar`, `GET /api/comprobantes?estado=pendiente`, `POST /api/comprobantes/{id}/reintentar`
  - Config: `ARCA_CERT/KEY`, punto de venta y CUIT por env (pendiente dato fiscal real)
  - Tests: emisión ok guarda CAE, error deja pendiente + reintento, venta confirmada aunque FE falle
- **Dependencias**: C-10
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-002
  - `knowledge-base/07_flujos_principales.md` §Flujo 1 (pasos 4-5, casos de error)
  - `knowledge-base/04_modelo_de_datos.md` §ComprobanteFE
  - `knowledge-base/10_preguntas_abiertas.md` §Datos fiscales ARCA

---

### [C-12] `cobros-mercadopago`
- **Estado**: `[ ]` pendiente
- **Scope**: Cobros con Mercado Pago + conciliación (complemento US-001)
  - Endpoints: `POST /api/pagos/mp/crear` (QR/link desde la venta), `POST /api/webhooks/mp` (valida firma MP, confirma PagoVenta async, reintentos)
  - Lógica: `PagoVenta.metodo=mp` + `ref_MP` para conciliar por ref (no por monto, evita doble acreditación); idempotencia por `idempotency_key`
  - Config: `MP_ACCESS_TOKEN` por env
  - Tests: crear intent, webhook con firma válida confirma, firma inválida rechaza, doble webhook no duplica
- **Dependencias**: C-10
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/11_pagos_mercadopago.md` (completo)
  - `knowledge-base/05_reglas_de_negocio.md` §Excepciones globales
  - `knowledge-base/02_descripcion_general.md` §Integraciones externas
  - `knowledge-base/10_preguntas_abiertas.md` §Credenciales Mercado Pago

---

## FASE 4 — Experiencia, reportes y producción

> C-11, C-12 y C-14 pueden ir en paralelo tras C-10. C-13 requiere C-10 + C-11 + C-12.

### [C-13] `pos-frontend`
- **Estado**: `[ ]` pendiente
- **Scope**: SPA de mostrador rápida en tablet (<60s por venta, US-001 UI)
  - `features/pos`: buscador con debounce + soporte lector HID (código barras como teclado), carrito con validación de stock en memoria, registro de pagos (efectivo/transferencia/MP), ticket imprimible (térmica)
  - Páginas: `/pos` (mostrador), `/stock` (consulta rápida), `/clientes` (selector inline)
  - Estado: Zustand + React Query; JWT con refresh; RBAC en rutas (mostrador vs dueña)
  - Tests: flujo buscar→agregar→cobrar→ticket (Playwright o Vitest + MSW)
- **Dependencias**: C-10, C-11, C-12
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-001
  - `knowledge-base/07_flujos_principales.md` §Flujo 1
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura de directorios (frontend)
  - `knowledge-base/09_decisiones_y_supuestos.md` §SU-02

---

### [C-14] `reportes-basicos`
- **Estado**: `[ ]` pendiente
- **Scope**: Reportes para decidir compras (US-009)
  - Endpoints: `GET /api/reportes/ventas-dia`, `/mas-vendidos`, `/reposicion` (bajo mínimo + rotación), `/margenes`
  - Jobs Redis para agregados pesados; cache TTL corto
  - Frontend: `features/reportes` + páginas `/reportes/*` (solo dueña ve completo, mostrador ve básico)
  - Tests: agregados correctos, aislamiento por fecha, cache invalidation tras venta
- **Dependencias**: C-10, C-05
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-009
  - `knowledge-base/04_modelo_de_datos.md` §Dominios (Ventas, Inventario)
  - `knowledge-base/08_arquitectura_propuesta.md` §Patrones aplicados (Outbox/jobs)
  - `knowledge-base/01_vision_y_objetivos.md` §Métricas de éxito

---

### [C-15] `devops-despliegue`
- **Estado**: `[ ]` pendiente
- **Scope**: Despliegue Opción A + backups (cierra el riesgo top de Discovery)
  - FE en Vercel (`vercel.json`), BE en Render/Railway (plan pago mínimo, `render.yaml` versionado), Postgres+Redis en mismo proveedor
  - Secrets en host (SECRET_KEY, ARCA certs, MP token); `.env` solo local
  - Backups: snapshots diarios del proveedor + `pg_dump` semanal a R2/S3 (script + cron documentado)
  - Docs: `docs/despliegue.md` con pasos BE/FE/DB + rollback; `GET /api/health` con checks DB/Redis
  - Tests: smoke post-deploy (health + login + buscar producto)
- **Dependencias**: C-01
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/12_devops_y_despliegue.md` (completo)
  - `knowledge-base/10_preguntas_abiertas.md` §Dónde se despliega
  - `knowledge-base/08_arquitectura_propuesta.md` §Variables de entorno
  - `knowledge-base/02_descripcion_general.md` §Infra local

---
