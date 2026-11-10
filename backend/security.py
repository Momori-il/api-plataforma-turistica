"""Hash Argon2id y JWT HS256 con claims obligatorios."""

from datetime import datetime, timedelta, timezone
import re
import secrets
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException
import jwt

import config

password_hasher = PasswordHasher()
# El usuario inexistente también realiza una verificación Argon2.
DUMMY_PASSWORD_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def hash_password(password):
    return password_hasher.hash(password)


def verify_password(password, stored_hash):
    try:
        return password_hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def jwt_settings():
    if (
        len(config.JWT_SECRET_KEY.encode()) < 32
        or not config.JWT_SECRET_KEY.strip()
        or not 1 <= config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES <= 120
        or not config.JWT_ISSUER.strip()
        or not config.JWT_AUDIENCE.strip()
    ):
        raise HTTPException(503, "Autenticación no configurada en este entorno")
    return config.JWT_SECRET_KEY


def create_access_token(user_id):
    key = jwt_settings()
    now = datetime.now(timezone.utc)
    expires_in = config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    payload = {
        "sub": str(user_id), "iat": now, "nbf": now,
        "exp": now + timedelta(seconds=expires_in),
        "iss": config.JWT_ISSUER, "aud": config.JWT_AUDIENCE,
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, key, algorithm="HS256"), expires_in


def decode_user_id(token):
    payload = jwt.decode(
        token, jwt_settings(), algorithms=["HS256"],
        issuer=config.JWT_ISSUER, audience=config.JWT_AUDIENCE,
        options={"require": ["sub", "exp", "iat", "nbf", "iss", "aud", "jti"], "strict_aud": True},
    )
    subject = payload["sub"]
    if not isinstance(subject, str) or not re.fullmatch(r"[1-9][0-9]{0,9}", subject) or int(subject) > 2147483647:
        raise jwt.InvalidTokenError("Subject inválido")
    return int(subject)
