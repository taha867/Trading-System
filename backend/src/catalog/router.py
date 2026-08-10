from fastapi import APIRouter

from src.catalog.models import Category, Item, Model
from src.catalog.schemas import (
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

router = APIRouter()
router.include_router(
    build_crud_router(
        model=Category,
        create_schema=CategoryCreate,
        read_schema=CategoryRead,
        update_schema=CategoryUpdate,
        prefix="/categories",
        tags=["catalog"],
    )
)
router.include_router(
    build_crud_router(
        model=Model,
        create_schema=ModelCreate,
        read_schema=ModelRead,
        update_schema=ModelUpdate,
        prefix="/models",
        tags=["catalog"],
    )
)
router.include_router(
    build_crud_router(
        model=Item,
        create_schema=ItemCreate,
        read_schema=ItemRead,
        update_schema=ItemUpdate,
        prefix="/items",
        tags=["catalog"],
    )
)
