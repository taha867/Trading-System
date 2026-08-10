# Phase 7 Backend Spec — Expenses

Governed by `PLAN.md` (what) and `CLAUDE.md` (how). This document is the missing middle layer: the exact schema, validation, and service logic needed to implement Phase 7 inside a new `backend/src/expenses/` package, consistent with what Phases 0–6 already built. Nothing here overrides `CLAUDE.md`'s conventions — every choice below either follows an existing precedent in the codebase (cited by file:line) or is flagged explicitly as a new decision this phase introduces. Unlike the Phase 6 spec, this domain does not exist yet at all — there is no `backend/src/expenses/` package, no migration, no route. Every citation below to `expenses/*` is proposed, not confirmed; citations to `payments/`, `ledger/`, `cargo/`, `purchasing/`, `crud.py` are all confirmed by reading the actual current code.

**Done when** (from `PLAN.md`): a lunch order and this month's rent both land in the same ledger, categorized, from the same screen shape. **Build:** `ExpenseCategory` dynamic CRUD with a daily/monthly flag; an expense-entry screen paid from a `PaymentAccount`; `RecurringExpenseTemplate` for the monthly fixed ones, generating a draft `Expense` each month you confirm rather than silently auto-posting. **Entities:** `ExpenseCategory`, `Expense`, `RecurringExpenseTemplate`.

---

## 1. Where we stand

Confirmed by reading the actual code:

- **No `backend/src/expenses/` package exists.** `find backend/src -maxdepth 1 -type d` lists `auth, cargo, catalog, inventory, ledger, middlewares, parties, payments, purchasing, sales` — no `expenses`. This is a from-scratch domain package, not an extension of an existing one.
- **`payments/constants.py:6-8`** already reserves the ground for this phase:
  ```python
  # Loose, non-FK-validated link — mirrors LedgerEntry.reference_type/reference_id.
  # "expense" doesn't exist as a domain until Phase 7; kept here so payments/ never
  # needs to change again once it does.
  PaymentReferenceType = Literal["sales_order", "purchase_order", "expense"]
  ```
  This is the single strongest signal for this phase's central design decision (§2.1): the codebase already anticipated that creating an `Expense` would create a `PaymentTransaction` with `reference_type="expense"`, not that `Expense` would post its own ledger rows directly. `payments/constants.py` needs **zero changes** this phase — `"expense"` is already a valid value.
- **`payments/service.py::create_payment_transaction`** (`payments/service.py:148-193`) already does everything an expense payment needs: validates the account is active (`get_active_payment_account`, line 149), optionally validates a linked party (lines 151-153, unused by this phase — see §2.5), inserts the `PaymentTransaction`, flushes for its `id` (line 157), posts the account-leg `LedgerEntry` signed from the account's own point of view (lines 160-169: `direction == "out"` → `credit = amount`, cash decreases), optionally posts a party leg (lines 175-185, unused here), and commits with `IntegrityError` → `ConflictException` translation (lines 187-191). Expenses reuses this function wholesale rather than duplicating any ledger-posting logic — see §2.1.
- **`payments/service.py::get_active_payment_account`** (`payments/service.py:26-30`) is the exact fetch-or-raise helper `expenses/service.py` needs to validate `Expense.payment_account_id` / `RecurringExpenseTemplate.payment_account_id` before use — imported directly, not reimplemented.
- **`ledger/models.py:24-26`**'s `payment_account_id` column (added in Phase 6) already covers everything this phase needs from the ledger. **No change to `ledger/models.py` or `ledger/service.py` this phase** — confirmed by the design in §2.1: an expense's ledger trail is entirely a byproduct of the `PaymentTransaction` it creates, and category information is recovered by joining `LedgerEntry.reference_id` (where `reference_type == "payment_transaction"`... actually the ledger entry's own `reference_type`/`reference_id` are set to `"payment_transaction"`/`txn.id` by `post_entry`'s caller inside `create_payment_transaction`, lines 167 and 183) back through `PaymentTransaction.reference_type/reference_id` (`"expense"`/`expense.id`) to `Expense.category_id` — a two-hop lookup, not a new ledger column.
- **`crud.py::build_crud_router`** (`crud.py:21-121`) asserts `hasattr(model, "is_active")` (line 30) and does a flat `model(**payload.model_dump())` insert (line 75) with zero business-logic hooks. `ExpenseCategory` is a pure lookup with no side effects on create/update/delete (exactly like `catalog.Category` or `payments.PaymentMethod`) — it fits the generic factory outright. `RecurringExpenseTemplate`'s plain CRUD (create/list/get/update/delete) also has zero side effects — creating a template is just saving a schedule/config row, nothing posts to the ledger until someone explicitly generates and confirms a draft from it (§2.3) — so it also fits the generic factory, with one hand-written action bolted on beside it.
- **`cargo/router.py:25-75`** is the precedent for combining generic and hand-written sub-routers into one package `router`: two `build_crud_router(...)` calls (`CargoMode`, `CargoCostBasis`) plus one fully hand-written `cargo_shipment_router`, combined via three `router.include_router(...)` calls (lines 72-75). `catalog/router.py:17-47` shows the same combining pattern for three fully-generic sub-routers, each on its own distinct prefix (`/categories`, `/models`, `/items` — never an empty prefix, confirmed by every existing domain). Phase 7 needs a **new variant** of this pattern not yet seen anywhere in this codebase: a generic CRUD router and a hand-written router *sharing the same prefix* (`RecurringExpenseTemplate`'s CRUD stays generic; a `/generate` action needs to live under that same `/recurring-expense-templates/{template_id}/...` path) — flagged explicitly in §2.3 since there's no exact precedent for it yet.
- **`purchasing/constants.py:1-8`**'s `PurchaseOrderStatus = Literal["draft", "allocated", "received"]`, with a comment naming exactly which service function performs each transition, is the direct precedent for `Expense`'s own `status` field and its documented transition (§3.3, §5).
- **`purchasing/models.py:25`**: `status: Mapped[str] = mapped_column(default="draft")` — confirms the "plain `str` column, `Literal` enforced only at the Pydantic layer" convention already used for a status field, cited again in `phase-6-backend.md §3.1`.
- **`exceptions.py:1-19`**: `AppException`/`NotFoundException` (404)/`ConflictException` (409), translated globally in `main.py`'s `@app.exception_handler(AppException)` — no new translation code needed for this phase's exceptions.
- **`parties/service.py::get_active_party`** exists and is imported by `payments/service.py:12` (`from src.parties import service as parties_service`) — confirms the accessor name, though this phase doesn't call it (§2.5, no party link on `Expense`).
- **Migrations**: current head is `b7a2e491f3c8` (`backend/migrations/versions/2026-08-09_add_payments.py:15`, `down_revision = '943d3cd058b8'`). No migration anywhere creates `expense_category`, `expense`, or `recurring_expense_template`. Naming convention: `YYYY-MM-DD_description.py`.
- **`scripts/seed.py`** already seeds `PaymentMethod` (`seed_payment_methods`) and `PaymentAccount` (`seed_payment_accounts`, keyed off `STARTER_PAYMENT_ACCOUNTS`) — so a real `PaymentAccount` to pay expenses from already exists after a fresh seed run, with no changes needed to get that precondition for manual testing (§8).
- **`main.py:4-32`**: every domain adds exactly one import line and one `app.include_router(..., prefix="/<domain>")` line; sub-router tags come from each sub-router's own `build_crud_router(tags=...)` or hand-written `APIRouter(tags=...)` call, never from the top-level `include_router` (confirmed by the comment at `main.py:25`).

---

## 2. Design decisions

### 2.1 `Expense` never posts a `LedgerEntry` directly — it always goes through `payments.create_payment_transaction`

`PLAN.md` says an expense is "paid from a `PaymentAccount`" — that is exactly what a `PaymentTransaction` already models (§1), and `payments/constants.py` already reserved `reference_type="expense"` for this (§1). Two designs were possible: (a) `Expense` posts its own `LedgerEntry` rows directly (mirroring how `purchasing`/`sales` post their own accrual entries), or (b) `Expense` creates a `PaymentTransaction` (which posts the ledger rows on its behalf). This spec picks (b), because:

- The existing `PaymentReferenceType` literal is meaningless under design (a) — nothing would ever construct a `PaymentTransaction` with `reference_type="expense"` if `Expense` posted its own ledger rows, and that value would sit dead in the codebase forever.
- Every expense is, by definition, money leaving an account — the "account balances" view (`payments/service.py::get_account_balances`, Phase 6) and the "payment transactions" list (`GET /payments/payment-transactions`) should show expense payments alongside every other kind of money movement, without a special case. Design (a) would silently exclude expenses from both.
- It reuses `create_payment_transaction`'s existing sign convention, account validation, and commit/rollback handling verbatim — zero new ledger-signing logic to get right in a second place.

So `expenses/service.py` imports `payments/service.py` and `payments/schemas.py` and, wherever an expense is actually paid (manual creation, or confirming a draft — §2.2), builds a `PaymentTransactionCreate(payment_account_id=..., direction="out", amount=..., transaction_date=expense.expense_date, party_id=None, reference_type="expense", reference_id=expense.id, note=expense.description)` and calls `payments_service.create_payment_transaction(db, payload)`. This is a new cross-domain import (`expenses/` → `payments/`), of the same shape `payments/service.py:12` already has into `parties/` — not a violation of any one-way-import rule (`CLAUDE.md` only calls out `ledger/` and `parties/` as one-way; `payments/` and `expenses/` are ordinary domains that may depend on each other in one direction, and `payments/` never needs to import `expenses/` back).

Consequence: **`ledger/models.py` and `ledger/service.py` need no changes at all this phase** — every column an expense's ledger trail needs (`payment_account_id`) already exists from Phase 6.

### 2.2 One `status` field, two entry points, one shared posting path — manual expenses skip "draft" entirely

`PLAN.md` draws a real distinction: a manually-entered expense ("a lunch order") is a fact you're recording after the money already moved — it should post immediately. A `RecurringExpenseTemplate`-generated expense ("this month's rent") is *not yet* paid — it's a draft the system proposes and a human confirms "rather than silently auto-posting" (`PLAN.md`'s own words). Both still end up as the same `Expense` row shape, so this is a `status` column, not two tables — following the `PurchaseOrderStatus` precedent (§1):

```python
# expenses/constants.py
ExpenseStatus = Literal["draft", "confirmed"]
```

- **Manual entry** (`expenses/service.py::create_expense`, called from `POST /expenses/entries`): inserts `Expense(status="confirmed", ...)` and immediately calls the shared posting helper (§2.1) in the same transaction. It never passes through `"draft"`.
- **Recurring-generated** (`expenses/service.py::generate_expense_from_template`, called from `POST /expenses/recurring-expense-templates/{id}/generate`): inserts `Expense(status="draft", recurring_template_id=template.id, ...)` and stops — no `PaymentTransaction`, no `LedgerEntry`, nothing posted. Money hasn't moved yet.
- **Confirming** (`expenses/service.py::confirm_expense`, called from `POST /expenses/entries/{id}/confirm`): only valid when `status == "draft"`; flips it to `"confirmed"` and calls the exact same shared posting helper manual entry uses.

Both paths converge on one private helper, `expenses/service.py::_post_expense_payment(db, expense) -> PaymentTransaction`, so the ledger-posting shape is defined exactly once (mirrors `crud.py`'s own `_get_active_or_404` private-helper convention, `crud.py:36`).

### 2.3 `ExpenseCategory` and `RecurringExpenseTemplate`'s CRUD stays fully generic; only state-transition actions are hand-written

Unlike `PaymentAccount` in Phase 6 (which had to abandon the generic factory entirely because *creation itself* had a ledger side effect — `phase-6-backend.md §2.1`), neither `ExpenseCategory` nor `RecurringExpenseTemplate` has any side effect on create/update/delete: a category is a pure lookup (name + frequency flag), and a template is just a saved schedule (category, account, amount, day-of-month) that does nothing until someone explicitly generates a draft from it. Both are built with `build_crud_router(...)`, unchanged from the `catalog.Category` / `payments.PaymentMethod` shape.

`RecurringExpenseTemplate` additionally needs one action with real logic — "generate this month's draft" — that doesn't fit any of the five generic verbs. Rather than abandon the generic factory for the whole entity (the `cargo_shipment_router` approach, §1), this phase mounts a **second**, hand-written `APIRouter` under the *same* `/recurring-expense-templates` prefix, carrying only `POST /{template_id}/generate`:

```python
recurring_expense_template_router = build_crud_router(
    model=RecurringExpenseTemplate, create_schema=..., read_schema=..., update_schema=...,
    prefix="/recurring-expense-templates", tags=["expenses"],
)
recurring_expense_generate_router = APIRouter(prefix="/recurring-expense-templates", tags=["expenses"])

@recurring_expense_generate_router.post("/{template_id}/generate", response_model=ExpenseRead, status_code=201)
async def generate_expense(...): ...
```
Both are `router.include_router(...)`'d into the domain's combined `router` (§6). This works because the two routers' full paths never collide by *shape* — `GET/PUT/DELETE /recurring-expense-templates/{template_id}` (generic) versus `POST /recurring-expense-templates/{template_id}/generate` (hand-written) differ in segment count, so declaration order between the two routers doesn't matter (unlike the literal-vs-`{param}` collision `payments/router.py`'s `/balances` route had to be declared before `/{account_id}`, `phase-6-backend.md §6`). Flagged explicitly because no existing domain package shares one prefix across two separately-constructed routers today — this is a new arrangement, not a copy of an existing one.

### 2.4 `Expense` has no `update` endpoint, no `is_active` column, and drafts are hard-deleted, not soft-deleted

Once an `Expense` is `"confirmed"`, it has posted real money — correcting a mistake is a new expense or an offsetting `PaymentTransaction`, not an edit, the same posture `PaymentTransaction` itself already takes (`phase-6-backend.md §2.7`: no update/delete route, no `is_active` column, because `PurchaseOrder`/`SalesOrder`/`CargoShipment` already established that a codebase-wide "every table gets `is_active`" (`CLAUDE.md` §4) is not literally exercised for every transactional/event-shaped table). `Expense` follows the same established deviation:

- No `ExpenseUpdate` schema, no `PUT` route — matches `PaymentTransaction`.
- No `is_active` column — a `"confirmed"` expense is permanent history; nothing ever needs to "reactivate" one.
- A `"draft"` expense, by contrast, has posted nothing yet — nothing anywhere references it (no `PaymentTransaction`, no `LedgerEntry`). Discarding one before it's confirmed is safe to hard-delete rather than soft-delete, because a soft-delete flag would be meaningless for the ~100% of rows that are `"confirmed"` and permanent. `DELETE /expenses/entries/{id}` is therefore only valid while `status == "draft"`; calling it on a `"confirmed"` row raises `ConflictException` (409), never a silent no-op.

### 2.5 No party link on `Expense` — scoped out, not merely omitted

`payments.PaymentTransactionCreate` supports an optional `party_id` (`payments/schemas.py:60`), and `create_payment_transaction` would happily post a party leg if one were supplied (§1). This phase's `_post_expense_payment` (§2.1/§2.2) deliberately never sets it — `PLAN.md`'s Phase 7 description says only "paid from a `PaymentAccount`," with no mention of a party. A real scenario exists where this would matter (paying a `local_vendor` `Party` for a repair bill), but wiring `Expense` to an optional `party_id` end-to-end (schema, model column, service, validation against `parties_service.get_active_party`) is a superset of what `PLAN.md` asks for this phase — deferred to §9 as an explicit open question rather than half-built here.

### 2.6 Idempotent monthly generation is a service-level query, not a database constraint

Calling `generate_expense_from_template` twice for the same template in the same month must not create two drafts. This phase enforces that with a plain existence check inside the service function (`select(Expense).where(Expense.recurring_template_id == template.id, Expense.expense_date == period_start)`) rather than a database `UniqueConstraint` — consistent with this codebase's general preference for business-rule checks in Python over exotic multi-column database constraints (e.g. `PurchaseOrderLineCreate`'s "exactly one of `rate_rmb`/`rate_pkr`" is a Pydantic `model_validator`, `purchasing/schemas.py`, not a DB `CHECK`; `LedgerEntry.reference_type`/`reference_id` are a loose pair, never FK-validated, §1). The generated draft's `expense_date` is always normalized to the first of the target month (`period.replace(day=1)`), so the equality check is exact — no `date_trunc` or range query needed. Flagged as a known, accepted gap in §9 (a genuine double-click race is theoretically possible; out of scope for a single-user system, per this repo's existing lack of optimistic locking anywhere else).

---

## 3. Data model

### 3.1 New: `backend/src/expenses/models.py`

```python
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class ExpenseCategory(Base):
    __tablename__ = "expense_category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    frequency: Mapped[str]  # "daily" | "monthly" — Literal enforced at the Pydantic layer, see constants.py
    is_active: Mapped[bool] = mapped_column(default=True)


class RecurringExpenseTemplate(Base):
    __tablename__ = "recurring_expense_template"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]  # e.g. "Shop rent", "Staff salaries"
    category_id: Mapped[int] = mapped_column(ForeignKey("expense_category.id"), index=True)
    payment_account_id: Mapped[int] = mapped_column(ForeignKey("payment_account.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    day_of_month: Mapped[int | None] = mapped_column(nullable=True)  # informational only, not used to auto-trigger
    description: Mapped[str | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class Expense(Base):
    __tablename__ = "expense"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("expense_category.id"), index=True)
    payment_account_id: Mapped[int] = mapped_column(ForeignKey("payment_account.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    expense_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str]  # "draft" | "confirmed" — no column default, see §2.2 (the two entry points disagree)
    recurring_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("recurring_expense_template.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```
`frequency`/`status` are plain `str` columns, `Literal` enforced only in Pydantic — same convention as `purchasing.PurchaseOrder.status` (§1) and `payments.PaymentTransaction.direction`/`reference_type` (`phase-6-backend.md §3.1`), so widening either literal later needs no migration.

### 3.2 No changes to any existing table

`ledger/models.py`, `payments/models.py`, `payments/schemas.py`, `payments/constants.py` — all unchanged (§1, §2.1). This phase is purely additive.

### 3.3 New: `backend/src/expenses/constants.py`

```python
from typing import Literal

ExpenseCategoryFrequency = Literal["daily", "monthly"]

# Manual entries (create_expense) go straight to "confirmed" — money already moved.
# Recurring-template-generated entries (generate_expense_from_template) start at "draft"
# and only reach "confirmed" via confirm_expense, which is the only status transition
# this domain has. Mirrors purchasing/constants.py::PurchaseOrderStatus's own convention
# of naming, in a comment, exactly which service function performs each transition.
ExpenseStatus = Literal["draft", "confirmed"]
```

### 3.4 New: `backend/src/expenses/exceptions.py`

```python
from src.exceptions import NotFoundException


class ExpenseNotFound(NotFoundException):
    detail = "Expense not found"


class RecurringExpenseTemplateNotFound(NotFoundException):
    detail = "Recurring expense template not found"
```
`ExpenseCategory` lookup misses (checked inside `create_expense`/`generate_expense_from_template`, never dependency-injected on their own path param since `ExpenseCategory` has no hand-written routes) stay a generic inline `NotFoundException("Expense category not found")`, matching `payments/service.py::create_payment_account`'s existing inline handling of a missing `PaymentMethod` (`phase-6-backend.md §3.4`) — no dedicated exception class for a plain referenced-lookup miss.

### 3.5 New: `backend/src/expenses/dependencies.py`

```python
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.expenses import service
from src.expenses.models import Expense, RecurringExpenseTemplate


async def valid_expense(expense_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> Expense:
    return await service.get_expense(db, expense_id)


async def valid_recurring_expense_template(
    template_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> RecurringExpenseTemplate:
    return await service.get_active_recurring_expense_template(db, template_id)
```
`valid_recurring_expense_template` is used only by the hand-written `/generate` route (§2.3) — the generic CRUD routes for `RecurringExpenseTemplate` resolve their own path param internally via `crud.py::_get_active_or_404` and never call this. Mirrors `payments/dependencies.py::valid_payment_account` exactly.

---

## 4. Pydantic schemas

### 4.1 New: `backend/src/expenses/schemas.py`

```python
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.expenses.constants import ExpenseCategoryFrequency, ExpenseStatus


class ExpenseCategoryCreate(BaseModel):
    name: Annotated[str, Field(max_length=120)]
    frequency: ExpenseCategoryFrequency


class ExpenseCategoryRead(ExpenseCategoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool


class ExpenseCategoryUpdate(BaseModel):
    name: Annotated[str, Field(max_length=120)] | None = None
    frequency: ExpenseCategoryFrequency | None = None


class RecurringExpenseTemplateCreate(BaseModel):
    name: Annotated[str, Field(max_length=120)]
    category_id: int
    payment_account_id: int
    amount: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    day_of_month: Annotated[int, Field(ge=1, le=28)] | None = None
    description: Annotated[str, Field(max_length=255)] | None = None


class RecurringExpenseTemplateRead(RecurringExpenseTemplateCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool


class RecurringExpenseTemplateUpdate(BaseModel):
    name: Annotated[str, Field(max_length=120)] | None = None
    category_id: int | None = None
    payment_account_id: int | None = None
    amount: Annotated[Decimal, Field(gt=0, decimal_places=2)] | None = None
    day_of_month: Annotated[int, Field(ge=1, le=28)] | None = None
    description: Annotated[str, Field(max_length=255)] | None = None


class ExpenseCreate(BaseModel):
    category_id: int
    payment_account_id: int
    amount: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    expense_date: date
    description: Annotated[str, Field(max_length=255)] | None = None


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    payment_account_id: int
    amount: Decimal
    expense_date: date
    description: str | None = None
    status: ExpenseStatus
    recurring_template_id: int | None = None
    created_at: datetime
```
No `ExpenseUpdate` schema (§2.4). `day_of_month` capped at 28, not 31, so every calendar month is a valid value without special-casing February — it's advisory display-only data for the frontend's "due soon" reminder, never used to compute an actual date server-side (§3.1's comment on `day_of_month`).

---

## 5. Service logic

### 5.1 `expenses/service.py::create_expense` — manual entry, posts immediately

```python
async def create_expense(db: AsyncSession, payload: ExpenseCreate) -> Expense:
    category = await get_active_expense_category(db, payload.category_id)
    account = await payments_service.get_active_payment_account(db, payload.payment_account_id)

    expense = Expense(
        category_id=category.id,
        payment_account_id=account.id,
        amount=payload.amount,
        expense_date=payload.expense_date,
        description=payload.description,
        status="confirmed",
    )
    db.add(expense)
    await db.flush()  # expense.id is needed by the ledger reference below

    await _post_expense_payment(db, expense)
    return expense
```

### 5.2 `expenses/service.py::_post_expense_payment` — the shared posting path (§2.1, §2.2)

```python
async def _post_expense_payment(db: AsyncSession, expense: Expense) -> PaymentTransaction:
    return await payments_service.create_payment_transaction(
        db,
        PaymentTransactionCreate(
            payment_account_id=expense.payment_account_id,
            direction="out",
            amount=expense.amount,
            transaction_date=expense.expense_date,
            reference_type="expense",
            reference_id=expense.id,
            note=expense.description,
        ),
    )
```
This call's own `await db.commit()` (inside `create_payment_transaction`, `payments/service.py:187-191`) is what actually commits the `Expense` row too — both were added to the same `AsyncSession` and nothing before this point calls `commit()`, so the `Expense` insert and the `PaymentTransaction`/`LedgerEntry` inserts land in one atomic transaction, matching this codebase's established `add`/`flush`/`commit` shape (`phase-6-backend.md §1`, last bullet) without `expenses/service.py` needing its own `try/except IntegrityError` around this call — the exception already surfaces as `ConflictException` from inside `create_payment_transaction`.

### 5.3 `expenses/service.py::confirm_expense` — the only status transition

```python
async def confirm_expense(db: AsyncSession, expense: Expense) -> Expense:
    if expense.status != "draft":
        raise ConflictException("Expense is not in draft status")
    expense.status = "confirmed"
    await _post_expense_payment(db, expense)
    return expense
```
`expense.status = "confirmed"` is set *before* calling `_post_expense_payment`, not after — so that mutation is still pending (dirty) when `create_payment_transaction`'s single commit fires, landing in the same transaction as the payment/ledger rows it triggers.

### 5.4 `expenses/service.py::generate_expense_from_template` — creates a draft, posts nothing

```python
async def generate_expense_from_template(
    db: AsyncSession, template: RecurringExpenseTemplate, period: date
) -> Expense:
    period_start = period.replace(day=1)

    existing = await db.scalar(
        select(Expense).where(
            Expense.recurring_template_id == template.id,
            Expense.expense_date == period_start,
        )
    )
    if existing:
        raise ConflictException("Expense already generated for this template this month")

    expense = Expense(
        category_id=template.category_id,
        payment_account_id=template.payment_account_id,
        amount=template.amount,
        expense_date=period_start,
        description=template.description,
        status="draft",
        recurring_template_id=template.id,
    )
    db.add(expense)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Expense could not be saved") from exc
    await db.refresh(expense)
    return expense
```

### 5.5 `expenses/service.py::discard_expense` — draft-only hard delete (§2.4)

```python
async def discard_expense(db: AsyncSession, expense: Expense) -> None:
    if expense.status != "draft":
        raise ConflictException("Only a draft expense can be discarded")
    await db.delete(expense)
    await db.commit()
```

### 5.6 Remaining plumbing

- `get_active_expense_category(db, category_id) -> ExpenseCategory` — inline fetch, raises generic `NotFoundException("Expense category not found")` if missing/inactive (§3.4).
- `get_expense(db, expense_id) -> Expense` — raises `ExpenseNotFound` if missing (used by `dependencies.py::valid_expense`).
- `get_active_recurring_expense_template(db, template_id) -> RecurringExpenseTemplate` — raises `RecurringExpenseTemplateNotFound` if missing/inactive (used by `dependencies.py::valid_recurring_expense_template`).
- `list_expenses(db, pagination, *, category_id=None, payment_account_id=None, status=None) -> PaginatedResponse[ExpenseRead]` — paginated, optional equality filters, ordered by `expense_date.desc(), id.desc()`, same shape as `payments/service.py::list_payment_transactions`. `status=None` returning every row (draft and confirmed together) is what makes "list pending drafts" simply `GET /expenses/entries?status=draft` — no separate "pending" endpoint needed (§9).

### 5.7 No changes to `payments/service.py`, `ledger/service.py`, `ledger/models.py`, `parties/service.py`, or any other existing domain's `service.py`

Confirmed by §1/§2.1: `create_payment_transaction` and `get_active_payment_account` are called exactly as they already exist, with no signature change. Every other domain is untouched.

---

## 6. API surface

`expenses/router.py` combines four sub-routers into one `router`, following the pattern in §2.3/§1 (`cargo/router.py:72-75`, `catalog/router.py:17-47`):

```python
router = APIRouter()
router.include_router(expense_category_router)              # generic CRUD
router.include_router(recurring_expense_template_router)     # generic CRUD
router.include_router(recurring_expense_generate_router)     # hand-written, same prefix as the router above
router.include_router(expense_router)                        # hand-written
```

| Method | Path | Notes |
|---|---|---|
| GET/POST | `/expenses/expense-categories`, `/expenses/expense-categories/{id}` | generic CRUD, unchanged shape |
| GET/POST | `/expenses/recurring-expense-templates`, `/expenses/recurring-expense-templates/{id}` | generic CRUD |
| POST | `/expenses/recurring-expense-templates/{template_id}/generate` | `generate_expense_from_template` — optional `?period=YYYY-MM-DD` query param, defaults to today normalized to the 1st; returns the new draft `ExpenseRead`, 201 |
| GET | `/expenses/entries` | list, paginated, optional `category_id`/`payment_account_id`/`status` query filters |
| POST | `/expenses/entries` | `create_expense` — posts immediately, `status="confirmed"` |
| GET | `/expenses/entries/{expense_id}` | via `valid_expense` |
| POST | `/expenses/entries/{expense_id}/confirm` | `confirm_expense` — 409 if not `"draft"` |
| DELETE | `/expenses/entries/{expense_id}` | `discard_expense` — 204; 409 if not `"draft"` |

`main.py` gets exactly one new import and one new `include_router` line, matching every other domain (§1):
```python
from src.expenses.router import router as expenses_router
...
app.include_router(expenses_router, prefix="/expenses")
```

No route-ordering trap exists here the way `payments/router.py`'s `/balances` route had (`phase-6-backend.md §6`) — `/{template_id}/generate` and `/{template_id}` differ in segment count, not just in literal-vs-variable at the same position, so FastAPI never has to choose between them regardless of `include_router` call order (§2.3).

---

## 7. Migration

One Alembic revision, `alembic revision --autogenerate`, reviewed by eye per `CLAUDE.md` §2.5. Filename `2026-08-10_add_expenses.py`, `down_revision = 'b7a2e491f3c8'` (current head, `migrations/versions/2026-08-09_add_payments.py:15`) — the actual `revision` hash is assigned by Alembic at generation time, not fabricated here. Expected diff, following the exact `op.create_table`/`op.create_index`/`op.f(...)` shape of every prior migration (e.g. `migrations/versions/2026-08-09_add_payments.py:23-51`):

- `CREATE TABLE expense_category (id, name UNIQUE, frequency, is_active)`
- `CREATE TABLE recurring_expense_template (id, name, category_id FK, payment_account_id FK, amount NUMERIC(12,2), day_of_month NULL, description NULL, is_active)`, with indexes on `category_id` and `payment_account_id`
- `CREATE TABLE expense (id, category_id FK, payment_account_id FK, amount NUMERIC(12,2), expense_date, description NULL, status, recurring_template_id FK NULL, created_at)`, with indexes on `category_id`, `payment_account_id`, and `recurring_template_id`

No changes to `ledger_entry`, `payment_account`, `payment_transaction`, or any other existing table (§3.2).

---

## 8. Seed data (`backend/scripts/seed.py`)

Not required to satisfy this phase's done-when line (creating an `ExpenseCategory` and an `Expense` through the app is the point), but a `seed_expense_categories` helper mirroring the existing `seed_payment_methods` (`scripts/seed.py:39-46`) — one row per `PLAN.md`'s own examples (`food`/daily, `repairs`/daily, `rent`/monthly, `bills`/monthly, `salaries`/monthly) — would give manual testing something to attach expenses to immediately. Optional, same restraint every prior phase's spec applied to its own seed-script suggestions (`phase-6-backend.md §8`).

Manual dev/testing path, using what's already seeded (`scripts/seed.py`'s existing `seed_payment_accounts` gives at least a "Cash drawer" account):
1. Seed or create an `ExpenseCategory` (`POST /expenses/expense-categories`, e.g. `{"name": "Food", "frequency": "daily"}`).
2. `POST /expenses/entries` with that category and an existing `payment_account_id` → confirm the response has `status="confirmed"`.
3. `GET /payments/payment-accounts/balances` → confirm the account's balance dropped by the expense's `amount`.
4. `GET /payments/payment-transactions?payment_account_id=<id>` → confirm a row with `reference_type="expense"`, `reference_id` equal to the new expense's `id`.
5. Create a `RecurringExpenseTemplate` (e.g. `{"name": "Shop rent", "category_id": <a monthly category>, "payment_account_id": <id>, "amount": "15000.00"}`).
6. `POST /expenses/recurring-expense-templates/{id}/generate` → confirm a new `Expense` with `status="draft"` and no change yet to `GET /payments/payment-accounts/balances`.
7. `POST /expenses/entries/{draft_id}/confirm` → confirm `status` flips to `"confirmed"` and the balance now drops.
8. Repeat step 6 for the same template/month → confirm a 409 `ConflictException` ("Expense already generated for this template this month").

---

## 9. Out of scope / open questions for later

- **No party link on `Expense`** (§2.5) — deliberately scoped out; `payments.PaymentTransactionCreate.party_id` already supports it end-to-end on the `payments/` side, so wiring it up later (e.g. to record a repair paid to a `local_vendor` `Party`) is additive, not a redesign.
- **Idempotent monthly generation is a service-level check, not a database constraint** (§2.6) — a genuine concurrent double-click on `/generate` could theoretically create two drafts for the same template/month; accepted risk for a single-user system, matching this codebase's existing lack of optimistic locking anywhere else.
- **`day_of_month` is advisory only** (§3.1, §4.1) — nothing in the backend uses it to auto-generate a draft on a schedule; `PLAN.md`'s "generates a draft Expense each month you confirm" is read as a user-triggered action (`POST .../generate`), not a cron job, and there is no background-scheduler infrastructure anywhere in this codebase to hang one off of. If real month-start automation is wanted later, it's a scheduler added at the infrastructure level calling the same `generate_expense_from_template` service function — no service-layer change needed to add it.
- **No "regenerate"/"skip this month" action on a template** — if a draft is discarded (§5.5) the template can simply be generated again for the same month (the uniqueness check in §5.4 only blocks *existing* rows, and discarding deletes the row); no separate "skip" state was added since discard already covers it.
- **`RecurringExpenseTemplate.category_id` is not validated against `ExpenseCategory.frequency == "monthly"`** — a template could reference a `"daily"` category. Left unenforced, matching `catalog.ItemCreate`'s own precedent of relying on the plain FK constraint rather than a cross-entity business-rule check for `category_id`/`model_id` (§1) — revisit only if this proves confusing in practice.
- **No dedicated "pending drafts" endpoint** — `GET /expenses/entries?status=draft` already is that view (§5.6); a dedicated route would be a thin, redundant wrapper.

---

## 10. Implementation checklist

New:
- `backend/src/expenses/__init__.py`
- `backend/src/expenses/models.py` — `ExpenseCategory`, `RecurringExpenseTemplate`, `Expense`
- `backend/src/expenses/constants.py` — `ExpenseCategoryFrequency`, `ExpenseStatus`
- `backend/src/expenses/exceptions.py` — `ExpenseNotFound`, `RecurringExpenseTemplateNotFound`
- `backend/src/expenses/schemas.py` — all schemas in §4.1
- `backend/src/expenses/dependencies.py` — `valid_expense`, `valid_recurring_expense_template`
- `backend/src/expenses/service.py` — `create_expense`, `_post_expense_payment`, `confirm_expense`, `generate_expense_from_template`, `discard_expense`, `get_active_expense_category`, `get_expense`, `get_active_recurring_expense_template`, `list_expenses`
- `backend/src/expenses/router.py` — four combined sub-routers (§6)
- `backend/migrations/versions/2026-08-10_add_expenses.py`

Changed:
- `backend/src/main.py` — one import, one `include_router` line (§6)

Not changed (confirmed, not assumed — §1, §2.1, §5.7):
- `backend/src/payments/*`, `backend/src/ledger/*`, `backend/src/parties/*`
- `backend/src/purchasing/*`, `backend/src/sales/*`, `backend/src/cargo/*`, `backend/src/inventory/*`, `backend/src/catalog/*`
- `backend/src/crud.py`, `backend/src/exceptions.py`, `backend/src/pagination.py`, `backend/src/models.py`

Optional (§8, not required to satisfy this phase's done-when line):
- `backend/scripts/seed.py` — a `seed_expense_categories` helper
