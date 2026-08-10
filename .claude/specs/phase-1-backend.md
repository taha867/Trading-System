# Phase 1 Backend — Spec

Source of truth: `PLAN.md` (§ Phase 1 — Catalog & China purchasing, § Architecture decisions, § Data model ERD) for *what*, `CLAUDE.md` (§2) for *how*. This document is the bridge between the two at implementation-detail level, scoped to `backend/` only. Nothing here overrides either file — if a conflict appears, PLAN.md wins on data model, CLAUDE.md wins on code shape.

**Done when** (verbatim from PLAN.md): you can create a PO against a real vendor, in RMB, and see the PKR cost per line and total — solves "how will we buy stock and at what rate."

**Verified starting state** (read directly from `backend/src/` before writing this spec — matches `.claude/specs/phase-0-backend.md` exactly): `auth/` (User, JWT login/refresh), `src/crud.py` (generic CRUD factory, auth-gated, soft-delete-only), `purchasing/` (containing only `ExchangeRate`), `payments/` (containing only `PaymentMethod`), `ledger/` (schema-only `LedgerEntry`, no router/service, nothing writes to it yet). One migration (`2026-08-07_initial_schema.py`) creates `user`, `exchange_rate`, `payment_method`, `ledger_entry`.

---

## 0. Decisions confirmed with user before writing this spec

PLAN.md's ERD draws an explicit `PURCHASE_ORDER ||--o{ LEDGER_ENTRY : posts` edge, and Phase 4's text states "a party's balance is just a query over `ledger.LedgerEntry` filtered by `party_id`" (Principle 4). Neither holds true unless something actually starts writing to the still-empty `ledger_entry` table, and Phase 1 is the first phase with money-committing writes (`PurchaseOrder`, `Party.opening_balance`). Two calls were confirmed up front because reworking the ledger's sign convention later means touching every subsequent phase (payments, sales, expenses):

1. **Ledger writes start now, not in Phase 6.** Creating a `PurchaseOrder` posts a `LedgerEntry` booking the vendor payable (RMB→PKR total) in the same transaction as the PO/line inserts. Creating a `Party` with a nonzero `opening_balance` posts one too. This makes Principle 4's balance-query claim true from Phase 1 onward instead of requiring a Phase 6 retrofit over every PO ever created.
2. **Polarity: credit increases payable.** For a party-linked `LedgerEntry`, `credit` represents money we owe *out* (a vendor payable), `debit` represents money owed *to us* (a customer receivable, starting Phase 4). A party's net payable/receivable is `SUM(credit) - SUM(debit)` filtered by `party_id` — positive means we owe them, negative means they owe us. A later vendor payment (Phase 6) debits the same `party_id` to settle the payable. This is the sign convention every future phase (customer sales in Phase 4, payments in Phase 6) must follow — do not invert it in a later phase.

These two decisions shape §5 (`parties/`) and §6 (`purchasing/`) below.

---

## 1. Scope

Build, in this order (each step is independently testable before moving to the next):

1. `catalog/` domain — `Category`, `Model`, `Item`, all mounted on the generic CRUD factory (`src/crud.py`), no business logic.
2. `parties/` domain — `Party` model (full four-role enum, per the Phase 0 architecture decision that fixed this value set before any phase shipped), hand-written router/service (not the generic factory — opening-balance ledger posting is business logic per CLAUDE.md §2.1/PLAN.md Principle 3).
3. `ledger/` domain gains its first Pydantic schema (`LedgerEntryRead`, read-only) and a `service.py` with a single `post_entry(...)` helper — still no public router; every domain that writes to it calls the helper directly inside its own transaction, per CLAUDE.md's "every other domain imports *into* it, it never imports back."
4. `purchasing/` domain grows from `ExchangeRate`-only to add `PurchaseOrder` and `PurchaseOrderLine` — hand-written router/service (transactional, computes `rate_pkr`, posts a ledger entry).
5. `main.py` wiring — one new router (`catalog`), `parties` router, `purchasing` router already mounted (unchanged prefix, new routes added to the existing file).
6. Migration — one migration for Phase 1: `category`, `model`, `item`, `party`, `purchase_order`, `purchase_order_line`, plus the deferred FK from `ledger_entry.party_id` → `party.id` (impossible in the Phase 0 migration since `party` didn't exist yet; add it now, per that migration's own comment).
7. Seed script extension — starter `Category`/`Model` rows are explicitly **not** seeded (see §7 — Phase 1 has no fixed lookup values the way Phase 0's payment rails did); one seed helper for a China vendor `Party` is added so the "done when" checklist has a real vendor to test against.

Out of scope for Phase 1 (explicitly deferred per PLAN.md roadmap): `CargoShipment`/`CargoAllocation`, `StockLot`, `SalesOrder`, `PaymentAccount`/`PaymentTransaction`, `Expense`. `PurchaseOrderLine` does **not** get a `landed_cost` or a "receive" action yet — that's Phase 2 (cargo) and Phase 3 (inventory) respectively. Do not add placeholder columns for those now.

---

## 2. Folder structure delivered by Phase 1

New/changed pieces only — everything from `.claude/specs/phase-0-backend.md` §2 stays as-is unless noted:

```
backend/
├── migrations/versions/
│   └── 2026-08-07_add_catalog_party_purchasing.py   # Category, Model, Item, Party, PurchaseOrder, PurchaseOrderLine
│                                                       # + ledger_entry.party_id FK (deferred from Phase 0)
├── src/
│   ├── catalog/                    # NEW
│   │   ├── router.py               # three generic CRUD routers (Category, Model, Item) mounted under one APIRouter
│   │   ├── schemas.py              # CategoryCreate/Read/Update, ModelCreate/Read/Update, ItemCreate/Read/Update
│   │   ├── models.py               # Category, Model, Item
│   │   ├── constants.py            # (empty/reserved — no enums needed yet)
│   │   └── exceptions.py           # (empty/reserved — generic CRUD's NotFoundException/ConflictException cover Phase 1)
│   ├── parties/                    # NEW — see CLAUDE.md §2.1: purchasing/cargo/sales import Party by id, parties/ never imports them
│   │   ├── router.py               # hand-written: list/create/get/update/soft-delete (NOT src/crud.py — opening_balance has a side effect)
│   │   ├── schemas.py              # PartyCreate/Read/Update, PartyRole enum
│   │   ├── models.py               # Party
│   │   ├── service.py              # create_party (posts opening-balance LedgerEntry), update_party, list/get (thin, no ledger side effect)
│   │   ├── dependencies.py         # valid_party (fetch-or-404), valid_china_vendor (role + active check, used by purchasing/)
│   │   ├── constants.py            # PARTY_ROLES literal tuple (mirrors the PartyRole enum for non-Pydantic contexts)
│   │   └── exceptions.py           # PartyNotFound, PartyRoleMismatch
│   ├── purchasing/                 # GROWN — ExchangeRate unchanged, PurchaseOrder/PurchaseOrderLine added
│   │   ├── router.py               # ExchangeRate generic router (unchanged) + new hand-written PurchaseOrder router, same file per CLAUDE.md "one APIRouter per domain" — combine with APIRouter().include_router or a second router mounted alongside in main.py
│   │   ├── schemas.py              # + PurchaseOrderCreate/Read/Update, PurchaseOrderLineCreate/Read
│   │   ├── models.py                # + PurchaseOrder, PurchaseOrderLine
│   │   ├── service.py              # NEW — create_purchase_order (snapshots rate_pkr, posts ledger entry, all in one `session.begin()`)
│   │   ├── dependencies.py          # NEW — valid_purchase_order (fetch-or-404), valid_exchange_rate_for_date
│   │   ├── constants.py             # NEW — PurchaseOrderStatus literal ("draft" only in Phase 1 — see §6.3)
│   │   └── exceptions.py            # NEW — ExchangeRateMissingForDate, PurchaseOrderNotFound
│   └── ledger/
│       ├── models.py                # unchanged
│       ├── schemas.py               # NEW — LedgerEntryRead only (no Create/Update — nothing external ever writes to it directly)
│       └── service.py               # NEW — post_entry(db, *, entry_date, account, debit, credit, reference_type, reference_id, party_id) -> LedgerEntry
├── scripts/
│   └── seed.py                     # + seed_china_vendor_party (idempotent, same pattern as existing seed_* helpers)
```

Notes on placement decisions (per CLAUDE.md §2.1's "where a lookup entity lives" rule, and its two named one-way packages):

- **`Category`, `Model`, `Item` → `catalog/`.** Exactly as named in CLAUDE.md's own tree (`catalog/ # Category, Model, Item`). All three are pure lookup/reference data with no side effects — textbook generic-CRUD material per PLAN.md Principle 3.
- **`Party` → its own `parties/` package**, not folded into `catalog/` or `purchasing/`. This is Phase 0's Architecture Decision, just not instantiated as a table until now: "a China vendor, a cargo agent, a customer, and a local vendor are all just contacts... Model one `Party` with roles, not four tables" (PLAN.md Principle 2), and CLAUDE.md is explicit that `purchasing/`, `cargo/`, and `sales/` reference `Party` by id but `parties/` never imports back.
- **`PurchaseOrder`, `PurchaseOrderLine` → `purchasing/`**, alongside the `ExchangeRate` already there — CLAUDE.md's own package comment: `purchasing/ # PurchaseOrder, PurchaseOrderLine`.
- **`ledger/` gains a `service.py` but still no `router.py`.** PLAN.md never gives the ledger its own screen — Phase 8 reads it through other domains' aggregation queries, and every write in Phases 1–7 goes through domain services, not a direct `POST /ledger/entries`. Per CLAUDE.md, this is what keeps `ledger/` "one-way": everything calls `ledger.service.post_entry(...)`, nothing calls back out of it.

---

## 3. `catalog/` domain

### 3.1 Models (`catalog/models.py`)

| Model | Fields | Notes |
|---|---|---|
| `Category` | `id, name (unique), is_active` | Cover, Protector, Charger, … |
| `Model` | `id, name (unique), priority (int, default 0), is_active` | `priority` is write-only-by-Phase-8 for now — Phase 1 just carries the column; nothing in Phase 1 sets it to anything but the default |
| `Item` | `id, category_id (FK→category.id), model_id (FK→model.id), sku (unique), variant (nullable), is_active` | matches the `Item` example already in CLAUDE.md §2.4 verbatim |

```python
# src/catalog/models.py
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.models import Base

class Category(Base):
    __tablename__ = "category"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)

class Model(Base):
    __tablename__ = "model"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    priority: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

class Item(Base):
    __tablename__ = "item"
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"))
    model_id: Mapped[int] = mapped_column(ForeignKey("model.id"))
    sku: Mapped[str] = mapped_column(unique=True)
    variant: Mapped[str | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
```

### 3.2 Schemas (`catalog/schemas.py`)

```python
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


class ModelCreate(BaseModel):
    name: Annotated[str, Field(max_length=120)]

class ModelRead(ModelCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    priority: int
    is_active: bool

class ModelUpdate(BaseModel):
    name: Annotated[str, Field(max_length=120)] | None = None
    priority: int | None = None   # generic factory allows updating it; nothing in Phase 1 writes it automatically


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
```

### 3.3 Router (`catalog/router.py`)

Three generic CRUD routers, combined under one module-level `router` so `main.py` still does one `include_router` call per domain (CLAUDE.md §2.2):

```python
from fastapi import APIRouter
from src.crud import build_crud_router
from src.catalog.models import Category, Model, Item
from src.catalog.schemas import (
    CategoryCreate, CategoryRead, CategoryUpdate,
    ModelCreate, ModelRead, ModelUpdate,
    ItemCreate, ItemRead, ItemUpdate,
)

router = APIRouter()
router.include_router(build_crud_router(model=Category, create_schema=CategoryCreate, read_schema=CategoryRead, update_schema=CategoryUpdate, prefix="/categories", tags=["catalog"]))
router.include_router(build_crud_router(model=Model, create_schema=ModelCreate, read_schema=ModelRead, update_schema=ModelUpdate, prefix="/models", tags=["catalog"]))
router.include_router(build_crud_router(model=Item, create_schema=ItemCreate, read_schema=ItemRead, update_schema=ItemUpdate, prefix="/items", tags=["catalog"]))
```

Mounted in `main.py` as `app.include_router(catalog_router, prefix="/catalog")`, giving `/catalog/categories`, `/catalog/models`, `/catalog/items`.

### 3.4 Known limitation carried from the generic factory (not fixed in Phase 1)

`Item.category_id`/`Item.model_id` are real foreign keys, but `src/crud.py`'s `create_item`/`update_item` only distinguish failures by catching `IntegrityError` broadly and always raising `ConflictException` (409) — per `.claude/specs/phase-0-backend.md` §6.1's note, this was written for `ExchangeRate`'s unique-date constraint, not FK violations. A `POST /catalog/items` with a nonexistent `category_id` will currently surface as a 409 ("Item already exists") rather than a more correct 404/422 on the bad reference. Not fixed here because it's a generic-factory concern, not `Item`-specific, and CLAUDE.md warns against adding per-model hooks to the factory speculatively. Worth revisiting in `src/crud.py` itself (e.g. inspect `exc.orig.pgcode` to distinguish `23505` unique-violation from `23503` FK-violation) the next time any domain hits this in practice — flagged here so it isn't mistaken for an oversight.

---

## 4. `ledger/` domain additions

### 4.1 Schema (`ledger/schemas.py`) — read-only

```python
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

class LedgerEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    entry_date: date
    account: str
    debit: Decimal
    credit: Decimal
    reference_type: str | None
    reference_id: int | None
    party_id: int | None
    created_at: datetime
```

No `LedgerEntryCreate`/`Update` — per PLAN.md, the ledger is append-only and every write is a side effect of a domain action, never a direct client POST. No router in Phase 1 either — nothing in Phase 1's "done when" reads the ledger back out through an endpoint (that's Phase 4's party statement and Phase 8's balance statement). `LedgerEntryRead` exists now only so `parties/service.py` and `purchasing/service.py` can type their internal calls precisely; it is unused by any router until a later phase needs `GET /ledger/entries` or a party-statement endpoint.

### 4.2 Service (`ledger/service.py`)

```python
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from src.ledger.models import LedgerEntry

async def post_entry(
    db: AsyncSession,
    *,
    entry_date: date,
    account: str,
    debit: Decimal = Decimal("0"),
    credit: Decimal = Decimal("0"),
    reference_type: str,
    reference_id: int,
    party_id: int | None = None,
) -> LedgerEntry:
    entry = LedgerEntry(
        entry_date=entry_date,
        account=account,
        debit=debit,
        credit=credit,
        reference_type=reference_type,
        reference_id=reference_id,
        party_id=party_id,
    )
    db.add(entry)
    return entry
```

Deliberately does **not** call `db.commit()` — per CLAUDE.md §2.5, the caller (`parties/service.py`'s `create_party`, `purchasing/service.py`'s `create_purchase_order`) wraps its own domain writes and this call in one `async with session.begin():` block, so a party or PO can never commit without its ledger entry, or vice versa. This is the one function every future ledger-affecting domain (Phase 4 sales, Phase 6 payments, Phase 7 expenses) will import — it is the single point that keeps `LedgerEntry` construction consistent (CLAUDE.md: "everyone imports into `ledger/`, it never imports back").

---

## 5. `parties/` domain

### 5.1 `Party` model (`parties/models.py`)

Per PLAN.md's Architecture Decisions table, plus the two decisions in §0:

| Field | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `name` | `str` | not unique — two distinct vendors can share a display name |
| `contact` | `str \| None` | phone/contact string |
| `address` | `str \| None` | |
| `roles` | `ARRAY(String)`, Postgres native array | full four-value set (`china_vendor`, `cargo_agent`, `customer`, `local_vendor`) — the value set was fixed as an Architecture Decision before Phase 0 shipped, so declaring all four now isn't scope creep, it's the documented shape of this one column. Only `china_vendor`-role business rules are exercised in Phase 1 (§5.4) |
| `opening_balance` | `Numeric(12,2)`, default `0` | signed — positive means the party owes us, negative means we owe them (same polarity as §0 decision 2) |
| `is_active` | `bool`, default `True` | soft delete |

```python
# src/parties/models.py
from decimal import Decimal
from sqlalchemy import ARRAY, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from src.models import Base

class Party(Base):
    __tablename__ = "party"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    contact: Mapped[str | None] = mapped_column(nullable=True)
    address: Mapped[str | None] = mapped_column(nullable=True)
    roles: Mapped[list[str]] = mapped_column(ARRAY(String))
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
```

`ARRAY(String)` (Postgres-native, via SQLAlchemy's dialect-level `ARRAY` type) was chosen over a `party_role` junction table because roles here are a fixed four-value enum with no per-role attributes of their own (no "date assigned," no per-role state) — a junction table would be normalization without payoff. Revisit only if a role ever needs its own data.

### 5.2 Schemas (`parties/schemas.py`)

```python
from decimal import Decimal
from enum import Enum
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator

class PartyRole(str, Enum):
    CHINA_VENDOR = "china_vendor"
    CARGO_AGENT = "cargo_agent"
    CUSTOMER = "customer"
    LOCAL_VENDOR = "local_vendor"

class PartyCreate(BaseModel):
    name: Annotated[str, Field(max_length=120)]
    contact: Annotated[str | None, Field(max_length=64)] = None
    address: Annotated[str | None, Field(max_length=255)] = None
    roles: Annotated[list[PartyRole], Field(min_length=1)]
    opening_balance: Decimal = Decimal("0")

class PartyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    contact: str | None
    address: str | None
    roles: list[PartyRole]
    opening_balance: Decimal
    is_active: bool

class PartyUpdate(BaseModel):
    name: Annotated[str, Field(max_length=120)] | None = None
    contact: Annotated[str | None, Field(max_length=64)] = None
    address: Annotated[str | None, Field(max_length=255)] = None
    roles: Annotated[list[PartyRole], Field(min_length=1)] | None = None
    # opening_balance is intentionally NOT updatable here — see §5.4, it's a
    # write-once value posted to the ledger at creation; changing it later
    # would silently desync the party's ledger history from the column.
```

`opening_balance` omission from `PartyUpdate` is a deliberate business rule, not an oversight — flagged inline since CLAUDE.md's usual pattern is "every field optional on Update" and this is the one field in Phase 1 that breaks that pattern for a documented reason.

### 5.3 Exceptions (`parties/exceptions.py`)

```python
from src.exceptions import AppException, NotFoundException

class PartyNotFound(NotFoundException):
    detail = "Party not found"

class PartyRoleMismatch(AppException):
    status_code = 422
    detail = "Party does not have the required role"
```

### 5.4 Service (`parties/service.py`)

```python
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from src.parties.models import Party
from src.parties.schemas import PartyCreate, PartyUpdate
from src.ledger import service as ledger_service

async def create_party(db: AsyncSession, payload: PartyCreate) -> Party:
    async with db.begin():
        party = Party(
            name=payload.name,
            contact=payload.contact,
            address=payload.address,
            roles=[r.value for r in payload.roles],
            opening_balance=payload.opening_balance,
        )
        db.add(party)
        await db.flush()   # party.id is needed for the ledger entry below

        if payload.opening_balance != 0:
            debit, credit = (payload.opening_balance, 0) if payload.opening_balance > 0 else (0, -payload.opening_balance)
            await ledger_service.post_entry(
                db,
                entry_date=date.today(),
                account="Party Opening Balance",
                debit=debit,
                credit=credit,
                reference_type="party_opening_balance",
                reference_id=party.id,
                party_id=party.id,
            )
    await db.refresh(party)
    return party

# list_parties / get_party / update_party / soft_delete_party: thin, no ledger side effect —
# same shape as the generic factory's list/get/update/delete, just hand-written because
# create_party above needs the transactional wrapper and a router can't mix one generic +
# one hand-written endpoint under `build_crud_router`.
```

Why the whole router is hand-written and not "generic factory for 4 of 5 endpoints, custom for create": `build_crud_router` returns one complete `APIRouter` with no seam to override a single endpoint — per CLAUDE.md §2.1/PLAN.md Principle 3, an entity where *any* endpoint carries business logic gets a hand-written package, not a partially-generic one. The list/get/update/soft-delete bodies are still trivial (same query shapes as `src/crud.py`), just copied into `parties/service.py` rather than inherited.

### 5.5 Dependencies (`parties/dependencies.py`)

```python
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.parties.models import Party
from src.parties.exceptions import PartyNotFound

async def valid_party(party_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> Party:
    party = await db.get(Party, party_id)
    if not party or not party.is_active:
        raise PartyNotFound()
    return party
```

`valid_china_vendor(party: Annotated[Party, Depends(valid_party)]) -> Party` (raises `PartyRoleMismatch` if `"china_vendor" not in party.roles`) lives here too, but is consumed by `purchasing/dependencies.py`, not `parties/router.py` itself — this is the cross-domain reference CLAUDE.md describes ("`purchasing/`... import[s] `Party` by id from here").

### 5.6 Router (`parties/router.py`)

Standard shape, all routes behind `get_current_user` (same as every other Phase 1 route — see §8):

```python
router = APIRouter(prefix="/parties", tags=["parties"])

@router.get("", response_model=PaginatedResponse[PartyRead])
async def list_parties(pagination: Annotated[PaginationParams, Query()], db: ..., _: Annotated[User, Depends(get_current_user)]): ...

@router.post("", response_model=PartyRead, status_code=201)
async def create_party(payload: PartyCreate, db: ..., _: ...):
    return await service.create_party(db, payload)

@router.get("/{party_id}", response_model=PartyRead)
async def get_party(party: Annotated[Party, Depends(valid_party)]):
    return party

@router.put("/{party_id}", response_model=PartyRead)
async def update_party(payload: PartyUpdate, party: Annotated[Party, Depends(valid_party)], db: ...): ...

@router.delete("/{party_id}", status_code=204)
async def soft_delete_party(party: Annotated[Party, Depends(valid_party)], db: ...): ...
```

---

## 6. `purchasing/` domain growth

### 6.1 Models (`purchasing/models.py`) — `ExchangeRate` unchanged, two new tables added to the same file

| Model | Fields | Notes |
|---|---|---|
| `PurchaseOrder` | `id, party_id (FK→party.id), order_date (date), status (str, default "draft"), created_at` | no `total` column — totals are computed, never stored (see §6.2) |
| `PurchaseOrderLine` | `id, purchase_order_id (FK→purchase_order.id), item_id (FK→item.id), qty (Numeric(10,2)), rate_rmb (Numeric(12,2)), rate_pkr (Numeric(12,2))` | `rate_pkr` is the snapshot — set once at creation from that day's `ExchangeRate`, per PLAN.md's Currency handling section, never recalculated |

```python
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column
from src.models import Base

class PurchaseOrder(Base):
    __tablename__ = "purchase_order"
    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"))
    order_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_line"
    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_order.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"))
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    rate_rmb: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    rate_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2))
```

Neither table gets `is_active` — CLAUDE.md's soft-delete non-negotiable is about *lookup/reference* rows being retired without breaking history; a `PurchaseOrder` is itself a historical record, not a lookup a later record points at. (`Party`, `Category`, `Model`, `Item` all keep `is_active` because *they* are the things a PO/line references and must survive being "deactivated.") No cancel/void flow exists in Phase 1 — if one is needed later, `status` already has room for a `"cancelled"` value without a schema change.

### 6.2 Schemas (`purchasing/schemas.py`) — appended after existing `ExchangeRate*` schemas

```python
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, computed_field

class PurchaseOrderLineCreate(BaseModel):
    item_id: int
    qty: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    rate_rmb: Annotated[Decimal, Field(gt=0, decimal_places=2)]

class PurchaseOrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    item_id: int
    qty: Decimal
    rate_rmb: Decimal
    rate_pkr: Decimal

    @computed_field
    @property
    def amount_rmb(self) -> Decimal:
        return self.qty * self.rate_rmb

    @computed_field
    @property
    def amount_pkr(self) -> Decimal:
        return self.qty * self.rate_pkr

class PurchaseOrderCreate(BaseModel):
    party_id: int
    order_date: date
    lines: Annotated[list[PurchaseOrderLineCreate], Field(min_length=1)]

class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    party_id: int
    order_date: date
    status: str
    lines: list[PurchaseOrderLineRead]

    @computed_field
    @property
    def total_rmb(self) -> Decimal:
        return sum((line.amount_rmb for line in self.lines), Decimal("0"))

    @computed_field
    @property
    def total_pkr(self) -> Decimal:
        return sum((line.amount_pkr for line in self.lines), Decimal("0"))

class PurchaseOrderUpdate(BaseModel):
    status: str | None = None   # the only field allowed to change post-creation in Phase 1 — see §6.3
```

`amount_*`/`total_*` are Pydantic `computed_field`s, not stored columns — `qty` and the snapshotted `rate_rmb`/`rate_pkr` are the only facts that need to survive a rate change elsewhere, and deriving the rest at read time means there's no risk of a stored total drifting from its line items. This does **not** conflict with PLAN.md's "snapshot, don't recompute, historical rates" rule — that rule protects `rate_pkr` itself (never recompute *that* from today's rate), not arithmetic on values already snapshotted.

### 6.3 `PurchaseOrderStatus` (`purchasing/constants.py`)

```python
from typing import Literal
PurchaseOrderStatus = Literal["draft"]
```

Phase 1 has exactly one status value. This isn't an oversight — PLAN.md gives `PurchaseOrder` no workflow in Phase 1 ("record a real PO," nothing about confirming/receiving it); "received" first appears conceptually in Phase 3 ("once its shipment has landed cost"). Widening this `Literal` (e.g. adding `"received"`) is a Phase 2/3 concern, done when those phases actually need to transition a PO's state — not pre-added here as a guess.

### 6.4 Exceptions (`purchasing/exceptions.py`)

```python
from src.exceptions import AppException, NotFoundException

class PurchaseOrderNotFound(NotFoundException):
    detail = "Purchase order not found"

class ExchangeRateMissingForDate(AppException):
    status_code = 422
    detail = "No exchange rate is set for this order's date"
```

### 6.5 Dependencies (`purchasing/dependencies.py`)

```python
async def valid_purchase_order(purchase_order_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> PurchaseOrder:
    po = await db.get(PurchaseOrder, purchase_order_id, options=[selectinload(PurchaseOrder.lines)])
    if not po:
        raise PurchaseOrderNotFound()
    return po
```

Uses `selectinload` per CLAUDE.md §2.5 ("load relationships explicitly... never rely on lazy-load inside an async context") — `PurchaseOrderRead` always serializes `lines`, so every fetch path must eager-load them. `PurchaseOrder.lines` relationship (`relationship("PurchaseOrderLine", ...)`) is declared in `purchasing/models.py` alongside the two model classes (omitted from §6.1's snippet for brevity, but required).

### 6.6 Service (`purchasing/service.py`)

```python
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.purchasing.models import ExchangeRate, PurchaseOrder, PurchaseOrderLine
from src.purchasing.schemas import PurchaseOrderCreate
from src.purchasing.exceptions import ExchangeRateMissingForDate
from src.parties.models import Party
from src.ledger import service as ledger_service

async def create_purchase_order(db: AsyncSession, payload: PurchaseOrderCreate, vendor: Party) -> PurchaseOrder:
    rate_row = await db.scalar(select(ExchangeRate).where(ExchangeRate.rate_date == payload.order_date, ExchangeRate.is_active.is_(True)))
    if not rate_row:
        raise ExchangeRateMissingForDate()

    async with db.begin():
        po = PurchaseOrder(party_id=vendor.id, order_date=payload.order_date)
        db.add(po)
        await db.flush()

        total_pkr = Decimal("0")
        for line in payload.lines:
            rate_pkr = (line.rate_rmb * rate_row.rate).quantize(Decimal("0.01"))
            db.add(PurchaseOrderLine(
                purchase_order_id=po.id, item_id=line.item_id,
                qty=line.qty, rate_rmb=line.rate_rmb, rate_pkr=rate_pkr,
            ))
            total_pkr += line.qty * rate_pkr

        await ledger_service.post_entry(
            db,
            entry_date=payload.order_date,
            account="Accounts Payable",
            credit=total_pkr,   # §0 decision 2: credit increases payable
            reference_type="purchase_order",
            reference_id=po.id,
            party_id=vendor.id,
        )

    await db.refresh(po, attribute_names=["lines"])
    return po
```

`vendor: Party` is injected by the router via `Depends(valid_china_vendor)` (§5.5), not looked up again inside the service — keeps the "does this party exist and hold the right role" check in one place, reusable by any future domain that also requires a `china_vendor` (none yet in Phase 1, but Phase 5 reuses this exact purchase flow for `local_vendor` per PLAN.md, which is why the check is a composable dependency and not inlined into this function).

One `ExchangeRate` lookup, one `session.begin()` wrapping the PO insert + every line insert + the ledger post — a partially-inserted PO (lines written, ledger entry missing, or vice versa) can never commit, per CLAUDE.md §2.5.

### 6.7 Router (`purchasing/router.py`) — appended after the existing `ExchangeRate` generic router

```python
purchase_order_router = APIRouter(prefix="/purchase-orders", tags=["purchasing"])

@purchase_order_router.post("", response_model=PurchaseOrderRead, status_code=201)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    vendor: Annotated[Party, Depends(valid_china_vendor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    return await service.create_purchase_order(db, payload, vendor)

@purchase_order_router.get("", response_model=PaginatedResponse[PurchaseOrderRead])
async def list_purchase_orders(...): ...

@purchase_order_router.get("/{purchase_order_id}", response_model=PurchaseOrderRead)
async def get_purchase_order(po: Annotated[PurchaseOrder, Depends(valid_purchase_order)]):
    return po
```

`valid_china_vendor` takes `party_id` from the request body (`PurchaseOrderCreate.party_id`), not a path param — FastAPI resolves a `Depends()` parameter's own sub-dependency (`valid_party`'s `party_id: int`) from any matching name in the combined path/query/body scope, so this works without extra plumbing as long as `PurchaseOrderCreate.party_id` and the dependency's `party_id` argument share the name. No `PUT`/`DELETE` on `purchase-orders` in Phase 1 — PLAN.md's "done when" only requires create + view; editing a submitted PO's lines is not asked for and would reopen the "already-posted ledger entry" problem this spec doesn't attempt to solve yet.

`main.py`: mount both routers from `purchasing/router.py` — `app.include_router(exchange_rate_router, prefix="/purchasing")` (unchanged) and `app.include_router(purchase_order_router, prefix="/purchasing")`.

---

## 7. Migration

- One migration for Phase 1: creates `category`, `model`, `item`, `party`, `purchase_order`, `purchase_order_line`, and **alters** `ledger_entry` to add the FK constraint on `party_id` → `party.id` that Phase 0's migration explicitly deferred ("`Party` table doesn't exist until Phase 1; adding the FK now is impossible... Add the constraint in the Phase-1 migration that creates `Party`").
- Autogenerate (`alembic revision --autogenerate -m "add catalog, party, purchasing"`), then hand-review — per CLAUDE.md, pay particular attention to `Numeric(10,2)` on `qty` and `Numeric(12,2)` on `rate_rmb`/`rate_pkr`/`opening_balance`, and to the `ARRAY(String)` column on `party.roles` (autogenerate sometimes needs a manual nudge for Postgres array types).
- Double-check the new `ledger_entry_party_id_fkey` migration step doesn't fail against any pre-existing `ledger_entry` rows — Phase 0 never wrote any, so this is a no-op in practice, but if a dev database was seeded with test ledger rows out-of-band, they'd need a valid `party_id` or `NULL` before the constraint lands.

---

## 8. `main.py`

```python
from src.catalog.router import router as catalog_router
from src.parties.router import router as parties_router
# existing imports unchanged: auth_router, purchasing exchange_rate router, payments_router
from src.purchasing.router import router as exchange_rate_router, purchase_order_router

app.include_router(catalog_router, prefix="/catalog")
app.include_router(parties_router)   # parties_router already declares prefix="/parties" internally
app.include_router(exchange_rate_router, prefix="/purchasing")
app.include_router(purchase_order_router, prefix="/purchasing")
```

Every new route in Phase 1 is bearer-gated via `get_current_user` — same default carried forward from Phase 0's confirmed decision ("Auth-gating the generic CRUD routes — confirmed yes"), extended here to the hand-written `parties/` and `purchasing/purchase-orders` routes for consistency (nothing in PLAN.md suggests Phase 1 introduces an unauthenticated surface).

---

## 9. Seed script (`scripts/seed.py`)

Extended, not replaced — existing `seed_user`/`seed_exchange_rate`/`seed_payment_methods` calls stay as they are:

- **No seeded `Category`/`Model` rows.** Unlike Phase 0's `PaymentMethod` list (`"Bank"`, `"JazzCash"`, …, which are the domain's actual fixed lookup values straight from PLAN.md), Phase 1's categories and models ("Cover, Protector, Charger", "iPhone 13, Galaxy A54") are PLAN.md's own *illustrative examples*, not a real starter catalog — hardcoding them would be inventing fictional business data. Leave catalog empty; the person running this seeds their real categories/models through the generic CRUD screen once the frontend phase exists, which is the whole point of Principle 3.
- **One seeded China vendor `Party`** — needed because Phase 1's "done when" requires "a real vendor" to place a PO against, and there's no CRUD screen yet to create one by hand. Same idempotent pattern as the existing helpers:

```python
async def seed_china_vendor(session, name: str) -> None:
    existing = await session.scalar(select(Party).where(Party.name == name))
    if existing:
        print(f"Party '{name}' already exists, skipping.")
        return
    session.add(Party(name=name, roles=["china_vendor"], opening_balance=Decimal("0")))
    print(f"Created Party '{name}' (china_vendor).")
```

Takes `--vendor-name` as a new CLI arg (default omitted deliberately — a fabricated vendor name shouldn't be baked into the script any more than a fabricated exchange rate is in the existing `--rate` arg). Uses `session.add` directly rather than `parties.service.create_party` since `opening_balance=0` here means no ledger entry needs posting — going through the full service would work too but pulls in a transaction wrapper for a no-op ledger write; documented here as the reason the seed script doesn't call the service layer, not an inconsistency.

---

## 10. API surface summary

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET/POST | `/catalog/categories[/…]` | bearer | generic CRUD |
| GET/POST | `/catalog/models[/…]` | bearer | generic CRUD |
| GET/POST | `/catalog/items[/…]` | bearer | generic CRUD |
| GET | `/parties` | bearer | paginated list |
| POST | `/parties` | bearer | create — posts a `LedgerEntry` if `opening_balance != 0` |
| GET | `/parties/{id}` | bearer | fetch one |
| PUT | `/parties/{id}` | bearer | partial update (not `opening_balance`) |
| DELETE | `/parties/{id}` | bearer | soft delete |
| GET/POST | `/purchasing/exchange-rates[/…]` | bearer | unchanged from Phase 0 |
| POST | `/purchasing/purchase-orders` | bearer | create — vendor must hold `china_vendor` role, requires an `ExchangeRate` row for `order_date`, posts a `LedgerEntry` |
| GET | `/purchasing/purchase-orders` | bearer | paginated list |
| GET | `/purchasing/purchase-orders/{id}` | bearer | fetch one, with lines + computed RMB/PKR totals |

---

## 11. Testing checklist (manual, matches PLAN.md's "done when")

1. `alembic upgrade head` runs clean on top of Phase 0's schema; `ledger_entry.party_id` now carries a real FK.
2. `python -m scripts.seed --username ... --password ... --rate ... --vendor-name "Shenzhen Accessories Co."` creates the vendor `Party` without error, safely re-runnable.
3. `POST /catalog/categories` / `/catalog/models` / `/catalog/items` each succeed with a valid payload; `POST /catalog/items` with an unknown `category_id` returns *some* 4xx (see §3.4's known-limitation note on the exact code) rather than a 500.
4. `POST /parties` with `roles: ["china_vendor"]` and `opening_balance: 50000` returns 201, and a follow-up query confirms exactly one new `LedgerEntry` row exists with `party_id` set, `credit=50000`, `reference_type="party_opening_balance"`.
5. `POST /parties` with `opening_balance: 0` (the common case) creates the party with **no** new `LedgerEntry` row — confirms the `!= 0` guard in §5.4 isn't posting empty entries.
6. `POST /purchasing/purchase-orders` against a party that does **not** have `china_vendor` in `roles` returns 422 (`PartyRoleMismatch`), not a silent success.
7. `POST /purchasing/purchase-orders` with `order_date` set to a date with no seeded `ExchangeRate` row returns 422 (`ExchangeRateMissingForDate`).
8. `POST /purchasing/purchase-orders` with a valid vendor, a date that has an `ExchangeRate`, and two lines succeeds (201); the response's `lines[].rate_pkr` matches `rate_rmb * that day's rate`, and `total_pkr` matches the sum of `qty * rate_pkr` across lines.
9. Immediately after step 8, exactly one new `LedgerEntry` exists with `account="Accounts Payable"`, `credit=total_pkr` from the response, `reference_type="purchase_order"`, `reference_id=` the new PO's id, `party_id=` the vendor's id.
10. `GET /purchasing/purchase-orders/{id}` returns the same PO with lines eager-loaded (no lazy-load error under the async session).
11. Any of the above without a bearer token returns 401.
