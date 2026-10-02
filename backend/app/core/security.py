"""Security helpers. C-01 STUB: real JWT (python-jose + passlib/bcrypt) lands in C-03."""

from typing import NoReturn


def _not_implemented() -> NoReturn:
    raise NotImplementedError("JWT auth is implemented in C-03")


def hash_password(_plain: str) -> NoReturn:
    """Hash a password (stub)."""
    _not_implemented()


def verify_password(_plain: str, _hashed: str) -> NoReturn:
    """Verify a password against its hash (stub)."""
    _not_implemented()


def create_access_token(_subject: str) -> NoReturn:
    """Create a JWT access token (stub)."""
    _not_implemented()
