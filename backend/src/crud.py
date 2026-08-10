from typing import Annotated, Type, TypeVar

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.exceptions import ConflictException, NotFoundException
from src.pagination import PaginatedResponse, PaginationParams

ModelT = TypeVar("ModelT")
CreateT = TypeVar("CreateT", bound=BaseModel)
ReadT = TypeVar("ReadT", bound=BaseModel)
UpdateT = TypeVar("UpdateT", bound=BaseModel)


def build_crud_router(
    *,
    model: Type[ModelT],
    create_schema: Type[CreateT],
    read_schema: Type[ReadT],
    update_schema: Type[UpdateT],
    prefix: str,
    tags: list[str],
) -> APIRouter:
    assert hasattr(model, "is_active"), (
        f"{model.__name__} must declare `is_active` to be used with the generic CRUD factory"
    )

    router = APIRouter(prefix=prefix, tags=tags)

    async def _get_active_or_404(db: AsyncSession, item_id: int) -> ModelT:
        item = await db.get(model, item_id)
        if not item or not item.is_active:
            raise NotFoundException(f"{model.__name__} not found")
        return item

    @router.get("", response_model=PaginatedResponse[read_schema])
    async def list_items(
        pagination: Annotated[PaginationParams, Query()],
        db: Annotated[AsyncSession, Depends(get_db)],
        _current_user: Annotated[User, Depends(get_current_user)],
    ):
        offset = (pagination.page - 1) * pagination.page_size

        total = await db.scalar(
            select(func.count()).select_from(model).where(model.is_active.is_(True))
        )
        result = await db.execute(
            select(model)
            .where(model.is_active.is_(True))
            .order_by(model.id)
            .offset(offset)
            .limit(pagination.page_size)
        )
        items = result.scalars().all()

        return PaginatedResponse[read_schema](
            items=items,
            total=total or 0,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    @router.post("", response_model=read_schema, status_code=201)
    async def create_item(
        payload: create_schema,
        db: Annotated[AsyncSession, Depends(get_db)],
        _current_user: Annotated[User, Depends(get_current_user)],
    ):
        item = model(**payload.model_dump())
        db.add(item)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(f"{model.__name__} already exists") from exc
        await db.refresh(item)
        return item

    @router.get("/{item_id}", response_model=read_schema)
    async def get_item(
        item_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
        _current_user: Annotated[User, Depends(get_current_user)],
    ):
        return await _get_active_or_404(db, item_id)

    @router.put("/{item_id}", response_model=read_schema)
    async def update_item(
        item_id: int,
        payload: update_schema,
        db: Annotated[AsyncSession, Depends(get_db)],
        _current_user: Annotated[User, Depends(get_current_user)],
    ):
        item = await _get_active_or_404(db, item_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(f"{model.__name__} already exists") from exc
        await db.refresh(item)
        return item

    @router.delete("/{item_id}", status_code=204)
    async def soft_delete_item(
        item_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
        _current_user: Annotated[User, Depends(get_current_user)],
    ):
        item = await _get_active_or_404(db, item_id)
        item.is_active = False
        await db.commit()

    return router
