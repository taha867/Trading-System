import asyncio

from sqlalchemy import select

from src.catalog.models import Brand, Category, Item, Model
from src.database import SessionLocal

CATEGORY_NAME = "Protector"

BRANDS = [
    "Apple", "Samsung", "Oppo", "OnePlus", "Vivo", "Google",
    "Redmi", "Xiaomi", "Infinix", "Tecno", "Huawei",
]

# (sku, brand, model, variant, [(compatible_brand, compatible_model), ...])
# Transcribed from the OG Glass Stock ledger (pages 32-35). A "/" in the ledger meant
# one glass fits both models — that's the compatible-models list here.
ITEMS = [
    # -- page 32 --
    ("PROT-OPPO-F11PRO", "Oppo", "F11 Pro", None, []),
    ("PROT-OPPO-A58", "Oppo", "A58", None, []),
    ("PROT-INFINIX-HOT9PLAY", "Infinix", "Hot9 Play", None, []),
    ("PROT-HUAWEI-Y9PRIME2019", "Huawei", "Y9 Prime 2019", None, []),
    ("PROT-HUAWEI-MATE10LITE", "Huawei", "Mate 10 Lite", None, []),
    ("PROT-APPLE-IPX", "Apple", "iPhone X", None, []),
    ("PROT-APPLE-IPXR-IP11", "Apple", "iPhone XR", None, [("Apple", "iPhone 11")]),
    ("PROT-APPLE-IPXS-IP11PRO", "Apple", "iPhone XS", None, [("Apple", "iPhone 11 Pro")]),
    ("PROT-APPLE-IPXSMAX-IP11PROMAX", "Apple", "iPhone XS Max", None, [("Apple", "iPhone 11 Pro Max")]),
    ("PROT-APPLE-IP12-IP12PRO", "Apple", "iPhone 12", None, [("Apple", "iPhone 12 Pro")]),
    ("PROT-APPLE-IP12PROMAX", "Apple", "iPhone 12 Pro Max", None, []),
    ("PROT-APPLE-IP13-IP13PRO", "Apple", "iPhone 13", None, [("Apple", "iPhone 13 Pro")]),
    ("PROT-APPLE-IP13PROMAX", "Apple", "iPhone 13 Pro Max", None, []),
    ("PROT-APPLE-IP14-IP14PRO", "Apple", "iPhone 14", None, [("Apple", "iPhone 14 Pro")]),
    ("PROT-APPLE-IP14PROMAX", "Apple", "iPhone 14 Pro Max", None, []),
    ("PROT-APPLE-IP15PRO", "Apple", "iPhone 15 Pro", None, []),
    ("PROT-APPLE-IP15PROMAX", "Apple", "iPhone 15 Pro Max", None, []),
    ("PROT-APPLE-IP16-IP15", "Apple", "iPhone 16", None, [("Apple", "iPhone 15")]),
    ("PROT-APPLE-IP16PRO-IP17", "Apple", "iPhone 16 Pro", None, [("Apple", "iPhone 17")]),
    ("PROT-APPLE-IP16PROMAX", "Apple", "iPhone 16 Pro Max", None, []),
    ("PROT-APPLE-IP15PLUS", "Apple", "iPhone 15+", None, []),
    ("PROT-APPLE-IP17PRO", "Apple", "iPhone 17 Pro", None, []),
    ("PROT-APPLE-IP17PROMAX", "Apple", "iPhone 17 Pro Max", None, []),
    ("PROT-APPLE-IP17AIR", "Apple", "iPhone 17 Air", None, []),
    ("PROT-APPLE-IP12MINI", "Apple", "iPhone 12 mini", None, []),
    ("PROT-APPLE-IP13MINI", "Apple", "iPhone 13 mini", None, []),

    # -- page 33 --
    ("PROT-SAMSUNG-A20", "Samsung", "Galaxy A20", None, []),
    ("PROT-SAMSUNG-S21FE", "Samsung", "Galaxy S21 FE", None, []),
    ("PROT-OPPO-A54", "Oppo", "A54", None, []),
    ("PROT-SAMSUNG-A35-A55", "Samsung", "Galaxy A35", None, [("Samsung", "Galaxy A55")]),
    ("PROT-SAMSUNG-A34", "Samsung", "Galaxy A34", None, []),
    ("PROT-SAMSUNG-A31-A32", "Samsung", "Galaxy A31", None, [("Samsung", "Galaxy A32")]),
    ("PROT-SAMSUNG-A10", "Samsung", "Galaxy A10", None, []),
    ("PROT-SAMSUNG-A36-A56", "Samsung", "Galaxy A36", None, [("Samsung", "Galaxy A56")]),
    ("PROT-OPPO-F19", "Oppo", "F19", None, []),
    ("PROT-VIVO-V50LITE", "Vivo", "V50 Lite", None, []),
    ("PROT-ONEPLUS-13T", "OnePlus", "13T", None, []),
    ("PROT-REDMI-15", "Redmi", "15", None, []),
    ("PROT-REDMI-10C", "Redmi", "10C", None, []),
    ("PROT-INFINIX-HOT6PRO", "Infinix", "Hot 6 Pro", None, []),
    ("PROT-GOOGLE-PIXEL6", "Google", "Pixel 6", None, []),
    ("PROT-GOOGLE-PIXEL6A", "Google", "Pixel 6A", None, []),
    ("PROT-GOOGLE-PIXEL7", "Google", "Pixel 7", None, []),
    ("PROT-GOOGLE-PIXEL7A", "Google", "Pixel 7A", None, []),
    ("PROT-GOOGLE-PIXEL8", "Google", "Pixel 8", None, []),
    ("PROT-GOOGLE-PIXEL8A", "Google", "Pixel 8A", None, []),
    ("PROT-GOOGLE-PIXEL8PRO", "Google", "Pixel 8 Pro", None, []),
    ("PROT-GOOGLE-PIXEL9-PIXEL9PRO", "Google", "Pixel 9", None, [("Google", "Pixel 9 Pro")]),
    ("PROT-GOOGLE-PIXEL10PRO", "Google", "Pixel 10 Pro", None, []),
    ("PROT-GOOGLE-PIXEL9PROXL-PIXEL10PROXL", "Google", "Pixel 9 Pro XL", None, [("Google", "Pixel 10 Pro XL")]),
    ("PROT-REDMI-NOTE12", "Redmi", "Note 12", None, []),
    ("PROT-SAMSUNG-J6PLUS", "Samsung", "Galaxy J6+", None, []),
    ("PROT-OPPO-A1K", "Oppo", "A1K", None, []),
    ("PROT-VIVO-Y81", "Vivo", "Y81", None, []),

    # -- page 34 --
    ("PROT-SAMSUNG-S21", "Samsung", "Galaxy S21", None, []),
    ("PROT-SAMSUNG-S21PLUS", "Samsung", "Galaxy S21+", None, []),
    ("PROT-SAMSUNG-S22PLUS-S23PLUS", "Samsung", "Galaxy S22+", None, [("Samsung", "Galaxy S23+")]),
    ("PROT-SAMSUNG-S22-S23", "Samsung", "Galaxy S22", None, [("Samsung", "Galaxy S23")]),
    ("PROT-SAMSUNG-S24", "Samsung", "Galaxy S24", None, []),
    ("PROT-SAMSUNG-S24PLUS", "Samsung", "Galaxy S24+", None, []),
    ("PROT-SAMSUNG-S24ULTRA", "Samsung", "Galaxy S24 Ultra", None, []),
    ("PROT-SAMSUNG-S25-FP", "Samsung", "Galaxy S25", "Fingerprint", []),
    ("PROT-SAMSUNG-S25PLUS", "Samsung", "Galaxy S25+", None, []),
    ("PROT-SAMSUNG-S25ULTRA", "Samsung", "Galaxy S25 Ultra", None, []),
    ("PROT-SAMSUNG-S26", "Samsung", "Galaxy S26", None, []),
    ("PROT-SAMSUNG-S26PLUS", "Samsung", "Galaxy S26+", None, []),
    ("PROT-SAMSUNG-S26ULTRA", "Samsung", "Galaxy S26 Ultra", None, []),
    ("PROT-VIVO-Y15-Y17", "Vivo", "Y15", None, [("Vivo", "Y17")]),
    ("PROT-APPLE-IP6PLUS-IP7PLUS-WHITE", "Apple", "iPhone 6+", "White", [("Apple", "iPhone 7+")]),
    ("PROT-TECNO-SPARK30PRO", "Tecno", "Spark 30 Pro", None, []),
    ("PROT-VIVO-Y20", "Vivo", "Y20", None, []),
    ("PROT-SAMSUNG-A24", "Samsung", "Galaxy A24", None, []),
    ("PROT-INFINIX-NOTE60-NOTE60PRO", "Infinix", "Note 60", None, [("Infinix", "Note 60 Pro")]),
    ("PROT-REDMI-12", "Redmi", "12", None, []),
    ("PROT-SAMSUNG-A54", "Samsung", "Galaxy A54", None, []),
    ("PROT-OPPO-RENO13", "Oppo", "Reno 13", None, []),
    # "GO 1" (page 34 row 23) excluded — brand unknown, add manually once confirmed.
    ("PROT-REDMI-13C", "Redmi", "13C", None, []),
    ("PROT-ONEPLUS-8T", "OnePlus", "8T", None, []),
    ("PROT-APPLE-IP6PLUS-IP7PLUS-BLACK", "Apple", "iPhone 6+", "Black", [("Apple", "iPhone 7+")]),
    ("PROT-APPLE-IP6-IP7-WHITE", "Apple", "iPhone 6", "White", [("Apple", "iPhone 7")]),
    ("PROT-APPLE-IP6-IP7-BLACK", "Apple", "iPhone 6", "Black", [("Apple", "iPhone 7")]),

    # -- page 35 --
    ("PROT-SAMSUNG-A70", "Samsung", "Galaxy A70", None, []),  # brand assumed — please verify
    ("PROT-INFINIX-NOTE7-POVA2", "Infinix", "Note 7", None, [("Tecno", "Pova 2")]),
    ("PROT-SAMSUNG-A71", "Samsung", "Galaxy A71", None, []),
    ("PROT-OPPO-A35", "Oppo", "A35", None, []),
    ("PROT-SAMSUNG-J6", "Samsung", "Galaxy J6", None, []),
    ("PROT-XIAOMI-MINOTE10", "Xiaomi", "Mi Note 10", None, []),
    ("PROT-INFINIX-HOT11S", "Infinix", "Hot 11S", None, []),
    ("PROT-SAMSUNG-A15", "Samsung", "Galaxy A15", None, []),
    ("PROT-SAMSUNG-A51", "Samsung", "Galaxy A51", None, []),
    ("PROT-OPPO-A80-HOT9S", "Oppo", "A80", None, [("Infinix", "Hot 9S")]),
    ("PROT-SAMSUNG-A05S", "Samsung", "Galaxy A05s", None, []),  # brand assumed — please verify
    ("PROT-OPPO-F11", "Oppo", "F11", None, []),
    ("PROT-INFINIX-HOT9", "Infinix", "Hot 9", None, []),
    # Ledger's second "Y20" row — same as PROT-VIVO-Y20 above, skipped as a duplicate.
    # "i+10i / Y200/Y100" (page 35 row 15) excluded — too unclear to transcribe confidently.
    ("PROT-SAMSUNG-A14", "Samsung", "Galaxy A14", None, []),
    ("PROT-INFINIX-HOT10", "Infinix", "Hot 10", None, []),
    ("PROT-INFINIX-NOTE50", "Infinix", "Note 50", None, []),  # reading uncertain — please verify
    ("PROT-REDMI-15C", "Redmi", "15C", None, []),
    ("PROT-OPPO-Y31D-A61", "Oppo", "Y31D", None, [("Oppo", "A61")]),
    # Oppo A5s / A15 (page 35 row 20) excluded — unclear if grouped with Y31D/A61 or
    # separate items; add manually once confirmed.
    ("PROT-VIVO-V70-V70LITE", "Vivo", "V70", None, [("Vivo", "V70 Lite")]),
    ("PROT-REDMI-C51", "Redmi", "C51", None, []),
    ("PROT-TECNO-CAMON50", "Tecno", "Camon 50", None, []),
    ("PROT-OPPO-RENO15-RENO15C-A65PRO", "Oppo", "Reno 15", None, [("Oppo", "Reno 15C"), ("Oppo", "A65 Pro")]),
]


async def get_or_create_category(session, name: str) -> Category:
    existing = await session.scalar(select(Category).where(Category.name == name))
    if existing:
        return existing
    category = Category(name=name)
    session.add(category)
    await session.flush()
    print(f"Created Category '{name}'.")
    return category


async def get_or_create_brand(session, name: str) -> Brand:
    existing = await session.scalar(select(Brand).where(Brand.name == name))
    if existing:
        return existing
    brand = Brand(name=name)
    session.add(brand)
    await session.flush()
    print(f"Created Brand '{name}'.")
    return brand


async def get_or_create_model(session, brand: Brand, name: str) -> Model:
    existing = await session.scalar(select(Model).where(Model.brand_id == brand.id, Model.name == name))
    if existing:
        return existing
    model = Model(brand_id=brand.id, name=name)
    session.add(model)
    await session.flush()
    print(f"Created Model '{brand.name} {name}'.")
    return model


async def main() -> None:
    async with SessionLocal() as session:
        category = await get_or_create_category(session, CATEGORY_NAME)
        brands = {name: await get_or_create_brand(session, name) for name in BRANDS}

        # Cache models by (brand, name) — the same model is referenced many times
        # across primary + compatible slots, and shouldn't trigger a repeat lookup/insert.
        models: dict[tuple[str, str], Model] = {}

        async def model_for(brand_name: str, model_name: str) -> Model:
            key = (brand_name, model_name)
            if key not in models:
                models[key] = await get_or_create_model(session, brands[brand_name], model_name)
            return models[key]

        created, skipped = 0, 0
        for sku, brand_name, model_name, variant, compat in ITEMS:
            existing = await session.scalar(select(Item).where(Item.sku == sku))
            if existing:
                print(f"Item '{sku}' already exists, skipping.")
                skipped += 1
                continue

            primary_model = await model_for(brand_name, model_name)
            compatible_models = [await model_for(cb, cm) for cb, cm in compat]

            item = Item(
                category_id=category.id,
                model_id=primary_model.id,
                sku=sku,
                variant=variant,
                compatible_models=compatible_models,
            )
            session.add(item)
            created += 1
            print(f"Created Item '{sku}' ({brand_name} {model_name}).")

        await session.commit()
        print(f"\nDone. {created} items created, {skipped} already existed.")


if __name__ == "__main__":
    asyncio.run(main())
