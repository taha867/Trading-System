from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: Annotated[str, Field(max_length=120)]


class CategoryRead(CategoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool


class CategoryUpdate(BaseModel):
    name: Annotated[str, Field(max_length=120)] | None = None


class BrandCreate(BaseModel):
    name: Annotated[str, Field(max_length=120)]


class BrandRead(BrandCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool


class BrandUpdate(BaseModel):
    name: Annotated[str, Field(max_length=120)] | None = None


class ModelCreate(BaseModel):
    brand_id: int
    name: Annotated[str, Field(max_length=120)]


class ModelRead(ModelCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    priority: int
    is_active: bool


class ModelUpdate(BaseModel):
    brand_id: int | None = None
    name: Annotated[str, Field(max_length=120)] | None = None
    priority: int | None = None


class ItemCreate(BaseModel):
    category_id: int
    model_id: int
    sku: Annotated[str, Field(max_length=64)]
    variant: Annotated[str | None, Field(max_length=64)] = None


class ItemRead(ItemCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool


class ItemUpdate(BaseModel):
    category_id: int | None = None
    model_id: int | None = None
    variant: Annotated[str | None, Field(max_length=64)] = None
