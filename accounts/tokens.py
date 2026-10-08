import uuid
from datetime import datetime, timedelta, timezone
import jwt
from django.conf import settings
from accounts.models import RefreshToken, User

ACCESS = "access"
REFRESH = "refresh"


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": str(user.id),
        "role": user.role,
        "type": ACCESS,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_LIFETIME_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_LIFETIME_DAYS)

    # Save the token id in the database so that we can revoke it later (logout / refresh / password change)
    record = RefreshToken.objects.create(user=user, expires_at=expires_at)

    payload = {
        "user_id": str(user.id),
        "type": REFRESH,
        "jti": str(record.jti),
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.JWT_REFRESH_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, token_type: str) -> dict:
    # Raises jwt.ExpiredSignatureError / jwt.InvalidTokenError when the token is not good.
    # Access and refresh tokens are signed with two different secret keys.
    secret = settings.JWT_SECRET_KEY if token_type == ACCESS else settings.JWT_REFRESH_SECRET_KEY

    payload = jwt.decode(
        token,
        secret,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["exp", "iat", "user_id", "type", "jti"]},
    )
    if payload["type"] != token_type:
        raise jwt.InvalidTokenError(f"Expected a {token_type} token")
    return payload


def build_token_response(user: User) -> dict:
    # Used by login and refresh: returns both tokens, ready to paste into Postman
    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "token_type": "Bearer",
        "access_token_expires_in": settings.ACCESS_TOKEN_LIFETIME_MINUTES * 60,
        "refresh_token_expires_in": settings.REFRESH_TOKEN_LIFETIME_DAYS * 24 * 60 * 60,
    }


def revoke_all_refresh_tokens(user: User) -> int:
    return RefreshToken.objects.filter(user=user, revoked=False).update(revoked=True)