
import os
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash


ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not SECRET_KEY:
    if ENVIRONMENT == "production":
        raise RuntimeError(
            "JWT_SECRET_KEY must be configured in production."
        )

    SECRET_KEY = "local-development-secret-change-this-before-deployment"

if len(SECRET_KEY) < 32:
    raise RuntimeError(
        "JWT_SECRET_KEY must contain at least 32 characters."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(member_id: int, role: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(member_id),
        "role": role,
        "exp": expires_at,
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
    )
