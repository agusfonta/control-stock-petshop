# DevOps y Despliegue

El usuario pide recomendación concreta dónde subir BE/FE/DB (riesgo top de Discovery). Prioridad: costo bajo + mantenibilidad.

## Opción A (recomendada costo bajo)

- **FE (React+Vite)**: Vercel o Netlify (gratis/hobby, TLS y preview incluidos). El demo ya trae `vercel.json`.
- **BE (FastAPI)**: Render Web Service o Railway (plan starter, docker directo, env + logs simples).
- **DB + Redis**: mismo proveedor que BE (Render Postgres + Render Redis / Railway Postgres+Redis) para no pagar inter-región ni latencia.
- **Backups**: snapshots diarios del proveedor + `pg_dump` semanal a objeto barato (R2/S3).

Pro: barato y simple. Contra: Render free duerme; usar plan pago mínimo para el local.

## Opción B (un solo VPS)

- VPS (Hetzner/Contabo) con Docker Compose (api + db + redis + caddy), backups a objeto externo.
- Pro: costo fijo predecible. Contra: operás vos (updates, TLS, monitoreo).

## Opción C (AWS/GCP)

- Solo si escala a multi-local/SaaS. Hoy overkill en costo y operación.

## Recomendación

Empezar con Opción A (Vercel + Render/Railway con Postgres+Redis pagos mínimos), con `render.yaml`/`docker-compose.yml` versionados. Pasar a VPS solo si el costo mensual lo justifica. Offline total queda para v2 por diseño.
