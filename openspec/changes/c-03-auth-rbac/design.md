# Design — c-03-auth-rbac

## Context

Ver `proposal.md` (Why) y `specs/auth-rbac/spec.md` (contrato observable). Estado actual del código: `backend/app/core/security.py` son stubs que lanzan `NotImplementedError` (ver `security.py:6-22`); `backend/app/deps.py` solo expone settings (`deps.py:1-5`); `backend/app/models.py:59-67` ya persiste `Usuario(email unique, password_hash, rol Enum duena/mostrador)` con `AuditMixin.activo`; `backend/app/main.py:7-15` registra solo `health.router` bajo `/api`; `backend/requirements.txt:8-10` ya trae `python-jose`, `passlib`, `bcrypt` pero **ningún cliente Redis**; `docker-compose.yml:16-40` ya provee servicio `redis:7` y `api` lo referencia vía `REDIS_URL`. Este diseño convierte los stubs en JWT real y agrega los guards que todo change posterior reutilizará.

## Goals / Non-Goals

**Goals:**

- Auth completa y testeable (login/refresh/me + rotación con blacklist) sobre el modelo `Usuario` existente sin migración.
- Guards reutilizables (`get_current_user`, `require_role`, `require_duena`) que C-04+ aplican sin rediseño.
- Fail-closed ante Redis caído o `SECRET_KEY` demo en entorno no-dev.

**Non-Goals:**

- CRUDs de dominio, ventas, FE ARCA, frontend login (ver proposal Non-goals).
- Logout server-side con access blacklist (los access son cortos; la revocación vive en el refresh) ni rotación de `SECRET_KEY` en caliente.

## Decisions

1. **JWT HS256 con `python-jose`, claims mínimos (`sub`, `rol`, `exp`, `iat`, `jti`, `type`)** — Alternativas: `PyJWT` directo (menos helpers de expiración) o RS256 (requiere gestión de llaves, sobredimensionado para 2 roles en monolito). Se elige lo ya declarado en `requirements.txt` para no sumar superficie.
2. **Passwords con `passlib` + `bcrypt` (rounds default 12)** — Alternativa: `argon2` (mejor memoria-hard pero nueva dependencia y sin soporte ya instalado). `bcrypt==4.0.1` ya está pineado y cumple el requisito KB de bcrypt.
3. **Refresh rotativo con familia + blacklist en Redis (`auth:refresh:<jti>`, `auth:blacklist:<jti>`, TTL = vida del refresh)** — Alternativa: JWT stateless puro sin revocación (imposible cumplir "reúso = revocación" del spec) o tabla SQL de sesiones (latencia + migración innecesaria; Redis ya está en compose). El `jti` del refresh es la clave de rotación; el access lleva `jti` propio solo para trazabilidad.
4. **Refresh en cookie HttpOnly `Secure` + `SameSite=lax`, access en body `{"access_token", "token_type": "bearer"}`** — Alternativa: ambos en body (XSS roba el refresh persistente) o ambos en cookies (CSRF sobre mutaciones). La división elegida minimiza robo del long-lived y mantiene el access usable por el futuro SPA con `Authorization: Bearer`.
5. **Rate limit en Redis con llave `auth:rl:<ip>:<sha256(email)>`, ventana fija 5/60s, solo cuenta fallos** — Alternativa: slowapi en memoria (no comparte estado entre réplicas) o bloquear cuenta completa (DoS por enumeración). Hash del email evita guardar PII en claro en la llave.
6. **Guards en `deps.py`: `get_current_user` (valida Bearer, usuario activo) → `require_role(*roles)` → `require_duena = require_role("duena")`** — Alternativa: decoradores por router (duplica lógica) o middleware global (rompe `/health` público). La cadena de dependencias FastAPI es el patrón estándar y deja `/health` intacto.
7. **Nueva dependencia `redis==7.x` (sincrónica) + settings `ACCESS_TOKEN_EXPIRE_MINUTES=15`, `REFRESH_TOKEN_EXPIRE_DAYS=7`** — Alternativa: `redis[async]` (el resto del backend es sync vía `SessionLocal`; async obligaría a reescribir `db.py` fuera de scope). Sin cliente Redis hoy, login/refresh no pueden implementarse; el pin mayor 7.x acompaña la imagen `redis:7`.

## Risks / Trade-offs

- [Redis caído tumba login/refresh] → Mitigación: fail-closed explícito (`503` con mensaje, nunca bypass); `GET /api/health` sigue sin depender de Redis (spec foundation intacto).
- [`SECRET_KEY=changeme` olvidado en prod] → Mitigación: `Settings` valida al arranque y aborta si `ENV != dev/test` y la clave es demo o < 32 chars; `.env.example` documenta placeholders.
- [Cookie `Secure` rompe login en http local] → Mitigación: `Secure` se activa solo cuando `ENV=prod` o el request es https; tests usan cliente httpx con cookie jar.
- [Enumeración de emails por timing] → Mitigación: `verify_password` siempre corre (hash dummy ante email inexistente) + mensaje `401` genérico idéntico.
- [Relojes desfasados rechazan tokens válidos] → Mitigación: `leeway=30s` en validación de `exp`; documentado en design, no en spec (detalle interno).

## Migration Plan

1. Merge a `main` en rama `c-03-auth-rbac` con PR y CI verde (pytest + tsc/build).
2. Deploy sin migraciones Alembic (ningún cambio de schema; `Usuario` ya existe por C-02).
3. Post-deploy: setear `SECRET_KEY` real + TTLs en el host; smoke `POST /login → /me → /refresh` con usuario seed.
4. Rollback: revert del merge; los tokens emitidos quedan inválidos al restaurar la clave anterior (sin estado persistente que limpiar salvo llaves Redis con TTL).
