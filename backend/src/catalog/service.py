from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.catalog.exceptions import InvalidCatalogName, ItemNotFound
from src.catalog.models import Brand, Category, Item, ItemCompatibleModel, Model
from src.catalog.naming import BRAND_ALIASES, build_sku, check_model_name, is_standard_sku, match_key
from src.catalog.schemas import ItemCreate, ItemRead, ItemUpdate, ModelCreate, ModelUpdate
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


async def _standard_model_name(db: AsyncSession, brand_id: int, raw_name: str, exclude_model_id: int | None) -> str:
    """The model's standard name, refusing text that isn't a clear model name or that is another spelling of a
    phone the brand already has (one Model per phone: '13C' and 'REDMI13C' are the same phone)."""
    brand = await db.get(Brand, brand_id)
    if not brand or not brand.is_active:
        raise NotFoundException("Brand not found or inactive")
    name, problem = check_model_name(brand.name, raw_name)
    if problem:
        raise InvalidCatalogName(problem)
    key = match_key(brand.name, name)
    rows = await db.execute(select(Model.id, Model.name).where(Model.brand_id == brand_id, Model.is_active.is_(True)))
    for model_id, existing_name in rows.all():
        if model_id != exclude_model_id and match_key(brand.name, existing_name) == key:
            raise ConflictException(f"{brand.name} '{existing_name}' already exists - use it (a phone has only one model)")
    return name


async def prepare_model_create(db: AsyncSession, payload: ModelCreate) -> ModelCreate:
    return payload.model_copy(update={"name": await _standard_model_name(db, payload.brand_id, payload.name, None)})


async def prepare_model_update(db: AsyncSession, model: Model, payload: ModelUpdate) -> ModelUpdate:
    if payload.name is None and payload.brand_id is None:
        return payload
    name = await _standard_model_name(db, payload.brand_id or model.brand_id, payload.name if payload.name is not None else model.name, model.id)
    return payload.model_copy(update={"name": name})


async def _ensure_no_duplicate_item(
    db: AsyncSession, category_id: int, model_id: int, variant: str | None, exclude_item_id: int | None = None
) -> None:
    """One Item per (category, primary model, colour): a second one is refused and the existing code is named."""
    stmt = select(Item.sku).where(
        Item.is_active.is_(True),
        Item.category_id == category_id,
        Item.model_id == model_id,
        func.upper(func.coalesce(Item.variant, "")) == (variant or "").strip().upper(),
    )
    if exclude_item_id is not None:
        stmt = stmt.where(Item.id != exclude_item_id)
    existing = (await db.scalars(stmt)).first()
    if existing:
        raise ConflictException(f"This product already exists as {existing} - add the phone to its 'also fits' list instead")


async def suggest_sku(db: AsyncSession, category: Category, model: Model, variant: str | None) -> str:
    """CATEGORY-BRAND-MODEL[-COLOUR] (see CLAUDE.md 'Catalog naming'); a clash gets -2, -3 ..."""
    brand = await db.get(Brand, model.brand_id)
    brand_name = BRAND_ALIASES.get(brand.name, (brand.name, None))[0]
    try:
        base = build_sku(category.name, brand_name, model.name, variant)
    except KeyError as exc:
        raise InvalidCatalogName(f"No item-code prefix is defined for {exc.args[0]} - enter the code yourself") from exc
    sku, n = base, 2
    while await db.scalar(select(Item.id).where(Item.sku == sku)):
        sku = f"{base}-{n}"
        n += 1
    return sku


_ITEM_LOAD_OPTIONS = (
    selectinload(Item.compatible_models),
    joinedload(Item.model),
    joinedload(Item.category),
)


async def get_item(db: AsyncSession, item_id: int) -> Item:
    # select().options(selectinload(...)), not db.get() — Session.get() silently ignores
    # loader options when it serves the object from the identity map.
    result = await db.execute(select(Item).options(*_ITEM_LOAD_OPTIONS).where(Item.id == item_id))
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
    search: str | None = None,
) -> PaginatedResponse[ItemRead]:
    offset = (pagination.page - 1) * pagination.page_size

    # `search` joins Model — a picker searching by what a human actually types
    # ("iPhone 15") needs to match the model name, not just the internal sku code.
    needs_model_join = search is not None
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
    if search is not None:
        conditions.append(or_(Item.sku.ilike(f"%{search}%"), Model.name.ilike(f"%{search}%")))

    count_stmt = select(func.count()).select_from(Item).where(*conditions)
    list_stmt = select(Item).options(*_ITEM_LOAD_OPTIONS).where(*conditions)
    if needs_model_join:
        count_stmt = count_stmt.join(Model, Model.id == Item.model_id)
        list_stmt = list_stmt.join(Model, Model.id == Item.model_id)

    total = await db.scalar(count_stmt)

    result = await db.execute(list_stmt.order_by(Item.id).offset(offset).limit(pagination.page_size))
    items = result.unique().scalars().all()

    return PaginatedResponse[ItemRead](
        items=items, total=total or 0, page=pagination.page, page_size=pagination.page_size
    )


async def create_item(db: AsyncSession, payload: ItemCreate) -> Item:
    category = await _get_active_category(db, payload.category_id)
    model = await _get_active_model(db, payload.model_id)
    await _ensure_no_duplicate_item(db, payload.category_id, payload.model_id, payload.variant)
    # an item never lists its own phone as "also fits"
    compatible_models = [m for m in await _get_compatible_models(db, payload.compatible_model_ids) if m.id != payload.model_id]

    sku = (payload.sku or "").strip()
    if not sku:
        sku = await suggest_sku(db, category, model, payload.variant)
    elif not is_standard_sku(sku):
        raise InvalidCatalogName("Item codes look like OG-VIVO-Y15 (CATEGORY-BRAND-MODEL) - leave it empty and it is created for you")

    item = Item(
        category_id=payload.category_id,
        model_id=payload.model_id,
        sku=sku,
        variant=payload.variant,
        compatible_models=compatible_models,
    )
    db.add(item)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Item already exists") from exc

    await db.refresh(item, attribute_names=["compatible_models", "model", "category"])
    return item


async def update_item(db: AsyncSession, item: Item, payload: ItemUpdate) -> Item:
    values = payload.model_dump(exclude_unset=True, exclude={"compatible_model_ids"})

    if "category_id" in values:
        await _get_active_category(db, values["category_id"])
    if "model_id" in values:
        await _get_active_model(db, values["model_id"])
    if values.keys() & {"category_id", "model_id", "variant"}:
        await _ensure_no_duplicate_item(
            db,
            values.get("category_id", item.category_id),
            values.get("model_id", item.model_id),
            values["variant"] if "variant" in values else item.variant,
            exclude_item_id=item.id,
        )
    for field, value in values.items():
        setattr(item, field, value)

    if "compatible_model_ids" in payload.model_fields_set:
        # `item` arrives with compatible_models already eagerly loaded (valid_item's
        # selectinload) — required so SQLAlchemy can diff against the loaded collection
        # instead of needing a lazy load (which lazy="raise" forbids) to compute it.
        item.compatible_models = [
            m for m in await _get_compatible_models(db, payload.compatible_model_ids or []) if m.id != item.model_id
        ]

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Item already exists") from exc

    await db.refresh(item, attribute_names=["compatible_models", "model", "category"])
    return item


async def soft_delete_item(db: AsyncSession, item: Item) -> None:
    item.is_active = False
    await db.commit()
