"""Rate limit de login: ventana fija 5 fallos / 60s por IP+email.

Llave `auth:rl:<ip>:<sha256(email)>` (design decision 5): solo cuentan los
fallos; el exito resetea. Sin Redis -> el caller falla cerrado (503).
"""

import hashlib

PREFIX = "auth:rl:"
MAX_FAILURES = 5
WINDOW_SECONDS = 60


def key_for(ip: str, email: str) -> str:
    """Llave estable sin PII en claro (email normalizado + hash)."""
    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
    return f"{PREFIX}{ip}:{digest}"


def failures(client, *, ip: str, email: str) -> int:
    """Cuenta fallos en la ventana actual (0 si no hay)."""
    value = client.get(key_for(ip, email))
    return int(value) if value is not None else 0


def register_failure(client, *, ip: str, email: str) -> int:
    """Suma un fallo y fija la ventana de 60s en el primero."""
    key = key_for(ip, email)
    count = int(client.incr(key))
    if count == 1:
        client.expire(key, WINDOW_SECONDS)
    return count


def reset(client, *, ip: str, email: str) -> None:
    """Limpia el contador ante un login exitoso."""
    client.delete(key_for(ip, email))


def retry_after_seconds(client, *, ip: str, email: str) -> int:
    """Segundos restantes de ventana (para header Retry-After)."""
    ttl = client.ttl(key_for(ip, email))
    return max(int(ttl), 0) if ttl and ttl > 0 else WINDOW_SECONDS
