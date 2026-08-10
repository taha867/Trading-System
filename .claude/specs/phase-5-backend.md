# Phase 5 Backend Spec — Local Vendors

Governed by `PLAN.md` (what) and `CLAUDE.md` (how). This document is the missing middle layer: the exact schema, validation, and service-logic changes to implement Phase 5 inside `backend/src/purchasing/`, `backend/src/parties/`, and `backend/src/sales/`, consistent with what Phases 0–4 already built. Nothing here overrides `CLAUDE.md`'s conventions — every choice below either follows an existing precedent in the codebase (cited by file) or is flagged explicitly as a new decision this phase introduces.

**Done when** (from `PLAN.md`): the same party record can appear as the vendor on one order and the customer on another, with one balance. `PLAN.md` is explicit that this phase adds **no new screens** — "if this phase needs a new screen, that's a sign the `Party` role model from Phase 0 needs revisiting — it shouldn't." The backend corollary this spec follows throughout: no new tables, no new endpoints, no new domain package. Every change below is a conditional branch inside code that already exists.

---

## 1. Where we stand

Confirmed by reading the actual code, not assumed:

- **`local_vendor` already exists as a `PartyRole`** (`parties/constants.py:4-9`) — nothing to add there. `Party.roles` is a Postgres array (`parties/models.py:18-21`), so a party holding both `local_vendor` and `customer` (or `local_vendor` and `china_vendor`) is already representable today — Phase 0's data model needs no change.
- **`parties/service.py::ensure_role`** (`parties/service.py:31-34`) is single-role, exact match only:
  ```python
  def ensure_role(party: Party, role: PartyRole) -> Party:
      if role.value not in party.roles:
          raise PartyRoleMismatch(f"Party {party.id} does not hold the '{role.value}' role")
      return party
  ```
  Three callers today: `purchasing.service.create_purchase_order` (requires `CHINA_VENDOR`), `sales.service.create_sales_order` (requires `CUSTOMER`), `cargo.service.create_shipment` (requires `CARGO_AGENT`). None of them can express "this party needs role A *or* role B" — which is exactly what selling surplus to a `local_vendor`-only party requires (§2.1).
- **`parties/dependencies.py::valid_china_vendor`** (`parties/dependencies.py:12-18`) already carries a comment anticipating this phase — *"Kept as the composable, path-param form of the same rule for Phase 5's local-vendor purchase flow"* — but it's unused by any router (Phase 1's `create_purchase_order` takes `party_id` from a JSON body, not a path param, so it calls `service.ensure_role` inline, same reasoning `sales`/`cargo` follow). As written it still only checks `CHINA_VENDOR`, not `LOCAL_VENDOR`. This spec does not wire it up — the inline-call precedent still applies (`party_id` is a body field in both `PurchaseOrderCreate` and `SalesOrderCreate`), so this dependency stays unused after Phase 5 too, unmodified.
- **`purchasing.service.create_purchase_order`** (`purchasing/service.py:22-77`) hard-requires `PartyRole.CHINA_VENDOR` and an `ExchangeRate` row for `order_date` (`ExchangeRateMissingForDate` if missing). Every `PurchaseOrderLine` stores `rate_rmb` (required, `Numeric(12,2)` not-null) and computes `rate_pkr = rate_rmb * exchange_rate.rate`. There is no concept of a purchase order that isn't priced in RMB. This is the one piece of Phase 1 that a local vendor purchase genuinely cannot reuse as-is — `PLAN.md` says so directly ("no cargo/exchange rate step").
- **`landed_cost_pkr` is set in exactly one place today**: `cargo.service.create_shipment` (`cargo/service.py:66-84`), as `line.landed_cost_pkr = money(line.rate_pkr + allocated_cost / line.qty)` — the snapshotted PKR rate plus a per-unit share of that shipment's freight/agent cost. `inventory.service.receive_purchase_order_line` (`inventory/service.py:31-34`) refuses to create a `StockLot` until `landed_cost_pkr is not None` (`LineNotAllocated`). A local vendor purchase has no freight to allocate — cargo cost is zero by construction (pickup is implicit in "local"), so its lines need `landed_cost_pkr` set at creation, without ever touching `cargo/`.
- **The `PurchaseOrder.status` state machine already has a slot for exactly this**: `PurchaseOrderStatus = Literal["draft", "allocated", "received"]` (`purchasing/constants.py`). `"draft"` means "open, attachable to a cargo shipment"; `cargo.service.create_shipment` requires every attached line's PO to be `"draft"` or raises `PurchaseOrderNotOpen` (`cargo/service.py:46-48`, `cargo/exceptions.py:8-10`); it flips the PO to `"allocated"` once every line has a landed cost (`cargo/service.py:86-88`). Nothing else in the codebase ever sets `"allocated"`. **This means a local PO can be created directly in the `"allocated"` state** — skip `"draft"` entirely — and `cargo.service.create_shipment`'s existing `status == "draft"` gate then *automatically* refuses to let a local PO be attached to a shipment, with zero changes to `cargo/`. `inventory.service.receive_purchase_order_line`'s only two checks are `landed_cost_pkr is not None` and "not already received into a lot" (`inventory/service.py:31-38`) — neither reads `PurchaseOrder.status` at all, so receiving a local PO's line works completely unmodified once `landed_cost_pkr` is set at creation.
- **`CargoShipment`/`CargoAllocation` have no FK pointing at `PurchaseOrder` or `PurchaseOrderLine` from the shipment side** — the only link is `CargoAllocation.purchase_order_line_id` (row-level, one allocation per line). A PO that never goes through cargo simply never gets a `CargoAllocation` row; nothing structurally requires one to exist. Combined with the previous point, **`cargo/` and `inventory/` need zero code changes for this phase** — every accommodation lives in `purchasing/` (branch on source) and `parties/`+`sales/` (role flexibility).
- **`src/exceptions.py`**'s `AppException(detail: str | None = None)` / `NotFoundException` / `ConflictException` shape (unchanged this phase) is what any new exception must match — same as every prior phase.
- **`src/crud.py::build_crud_router`** asserts `hasattr(model, "is_active")` (`crud.py:30-32`) and does a flat `model(**payload.model_dump())` insert with no business logic — `PurchaseOrder` still has no `is_active` column, so the generic factory remains unusable for it, unchanged from Phase 1/4's conclusion.
- **`main.py`** mounts `purchasing_router` at `/purchasing` and `sales_router` at `/sales` already (`main.py:23-31`, `main.py:27`, `main.py:31`). Phase 5 adds no new router object and no new `app.include_router` line — every change rides on existing mounts, matching "no new endpoints" (§0).
- **`scripts/seed.py`** seeds a `china_vendor`-only `Party` behind `--vendor-name` (`seed_china_vendor`) and nothing else party-related. No `local_vendor` party is seeded, and there is still no seeded PO→cargo→stock-lot chain at all (a gap that predates this phase — Phase 4's spec flagged the same thing). §8 covers what Phase 5 needs here.
- **`payments/` is unrelated scaffolding** — it's Phase 0's `PaymentMethod` lookup table via the generic CRUD factory (no `service.py`, no reference to `purchasing`/`parties`), not the Phase 6 `PaymentAccount`/`PaymentTransaction` entities. Nothing to touch there.

---

## 2. Design decisions

### 2.1 `parties/service.py` gains `ensure_any_role` — `ensure_role` is not replaced

Selling surplus stock to a party that holds only `local_vendor` (not also `customer`) requires `sales.service.create_sales_order`'s role check to accept either role — a party shouldn't need a redundant `customer` role tacked on just to satisfy a strict single-role check that predates this phase. Rather than widening `ensure_role` itself (which would silently change its contract for every existing caller, none of which need the widening), add a second function alongside it:

```python
def ensure_any_role(party: Party, roles: tuple[PartyRole, ...]) -> Party:
    if not any(role.value in party.roles for role in roles):
        names = " or ".join(role.value for role in roles)
        raise PartyRoleMismatch(f"Party {party.id} does not hold any of: {names}")
    return party
```

`ensure_role` stays exactly as-is and keeps its three existing callers (`purchasing` china-branch, `cargo`, and `purchasing` local-branch — both branches want an *exact* single role, never "either"). Only `sales.service.create_sales_order` switches to the new function (§2.4). This mirrors the exact shape `PartyRoleMismatch` already has — no new exception class, just a new call site raising the existing one with a different message.

### 2.2 `PurchaseOrder` gains a `source` column — `"china"` (default) or `"local"`

`PLAN.md`'s entity note for this phase is literally `PurchaseOrder(source=local)` — the plan already names this as a column, not an inference from the vendor's role. A column is also strictly more correct than inferring source from `Party.roles`: a party can hold both `china_vendor` and `local_vendor` (nothing stops that), so "what pricing flow does *this* order use" has to be a fact about the order, not derived from the vendor's full role set at read time. `source` is set once at creation and never updated — no `PurchaseOrderUpdate` schema exists for this entity at all (Phase 1 never added one; this phase doesn't either).

```python
# purchasing/constants.py — new Literal alongside PurchaseOrderStatus
PurchaseOrderSource = Literal["china", "local"]
```

### 2.3 A local-sourced line skips the RMB step entirely — `rate_rmb` becomes nullable, `rate_pkr` becomes client-supplied for local lines

For a `"china"` order, the existing flow is unchanged byte-for-byte: client sends `rate_rmb`, service looks up `ExchangeRate` for `order_date`, computes `rate_pkr = rate_rmb * rate`. For a `"local"` order, there is no RMB leg at all — the vendor quotes directly in PKR, the same way `sales.SalesOrderLineCreate.rate_pkr` already works (`sales/schemas.py`). So a local line's `PurchaseOrderLineCreate` carries `rate_pkr` directly, and `rate_rmb` stays `None`.

This means `PurchaseOrderLine.rate_rmb` must become nullable (it's `Numeric(12,2)` not-null today, `purchasing/models.py:31`) — a migration change (§7), not just a schema one. `rate_pkr` stays not-null (every line, china or local, ends up with a PKR rate one way or another).

Cross-field validity (a china line must carry `rate_rmb` and not `rate_pkr`; a local line the reverse) is enforced once, at the `PurchaseOrderCreate` level, via `@model_validator(mode="after")` — this is a genuine cross-field, business-rule check (`CLAUDE.md` §2.4's stated bar for reaching past a bare `Field()` constraint), not something a per-line `Annotated[..., Field(...)]` bound could express, since the rule depends on the *parent* order's `source`, not anything intrinsic to one line.

### 2.4 A local line's `landed_cost_pkr` is set at creation — equal to `rate_pkr`, no cargo step

Because a local vendor purchase has no freight/agent cost to allocate (`PLAN.md`: "no cargo/exchange rate step"), `landed_cost_pkr` for a local line is simply its `rate_pkr` — the same value cargo would otherwise compute as `rate_pkr + allocated_cost / qty` with `allocated_cost = 0`. Setting it directly at line-construction time, inside `purchasing.service.create_purchase_order`, is what lets `inventory.service.receive_purchase_order_line` work completely unmodified (§1) — from that function's point of view, a local line simply arrived pre-allocated.

### 2.5 A local `PurchaseOrder` is created directly in `"allocated"` status — never `"draft"`

Per §1's discovery, this single choice is what makes `cargo/` require zero code changes: `cargo.service.create_shipment` already refuses to attach any PO whose status isn't `"draft"` (`PurchaseOrderNotOpen`). Creating local orders straight into `"allocated"` reuses that existing gate as the enforcement mechanism for "local orders never go through cargo," rather than adding a new `source == "local"` check inside `cargo/` that would duplicate the same intent in a second place. `PurchaseOrderStatus`'s `Literal` already includes `"allocated"` — no constant change needed, only a new *entry path* into a value that already exists, documented with a code comment at the call site (§5.1) so a future reader isn't surprised to see `"allocated"` set outside `cargo/service.py`.

The transition to `"received"` (once every line has a `StockLot`) is untouched — `inventory.service.receive_purchase_order_line`'s flip-to-`"received"` logic (`inventory/service.py:75-84`) already works from either `"draft"` or `"allocated"`, since it only counts unreceived lines, never reads the PO's current status as a precondition.

### 2.6 Vendor role check branches on `source`, using the existing `ensure_role` (not the new `ensure_any_role`)

`purchasing.service.create_purchase_order` picks exactly one required role from `source` — `CHINA_VENDOR` for `"china"`, `LOCAL_VENDOR` for `"local"` — and calls the existing `ensure_role` with it. This is deliberately *not* `ensure_any_role(vendor, (CHINA_VENDOR, LOCAL_VENDOR))`: that would let a `china_vendor`-only party be charged as a local-sourced order (or vice versa) as long as it held *either* role, silently accepting a party/source mismatch that should be a hard error. `source` and the vendor's role must match exactly — `ensure_any_role` exists for `sales/` (§2.1), where either role is genuinely acceptable, not for this check.

### 2.7 `sales.service.create_sales_order`'s role check widens to accept `local_vendor`

`PLAN.md`: "reuse the Phase 4 sales screen for selling surplus to them [local vendors]." The one-line change is the call site itself:

```python
# before (Phase 4)
parties_service.ensure_role(customer, PartyRole.CUSTOMER)
# after (Phase 5)
parties_service.ensure_any_role(customer, (PartyRole.CUSTOMER, PartyRole.LOCAL_VENDOR))
```

Nothing else in `create_sales_order` changes — FIFO consumption, the ledger post (`"Accounts Receivable"`, debit), and the response schema are all role-agnostic already.

### 2.8 No new endpoints, no new router, no new domain package

Every change above lives inside functions and schemas that already exist in `purchasing/` and `sales/`, plus one new function in `parties/service.py`. `POST /purchasing/purchase-orders` gains an optional `source` field on its existing body schema (default `"china"`, so every existing Phase 1 caller keeps working unchanged); `POST /sales/sales-orders` changes internally with no body-schema change at all. This is the backend expression of `PLAN.md`'s "no new screens" — confirmed, not assumed, against the current router/schema shape in §1.

---

## 3. Data model

### 3.1 Changed: `backend/src/purchasing/models.py`

```python
class PurchaseOrder(Base):
    __tablename__ = "purchase_order"

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"), index=True)
    order_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(default="china", server_default="china")  # new
    status: Mapped[str] = mapped_column(default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ...


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_line"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_order.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), index=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    rate_rmb: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)  # changed: was not-null
    rate_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    landed_cost_pkr: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    ...
```

Plain `str` column for `source`, same convention `status` already uses (Literal enforced at the Pydantic/service layer, not a Postgres enum type) — widening either `Literal` later needs no migration, matching the precedent `purchasing/constants.py`'s own comment already documents for `PurchaseOrderStatus`.

### 3.2 Changed: `backend/src/purchasing/constants.py`

```python
from typing import Literal

PurchaseOrderStatus = Literal["draft", "allocated", "received"]

# "china" orders go through the existing RMB/exchange-rate + cargo-allocation flow;
# "local" orders are quoted directly in PKR and skip both — see phase-5-backend.md §2.
PurchaseOrderSource = Literal["china", "local"]
```

### 3.3 No changes to `cargo/` or `inventory/` (§1, §2.5)

Called out explicitly because it's easy to assume otherwise going in: `cargo/models.py`, `cargo/service.py`, `cargo/schemas.py`, `inventory/models.py`, `inventory/service.py`, `inventory/schemas.py` — none of these files change for Phase 5.

### 3.4 No new directional dependency

`purchasing/` already imports `parties.service`/`parties.constants.PartyRole`; `sales/` already imports the same. Phase 5 adds no new edge to the dependency graph — it only calls one new function (`ensure_any_role`) on an import that already exists.

---

## 4. Pydantic schemas

### 4.1 Changed: `backend/src/purchasing/schemas.py`

```python
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from src.purchasing.constants import PurchaseOrderSource
from src.purchasing.utils import money


class PurchaseOrderLineCreate(BaseModel):
    item_id: int
    qty: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    rate_rmb: Annotated[Decimal, Field(gt=0, decimal_places=2)] | None = None
    rate_pkr: Annotated[Decimal, Field(gt=0, decimal_places=2)] | None = None


class PurchaseOrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    qty: Decimal
    rate_rmb: Decimal | None = None
    rate_pkr: Decimal
    landed_cost_pkr: Decimal | None = None

    @computed_field
    @property
    def amount_rmb(self) -> Decimal | None:
        return money(self.qty * self.rate_rmb) if self.rate_rmb is not None else None

    @computed_field
    @property
    def amount_pkr(self) -> Decimal:
        return money(self.qty * self.rate_pkr)

    @computed_field
    @property
    def amount_landed_pkr(self) -> Decimal | None:
        return money(self.qty * self.landed_cost_pkr) if self.landed_cost_pkr is not None else None


class PurchaseOrderCreate(BaseModel):
    party_id: int
    order_date: date
    source: PurchaseOrderSource = "china"
    lines: Annotated[list[PurchaseOrderLineCreate], Field(min_length=1)]

    @model_validator(mode="after")
    def _validate_line_rates_match_source(self) -> "PurchaseOrderCreate":
        for line in self.lines:
            if self.source == "china":
                if line.rate_rmb is None or line.rate_pkr is not None:
                    raise ValueError("china-sourced lines must set rate_rmb, not rate_pkr")
            else:
                if line.rate_pkr is None or line.rate_rmb is not None:
                    raise ValueError("local-sourced lines must set rate_pkr, not rate_rmb")
        return self


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    party_id: int
    order_date: date
    source: PurchaseOrderSource
    status: str
    lines: list[PurchaseOrderLineRead]

    @computed_field
    @property
    def total_rmb(self) -> Decimal | None:
        if self.source == "local":
            return None
        return money(sum((line.amount_rmb for line in self.lines), Decimal(0)))

    @computed_field
    @property
    def total_pkr(self) -> Decimal:
        return money(sum((line.amount_pkr for line in self.lines), Decimal(0)))
```

`ExchangeRateCreate`/`ExchangeRateRead`/`ExchangeRateUpdate` are unchanged — a local order never touches `ExchangeRate` at all.

`total_rmb` returns `None` for local orders rather than `Decimal(0)` — `0` would misleadingly read as "an RMB total of zero" (a real, priced-in-RMB order that happens to sum to nothing); `None` is honest that RMB isn't the order's currency at all. This mirrors `amount_landed_pkr`'s existing `None`-before-allocation convention on the same schema.

### 4.2 No changes to `backend/src/sales/schemas.py` or `backend/src/parties/schemas.py`

Confirmed against §2.7/§2.1 — the sales role-check change and the new `ensure_any_role` function are both pure service-layer logic; no schema shape changes.

---

## 5. Service logic

### 5.1 `purchasing/service.py::create_purchase_order` — branch on `payload.source`

```python
async def create_purchase_order(db: AsyncSession, payload: PurchaseOrderCreate) -> PurchaseOrder:
    vendor = await parties_service.get_active_party(db, payload.party_id)
    required_role = PartyRole.CHINA_VENDOR if payload.source == "china" else PartyRole.LOCAL_VENDOR
    parties_service.ensure_role(vendor, required_role)  # exact match by design — see §2.6

    rate_row = None
    if payload.source == "china":
        rate_row = await db.scalar(
            select(ExchangeRate).where(
                ExchangeRate.rate_date == payload.order_date,
                ExchangeRate.is_active.is_(True),
            )
        )
        if rate_row is None:
            raise ExchangeRateMissingForDate()

    # item-id validation: unchanged, applies to both sources identically

    lines: list[PurchaseOrderLine] = []
    total_pkr = Decimal(0)
    for line in payload.lines:
        if payload.source == "china":
            rate_pkr = money(line.rate_rmb * rate_row.rate)
            po_line = PurchaseOrderLine(item_id=line.item_id, qty=line.qty, rate_rmb=line.rate_rmb, rate_pkr=rate_pkr)
        else:
            # No freight to allocate for a local pickup — landed cost is the quoted
            # PKR rate itself, set here instead of by cargo.service.create_shipment (§2.4).
            po_line = PurchaseOrderLine(
                item_id=line.item_id, qty=line.qty, rate_rmb=None,
                rate_pkr=line.rate_pkr, landed_cost_pkr=line.rate_pkr,
            )
        lines.append(po_line)
        total_pkr += money(line.qty * po_line.rate_pkr)
    total_pkr = money(total_pkr)

    po = PurchaseOrder(
        party_id=vendor.id,
        order_date=payload.order_date,
        source=payload.source,
        # Local orders skip the cargo step entirely — starting in "allocated" (rather
        # than "draft") reuses cargo.service.create_shipment's existing status=="draft"
        # gate to keep them from ever being attached to a shipment (§2.5).
        status="allocated" if payload.source == "local" else "draft",
        lines=lines,
    )
    db.add(po)
    await db.flush()

    await ledger_service.post_entry(
        db,
        entry_date=payload.order_date,
        account="Accounts Payable",
        credit=total_pkr,
        reference_type="purchase_order",
        reference_id=po.id,
        party_id=vendor.id,
    )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Purchase order could not be saved") from exc

    return po
```

Everything after the source-conditional block (item validation, the ledger post, commit/rollback shape) is byte-identical to the Phase 1 version — the branch is isolated to exactly the two places that differ (role/rate-lookup, and per-line construction/status).

`list_purchase_orders`, `valid_purchase_order` (`dependencies.py`), and the router (`router.py`) need **no changes** — they're already source-agnostic (they select/return whatever's in the table).

### 5.2 `parties/service.py` — add `ensure_any_role`

Exact function given in §2.1, placed directly below the existing `ensure_role`. No changes to `get_active_party`, `create_party`, `update_party`, `soft_delete_party`, or `get_party_statement`.

### 5.3 `sales/service.py::create_sales_order` — one-line role-check change

```python
customer = await parties_service.get_active_party(db, payload.party_id)
parties_service.ensure_any_role(customer, (PartyRole.CUSTOMER, PartyRole.LOCAL_VENDOR))
```

Everything else in the function (duplicate/inactive item validation, FIFO consumption via `inventory_service.consume_stock_fifo`, the `"Accounts Receivable"` ledger post, commit shape) is unchanged.

### 5.4 No changes to `cargo/service.py` or `inventory/service.py`

Restated from §1/§2.5/§3.3 because it's the single most important fact this spec establishes: the existing `status == "draft"` gate in `cargo.service.create_shipment` and the existing `landed_cost_pkr is not None` gate in `inventory.service.receive_purchase_order_line` are *sufficient*, unmodified, once local orders are created with `landed_cost_pkr` pre-set and `status="allocated"`.

### 5.5 No new exceptions

`PurchaseOrderCreate`'s cross-field rate/source check (§2.3) is a Pydantic `model_validator` — a `ValueError` there surfaces as FastAPI's standard 422 validation-error response automatically, the same mechanism every other `Field()`/`@field_validator` constraint in this codebase already relies on. It is not a domain `AppException`, because it's a shape problem with the request body, not a business-rule failure against database state (contrast `ExchangeRateMissingForDate`, which *is* an `AppException` because it depends on what's in the `exchange_rate` table). `ensure_any_role` (§5.2) reuses `PartyRoleMismatch`, already defined in `parties/exceptions.py` — no new exception class needed anywhere in this phase.

---

## 6. API surface

No new routes, no new router, no new `main.py` mount (§2.8, confirmed against current `main.py` in §1).

| Method | Path | Change |
|---|---|---|
| POST | `/purchasing/purchase-orders` | body gains optional `source: "china" \| "local"` (default `"china"`); lines gain optional `rate_pkr`, `rate_rmb` becomes optional (exactly one of the two required, enforced by `source`, §2.3) |
| GET | `/purchasing/purchase-orders`, `/purchasing/purchase-orders/{id}` | response gains `source`; `total_rmb` becomes nullable |
| POST | `/sales/sales-orders` | no body-schema change; internal role check now accepts a `local_vendor`-role party |

Every existing Phase 1 client request (no `source` field, `rate_rmb` set on every line) continues to work unchanged — `source` defaults to `"china"`, which is exactly the validator branch that requires `rate_rmb` and forbids `rate_pkr`, i.e. exactly what a pre-Phase-5 request body already looks like.

---

## 7. Migration

One Alembic revision, `alembic revision --autogenerate`, reviewed by eye (`CLAUDE.md` §2.5 — autogenerate is known to miss `Numeric`-precision-adjacent changes, and a nullability change on an existing column is exactly the kind of thing to double check by hand). Expected diff:

- `ALTER TABLE purchase_order ADD COLUMN source VARCHAR NOT NULL DEFAULT 'china'` — existing rows all become `"china"`, correct for every PO created before this phase (there was no other kind).
- `ALTER TABLE purchase_order_line ALTER COLUMN rate_rmb DROP NOT NULL`

No new tables, no `ALTER` on any other table. File name: `<date>_add_purchase_order_source.py`, one migration for the whole phase, matching every prior phase's one-migration-per-phase precedent (`migrations/versions/` currently ends at `2026-08-08_add_sales.py`).

---

## 8. Seed data (`backend/scripts/seed.py`)

**No structural change required** — Phase 5's `PurchaseOrder`/`SalesOrder` rows are still transactional records produced by using the app, same reasoning Phase 1/4 already established for not seeding them. What's missing for *manual testing* of this phase specifically is a `Party` that actually holds `local_vendor` (optionally alongside `customer`, to exercise "same party as vendor on one order and customer on another" in a single record, per this phase's own done-when line).

`seed.py` already has the exact template to copy: `seed_china_vendor(name)` gated behind `--vendor-name`. A symmetrical `seed_local_vendor(name, also_customer: bool)` behind a new `--local-vendor-name` flag (creating `roles=["local_vendor"]` or `roles=["local_vendor", "customer"]`) would cost about the same ten lines and directly serves this phase's own acceptance criterion. Optional rather than mandatory for this spec — flagged here, not written speculatively into the checklist, following the same restraint Phase 4's spec used for its own seed-script suggestion (§9).

Manual dev/testing setup, in order: run `scripts/seed.py --local-vendor-name "..."` (once the flag above exists — otherwise create the party by hand via `POST /parties` with `roles: ["local_vendor"]`) → create a `Category`/`Model`/`Item` if none exist → `POST /purchasing/purchase-orders` with `source: "local"`, `party_id` = that local vendor's id, lines carrying `rate_pkr` (no `rate_rmb`) → confirm the response's `status` is already `"allocated"` and `landed_cost_pkr` is already set per line, with no cargo-shipment step in between → `POST /inventory/stock-lots` to receive each line directly → (optionally) `POST /sales/sales-orders` selling that same stock back to the same party id, confirming the role check accepts it → `GET /parties/{id}/statement` to see both the payable-side and receivable-side ledger entries against one balance.

---

## 9. Out of scope / open questions for later

- **No `PurchaseOrderUpdate` endpoint for `source`.** `source` is set once at creation, matching the existing precedent that `PurchaseOrder` has no update endpoint at all today. If a PO is created with the wrong source, correcting it means creating a new PO and manually reasoning about the ledger — no worse than any other PO-creation mistake today, and not a gap this phase introduces.
- **No `PaymentAccount`-level distinction between paying a China vendor vs. a local vendor.** Phase 6 owns `PaymentAccount`/`PaymentTransaction`; this phase only makes the `Party`/`PurchaseOrder` side vendor-flexible. A `PaymentTransaction`'s `party_id` will already work against a `local_vendor`-role party once Phase 6 exists, with no anticipated change needed there — noted here only so Phase 6's spec doesn't need to rediscover it.
- **`ensure_any_role`'s error message lists the required roles but not which ones the party actually has.** Matches `ensure_role`'s existing message style (states what's required, not what's present) — revisit only if a future debugging session shows this is genuinely confusing in practice.
- **A party holding both `china_vendor` and `local_vendor` must pick a `source` correctly per order — nothing warns if they mean to buy locally but forget to set `source: "local"`.** The `ensure_role`-with-exact-match design (§2.6) turns a mismatch into a hard `PartyRoleMismatch` only if the party *doesn't* hold the role the (possibly wrong) `source` implies; if they hold both roles, a wrong `source` silently succeeds against the wrong pricing flow. This is an acceptable gap for a solo-operator system where the person creating the PO knows which vendor they're actually buying from — revisit if this system ever gets a second data-entry user.
- **No seed-script change is made mandatory** (§8) — left as an implementation-time judgment call, same restraint prior phases' specs applied to their own seed-script suggestions.

---

## 10. Implementation checklist

Changed:
- `backend/src/purchasing/constants.py` — add `PurchaseOrderSource = Literal["china", "local"]`
- `backend/src/purchasing/models.py` — `PurchaseOrder.source` (new column); `PurchaseOrderLine.rate_rmb` (now nullable)
- `backend/src/purchasing/schemas.py` — `PurchaseOrderLineCreate`/`Read` (`rate_rmb`/`rate_pkr` optionality, nullable `amount_rmb`); `PurchaseOrderCreate` (`source` field + `model_validator`); `PurchaseOrderRead` (`source` field, nullable `total_rmb`)
- `backend/src/purchasing/service.py::create_purchase_order` — branch on `payload.source` (§5.1)
- `backend/src/parties/service.py` — add `ensure_any_role`
- `backend/src/sales/service.py::create_sales_order` — role check widened to `ensure_any_role(customer, (PartyRole.CUSTOMER, PartyRole.LOCAL_VENDOR))`
- `backend/migrations/versions/<date>_add_purchase_order_source.py`

Not changed (confirmed, not assumed — §1, §3.3, §5.4):
- `backend/src/cargo/*`
- `backend/src/inventory/*`
- `backend/src/purchasing/router.py`, `backend/src/purchasing/dependencies.py`, `backend/src/purchasing/exceptions.py`
- `backend/src/sales/router.py`, `backend/src/sales/schemas.py`, `backend/src/sales/dependencies.py`, `backend/src/sales/exceptions.py`
- `backend/src/parties/router.py`, `backend/src/parties/dependencies.py`, `backend/src/parties/schemas.py`, `backend/src/parties/exceptions.py`
- `backend/src/main.py`

Optional (§8, not required to satisfy this phase's done-when line):
- `backend/scripts/seed.py` — a `--local-vendor-name` flag mirroring `--vendor-name`
