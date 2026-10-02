"""Auth router: login (emite par) + me (identidad actual).

El refresh viaja SOLO en cookie HttpOnly; la rotacion vive en
POST /api/auth/refresh (grupo 3.4). Rate limiting en 5.2.
"""

import uuid

import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app import deps
from app.core import security
from app.core.config import Settings, get_settings
from app.core.rate_limit import (
    MAX_FAILURES,
    failures,
    register_failure,
    reset,
    retry_after_seconds,
)
from app.core.refresh_store import (
    get_refresh,
    is_blacklisted,
    revoke_family,
    rotate_refresh,
    save_refresh,
)
from app.models import Usuario
from app.schemas import LoginRequest, MeResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
GENERIC_401 = "credenciales invalidas"
SESSION_UNAVAILABLE = "servicio de sesion no disponible"


def _secure_cookie(request: Request, settings: Settings) -> bool:
    """Secure solo en prod o sobre https (design: no romper http local)."""
    return settings.env == "prod" or request.url.scheme == "https"


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(deps.get_db),
    cache: redis_lib.Redis = Depends(deps.get_redis),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Valida credenciales y emite access (body) + refresh (cookie)."""
    ip = request.client.host if request.client else "unknown"
    try:
        if failures(cache, ip=ip, email=data.email) >= MAX_FAILURES:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="demasiados intentos, reintente mas tarde",
                headers={
                    "Retry-After": str(
                        retry_after_seconds(cache, ip=ip, email=data.email)
                    )
                },
            )
    except redis_lib.exceptions.RedisError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=SESSION_UNAVAILABLE,
        ) from None
    user = db.query(Usuario).filter_by(email=data.email).one_or_none()
    presented = security.verify_password(
        data.password, user.password_hash if user else security.DUMMY_HASH
    )
    if user is None or not presented or not user.activo:
        try:
            register_failure(cache, ip=ip, email=data.email)
        except redis_lib.exceptions.RedisError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=SESSION_UNAVAILABLE,
            ) from None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_401
        )
    try:
        reset(cache, ip=ip, email=data.email)
    except redis_lib.exceptions.RedisError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=SESSION_UNAVAILABLE,
        ) from None
    access = security.create_access_token(
        user.id, user.rol, secret_key=settings.secret_key
    )
    family = uuid.uuid4().hex
    refresh = security.create_refresh_token(
        user.id, secret_key=settings.secret_key, family=family
    )
    jti = security.decode_token(
        refresh, expected_type="refresh", secret_key=settings.secret_key
    )["jti"]
    try:
        save_refresh(
            cache,
            jti=jti,
            subject=user.id,
            family=family,
            ttl_seconds=settings.refresh_token_expire_days * 86400,
        )
    except redis_lib.exceptions.RedisError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=SESSION_UNAVAILABLE,
        ) from None
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh,
        httponly=True,
        samesite="lax",
        secure=_secure_cookie(request, settings),
        path="/api/auth",
    )
    return TokenResponse(access_token=access, token_type="bearer")


@router.get("/me", response_model=MeResponse)
def me(current: Usuario = Depends(deps.get_current_user)) -> MeResponse:
    """Devuelve identidad y rol del usuario del access token."""
    return MeResponse(
        id=current.id, email=current.email, rol=current.rol, activo=current.activo
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(deps.get_db),
    cache: redis_lib.Redis = Depends(deps.get_redis),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """Rota el refresh de la cookie: emite un par nuevo e invalida el anterior.

    Reusar un refresh ya rotado revoca la cadena completa (401 en adelante).
    """
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_401
        )
    try:
        payload = security.decode_token(
            raw, expected_type="refresh", secret_key=settings.secret_key
        )
    except security.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_401
        ) from None
    jti = payload["jti"]
    subject = payload["sub"]
    family = payload.get("fam")
    if not family:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_401
        )
    ttl_seconds = settings.refresh_token_expire_days * 86400
    try:
        if is_blacklisted(cache, jti=jti):
            revoke_family(cache, family=family, ttl_seconds=ttl_seconds)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_401
            )
        entry = get_refresh(cache, jti=jti)
        if entry is None or entry["sub"] != subject or entry["fam"] != family:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_401
            )
        user = db.get(Usuario, subject)
        if user is None or not user.activo:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_401
            )
        access = security.create_access_token(
            user.id, user.rol, secret_key=settings.secret_key
        )
        new_refresh = security.create_refresh_token(
            user.id, secret_key=settings.secret_key, family=family
        )
        new_jti = security.decode_token(
            new_refresh, expected_type="refresh", secret_key=settings.secret_key
        )["jti"]
        rotate_refresh(
            cache,
            old_jti=jti,
            new_jti=new_jti,
            subject=user.id,
            family=family,
            ttl_seconds=ttl_seconds,
        )
    except redis_lib.exceptions.RedisError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=SESSION_UNAVAILABLE,
        ) from None
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=new_refresh,
        httponly=True,
        samesite="lax",
        secure=_secure_cookie(request, settings),
        path="/api/auth",
    )
    return TokenResponse(access_token=access, token_type="bearer")
