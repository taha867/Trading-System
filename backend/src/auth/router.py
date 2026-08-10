from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import service
from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.auth.schemas import LoginRequest, RefreshRequest, TokenPair, UserRead
from src.database import get_db

router = APIRouter()


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await service.authenticate_user(db, payload.username, payload.password)
    return service.issue_token_pair(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    return await service.refresh_access_token(db, payload.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user
