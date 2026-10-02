"""Store de refresh tokens en Redis: familias + blacklist con TTL.

Claves:
- `auth:refresh:<jti>` -> JSON {sub, fam}, expira con la vida del refresh.
- `auth:family:<fam>`  -> set de jtis vivos de la familia (rotacion/revocacion).
- `auth:blacklist:<jti>` -> marca de refresh rotado/revocado (detecta reuso).
"""

import json

REFRESH_PREFIX = "auth:refresh:"
BLACKLIST_PREFIX = "auth:blacklist:"
FAMILY_PREFIX = "auth:family:"


def save_refresh(
    client, *, jti: str, subject: str, family: str, ttl_seconds: int
) -> None:
    """Persiste un refresh recien emitido junto a su familia."""
    pipe = client.pipeline()
    pipe.set(
        f"{REFRESH_PREFIX}{jti}",
        json.dumps({"sub": subject, "fam": family}),
        ex=ttl_seconds,
    )
    pipe.sadd(f"{FAMILY_PREFIX}{family}", jti)
    pipe.expire(f"{FAMILY_PREFIX}{family}", ttl_seconds)
    pipe.execute()


def is_blacklisted(client, *, jti: str) -> bool:
    """Indica si un jti fue rotado o revocado (reuso -> 401 + revoca)."""
    return bool(client.exists(f"{BLACKLIST_PREFIX}{jti}"))


def get_refresh(client, *, jti: str) -> dict | None:
    """Devuelve {sub, fam} del refresh vivo, o None si no existe."""
    raw = client.get(f"{REFRESH_PREFIX}{jti}")
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or "sub" not in data or "fam" not in data:
        return None
    return data


def rotate_refresh(
    client,
    *,
    old_jti: str,
    new_jti: str,
    subject: str,
    family: str,
    ttl_seconds: int,
) -> None:
    """Rotacion: invalida el jti viejo (blacklist) y persiste el nuevo."""
    pipe = client.pipeline()
    pipe.delete(f"{REFRESH_PREFIX}{old_jti}")
    pipe.set(f"{BLACKLIST_PREFIX}{old_jti}", family, ex=ttl_seconds)
    pipe.set(
        f"{REFRESH_PREFIX}{new_jti}",
        json.dumps({"sub": subject, "fam": family}),
        ex=ttl_seconds,
    )
    pipe.sadd(f"{FAMILY_PREFIX}{family}", new_jti)
    pipe.expire(f"{FAMILY_PREFIX}{family}", ttl_seconds)
    pipe.execute()


def revoke_family(client, *, family: str, ttl_seconds: int) -> None:
    """Revoca la cadena completa ante reuso: borra vivos y los blacklista."""
    members = client.smembers(f"{FAMILY_PREFIX}{family}")
    pipe = client.pipeline()
    for member in members:
        pipe.delete(f"{REFRESH_PREFIX}{member}")
        pipe.set(f"{BLACKLIST_PREFIX}{member}", family, ex=ttl_seconds)
    pipe.delete(f"{FAMILY_PREFIX}{family}")
    pipe.execute()
