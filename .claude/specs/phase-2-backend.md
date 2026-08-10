# Phase 2 Backend Spec — Cargo & Landed Cost

Governed by `PLAN.md` (what) and `CLAUDE.md` (how). This document is the missing middle layer: the exact entities, endpoints, and service logic to implement Phase 2 inside `backend/src/cargo/`, consistent with what Phase 0/1 already built. Nothing here overrides `CLAUDE.md`'s conventions — every choice below follows an existing precedent in the codebase, cited by file.

**Done when** (from `PLAN.md`): a shipment's freight cost is visibly split across the items in it, and each PO line shows a landed cost, not just its RMB rate.

---

## 1. Where we stand

Confirmed by reading the actual code, not assumed:

- **Built**: `auth`, `parties`, `catalog`, `purchasing`, `ledger`, and a `payments` stub (`PaymentMethod` lookup only). Generic CRUD engine (`src/crud.py`) works and is proven on `Category`, `Model`, `PaymentMethod`, `ExchangeRate`.
- **`Party.roles`** already includes `cargo_agent` (`parties/constants.py`) — the model was explicitly built with `postgresql.ARRAY` anticipating this. **No schema change needed for the Party side of Phase 2.**
- **`PurchaseOrder.status`** is currently `Literal["draft"]` — every PO ever created stays `"draft"` forever; there is no workflow yet (`purchasing/constants.py`, confirmed by comment in that file). Phase 2 is what gives `status` its first real transition.
- **`PurchaseOrderLine`** has `qty`, `rate_rmb`, `rate_pkr` only. No landed-cost column, no cargo-allocation placeholder exists anywhere.
- **`src/cargo/` does not exist.** Phase 2 starts from zero on this domain.
- Ledger (`ledger/service.post_entry`) is only called by `purchasing` (PO creation → "Accounts Payable") and `parties` (opening balance). Per `PLAN.md`, cargo cost allocation is a cost split, not a cash movement — **Phase 2 posts nothing to the ledger.**

---

## 2. Design decisions

Three calls this spec makes that aren't spelled out in `PLAN.md`. Recorded here so they're reviewed once, not re-derived during implementation.

### 2.1 A shipment attaches whole purchase orders, not individual lines

`PLAN.md` says "attach one or more open POs." Read literally: the unit of attachment is the PO, not a line within it. This keeps the status transition clean — a PO is either `draft` (open, attachable) or `allocated` (every one of its lines got a landed cost from some shipment). There's no partial state to model, no "PO half-allocated" edge case, and no need for a `dependencies.py` helper that resolves individual line ownership across POs.

The one thing this does require from the client: enough weight/CBM figures to split the *lines* inside those attached POs, since the cost still has to divide per line, not per PO. That's `line_basis_values` in the payload (§4.4) — a flat list keyed by `purchase_order_line_id`, scoped only to the POs being attached in that call.

### 2.2 `CargoCostBasis` needs a stable `code`, not just a display `name`

`PLAN.md` calls `CargoCostBasis` a "dynamic lookup" alongside `CargoMode`, in the same spirit as `Category`/`PaymentMethod` — pure CRUD, no code cares what the row is *named*. But cost-basis rows aren't purely descriptive: the allocation math branches on whether a given basis means "split by weight," "split by CBM," or "split by piece count (i.e., `qty`, already on the line, no manual entry)." A free-text `name` a user can rename any time (`"Weight"` → `"Weight (kg)"`) is not safe to branch service logic on.

Resolution: add `code: Literal["weight", "cbm", "piece"]`, unique, immutable after creation (not in `CargoCostBasisUpdate`) — same rationale `Party.opening_balance` already uses for being write-once (`parties/schemas.py`). The row stays CRUD-managed (rename, deactivate) like every other dynamic lookup; only `code` is pinned, because it's what the allocation algorithm reads, not what a user sees. `CargoMode` gets no such field — Sea vs. Air is purely descriptive today, nothing branches on it.

### 2.3 `landed_cost_pkr` lives on `PurchaseOrderLine`, snapshotted once, not recomputed

Same rule `rate_pkr` already follows (`CLAUDE.md` §4, "snapshot, don't recompute historical rates"): once a shipment's allocation runs, `PurchaseOrderLine.landed_cost_pkr` is written once (`rate_pkr` + this line's per-unit share of freight) and never touched again by this phase. There's deliberately no "re-allocate" or "undo" endpoint — correcting a mistake is out of scope for Phase 2 (flagged again in §9).

This also sets up Phase 3 cleanly: when a PO line gets "received" into a `StockLot`, the lot's cost is just `PurchaseOrderLine.landed_cost_pkr` — no join through `CargoAllocation` required at that point.

---

## 3. Data model

### 3.1 New tables (`backend/src/cargo/models.py`)

**`cargo_mode`** — pure dynamic lookup, identical shape to `PaymentMethod`:

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `name` | `str`, unique | "Sea", "Air" |
| `is_active` | `bool`, default `True` | soft delete via generic CRUD |

**`cargo_cost_basis`** — dynamic lookup with a pinned `code` (§2.2):

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `name` | `str`, unique | "Weight", "CBM", "Piece" — user-editable label |
| `code` | `str`, unique | `"weight" \| "cbm" \| "piece"` — service branches on this, never on `name` |
| `is_active` | `bool`, default `True` | |

**`cargo_shipment`** — hand-written, transactional (like `PurchaseOrder`): no `is_active`, no delete endpoint.

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `cargo_agent_id` | FK → `party.id`, indexed | must hold `cargo_agent` role |
| `cargo_mode_id` | FK → `cargo_mode.id`, indexed | |
| `cost_basis_id` | FK → `cargo_cost_basis.id`, indexed | |
| `shipment_date` | `Date` | |
| `total_cost_pkr` | `Numeric(12,2)` | the freight bill being split |
| `created_at` | `DateTime(timezone=True)`, `server_default=func.now()` | |
| `allocations` | relationship → `CargoAllocation`, `cascade="all, delete-orphan"`, `lazy="raise"` | mirrors `PurchaseOrder.lines` exactly |

**`cargo_allocation`** — one row per PO line covered by a shipment.

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `cargo_shipment_id` | FK → `cargo_shipment.id`, indexed | |
| `purchase_order_line_id` | FK → `purchase_order_line.id`, **unique**, indexed | a line can only ever be allocated once — DB-enforced |
| `basis_value` | `Numeric(12,4)` | the weight/CBM figure entered, or `qty` copied through for piece basis |
| `allocated_cost_pkr` | `Numeric(12,2)` | this line's share of `total_cost_pkr` |
| `created_at` | `DateTime(timezone=True)`, `server_default=func.now()` | |

### 3.2 Changed table: `purchase_order_line` (`backend/src/purchasing/models.py`)

Add one nullable column:

```python
landed_cost_pkr: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
```

`NULL` until a cargo shipment allocates against this line; set exactly once (§2.3).

### 3.3 Changed constant: `purchasing/constants.py`

```python
# Phase 2 introduces the first status transition: a PO stays "draft" (open, attachable
# to a cargo shipment) until every one of its lines gets a landed cost, then flips to
# "allocated". Widen again when a later phase needs to (e.g. Phase 3's "received").
PurchaseOrderStatus = Literal["draft", "allocated"]
```

No migration needed for this change by itself — `status` is already a plain `str` column; only the Python-side `Literal` widens.

### 3.4 Directional dependency this phase establishes

`cargo/` imports `purchasing.models.{PurchaseOrder, PurchaseOrderLine}` directly (reads and mutates them in the same transaction as its own inserts) and imports `parties.service.{get_active_party, ensure_role}` — the same one-directional shape `purchasing` already has toward `parties`. `purchasing` and `parties` never import `cargo`. This keeps `CLAUDE.md`'s one-way rule for `parties`/`ledger` intact and extends the same discipline by convention (not by a written rule) to `purchasing`.

---

## 4. Pydantic schemas (`backend/src/cargo/schemas.py`)

### 4.1 `CargoMode` — identical shape to `PaymentMethodCreate/Read/Update`

```python
class CargoModeCreate(BaseModel):
    name: Annotated[str, Field(max_length=64)]

class CargoModeRead(CargoModeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool

class CargoModeUpdate(BaseModel):
    name: Annotated[str, Field(max_length=64)] | None = None
```

### 4.2 `CargoCostBasis`

```python
class CargoCostBasisCreate(BaseModel):
    name: Annotated[str, Field(max_length=64)]
    code: CargoCostBasisCode          # Literal["weight", "cbm", "piece"], from constants.py

class CargoCostBasisRead(CargoCostBasisCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool

class CargoCostBasisUpdate(BaseModel):
    name: Annotated[str, Field(max_length=64)] | None = None
    # `code` intentionally omitted — pinned at creation, service logic branches on it (§2.2)
```

### 4.3 `CargoAllocation` (read-only — never created directly by a client)

```python
class CargoAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    purchase_order_line_id: int
    basis_value: Decimal
    allocated_cost_pkr: Decimal
```

### 4.4 `CargoShipment`

```python
class CargoShipmentLineInput(BaseModel):
    purchase_order_line_id: int
    basis_value: Annotated[Decimal, Field(gt=0, decimal_places=4)] | None = None
    # required (and validated) when cost_basis.code in {"weight", "cbm"};
    # must be omitted when cost_basis.code == "piece" — derived from the line's own qty instead

class CargoShipmentCreate(BaseModel):
    cargo_agent_id: int
    cargo_mode_id: int
    cost_basis_id: int
    shipment_date: date
    total_cost_pkr: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    purchase_order_ids: Annotated[list[int], Field(min_length=1)]
    line_basis_values: list[CargoShipmentLineInput] = []

class CargoShipmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cargo_agent_id: int
    cargo_mode_id: int
    cost_basis_id: int
    shipment_date: date
    total_cost_pkr: Decimal
    allocations: list[CargoAllocationRead]
```

No `CargoShipmentUpdate` — like `PurchaseOrder`, this is a hand-written transactional entity with create + read only in this phase (§9).

### 4.5 Changed: `purchasing/schemas.py`

`PurchaseOrderLineRead` gains the new column, plus a computed field mirroring the existing `amount_rmb`/`amount_pkr` pattern:

```python
class PurchaseOrderLineRead(BaseModel):
    ...
    landed_cost_pkr: Decimal | None = None

    @computed_field
    @property
    def amount_landed_pkr(self) -> Decimal | None:
        return money(self.qty * self.landed_cost_pkr) if self.landed_cost_pkr is not None else None
```

`PurchaseOrderRead.status` stays typed `str` (unchanged) — it already round-trips whatever the model holds.

---

## 5. Service logic (`backend/src/cargo/service.py`)

### 5.1 `create_shipment(db, payload: CargoShipmentCreate) -> CargoShipment`

Validation order (fail fast, cheapest checks first — matches `purchasing.service.create_purchase_order`'s shape):

1. **Agent**: `party = await parties_service.get_active_party(db, payload.cargo_agent_id)`, then `parties_service.ensure_role(party, PartyRole.CARGO_AGENT)`.
2. **Mode**: fetch `CargoMode` by id, 422 if missing/inactive.
3. **Cost basis**: fetch `CargoCostBasis` by id, 422 if missing/inactive. Its `code` drives step 5.
4. **Lines**: one query pulls every `PurchaseOrderLine` for `payload.purchase_order_ids`, eager-loading `.purchase_order` (`selectinload`, per `CLAUDE.md` §2.5 — no lazy-load in async).
   - If any requested `purchase_order_id` yields zero lines → that PO doesn't exist; raise (reuse `purchasing.exceptions.PurchaseOrderNotFound` — read-only cross-import of an exception class, not a service call).
   - If any line's parent PO has `status != "draft"` → raise `PurchaseOrderNotOpen` (new, cargo-local exception) — it's already allocated by an earlier shipment.
5. **Basis values** — branch on `cost_basis.code`:
   - `"piece"`: `basis_value = line.qty` for every line; reject (422) if the client supplied any `line_basis_values` entries at all — that would silently be ignored otherwise, better to fail loud.
   - `"weight"` / `"cbm"`: every fetched line must have a matching entry in `payload.line_basis_values` with a positive `basis_value`; missing or non-positive → raise `MissingBasisValue` (new exception) naming the offending line id.
6. **Split the cost**: `total_basis = sum(basis_values.values())`. For each line (ordered deterministically by `line.id`), `share = total_cost_pkr * basis_value / total_basis`, rounded via a local `money()` helper (same `ROUND_HALF_UP` 2dp rounding as `purchasing/utils.py`, duplicated in `cargo/utils.py` rather than cross-imported — keeps the domain self-contained per `CLAUDE.md` §2.1).
   - **Remainder correction**: running-sum every rounded share except the last line; the last line (highest `id`) gets `total_cost_pkr - sum(all_previous)` instead of its own rounded share. This guarantees `sum(allocated_cost_pkr across the shipment's allocations) == total_cost_pkr` exactly — rounding many small shares independently can otherwise leave the total a cent off, which would make the shipment's own total untrustworthy.
7. **Write**: insert the `CargoShipment` row, flush for its `id`, insert one `CargoAllocation` per line, and set `line.landed_cost_pkr = money(line.rate_pkr + allocated_cost_pkr / line.qty)` directly on the already-loaded `PurchaseOrderLine` ORM objects (SQLAlchemy tracks the mutation; no extra query needed).
8. **Flip PO status**: for every distinct `purchase_order_id` touched, set `po.status = "allocated"` — safe because step 4 already fetched *every* line belonging to that PO (attachment is whole-PO, §2.1), so there's never a partially-covered PO at this point.
9. **Commit**: single `await db.commit()`, `IntegrityError` → `ConflictException` (matches the `try/except` shape in every existing `service.py`) — the `unique` constraint on `cargo_allocation.purchase_order_line_id` is the actual backstop against double-allocating a line if a race slips past step 4's status check.
10. `await db.refresh(shipment)` and return; the router's `response_model` needs the `allocations` relationship loaded, so re-fetch through `dependencies.valid_cargo_shipment` (§5.3) rather than trusting `refresh()` to populate a `lazy="raise"` relationship.

### 5.2 `list_shipments(db, pagination) -> PaginatedResponse[CargoShipmentRead]`

Same shape as `purchasing.service.list_purchase_orders` — paginated, ordered by `id`, no filters in this phase.

### 5.3 `dependencies.py` — `valid_cargo_shipment`

```python
async def valid_cargo_shipment(cargo_shipment_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> CargoShipment:
    result = await db.execute(
        select(CargoShipment)
        .options(selectinload(CargoShipment.allocations))
        .where(CargoShipment.id == cargo_shipment_id)
    )
    shipment = result.scalar_one_or_none()
    if not shipment:
        raise CargoShipmentNotFound()
    return shipment
```

Direct copy of `purchasing.dependencies.valid_purchase_order`'s shape, including the same comment about why `select()` + `selectinload` is used instead of `db.get()`.

### 5.4 `cargo/exceptions.py`

```python
class CargoShipmentNotFound(NotFoundException):
    detail = "Cargo shipment not found"

class PurchaseOrderNotOpen(AppException):
    status_code = 422
    detail = "One or more attached purchase orders are already allocated to a shipment"

class MissingBasisValue(AppException):
    status_code = 422
    detail = "A positive basis figure is required for every attached line under this cost basis"
```

`CargoModeNotFound`/`CargoCostBasisNotFound` aren't separate classes — reuse the generic pattern already in `crud.py`'s `_get_active_or_404` (raises `NotFoundException` with a model-specific message) for those two lookups inside `service.py`.

### 5.5 `cargo/utils.py`

```python
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")

def money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
```

Deliberate duplicate of `purchasing/utils.py` — see §5.1 step 6 for why.

### 5.6 `cargo/constants.py`

```python
from typing import Literal

CargoCostBasisCode = Literal["weight", "cbm", "piece"]
```

---

## 6. API surface (`backend/src/cargo/router.py`)

| Method | Path | Backing | Notes |
|---|---|---|---|
| GET | `/cargo/modes` | `build_crud_router(CargoMode, ...)` | paginated |
| POST | `/cargo/modes` | ″ | |
| GET | `/cargo/modes/{id}` | ″ | |
| PUT | `/cargo/modes/{id}` | ″ | |
| DELETE | `/cargo/modes/{id}` | ″ | soft delete |
| GET | `/cargo/cost-bases` | `build_crud_router(CargoCostBasis, ...)` | paginated |
| POST | `/cargo/cost-bases` | ″ | |
| GET/PUT/DELETE | `/cargo/cost-bases/{id}` | ″ | |
| POST | `/cargo/shipments` | `service.create_shipment` | 201, runs the allocation (§5.1) |
| GET | `/cargo/shipments` | `service.list_shipments` | paginated |
| GET | `/cargo/shipments/{id}` | `Depends(valid_cargo_shipment)` | includes `allocations` |

Structured exactly like `purchasing/router.py`: two `build_crud_router` sub-routers for the lookups, one hand-written `APIRouter(prefix="/shipments", tags=["cargo"])` for the transactional entity, combined under a bare `router = APIRouter()` that `main.py` mounts at `/cargo`.

### 6.1 `main.py`

```python
from src.cargo.router import router as cargo_router
...
app.include_router(cargo_router, prefix="/cargo")
```

(Sub-routers already carry `tags=["cargo"]`, same comment pattern as the existing `purchasing_router`/`payments_router` lines.)

---

## 7. Migration

One Alembic revision, `alembic revision --autogenerate`, reviewed by eye (per `CLAUDE.md` §2.5 — autogenerate is known to miss `Numeric` precision details). Expected diff:

- `CREATE TABLE cargo_mode` (`id`, `name` unique, `is_active`)
- `CREATE TABLE cargo_cost_basis` (`id`, `name` unique, `code` unique, `is_active`)
- `CREATE TABLE cargo_shipment` (`id`, `cargo_agent_id` FK, `cargo_mode_id` FK, `cost_basis_id` FK, `shipment_date`, `total_cost_pkr`, `created_at`)
- `CREATE TABLE cargo_allocation` (`id`, `cargo_shipment_id` FK, `purchase_order_line_id` FK unique, `basis_value` `Numeric(12,4)`, `allocated_cost_pkr` `Numeric(12,2)`, `created_at`)
- `ALTER TABLE purchase_order_line ADD COLUMN landed_cost_pkr NUMERIC(12,2) NULL`

File name: `2026-08-07_add_cargo_shipment.py` (or the actual implementation date, date-prefixed per `CLAUDE.md` §2.1) — one migration for the whole phase, not one per table.

---

## 8. Seed data (`backend/scripts/seed.py`)

Extend the existing script — same pattern as `seed_payment_methods`:

```python
STARTER_CARGO_MODES = ["Sea", "Air"]
STARTER_CARGO_COST_BASES = [("Weight", "weight"), ("CBM", "cbm"), ("Piece", "piece")]

async def seed_cargo_modes(session) -> None: ...   # mirrors seed_payment_methods exactly
async def seed_cargo_cost_bases(session) -> None: ...  # same, but inserts (name, code) pairs
```

Called from `main()` alongside the existing seed calls. No seed needed for a `cargo_agent` `Party` — that's real vendor/agent data, seeded manually through the existing `Party` CRUD like any other party (the script's `--vendor-name` flag already sets a precedent: don't fabricate real business contacts in a seed script).

---

## 9. Out of scope / open questions for later

- **No re-allocation or undo.** Once a shipment's `create_shipment` call succeeds, its allocations and the POs' `landed_cost_pkr`/`status` are final in this phase. Fixing a data-entry mistake (wrong total cost, wrong basis figure) has no endpoint yet — would need a `DELETE /cargo/shipments/{id}` that reverses the PO status and clears `landed_cost_pkr`, deliberately deferred rather than rushed into this phase.
- **No update/delete on `CargoShipment`** at all — matches `PurchaseOrder`'s existing precedent (create + list + get only).
- **Partial shipments** (a PO where only some lines have landed and others are still awaiting a second shipment) are explicitly not modeled — §2.1's whole-PO attachment makes this impossible by construction. If that turns out to be a real business need, it changes the attachment unit from PO to line and reopens the status-transition design in §2.1.
- **Cargo agent role assignment** requires no new code — create the agent through the existing `POST /parties` with `roles: ["cargo_agent"]`, same as any `china_vendor`.

---

## 10. Implementation checklist

New:
- `backend/src/cargo/__init__.py`
- `backend/src/cargo/models.py` — `CargoMode`, `CargoCostBasis`, `CargoShipment`, `CargoAllocation`
- `backend/src/cargo/schemas.py`
- `backend/src/cargo/constants.py`
- `backend/src/cargo/exceptions.py`
- `backend/src/cargo/dependencies.py`
- `backend/src/cargo/service.py`
- `backend/src/cargo/utils.py`
- `backend/src/cargo/router.py`
- `backend/migrations/versions/<date>_add_cargo_shipment.py`

Changed:
- `backend/src/purchasing/models.py` — `landed_cost_pkr` column on `PurchaseOrderLine`
- `backend/src/purchasing/constants.py` — widen `PurchaseOrderStatus`
- `backend/src/purchasing/schemas.py` — `landed_cost_pkr`/`amount_landed_pkr` on `PurchaseOrderLineRead`
- `backend/src/main.py` — mount `cargo_router`
- `backend/scripts/seed.py` — seed `CargoMode`/`CargoCostBasis` rows
