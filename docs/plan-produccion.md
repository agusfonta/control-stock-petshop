# Plan de producción — dejar la app lista para la dueña

> Desglosa el change **C-15 `devops-despliegue`** de `CHANGES.md` en 4 changes atómicos.
> Estado al 2026-10-21: la app corre solo en local (SQLite `dev.db`, uvicorn 8000 + Vite 5173). No hay despliegue, ni `render.yaml`, ni `vercel.json`, ni backups.
> Base: `knowledge-base/12_devops_y_despliegue.md` (Opción A: Vercel + Render/Railway + Postgres/Redis administrados).

## Árbol de changes

```
(local hoy) ── C-19 mascotas-en-tabla-y-edicion   ← archivado
      │
      ▼
C-14.5 demo-render (mini C-15b)      [BE+FE] render.yaml en plan gratis, seed demo en staging → la dueña prueba y pide cambios
      │                              (implementado; pendiente de que la usuaria cree la cuenta de Render y siga docs/demo-render.md)
      ▼
C-15a  hardening-produccion          [BE]    config prod, health con checks, seed de producción
      │
      ▼
C-15b  config-despliegue             [BE+FE] Dockerfile/migraciones, render.yaml, vercel.json, .env.example
      │
      ├────────────► C-15c  backups-y-restauracion   [Ops]  pg_dump automático + prueba de restore
      │                      (puede ir en paralelo con el go-live; debe estar listo ANTES de cargar datos reales)
      ▼
C-15d  go-live-y-runbook             [Ops]   provisionar, desplegar, smoke test, cargar datos reales, docs/despliegue.md
      │
      ▼
 USO REAL por la dueña
      │
      ├── C-11 facturacion-arca      (diferido; checklist en docs/arca-checklist-datos.md)
      └── C-12 cobros-mercadopago    (diferido)
```

Camino crítico: **C-15a → C-15b → C-15d** (C-15c en paralelo, pero obligatorio antes de datos reales).

---

## Decisiones previas (bloqueantes)

| # | Decisión | Estado | Detalle |
|---|---|---|---|
| D1 | Proveedor del backend + DB | **DECIDIDO (2026-10-21): Render** | Web service + Postgres + Redis en Render. VPS de Hostinger descartado (es de la facultad). |
| D2 | Plan | **DECIDIDO: pago mínimo** | Aprox. 24 USD/mes (web ~7 + Postgres ~7 + Redis ~10; precios sin verificar, confirmar en render.com/pricing). El plan gratis duerme el servicio y borra la DB. |
| D3 | Destino de backups externos | Pendiente (recomendado: Cloudflare R2) | Barato, sin costo de salida; primeros 10 GB gratis |
| D4 | Dominio | **Disponible: Namecheap (gratis, con tu nombre)** | Usar un subdominio (`tienda.<dominio>`); se puede cambiar después sin tocar la app. Verificar cuándo vence y si renueva gratis. |
| D5 | Redis en producción | A evaluar en C-15a | Hoy lo usa auth; `REDIS_URL=memory://` solo se admite en dev/test. Si se puede evitar, el total baja a ~14 USD/mes. |
| D6 | Hosting del frontend | **DECIDIDO: Render Static Site** | Mismo proveedor que el backend. Vercel Hobby es para uso no comercial, por eso se descarta (`vercel.json` ya no hace falta; se usan rewrites de SPA en `render.yaml`). |
| D7 | Despliegue de demo previo | **DECIDIDO: opción 2** | Antes de C-15a, un "mini C-15b" en plan gratis de Render para que la dueña pruebe la app y pida cambios. Pendiente: la usuaria crea la cuenta de Render y avisa. Requiere decidir cómo cargar el seed demo en la nube (`seed_demo` hoy solo corre con `ENV=dev|test`; propuesta: permitir `ENV=staging` explícito). Límites del plan gratis: backend se duerme, Postgres gratis vence a ~30 días, sin backups; nunca cargar datos reales ahí. |

> Lo que NO puede hacer el agente: crear las cuentas (Render/Vercel/R2), cargar secretos en los paneles y pagar. Eso lo hacés vos; el agente deja todo listo y documentado.

---

## C-15a `hardening-produccion`

- **Governance**: ALTO (config de seguridad y datos de usuarios) → el agente propone y espera OK antes de escribir.
- **Dependencias**: C-19 cerrado.
- **Scope**
  - `GET /api/health` con chequeo real de DB y Redis (200 solo si ambos responden; el healthcheck del Dockerfile ya apunta ahí).
  - Verificar el arranque fail-closed con `ENV=prod`: `SECRET_KEY` ≥ 32 caracteres, `REDIS_URL` real, `CORS_ORIGINS` explícito, sin valores demo.
  - Script `scripts/seed.py` (o `crear_duena.py`) para crear la cuenta de la dueña con contraseña tomada de variable de entorno; confirmar que `seed_demo` no puede correr con `ENV=prod`.
  - Revisión de seguridad (`/security-review`) y auditoría de endpoints sin schema estricto o sin RBAC.
  - Bug pendiente RN-ST-03 (`POST /api/productos` con `stock_actual>0` sin `MovimientoStock`): corregirlo acá, porque con datos reales afecta el stock.
- **Tests (TDD)**: health 503 si cae DB/Redis; arranque falla con config débil en prod; seed de prod no crea datos demo; regresión RN-ST-03.
- **Hecho cuando**: suite verde, `ENV=prod` local rechaza config débil, `/security-review` sin hallazgos altos.

## C-15b `config-despliegue`

- **Governance**: BAJO.
- **Dependencias**: C-15a. Decisiones D1, D2 y D5.
- **Scope**
  - Backend: ejecutar `alembic upgrade head` en cada deploy (release command / pre-deploy), imagen `target: runtime`.
  - `render.yaml` (o `railway.json`) versionado: web service Docker, Postgres, Redis, variables sin valores secretos.
  - `frontend/vercel.json`: rewrites de SPA y ruteo de `/api` hacia el backend (o `VITE_API_URL`); revisar que no queden URLs a localhost.
  - `.env.example` de producción con todas las variables: `ENV`, `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `CORS_ORIGINS`, `SEED_OWNER_PASSWORD`. Las de `ARCA_*` y `MP_ACCESS_TOKEN` quedan vacías hasta C-11/C-12.
  - Ajustar CI para que construya la imagen `runtime` (detecta Dockerfile roto antes del deploy).
  - La usuaria completa los `.env` (los agentes no pueden editarlos).
- **Hecho cuando**: `docker build --target runtime` OK, y el stack levanta localmente con un compose de prueba usando `ENV=prod` y Postgres real.

## C-15c `backups-y-restauracion`

- **Governance**: ALTO (backup/restore de datos de usuario) → proponer y esperar revisión.
- **Dependencias**: C-15b (necesita la `DATABASE_URL` real). Decisión D3.
- **Scope**
  - Activar los backups automáticos del proveedor (paso manual, documentado).
  - Workflow de GitHub Actions programado (`pg_dump` → comprimido → R2/S3), con retención (p. ej. 4 semanales + 7 diarios). Secretos en GitHub Secrets, nunca en el repo.
  - `scripts/restaurar_backup.md` o script: cómo restaurar en una base vacía.
  - **Prueba de restauración real** una vez, con evidencia (conteo de productos/ventas coincide).
  - Alerta si el workflow de backup falla.
- **Hecho cuando**: existe al menos un backup externo y se restauró con éxito en una base de prueba.

## C-15d `go-live-y-runbook`

- **Governance**: MEDIO. Combina pasos del agente y pasos tuyos.
- **Dependencias**: C-15b (y C-15c antes de cargar datos reales).
- **Scope**
  - Provisionar (vos): cuentas, servicios, variables secretas, dominio opcional.
  - Desplegar BE + FE, correr migraciones, crear usuarios reales (dueña y mostrador) con contraseñas propias.
  - Smoke test post-deploy automatizable: health + login + buscar producto + venta de prueba anulada.
  - Cargar datos reales: migración del Excel real de productos (C-08, `scripts/importar_productos.py`) y verificación manual por la dueña.
  - Monitoreo básico: ping externo gratuito (UptimeRobot) a `/api/health`.
  - `docs/despliegue.md`: pasos BE/FE/DB, rollback, cómo rotar `SECRET_KEY`, cómo restaurar un backup, a quién llamar si se cae.
  - Prueba en tablet/celular real en el mostrador (HTTPS, lector de código de barras, impresión de ticket).
- **Hecho cuando**: la dueña hace una venta real de punta a punta en la URL pública y se revisó un backup posterior a esa venta.

---

## Después del go-live

- **C-11 facturación ARCA**: depende de los datos fiscales (`docs/arca-checklist-datos.md`). Deploy ya listo ⇒ secretos `ARCA_*` se cargan en el host.
- **C-12 Mercado Pago**: depende de la pregunta abierta de modo MP (`knowledge-base/10_preguntas_abiertas.md`).
- Mantenimiento recurrente: revisar backups mensualmente, actualizar dependencias, repetir prueba de restore cada trimestre.

## Cómo ejecutarlo

Cada paso va con el flujo OPSX, en orden:

```
/opsx:propose c-15a-hardening-produccion
/opsx:apply   c-15a-hardening-produccion
/opsx:archive c-15a-hardening-produccion
```

Al archivar, tildar `[x]` en `CHANGES.md` (sección C-15 → reemplazarla por una referencia a este plan).
