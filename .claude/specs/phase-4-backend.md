# Phase 4 Backend Spec — Wholesale Sales

Governed by `PLAN.md` (what) and `CLAUDE.md` (how). This document is the missing middle layer: the exact entities, endpoints, and service logic to implement Phase 4 inside `backend/src/sales/`, plus the additions this phase requires to `parties/` and `inventory/`, consistent with what Phases 0–3 already built. Nothing here overrides `CLAUDE.md`'s conventions — every choice below either follows an existing precedent in the codebase (cited by file) or is flagged explicitly as a new decision this phase introduces.

**Done when** (from `PLAN.md`): you can invoice a customer, see stock drop, and pull up that party's full history and current balance on one screen.

---

## 1. Where we stand

Confirmed by reading the actual code, not assumed:

- **`customer` already exists as a `PartyRole`** (`parties/constants.py`) — nothing to add there. `parties/service.py` already has both halves Phase 4 needs: `get_active_party(db, party_id)` (fetch-or-404) and `ensure_role(party, role)` (raises `PartyRoleMismatch` if the role isn't held). `parties/dependencies.py` has a `valid_china_vendor` role-check dependency that's currently **unused**, with a comment explaining why: `purchasing.service.create_purchase_order` needs `party_id` from a request body, not a path param, so it calls `get_active_party` + `ensure_role` inline instead of through a dependency. Phase 4's `SalesOrderCreate.party_id` is the same shape (a body field) — `sales/service.py` follows the same inline-call precedent, not a new dependency.
- **No balance/statement code exists anywhere.** `parties/router.py` only has `list`/`create`/`get`/`update`/`delete`. There is no `/parties/{id}/statement` route and no `ledger/router.py` at all — `ledger` is currently write-only-into. Building the party statement is entirely new work this phase (§5.5, §6).
- **No FIFO logic exists anywhere.** `inventory/constants.py` currently has `StockMovementType = Literal["receipt", "adjustment"]`, with a comment already anticipating this phase: *"'sale' gets added here in Phase 4, when FIFO consumption becomes a third kind of qty_remaining-moving event."* The only existing `qty_remaining`-mutating code is `create_adjustment` (Phase 3), and it takes an **explicit** `stock_lot_id` from the caller — it does not search across an item's lots, so it's not a FIFO template, only a template for "decrement `qty_remaining` + write a `StockMovement`" mechanics. `StockLot` already carries everything Phase 4 needs to read: `item_id`, `qty_remaining`, `landed_cost_pkr` (immutable per-unit cost, snapshotted once at receive time).
- **`ledger_service.post_entry`** signature, confirmed from code (`ledger/service.py`):
  ```python
  async def post_entry(
      db: AsyncSession, *, entry_date: date, account: str,
      reference_type: str, reference_id: int,
      debit: Decimal = Decimal(0), credit: Decimal = Decimal(0),
      party_id: int | None = None,
  ) -> LedgerEntry
  ```
  It does not flush or commit — the caller owns the transaction, exactly the shape Phase 4's `sales/service.py` plugs into.
- **`purchasing/` is the closest analog** — a transactional entity with lines, a party, and money. Its `create_purchase_order` shape (inline party-role check → batch-validate item ids → build lines in Python with a computed-field-matching formula → attach via ORM relationship → flush for id → post ledger entry → commit with `IntegrityError → ConflictException`) is the template Phase 4's `create_sales_order` follows directly (§5.1).
- **`catalog.Item` has no price field at all** (`id, category_id, model_id, sku, variant, is_active`) — sale rate is purely entered per `SalesOrderLine`, same as `rate_rmb` is purely entered per `PurchaseOrderLine`. Nothing to read from `catalog` beyond validating the item exists and is active.
- **`src/crud.py`'s generic factory is unusable here** — same reasoning `purchasing`/`cargo`/`parties` are already carved out for: cross-table logic (FIFO consumption, a ledger post) that a bare `model(**payload.model_dump())` insert can't do, and neither `SalesOrder` nor `SalesOrderLine` will carry an `is_active` column the factory asserts on (matching `PurchaseOrder`/`CargoShipment`/`StockLot`, none of which have one either — see the last bullet below).
- **No `sales_order`/`sales_order_line` migration exists** — clean slate on the DB side, confirmed against `migrations/versions/` (four files, most recent `2026-08-08_add_inventory.py`; nothing later).
- **`scripts/seed.py` seeds no `customer`-role party and no stock at all** (no PO, no shipment, no `StockLot`). Manual testing of this phase requires building a full chain by hand first (customer party → PO → cargo shipment → receive) — see §8.
- **Three repo-wide deviations from `CLAUDE.md`'s literal text, established by every existing domain, that Phase 4 must follow (not "fix"):**
  1. **No `async with session.begin()` anywhere.** Every transactional service uses `db.add(...)` → `await db.flush()` (when an id is needed downstream) → more mutation → `try: await db.commit() except IntegrityError: await db.rollback(); raise ConflictException(...)`. `sales/service.py` follows this exact manual pattern.
  2. **Exception translation is centralized**, not per-router. Domain exceptions subclass `AppException`/`NotFoundException`/`ConflictException` from `src/exceptions.py`; a single `@app.exception_handler(AppException)` in `main.py` converts them to JSON. `sales/exceptions.py` needs nothing beyond the exception classes themselves — no per-router try/except.
  3. **`money()` is duplicated per domain** (`purchasing/utils.py`, `cargo/utils.py`, `inventory/utils.py`, byte-identical), not shared from `src/`. `sales/utils.py` gets its own copy, for the same "self-contained package" reason (`CLAUDE.md` §2.1).
  4. (Not a deviation, but a load-bearing precedent:) **hand-written transactional entities carry no `is_active` and no update/delete endpoint** — `PurchaseOrder`, `CargoShipment`, `StockLot` are all create + list + get only. `SalesOrder`/`SalesOrderLine` follow suit (§9).

---

## 2. Design decisions

Decisions this spec makes that `PLAN.md` doesn't spell out, recorded here so they're reviewed once rather than re-derived mid-implementation.

### 2.1 A new join table, `SalesOrderLineLot`, records which lots each line actually drew from

`PLAN.md`'s Phase 4 entity list names only `Party(customer)`, `SalesOrder`, `SalesOrderLine` — but it also requires "the line shows margin against the lot(s) it drew from," which a `SalesOrderLine` with only `qty`/`rate_pkr` columns cannot express once a line's qty spans more than one lot. A new table is needed the same way Phase 2 needed `CargoAllocation` beyond a bare `PurchaseOrder`/`PurchaseOrderLine` pair, for the same reason: a single line's cost is a many-to-something relationship, not a scalar.

`SalesOrderLineLot` belongs in `sales/` (not `inventory/`), mirroring exactly where `CargoAllocation` lives relative to `purchasing`/`cargo`: the *action* that produces the row (invoicing) is a sales concern, even though one of its two foreign keys points at another domain's table. `unit_cost_pkr` is stored redundantly on this row rather than looked up live from `StockLot.landed_cost_pkr` at read time — this is the same denormalization rationale already used for `StockLot.item_id` ("lets every inventory query filter by item without joining through purchasing"): it lets `sales/` compute a line's cost and margin from its own tables, without joining back into `inventory` for every statement/report read. Since `StockLot.landed_cost_pkr` is immutable after receipt (Phase 3 §2.3), the copy can never drift from its source.

### 2.2 Margin is computed, not stored — `SalesOrderLine` carries no `cost_pkr`/`margin_pkr` column

Mirrors `purchasing/schemas.py`'s existing pattern exactly: `PurchaseOrderLineRead.amount_pkr`/`amount_landed_pkr` are `@computed_field` properties derived from the line's own stored columns, never persisted redundantly. Here, `SalesOrderLineRead.cost_pkr` is a `@computed_field` that sums `qty_consumed * unit_cost_pkr` across the line's loaded `SalesOrderLineLot` rows (§4.1) — the underlying `unit_cost_pkr`/`qty_consumed` values are the immutable snapshot (§2.1), so recomputing on read is exactly as safe as `purchasing` recomputing `amount_pkr = qty * rate_pkr` on read. `margin_pkr = amount_pkr - cost_pkr`, same computed-field shape.

The one place this must be computed **eagerly in Python**, not read off the response schema, is inside `service.create_sales_order` itself — the ledger credit for the whole order needs `total_pkr` before anything is serialized. That total is built with the *identical* `money(qty * rate_pkr)` formula the schema's `amount_pkr` uses, summed per line — the same "intentional so the response total and the ledger entry never disagree" rule `purchasing.service.create_purchase_order` already documents in its own code comment.

### 2.3 Each item may appear at most once per sales order

If a customer needs more of an item, the line's `qty` goes up — it doesn't become a second line for the same `item_id`. This is a deliberate simplification: without it, two lines for the same item would need to agree on which contiguous slice of that item's FIFO queue each one draws from (line 1 takes the front, line 2 continues where line 1 left off), which is real complexity `PLAN.md` never asks for and no real invoice needs. `sales/service.py` validates this the same way it validates item existence — one batch check, `InvalidSalesOrderItem` on the first violation found (duplicate id or missing/inactive id, same exception, distinct messages).

Because of this, each line's FIFO draw is independent of every other line in the same order — `create_sales_order` can process lines one at a time in a simple loop, matching the simplicity of `purchasing.service.create_purchase_order`'s per-line loop.

### 2.4 FIFO consumption lives in `inventory/service.py`, not `sales/service.py`

`inventory/` already owns every mutation of `StockLot.qty_remaining` and every `StockMovement` insert (`receive_purchase_order_line`, `create_adjustment` — Phase 3). Phase 4 adds a third: `inventory.service.consume_stock_fifo(db, *, item_id, qty_needed, movement_date) -> list[FifoConsumption]`. `sales/service.py` calls this rather than querying/mutating `StockLot` directly, keeping `inventory/` the sole owner of its own tables' write paths — the same shape `cargo/` established toward `purchasing` (one-way dependency, but here expressed as a service-function call rather than a direct column write, because `inventory` already has the multi-step bookkeeping — lot selection, movement logging — encapsulated, and a second domain reaching in to duplicate that logic would be the actual violation).

This is the first new one-way edge in the dependency graph this phase adds: `sales/` → `parties/`, `sales/` → `catalog/` (read-only item validation), `sales/` → `inventory/` (via `consume_stock_fifo`), `sales/` → `ledger/`. `inventory/` does not import `sales/`. `parties/` gains a read-only edge to `ledger/` for the statement query (§2.6) — `ledger/` still imports nothing, preserving the rule that every other domain may import *into* it but it never imports back.

Signature and internals:
```python
@dataclass(frozen=True)
class FifoConsumption:
    stock_lot_id: int
    qty_consumed: Decimal
    unit_cost_pkr: Decimal
```
1. Lock and read every lot with stock for this item, oldest first — the same ordering `list_stock_lots` already uses, now under `.with_for_update()`:
   ```python
   lots = (await db.scalars(
       select(StockLot)
       .where(StockLot.item_id == item_id, StockLot.qty_remaining > 0)
       .order_by(StockLot.received_date, StockLot.id)
       .with_for_update()
   )).all()
   ```
2. **Check sufficiency before mutating anything**: `if sum(l.qty_remaining for l in lots) < qty_needed: raise InsufficientStock(item_id, needed=qty_needed, available=...)`. Checking up front (rather than decrementing greedily and unwinding on shortfall) means a failed line never leaves a partial decrement for this item to reason about, even though the enclosing `create_sales_order` transaction would also safely roll the partial state back on any exception (§2.5) — this is belt-and-suspenders, matching the codebase's general preference for fail-fast validation before mutation (`purchasing`'s item-existence check runs entirely before any `PurchaseOrderLine` is built, for the same reason).
3. Walk `lots` in order, consuming `min(remaining_needed, lot.qty_remaining)` from each: decrement `lot.qty_remaining`, insert one `StockMovement(stock_lot_id=lot.id, movement_type="sale", qty_delta=-consumed, reason=None, movement_date=movement_date)` (reason stays `NULL` for `"sale"` movements, same as `"receipt"` — only `"adjustment"` rows require one, per Phase 3 §3.1), and append a `FifoConsumption(lot.id, consumed, lot.landed_cost_pkr)` to the result list.
4. Return the list. No commit, no flush required by this function's own logic (callers that need ids from earlier work must flush themselves, same as every other service function's convention — `post_entry` behaves identically).

This is the first row-locking (`with_for_update`) call anywhere in the codebase. It's introduced here specifically because this is the first place a service function reads a *set* of rows and then mutates based on their aggregate value (`SUM(qty_remaining) >= qty_needed`) — every earlier mutation (`receive_purchase_order_line`, `create_adjustment`) acts on one already-identified row fetched by primary key, where there's nothing to race against. Two concurrent sales against the same low-stock item is exactly the scenario this guards against, even in a single-user system: one browser tab and one API script hitting the same endpoint at once is still two connections.

### 2.5 `create_sales_order` fails atomically — a mid-order shortfall unwinds everything, not just its own line

Because `db.commit()` is called exactly once, at the end, an `InsufficientStock` raised while processing line 3 of 5 propagates up through `sales/router.py` to the global `AppException` handler without ever reaching `commit()`. `get_db`'s `async with SessionLocal() as session: yield session` closes the session on the way out, and `AsyncSession.close()` implicitly rolls back any open transaction — so lines 1–2's already-flushed `StockLot`/`StockMovement` mutations are undone along with everything else. No explicit `try/except` + manual rollback is needed around the per-line loop itself; only the final commit needs the existing `except IntegrityError` shape every other domain already uses.

### 2.6 The party statement is new work in `parties/`, not a new `ledger/router.py`

`PLAN.md`'s Architecture Decisions (`The ledger`) are explicit: "there is no separate party ledger table; a party's balance is just `LedgerEntry` filtered by `party_id`." The natural home for that read is next to the entity it's about — `parties/service.py` gains `get_party_statement(db, party: Party) -> PartyStatementRead`, reading `ledger.models.LedgerEntry` directly (a new one-way `parties → ledger` import; `ledger` still imports nothing). A generic `ledger/router.py` isn't added — nothing else needs to list ledger entries yet, and adding one on spec with no second caller repeats the mistake the Phase 3 spec explicitly declined to make with an "on-hand by model" aggregate endpoint (see that document's §9).

The statement reuses the existing `valid_party` path-param dependency (`parties/dependencies.py`) rather than `get_active_party` — this endpoint's `party_id` is a path param, the exact case `valid_party` already exists for.

Balance sign convention: every ledger row's `debit - credit`, summed and added to `party.opening_balance`, gives a signed balance where **positive means the party owes the business** (a net receivable) and negative means the business owes the party (a net payable) — one uniform formula regardless of which role(s) the party holds, since `purchasing.service.create_purchase_order` already credits "Accounts Payable" (liability increases via credit) and this phase's sales entry debits "Accounts Receivable" (asset increases via debit) using the same convention (§3.4). The statement itself is returned unpaginated — a single customer's full history is not expected to be large enough in this business to need pagination yet; if it becomes one, that's the moment to add it, not before (§9).

### 2.7 No `SalesOrder.status`, no update/delete endpoint

Unlike `PurchaseOrder`, a sales order has no intermediate lifecycle in this phase — there's no cargo/exchange-rate step between "created" and "final." Creating one is a single atomic action (validate → consume stock → post ledger → commit), so there's nothing for a status column to track. This also means no undo/void endpoint exists this phase, matching the exact precedent Phase 3's spec set for `receive_purchase_order_line` ("no re-receiving or undo") — flagged again in §9 rather than silently omitted.

---

## 3. Data model

### 3.1 New tables (`backend/src/sales/models.py`)

**`sales_order`** — hand-written, transactional, no `is_active`, no delete endpoint (§2.7).

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `party_id` | FK → `party.id`, indexed | validated as an active party holding the `customer` role (§5.1 step 1) |
| `order_date` | `Date` | |
| `created_at` | `DateTime(timezone=True)`, `server_default=func.now()` | |

**`sales_order_line`** — no `is_active`; deleted only via `SalesOrder`'s `cascade="all, delete-orphan"` if the parent were ever deleted (it never is this phase — see §9).

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `sales_order_id` | FK → `sales_order.id`, indexed | |
| `item_id` | FK → `item.id`, indexed | |
| `qty` | `Numeric(10, 2)` | |
| `rate_pkr` | `Numeric(12, 2)` | entered directly by the user — no exchange-rate snapshot needed, unlike `purchasing`; wholesale sales are quoted in PKR to begin with |

No `cost_pkr` column — computed from `consumptions` at read time (§2.2).

**`sales_order_line_lot`** — append-only join table (§2.1), same shape as `cargo_allocation`/`stock_movement`: no `is_active`, no update/delete endpoint, ever.

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `sales_order_line_id` | FK → `sales_order_line.id`, indexed | |
| `stock_lot_id` | FK → `stock_lot.id`, indexed | plain FK, not unique — one lot can supply many lines across many orders, and (in principle) a large line could draw from several lots |
| `qty_consumed` | `Numeric(10, 2)` | |
| `unit_cost_pkr` | `Numeric(12, 2)` | snapshot of `StockLot.landed_cost_pkr` at the moment of sale (§2.1) |
| `created_at` | `DateTime(timezone=True)`, `server_default=func.now()` | |

```python
# backend/src/sales/models.py
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class SalesOrder(Base):
    __tablename__ = "sales_order"

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"), index=True)
    order_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lines: Mapped[list["SalesOrderLine"]] = relationship(
        lazy="raise", cascade="all, delete-orphan"
    )


class SalesOrderLine(Base):
    __tablename__ = "sales_order_line"

    id: Mapped[int] = mapped_column(primary_key=True)
    sales_order_id: Mapped[int] = mapped_column(ForeignKey("sales_order.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), index=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    rate_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    consumptions: Mapped[list["SalesOrderLineLot"]] = relationship(
        lazy="raise", cascade="all, delete-orphan"
    )


class SalesOrderLineLot(Base):
    __tablename__ = "sales_order_line_lot"

    id: Mapped[int] = mapped_column(primary_key=True)
    sales_order_line_id: Mapped[int] = mapped_column(ForeignKey("sales_order_line.id"), index=True)
    stock_lot_id: Mapped[int] = mapped_column(ForeignKey("stock_lot.id"), index=True)
    qty_consumed: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit_cost_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

`lines`/`consumptions` use `lazy="raise"` + eager `selectinload` at the query site, matching `PurchaseOrder.lines`/`CargoShipment.allocations` exactly — both response schemas need the nested data, so a relationship earns its keep here (unlike `StockLot`/`StockMovement` in Phase 3, which had no relationships at all).

### 3.2 Changed constant: `inventory/constants.py`

```python
from typing import Literal

StockMovementType = Literal["receipt", "adjustment", "sale"]
```

Plain `str` column underneath (Phase 3 §3.1) — no migration needed for this widening, same as Phase 3 widening `PurchaseOrderStatus` needed none.

### 3.3 `sales/constants.py` — not created

No enums or literals are needed for this domain (no status field, no lookup-style constant) — mirrors `catalog/`'s precedent of omitting the file entirely rather than shipping an empty one.

### 3.4 Directional dependency this phase establishes

```
catalog/  parties/  ledger/
   ▲         ▲         ▲
   │         │         │
   └─────────┴── sales/ ── inventory/
                              ▲
                              │
                          purchasing/ ◄── cargo/
```
`sales/` imports `parties.service` (`get_active_party`, `ensure_role`), `parties.constants.PartyRole`, `catalog.models.Item` (read-only existence check), `inventory.service.consume_stock_fifo`, `inventory.exceptions.InsufficientStock`, and `ledger.service.post_entry`. `parties/` gains one new import, `ledger.models.LedgerEntry`, for the statement query. Nothing downstream (`ledger/`, `catalog/`, `inventory/`, `parties/`) imports `sales/` — the DAG stays acyclic, same principle Phase 2/3 each preserved when they added their own edges.

---

## 4. Pydantic schemas

### 4.1 `backend/src/sales/schemas.py`

```python
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field

from src.sales.utils import money


class SalesOrderLineCreate(BaseModel):
    item_id: int
    qty: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    rate_pkr: Annotated[Decimal, Field(gt=0, decimal_places=2)]


class SalesOrderCreate(BaseModel):
    party_id: int
    order_date: date
    lines: Annotated[list[SalesOrderLineCreate], Field(min_length=1)]


class SalesOrderLineLotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stock_lot_id: int
    qty_consumed: Decimal
    unit_cost_pkr: Decimal


class SalesOrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    qty: Decimal
    rate_pkr: Decimal
    consumptions: list[SalesOrderLineLotRead]

    @computed_field
    @property
    def amount_pkr(self) -> Decimal:
        return money(self.qty * self.rate_pkr)

    @computed_field
    @property
    def cost_pkr(self) -> Decimal:
        return money(sum((c.qty_consumed * c.unit_cost_pkr for c in self.consumptions), Decimal(0)))

    @computed_field
    @property
    def margin_pkr(self) -> Decimal:
        return money(self.amount_pkr - self.cost_pkr)


class SalesOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    party_id: int
    order_date: date
    created_at: datetime
    lines: list[SalesOrderLineRead]

    @computed_field
    @property
    def total_pkr(self) -> Decimal:
        return money(sum((line.amount_pkr for line in self.lines), Decimal(0)))

    @computed_field
    @property
    def total_margin_pkr(self) -> Decimal:
        return money(sum((line.margin_pkr for line in self.lines), Decimal(0)))
```

No `SalesOrderUpdate` — create + list + get only (§2.7, §9).

### 4.2 `backend/src/sales/utils.py`

Byte-identical to `purchasing/utils.py`/`cargo/utils.py`/`inventory/utils.py` (§1, deviation 3):

```python
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
```

### 4.3 Additions to `backend/src/parties/schemas.py`

```python
class PartyStatementEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_date: date
    account: str
    debit: Decimal
    credit: Decimal
    reference_type: str | None
    reference_id: int | None
    running_balance: Decimal


class PartyStatementRead(BaseModel):
    party: PartyRead
    opening_balance: Decimal
    entries: list[PartyStatementEntryRead]
    closing_balance: Decimal
```

`running_balance` isn't a column on `LedgerEntry` — `PartyStatementEntryRead` rows are built with explicit keyword arguments in `service.get_party_statement` (§5.5), not via `.model_validate(ledger_row)` directly, since the running total is inherently cumulative across rows, not intrinsic to any one of them. `model_config` stays for consistency with every other `*Read` schema in the codebase even though this particular schema is never constructed via `from_attributes` in practice.

---

## 5. Service logic

### 5.1 `sales/service.py::create_sales_order(db, payload: SalesOrderCreate) -> SalesOrder`

Validation order mirrors `purchasing.service.create_purchase_order`'s shape exactly — cheapest, most decisive checks first, no mutation until everything about the *shape* of the order is known to be valid:

1. **Party is an active customer**: `party = await parties_service.get_active_party(db, payload.party_id)`; `await parties_service.ensure_role(party, PartyRole.CUSTOMER)` — raises `PartyNotFound`/`PartyRoleMismatch` (both already exist in `parties/exceptions.py`; no new exception needed here).
2. **No duplicate items, all items exist and are active** (§2.3): collect `item_id`s from `payload.lines`; if `len(set(ids)) != len(ids)`, raise `InvalidSalesOrderItem` naming the repeated id(s); otherwise batch-query `Item` for all ids with `is_active=True` and raise the same exception listing any missing/inactive ones — same batched-query shape `purchasing.service.create_purchase_order` already uses for its own item check.
3. **Per line, consume stock and build the line**:
   ```python
   lines: list[SalesOrderLine] = []
   total_pkr = Decimal(0)
   for line_in in payload.lines:
       consumptions = await inventory_service.consume_stock_fifo(
           db, item_id=line_in.item_id, qty_needed=line_in.qty, movement_date=payload.order_date,
       )
       line = SalesOrderLine(
           item_id=line_in.item_id,
           qty=line_in.qty,
           rate_pkr=line_in.rate_pkr,
           consumptions=[
               SalesOrderLineLot(
                   stock_lot_id=c.stock_lot_id,
                   qty_consumed=c.qty_consumed,
                   unit_cost_pkr=c.unit_cost_pkr,
               )
               for c in consumptions
           ],
       )
       lines.append(line)
       total_pkr += money(line_in.qty * line_in.rate_pkr)  # same formula SalesOrderLineRead.amount_pkr uses (§2.2)
   ```
   `consume_stock_fifo` raising `InsufficientStock` here propagates straight out — nothing has been added to the session yet for this order, and any lots it already mutated for an earlier line in this same loop unwind on rollback (§2.5).
4. **Attach lines via the ORM relationship**, not standalone inserts — `SalesOrder(party_id=party.id, order_date=payload.order_date, lines=lines)` — keeps `so.lines` populated post-commit under `expire_on_commit=False` without a lazy load, same reasoning `purchasing.service.create_purchase_order` documents for its own `lines=lines` construction.
5. `db.add(so)` → `await db.flush()` (assigns `so.id`, needed by the ledger post below).
6. **Post the ledger entry** — one row for the whole order, debiting the party's receivable (§2.6):
   ```python
   await ledger_service.post_entry(
       db,
       entry_date=payload.order_date,
       account="Accounts Receivable",
       debit=total_pkr,
       reference_type="sales_order",
       reference_id=so.id,
       party_id=party.id,
   )
   ```
7. **Commit**: `try: await db.commit() except IntegrityError: await db.rollback(); raise ConflictException(...)` — identical shape to every other transactional service function. `await db.refresh(so, attribute_names=["lines"])` (or re-fetch via the same `selectinload` the `get`/`list` paths use) and return.

### 5.2 `sales/service.py::list_sales_orders(db, pagination) -> PaginatedResponse[SalesOrderRead]`

Same paginated shape as every other domain's list function, ordered `(order_date desc, id desc)` — most recent invoice first, the natural default for a sales list screen. Eager-loads `.options(selectinload(SalesOrder.lines).selectinload(SalesOrderLine.consumptions))` so the nested `computed_field`s in `SalesOrderLineRead` never trigger a lazy load under `lazy="raise"`.

### 5.3 `sales/dependencies.py::valid_sales_order`

```python
async def valid_sales_order(sales_order_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> SalesOrder:
    so = await db.scalar(
        select(SalesOrder)
        .where(SalesOrder.id == sales_order_id)
        .options(selectinload(SalesOrder.lines).selectinload(SalesOrderLine.consumptions))
    )
    if not so:
        raise SalesOrderNotFound()
    return so
```
Uses `select(...).options(...)`, not `db.get()`, for the same reason `purchasing.dependencies.valid_purchase_order` does: `Session.get()` silently ignores loader options when serving from the identity map, which would intermittently reintroduce the `lazy="raise"` trap depending on what else touched this row earlier in the request.

### 5.4 `inventory/service.py::consume_stock_fifo` and `inventory/exceptions.py::InsufficientStock`

Full mechanics specified in §2.4. New exception:
```python
class InsufficientStock(AppException):
    status_code = 422

    def __init__(self, item_id: int, needed: Decimal, available: Decimal):
        super().__init__(
            f"Item {item_id}: need {needed}, only {available} in stock"
        )
```
(matches the existing `AppException.__init__(self, detail: str)` override pattern already used by `InvalidPurchaseOrderItem` to report specifics rather than a static message.)

### 5.5 `parties/service.py::get_party_statement(db, party: Party) -> PartyStatementRead`

```python
async def get_party_statement(db: AsyncSession, party: Party) -> PartyStatementRead:
    rows = (await db.scalars(
        select(LedgerEntry)
        .where(LedgerEntry.party_id == party.id)
        .order_by(LedgerEntry.entry_date, LedgerEntry.id)
    )).all()

    running = party.opening_balance
    entries = []
    for row in rows:
        running += row.debit - row.credit
        entries.append(PartyStatementEntryRead(
            id=row.id, entry_date=row.entry_date, account=row.account,
            debit=row.debit, credit=row.credit,
            reference_type=row.reference_type, reference_id=row.reference_id,
            running_balance=running,
        ))

    return PartyStatementRead(
        party=PartyRead.model_validate(party),
        opening_balance=party.opening_balance,
        entries=entries,
        closing_balance=running,
    )
```
Takes the already-fetched `Party` (from `valid_party`), not a bare `party_id` — avoids a second fetch, and matches the shape every other path-param-driven read endpoint in this codebase already uses (`get_stock_lot`, `get_purchase_order`, etc., all take the `Depends`-resolved object directly).

### 5.6 `sales/exceptions.py`

```python
from src.exceptions import AppException, NotFoundException


class SalesOrderNotFound(NotFoundException):
    detail = "Sales order not found"


class InvalidSalesOrderItem(AppException):
    status_code = 422
```
(`InvalidSalesOrderItem` takes a constructed detail string listing the offending id(s), same `__init__` override shape as `InventoryService`'s `InsufficientStock` and `purchasing`'s `InvalidPurchaseOrderItem`.) No `ConflictException` subclass is needed here beyond the shared one `purchasing`/`inventory` already reuse directly for the commit-time `IntegrityError` path.

---

## 6. API surface

### 6.1 `backend/src/sales/router.py`

| Method | Path | Backing | Notes |
|---|---|---|---|
| POST | `/sales/sales-orders` | `service.create_sales_order` | 201 — this *is* the invoice action |
| GET | `/sales/sales-orders` | `service.list_sales_orders` | paginated |
| GET | `/sales/sales-orders/{id}` | `Depends(valid_sales_order)` | |

No `PUT`/`DELETE` (§2.7, §9). One hand-written `APIRouter(prefix="/sales-orders", tags=["sales"])`, mounted at `/sales` from `main.py` — simpler than `inventory`'s two-sub-router composition since this phase has exactly one transactional resource (the join table has no endpoints of its own; it's only ever read nested inside a `SalesOrderRead`).

```python
# backend/src/sales/router.py
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.pagination import PaginatedResponse, PaginationParams
from src.sales import service
from src.sales.dependencies import valid_sales_order
from src.sales.models import SalesOrder
from src.sales.schemas import SalesOrderCreate, SalesOrderRead

router = APIRouter(prefix="/sales-orders", tags=["sales"])


@router.post("", response_model=SalesOrderRead, status_code=201)
async def create_sales_order(
    payload: SalesOrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.create_sales_order(db, payload)


@router.get("", response_model=PaginatedResponse[SalesOrderRead])
async def list_sales_orders(
    pagination: Annotated[PaginationParams, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.list_sales_orders(db, pagination)


@router.get("/{sales_order_id}", response_model=SalesOrderRead)
async def get_sales_order(
    sales_order: Annotated[SalesOrder, Depends(valid_sales_order)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return sales_order
```

### 6.2 Addition to `backend/src/parties/router.py`

```python
@router.get("/{party_id}/statement", response_model=PartyStatementRead)
async def get_party_statement(
    party: Annotated[Party, Depends(valid_party)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.get_party_statement(db, party)
```

### 6.3 `main.py`

```python
from src.sales.router import router as sales_router
...
app.include_router(sales_router, prefix="/sales")
```
(`parties_router` is already mounted from Phase 1 — the new statement route rides along on the existing include, no change needed there beyond the router file itself.)

---

## 7. Migration

One Alembic revision, `alembic revision --autogenerate`, reviewed by eye (`CLAUDE.md` §2.5). Expected diff:

- `CREATE TABLE sales_order` (`id`, `party_id` FK, `order_date`, `created_at`)
- `CREATE TABLE sales_order_line` (`id`, `sales_order_id` FK, `item_id` FK, `qty` `Numeric(10,2)`, `rate_pkr` `Numeric(12,2)`)
- `CREATE TABLE sales_order_line_lot` (`id`, `sales_order_line_id` FK, `stock_lot_id` FK, `qty_consumed` `Numeric(10,2)`, `unit_cost_pkr` `Numeric(12,2)`, `created_at`)

No `ALTER TABLE` on any existing table — `inventory.constants.StockMovementType`'s widening (§3.2) is a Python-only `Literal` change against an already-`str` column, same as Phase 3's `PurchaseOrderStatus` widening needed no migration. File name: `<date>_add_sales.py`, one migration for the whole phase, matching every prior phase's one-migration-per-phase precedent.

---

## 8. Seed data (`backend/scripts/seed.py`)

**No changes to the script itself** — `SalesOrder`/`SalesOrderLine`/`SalesOrderLineLot` are transactional records produced by using the app, the same reason `PurchaseOrder`/`CargoShipment`/`StockLot` are never seeded either (§1). What Phase 4 does need, which nothing seeds today, is at least one `StockLot` with `qty_remaining > 0` to sell against and at least one `customer`-role `Party` to sell to — neither exists out of the box.

Manual dev/testing setup, in order: run `scripts/seed.py` (gets `ExchangeRate`, `PaymentMethod`, `CargoMode`, `CargoCostBasis`, optionally a `china_vendor` via `--vendor-name`) → create a `customer`-role `Party` via `POST /parties` → create a `Category`/`Model`/`Item` → create a `PurchaseOrder` against the seeded vendor → create a `CargoShipment` attaching that PO's line(s) → `POST /inventory/stock-lots` to receive the line into a lot → only then is there anything for `POST /sales/sales-orders` to consume. This full chain is worth scripting into `seed.py` behind a flag (e.g. `--with-sample-stock`) if manual setup proves tedious during implementation, but isn't added speculatively here (§9).

---

## 9. Out of scope / open questions for later

- **No undo/void on a posted sale.** Once `create_sales_order` commits, there's no endpoint to reverse it — matches the exact precedent Phase 3 set for `receive_purchase_order_line`. If a sale needs correcting, today that means a manual `StockMovement` adjustment (Phase 3) plus a manual offsetting `LedgerEntry`, neither of which exists as a guided flow. Revisit if this turns out to be a real, frequent need rather than a rare correction.
- **No Cost-of-Goods-Sold / inventory-decrement ledger entry.** This phase posts exactly one `LedgerEntry` per sale — debiting "Accounts Receivable" for the party (§2.6, §5.1 step 6) — because that's the specific entry `PLAN.md`'s Phase 4 write-up asks for ("every invoice posts a `LedgerEntry` with that party's id set"). It does **not** also credit an "Inventory" account for the cost of goods sold, even though Phase 3's spec explicitly flagged this as the matching future half of its own "Inventory" debit-on-receipt entry ("nothing decrements it — Phase 4's future sale-consumption isn't scoped here"). Two things soften this gap: `StockLot.qty_remaining` itself is authoritative and already decrements correctly regardless of the ledger (Phase 8's inventory valuation reads lots directly, per that phase's own `PLAN.md` description, not the "Inventory" ledger account), and margin is already fully visible per-line via `SalesOrderLineRead.margin_pkr` without needing a ledger-side COGS entry to derive it. If a future phase (most naturally Phase 8, or a books-must-tie-out pass before it) needs the "Inventory" account's running balance to mean something precise, this is the gap to close, alongside the still-open Phase 2 cargo-agent-payable gap this codebase already carries (Phase 3 spec §9).
- **No pagination on the party statement** (§2.6) — returns every `LedgerEntry` for a party in one response. Fine at today's scale (a handful of parties, a solo trading business); revisit if any one party's history grows large enough for this to matter.
- **No aggregate "who owes us the most" / receivables-summary endpoint.** `GET /parties/{id}/statement` is per-party only. A cross-party receivables dashboard is plausibly Phase 8's job (it already owns "balance statement" as a named deliverable), not this phase's.
- **`sales_order_line_lot` rows are never surfaced as their own list/detail endpoint** — they're only ever read nested inside `SalesOrderLineRead.consumptions`. If a future "which sales drew from lot X" audit view is needed, add a filtered list endpoint then (mirrors Phase 3 §9's stance on not adding endpoints without a confirmed second caller).
- **`InsufficientStock`'s sufficiency check and the actual consumption walk are two passes over the same locked row set** (§2.4) rather than one — a deliberate correctness-over-cleverness choice (no partial decrement to reason about on the failure path) rather than a performance one; revisit only if profiling ever shows this matters, which it will not at this business's transaction volume.

---

## 10. Implementation checklist

New:
- `backend/src/sales/__init__.py`
- `backend/src/sales/models.py` — `SalesOrder`, `SalesOrderLine`, `SalesOrderLineLot`
- `backend/src/sales/schemas.py`
- `backend/src/sales/exceptions.py`
- `backend/src/sales/dependencies.py`
- `backend/src/sales/service.py`
- `backend/src/sales/utils.py`
- `backend/src/sales/router.py`
- `backend/migrations/versions/<date>_add_sales.py`

Changed:
- `backend/src/inventory/constants.py` — widen `StockMovementType` to include `"sale"`
- `backend/src/inventory/service.py` — add `consume_stock_fifo`
- `backend/src/inventory/exceptions.py` — add `InsufficientStock`
- `backend/src/parties/schemas.py` — add `PartyStatementEntryRead`, `PartyStatementRead`
- `backend/src/parties/service.py` — add `get_party_statement`
- `backend/src/parties/router.py` — add `GET /parties/{party_id}/statement`
- `backend/src/main.py` — mount `sales_router`
