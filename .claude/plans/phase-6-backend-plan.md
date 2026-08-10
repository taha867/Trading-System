# Phase 6 Backend Implementation Plan — Payments

## Context

`PLAN.md` Phase 6 ("Payments") needs a `PaymentAccount` entity (concrete instances of Phase 0's `PaymentMethod` — "JazzCash · 0300-…", "Meezan Bank · 0123…", "Cash drawer") and a `PaymentTransaction` entity (direction in/out, amount, optional link to a party/invoice/PO/expense), with every transaction posting to `LedgerEntry` and an account-balances view. This was designed in detail in `.claude/specs/phase-6-backend.md`, which was written after reading the actual current code. This plan turns that spec into exact file changes, verified against the literal current contents of every file it touches and reviewed by a design-check pass that caught two real gaps in the spec before implementation:

1. `ledger/service.py::post_entry`'s real signature had no `payment_account_id` parameter — the spec's §5.5 claim that it "already accepts" one was wrong. Fixed by adding the parameter.
2. `payments/` had no `utils.py` (every other domain — `purchasing`, `sales`, `cargo`, `inventory` — has its own local `money()` rounding helper). Added.

A third issue was caught during live verification, after implementation (not in the spec or the initial plan): `get_account_balances`'s first draft computed `balance = account.opening_balance + ledger_sum`, which double-counts the opening balance, because `create_payment_account` already posts the opening balance as a ledger row (with `payment_account_id` set) — that row is already inside `ledger_sum`. Fixed by dropping the extra `+ account.opening_balance` term; balance is just the ledger sum. Confirmed by an end-to-end functional test (create account with `opening_balance=1000` → balance was `2000`, not `1000`) before the fix, and `1000` after.

While chasing that bug, **a real, pre-existing defect was found in `parties/service.py::get_party_statement`** (out of scope for this phase — not fixed here): it seeds `running` from `party.opening_balance` and then also sums every `LedgerEntry` for that party, which *includes* the "Party Opening Balance" entry `create_party` posts — so any party with a nonzero `opening_balance` has its statement balance inflated by that amount. Confirmed against live data: party id 2 ("Test Vendor A", `opening_balance=50000.00`) shows a `+50000` jump in its own statement at the "Party Opening Balance" line, on top of the `opening_balance` the statement already started from. This bug predates Phase 6 and affects every party with a nonzero opening balance today — worth a follow-up fix, but not part of this phase's scope (`parties/service.py` is explicitly unmodified by this plan) and is called out here rather than silently repeated in `payments/`.

The core design, unchanged from the spec: `PaymentAccount` is hand-written (not generic-CRUD) because creating one with a nonzero `opening_balance` must post a `LedgerEntry`, mirroring why `Party` itself is hand-written. `PaymentTransaction` posts **one** ledger row always (the "account leg," signed for the account's own point of view: debit = cash in, credit = cash out) and a **second** row only when a party is linked (the "party leg," signed the *opposite* way — credit reduces a receivable on `direction="in"`, debit reduces a payable on `direction="out"`), hand-traced through two concrete examples and confirmed self-consistent with `parties/service.py::get_party_statement`'s `running += debit - credit` sign convention. A new nullable `payment_account_id` FK on `LedgerEntry` (mirroring the existing `party_id` column) is what lets `get_account_balances` do a SQL-side `GROUP BY` sum for the "account balances view," rather than copying `get_party_statement`'s Python-loop-over-full-history shape.

Full design rationale lives in `.claude/specs/phase-6-backend.md`.

---

## Files created

- `backend/src/payments/constants.py` — `PaymentDirection = Literal["in", "out"]`; `PaymentReferenceType = Literal["sales_order", "purchase_order", "expense"]` (loose, non-FK-validated, mirrors `LedgerEntry.reference_type`/`reference_id`).
- `backend/src/payments/exceptions.py` — `PaymentAccountNotFound(NotFoundException)`.
- `backend/src/payments/utils.py` — `money()`, the same `ROUND_HALF_UP` 2dp helper every other domain defines locally.
- `backend/src/payments/service.py` — `get_active_payment_account`, `get_payment_transaction`, `list_payment_accounts`, `create_payment_account` (posts opening-balance ledger row, mirrors `create_party`), `update_payment_account`, `soft_delete_payment_account`, `get_account_balances` (SQL `GROUP BY payment_account_id` sum — **not** `opening_balance + sum`, see Context), `create_payment_transaction` (posts one or two ledger rows per §2.3 of the spec), `list_payment_transactions`.
- `backend/src/payments/dependencies.py` — `valid_payment_account`, `valid_payment_transaction` (fetch-or-404, mirror `parties/dependencies.py::valid_party` and `cargo/dependencies.py::valid_cargo_shipment`).
- `backend/migrations/versions/2026-08-09_add_payments.py` — revision `b7a2e491f3c8`, `down_revision='943d3cd058b8'`. Creates `payment_account`, `payment_transaction`; adds `ledger_entry.payment_account_id` (nullable FK + index). Naming follows `POSTGRES_INDEXES_NAMING_CONVENTION` by hand (`{table}_{column}_idx`, `{table}_{column}_fkey`), verified against how `party_id`'s own index/FK on `ledger_entry` were named in an earlier migration.

## Files changed

- `backend/src/payments/models.py` — added `PaymentAccount`, `PaymentTransaction` alongside the existing `PaymentMethod`.
- `backend/src/payments/schemas.py` — added `PaymentAccountCreate/Read/Update`, `PaymentAccountBalanceRead`, `PaymentTransactionCreate` (with a `model_validator` requiring `reference_type`/`reference_id` together), `PaymentTransactionRead`. `PaymentMethod*` schemas untouched.
- `backend/src/payments/router.py` — restructured from a single `build_crud_router(...)` call into three combined sub-routers (`payment_method_router` unchanged/generic, new hand-written `payment_account_router` and `payment_transaction_router`), combined via `router.include_router(...)` three times — the exact pattern `cargo/router.py` already uses. `GET /payment-accounts/balances` is declared **before** `GET /payment-accounts/{account_id}` in source order (verified via the app's generated OpenAPI schema — both routes register and resolve correctly; `/balances` does not get shadowed).
- `backend/src/ledger/models.py` — added `payment_account_id: Mapped[int | None]` FK to `payment_account.id`, nullable, indexed — same shape as the existing `party_id` column.
- `backend/src/ledger/service.py` — `post_entry` gained a keyword-only `payment_account_id: int | None = None` parameter, forwarded into `LedgerEntry(...)`. Additive only; no existing caller (`purchasing`, `sales`, `parties`) passes it, so nothing else changed behavior.
- `backend/migrations/env.py` — `from src.payments.models import PaymentMethod` → `from src.payments.models import PaymentAccount, PaymentMethod, PaymentTransaction`, so `Base.metadata` sees the new tables for any future autogenerate diff.
- `backend/scripts/seed.py` — added `STARTER_PAYMENT_ACCOUNTS` and `seed_payment_accounts()` (one `PaymentAccount` per starter `PaymentMethod`), wired into `main()` right after `seed_payment_methods()` with an intervening `await session.flush()` so the new `PaymentMethod` rows have ids before being looked up in the same uncommitted session.

## Not changed

`backend/src/main.py` (`/payments` already mounted, router object still named `router`), `backend/src/crud.py`, `backend/src/parties/*`, `backend/src/purchasing/*`, `backend/src/sales/*`, `backend/src/cargo/*`, `backend/src/inventory/*`, `backend/src/ledger/schemas.py` (`LedgerEntryRead` stays without `payment_account_id` — unused elsewhere today, consistent with there being no per-account statement/drill-down endpoint yet).

---

## Verification performed

1. **Syntax**: `python -m py_compile` on every new/changed file — clean.
2. **Migration**: `alembic upgrade head` from a real head of `943d3cd058b8` applied cleanly (`payment_account`, `payment_transaction`, `ledger_entry.payment_account_id` all created). `alembic downgrade -1` then `alembic upgrade head` confirmed the downgrade path is also clean.
3. **App boot**: `from src.main import app` imports with no errors; `app.openapi()` shows all expected routes, including confirming `/payments/payment-accounts/balances` resolves ahead of `/payments/payment-accounts/{account_id}`.
4. **Functional, end-to-end, against the real dev database** (via direct service-layer calls, since `httpx`/`TestClient` isn't installed in this env):
   - Created a `PaymentAccount` with `opening_balance=1000.00` → `get_account_balances` returned `1000.00` (after the double-count fix — it returned `2000.00` before).
   - Posted a `direction="out"`, `amount=500.00` transaction linked to an existing vendor `Party` (id 2) → account balance dropped to `500.00`; that party's `get_party_statement` `closing_balance` increased by exactly `500.00` (their payable reduced), and the new statement entry showed `account="Accounts Payable", debit=500.00`.
   - Posted a `direction="in"`, `amount=250.00` transaction with **no** `party_id` → account balance rose to `750.00`; the vendor's party statement was unaffected (confirming the account leg and party leg don't cross-contaminate).
   - All test rows (the payment account, both transactions, and their ledger entries) were deleted afterward to leave the dev database exactly as found; confirmed the vendor's statement balance returned to its original value.

This confirms the double-entry sign convention from the spec (§2.3) is correct in practice, not just on paper, and that the FastAPI route-ordering fix works.

## Follow-up (not part of this phase, flagged for later)

`parties/service.py::get_party_statement` double-counts `opening_balance` for any party where it's nonzero (see Context above). Worth its own small fix — likely either not seeding `running` from `party.opening_balance` and relying entirely on the ledger rows (which already include the opening-balance entry), or excluding the opening-balance entry from the `rows` loop — but that's a decision for whoever owns `parties/` next, not bundled into this phase.
