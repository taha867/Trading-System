from datetime import timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.constants import ACCESS_TOKEN_TYPE, REFRESH_TOKEN_TYPE
from src.auth.exceptions import InvalidCredentials, TokenExpired, TokenInvalid
from src.auth.models import User
from src.auth.schemas import TokenPair
from src.config import settings
from src.security import create_token, decode_token, verify_password


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    return user


def issue_token_pair(user: User) -> TokenPair:
    access_token = create_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type=ACCESS_TOKEN_TYPE,
    )
    refresh_token = create_token(
        subject=str(user.id),
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        token_type=REFRESH_TOKEN_TYPE,
    )
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> TokenPair:
    try:
        payload = decode_token(refresh_token)
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpired() from exc
    except jwt.PyJWTError as exc:
        raise TokenInvalid() from exc

    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise TokenInvalid()

    user = await db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise TokenInvalid()

    return issue_token_pair(user)
