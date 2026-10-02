"""Nucleo security: bcrypt + JWT (C-03 task 2.1, RED-first).

Clave efimera `test-only-*` por test: ninguna credencial real en el repo.
"""

import time

import pytest

TEST_SECRET = "test-only-ephemeral-secret-key-0123456789"


def test_hash_y_verify_ok() -> None:
    from app.core.security import hash_password, verify_password

    hashed = hash_password("test-only-password")
    assert hashed != "test-only-password"
    assert hashed.startswith("$2b$")
    assert verify_password("test-only-password", hashed) is True


def test_verify_password_incorrecto_es_false() -> None:
    from app.core.security import hash_password, verify_password

    hashed = hash_password("test-only-password")
    assert verify_password("otra-clave", hashed) is False


def test_verify_hash_malformado_no_explota() -> None:
    from app.core.security import verify_password

    assert verify_password("test-only-password", "no-es-un-hash") is False


def test_access_token_trae_claims_minimos() -> None:
    from app.core.security import decode_token

    from app.core.security import create_access_token

    token = create_access_token(
        subject="user-123", rol="duena", secret_key=TEST_SECRET
    )
    payload = decode_token(token, expected_type="access", secret_key=TEST_SECRET)
    assert payload["sub"] == "user-123"
    assert payload["rol"] == "duena"
    assert payload["type"] == "access"
    assert "jti" in payload and payload["jti"]
    assert "iat" in payload and "exp" in payload
    assert payload["exp"] - payload["iat"] == 15 * 60


def test_access_expirado_se_rechaza() -> None:
    from app.core.security import InvalidTokenError, decode_token

    from app.core.security import create_access_token

    token = create_access_token(
        subject="user-123",
        rol="duena",
        secret_key=TEST_SECRET,
        expires_minutes=-1,
    )
    with pytest.raises(InvalidTokenError):
        decode_token(token, expected_type="access", secret_key=TEST_SECRET)


def test_type_equivocado_se_rechaza() -> None:
    from app.core.security import InvalidTokenError, decode_token

    from app.core.security import create_access_token, create_refresh_token

    access = create_access_token(
        subject="user-123", rol="duena", secret_key=TEST_SECRET
    )
    refresh = create_refresh_token(subject="user-123", secret_key=TEST_SECRET)
    with pytest.raises(InvalidTokenError):
        decode_token(refresh, expected_type="access", secret_key=TEST_SECRET)
    with pytest.raises(InvalidTokenError):
        decode_token(access, expected_type="refresh", secret_key=TEST_SECRET)


def test_firma_manipulada_se_rechaza() -> None:
    from app.core.security import InvalidTokenError, decode_token

    from app.core.security import create_access_token

    token = create_access_token(
        subject="user-123", rol="duena", secret_key=TEST_SECRET
    )
    manipulado = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    with pytest.raises(InvalidTokenError):
        decode_token(manipulado, expected_type="access", secret_key=TEST_SECRET)


def test_secret_distinto_no_valida() -> None:
    from app.core.security import InvalidTokenError, decode_token

    from app.core.security import create_access_token

    token = create_access_token(
        subject="user-123", rol="duena", secret_key=TEST_SECRET
    )
    with pytest.raises(InvalidTokenError):
        decode_token(
            token,
            expected_type="access",
            secret_key="test-only-otra-clave-efimera-987654321",
        )


def test_password_unicode_largo_hashea_y_verifica() -> None:
    from app.core.security import hash_password, verify_password

    clave = "test-only-ñandú-mate-🧉-segura"
    hashed = hash_password(clave)
    assert verify_password(clave, hashed) is True
    assert verify_password(clave + "x", hashed) is False


def test_leeway_tolera_desfase_pequeno_pero_no_grande() -> None:
    from app.core.security import InvalidTokenError, decode_token

    from app.core.security import create_access_token

    # Expirado hace 10s: dentro del leeway de 30s -> valido.
    token = create_access_token(
        subject="user-123",
        rol="duena",
        secret_key=TEST_SECRET,
        expires_minutes=-10 / 60,
    )
    assert (
        decode_token(token, expected_type="access", secret_key=TEST_SECRET)[
            "sub"
        ]
        == "user-123"
    )
    # Expirado hace 120s: fuera del leeway -> rechazado.
    viejo = create_access_token(
        subject="user-123",
        rol="duena",
        secret_key=TEST_SECRET,
        expires_minutes=-2,
    )
    with pytest.raises(InvalidTokenError):
        decode_token(viejo, expected_type="access", secret_key=TEST_SECRET)


def test_cada_token_tiene_jti_unico() -> None:
    from app.core.security import decode_token

    from app.core.security import create_access_token

    primero = decode_token(
        create_access_token(
            subject="user-123", rol="duena", secret_key=TEST_SECRET
        ),
        expected_type="access",
        secret_key=TEST_SECRET,
    )
    segundo = decode_token(
        create_access_token(
            subject="user-123", rol="duena", secret_key=TEST_SECRET
        ),
        expected_type="access",
        secret_key=TEST_SECRET,
    )
    assert primero["jti"] != segundo["jti"]


def test_refresh_trae_claims_y_ttl_largo() -> None:
    from app.core.security import decode_token

    from app.core.security import create_refresh_token

    token = create_refresh_token(subject="user-123", secret_key=TEST_SECRET)
    payload = decode_token(token, expected_type="refresh", secret_key=TEST_SECRET)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "refresh"
    assert "jti" in payload
    assert payload["exp"] - payload["iat"] == 7 * 24 * 3600
