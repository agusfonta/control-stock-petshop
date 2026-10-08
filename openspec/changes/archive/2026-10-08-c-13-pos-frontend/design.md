# Design

## Context

Motivación y alcance: ver `proposal.md`. Comportamiento esperado: specs `frontend-shell`, `pos-mostrador`, `gestion-ui`, `entorno-local`.

Estado actual relevante (observado en el repo):

- **Frontend** (`frontend/`): React 19.1, TS 5.8 estricto (`noImplicitAny`, `noUnused*`), Vite 8, Tailwind 3.4 + PostCSS, react-router 7.6, React Query 5, Zustand 5. Alias `@/` → `src/`. `components.json` de shadcn (new-york, `tailwind.config: ""` — formato Tailwind 4, `iconLibrary: lucide`) sin componentes instalados. Proxy de Vite `/api` → `http://localhost:8000`. Sin tests ni script `test`. Existen `frontend/.env.example` y `backend/.env.example` (se extienden, no se reemplazan).
- **API**: todas las rutas bajo `/api`. Login devuelve `{access_token, token_type}` y setea cookie `refresh_token` HttpOnly, `SameSite=Lax`, `path=/api/auth`, `Secure` solo en prod/https. `POST /api/auth/refresh` lee solo la cookie. **No existe endpoint de logout.** Access de 15 min, refresh de 7 días con rotación y detección de reúso en Redis. **Login y refresh fallan cerrado con `503` si Redis no responde.**
- Contratos que condicionan la UI: listados paginados `{total, page, page_size, total_pages, items}` con `page_size ≤ 100`; `GET /api/stock` **no tiene búsqueda** (solo `bajo_minimo` y `orden=rotacion`); listas de precios, líneas de pedido y pagos devuelven **ids** (`producto_id`, `distribuidora_id`) sin nombres; `VentaResumen` trae `cliente_id`/`usuario_id` sin nombres; las líneas de venta sí traen `producto_nombre`; no hay endpoint para listar usuarios ni movimientos de stock. Los decimales se serializan como número JSON en ventas y reportes y pueden llegar como número o string en otros recursos; la API acepta montos como string (`_coerce_decimal`). `409` de stock en ventas: `detail = {mensaje, faltantes: [{producto_id, solicitado, disponible}]}`; `422` de Pydantic: `detail = [{loc, msg, type}]`; el resto: `detail: string`.
- **Backend/entorno**: `docker-compose.yml` tiene db (postgres:16) + redis + api (target `dev`, sin bind mount, sin migraciones al arrancar, sin `scripts/` en la imagen) y no tiene frontend. Sin CORS. `scripts/seed.py` crea solo la dueña con `SEED_OWNER_PASSWORD` (un test prohíbe passwords literales en el script). Los tests corren sobre SQLite (`create_all`) + fakeredis, por lo que los modelos son compatibles con SQLite; la migración `0002` usa `pg_trgm` (solo Postgres). Postgres 17 del sistema tiene contraseña desconocida y un `UnicodeDecodeError` conocido en tests `pg_only` locales.
- **Referencia visual**: demo Animall (`C:\Users\agusf\Desktop\PetShop\Animall\frontend`): teal `#15a092`, rosa suave, Poppins/Nunito/Caveat, pestañas tipo píldora, tarjetas con sombra, modales centrados. Es **referencia**, no plantilla (corrección de la usuaria; ver "Decisiones de UX"). Única restricción de marca: el logo (`logo.png`: pata y "ANI" teal `≈#0F978A`, carrito y "Mall" negro, fondo rosa `≈#F1E6E6`).

## Goals / Non-Goals

**Goals:**

- Que la usuaria vea login + shell funcionando al terminar la tanda B1, y la app completa al terminar B6, siempre en estado ejecutable entre tandas.
- Una sola fuente de verdad por tema: cliente HTTP, mapa de permisos, formato de dinero, claves de React Query.
- Lógica de negocio de UI (carrito, pagos, vuelto, idempotencia, lector) en funciones puras testeadas antes de la UI.
- Cero cambios de contrato en la API; los cambios de backend se limitan a adaptadores de entorno de desarrollo.

**Non-Goals:**

- Generación automática de tipos desde OpenAPI (tipos escritos a mano; ver D3).
- Estado offline, PWA, impresión ESC/POS directa, modo oscuro, i18n.
- Endpoints nuevos de negocio (logout, listado de movimientos, listado de usuarios).

## Decisions

### D1 — Estructura del frontend por features

```
frontend/src/
  app/            router.tsx, providers.tsx, layout/ (AppShell, AppSidebar, Topbar), guards/ (RequireAuth, RequireRole, Forbidden)
  components/ui/  componentes shadcn (generados por CLI, no se editan salvo theming)
  shared/
    api/          client.ts (fetch + refresh), errors.ts (ApiError, parseo de detail), types.ts, queryKeys.ts
    lib/          money.ts, dates.ts, utils.ts (cn), permissions.ts
    hooks/        useDebouncedValue, useIndices (productos/distribuidoras/clientes por id), usePagination
    components/   DataTable, PageHeader, EmptyState, ErrorState, MoneyText, ConfirmDialog, KpiCard
  features/
    auth/ pos/ ventas/ productos/ stock/ clientes/ distribuidoras/ compras/ reportes/
      (cada una: api.ts con hooks de React Query, componentes, páginas, *.test.ts(x))
  test/           setup.ts, server.ts (MSW), handlers/ por feature, fixtures.ts, render.tsx (renderWithProviders)
```

Se eliminan `pages/HomePage|PosPage|StockPage.tsx` y `shared/healthStore.ts`. Alternativa descartada: carpeta `pages/` plana (KB 08 ya define `features/`; las features agrupan api + UI + tests).

### D2 — Tooling: Tailwind 4 vía PostCSS, shadcn CLI, Vitest

- **Tailwind 4 con `@tailwindcss/postcss`** (reemplaza `tailwindcss@3` + `autoprefixer`; se borra `tailwind.config.js`; `index.css` usa `@import "tailwindcss"` + tokens `@theme`). Motivo: `components.json` ya está en formato v4 y el CLI actual de shadcn genera para v4; el plugin PostCSS evita depender de que `@tailwindcss/vite` declare compatibilidad con Vite 8. Alternativa: mantener v3 y usar `shadcn@2.3.0` (componentes más viejos, `tailwind.config` manual) → fallback solo si v4 falla.
- **shadcn/ui** (`npx shadcn@latest add ...`): button, input, label, field, card, table, badge, dialog, alert-dialog, sheet, drawer, dropdown-menu, select, toggle-group, tabs, sidebar, tooltip, skeleton, separator, sonner, alert, empty, spinner, popover, command, pagination, input-group, kbd. Íconos `lucide-react`. Toasts `sonner`.
- **Formularios**: `react-hook-form` + `zod` + `@hookform/resolvers`, integrados con `Field` de shadcn; los `422`/`409` del servidor se vuelcan con `setError` al campo. Alternativa: formularios controlados a mano (más código repetido en ~10 formularios).
- **Fuente**: `@fontsource-variable/figtree` (empaquetada, funciona sin internet).
- **Tests**: `vitest` (versión compatible con Vite 8; si npm reporta conflicto de peer, usar la última que declare `vite@^8`), `jsdom`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, `msw@2`. Config `test` dentro de `vite.config.ts` (`environment: "jsdom"`, `setupFiles: "src/test/setup.ts"`, `css: false`). Scripts: `"test": "vitest run"`, `"test:watch": "vitest"`. `tsconfig` incluye tipos `vitest/globals` y `@testing-library/jest-dom`.

### D3 — Cliente HTTP tipado con refresh single-flight

- `apiFetch<T>(path, { method, body, query, signal })`: base `import.meta.env.VITE_API_BASE_URL ?? "/api"`, `credentials: "include"`, `Authorization: Bearer <access>` desde el store de sesión, JSON in/out, `204` → `undefined`.
- Ante `401` en una ruta distinta de `/auth/login` y `/auth/refresh`: llama a `refreshSession()`, que comparte **una única promesa en vuelo** entre todas las solicitudes; si resuelve, reintenta la original **una vez**; si falla, `session.expire()` (limpia y navega a `/login?next=...&expired=1`).
- `ApiError { status, message, fieldErrors: Record<string,string>, faltantes?: Faltante[] }` construido desde los tres formatos de `detail` (string, lista Pydantic, objeto con `faltantes`). Error de red → `ApiError` con `status: 0`.
- **Tipos escritos a mano** en `shared/api/types.ts` espejando los schemas Pydantic usados (Producto, StockItem, Alertas, Movimiento, Distribuidora, ListaPrecio, CompararResponse, Pedido, PagoDistribuidora, Cuenta, Cliente, Venta, VentaResumen, reportes, Paginated<T>, Me, Rol). Dinero tipado `Money = number | string`. Alternativa: `openapi-typescript` contra `/openapi.json` (exige backend corriendo en build/CI; se puede sumar después sin cambiar la UI).

### D4 — Sesión: access en memoria + "pista" de sesión para el logout

- Store Zustand `useSession`: `{ status: "loading" | "authenticated" | "anonymous", accessToken, user: Me | null, login, logout, expire, setAccess }`. **No se persiste** el token.
- Arranque: si `localStorage["animall.session"] === "1"` → `refresh` → `me` → `authenticated`; si falla o no hay pista → `anonymous`. Login exitoso escribe la pista; logout la borra (además limpia el cache de React Query y el carrito).
- **Por qué la pista**: no existe `POST /api/auth/logout`, así que la cookie de refresh sigue viva hasta vencer; sin la pista, recargar tras "Cerrar sesión" volvería a entrar. Limitación aceptada: alguien con acceso al navegador podría usar la cookie llamando a la API a mano. **Seguimiento recomendado** (auth = dominio CRÍTICO, requiere aprobación humana, fuera de C-13): endpoint de logout que revoque la familia y borre la cookie; al existir, `logout()` lo llama y la pista queda redundante.
- Acceso a `localStorage` siempre en `try/catch` (modo privado).

### D5 — Permisos: un mapa único espejo de la matriz RBAC

`shared/lib/permissions.ts` define `type Permiso = "productos.editar" | "stock.ajustar" | "ventas.anular" | "clientes.editar" | "distribuidoras.editar" | "compras.cancelar" | "compras.pagos" | "reportes.completos" | ...` y `PERMISOS: Record<Permiso, Rol[]>`. Hook `useCan(permiso)`; `<RequireRole roles>` para rutas; la navegación se filtra con el mismo mapa. Test de tabla que fija el mapa contra la matriz del spec `auth-rbac`. El servidor sigue siendo la autoridad (`403` → toast, sin cerrar sesión).

### D6 — React Query: claves y frescura

Fábrica `queryKeys` por recurso. Defaults: `staleTime: 30s`, `retry: 1` solo para errores de red/5xx (nunca 4xx), `refetchOnWindowFocus: true`. Búsqueda POS: `staleTime: 10s`, `placeholderData: keepPreviousData`. Invalidaciones tras mutación: venta confirmada/anulada → `stock`, `alertas`, `productos`, `ventas`, `reportes`, `clientes.historial`; ajuste → `stock`, `alertas`, `productos`; pedido recibido → `stock`, `alertas`, `productos`, `pedidos`, `cuenta`. El badge de alertas del sidebar usa `GET /api/stock/alertas` con `refetchInterval: 60s`.

### D7 — Dinero en centavos enteros

`money.ts`: `toCents(v: Money): number` parsea **desde string** (nunca `v * 100` sobre float) con redondeo mitad hacia arriba a 2 decimales; `centsToApi(c): string` → `"3800.50"` (se envía como string, la API lo acepta); `formatARS(c)` con `Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" })` (los tests normalizan el espacio no separable). Toda suma de carrito/pagos/vuelto opera en centavos.

### D8 — Carrito y pagos como funciones puras + store

- `features/pos/cart.ts` (puro): `addProduct(cart, p, qty=1)`, `setQty`, `removeLine`, `totalCents`, `applyFaltantes(cart, faltantes)` (marca `disponible`), `clampToDisponible`, `cartSignature(cart, clienteId)` (líneas ordenadas por `producto_id`). Respeta `1 ≤ cantidad ≤ stock_actual` y devuelve un aviso cuando recorta.
- `features/pos/payments.ts` (puro): `sumCents`, `remainingCents(total, pagos)` (positivo falta, negativo sobra), `canConfirm` (1–5 pagos, cada uno > 0, suma == total), `vueltoCents(pagaCon, montoEfectivo)`, `quickCashOptions(total)` (exacto + próximos múltiplos de 1.000/5.000/10.000 sin repetir).
- Store `useCartStore` (Zustand, en memoria, sobrevive navegación, no recargas) que delega en esas funciones; incluye `cliente` y `checkout: { signature, idempotencyKey, ventaId?, pagos? }`.

### D9 — Flujo de cobro idempotente

1. "Confirmar venta" → si `cartSignature` ≠ `checkout.signature` → nueva `crypto.randomUUID()`; si es igual (reintento) se reutiliza la clave.
2. `POST /api/ventas` (201 nuevo / 200 replay). Si `total` del servidor ≠ total local → actualizar precios/total, recalcular pagos propuestos y pedir reconfirmación (toast "El precio cambió").
3. `POST /api/ventas/{id}/confirmar` con `pagos` (montos string). Error de red → "Reintentar" reenvía **el mismo id y los mismos pagos** (la API es idempotente con pagos iguales).
4. `409` con `faltantes` (paso 2 o 3) → `applyFaltantes` + volver al carrito; el borrador queda abandonado (no se lista ni mueve stock). `422` → mensaje del servidor. `404` cliente/producto → refrescar y avisar.
5. Éxito → guardar `VentaResponse` + vuelto local para el comprobante, vaciar carrito, invalidar queries (D6).

### D10 — Lector de código de barras y atajos

El lector escribe en el input enfocado; el buscador tiene `autoFocus`. `resolveScan(texto, resultados)` (puro): SKU exacto (comparación sin distinguir mayúsculas, recortado) → agregar; único resultado → agregar; sin resultados → aviso. En Enter se consulta `GET /api/productos/buscar?q=<texto>` **sin esperar el debounce**. Listener global en `/pos`: tecla imprimible con foco en `body` y sin diálogo abierto → enfoca el buscador y conserva el carácter. Atajos: `F2` o `/` buscador, `F9` o `Ctrl+Enter` cobrar, `+`/`-` cantidad de la línea seleccionada, `Esc` cierra paneles; se muestran con `Kbd`. Alternativa descartada: detección por velocidad entre teclas (frágil y dependiente del lector).

### D11 — Comprobante imprimible con CSS de impresión

Componente `Comprobante` renderizado en el diálogo de éxito y en el detalle de venta, y duplicado en un portal `#print-root`. `@media print`: oculta todo salvo `#print-root`, `@page { margin: 4mm }`, ancho máx. 80 mm centrado (sirve en térmica y en A4), tipografía monoespaciada para importes. Número corto = primeros 8 caracteres del id en mayúsculas. Nombre del comercio = `VITE_STORE_NAME` (default "Animall"). Leyenda fija "Comprobante no válido como factura". `window.print()`.

### D12 — Resolución de nombres por índices cacheados

`useIndices`: `useProductosIndex`, `useDistribuidorasIndex`, `useClientesIndex` cargan todas las páginas (`page_size=100`) de los activos y devuelven `Map<id, entidad>`, `staleTime: 5 min`, invalidados por las mutaciones del recurso. Usados en listas de precios, pedidos, pagos y listado de ventas. Faltantes en el índice (dados de baja) → `GET /{recurso}/{id}` puntual o "—". **Vendedor**: no hay listado de usuarios → "Vos" si `usuario_id === me.id`, si no "Otro usuario". Supuesto: catálogo < 2.000 productos (petshop de barrio).

### D13 — Stock: búsqueda vía catálogo, sin historial de movimientos

`/stock` lista `GET /api/stock` (filtro y orden de servidor); el buscador de la pantalla usa `GET /api/productos/buscar` y calcula `bajo_minimo` con la misma regla (`stock_actual <= stock_minimo`). Como no hay endpoint de movimientos, el ajuste muestra solo el movimiento devuelto (previo → nuevo); el historial queda para un change futuro.

### D14 — Adaptadores de backend solo para desarrollo

- `config.py`: `cors_origins: str = "http://localhost:5173"` (lista separada por comas) y validador que rechaza `redis_url` con esquema `memory://` si `env ∉ {dev, test}`.
- `main.py`: `CORSMiddleware(allow_origins=<lista>, allow_credentials=True, allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])`.
- `db.py`: si la URL empieza con `sqlite`, `connect_args={"check_same_thread": False}`.
- `deps.get_redis`: `memory://` → singleton `fakeredis.FakeRedis(decode_responses=True)` del proceso (fakeredis ya está en `requirements.txt`). Así login/refresh/rate limit funcionan sin Redis real.
- Todo con tests pytest RED-first (TDD estricto del proyecto) y sin tocar routers de negocio.

### D15 — `init_db` y `seed_demo`

- `scripts/init_db.py`: SQLite → `Base.metadata.create_all`; Postgres → `alembic upgrade head` (API de Alembic).
- `scripts/seed_demo.py`: aborta si `ENV ∉ {dev, test}`; exige `SEED_OWNER_PASSWORD` y `SEED_MOSTRADOR_PASSWORD` (mensaje con las faltantes; sin defaults en código). Reutiliza `run_seed` (dueña `duena@petshop.local`) y crea `mostrador@petshop.local`. Catálogo tomado del demo Animall (Royal Canin, Pro Plan, Whiskas, snacks, higiene, juguetes, accesorios, farmacia, cuchas; ~20 SKUs con unidades `unidad`/`bolsa`/`caja`), creado con stock 0 y cargado con movimiento `apertura` vía `services.stock.aplicar_movimiento`; 4 distribuidoras del demo con listas superpuestas; 8 clientes del demo; pedido recibido vía `services.compras.crear_pedido` + `recibir_pedido` y uno pendiente; ~12 ventas vía `services.ventas` (crear + confirmar, una anulada) repartidas en 7 días retrocediendo `created_at`/`confirmada_at` de la venta tras confirmar. Idempotencia: si existe el SKU ancla `RC-MINI-3KG`, solo asegura usuarios y sale; todo el bloque de datos en una transacción. Reinicio: `docker compose down -v` o borrar `backend/dev.db`.

### D16 — Docker Compose de desarrollo

- `api`: bind mount `./backend:/code` (incluye `scripts/`, hot reload), `command: sh -c "alembic upgrade head && python -m scripts.seed_demo && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"`, env `ENV=dev`, `SECRET_KEY` de desarrollo, `SEED_*` con valores de prueba, `CORS_ORIGINS`, healthcheck a `/api/health`.
- `frontend`: `node:22-alpine`, `working_dir: /app`, volúmenes `./frontend:/app` + volumen anónimo `/app/node_modules`, `command: sh -c "npm ci && npm run dev -- --host 0.0.0.0"`, env `VITE_PROXY_TARGET=http://api:8000`, `VITE_USE_POLLING=true` (file watching en Windows), puerto `5173`, `depends_on: api (service_healthy)`.
- `db`: se publica en `5433:5432` (evita choque con el Postgres 17 del sistema en 5432). `vite.config.ts` lee `VITE_PROXY_TARGET` (default `http://localhost:8000`) y `VITE_USE_POLLING`.

### D17 — Estrategia de tests

- Unit (Vitest): `money`, `cart`, `payments`, `resolveScan`, `permissions`, parseo de `ApiError`, `refreshSession` single-flight.
- Integración de UI (RTL + MSW, `renderWithProviders({ route, user })`): login/guard/expiración (B1); buscar → escanear → agregar → cobrar dividido → comprobante, y `409` faltantes (B2); ajuste de stock y alta de producto (B3); recibir pedido (B4); reportes por rol (B5).
- Backend (pytest): CORS, `memory://`, SQLite threads, `init_db`, `seed_demo` (idempotencia, guard de ENV, passwords por env, reportes no vacíos).
- Cada tanda cierra con `npm run build`, `npm test`, `pytest -q` (si tocó backend) y una lista de verificación manual corta.

## Decisiones de UX

Criterios: venta < 60 s con teclado y lector, targets táctiles grandes, jerarquía clara, feedback inmediato, consistencia shadcn, accesibilidad básica, tablet-first, estética sobria con la marca del logo.

- **UX1 — Navegación lateral colapsable en lugar de píldoras superiores.** `Sidebar` de shadcn con grupos (Vender: POS, Ventas · Inventario: Productos, Stock · Compras: Distribuidoras, Pedidos · Clientes · Reportes), modo solo-íconos con tooltip en tablet vertical, `Sheet` en teléfono. *Por qué*: son 8 destinos (el demo tenía 5 pestañas y ya hacía wrap); la barra lateral escala, da deep links, deja el ancho para el POS y permite el badge de alertas. *Se descarta*: tarjeta de marca grande arriba y píldoras con gradiente (consumen ~150 px verticales en una tablet apaisada).
- **UX2 — POS en dos paneles.** Izquierda: buscador grande + resultados como lista de filas táctiles (nombre, SKU, stock, precio). Derecha: carrito fijo con líneas compactas, stepper de cantidad, cliente opcional arriba, **total grande y botón "Cobrar" como único elemento de alto contraste de toda la app**. En teléfono el carrito es una barra inferior con total que abre un `Drawer`. *Por qué*: el mostrador ve siempre qué está cobrando y nunca pierde el buscador; el demo usaba filas de formulario por línea (más clics). *Se descarta*: "sale-box" con inputs por línea y selects.
- **UX3 — Teclado primero.** Foco permanente en el buscador, Enter agrega, lector sin clics, atajos visibles (`F2`, `F9`, `Esc`), Enter en el comprobante = nueva venta. *Por qué*: el objetivo de <60 s depende de no tocar el mouse.
- **UX4 — Cobro en panel lateral con medios como botones.** `Sheet` derecho: medios en `ToggleGroup` (Efectivo / Transferencia / Tarjeta, íconos + texto), propuesta automática de efectivo por el total, montos rápidos para "Paga con", **vuelto en tipografía grande**, "Agregar otro medio" para dividir, indicador vivo "Faltan / Sobran". *Por qué*: el caso común (efectivo exacto o con vuelto) se resuelve en 1–2 toques; dividir es posible sin complicar el caso común.
- **UX5 — Comprobante como pantalla de éxito.** Check de confirmación, resumen, botones "Imprimir" y "Nueva venta" (primario). *Por qué*: cierre claro de la venta y siguiente acción obvia; el demo no tenía ticket.
- **UX6 — Altas/ediciones en `Sheet` lateral; confirmaciones en `AlertDialog`.** *Por qué*: el formulario se abre sin perder el listado de contexto y es cómodo en tablet; las acciones destructivas siempre piden confirmación con el verbo concreto ("Anular venta", "Dar de baja"). *Se descarta*: modales centrados para todo.
- **UX7 — Tablas legibles y tranquilas.** `Table` de shadcn con encabezado fijo, importes alineados a la derecha con `tabular-nums`, filas de 48 px en táctil, acciones secundarias en menú "⋯" por fila, búsqueda y filtros arriba, paginación abajo. Estado de stock con `Badge` (ámbar "Bajo mínimo", rojo "Sin stock") en vez de pintar la fila entera de rojo como el demo. *Por qué*: menos ruido visual, el estado se escanea por color + texto (accesible para daltonismo).
- **UX8 — Identidad visual derivada del logo.** Tokens: `primary` teal oscuro `#0B7F74` (contraste ≈4.9:1 con blanco, cumple AA; el teal del demo `#15a092` no llega con texto blanco), `brand` teal del logo `#149A8C` solo para elementos grandes/acentos, `ink` `#1C2024`, fondo `#FAFAF9`, superficies blancas, `blush` `#F3E7E6` (fondo del logo) solo en el panel de marca del login y la cabecera del sidebar, `warning` `#B54708`, `destructive` `#B42318`, radio `0.75rem`, sombras mínimas (borde en vez de sombra). Una sola familia, **Figtree**, con escala corta (14/16/20/28/40) y números tabulares. *Se descarta del demo*: fondo con manchas radiales, mezcla Poppins/Nunito/Caveat (la tipografía script vive solo en el logo), emojis como íconos (→ lucide), gradientes y sombras teal intensas.
- **UX9 — Login de dos columnas.** Panel de marca (logo sobre blush) + formulario; en teléfono, logo arriba y formulario. Errores en línea y botón con spinner.
- **UX10 — Estados útiles.** `Skeleton` con la forma de la tabla, `Empty` con explicación + acción permitida por rol, `Alert` con "Reintentar". Toasts `sonner` en `top-center` (no tapan el carrito ni el botón Cobrar) con duración corta para éxito y persistentes para errores.
- **UX11 — Menos para el mostrador.** Se ocultan columnas de costo/margen y todas las acciones de dueña; la navegación muestra solo lo accesible; Reportes muestra "Tus ventas de hoy". *Por qué*: menos decisiones y menos ruido en la pantalla del mostrador.
- **UX12 — Accesibilidad.** Labels visibles en todos los campos, foco visible con anillo `primary`, orden de tabulación natural, `aria-live` para total del carrito y avisos del lector, `prefers-reduced-motion` respetado (la única animación es la del check de éxito).

## Decisiones tomadas por defecto

1. Tailwind 4 vía `@tailwindcss/postcss` (fallback: v3 + `shadcn@2.3.0`). shadcn new-york, base neutral, íconos lucide, toasts sonner.
2. Formularios con react-hook-form + zod; tipos de API escritos a mano (sin codegen).
3. Fuente Figtree empaquetada con `@fontsource-variable/figtree`; sin Google Fonts.
4. Access token solo en memoria; pista `animall.session` en localStorage para restaurar sesión; sin endpoint de logout (seguimiento recomendado, dominio CRÍTICO).
5. Ruta inicial `/pos` para ambos roles. Rutas: `/login`, `/pos`, `/ventas`, `/ventas/:id`, `/productos`, `/stock`, `/clientes`, `/clientes/:id`, `/distribuidoras`, `/distribuidoras/:id`, `/compras` (pestañas Pedidos / Pagos / Cuentas), `/compras/pedidos/:id`, `/reportes/{ventas-dia,reposicion,mas-vendidos,margenes}`.
6. Búsqueda: debounce 250 ms, mínimo 2 caracteres, 20 resultados; Enter consulta sin debounce.
7. Página por defecto de listados: 20; índices de nombres con páginas de 100.
8. Montos enviados como string con 2 decimales; cálculos en centavos; formato `es-AR`/ARS; fechas mostradas en hora local del navegador (`es-AR`); filtros de fecha de ventas construidos como `[inicio del día local, inicio del día siguiente)` con offset ISO.
9. Margen ingresado como porcentaje y enviado como fracción (35 → `0.35`).
10. Listado de ventas: por defecto hoy, estados confirmada + anulada.
11. Comprobante 80 mm, nombre de comercio por `VITE_STORE_NAME` (default "Animall"), sin datos fiscales; vuelto solo en el comprobante recién emitido.
12. Medios de venta en UI: efectivo, transferencia, tarjeta. `mp` oculto (solo aparece en el reporte si tuviera monto).
13. Vendedor mostrado como "Vos" / "Otro usuario" (no hay listado de usuarios).
14. Sin historial de movimientos de stock, sin gestión de usuarios, sin modo oscuro, sin librería de gráficos (tarjetas KPI + tablas).
15. Usuarios demo: `duena@petshop.local` y `mostrador@petshop.local`; contraseñas de prueba `demo-duena-2026` / `demo-mostrador-2026` **solo** en `backend/.env.example` y `docker-compose.yml` (nunca en código).
16. Puertos: frontend 5173, API 8000, Postgres del compose 5433 en el host.
17. Variables nuevas: frontend `VITE_API_BASE_URL` (default `/api`), `VITE_PROXY_TARGET`, `VITE_USE_POLLING`, `VITE_STORE_NAME`; backend `CORS_ORIGINS`, `SEED_MOSTRADOR_PASSWORD`, `REDIS_URL=memory://` (dev/test).
18. Fallback sin Docker: SQLite (`sqlite:///./dev.db`) + `memory://`; el Postgres del sistema no se usa.

## Risks / Trade-offs

- [Vitest/Tailwind/shadcn aún no declaran Vite 8 en sus peers] → PostCSS para Tailwind; para Vitest usar la última versión compatible; si hay conflicto, `overrides` puntual en `package.json` documentado; nunca `--force` silencioso.
- [Cookie de refresh sobrevive al logout (sin endpoint)] → pista de sesión + aviso en README; seguimiento como change de auth con aprobación humana.
- [Índices de nombres cargan todo el catálogo] → aceptable para < 2.000 productos; si crece, pasar a resolución por id o a que la API incluya nombres.
- [Redis en memoria: sesiones se pierden al reiniciar la API y no se comparten entre procesos] → solo dev/test, validado al arrancar; uvicorn de desarrollo usa un proceso.
- [SQLite no reproduce el bloqueo de filas de Postgres] → la concurrencia real ya está cubierta por tests `pg_only`; el fallback es para ver la app, no para validar concurrencia.
- [Seed con fechas retrocedidas no pasa por la API] → es código de carga demo, igual que en el demo Animall; todo cambio de stock tiene movimiento y el seed está bloqueado fuera de dev/test.
- [Bind mounts en Windows: watchers lentos y `node_modules` nativos de Linux] → volumen anónimo para `node_modules` y polling opcional.
- [Precios cambian entre carrito y borrador] → D9 paso 2 sincroniza y pide reconfirmación.

## Migration Plan

No hay datos que migrar ni migraciones Alembic nuevas. Arranque local:

1. Docker: `docker compose up --build` → `http://localhost:5173` (migraciones + seed automáticos). Reinicio de datos: `docker compose down -v`.
2. Sin Docker: backend con `.env` desde `backend/.env.example` (`ENV=dev`, `DATABASE_URL=sqlite:///./dev.db`, `REDIS_URL=memory://`), `python -m scripts.init_db`, `python -m scripts.seed_demo`, `uvicorn app.main:app --reload`; frontend `npm install && npm run dev`.

Rollback: revertir los archivos del change; los adaptadores de backend son aditivos y no cambian comportamiento con la configuración por defecto de producción (`ENV=prod`, Redis real, Postgres).
