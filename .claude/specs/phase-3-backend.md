# Phase 3 Backend Spec — Inventory / Warehouse

Governed by `PLAN.md` (what) and `CLAUDE.md` (how). This document is the missing middle layer: the exact entities, endpoints, and service logic to implement Phase 3 inside `backend/src/inventory/`, consistent with what Phases 0–2 already built. Nothing here overrides `CLAUDE.md`'s conventions — every choice below follows an existing precedent in the codebase, cited by file.

**Done when** (from `PLAN.md`): for any model, you can see exactly how many units you hold, split by which lot they came in on and at what cost.

---

## 1. Where we stand

Confirmed by reading the actual code, not assumed:

- **Built**: `auth`, `parties`, `catalog`, `purchasing`, `cargo`, `ledger`, and a `payments` stub (`PaymentMethod` lookup only). Generic CRUD engine (`src/crud.py`) is proven on `Category`, `Model`, `Item`, `PaymentMethod`, `ExchangeRate`, `CargoMode`, `CargoCostBasis`.
- **`PurchaseOrderLine.landed_cost_pkr`** (`purchasing/models.py:45`) is already there — `Numeric(12,2)`, nullable, written exactly once by `cargo/service.py:84` when a shipment allocates freight cost to that line. Nothing in Phase 3 needs to touch cargo at all; it only ever reads this already-persisted column via `purchasing`.
- **`PurchaseOrder.status`** (`purchasing/constants.py`) is currently `Literal["draft", "allocated"]`, with a comment already anticipating this phase: *"Widen again when a later phase needs to (e.g. Phase 3's 'received')."* Phase 3 is what cashes in that breadcrumb.
- **No receipt-state field exists anywhere.** Neither `PurchaseOrder` nor `PurchaseOrderLine` has a boolean/timestamp marking "this line has been received." Phase 3 must decide how a line's receipt state is tracked (§2.1).
- **`src/inventory/` does not exist.** Confirmed via grep across the whole `backend/` tree: zero matches for `StockLot` or `StockMovement`. Phase 3 starts this domain from zero.
- **Ledger** (`ledger/service.post_entry`) is currently called only by `purchasing` (PO creation → credits "Accounts Payable") and `parties` (opening balance). `cargo/service.py` posts nothing to the ledger — freight cost changes `PurchaseOrderLine.landed_cost_pkr` but never books a payable to the cargo agent. **This is a pre-existing gap, not something Phase 3 fixes** (see §9) — flagged here so it isn't mistaken for something this phase was supposed to close.
- `PLAN.md`'s own Principle 4 explicitly names "a stock receipt" as one of the actions that must post to the ledger, alongside a sale/payment/expense — so, unlike cargo's allocation, Phase 3's receive action is not optional on this point (§2.4).

---

## 2. Design decisions

Four calls this spec makes that aren't spelled out in `PLAN.md`. Recorded here so they're reviewed once, not re-derived during implementation.

### 2.1 A line's "received" state is the existence of its `StockLot`, not a new column on `PurchaseOrderLine`

`CargoAllocation.purchase_order_line_id` already uses a DB-unique FK to make "this line has already been allocated" a query, not a flag someone forgets to set (`cargo/models.py:51-53`). `StockLot.purchase_order_line_id` follows the identical pattern: `unique=True, index=True`. A line is "received" exactly when a row in `stock_lot` references it.

This means **no migration touches `purchasing/models.py` at all** — `purchasing` stays the sole owner of its own table, and `inventory` only ever reads `PurchaseOrderLine.landed_cost_pkr`/`.qty`/`.purchase_order_id` and writes to its own tables. Same one-way shape `cargo` already established toward `purchasing` (§2.4 in the Phase 2 spec).

### 2.2 `PurchaseOrder.status` gains `"received"`, flipped once every line on that PO has a lot

Mirrors exactly how `cargo/service.py:88` flips `status = "allocated"` once every line under an attached PO has been allocated. `purchasing/constants.py` widens to:

```python
# Phase 3 adds the terminal status: once every line on a PO has a StockLot
# (src.inventory.service.receive_purchase_order_line), the PO flips to "received".
# There is no status after this — a received PO is done.
PurchaseOrderStatus = Literal["draft", "allocated", "received"]
```

Receiving happens per-line (`PLAN.md`: "a 'Receive' action turns a PO line ... into a StockLot"), so the flip is computed as a side effect after each receive, not a separate action — see §5.1 step 6.

### 2.3 A line is received whole, in one shot — no partial receiving, no quantity override

`StockLot.qty_received` is always exactly `PurchaseOrderLine.qty`; the receive payload carries only `purchase_order_line_id` and `received_date`. This is the same simplifying call the Phase 2 spec made for shipments ("no partial shipments" — see that document's §9): modeling "the shipment arrived short of what was ordered" would mean a line could spawn more than one `StockLot`, which breaks the unique-FK-as-receipt-marker design in §2.1 and isn't asked for by `PLAN.md`'s wording. If short-shipment tracking turns out to be a real need, it reopens both this decision and §2.1's uniqueness constraint together — flagged again in §9.

Landed cost is never re-entered at receive time either — `StockLot.landed_cost_pkr` is copied once from `PurchaseOrderLine.landed_cost_pkr`, same "snapshot, don't recompute" rule `rate_pkr` and `landed_cost_pkr` itself already follow (`CLAUDE.md` §4).

### 2.4 Receiving posts one `LedgerEntry`; manual adjustments post none

`PLAN.md` Principle 4 lists "a stock receipt" by name as a ledger-affecting action, so `receive_purchase_order_line` debits an `"Inventory"` account for the landed value of the qty received (`reference_type="stock_lot"`), in the same transaction as the `StockLot` insert — exactly the `post_entry`-then-`commit` shape `purchasing.service.create_purchase_order` already uses (§5.1 step 5).

Manual `StockMovement` adjustments (damage/loss/recount) deliberately **do not** post anything to the ledger in this phase. `PLAN.md` names "a stock receipt," not "any stock movement," as the ledger-triggering event — a damage write-off turning into a booked expense is plausibly Phase 7's (`Expense`) job once that domain exists, referencing the `StockMovement` row, not something to half-implement here by guessing at an account name. Called out explicitly in §9 rather than silently skipped.

One consequence worth being upfront about: because the "Inventory" account only ever receives debits in this phase (nothing decrements it — Phase 4's future sale-consumption isn't scoped here, and adjustments don't touch it either per this decision), its running balance will not equal `SUM(qty_remaining × landed_cost_pkr)` over live lots except immediately after this phase ships. `PLAN.md`'s own Phase 8 description confirms this is expected, not a bug to pre-empt: it computes inventory valuation "from remaining `StockLot` quantity × cost" directly off the lots table, not by reading the `"Inventory"` ledger account. The ledger entry this phase posts exists to satisfy Principle 4 literally and to give Phase 8 a receipts-over-time audit trail — it is not, and was never meant to be, the source of truth for current on-hand value.

---

## 3. Data model

### 3.1 New tables (`backend/src/inventory/models.py`)

**`stock_lot`** — hand-written, transactional (like `PurchaseOrder`/`CargoShipment`): no `is_active`, no delete endpoint. `qty_remaining` is the one mutable field on this table, moved only by `inventory.service` functions (receive, adjust — and, later, Phase 4's FIFO consumption), never by a generic CRUD `PUT`.

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `purchase_order_line_id` | FK → `purchase_order_line.id`, **unique**, indexed | one lot per line — the receipt marker itself (§2.1) |
| `item_id` | FK → `item.id`, indexed | denormalized copy of `line.item_id` at receive time — lets every inventory query filter by item without joining through `purchasing` (mirrors why `cargo_allocation` copies `basis_value` rather than recomputing it) |
| `qty_received` | `Numeric(10, 2)` | snapshot of `line.qty` at receive time (§2.3), immutable after insert |
| `qty_remaining` | `Numeric(10, 2)` | starts equal to `qty_received`; the only column this phase's adjustment endpoint mutates |
| `landed_cost_pkr` | `Numeric(12, 2)` | per-unit cost, snapshot of `line.landed_cost_pkr` at receive time (§2.3), immutable |
| `received_date` | `Date` | user-supplied — may differ from the cargo shipment's `shipment_date`; goods can land days after a shipment record is created |
| `created_at` | `DateTime(timezone=True)`, `server_default=func.now()` | |

**`stock_movement`** — append-only audit trail, same shape as `LedgerEntry`: no `is_active`, no update/delete endpoint, ever. Every change to a lot's `qty_remaining` — the initial receipt and every later adjustment — gets one row here, so `SUM(qty_delta) for a lot == that lot's current qty_remaining` always holds, the same invariant `LedgerEntry` gives you for an account balance.

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `stock_lot_id` | FK → `stock_lot.id`, indexed | |
| `movement_type` | `str` | `"receipt" \| "adjustment"` — see `constants.py` below |
| `qty_delta` | `Numeric(10, 2)` | signed: `+qty_received` on receipt; positive (recount found more) or negative (damage/loss) on adjustment |
| `reason` | `str \| None`, nullable | `NULL` for the auto-created `"receipt"` row; required (enforced in the schema/service, not the DB) for `"adjustment"` |
| `movement_date` | `Date` | |
| `created_at` | `DateTime(timezone=True)`, `server_default=func.now()` | |

```python
# backend/src/inventory/models.py
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class StockLot(Base):
    __tablename__ = "stock_lot"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_line_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_order_line.id"), unique=True, index=True
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), index=True)
    qty_received: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    qty_remaining: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    landed_cost_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    received_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StockMovement(Base):
    __tablename__ = "stock_movement"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_lot_id: Mapped[int] = mapped_column(ForeignKey("stock_lot.id"), index=True)
    movement_type: Mapped[str]
    qty_delta: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    reason: Mapped[str | None] = mapped_column(nullable=True)
    movement_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

No relationship attributes needed on either side this phase — every access pattern below (§5) is a direct filtered query, not a graph walk, so there's nothing to justify a `lazy="raise"` relationship yet (unlike `PurchaseOrder.lines`/`CargoShipment.allocations`, which the response schemas need nested).

### 3.2 Changed constant: `purchasing/constants.py`

Widen `PurchaseOrderStatus` per §2.2. This is the only change to an existing file's *schema-relevant* content in this phase — no migration required for it (`status` is already a plain `str` column; only the Python-side `Literal` widens, same as Phase 2's own note here).

### 3.3 `inventory/constants.py`

```python
from typing import Literal

# "sale" gets added here in Phase 4, when FIFO consumption becomes a third
# kind of qty_remaining-moving event — same widen-later pattern as
# purchasing.constants.PurchaseOrderStatus.
StockMovementType = Literal["receipt", "adjustment"]
```

### 3.4 Directional dependency this phase establishes

`inventory/` imports `purchasing.models.{PurchaseOrder, PurchaseOrderLine}` (reads `qty`/`item_id`/`landed_cost_pkr`, mutates `PurchaseOrder.status`) — the same one-way shape `cargo` already has toward `purchasing`. `inventory/` does **not** import anything from `src.cargo` — it never needs to, because `landed_cost_pkr` already carries cargo's contribution by the time inventory reads it (§1). `purchasing` never imports `inventory`. This keeps three domains in a strict line — `purchasing` ← `cargo`, `purchasing` ← `inventory` — rather than a triangle, which is what makes `cargo`'s eventual removal-or-rework (if the business ever changes how freight is costed) unable to break `inventory`.

---

## 4. Pydantic schemas (`backend/src/inventory/schemas.py`)

### 4.1 `StockLot`

```python
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field

from src.inventory.constants import StockMovementType
from src.inventory.utils import money


class StockLotReceiveCreate(BaseModel):
    purchase_order_line_id: int
    received_date: date


class StockLotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    purchase_order_line_id: int
    item_id: int
    qty_received: Decimal
    qty_remaining: Decimal
    landed_cost_pkr: Decimal
    received_date: date

    @computed_field
    @property
    def value_remaining_pkr(self) -> Decimal:
        return money(self.qty_remaining * self.landed_cost_pkr)
```

No `StockLotUpdate` — like `PurchaseOrder`/`CargoShipment`, this is create + list + get only in this phase (§9). `qty_remaining` is never edited directly through this schema; it only moves via `StockMovementCreate` (§4.2).

### 4.2 `StockMovement`

```python
class StockMovementCreate(BaseModel):
    stock_lot_id: int
    qty_delta: Annotated[Decimal, Field(decimal_places=2)]
    reason: Annotated[str, Field(max_length=255)]
    movement_date: date
    # movement_type is not client-settable — every row created through this schema
    # is a "adjustment"; "receipt" rows are only ever created internally by
    # service.receive_purchase_order_line (§5.1).


class StockMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_lot_id: int
    movement_type: StockMovementType
    qty_delta: Decimal
    reason: str | None
    movement_date: date
    created_at: datetime
```

`qty_delta == 0` and out-of-range results are rejected in `service.py`, not the schema (§5.2) — the valid range depends on the target lot's current `qty_remaining`/`qty_received`, which a stateless Pydantic validator can't see.

### 4.3 `inventory/utils.py`

Deliberate duplicate of `purchasing/utils.py`/`cargo/utils.py` — same rationale as the Phase 2 spec's §5.5 (keeps the domain self-contained per `CLAUDE.md` §2.1, rather than reaching across domains for a two-line helper):

```python
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
```

---

## 5. Service logic (`backend/src/inventory/service.py`)

### 5.1 `receive_purchase_order_line(db, payload: StockLotReceiveCreate) -> StockLot`

Validation order (fail fast, cheapest checks first — matches `purchasing.service.create_purchase_order`'s shape):

1. **Line exists**: `line = await db.get(PurchaseOrderLine, payload.purchase_order_line_id)`; `None` → `PurchaseOrderLineNotFound`.
2. **Line is allocated**: `line.landed_cost_pkr is None` → `LineNotAllocated` — it hasn't been attached to a cargo shipment yet, so there's no cost to snapshot.
3. **Not already received**: `existing = await db.scalar(select(StockLot).where(StockLot.purchase_order_line_id == line.id))`; if found → `LineAlreadyReceived`. (The DB-level `unique=True` from §2.1/§3.1 is the actual backstop against a race — same belt-and-suspenders shape `cargo`'s `unique` constraint on `cargo_allocation.purchase_order_line_id` provides underneath its own pre-check.)
4. **Insert the lot**:
   ```python
   lot = StockLot(
       purchase_order_line_id=line.id,
       item_id=line.item_id,
       qty_received=line.qty,
       qty_remaining=line.qty,
       landed_cost_pkr=line.landed_cost_pkr,
       received_date=payload.received_date,
   )
   db.add(lot)
   await db.flush()  # assigns lot.id, needed by the movement + ledger rows below
   ```
5. **Log the receipt as a `StockMovement`** and **post the ledger entry**, both in the same transaction as the lot insert:
   ```python
   db.add(StockMovement(
       stock_lot_id=lot.id,
       movement_type="receipt",
       qty_delta=lot.qty_received,
       reason=None,
       movement_date=payload.received_date,
   ))

   await ledger_service.post_entry(
       db,
       entry_date=payload.received_date,
       account="Inventory",
       debit=money(lot.qty_received * lot.landed_cost_pkr),
       reference_type="stock_lot",
       reference_id=lot.id,
   )
   ```
6. **Flip the PO's status if this was its last unreceived line** (§2.2) — one query, using the fact that `lot` is already flushed and therefore visible to it within the same transaction:
   ```python
   unreceived_count = await db.scalar(
       select(func.count())
       .select_from(PurchaseOrderLine)
       .outerjoin(StockLot, StockLot.purchase_order_line_id == PurchaseOrderLine.id)
       .where(PurchaseOrderLine.purchase_order_id == line.purchase_order_id, StockLot.id.is_(None))
   )
   if unreceived_count == 0:
       po = await db.get(PurchaseOrder, line.purchase_order_id)
       po.status = "received"
   ```
7. **Commit**: `try: await db.commit() except IntegrityError: await db.rollback(); raise ConflictException(...)` — same shape as every existing transactional service function. `await db.refresh(lot)` and return.

### 5.2 `create_adjustment(db, payload: StockMovementCreate) -> StockMovement`

1. `lot = await db.get(StockLot, payload.stock_lot_id)`; `None` → `StockLotNotFound`.
2. `payload.qty_delta == 0` → `InvalidAdjustment("Adjustment quantity must be non-zero")`.
3. Bounds check: `new_remaining = lot.qty_remaining + payload.qty_delta`; if `new_remaining < 0 or new_remaining > lot.qty_received` → `InvalidAdjustment(...)` naming the resulting value and the valid range. The upper bound matters as much as the lower one: a lot can never legitimately hold more units than it was ever received with — "recount found extra stock nobody remembers ordering" is a new-lot/new-receiving problem, not a correction to an existing one (see §9).
4. `lot.qty_remaining = new_remaining`; insert one `StockMovement(movement_type="adjustment", qty_delta=payload.qty_delta, reason=payload.reason, movement_date=payload.movement_date)`.
5. Commit with the same `IntegrityError` → `ConflictException` shape; refresh and return the movement (not the lot — the caller already has the lot's prior state and can re-fetch `GET /inventory/stock-lots/{id}` if it needs the new `qty_remaining`).

### 5.3 `list_stock_lots(db, pagination, item_id: int | None, include_depleted: bool) -> PaginatedResponse[StockLotRead]`

Same paginated shape as every other domain's list function. Filters:
- `item_id` (optional) — `WHERE item_id = :item_id` when given.
- `include_depleted` (default `False`) — when `False`, adds `WHERE qty_remaining > 0`, so a routine stock view doesn't have to scroll past fully-consumed lots; `True` surfaces the full history for anyone auditing.

Ordered by `(item_id, received_date, id)` — oldest lot first, per item. This ordering isn't just for display ("old stock next to new stock," per `PLAN.md`'s "done when") — it's the exact order Phase 4's FIFO consumption will need to walk lots in, so this function's `WHERE`/`ORDER BY` shape is written to be callable directly from a future `sales/service.py`, not just from this phase's own router.

### 5.4 `list_stock_movements(db, pagination, stock_lot_id: int | None) -> PaginatedResponse[StockMovementRead]`

Same shape, filtered by `stock_lot_id` when given, ordered by `id` — this is the audit-trail view for one lot (or, unfiltered, for everything).

### 5.5 `dependencies.py` — `valid_stock_lot`

```python
async def valid_stock_lot(stock_lot_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> StockLot:
    lot = await db.get(StockLot, stock_lot_id)
    if not lot:
        raise StockLotNotFound()
    return lot
```

Plain `db.get()` is fine here (unlike `valid_purchase_order`/`valid_cargo_shipment`) because `StockLot` has no relationship attributes to eager-load yet (§3.1) — there's no `lazy="raise"` trap to fall into.

### 5.6 `inventory/exceptions.py`

```python
from src.exceptions import AppException, ConflictException, NotFoundException


class PurchaseOrderLineNotFound(NotFoundException):
    detail = "Purchase order line not found"


class LineNotAllocated(AppException):
    status_code = 422
    detail = "This line has no landed cost yet — attach it to a cargo shipment before receiving"


class LineAlreadyReceived(ConflictException):
    detail = "This purchase order line has already been received into a stock lot"


class StockLotNotFound(NotFoundException):
    detail = "Stock lot not found"


class InvalidAdjustment(AppException):
    status_code = 422
    detail = "Adjustment is invalid"
```

---

## 6. API surface (`backend/src/inventory/router.py`)

| Method | Path | Backing | Notes |
|---|---|---|---|
| POST | `/inventory/stock-lots` | `service.receive_purchase_order_line` | 201 — this *is* the "Receive" action |
| GET | `/inventory/stock-lots` | `service.list_stock_lots` | paginated; query params `item_id`, `include_depleted` |
| GET | `/inventory/stock-lots/{id}` | `Depends(valid_stock_lot)` | |
| POST | `/inventory/stock-movements` | `service.create_adjustment` | 201 — the manual adjustment screen |
| GET | `/inventory/stock-movements` | `service.list_stock_movements` | paginated; query param `stock_lot_id` |

No `PUT`/`DELETE` on either resource — matches the `PurchaseOrder`/`CargoShipment` precedent of create + list + get only for hand-written transactional entities (§9). Structured like `cargo/router.py`: two hand-written `APIRouter(prefix=..., tags=["inventory"])` sub-routers, combined under a bare `router = APIRouter()` that `main.py` mounts at `/inventory`. Nothing here goes through `build_crud_router` — both `StockLot` and `StockMovement` are transactional (need cross-table validation and, for `StockLot`, a ledger post), exactly the case `PLAN.md`'s own rule reserves for hand-written services, and neither model even carries the `is_active` column the generic factory asserts on (§3.1).

```python
# backend/src/inventory/router.py
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.inventory import service
from src.inventory.dependencies import valid_stock_lot
from src.inventory.models import StockLot
from src.inventory.schemas import (
    StockLotRead,
    StockLotReceiveCreate,
    StockMovementCreate,
    StockMovementRead,
)
from src.pagination import PaginatedResponse, PaginationParams

stock_lot_router = APIRouter(prefix="/stock-lots", tags=["inventory"])


@stock_lot_router.post("", response_model=StockLotRead, status_code=201)
async def receive_line(
    payload: StockLotReceiveCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.receive_purchase_order_line(db, payload)


@stock_lot_router.get("", response_model=PaginatedResponse[StockLotRead])
async def list_stock_lots(
    pagination: Annotated[PaginationParams, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    item_id: int | None = None,
    include_depleted: bool = False,
):
    return await service.list_stock_lots(db, pagination, item_id, include_depleted)


@stock_lot_router.get("/{stock_lot_id}", response_model=StockLotRead)
async def get_stock_lot(
    lot: Annotated[StockLot, Depends(valid_stock_lot)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return lot


stock_movement_router = APIRouter(prefix="/stock-movements", tags=["inventory"])


@stock_movement_router.post("", response_model=StockMovementRead, status_code=201)
async def create_adjustment(
    payload: StockMovementCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.create_adjustment(db, payload)


@stock_movement_router.get("", response_model=PaginatedResponse[StockMovementRead])
async def list_stock_movements(
    pagination: Annotated[PaginationParams, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    stock_lot_id: int | None = None,
):
    return await service.list_stock_movements(db, pagination, stock_lot_id)


router = APIRouter()
router.include_router(stock_lot_router)
router.include_router(stock_movement_router)
```

### 6.1 `main.py`

```python
from src.inventory.router import router as inventory_router
...
app.include_router(inventory_router, prefix="/inventory")
```

(Sub-routers already carry `tags=["inventory"]`, same comment pattern already used for `purchasing_router`/`payments_router`/`catalog_router`.)

### 6.2 What the frontend's "Receive" and stock-view screens compose from, without a new endpoint

Two things `PLAN.md` asks for don't get a dedicated backend endpoint, on purpose:

- **"Which lines are waiting to be received"**: the frontend's Receive screen reconciles `GET /purchasing/purchase-orders` (or a single PO's detail, already returning `lines[].landed_cost_pkr`) against `GET /inventory/stock-lots` (already-received line ids, via `purchase_order_line_id`) — a receivable line is one with `landed_cost_pkr != null` and no matching stock lot. This is ordinary container-level composition (`CLAUDE.md` §3.4's "container ... composes the domain components"), not a gap. Adding a `received: bool` field to `PurchaseOrderLineRead` was considered and rejected — it would make `purchasing/schemas.py` depend on `inventory`, breaking the one-way shape §3.4 establishes.
- **"Stock view grouped by Model → Item"**: `GET /inventory/stock-lots?item_id=...` returns every lot for one item; grouping lots under their `Model`/`Category` is a display concern the frontend's `StockLotTable` component already owns per `CLAUDE.md` §3.3 ("model-wise, old lot vs new lot side by side") — it has `Category`/`Model`/`Item` already available via `catalogHooks`. No aggregate "on-hand by model" endpoint is added this phase; see §9 for why, and what would change that call.

---

## 7. Migration

One Alembic revision, `alembic revision --autogenerate`, reviewed by eye (`CLAUDE.md` §2.5). Expected diff:

- `CREATE TABLE stock_lot` (`id`, `purchase_order_line_id` FK unique, `item_id` FK, `qty_received` `Numeric(10,2)`, `qty_remaining` `Numeric(10,2)`, `landed_cost_pkr` `Numeric(12,2)`, `received_date`, `created_at`)
- `CREATE TABLE stock_movement` (`id`, `stock_lot_id` FK, `movement_type`, `qty_delta` `Numeric(10,2)`, `reason` nullable, `movement_date`, `created_at`)

No `ALTER TABLE` on any existing table — §2.1 deliberately avoided that. File name: `2026-08-08_add_inventory.py` (or the actual implementation date, date-prefixed per `CLAUDE.md` §2.1) — one migration for the whole phase, matching Phase 1/2's precedent of one file per phase, not per table.

---

## 8. Seed data (`backend/scripts/seed.py`)

**No changes.** `StockLot`/`StockMovement` are transactional records produced by using the app (receiving a real PO line, recording a real adjustment) — the same reason `scripts/seed.py` never seeds a `PurchaseOrder` or `CargoShipment` today, only the dynamic lookups those domains depend on (`ExchangeRate`, `CargoMode`, `CargoCostBasis`). Phase 3 introduces no new lookup table, so there's nothing for this script to grow.

---

## 9. Out of scope / open questions for later

- **No re-receiving or undo.** Once `receive_purchase_order_line` succeeds, there's no endpoint to un-receive a line (e.g., it was received against the wrong `received_date` by mistake). Matches `PurchaseOrder`/`CargoShipment`'s existing precedent of no delete/undo on a completed transactional action — deliberately deferred rather than rushed in.
- **No partial receiving.** A line is received for its full `qty` or not at all (§2.3). If the business hits a real short-shipment case, this reopens both §2.1 (the unique-FK-as-receipt-marker design) and §2.3 together — it's not a small patch on top of this design, it's a different one.
- **Manual adjustments never touch the ledger** (§2.4). A damage/loss write-off is a real value change that arguably belongs in the books; this phase treats it as a physical-count correction only, on the theory that turning it into money is Phase 7's (`Expense`) job, referencing `StockMovement`, once that domain exists. Revisit if the business needs inventory shrinkage visible in a balance statement before Phase 7 ships.
- **Cargo's ledger gap (Phase 2) is inherited, not fixed here.** `cargo/service.py` never books a payable to the cargo agent for freight cost — it only mutates `PurchaseOrderLine.landed_cost_pkr`. Phase 3's "Inventory" debit uses that same `landed_cost_pkr`, so the *value* moving into inventory is correct, but the corresponding liability side was never booked anywhere. The ledger's total debits and credits will not tie out across `Accounts Payable` + `Inventory` until that gap is closed — worth a deliberate decision in a future phase (most naturally Phase 2's own domain, retroactively, or Phase 6/Payments when cargo-agent payments start flowing), not something to silently paper over here.
- **No aggregate "on-hand by item/model" endpoint.** `GET /inventory/stock-lots?item_id=...` gives every lot for an item; summing `qty_remaining` across a model's items is left to the frontend (which already has the full lot list for anything it's displaying) rather than adding a `GROUP BY` endpoint with no confirmed second caller yet. If Phase 4's FIFO consumption or Phase 8's fast/slow-mover analytics need a server-side aggregate instead of walking lots themselves, that's the moment to add it — not preemptively now.
- **Adjustment range is capped at `[0, qty_received]`** (§5.2 step 3) — a recount that finds *more* stock than a lot ever received is treated as out of scope for this endpoint (it would mean either a data-entry error somewhere upstream or genuinely new, unordered stock, which is a new-lot problem, not a correction to an old one). No workaround endpoint is provided for that case in this phase.

---

## 10. Implementation checklist

New:
- `backend/src/inventory/__init__.py`
- `backend/src/inventory/models.py` — `StockLot`, `StockMovement`
- `backend/src/inventory/schemas.py`
- `backend/src/inventory/constants.py`
- `backend/src/inventory/exceptions.py`
- `backend/src/inventory/dependencies.py`
- `backend/src/inventory/service.py`
- `backend/src/inventory/utils.py`
- `backend/src/inventory/router.py`
- `backend/migrations/versions/<date>_add_inventory.py`

Changed:
- `backend/src/purchasing/constants.py` — widen `PurchaseOrderStatus` to include `"received"`
- `backend/src/main.py` — mount `inventory_router`
