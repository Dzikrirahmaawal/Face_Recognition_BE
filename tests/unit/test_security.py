from __future__ import annotations

import uuid

import jwt
import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_kiosk_token,
    hash_kiosk_token,
    hash_password,
    token_hash,
    validate_password_strength,
    verify_password,
)


def test_password_hashing_round_trip():
    hashed = hash_password("Str0ng-Password!")
    assert hashed.startswith("$argon2")
    assert verify_password("Str0ng-Password!", hashed) is True
    assert verify_password("wrong", hashed) is False


@pytest.mark.parametrize(
    ("password", "expected_issue"),
    [
        ("short1!", "at least"),
        ("alllowercase123!", "uppercase"),
        ("ALLUPPERCASE123!", "lowercase"),
        ("NoDigitsHere!", "digit"),
        ("NoSpecial12345", "special"),
    ],
)
def test_password_strength_rules(password, expected_issue):
    errors = validate_password_strength(password)
    assert any(expected_issue in error for error in errors)


def test_password_strength_accepts_valid_password():
    assert validate_password_strength("V4lid-Password!") == []


def test_access_and_refresh_token_claims():
    user_id = uuid.uuid4()
    access = create_access_token(user_id, "ADMIN", 3)
    payload = decode_token(access, expected_type="access")
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "ADMIN"
    assert payload["tv"] == 3
    assert isinstance(payload["exp"], int)
    assert isinstance(payload["iat"], int)

    refresh, claims = create_refresh_token(user_id, "ADMIN", 3)
    decoded_refresh = decode_token(refresh, expected_type="refresh")
    assert decoded_refresh["jti"] == claims["jti"]
    assert decoded_refresh["type"] == "refresh"


def test_token_type_mismatch_is_rejected():
    token = create_access_token(uuid.uuid4(), "VIEWER", 0)
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, expected_type="refresh")


def test_token_hash_and_kiosk_token_are_deterministic():
    token = generate_kiosk_token()
    assert token.startswith("kiosk_")
    assert hash_kiosk_token(token) == hash_kiosk_token(token)
    assert hash_kiosk_token(token) != hash_kiosk_token(generate_kiosk_token())
    assert token_hash(token) == token_hash(token)
    assert len(token_hash(token)) == 64
