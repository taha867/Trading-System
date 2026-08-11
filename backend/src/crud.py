from typing import Annotated, Sequence, Type, TypeVar

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, create_model
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
    exact_filters: Sequence[str] = (),
    search_filters: Sequence[str] = (),
) -> APIRouter:
    assert hasattr(model, "is_active"), (
        f"{model.__name__} must declare `is_active` to be used with the generic CRUD factory"
    )

    router = APIRouter(prefix=prefix, tags=tags)

    # Filtering happens in the database, not by fetching a page and scanning it in
    # JS — a list already past the 100-row page cap (Items, for one) would silently
    # miss matches under client-side filtering. `exact_filters` are FK/id columns
    # matched by equality (dropdown-driven); `search_filters` are free-text columns
    # matched case-insensitively as a substring (a search box, not a dropdown).
    #
    # Built as one Pydantic model extending PaginationParams — not a second,
    # separate `Annotated[..., Query()]` parameter — because FastAPI 0.141 doesn't
    # flatten two independent Query-model parameters on the same endpoint (the
    # second one starts erroring "field required" even though every field on it is
    # optional). One combined model is also just the correct shape: page/page_size
    # and the filters all live in the same query string together.
    filter_fields = {name: (int | None, None) for name in exact_filters}
    filter_fields.update({name: (str | None, None) for name in search_filters})
    ListParams = create_model(f"{model.__name__}ListParams", __base__=PaginationParams, **filter_fields)

    def _apply_filters(stmt, params: BaseModel):
        values = params.model_dump(exclude_none=True)
        for name in exact_filters:
            if name in values:
                stmt = stmt.where(getattr(model, name) == values[name])
        for name in search_filters:
            if name in values:
                stmt = stmt.where(getattr(model, name).ilike(f"%{values[name]}%"))
        return stmt

    async def _get_active_or_404(db: AsyncSession, item_id: int) -> ModelT:
        item = await db.get(model, item_id)
        if not item or not item.is_active:
            raise NotFoundException(f"{model.__name__} not found")
        return item

    @router.get("", response_model=PaginatedResponse[read_schema])
    async def list_items(
        params: Annotated[ListParams, Query()],
        db: Annotated[AsyncSession, Depends(get_db)],
        _current_user: Annotated[User, Depends(get_current_user)],
    ):
        offset = (params.page - 1) * params.page_size

        base_condition = model.is_active.is_(True)
        count_stmt = _apply_filters(select(func.count()).select_from(model).where(base_condition), params)
        total = await db.scalar(count_stmt)

        list_stmt = _apply_filters(select(model).where(base_condition), params)
        result = await db.execute(list_stmt.order_by(model.id).offset(offset).limit(params.page_size))
        items = result.scalars().all()

        return PaginatedResponse[read_schema](
            items=items,
            total=total or 0,
            page=params.page,
            page_size=params.page_size,
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
