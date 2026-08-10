# Implement Phase 7 Backend — Expenses

## Context

`PLAN.md`'s Phase 7 ("Expenses") is fully designed in `.claude/specs/phase-7-backend.md` — a from-scratch backend domain (`ExpenseCategory`, `RecurringExpenseTemplate`, `Expense`) that lets a manual expense ("a lunch order") and a confirmed monthly recurring expense ("this month's rent") both land in the ledger, categorized, through the same posting path. This plan turns that spec into an ordered, verified set of file changes. The spec was cross-checked against the current repo by a design pass (Plan agent) and by direct reads of the critical files; one real gap was found beyond the spec (`migrations/env.py` doesn't know about the new models yet — see Step 8) and is folded in below. No frontend work is in scope. No test suite exists in this repo (no `tests/` dir, no `pytest` in `requirements/dev.txt`) — verification is manual, via a running server and `curl`, mirroring how every prior phase was verified.

Central design decision (already made in the spec, not re-litigated here): an `Expense` never posts its own `LedgerEntry`. It builds a `PaymentTransactionCreate` and calls the *existing* `payments.service.create_payment_transaction` — which is exactly what `payments/constants.py`'s `PaymentReferenceType = Literal["sales_order", "purchase_order", "expense"]` already anticipated in Phase 6. This means **zero changes to `ledger/` or `payments/`** — this phase is purely additive.

## Files to create

All under `backend/src/expenses/` (new package) plus one new migration. Full code for each is finalized in `.claude/specs/phase-7-backend.md` §3–§5, made concrete/copy-paste-ready by the design pass — content below is what actually gets written, not paraphrased.

1. **`backend/src/expenses/__init__.py`** — empty.

2. **`backend/src/expenses/models.py`** — three SQLAlchemy 2.0 `Mapped`/`mapped_column` classes:
   - `ExpenseCategory(Base)`: `id`, `name` (unique), `frequency` (plain `str`, "daily"/"monthly" enforced only in Pydantic — same convention as `purchasing.PurchaseOrder.status`, `backend/src/purchasing/models.py:26`), `is_active`.
   - `RecurringExpenseTemplate(Base)`: `id`, `name`, `category_id` (FK `expense_category.id`, indexed), `payment_account_id` (FK `payment_account.id`, indexed), `amount` (`Numeric(12,2)`), `day_of_month` (`int | None`, advisory only — never used to auto-trigger anything), `description` (`str | None`), `is_active`.
   - `Expense(Base)`: `id`, `category_id` (FK, indexed), `payment_account_id` (FK, indexed), `amount` (`Numeric(12,2)`), `expense_date` (`Date`), `description` (`str | None`), `status` (plain `str`, no column default — see rationale below), `recurring_template_id` (FK `recurring_expense_template.id`, nullable, indexed), `created_at` (server-default `now()`).
   - Deliberately **no `is_active` on `Expense`** — a confirmed expense is permanent history (matches `PaymentTransaction`'s own precedent of no `is_active`, no update route); a still-`"draft"` one is hard-deleted instead (Step "service.py" below) since it has posted nothing anywhere yet.

3. **`backend/src/expenses/constants.py`**:
   ```python
   ExpenseCategoryFrequency = Literal["daily", "monthly"]
   ExpenseStatus = Literal["draft", "confirmed"]
   ```
   Manual entries go straight to `"confirmed"`; only `RecurringExpenseTemplate`-generated ones start at `"draft"` and move to `"confirmed"` via `confirm_expense` — the one and only transition, documented in a comment the same way `purchasing/constants.py:1-8`'s `PurchaseOrderStatus` names which function performs each step.

4. **`backend/src/expenses/exceptions.py`**: `ExpenseNotFound`, `RecurringExpenseTemplateNotFound` (both `NotFoundException` subclasses, 404). A missing `ExpenseCategory` referenced by id stays a generic inline `NotFoundException("Expense category not found")` inside `service.py` — matching how `payments/service.py::create_payment_account` handles a missing `PaymentMethod` (no dedicated exception class for a plain referenced-lookup miss).

5. **`backend/src/expenses/schemas.py`**: `ExpenseCategoryCreate/Read/Update`, `RecurringExpenseTemplateCreate/Read/Update`, `ExpenseCreate`, `ExpenseRead` (no `ExpenseUpdate` — once posted, an expense isn't edited, matches `PaymentTransaction`). Money fields are `Annotated[Decimal, Field(gt=0, decimal_places=2)]`, matching every other domain's schemas (e.g. `payments/schemas.py:58`).

6. **`backend/src/expenses/dependencies.py`**: `valid_expense(expense_id, db)` and `valid_recurring_expense_template(template_id, db)` — thin fetch-or-404 dependencies, same shape as `payments/dependencies.py::valid_payment_account`.

7. **`backend/src/expenses/service.py`** — the core logic, one shared posting path used by two entry points:
   - `create_expense(db, payload)` — validates category + account, inserts `Expense(status="confirmed")`, flushes for its id, calls `_post_expense_payment`.
   - `_post_expense_payment(db, expense) -> PaymentTransaction` — builds `PaymentTransactionCreate(payment_account_id=expense.payment_account_id, direction="out", amount=expense.amount, transaction_date=expense.expense_date, reference_type="expense", reference_id=expense.id, note=expense.description)` and calls `payments_service.create_payment_transaction(db, payload)`. Its internal `db.commit()` is what atomically commits the `Expense` row too, since both are in the same `AsyncSession` before that call.
   - `confirm_expense(db, expense)` — 409 (`ConflictException`) unless `status == "draft"`; sets `status = "confirmed"` *before* calling `_post_expense_payment` so the mutation lands in the same commit.
   - `generate_expense_from_template(db, template, period)` — normalizes `period` to the 1st of its month, checks no `Expense` already exists for `(recurring_template_id, expense_date)` (409 if so — service-level idempotency check, not a DB constraint, matching this codebase's general preference for Python-level business rules over exotic multi-column constraints), inserts `Expense(status="draft", ...)`, commits — posts nothing to the ledger.
   - `discard_expense(db, expense)` — 409 unless `status == "draft"`; otherwise `await db.delete(expense)` + commit. **This is the first hard-delete anywhere in this codebase's service layer** (confirmed by grep: no `db.delete()`/`session.delete()` exists in any other `service.py` today — every other "delete" is `is_active = False`). Deliberate, not an oversight: a draft has zero downstream references (no `PaymentTransaction`, no `LedgerEntry` yet), so there's nothing for a soft-delete flag to protect.
   - Plus: `get_active_expense_category`, `get_expense`, `get_active_recurring_expense_template`, `list_expenses` (paginated, optional `category_id`/`payment_account_id`/`status` filters, ordered `expense_date.desc(), id.desc()` — mirrors `payments/service.py::list_payment_transactions`).

8. **`backend/migrations/env.py`** — **one-line addition, not in the original spec, required for autogenerate to see the new tables.** `env.py` explicitly imports every domain's models (lines 9-28) so `Base.metadata` is populated before Alembic diffs it — `src.main` (which wires routers) is never imported by the Alembic CLI, so without this line `alembic revision --autogenerate` would silently produce an empty/wrong migration. Insert alphabetically between the `catalog`/`config` imports and the `inventory` import:
   ```python
   from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate  # noqa: F401
   ```

9. **`backend/src/expenses/router.py`** — combines four sub-routers into one `router`, following `cargo/router.py:72-75`'s combining pattern:
   - `expense_category_router = build_crud_router(..., prefix="/expense-categories")` — fully generic.
   - `recurring_expense_template_router = build_crud_router(..., prefix="/recurring-expense-templates")` — fully generic CRUD.
   - `recurring_expense_generate_router = APIRouter(prefix="/recurring-expense-templates", ...)` — hand-written, **same prefix as the router above** (a new pattern for this codebase, called out explicitly in the spec §2.3 — no existing domain shares one prefix across two separately-built routers, but it works here because `POST /{template_id}/generate` and `GET/PUT/DELETE /{template_id}` never collide by path shape regardless of router registration order). Single route: `POST /{template_id}/generate` (optional `?period=` query param, defaults to today) → `ExpenseRead`, 201.
   - `expense_router = APIRouter(prefix="/entries", ...)` — hand-written: `GET ""` (list, paginated + filters), `POST ""` (create), `GET "/{expense_id}"`, `POST "/{expense_id}/confirm"`, `DELETE "/{expense_id}"`.
   - All four `router.include_router(...)`'d into one `router`.

## Files to change

- **`backend/src/main.py`** — one new import (`from src.expenses.router import router as expenses_router`, inserted alphabetically after `from src.exceptions import AppException`) and one new line (`app.include_router(expenses_router, prefix="/expenses")`), matching every other domain's exact one-line-per-domain wiring.

## Resulting API surface

| Method | Path | Behavior |
|---|---|---|
| GET/POST/PUT/DELETE | `/expenses/expense-categories[/{id}]` | generic CRUD |
| GET/POST/PUT/DELETE | `/expenses/recurring-expense-templates[/{id}]` | generic CRUD |
| POST | `/expenses/recurring-expense-templates/{id}/generate` | create this month's `draft` Expense (409 if already generated) |
| GET/POST | `/expenses/entries[?category_id=&payment_account_id=&status=]` | list / create (posts immediately, `status="confirmed"`) |
| GET | `/expenses/entries/{id}` | fetch |
| POST | `/expenses/entries/{id}/confirm` | draft → confirmed, posts the payment (409 if not draft) |
| DELETE | `/expenses/entries/{id}` | discard a draft only (409 if confirmed) — hard delete |

## Implementation order

Dependency-driven — each step needs the previous one to exist:
`__init__.py` → `models.py` → `constants.py` → `exceptions.py` → `schemas.py` → `service.py` → `dependencies.py` → `migrations/env.py` (needs `models.py`) → `router.py` (needs `service.py`, `dependencies.py`, `schemas.py`) → `main.py` → generate migration → apply migration → (optional) seed helper.

Migration generation is a command, not a hand-written file: `./.venv/bin/alembic revision --autogenerate -m "add_expenses"` from `backend/`, with `env.py` already updated (Step 8) so it sees the three new tables. Review the generated file by eye against the expected DDL (three `CREATE TABLE`s in FK order: `expense_category`, then `recurring_expense_template`, then `expense`; new indexes on every FK column) before running `./.venv/bin/alembic upgrade head` — per `CLAUDE.md` §2.5's "autogenerate misses some constraint changes... reviewed by eye" rule. Chains from the confirmed current head `b7a2e491f3c8` (`migrations/versions/2026-08-09_add_payments.py`).

## Verification

No automated test suite exists in this repo — verify by running the real server and exercising every new endpoint with `curl`, using the already-documented dev workflow (`backend/credentials.md`):

```bash
cd backend
docker compose up -d
./.venv/bin/alembic upgrade head
./.venv/bin/python -m scripts.seed --username admin --password 'ChangeMe123!' --rate 39.50
./.venv/bin/uvicorn src.main:app --reload --port 8001
```

In a second terminal, log in (`POST /auth/login` with `{"username":"admin","password":"ChangeMe123!"}` per `auth/schemas.py::LoginRequest`) to get a bearer token, then find a seeded `PaymentAccount` id via `GET /payments/payment-accounts`. Then walk the full lifecycle:

1. `POST /expenses/expense-categories` → create `"Food"` (`frequency: "daily"`) and `"Rent"` (`"monthly"`).
2. `POST /expenses/entries` with the Food category + a seeded account → expect `status: "confirmed"` in the response.
3. `GET /payments/payment-accounts/balances` → confirm that account's balance dropped by the expense amount.
4. `GET /payments/payment-transactions` → confirm a row with `reference_type: "expense"`, `reference_id` == the new expense's id.
5. `POST /expenses/recurring-expense-templates` → create a `"Shop rent"` template against the Rent category.
6. `POST /expenses/recurring-expense-templates/{id}/generate` → expect `status: "draft"`; confirm `GET /payments/payment-accounts/balances` has **not** moved yet.
7. `POST /expenses/entries/{draft_id}/confirm` → expect `status: "confirmed"`; confirm the balance **now** dropped by that amount too.
8. Repeat step 6 for the same template/month → expect **409**.
9. Generate a draft for a different month (`?period=2026-09-01`), then `DELETE /expenses/entries/{id}` on it → expect **204**, then `GET` the same id → expect **404** (genuinely gone, not soft-deleted).
10. `DELETE` on the now-confirmed expense from step 7 → expect **409** (can't discard a confirmed one).
11. `GET /expenses/entries?status=draft` → confirms the filter works as the de-facto "pending drafts" view (no dedicated endpoint needed, per spec §9).

This exercises every new route, the shared posting path (steps 2 and 7 both moving the same account balance), the draft/confirm/discard state machine, and the idempotent-generation guard.
