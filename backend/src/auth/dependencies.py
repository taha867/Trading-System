from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.constants import ACCESS_TOKEN_TYPE
from src.auth.exceptions import TokenExpired, TokenInvalid
from src.auth.models import User
from src.database import get_db
from src.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpired() from exc
    except jwt.PyJWTError as exc:
        raise TokenInvalid() from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise TokenInvalid()

    user = await db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise TokenInvalid()
    return user
