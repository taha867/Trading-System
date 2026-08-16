from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.catalog.exceptions import ItemNotFound
from src.catalog.models import Category, Item, ItemCompatibleModel, Model
from src.catalog.schemas import ItemCreate, ItemRead, ItemUpdate
from src.exceptions import ConflictException, NotFoundException
from src.pagination import PaginatedResponse, PaginationParams


async def _get_active_category(db: AsyncSession, category_id: int) -> Category:
    category = await db.get(Category, category_id)
    if not category or not category.is_active:
        raise NotFoundException("Category not found or inactive")
    return category


async def _get_active_model(db: AsyncSession, model_id: int) -> Model:
    model = await db.get(Model, model_id)
    if not model or not model.is_active:
        raise NotFoundException("Model not found or inactive")
    return model


async def _get_compatible_models(db: AsyncSession, model_ids: list[int]) -> list[Model]:
    unique_ids = set(model_ids)
    if not unique_ids:
        return []
    result = await db.execute(select(Model).where(Model.id.in_(unique_ids), Model.is_active.is_(True)))
    models = result.scalars().all()
    found_ids = {m.id for m in models}
    if missing := unique_ids - found_ids:
        raise NotFoundException(f"Compatible model id(s) not found or inactive: {sorted(missing)}")
    return list(models)


async def get_item(db: AsyncSession, item_id: int) -> Item:
    # select().options(selectinload(...)), not db.get() — Session.get() silently ignores
    # loader options when it serves the object from the identity map.
    result = await db.execute(
        select(Item).options(selectinload(Item.compatible_models)).where(Item.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item or not item.is_active:
        raise ItemNotFound()
    return item


async def list_items(
    db: AsyncSession,
    pagination: PaginationParams,
    category_id: int | None,
    model_id: int | None,
    sku: str | None,
    variant: str | None,
) -> PaginatedResponse[ItemRead]:
    offset = (pagination.page - 1) * pagination.page_size

    conditions = [Item.is_active.is_(True)]
    if category_id is not None:
        conditions.append(Item.category_id == category_id)
    if model_id is not None:
        # Primary model OR tagged-compatible via the join table — an EXISTS/IN, not a
        # plain column comparison, which is exactly why this can't be a generic exact_filter.
        compatible_item_ids = select(ItemCompatibleModel.item_id).where(ItemCompatibleModel.model_id == model_id)
        conditions.append(or_(Item.model_id == model_id, Item.id.in_(compatible_item_ids)))
    if sku is not None:
        conditions.append(Item.sku.ilike(f"%{sku}%"))
    if variant is not None:
        conditions.append(Item.variant.ilike(f"%{variant}%"))

    total = await db.scalar(select(func.count()).select_from(Item).where(*conditions))

    result = await db.execute(
        select(Item)
        .options(selectinload(Item.compatible_models))
        .where(*conditions)
        .order_by(Item.id)
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = result.scalars().all()

    return PaginatedResponse[ItemRead](
        items=items, total=total or 0, page=pagination.page, page_size=pagination.page_size
    )


async def create_item(db: AsyncSession, payload: ItemCreate) -> Item:
    await _get_active_category(db, payload.category_id)
    await _get_active_model(db, payload.model_id)
    compatible_models = await _get_compatible_models(db, payload.compatible_model_ids)

    item = Item(
        category_id=payload.category_id,
        model_id=payload.model_id,
        sku=payload.sku,
        variant=payload.variant,
        compatible_models=compatible_models,
    )
    db.add(item)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Item already exists") from exc

    await db.refresh(item, attribute_names=["compatible_models"])
    return item


async def update_item(db: AsyncSession, item: Item, payload: ItemUpdate) -> Item:
    values = payload.model_dump(exclude_unset=True, exclude={"compatible_model_ids"})

    if "category_id" in values:
        await _get_active_category(db, values["category_id"])
    if "model_id" in values:
        await _get_active_model(db, values["model_id"])
    for field, value in values.items():
        setattr(item, field, value)

    if "compatible_model_ids" in payload.model_fields_set:
        # `item` arrives with compatible_models already eagerly loaded (valid_item's
        # selectinload) — required so SQLAlchemy can diff against the loaded collection
        # instead of needing a lazy load (which lazy="raise" forbids) to compute it.
        item.compatible_models = await _get_compatible_models(db, payload.compatible_model_ids or [])

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Item already exists") from exc

    await db.refresh(item, attribute_names=["compatible_models"])
    return item


async def soft_delete_item(db: AsyncSession, item: Item) -> None:
    item.is_active = False
    await db.commit()
