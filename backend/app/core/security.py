"""Security real (C-03): bcrypt via passlib + JWT HS256 via python-jose.

Claims minimos: sub/rol/exp/iat/jti/type. Expiracion con leeway 30s
(design: relojes desfasados). `verify_password` nunca propaga excepciones
por hash malformado (timing/enumeracion: login siempre compara).
"""

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

ALGORITHM = "HS256"
ACCESS_TYPE = "access"
REFRESH_TYPE = "refresh"
LEEWAY_SECONDS = 30

_pwd = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=get_settings().bcrypt_rounds,
)

# Hash dummy para anti-timing: ante email inexistente el login compara
# contra este valor (hash valido, bcrypt corre completo) para no revelar
# existencia por tiempo de respuesta.
DUMMY_HASH = _pwd.hash("dummy-anti-timing-seed")


class InvalidTokenError(ValueError):
    """Token ausente, expirado, manipulado o de tipo inesperado."""


def hash_password(plain: str) -> str:
    """Hashea un password con bcrypt (rounds de `Settings.bcrypt_rounds`)."""
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Compara password; hash malformado -> False (nunca explota)."""
    try:
        return bool(_pwd.verify(plain, hashed))
    except (ValueError, AttributeError):
        return False


def _secret(secret_key: str | None) -> str:
    return secret_key if secret_key is not None else get_settings().secret_key


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    subject: str,
    rol: str,
    secret_key: str | None = None,
    expires_minutes: int | None = None,
) -> str:
    """Emite JWT access corto con claims minimos + jti de trazabilidad."""
    ttl = (
        expires_minutes
        if expires_minutes is not None
        else get_settings().access_token_expire_minutes
    )
    now = _now()
    payload = {
        "sub": subject,
        "rol": rol,
        "type": ACCESS_TYPE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, _secret(secret_key), algorithm=ALGORITHM)


def create_refresh_token(
    subject: str,
    secret_key: str | None = None,
    expires_days: int | None = None,
    family: str | None = None,
) -> str:
    """Emite JWT refresh largo; la revocacion vive en Redis (store)."""
    ttl = (
        expires_days
        if expires_days is not None
        else get_settings().refresh_token_expire_days
    )
    now = _now()
    payload = {
        "sub": subject,
        "type": REFRESH_TYPE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=ttl)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if family is not None:
        payload["fam"] = family
    return jwt.encode(payload, _secret(secret_key), algorithm=ALGORITHM)


def decode_token(
    token: str,
    expected_type: str = ACCESS_TYPE,
    secret_key: str | None = None,
    leeway_seconds: int = LEEWAY_SECONDS,
) -> dict:
    """Valida firma, expiracion (con leeway) y claim `type`.

    Cualquier desvio -> InvalidTokenError (mensaje generico, sin detalle).
    """
    try:
        payload = jwt.decode(
            token,
            _secret(secret_key),
            algorithms=[ALGORITHM],
            options={
                "require": ["sub", "exp", "iat", "jti", "type"],
                "leeway": leeway_seconds,
            },
        )
    except JWTError as exc:
        raise InvalidTokenError("token invalido o expirado") from exc
    if payload.get("type") != expected_type:
        raise InvalidTokenError("token invalido o expirado")
    return payload
