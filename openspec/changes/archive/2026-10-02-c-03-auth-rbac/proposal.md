# Proposal — c-03-auth-rbac

## Why

Sin autenticación, todo lo construido en C-01/C-02 queda abierto: cualquier cliente podría mutar catálogo y stock. Este change cierra ese hueco con JWT + RBAC dueña/mostrador (RN-AU-01, RN-AU-02) y desbloquea todo el resto del roadmap (C-04 en adelante exige endpoints protegidos).

## What Changes

- `POST /api/auth/login` — valida email + password con bcrypt, emite JWT access corto + refresh; rate limiting 5 intentos/60s por par IP+email (contadores en Redis).
- `POST /api/auth/refresh` — rotación de refresh tokens con blacklist/revocación en Redis; refresh viaja en cookie HttpOnly (`Secure`, `SameSite=lax`), nunca en body JSON persistido.
- `GET /api/auth/me` — devuelve usuario actual + rol desde el access token.
- `deps.py`: `get_current_user()`, `require_role(*roles)`, `require_duena()`; todo endpoint sensible futuro usa `require_roles()`/`require_duena()`.
- `POST /api/usuarios` — solo dueña crea usuarios (sin registro público); schemas Pydantic estrictos para login/refresh/me/crear-usuario.
- `core/security.py`: JWT real con `python-jose` (HS256) + `passlib`/`bcrypt`; reemplaza los stubs `NotImplementedError` de C-01.
- Config: `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` solo por env; `SECRET_KEY=changeme` bloquea arranque fuera de dev/test.
- Dependencia nueva: cliente Redis (`redis==7.x`) — `requirements.txt` hoy no trae ninguno y la rotación/blacklist + rate-limit lo exigen.
- Tests TDD (RED-first): login ok/ko, token expirado, refresh rotation (reúso = revocación), matriz RBAC (mostrador bloqueado en `POST /api/usuarios` y rutas de config).

## Capabilities

### New Capabilities

- `auth-rbac`: autenticación JWT (login/refresh/me, rotación con blacklist en Redis, rate limiting, cookie HttpOnly) + autorización RBAC dueña/mostrador (guards, creación de usuarios solo por dueña, sin registro público).

### Modified Capabilities

_(ninguna — `foundation` y `core-models` no cambian requisitos; el modelo `Usuario` de C-02 ya trae `email/rol/activo` y se reutiliza sin alterar su spec)_

## Impact

- Código: `backend/app/core/security.py` (JWT real), `backend/app/deps.py` (guards), `backend/app/schemas.py` (schemas auth estrictos), `backend/app/routers/auth.py` + `backend/app/routers/usuarios.py` (nuevos), `backend/app/main.py` (registro routers), `backend/requirements.txt` (+`redis`), `.env.example` (nuevas TTLs), `core/config.py` (nuevos settings).
- APIs: 4 endpoints nuevos (`/api/auth/login`, `/api/auth/refresh`, `/api/auth/me`, `/api/usuarios`); ningún endpoint existente cambia comportamiento (`/api/health` sigue público).
- Sistemas: requiere Redis levantado (compose ya lo provee); sin Redis, login/refresh fallan cerrado (fail-closed).
- Non-goals: CRUDs de dominio (C-04+), ventas (C-10), FE ARCA (C-11), frontend login (C-13).
