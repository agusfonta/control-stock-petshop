"""Minimal idempotent seed (C-02 core-models).

Creates the initial owner user via get-or-create on the natural key
(OWNER_EMAIL). The owner password comes ONLY from the SEED_OWNER_PASSWORD
environment variable — it is never hardcoded and there is no default.

Base categories and payment methods are versioned constants (no dedicated
tables in migration 0002, no preloaded catalog). Auth/hashing policy
belongs to C-03; here bcrypt is used directly for the dev seed only.

Usage:
    SEED_OWNER_PASSWORD=... python -m scripts.seed   (from backend/)
"""

import os
import sys

import bcrypt

OWNER_EMAIL = "duena@petshop.local"
OWNER_ROLE = "duena"

ROLES = ("duena", "mostrador")
CATEGORIAS_BASE = ("alimentos", "accesorios", "higiene", "farmacia")
METODOS_PAGO_BASE = ("efectivo", "transferencia", "mercadopago", "tarjeta")


def _hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def run_seed(session_factory=None, owner_password: str | None = None) -> dict:
    """Ensure the owner user exists; return a summary. Idempotent."""
    from app.core.db import SessionLocal
    from app.models import Usuario

    if owner_password is None:
        owner_password = os.environ.get("SEED_OWNER_PASSWORD")
    if not owner_password:
        raise SystemExit(
            "SEED_OWNER_PASSWORD environment variable is not set; "
            "export it with the initial owner password and retry. "
            "No default credential is used on purpose."
        )

    factory = session_factory or SessionLocal
    created = False
    with factory() as session:
        owner = session.query(Usuario).filter_by(email=OWNER_EMAIL).one_or_none()
        if owner is None:
            session.add(
                Usuario(
                    email=OWNER_EMAIL,
                    password_hash=_hash_password(owner_password),
                    rol=OWNER_ROLE,
                )
            )
            session.commit()
            created = True
    return {
        "owner_email": OWNER_EMAIL,
        "owner_created": created,
        "categorias": list(CATEGORIAS_BASE),
        "metodos_pago": list(METODOS_PAGO_BASE),
    }


def main() -> None:
    summary = run_seed()
    print(
        f"seed ok: owner={summary['owner_email']} "
        f"(created={summary['owner_created']}) "
        f"categorias={len(summary['categorias'])} "
        f"metodos_pago={len(summary['metodos_pago'])}"
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit as exc:
        print(f"seed failed: {exc.code}", file=sys.stderr)
        raise
