# Spec Delta

## Purpose

Establecer los cimientos observables del proyecto: health check público, entorno local reproducible con compose, CI paralela y plantilla CSV canónica para la futura migración de productos.

## ADDED Requirements

### Requirement: Health check público sin dependencias

The system SHALL exponer `GET /api/health` que responde `200` con cuerpo `{"status":"ok","version": string}` validado por schema Pydantic estricto `HealthResponse`, sin requerir DB, Redis ni auth.

#### Scenario: Health responde ok

- **WHEN** un cliente hace `GET /api/health`
- **THEN** el sistema responde `200` con `status == "ok"` y `version == "0.1.0"`

#### Scenario: Health no exige auth ni DB

- **WHEN** se llama a `GET /api/health` sin token y con DB/Redis caídos
- **THEN** el sistema responde `200` igualmente (los checks con DB/Redis van en C-15)

### Requirement: Entorno local con compose

The system SHALL proveer `docker compose up` con servicios `api` (puerto 8000), `db` (Postgres 16, volumen `pgdata`, healthcheck `pg_isready`) y `redis` (7, volumen `redisdata`, healthcheck `redis-cli ping`); `api` SHALL arrancar solo tras `db` healthy (`depends_on` con `condition: service_healthy`).

#### Scenario: Compose levanta 3 servicios sanos

- **WHEN** un dev nuevo ejecuta `docker compose up --build`
- **THEN** los 3 servicios quedan en estado healthy y `curl localhost:8000/api/health` responde `{"status":"ok","version":"0.1.0"}`

### Requirement: CI paralela backend/frontend

The system SHALL proveer `.github/workflows/ci.yml` con jobs paralelos `backend` (pytest) y `frontend` (tsc + build) que corren en cada PR a `main`.

#### Scenario: CI verde en PR

- **WHEN** se abre un PR contra `main`
- **THEN** ambos jobs `backend` y `frontend` corren en paralelo y deben estar en verde para mergear

### Requirement: Plantilla CSV canónica versionada

The system SHALL versionar `data/plantilla_productos.csv` con headers exactos `sku,nombre,categoria,costo,margen_pct,stock_actual,stock_minimo,distribuidora` y 3 filas ejemplo válidas (la validación real va en C-08).

#### Scenario: Plantilla con columnas exactas

- **WHEN** se lee la primera línea de `data/plantilla_productos.csv`
- **THEN** contiene exactamente `sku,nombre,categoria,costo,margen_pct,stock_actual,stock_minimo,distribuidora` y hay al menos 3 filas de datos
