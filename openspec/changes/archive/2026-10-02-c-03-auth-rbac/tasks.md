# Tasks — c-03-auth-rbac

> TDD obligatorio (AGENTS.md): cada grupo RED → GREEN → TRIANGULATE → REFACTOR. Fixtures con passwords `test-only`; ninguna credencial real en repo ni tests.

## 1. Setup: dependencia Redis + settings por env

- [x] 1.1 Agregar `redis==7.*` a `backend/requirements.txt` y verificar con `pip install -r backend/requirements.txt --dry-run` o `pip show redis`
- [x] 1.2 Extender `Settings` (`SECRET_KEY` guard demo, `ACCESS_TOKEN_EXPIRE_MINUTES=15`, `REFRESH_TOKEN_EXPIRE_DAYS=7`, `ENV`) con validación fail-closed y verificar con `pytest backend/tests/test_config_auth.py -q` (RED-first: test arranca-con-demo-en-prod-aborta)
- [x] 1.3 Actualizar `backend/.env.example` con las nuevas TTLs/ENV y verificar por inspección que no hay secretos reales

## 2. Núcleo security: bcrypt + JWT (RED-first)

- [x] 2.1 Escribir `backend/tests/test_security_auth.py` en RED: hash/verify ok, verify ko, access con claims (`sub/rol/exp/iat/jti/type=access`), expirado rechaza, `type` equivocado rechaza — y verificar que falla antes de implementar
- [x] 2.2 Implementar `core/security.py` real (jose HS256 + passlib/bcrypt, `create_access_token`, `create_refresh_token`, `decode_token`, hash dummy anti-timing) y verificar con `pytest backend/tests/test_security_auth.py -q` en verde
- [x] 2.3 Triangular: segundo caso por comportamiento (password largo/unicode, `leeway` exp, `jti` único por token) y verificar suite verde + `ruff`/lint si aplica

## 3. Endpoints auth: login / refresh / me (RED-first)

- [x] 3.1 Escribir `backend/tests/test_auth_endpoints.py` en RED: login ok (200 + access en body + cookie HttpOnly), login ko genérico (401 sin token), usuario inactivo (401), `me` con token (200 id/email/rol/activo), `me` sin/expirado (401) — verificar que falla sin routers
- [x] 3.2 Implementar schemas Pydantic estrictos (`LoginRequest/TokenResponse/MeResponse`, `extra=forbid`) + `routers/auth.py` + registro en `main.py`, y verificar con `pytest backend/tests/test_auth_endpoints.py -q` en verde
- [x] 3.3 Escribir test RED de rotación: refresh válido rota (nuevo par + anterior invalidado), reúso del rotado → 401, expirado/revocado → 401 — verificar que falla antes del store Redis
- [x] 3.4 Implementar store Redis de refresh (`auth:refresh:<jti>` + blacklist, TTL = vida del refresh, fail-closed 503 sin Redis) y verificar suite de rotación en verde
- [x] 3.5 Triangular payloads: login malformado → 422, refresh sin cookie → 401, y verificar `pytest backend/tests/test_auth_endpoints.py -q` todo verde

## 4. RBAC: guards + POST /api/usuarios (RED-first)

- [x] 4.1 Escribir `backend/tests/test_rbac_matrix.py` en RED: matriz mostrador-bloqueado (crear usuario, acción solo-dueña parametrizada → 403), anónimo → 401, dueña crea mostrador (201 sin password + login posterior ok), sin registro público — verificar que falla sin guards
- [x] 4.2 Implementar `deps.py` (`get_current_user`, `require_role`, `require_duena`) + `routers/usuarios.py` (`POST /api/usuarios` solo dueña, bcrypt, 201 sin password) y verificar con `pytest backend/tests/test_rbac_matrix.py -q` en verde
- [x] 4.3 Triangular: dueña crea dueña ok, email duplicado → 409, rol inválido → 422, usuario desactivado pierde acceso (401 en `me`) — verificar suite verde

## 5. Hardening: rate-limit + cookies + guard SECRET_KEY + integración

- [x] 5.1 Escribir test RED de rate-limit (5 fallos IP+email → 6º 429, éxito resetea) con fakeredis/Redis test y verificar que falla sin el limiter
- [x] 5.2 Implementar rate-limit Redis (`auth:rl:<ip>:<sha256(email)>`, ventana fija 60s, solo fallos) y verificar test de 5.1 en verde
- [x] 5.3 Verificar flags de cookie (`HttpOnly`, `SameSite=Lax`, `Secure` en prod/https) con test de headers `Set-Cookie` en verde
- [x] 5.4 Integración final: `pytest backend/tests/test_security_auth.py backend/tests/test_auth_endpoints.py backend/tests/test_rbac_matrix.py -q` todo verde + `npm run lint` si toca frontend (no toca) + inspección de que `/api/health` sigue público sin token
