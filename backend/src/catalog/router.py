from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.catalog import service
from src.catalog.dependencies import valid_item
from src.catalog.models import Brand, Category, Item, Model
from src.catalog.schemas import (
    BrandCreate,
    BrandRead,
    BrandUpdate,
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    ItemCreate,
    ItemRead,
    ItemUpdate,
    ModelCreate,
    ModelRead,
    ModelUpdate,
)
from src.crud import build_crud_router
from src.database import get_db
from src.pagination import PaginatedResponse, PaginationParams

category_router = build_crud_router(
    model=Category,
    create_schema=CategoryCreate,
    read_schema=CategoryRead,
    update_schema=CategoryUpdate,
    prefix="/categories",
    tags=["catalog"],
)

brand_router = build_crud_router(
    model=Brand,
    create_schema=BrandCreate,
    read_schema=BrandRead,
    update_schema=BrandUpdate,
    prefix="/brands",
    tags=["catalog"],
)

model_router = build_crud_router(
    model=Model,
    create_schema=ModelCreate,
    read_schema=ModelRead,
    update_schema=ModelUpdate,
    prefix="/models",
    tags=["catalog"],
    exact_filters=["brand_id"],
)

item_router = APIRouter(prefix="/items", tags=["catalog"])


@item_router.get("", response_model=PaginatedResponse[ItemRead])
async def list_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category_id: int | None = None,
    model_id: int | None = None,
    sku: str | None = None,
    variant: str | None = None,
):
    # A Query()-annotated PaginationParams model doesn't flatten into page/page_size
    # query params when the endpoint also takes other plain scalar query params
    # (confirmed empirically — FastAPI instead requires a single JSON `pagination`
    # param) — so pagination is taken as plain scalars here and reassembled below,
    # unlike build_crud_router's generic list endpoint, which never mixes a
    # Query-model with hand-picked extra filters on one route.
    pagination = PaginationParams(page=page, page_size=page_size)
    return await service.list_items(db, pagination, category_id, model_id, sku, variant)


@item_router.post("", response_model=ItemRead, status_code=201)
async def create_item(
    payload: ItemCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.create_item(db, payload)


@item_router.get("/{item_id}", response_model=ItemRead)
async def get_item(
    item: Annotated[Item, Depends(valid_item)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return item


@item_router.put("/{item_id}", response_model=ItemRead)
async def update_item(
    payload: ItemUpdate,
    item: Annotated[Item, Depends(valid_item)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.update_item(db, item, payload)


@item_router.delete("/{item_id}", status_code=204)
async def soft_delete_item(
    item: Annotated[Item, Depends(valid_item)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    await service.soft_delete_item(db, item)


router = APIRouter()
router.include_router(category_router)
router.include_router(brand_router)
router.include_router(model_router)
router.include_router(item_router)
