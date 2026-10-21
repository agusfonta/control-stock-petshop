# Demo de Animall en Render (plan gratis)

> **Advertencia: esto es una DEMO. No cargues nunca datos reales** (clientes, ventas, precios de verdad). La base gratis vence, no tiene backups y se puede reiniciar en cualquier momento. Los usuarios son `@petshop.local`.

Con un solo Blueprint (`render.yaml`, en la raíz del repo) Render crea: el backend (web service Docker), la base PostgreSQL, el Redis (Key Value) y el frontend (Static Site). Todo en plan **Free** y en la región **Virginia**.

## Requisitos

- Una cuenta de [Render](https://render.com) conectada a tu cuenta de GitHub, con acceso a este repositorio.
- Que el código con `render.yaml` esté en la rama que vas a elegir (`main`, o la rama del change si todavía no se mergeó).
- Dos contraseñas a elección para los usuarios demo (anotalas, no las subas al repo).

## Pasos

1. En Render: **New → Blueprint**.
2. Elegí el repositorio y la **rama**. Render lee `render.yaml` y muestra los 4 recursos.
3. Completá lo que te pide:
   - `SEED_OWNER_PASSWORD`: contraseña de la dueña (`duena@petshop.local`).
   - `SEED_MOSTRADOR_PASSWORD`: contraseña del mostrador (`mostrador@petshop.local`).
4. **Apply**. El primer deploy tarda varios minutos (construye la imagen y el frontend).

Qué completás vos y qué genera Render:

| Variable | Quién la define |
|---|---|
| `SEED_OWNER_PASSWORD`, `SEED_MOSTRADOR_PASSWORD` | Vos, al crear el Blueprint |
| `SECRET_KEY` | Render (valor aleatorio) |
| `DATABASE_URL`, `REDIS_URL` | Render, desde la base y el Key Value del Blueprint |
| `ENV=staging`, `SEED_DEMO_AL_ARRANCAR=true`, `PORT`, `CORS_ORIGINS` | Ya están en `render.yaml` |

Al arrancar, el backend aplica las migraciones y carga los datos demo (solo la primera vez; no repite ni cambia contraseñas).

## Cómo verificar que funciona

1. Abrí `https://animall-demo-api.onrender.com/api/health`: debe responder `200`.
2. Abrí `https://animall-demo.onrender.com` e ingresá con `duena@petshop.local` (o `mostrador@petshop.local`) y la contraseña que elegiste.
3. Recargá la página (por ejemplo en `/stock`): tiene que seguir mostrando la app y mantener la sesión.
4. Entrá a Reportes: deben verse datos.

### Si la URL del backend no es `animall-demo-api.onrender.com`

Si el nombre ya estaba ocupado, Render asigna otro subdominio. Copiá la URL real del servicio `animall-demo-api` (panel de Render) y corregí:

- En `render.yaml`, el `destination` de la regla `/api/*` del Static Site, y hacer commit; o directamente en el panel, en el Static Site → **Redirects/Rewrites**.
- Lo mismo con `CORS_ORIGINS` si la URL del frontend no es `animall-demo.onrender.com`.

## Límites del plan gratis (importante)

- **El backend se duerme** tras ~15 minutos sin uso. La primera visita después tarda ~1 minuto y puede mostrar un error: esperá y recargá.
- **La base PostgreSQL gratis vence a los 30 días** y se borra a los 14 días de gracia posteriores. Sin backups.
- **El Redis gratis no guarda datos**: si se reinicia hay que volver a iniciar sesión.
- Sin shell ni tareas manuales en el plan gratis (por eso el seed corre al arrancar).
- El límite de intentos de login es efectivamente por email (todas las solicitudes llegan con la IP del proxy): 5 intentos fallidos bloquean ese email 1 minuto para todas.
- La documentación de la API (`/docs`) queda visible en la demo.

## Reiniciar los datos

En el panel de Render, borrá la base `animall-demo-db`, volvé a **sincronizar el Blueprint** (recrea la base) y reiniciá el backend: migra y vuelve a cargar los datos demo. Esto sirve también cuando la base vence, o si un deploy se cortó a mitad del primer seed.

## Borrar la demo

Panel de Render → el Blueprint → eliminar los recursos (los 4). No afecta el repo ni tu entorno local.

## Nota técnica

El navegador solo habla con la URL del frontend: el Static Site reenvía `/api/*` al backend (rewrite), así la cookie de sesión funciona sin CORS. Verificá en el primer deploy que el login y la recarga mantienen la sesión; si no, avisá (hay un plan B que requiere cambiar la configuración de auth, como change aparte).
