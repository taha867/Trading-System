# Phase 5 Backend Implementation — Local Vendors

## Context

`PLAN.md` Phase 5 ("Local vendors") adds `local_vendor` as a third `Party` role and lets the same party be a purchase-order vendor on one order and a sales-order customer on another, with one ledger balance. The full design was already worked out and written to `.claude/specs/phase-5-backend.md` in a prior turn (read against the live codebase, citing exact files/lines). This plan executes that spec, with four corrections found by an adversarial design review run just now (which executed the spec's Pydantic snippets against the repo's actual venv and re-verified every file/line citation) and one explicit deviation decision.

**Key discovery driving the whole design:** `cargo/service.py`'s existing "PO must be `status == 'draft'`" gate and `inventory/service.py`'s existing "line must have `landed_cost_pkr`" gate are *already sufficient* to keep local-sourced purchase orders out of the cargo-allocation flow and straight into stock receiving — if a local PO is created directly with `status="allocated"` and `landed_cost_pkr` pre-set to its PKR rate. This means **`cargo/` and `inventory/` need zero code changes** (confirmed twice now, independently). Everything lives in `purchasing/`, plus one new helper in `parties/service.py` and a one-line role-check widening in `sales/service.py`.

**Scope note:** this is backend-only, per the user's request. The review surfaced that the frontend (party-role dropdown filters, the PO form's hardcoded `rate_rmb`-only fields, `CurrencyAmount`'s `¥0.00` rendering of a `null` RMB rate) cannot exercise this yet — that's expected and out of scope here; a phase-5-frontend spec is a separate follow-up, not silently bundled into this task.

---

## Corrections applied on top of the original spec

1. **`PurchaseOrderRead.total_rmb` keys on the data, not on `source`.** The spec's `if self.source == "local": return None` breaks (`TypeError` inside response serialization → 500) the moment any china-sourced order has a line with a NULL `rate_rmb` (a hand fix, a future edge case) — because `rate_rmb` is nullable at the column level now, not just for local orders. Fix: compute the list of `amount_rmb` values first; return `None` if any is `None`, else sum them. Same fix applies conceptually to nothing else — `amount_rmb` on the line schema already returns `None`/value correctly per-line.
2. **Local line rates go through `money()` before being stored**, on both `rate_pkr` and `landed_cost_pkr`. The spec's original service code assigned the client's raw `Decimal` straight through; `Field(decimal_places=2)` accepts values with *fewer* than 2 dp (e.g. `500.5`), so the 201 response would echo `"500.5"` while a subsequent `GET` reads back `"500.50"` from the `Numeric(12,2)` column — a response that disagrees with itself. The china branch never had this bug because `rate_pkr` there is always the output of `money(rate_rmb * rate)`.
3. **Migration mechanics**: use `alembic revision -m "add_purchase_order_source"` (no `--autogenerate`, since generating against a live DB isn't available/needed here) to get a correctly-chained revision id off the confirmed head `f5f369972f38`, then hand-write the two `op.add_column`/`op.alter_column` calls (template: `2026-08-07_add_cargo_shipment.py`'s `op.add_column(...)` shape, not `2026-08-08_add_sales.py`, which is all `create_table`). Rename the file to `2026-08-08_add_purchase_order_source.py` (repo convention), keep the `revision:`/`down_revision` header values from the generated file untouched. Keep `server_default='china'` permanently (not just for backfill) so the model and future autogenerates stay in agreement. Comment the `downgrade()`'s `alter_column(..., nullable=False)` as lossy/will-fail-if-local-POs-exist, since that's inherent and expected, not a bug to fix.
4. **Validation error includes the offending line index** (`f"line {i}: ..."`) rather than a bare model-level message — cheap, and makes a 422 on a multi-line PO actionable.

### Explicit deviation decision: harden `cargo/service.py`'s draft gate

The spec's enforcement of "local POs never go through cargo" is entirely the existing `status == "draft"` check — correct today, but fragile: if any future code path ever resets a PO's status back to `"draft"` (a reopen/correction flow, not planned now but not impossible), a local PO would silently become attachable to a shipment, and `cargo/service.py` would overwrite its `landed_cost_pkr` with a wrong (freight-inflated) value with no error raised. This is real-money-wrong, not cosmetic.

**Decision: add the one-clause belt-and-suspenders check anyway**, consistent with this codebase's own established preference for fail-fast validation before mutation (the same reasoning `inventory.consume_stock_fifo`'s upfront sufficiency check already documents in its own comment). Change `cargo/service.py`'s gate from checking only `status != "draft"` to also rejecting `source == "local"` explicitly, and reword the exception message (currently *"already allocated to a shipment"*, which is factually wrong for a PO that was never on one). This is a two-line change to one existing conditional plus a string — it does not reintroduce any of the schema/service branching the spec otherwise keeps entirely inside `purchasing/`.

---

## Files to change

### `backend/src/purchasing/constants.py` (currently 8 lines)
Add, after the existing `PurchaseOrderStatus`:
```python
# "china" orders go through the existing RMB/exchange-rate + cargo-allocation flow;
# "local" orders are quoted directly in PKR and skip both — see .claude/specs/phase-5-backend.md §2.
PurchaseOrderSource = Literal["china", "local"]
```

### `backend/src/purchasing/models.py`
- `PurchaseOrder` (class body around line 19-33): add `source: Mapped[str] = mapped_column(default="china", server_default="china")` alongside the existing `status` column.
- `PurchaseOrderLine.rate_rmb` (line 43): change from `Mapped[Decimal] = mapped_column(Numeric(12, 2))` to `Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)` — matches this file's existing style for `landed_cost_pkr` (line 45) and `parties/models.py`'s `contact`/`address`.

### `backend/src/purchasing/schemas.py`
- Add `model_validator` to the pydantic import line (line 5) and `from src.purchasing.constants import PurchaseOrderSource`.
- `PurchaseOrderLineCreate` (lines 26-29): `rate_rmb` becomes `Annotated[Decimal, Field(gt=0, decimal_places=2)] | None = None`; add `rate_pkr: Annotated[Decimal, Field(gt=0, decimal_places=2)] | None = None`.
- `PurchaseOrderLineRead` (lines 32-55): `rate_rmb: Decimal | None = None`; `amount_rmb` computed field returns `Decimal | None`, `None` when `self.rate_rmb is None`.
- `PurchaseOrderCreate` (lines 58-61): add `source: PurchaseOrderSource = "china"`; add `@model_validator(mode="after")` enforcing, per line (with index in the error message per correction 4): china → `rate_rmb` set and `rate_pkr` unset; local → `rate_pkr` set and `rate_rmb` unset.
- `PurchaseOrderRead` (lines 64-81): add `source: PurchaseOrderSource`; `total_rmb` computed field rewritten per correction 1 (key on whether any line's `amount_rmb` is `None`, not on `source`).

### `backend/src/purchasing/service.py`
`create_purchase_order` (lines 23-85):
- Role check (line 28): branch — `required_role = PartyRole.CHINA_VENDOR if payload.source == "china" else PartyRole.LOCAL_VENDOR`, then the existing `ensure_role(vendor, required_role)` call (exact-match role check is intentional here — a china/local mismatch against the vendor's actual role(s) must hard-fail, not soft-match; this is *not* a place for the new `ensure_any_role`).
- Exchange-rate lookup (lines 30-37): only run for `source == "china"`; `rate_row = None` otherwise.
- Item-id validation (lines 39-48): unchanged verbatim, applies to both sources.
- Line-building loop (lines 50-60): branch per line — china computes `rate_pkr = money(line.rate_rmb * rate_row.rate)` as today; local computes `rate_pkr = money(line.rate_pkr)` and sets `landed_cost_pkr=rate_pkr` directly (correction 2 — both fields get the `money()`-rounded value, not the raw client input).
- `PurchaseOrder(...)` construction (line 65): add `source=payload.source`, and `status="allocated" if payload.source == "local" else "draft"` with a code comment explaining the reuse of `cargo/service.py`'s existing draft-gate as the enforcement mechanism (now hardened per the deviation decision above).
- Everything else (ledger post, commit/rollback, return) — unchanged.

No changes to `purchasing/router.py`, `purchasing/dependencies.py`, or `purchasing/exceptions.py` — confirmed no caller of any changed symbol lives there.

### `backend/src/parties/service.py`
Insert directly after `ensure_role` (lines 31-34), before `list_parties` (line 37):
```python
def ensure_any_role(party: Party, roles: tuple[PartyRole, ...]) -> Party:
    if not any(role.value in party.roles for role in roles):
        names = " or ".join(role.value for role in roles)
        raise PartyRoleMismatch(f"Party {party.id} does not hold any of: {names}")
    return party
```
No import changes needed — `PartyRole` and `PartyRoleMismatch` are already imported in this file.

### `backend/src/sales/service.py`
Line 25: change
```python
parties_service.ensure_role(customer, PartyRole.CUSTOMER)
```
to
```python
parties_service.ensure_any_role(customer, (PartyRole.CUSTOMER, PartyRole.LOCAL_VENDOR))
```
Nothing else in this function changes.

### `backend/src/cargo/service.py` (the one deviation from "spec says zero changes")
Line 47-48's gate — currently:
```python
if line.purchase_order.status != "draft":
    raise PurchaseOrderNotOpen(f"Purchase order {line.purchase_order_id} is already allocated to a shipment")
```
becomes:
```python
if line.purchase_order.source == "local" or line.purchase_order.status != "draft":
    raise PurchaseOrderNotOpen(
        f"Purchase order {line.purchase_order_id} cannot be attached to a cargo shipment "
        "(local-sourced orders skip cargo entirely; china-sourced orders must be in 'draft' status)"
    )
```
And `cargo/exceptions.py`'s `PurchaseOrderNotOpen.detail` class-level default (line 10, currently *"One or more attached purchase orders are already allocated to a shipment"*) gets reworded to something source-neutral, since the per-call message above now always overrides it anyway but the default should stop being actively wrong.

### `backend/migrations/versions/<new file>`
New file `2026-08-08_add_purchase_order_source.py` (or the next available date-slug if run on a later date), generated via `alembic revision -m "add_purchase_order_source"` off head `f5f369972f38`, then hand-edited:
```python
def upgrade() -> None:
    op.add_column(
        "purchase_order",
        sa.Column("source", sa.String(), nullable=False, server_default="china"),
    )
    op.alter_column(
        "purchase_order_line", "rate_rmb",
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=True,
    )


def downgrade() -> None:
    # Will raise IntegrityError if any local-sourced PO line exists with rate_rmb NULL —
    # expected: a downgrade past this point requires resolving those rows manually first.
    op.alter_column(
        "purchase_order_line", "rate_rmb",
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=False,
    )
    op.drop_column("purchase_order", "source")
```

---

## Not changed (confirmed by two independent reads of the live code)

`backend/src/inventory/*` (entirely), `backend/src/purchasing/router.py`/`dependencies.py`/`exceptions.py`, `backend/src/sales/router.py`/`schemas.py`/`dependencies.py`/`exceptions.py`, `backend/src/parties/router.py`/`dependencies.py`/`schemas.py`/`exceptions.py`, `backend/src/main.py`, `backend/src/cargo/models.py`/`schemas.py`/`dependencies.py`/`exceptions.py` (only `service.py`'s one gate changes, per the deviation decision).

---

## Verification

1. **Static check**: run `ruff check backend/src` (per `backend/requirements/dev.txt` tooling already in this repo) to catch import/syntax issues before touching a DB.
2. **Migration review by eye** (`CLAUDE.md` §2.5's explicit requirement): confirm the hand-written `upgrade()`/`downgrade()` match the model changes exactly — `Numeric(12,2)` precision preserved, `server_default` string-quoted correctly.
3. **Apply the migration** against the dev DB (`alembic upgrade head`) and confirm `\d purchase_order` / `\d purchase_order_line` in `psql` show the new `source` column and the now-nullable `rate_rmb`.
4. **Manual API walkthrough** (mirrors spec §8), using the running FastAPI app (`uvicorn` per this repo's existing dev setup) and its `/docs` Swagger UI or `curl`:
   - Create a `Party` with `roles: ["local_vendor"]` (optionally also `"customer"`).
   - `POST /purchasing/purchase-orders` with `source: "china"` and no `rate_pkr` on lines — confirm existing behavior is unchanged (exchange-rate lookup still required, still lands in `"draft"`).
   - `POST /purchasing/purchase-orders` with `source: "local"`, `party_id` = the local vendor, lines carrying `rate_pkr` and no `rate_rmb` — confirm 201, `status: "allocated"`, `landed_cost_pkr` already set per line, `total_rmb: null` in the response.
   - Attempt `POST /cargo/shipments` attaching that local PO's line — confirm it's rejected with the reworded `PurchaseOrderNotOpen`.
   - `POST /inventory/stock-lots` receiving that local PO's line directly (no cargo step) — confirm it succeeds and the PO flips to `"received"`.
   - `POST /sales/sales-orders` selling to that same local-vendor party — confirm the widened role check accepts it (previously would have raised `PartyRoleMismatch`).
   - `GET /parties/{id}/statement` — confirm both the payable-side (purchase) and receivable-side (sale) ledger entries appear against one balance.
   - Send a `source: "china"` line with `rate_pkr` also set (or a `source: "local"` line with `rate_rmb` also set) — confirm a 422 with the per-line indexed error message.
5. **Save this plan** to the project's own `.claude/plans/phase-5-backend-plan.md` (matching the existing convention of `phase-0-backend-plan.md` … `phase-3-backend-plan.md` already in that folder) as the first implementation step, once plan mode exits — the harness's plan-mode file above is a side effect of the workflow, not the durable copy the user asked for.

---

## Explicitly out of scope for this task

Frontend changes (party-role dropdown filters in `partyQueries.js`, the PO form's `rate_rmb`-only fields, `CurrencyAmount`'s handling of a `null` RMB rate) — the backend will be fully correct and testable via the API/Swagger UI per step 4 above, but the feature isn't reachable through the existing UI until a phase-5-frontend pass happens separately.
