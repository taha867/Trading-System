# Phase 2 Backend — Implementation Plan (executed)

## Context

`PLAN.md` defines Phase 2 ("Cargo & landed cost") and `.claude/specs/phase-2-backend.md` contains the full design for it — a new `cargo/` domain package (`CargoMode`/`CargoCostBasis` dynamic lookups, `CargoShipment`/`CargoAllocation` hand-written transactional entities), a proportional freight-cost split algorithm, and the changes it required in `purchasing/` (`PurchaseOrderLine.landed_cost_pkr`, widened `PurchaseOrderStatus`). Phase 0/1 (auth, ledger, generic CRUD, catalog, purchasing) were already built and confirmed unchanged from the spec's assumptions before implementation started.

Before writing code, the spec's `create_shipment` design was independently validated against the actual installed stack (FastAPI 0.141.1, Pydantic 2.13.4, SQLAlchemy 2.0.51, asyncpg 0.31.0) and this codebase's established transaction pattern. **Unlike Phase 1's review, no runtime-breaking bug was found** — the spec already anticipated the one real risk (`db.refresh()` doesn't reload a `lazy="raise"` relationship). This plan executed the spec with one genuine simplification and reached the spec's "done when": a shipment's freight cost is visibly split across the items in it, and each PO line shows a landed cost, not just its RMB rate. **Status: complete and verified** — see the verification section below for the full walkthrough with real numbers.

## Simplification made relative to the spec

The spec's own `create_shipment` pseudocode flushed for `shipment.id`, built `CargoAllocation` rows referencing that id, then (since `CargoShipment.allocations` is `lazy="raise"`) re-fetched the shipment through `valid_cargo_shipment`'s `selectinload` before returning, to avoid `db.refresh()`'s inability to populate a `lazy="raise"` relationship. Implemented instead: build the `CargoAllocation` list in Python first, then construct `CargoShipment(..., allocations=allocations)` and pass it through the relationship constructor — the exact pattern `purchasing.service.create_purchase_order` already uses for `PurchaseOrder(..., lines=lines)`. This sets `cargo_shipment_id` on each allocation automatically at flush time, keeps `shipment.allocations` populated in memory (`expire_on_commit=False` means it's never discarded), and needs neither the mid-function `flush()` nor the end-of-function re-fetch — `create_shipment` returns the same in-memory `shipment` object straight after `commit()`. One fewer DB round trip than the spec, same correctness guarantee.

Two smaller nits caught during the pre-implementation design review were folded straight into the implementation (not corrections, just spec polish): dropped the redundant `.join(PurchaseOrder)` in the line-fetch query (`selectinload` eager-loads via its own batched query; the join added nothing), and added an explicit `.order_by(PurchaseOrderLine.id)` to that same query (the remainder-correction rounding depends on deterministic line order, and the spec's query snippet didn't show one).

One thing the spec's checklist missed: `migrations/env.py` imports every domain's models module explicitly for autogenerate — `src.cargo.models` needed adding to that list, done as part of the migration step.

## One deliberate deviation from the plan's stated expectation

The plan's verification section expected `422` for a missing/inactive `CargoMode`/`CargoCostBasis`. The implementation instead raises the shared `src.exceptions.NotFoundException` (404) for both — the same class `src/crud.py`'s generic CRUD factory already uses for "referenced row doesn't exist." This is more consistent with the rest of the codebase than the plan's own guess, and was kept as implemented rather than forced to match the plan's 422 assumption. `422` is reserved in `cargo/exceptions.py` for genuine business-rule violations (`PurchaseOrderNotOpen`, `MissingBasisValue`) where the referenced row does exist but the request is invalid regardless.

## Build order (as executed)

### 1. `src/cargo/` (spec §3, §4, §5, §6)

`src/cargo/{__init__,constants,models,exceptions,utils,schemas,dependencies,service,router}.py` built following `purchasing/`'s shape as the template. `CargoMode`/`CargoCostBasis` are plain generic-CRUD lookups (`CargoCostBasis` carries a pinned `code: Literal["weight","cbm","piece"]` alongside its editable `name`, per the spec's §2.2 design call — the split algorithm branches on `code`, never on the user-editable `name`). `CargoShipment`/`CargoAllocation` are hand-written, mirroring `PurchaseOrder`/`PurchaseOrderLine`'s relationship shape exactly (`cascade="all, delete-orphan"`, `lazy="raise"`). `cargo_allocation.purchase_order_line_id` is a **unique** FK — one shipment per line, DB-enforced. `service.create_shipment` validates in order: active `cargo_agent`-role party → active `CargoMode` → active `CargoCostBasis` → fetch every line under the requested `purchase_order_ids` (ordered by `id`, eager-loading `.purchase_order`) → every requested PO id must have yielded a line → every line's PO must be `"draft"` → resolve `basis_value` per line (branch on `cost_basis.code`) → proportional split with `money()` rounding and last-line remainder correction → flip every touched PO to `"allocated"` → one `commit()` (`IntegrityError` → `ConflictException`). Mounted in `main.py` as `/cargo`.

### 2. `src/purchasing/` changes (spec §3.2, §3.3, §4.5)

`models.py` — added `landed_cost_pkr: Mapped[Decimal | None]` (`Numeric(12,2)`, nullable) to `PurchaseOrderLine`. `constants.py` — widened `PurchaseOrderStatus = Literal["draft", "allocated"]`, comment updated to explain the transition lives in `cargo.service.create_shipment`, not here. `schemas.py` — `PurchaseOrderLineRead` gained `landed_cost_pkr` and a computed `amount_landed_pkr` (mirrors `amount_pkr`, `None` while unallocated). No changes to `service.py`/`router.py`/`dependencies.py` — `cargo/service.py` reads/writes `PurchaseOrder`/`PurchaseOrderLine` directly, a one-directional dependency matching `purchasing`'s existing shape toward `parties`.

### 3. Migration

`migrations/env.py` — added the `src.cargo.models` import (ruff's import-sort auto-fix reordered the block on save). `alembic revision --autogenerate -m "add cargo shipment and landed cost"` produced a clean diff on the first try: `cargo_mode`, `cargo_cost_basis` (with both `name` and `code` unique constraints), `cargo_shipment`, `cargo_allocation` (with the unique index on `purchase_order_line_id`), plus `purchase_order_line.landed_cost_pkr` — correct `Numeric(12,4)` on `basis_value`, correct FK/unique naming via the shared naming convention. Renamed to `migrations/versions/2026-08-07_add_cargo_shipment.py`; `alembic upgrade head` applied cleanly on top of Phase 0/1's schema.

### 4. Seed script (spec §8)

`scripts/seed.py` extended with `seed_cargo_modes` (`["Sea", "Air"]`) and `seed_cargo_cost_bases` (`[("Weight","weight"), ("CBM","cbm"), ("Piece","piece")]`), both following `seed_payment_methods`'s exact idempotent shape, called from `main()`. No cargo-agent party seeded — real business data, created manually through the existing `POST /parties`, same reasoning already applied to `--vendor-name`.

## Verification — all passed, against the already-running dev server (`--reload`, picked up every change live)

1. `ruff check` on every new/edited file — clean except one pre-existing `DTZ011` (`date.today()`) finding in `seed.py`, unrelated to this phase's edits (same finding Phase 1 already left as-is).
2. `alembic upgrade head` — clean on top of Phase 0/1's schema.
3. `python -m scripts.seed --username phase2_admin ... --vendor-name "Shenzhen Accessories Co."` — created the cargo modes/cost bases; re-running confirmed full idempotency ("already exists, skipping" for every row).
4. `GET /openapi.json` — `/cargo/modes`, `/cargo/cost-bases`, `/cargo/shipments` all present with correct tags/response models; confirmed `POST /cargo/shipments`' body schema has no leaked query params (`parameters: None`).
5. Generic CRUD on `CargoMode`/`CargoCostBasis` via direct calls: create, list, soft-delete (`DELETE` → `204`, item vanishes from the active list) all worked; a duplicate `code` on `CargoCostBasis` → `409` (`"CargoCostBasis already exists"`), not `500`.
6. **Piece-basis shipment**: PO with two lines (`qty=100`, `rate_rmb=5.00` → `rate_pkr=197.50`; `qty=50`, `rate_rmb=8.00` → `rate_pkr=316.00`), shipment `total_cost_pkr=3000`, `cost_basis=piece`. Result: `allocated_cost_pkr` = `2000.00` / `1000.00` (exact 100:50 ratio, sums to `3000.00`), PO status flipped to `"allocated"`, `landed_cost_pkr` = `217.50` (`197.50 + 2000.00/100`) and `336.00` (`316.00 + 1000.00/50`) — both matched hand-calculation exactly.
7. **Weight-basis shipment**: second PO (`qty=10`/`qty=10`), `total_cost_pkr=1000`, weights `3` and `7` entered manually → split `300.00`/`700.00` (proportional to the entered weights, not equal quantities) — confirmed the basis-value override path works independently of `qty`.
8. **Negative cases**, all clean 4xx, never 500: non-`cargo_agent` party as agent → `422`; missing `CargoMode`/`CargoCostBasis` id → `404` (see deviation note above); re-attaching an already-`"allocated"` PO → `422` (`"Purchase order 3 is already allocated to a shipment"`); weight-basis shipment missing a `basis_value` for one line → `422` (`"Line 9 needs a positive weight figure"`); piece-basis shipment with `line_basis_values` supplied anyway → `422` (`"Piece-basis shipments derive the split from qty — do not supply basis values"`).
9. `SELECT * FROM ledger_entry` — confirmed only `party_opening_balance`/`purchase_order` reference types exist; **zero** rows reference a cargo shipment, confirming Phase 2 posts nothing to the ledger per `PLAN.md`.
10. `POST`/`GET /cargo/shipments` without a bearer token → `401` on both.
11. `GET /cargo/shipments` (list) — both created shipments returned with `allocations` fully populated, no `lazy="raise"` error triggered.

## Known state left behind

Verification created real rows against the dev database beyond the seed script's output: one `Party` ("Fast Freight Logistics", `cargo_agent` role, id 6), three `PurchaseOrder`s with lines (ids 3–5, all now `"allocated"` or partially exercised), two `CargoShipment`s (ids 1–2) with their allocations, and one soft-deleted `CargoMode` ("Rail", id 3, `is_active=false`). These are genuine, correctly-behaving rows from exercising the new endpoints, not artifacts of a bug — left in place rather than deleted unprompted, same policy Phase 1's plan documented. If a clean slate is wanted before building the frontend against this API, drop and recreate the dev database (`docker compose down -v && docker compose up -d && alembic upgrade head && python -m scripts.seed ...`) rather than hand-deleting rows with FK dependencies between them.
