# Proposal

## Why

El backend ya cubre auth, catálogo, stock, distribuidoras, compras, clientes, ventas (C-10) y reportes (C-14), pero no existe interfaz: el frontend tiene solo tres páginas vacías y no hay una forma documentada de levantar todo localmente con datos. Sin UI no se puede vender en mostrador (US-001, <60 s por venta) ni operar el negocio, y la usuaria necesita **ver la app funcionando ya**. Este change entrega una SPA completa y usable sobre la API existente, tablet-first, más una experiencia de "correr local" de un comando.

## What Changes

- **Base del frontend**: cliente HTTP tipado (base URL por env, access JWT en memoria, refresh rotativo por cookie HttpOnly con reintento único ante `401`), React Query, store de sesión Zustand, guards de ruta por rol (`duena` / `mostrador`), shell con navegación lateral por secciones, login, estados de carga/vacío/error y toasts. UI con shadcn/ui sobre Tailwind; estética sobria derivada del logo de Animall (el demo es referencia, no plantilla).
- **POS `/pos`**: búsqueda con debounce y lector de código de barras HID (teclado + Enter), carrito con validación de stock en memoria (espejo de RN-VT-01; el servidor manda y sus `409` con faltantes se muestran por línea), cliente opcional (buscar o crear inline), cobro con pagos divididos **efectivo / transferencia / tarjeta** (suma = total, vuelto calculado en UI), flujo de dos pasos del spec de ventas (borrador idempotente → confirmar con pagos) y **comprobante imprimible simple** (no fiscal).
- **Ventas `/ventas`**: listado y detalle (mostrador ve las propias), reimpresión del comprobante y anulación con motivo (solo dueña).
- **Gestión**: `/productos` (listado, búsqueda, alta/edición, margen y stock mínimo, baja — escritura solo dueña), `/stock` (consulta rápida, alertas bajo mínimo, ajuste con motivo — dueña), `/clientes` (listado, búsqueda, alta, edición/baja dueña, historial de ventas), `/distribuidoras` (ABM, listas de precios, comparador), `/compras` (pedidos: crear, recibir, cancelar; pagos a distribuidoras y cuenta — dueña).
- **Reportes `/reportes/*`**: ventas del día y reposición (ambos roles), más vendidos y márgenes (solo dueña), con tablas y tarjetas KPI, sin librería de gráficos. (La línea de frontend de reportes se movió aquí desde C-14.)
- **Correr local**: `docker compose up` levanta db + redis + api + frontend con migraciones y seed demo automáticos; alternativa sin Docker con SQLite + Redis en memoria (solo `ENV=dev/test`); seed demo con catálogo, distribuidoras y listas, clientes, un pedido recibido y ventas de los últimos días; usuarios dueña y mostrador con passwords de prueba solo en archivos de ejemplo/compose; CORS configurable para el origen de Vite; sección "Cómo correr" en el README raíz.
- **Ajustes mínimos de backend para el entorno local** (sin cambiar contratos de la API): engine SQLite apto para threads, `REDIS_URL=memory://` → fakeredis solo en dev/test, middleware CORS por env, script de inicialización de base y seed demo.
- **Tests**: Vitest + React Testing Library + MSW para sesión/guards, carrito y pagos, flujo buscar → agregar → cobrar → comprobante, ajuste de stock y recepción de pedido; `npm test` y `npm run build` en verde.
- **Fuera de alcance** (decisión de la usuaria): facturación electrónica ARCA (C-11) y Mercado Pago (C-12). El método `mp` del backend no se ofrece en la UI; el comprobante no tiene datos fiscales.

## Capabilities

### New Capabilities

- `frontend-shell`: sesión (login, refresh, logout), guards por rol, navegación, estados de carga/vacío/error, notificaciones y lineamientos visuales/accesibilidad de la SPA.
- `pos-mostrador`: venta de mostrador en la UI — búsqueda y lector de barras, carrito con validación de stock, cliente opcional, cobro con pagos divididos y vuelto, confirmación idempotente, comprobante imprimible, listado/detalle/anulación de ventas.
- `gestion-ui`: pantallas de productos, stock, clientes, distribuidoras, compras y reportes con la matriz RBAC de la API.
- `entorno-local`: forma documentada de correr todo localmente (Docker y sin Docker), seed demo, usuarios de prueba y CORS de desarrollo.

### Modified Capabilities

(Ninguna: los contratos de la API existentes no cambian. Los ajustes de backend son de configuración de entorno de desarrollo y quedan especificados en `entorno-local`.)

## Impact

- **Frontend** (`frontend/`): nueva estructura `src/{app,shared,features/*,components/ui}`, dependencias shadcn/ui (Radix, lucide-react, sonner, class-variance-authority, tailwind-merge), Tailwind 4 vía PostCSS, fuente vía `@fontsource`, Vitest + Testing Library + MSW + jsdom, script `npm test`. Se reemplazan `HomePage`/`PosPage`/`StockPage` y `healthStore`.
- **Backend**: `app/core/db.py` (SQLite `check_same_thread`), `app/deps.py` (`memory://` → fakeredis en dev/test), `app/core/config.py` (`cors_origins`), `app/main.py` (CORSMiddleware), nuevos `scripts/init_db.py` y `scripts/seed_demo.py`, tests nuevos. Sin migraciones nuevas, sin cambios de endpoints.
- **Infra**: `docker-compose.yml` (servicio `frontend`, bind mount de backend, arranque con migraciones + seed), `.env.example` de backend y frontend, `README.md` raíz.
- Governance **MEDIO**. Sin commits en este trabajo (decisión de la usuaria).
- Non-goals: ARCA/FE, Mercado Pago/QR, impresión térmica ESC/POS nativa, modo offline, historial de movimientos de stock (no hay endpoint de listado), gestión de usuarios en UI, endpoint de logout (ver design), modo oscuro, Playwright/E2E.
