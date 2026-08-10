# Phase 1 Backend — Implementation Plan (executed)

## Context

`PLAN.md` defines Phase 1 ("Catalog & China purchasing") and `.claude/specs/phase-1-backend.md` contains the full design for it — folder structure, models, schemas, the new `parties/` domain, `PurchaseOrder`/`PurchaseOrderLine`, and the first real writes to the previously schema-only `ledger_entry` table. Two consequential decisions were confirmed with the user before that spec was written: ledger writes start in Phase 1 rather than being deferred to Phase 6, and a party-linked `LedgerEntry`'s `credit` represents a payable (money we owe out) while `debit` represents a receivable (money owed to us) — a polarity every later phase must keep.

Before implementation, the spec's pseudocode was independently validated against the actual installed stack (`fastapi 0.141.1`, `pydantic 2.13.4`, `SQLAlchemy 2.0.51`, `asyncpg 0.31.0`) and found to have **two real runtime bugs**, both fixed during implementation (details below). This plan executed the corrected version end to end and reached the spec's "done when": create a PO against a real vendor, in RMB, and see the PKR cost per line and total. **Status: complete and verified** — see §8 for the full verification walkthrough.

## Two runtime bugs found in the spec's pseudocode, fixed during implementation

1. **A JSON body field cannot be resolved through a chained `Depends()` the way a path param can.** The spec's `POST /purchasing/purchase-orders` sketch had the route depend on `Depends(valid_china_vendor)`, wrapping `valid_party(party_id: int, ...)` — but `party_id` there is `PurchaseOrderCreate.party_id`, a body field, not a path segment. Verified via the generated OpenAPI schema that FastAPI resolves a bare scalar sub-dependency parameter as a **query** param, not from the body. Fixed by dropping the `Depends`-chain for this specific check: `parties/service.py` gained two plain (non-FastAPI) functions, `get_active_party(db, party_id) -> Party` and `ensure_role(party, role)`, and `purchasing/service.create_purchase_order` calls them directly with `payload.party_id`. `parties/dependencies.py`'s `valid_party`/`valid_china_vendor` remain as thin delegates to those same service functions, used by `parties/router.py`'s own path-based routes; `valid_china_vendor` currently has no caller in Phase 1 but is kept for Phase 5's local-vendor reuse of this same purchase flow.
2. **`async with db.begin():` crashes with `InvalidRequestError: a transaction is already begun on this Session`.** Every authenticated route already has an auto-begun transaction on its request-scoped session before a service function runs — `auth/dependencies.get_current_user` does `await db.get(User, ...)` on that same session first. Fixed by following `src/crud.py`'s existing convention everywhere in Phase 1 instead: reads, then `db.add(...)`/`await db.flush()` where a PK is needed, then one `await db.commit()` at the end wrapped in `try/except IntegrityError → rollback → ConflictException`. Verified atomic — nothing persists before that single commit.

## Smaller corrections made relative to the spec

- `Party.roles` uses `sqlalchemy.dialects.postgresql.ARRAY(String)`, not generic `sqlalchemy.ARRAY` — the generic type's `.contains()`/`.overlap()` raise `NotImplementedError`/`AttributeError`, which Phase 2/4 role-membership queries will need.
- `PurchaseOrder.lines` relationship (missing from the spec) declared as `relationship(back_populates="purchase_order", cascade="all, delete-orphan", order_by="PurchaseOrderLine.id", lazy="raise")`, with the matching `purchase_order` back-reference on `PurchaseOrderLine`. `lazy="raise"` per CLAUDE.md §2.5 ("never rely on lazy-load in async"). `create_purchase_order` builds `PurchaseOrder(..., lines=[...])` through the relationship (not standalone inserts with an explicit `purchase_order_id`), which keeps `po.lines` loaded through `flush()`/`commit()` (`expire_on_commit=False`) with no extra `db.refresh()`.
- `purchasing/dependencies.valid_purchase_order` uses `select(PurchaseOrder).options(selectinload(...)).where(...)`, not `db.get()` — `Session.get()` silently ignores loader options when serving from the identity map. `list_purchase_orders` uses the same `selectinload`.
- Added `src/purchasing/utils.py::money()` (`Decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`), used identically by `PurchaseOrderRead`/`PurchaseOrderLineRead`'s computed fields and by the service's `total_pkr` calculation — verified the response's `total_pkr` and the ledger's `credit` land on the exact same value (see §8, test 9).
- `create_purchase_order` validates `item_id`s against `catalog.Item` before writing anything (`InvalidPurchaseOrderItem`, 422) — the spec didn't, which would have let a bad id reach an uncaught `IntegrityError` → 500 at commit.
- `ledger/models.py` was edited (the spec listed it as "unchanged," which was wrong) — added `ForeignKey("party.id")` + `index=True` on `party_id`, the FK deferred from Phase 0's migration since `Party` didn't exist yet.
- `purchasing/router.py` restructured to export one module-level `router` (the exchange-rate CRUD router plus the new PO router combined via `router.include_router(...)`) so `main.py`'s existing `include_router(purchasing_router, prefix="/purchasing")` line needed no change.
- `PartyRole` enum lives in `parties/constants.py` (one definition); `parties/schemas.py` imports it rather than redefining it.
- Dropped `PurchaseOrderUpdate` from the spec — no `PUT` route ships in Phase 1, so it would have been a dead schema.
- **Deviation from Phase 0's own precedent, applied consistently**: skipped empty placeholder `catalog/constants.py`/`catalog/exceptions.py` — Category/Model/Item are pure generic-CRUD with no hand-written logic needing domain-specific exceptions, same reasoning Phase 0 used to skip empty stubs for `purchasing`/`payments`/`ledger`.
- The spec's own §11 test 4 had the ledger polarity backwards relative to its own §0/§5.1 decision (said `opening_balance: 50000` should produce `credit=50000`; the decision and the implemented code both say `debit=50000`). Verified the implemented code follows the decision correctly (§8, test 5).

## Build order (as executed)

### 1. `src/catalog/` (spec §3)

`src/catalog/{__init__,models,schemas,router}.py` built as specified — `Category`, `Model` (carries `priority`, unused until Phase 8), `Item` (`category_id`/`model_id` FKs + unique `sku`), three generic CRUD routers combined under one `router` via `router.include_router(...)`, mounted in `main.py` as `/catalog`. No `constants.py`/`exceptions.py` (see deviation above).

### 2. `src/parties/` (spec §5, corrected per bug #1)

`src/parties/{__init__,constants,models,exceptions,schemas,service,dependencies,router}.py`. `Party` model with `postgresql.ARRAY(String)` roles and `Numeric(12,2)` `opening_balance`. `service.py` holds `get_active_party`/`ensure_role` (the plain functions bug #1 required), `create_party` (posts a `LedgerEntry` only when `opening_balance != 0`, flushing first to get `party.id`), and thin `list_parties`/`update_party`/`soft_delete_party`. Mounted in `main.py` as `/parties`.

### 3. `src/ledger/` additions (spec §4, corrected per the `models.py` note above)

`ledger/schemas.py` (`LedgerEntryRead`, still no router — nothing in Phase 1 reads the ledger back through an endpoint). `ledger/service.py::post_entry` — add-only, no commit, no flush; callers commit once at the end of their own transaction. `ledger/models.py` edited to add the `party_id` FK.

### 4. `src/purchasing/` growth (spec §6, corrected per bug #2 and the smaller corrections above)

`utils.py` (`money()`), `models.py` (`PurchaseOrder`/`PurchaseOrderLine` with the relationship pair), `constants.py` (`PurchaseOrderStatus = Literal["draft"]`), `exceptions.py` (`PurchaseOrderNotFound`, `ExchangeRateMissingForDate`, `InvalidPurchaseOrderItem`), `schemas.py` (PO schemas appended after the existing `ExchangeRate*` ones, using `money()` in computed fields, no `PurchaseOrderUpdate`), `dependencies.py` (`valid_purchase_order`), `service.py` (`create_purchase_order`, `list_purchase_orders`), `router.py` restructured into one `router`.

### 5. Migration (spec §7)

`migrations/env.py` updated with `Category`/`Item`/`Model`/`Party`/`PurchaseOrder`/`PurchaseOrderLine` imports. `alembic revision --autogenerate -m "add catalog, party, purchasing"` produced a clean migration on the first try — correct FK-dependency table order (`category`, `model`, `party` → `item` → `purchase_order` → `purchase_order_line`), correctly detected and included the deferred `ledger_entry_party_id_fkey` + index, correct `postgresql.ARRAY(sa.String())` and `Numeric` precisions throughout. Renamed to `migrations/versions/2026-08-07_add_catalog_party_purchasing.py`; `alembic upgrade head` applied cleanly on top of Phase 0's schema (confirmed via `\d` on `party`/`ledger_entry`/`purchase_order_line`).

### 6. Seed script (spec §9)

`scripts/seed.py` extended with `seed_china_vendor(session, name)` and an optional `--vendor-name` CLI arg (guarded — omitting it leaves seeding behavior unchanged from Phase 0). No catalog rows seeded, per the spec's own reasoning: PLAN.md's "Cover, Protector, Charger" / "iPhone 13, Galaxy A54" are illustrative examples, not real starter data.

### 7. Verification — all passed, against the already-running dev server (`--reload`, confirmed it picked up every change live)

1. `alembic upgrade head` — clean on top of Phase 0's schema.
2. `python -m scripts.seed --username phase1_admin --password ... --rate 39.50 --vendor-name "Shenzhen Accessories Co."` — created user + China vendor party without error; safely idempotent (existing exchange rate/payment methods reported "already exists, skipping").
3. `GET /openapi.json` — all 17 routes present with correct tags/response models; confirmed `POST /purchasing/purchase-orders` has **no** `party_id` query parameter (proof bug #1's fix landed — `party_id` only appears in the request body schema).
4. `POST /catalog/categories`/`/models`/`/items` — all succeeded; an `Item` with a nonexistent `category_id` returned `409` (not `500`) — the pre-existing, documented generic-factory limitation (broad `IntegrityError` → `ConflictException`), not a Phase 1 regression.
5. `POST /parties` with `roles: ["china_vendor"]`, `opening_balance: 50000` → `201`; the resulting `LedgerEntry` has **`debit=50000.00, credit=0.00`**, `reference_type="party_opening_balance"` — correct polarity per §0/§5.1 (positive `opening_balance` = party owes us = debit). `opening_balance: 0` → confirmed zero new ledger rows for that party.
6. `POST /purchasing/purchase-orders` against a `customer`-role (non-`china_vendor`) party → `422` (`"Party N does not hold the 'china_vendor' role"`). Against a date with no seeded `ExchangeRate` (`2020-01-01`) → `422`. With an unknown `item_id` → `422` (`"Unknown or inactive item id(s): [999999]"`) — none of these hit a `500`.
7. `POST /purchasing/purchase-orders` with a real vendor, `order_date=2026-08-07` (rate `39.5000`), two lines (`qty=10, rate_rmb=12.35` and `qty=3, rate_rmb=8.10`) → `201`. Verified by hand: `rate_pkr = money(12.35 × 39.5) = 487.83`, `amount_pkr = 4878.30`; second line `rate_pkr = 319.95`, `amount_pkr = 959.85`; `total_pkr = 5838.15`. The response's `total_pkr` **exactly matched** the new `LedgerEntry` row's `credit` (`5838.15`), confirming the shared `money()` helper eliminated the rounding-drift risk identified during planning.
8. `GET /purchasing/purchase-orders/{id}` and `GET /purchasing/purchase-orders` (list) both returned lines fully populated, no lazy-load error under the async session (`lazy="raise"` never triggered, meaning the eager-load path was hit correctly both times).
9. `POST /purchasing/purchase-orders` and `GET /purchasing/purchase-orders` and `GET /parties` all returned `401` when called without a bearer token.
10. `ruff check` on every new/edited file surfaced only style-level findings consistent with the pre-existing baseline (`src/crud.py` itself has unfixed `UP006` findings) — the fixable ones (`Decimal("0")` → `Decimal(0)`, import sorting) were auto-fixed with `ruff check --fix`; the two `DTZ011` (`date.today()`) findings were left as-is, matching the existing pattern already used in Phase 0's `seed.py`.

## Known state left behind

Manual verification created a few rows directly against the dev database beyond the seed script's output — two more `Party` rows besides the seeded vendor ("Test Vendor A" with a 50000 opening balance, "Test Vendor B (zero)"), a "Not A Vendor" `customer`-role party, one `Category`/`Model`/`Item` (`Cover`/`iPhone 13`/`COVER-IP13-BLK`), and one real `PurchaseOrder` with two lines and its `LedgerEntry`. These are genuine, correctly-behaving rows (not artifacts of a bug), left in place rather than deleted unprompted since deleting rows out of a database wasn't asked for. If a clean slate is wanted before building the frontend against this API, drop and recreate the dev database (`docker compose down -v && docker compose up -d && alembic upgrade head && python -m scripts.seed ...`) rather than hand-deleting rows with FK dependencies between them.
