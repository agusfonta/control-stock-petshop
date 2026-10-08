"""Minimal idempotent seed (C-02 core-models).

Creates the initial owner user via get-or-create on the natural key
(OWNER_EMAIL). The owner password comes ONLY from the SEED_OWNER_PASSWORD
environment variable — it is never hardcoded and there is no default.

Usage:
    SEED_OWNER_PASSWORD=... python -m scripts.seed   (from backend/)
"""

import os
import sys

from app.core.security import hash_password

OWNER_EMAIL = "duena@petshop.local"
OWNER_ROLE = "duena"


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
                    password_hash=hash_password(owner_password),
                    rol=OWNER_ROLE,
                )
            )
            session.commit()
            created = True
    return {
        "owner_email": OWNER_EMAIL,
        "owner_created": created,
    }


def main() -> None:
    summary = run_seed()
    print(
        f"seed ok: owner={summary['owner_email']} "
        f"(created={summary['owner_created']})"
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit as exc:
        print(f"seed failed: {exc.code}", file=sys.stderr)
        raise
