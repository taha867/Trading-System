from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.pagination import PaginatedResponse, PaginationParams
from src.parties import service
from src.parties.dependencies import valid_party
from src.parties.models import Party
from src.parties.schemas import PartyCreate, PartyRead, PartyStatementRead, PartyUpdate

router = APIRouter(tags=["parties"])


@router.get("", response_model=PaginatedResponse[PartyRead])
async def list_parties(
    pagination: Annotated[PaginationParams, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.list_parties(db, pagination)


@router.post("", response_model=PartyRead, status_code=201)
async def create_party(
    payload: PartyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.create_party(db, payload)


@router.get("/{party_id}", response_model=PartyRead)
async def get_party(
    party: Annotated[Party, Depends(valid_party)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return party


@router.put("/{party_id}", response_model=PartyRead)
async def update_party(
    payload: PartyUpdate,
    party: Annotated[Party, Depends(valid_party)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.update_party(db, party, payload)


@router.delete("/{party_id}", status_code=204)
async def soft_delete_party(
    party: Annotated[Party, Depends(valid_party)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    await service.soft_delete_party(db, party)


@router.get("/{party_id}/statement", response_model=PartyStatementRead)
async def get_party_statement(
    party: Annotated[Party, Depends(valid_party)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.get_party_statement(db, party)
