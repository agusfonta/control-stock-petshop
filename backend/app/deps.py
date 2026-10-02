"""Shared FastAPI dependencies: settings, DB, Redis, identidad actual.

C-03: get_db/get_redis/get_current_user. Los guards de rol
(require_role/require_duena) llegan con el grupo 4 (RBAC).
"""

from collections.abc import Callable, Generator

import redis as redis_lib
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import InvalidTokenError, decode_token
from app.models import Usuario

__all__ = [
    "Settings",
    "get_settings",
    "get_db",
    "get_redis",
    "get_current_user",
    "require_role",
    "require_duena",
]

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """Sesion SQLAlchemy por request (testeable via dependency_overrides)."""
    from app.core.db import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_redis(settings: Settings = Depends(get_settings)) -> redis_lib.Redis:
    """Cliente Redis sincronico (design decision 7); testeable con fakeredis."""
    return redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Usuario:
    """Valida el Bearer access y devuelve el usuario activo.

    Sin token, token invalido/expirado, usuario inexistente o desactivado
    -> 401 generico (sin distinguir causa).
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="no autenticado",
        )
    try:
        payload = decode_token(
            credentials.credentials,
            expected_type="access",
            secret_key=settings.secret_key,
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="no autenticado",
        ) from None
    user = db.get(Usuario, payload["sub"])
    if user is None or not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="no autenticado",
        )
    return user


def require_role(*roles: str) -> Callable:
    """Guard reutilizable: exige uno de los roles (sino 403).

    Todo endpoint sensible futuro usa `Depends(require_role(...))` o
    `Depends(require_duena)` (regla dura AGENTS.md: require_roles()).
    """

    def _guard(current: Usuario = Depends(get_current_user)) -> Usuario:
        if str(current.rol) not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="permiso denegado",
            )
        return current

    return _guard


require_duena = require_role("duena")
