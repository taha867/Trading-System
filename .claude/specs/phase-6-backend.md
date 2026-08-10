# Phase 6 Backend Spec — Payments

Governed by `PLAN.md` (what) and `CLAUDE.md` (how). This document is the missing middle layer: the exact schema, validation, and service-logic needed to implement Phase 6 inside `backend/src/payments/` and `backend/src/ledger/`, consistent with what Phases 0–5 already built. Nothing here overrides `CLAUDE.md`'s conventions — every choice below either follows an existing precedent in the codebase (cited by file:line) or is flagged explicitly as a new decision this phase introduces.

**Done when** (from `PLAN.md`): receiving a customer's payment or paying a vendor updates that account's balance and the party's credit/debit in the same action. **Build:** `PaymentAccount` CRUD (concrete instances of Phase 0's `PaymentMethod`); a record-payment flow with direction (in/out), account, amount, optional link to a party/invoice/PO/expense; every transaction posts to `LedgerEntry`; an account-balances view. **Entities:** `PaymentAccount`, `PaymentTransaction`.

---

## 1. Where we stand

Confirmed by reading the actual code, not assumed:

- **`backend/src/payments/`** today has only `models.py`, `schemas.py`, `router.py`, `__init__.py` — no `service.py`, `constants.py`, `exceptions.py`, or `dependencies.py`. `PaymentMethod` (`payments/models.py:1-11`) is a bare 3-column lookup (`id`, `name` unique, `is_active`), and `payments/router.py:1-12` is a single `build_crud_router(...)` call — no hand-written logic exists in this package at all yet. `PaymentAccount` and `PaymentTransaction` do not exist anywhere in the codebase — no model, no migration, no route.
- **`/payments` is already mounted** at `main.py:28` (`app.include_router(payments_router, prefix="/payments")`), with the comment at `main.py:25` noting this router's sub-routers carry their own tags via `build_crud_router`. Phase 6 adds no new `main.py` line — every new route rides on this existing mount, exactly the way `cargo/router.py` combines three sub-routers under one object mounted once (`cargo/router.py:72-75`, `main.py:30`).
- **`ledger/models.py`**'s `LedgerEntry` (`ledger/models.py:10-24`) has `id, entry_date, account (str), debit, credit (Numeric(12,2), default 0), reference_type (str|None), reference_id (int|None), party_id (FK party.id, nullable, indexed), created_at`. `reference_type`/`reference_id` are a loose polymorphic reference — plain columns, not FK-constrained. There is **no `payment_account_id` column** — the only entity-link column today is `party_id`.
- **`ledger/service.py::post_entry`** (`ledger/service.py:9-33`) is the only function in the file:
  ```python
  async def post_entry(
      db: AsyncSession, *, entry_date: date, account: str,
      reference_type: str, reference_id: int,
      debit: Decimal = Decimal(0), credit: Decimal = Decimal(0),
      party_id: int | None = None,
  ) -> LedgerEntry: ...
  ```
  It only `db.add()`s — no flush, no commit — deliberately, so the caller's own `await db.commit()` covers the domain row and the ledger row atomically. There is **no balance-query or account-aggregation helper anywhere in `ledger/`** — that logic lives in `parties/service.py` as a query *over* `LedgerEntry` (Principle 4). Phase 6's account-balances view has no existing helper to reuse and needs its own query (§2.4, §5.4).
- **`parties/service.py::get_party_statement`** (`parties/service.py:118-148`) is the direct precedent for any "balance over ledger rows" view: it selects every `LedgerEntry` where `party_id == party.id`, ordered by date/id, and accumulates `running += row.debit - row.credit` starting from `party.opening_balance`. The **sign convention this establishes across the whole ledger**: for a given party, `debit` increases their balance, `credit` decreases it, and by existing usage (`purchasing/service.py:99` credits "Accounts Payable" on a purchase; `sales/service.py:82` debits "Accounts Receivable" on a sale) **positive party balance = they owe us; negative = we owe them**, uniformly, regardless of which role the party holds. Phase 6 must not invert this for payments (§2.3).
- **`parties/service.py::create_party`** (`parties/service.py:71-86`) posts an opening-balance `LedgerEntry` in the same transaction as the `Party` insert, so a party onboarded mid-history doesn't start falsely at zero. This is the exact precedent for `PaymentAccount.opening_balance` (§2.2) — an account being onboarded (e.g. this system going live with money already in the bank) needs the identical treatment.
- **Ledger-posting shape, confirmed from both `purchasing/service.py:93-106` and `sales/service.py:76-89`**: `db.add(domain_row)` → `await db.flush()` (to get its `id`) → `await ledger_service.post_entry(db, ..., reference_id=domain_row.id)` → single `await db.commit()` wrapped in `try/except IntegrityError: await db.rollback(); raise ConflictException(...)`. Neither uses `async with session.begin():` despite `CLAUDE.md` §2.5's literal snippet — this is a consistent, deliberate divergence across every domain's `service.py` (`purchasing`, `sales`, `parties`, `cargo`), not a bug. Phase 6 follows the actual codebase convention (`db.add`/`flush`/`commit` + `try/except IntegrityError`), not the doc's literal idiom, for consistency with every other domain.
- **`crud.py::build_crud_router`** (`crud.py:1-122`) asserts `hasattr(model, "is_active")` and does a flat `model(**payload.model_dump())` insert with zero business logic — it cannot post a `LedgerEntry` on create. Since `PaymentAccount` needs an opening-balance ledger post at creation (mirroring `create_party`), **it cannot be built on the generic factory**, exactly the same reason `Party` itself is hand-written rather than generic-CRUD despite superficially looking like a lookup table.
- **`cargo/` is the direct precedent for mixing a generic-CRUD lookup and hand-written transactional logic inside one package**: `cargo/router.py` builds `cargo_mode_router`/`cargo_cost_basis_router` via `build_crud_router(...)` and a hand-written `cargo_shipment_router` as a plain `APIRouter`, then combines all three into one `router` via `router.include_router(...)` three times (`cargo/router.py:72-75`), which is what `main.py:30` mounts as a whole. `payments/router.py` needs the identical restructuring: keep `payment_method_router` (generic, unchanged) and add hand-written `payment_account_router` + `payment_transaction_router`, combined the same way.
- **`cargo/service.py::create_shipment` never posts a `LedgerEntry`** for the cargo agent's payable (confirmed: no `ledger_service.post_entry` call anywhere in that function) — a pre-existing gap relative to `CLAUDE.md` §4's "every ledger-affecting action posts a `LedgerEntry`" non-negotiable. Not this phase's bug to fix, but relevant context: a cargo agent's payable is **not** trackable via `LedgerEntry` today, so "paying a cargo agent" through Phase 6's payment screen will move money out of a `PaymentAccount` and (if `party_id` is set) affect that party's ledger balance for the first time — which is a *feature* of this phase, not a regression, but worth naming so it isn't mistaken for something Phase 6 broke.
- **`exceptions.py`** (`exceptions.py:1-19`): `AppException(detail: str|None=None)` base with `status_code`/`detail` class attrs; `NotFoundException` (404); `ConflictException` (409). Translated to JSON globally in `main.py`'s `@app.exception_handler(AppException)`, not per-router — Phase 6's new exceptions follow this same base, no new translation code needed.
- **Migrations**: current head is `943d3cd058b8` (`2026-08-08_add_purchase_order_source.py`). No migration anywhere creates `payment_account` or `payment_transaction`. Naming convention: `YYYY-MM-DD_description.py`.
- **`scripts/seed.py`** seeds four `PaymentMethod` rows (`Bank`, `JazzCash`, `Easypaisa`, `Cash`) via `seed_payment_methods` (lines 39-46), idempotent check-then-insert. No `PaymentAccount` seeding exists (the entity doesn't exist yet).

---

## 2. Design decisions

### 2.1 `PaymentAccount` is hand-written, not generic-CRUD — same reason `Party` is

`PLAN.md` calls this "`PaymentAccount` CRUD," which could read as "give it to `build_crud_router`." It can't: creating an account with a nonzero `opening_balance` must post a `LedgerEntry` in the same transaction (§2.2), and the generic factory has no hook for that (§1). So `payments/` gets a new `service.py` with `create_payment_account`/`list_payment_accounts`/`update_payment_account`/`soft_delete_payment_account`, and a new `dependencies.py::valid_payment_account` (fetch-or-404 by path param, mirroring `parties/dependencies.py::valid_party`) for the hand-written router's `GET/PUT/DELETE/{account_id}` routes. `PaymentMethod` stays exactly as-is on the generic factory — nothing about it changes this phase.

### 2.2 `PaymentAccount.opening_balance` — same field, same reasoning, same ledger treatment as `Party.opening_balance`

An account onboarded after this system already has money in it (the bank account that's existed for a year, the cash drawer that already has float in it) needs a non-zero starting point, for the identical reason `PLAN.md`'s Architecture Decisions section gives for `Party.opening_balance`. `create_payment_account` posts one `LedgerEntry` at creation, only if `opening_balance != 0`, mirroring `create_party` (`parties/service.py:71-86`):

```python
if account.opening_balance != 0:
    debit = account.opening_balance if account.opening_balance > 0 else Decimal(0)
    credit = -account.opening_balance if account.opening_balance < 0 else Decimal(0)
    await ledger_service.post_entry(
        db, entry_date=date.today(), account=account.label,
        debit=debit, credit=credit, payment_account_id=account.id,
        reference_type="payment_account", reference_id=account.id,
    )
```
Signed like `Party.opening_balance` (a negative starting balance — an overdrawn account — is representable, even if the common case is positive).

### 2.3 A `PaymentTransaction` posts **two** `LedgerEntry` rows when a party is linked, **one** when it isn't — this is a deliberate departure from the one-row-per-transaction precedent

Every existing ledger-poster (`purchasing`, `sales`) posts exactly one row, because a PO/SO is a pure accrual — it only ever touches one side (the party's payable/receivable). A payment is different: it is inherently a movement *between* two ledger accounts — the specific `PaymentAccount` (cash/bank/wallet) on one side, and the party's payable/receivable subledger on the other, when one is linked. A single row's one `debit`/`credit` pair cannot correctly represent both sides at once (verified by working the signs through both directions — see below), so this phase posts:

1. **The account leg — always.** `account = payment_account.label` (snapshotted string, matching the "snapshot, don't recompute" non-negotiable — a later rename of the account doesn't rewrite history), `payment_account_id = payment_account.id`, `party_id = None` (critical — see below), `reference_type = "payment_transaction"`, `reference_id = transaction.id`. Direction maps onto debit/credit the way a cash/asset account naturally works: `direction == "in"` → `debit = amount` (cash increases); `direction == "out"` → `credit = amount` (cash decreases).

2. **The party leg — only if `party_id` is set.** `account = "Accounts Receivable"` if `direction == "in"`, else `"Accounts Payable"` (cosmetic labeling only, consistent with the strings `sales`/`purchasing` already use — nothing downstream keys off this string for the party's own balance math). `party_id = payload.party_id`, `payment_account_id = None` (same reason as below), same `reference_type`/`reference_id`. Sign is the mirror image of the account leg, **not** the same debit/credit values: `direction == "in"` (we received money from them) reduces what they owe us → `credit = amount`; `direction == "out"` (we paid them) reduces what we owe them → `debit = amount`. This is deliberately the *opposite* debit/credit assignment from the account leg for the same `direction` — confirmed against `get_party_statement`'s `running += debit - credit` and the established sign convention (§1): crediting a receivable-holding party's row moves their balance down (toward "owes us less"), debiting a payable-holding party's row moves their balance up (toward "we owe them less") — exactly right in both cases, and notably **role-agnostic** — it works whether the linked party is a `customer`, a `china_vendor`, a `cargo_agent`, or a `local_vendor`, with no need to branch on `party.roles` at all.

**Why `party_id`/`payment_account_id` are mutually exclusive per row, not both set on both rows**: `get_party_statement` filters *only* by `party_id`, and a prospective account-balance view (§2.4) filters *only* by `payment_account_id`. If a single row carried both, it would be double-counted in exactly one of the two views with the *wrong* sign for that view (the account-leg's debit/credit is signed for the account's own perspective, not the party's, and vice versa) — silently corrupting either the party statement or the account balance. Keeping the two legs as two rows, each populating only its own link column, is what keeps both existing (`get_party_statement`) and new (§2.4) balance queries correct without any special-casing.

### 2.4 Account balances are a SQL-side aggregate, not a Python-loop statement like `get_party_statement`

`PLAN.md`'s "Account balances view" asks for a *summary* across every account (a dashboard), not a full transaction history for one account the way the party statement page is a full history for one party. `get_party_statement`'s "fetch every row, loop in Python, accumulate a running balance" shape exists because it also returns the running-balance-per-row for a history table — Phase 6 doesn't need that per-row detail, so `payments/service.py::get_account_balances` does the summation in the database instead:

```python
async def get_account_balances(db: AsyncSession) -> list[PaymentAccountBalanceRead]:
    accounts = (await db.scalars(
        select(PaymentAccount).where(PaymentAccount.is_active.is_(True))
    )).all()
    sums = dict((await db.execute(
        select(LedgerEntry.payment_account_id, func.sum(LedgerEntry.debit - LedgerEntry.credit))
        .where(LedgerEntry.payment_account_id.isnot(None))
        .group_by(LedgerEntry.payment_account_id)
    )).all())
    return [
        PaymentAccountBalanceRead(
            id=a.id, label=a.label, payment_method_id=a.payment_method_id,
            balance=money(a.opening_balance + sums.get(a.id, Decimal(0))),
        )
        for a in accounts
    ]
```
This is a deliberate, narrower alternative to copying `get_party_statement`'s shape verbatim — flagged explicitly since it's the one place this phase's ledger-querying code doesn't mirror the closest existing precedent byte-for-byte.

### 2.5 `payment_account_id` is a new nullable FK column on `LedgerEntry`, added the same way `party_id` was

Not a new free-text convention layered on top of the existing `account` string column — a real, indexed FK, structurally identical to `party_id` (`ledger/models.py:16` today: `party_id: Mapped[int | None] = mapped_column(ForeignKey("party.id"), nullable=True, index=True)`). This is what makes §2.4's query possible and keeps `LedgerEntry` growing by the same pattern it already used once (Phase 4's `party_id` addition), rather than inventing a second, string-based way to link a row to an entity.

### 2.6 `PaymentTransaction`'s `reference_type`/`reference_id` stay a loose pair, not FK-validated — matching `LedgerEntry`'s own convention

`PLAN.md` says "optional link to a party/invoice/PO/expense." In this codebase "invoice" means a `SalesOrder` (Phase 4 uses "invoice a customer" as its own description of creating one — there is no separate `Invoice` entity), so the four link kinds collapse to three concrete `reference_type` values: `"sales_order"`, `"purchase_order"`, `"expense"`. `expense` doesn't exist as a domain yet (Phase 7) — validating it against a real table today isn't possible, and `LedgerEntry.reference_type`/`reference_id` are already a loose polymorphic pair, not FK-constrained, for exactly this reason (a `reference_type` naming a table the ledger itself never imports, per `CLAUDE.md`'s one-way-import rule for `ledger/`). `PaymentTransaction` copies this same shape rather than importing `sales`/`purchasing` into `payments/` to validate existence — a cross-field `model_validator` only enforces that `reference_type` and `reference_id` are both present or both absent (a shape rule, not a business rule against another domain's data).

### 2.7 No update/delete endpoint for `PaymentTransaction`; no `is_active` column on it

Once money has moved and posted to the ledger, correcting a mistake is a new offsetting transaction, not an edit — the exact posture `purchasing`/`sales`/`cargo` already take with their own transactional entities (none of `PurchaseOrder`, `SalesOrder`, `CargoShipment` has an update or delete route; `PurchaseOrder` itself has no `is_active` column at all, confirmed in §1 of `phase-5-backend.md`, despite `CLAUDE.md` §4's "every table" phrasing — an established, pre-existing deviation this phase follows rather than one it introduces). `PaymentTransaction` gets `create` + `list` + `get`, nothing else, and no `is_active` column. `PaymentAccount`, by contrast, is closable (a bank account really can be closed while old transactions against it must remain valid history) — it keeps `is_active` and a soft-delete route, matching `Party`.

### 2.8 No role requirement on the linked party

`purchasing`/`sales` enforce `ensure_role`/`ensure_any_role` because a PO or SO is meaningless against the wrong kind of party. A payment has no such constraint — `PLAN.md` says "optional link to a party," full stop, and money can legitimately flow to or from any party regardless of role (paying a `cargo_agent`, receiving from a `customer`, refunding a `local_vendor`). `create_payment_transaction` calls `parties_service.get_active_party(db, party_id)` when `party_id` is given (existence + active check only) and nothing more.

---

## 3. Data model

### 3.1 New: `backend/src/payments/models.py` additions

```python
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class PaymentAccount(Base):
    __tablename__ = "payment_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_method_id: Mapped[int] = mapped_column(ForeignKey("payment_method.id"), index=True)
    label: Mapped[str]  # e.g. "JazzCash - 0300-1234567", "Meezan Bank - 0123...", "Cash drawer"
    account_number: Mapped[str | None] = mapped_column(nullable=True)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    is_active: Mapped[bool] = mapped_column(default=True)


class PaymentTransaction(Base):
    __tablename__ = "payment_transaction"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_account_id: Mapped[int] = mapped_column(ForeignKey("payment_account.id"), index=True)
    direction: Mapped[str]  # "in" | "out" — Literal enforced at the Pydantic layer, see constants.py
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    transaction_date: Mapped[date]
    party_id: Mapped[int | None] = mapped_column(ForeignKey("party.id"), nullable=True, index=True)
    reference_type: Mapped[str | None] = mapped_column(nullable=True)
    reference_id: Mapped[int | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```
`direction`/`reference_type` are plain `str` columns (Literal enforced in Pydantic only) — same convention `purchasing/models.py`'s `status`/`source` columns already use, per `phase-5-backend.md` §3.1's own note that widening a `Literal` later needs no migration this way.

### 3.2 Changed: `backend/src/ledger/models.py`

```python
class LedgerEntry(Base):
    __tablename__ = "ledger_entry"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_date: Mapped[date] = mapped_column(Date)
    account: Mapped[str]
    debit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    credit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    reference_type: Mapped[str | None] = mapped_column(nullable=True)
    reference_id: Mapped[int | None] = mapped_column(nullable=True)
    party_id: Mapped[int | None] = mapped_column(ForeignKey("party.id"), nullable=True, index=True)
    payment_account_id: Mapped[int | None] = mapped_column(ForeignKey("payment_account.id"), nullable=True, index=True)  # new
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### 3.3 New: `backend/src/payments/constants.py`

```python
from typing import Literal

PaymentDirection = Literal["in", "out"]

# Loose, non-FK-validated link — mirrors LedgerEntry.reference_type/reference_id (§2.6).
# "expense" doesn't exist as a domain until Phase 7; kept here so payments/ never needs
# to change again once it does.
PaymentReferenceType = Literal["sales_order", "purchase_order", "expense"]
```

### 3.4 New: `backend/src/payments/exceptions.py`

```python
from src.exceptions import NotFoundException


class PaymentAccountNotFound(NotFoundException):
    detail = "Payment account not found"
```
`PaymentMethod` lookup misses stay a generic inline `NotFoundException("Payment method not found")` raised from `create_payment_account`, matching `cargo/service.py`'s existing precedent of inline generic `NotFoundException` for lookup-model misses (§1) rather than a dedicated subclass for every lookup.

---

## 4. Pydantic schemas

### 4.1 New in `backend/src/payments/schemas.py` (alongside the unchanged `PaymentMethod*` schemas)

```python
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.payments.constants import PaymentDirection, PaymentReferenceType


class PaymentAccountCreate(BaseModel):
    payment_method_id: int
    label: Annotated[str, Field(max_length=120)]
    account_number: Annotated[str, Field(max_length=64)] | None = None
    opening_balance: Annotated[Decimal, Field(decimal_places=2)] = Decimal(0)


class PaymentAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_method_id: int
    label: str
    account_number: str | None = None
    opening_balance: Decimal
    is_active: bool


class PaymentAccountUpdate(BaseModel):
    label: Annotated[str, Field(max_length=120)] | None = None
    account_number: Annotated[str, Field(max_length=64)] | None = None


class PaymentAccountBalanceRead(BaseModel):
    id: int
    label: str
    payment_method_id: int
    balance: Decimal


class PaymentTransactionCreate(BaseModel):
    payment_account_id: int
    direction: PaymentDirection
    amount: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    transaction_date: date
    party_id: int | None = None
    reference_type: PaymentReferenceType | None = None
    reference_id: int | None = None
    note: Annotated[str, Field(max_length=255)] | None = None

    @model_validator(mode="after")
    def _reference_type_and_id_together(self) -> "PaymentTransactionCreate":
        if (self.reference_type is None) != (self.reference_id is None):
            raise ValueError("reference_type and reference_id must be set together")
        return self


class PaymentTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_account_id: int
    direction: PaymentDirection
    amount: Decimal
    transaction_date: date
    party_id: int | None = None
    reference_type: str | None = None
    reference_id: int | None = None
    note: str | None = None
    created_at: datetime
```
`PaymentAccountUpdate` deliberately omits `opening_balance` (and `payment_method_id`) — `opening_balance` is a creation-time fact that already posted its own `LedgerEntry` (§2.2); allowing it to be edited later would silently desync the account's ledger history from its stated opening figure, the same reasoning `PurchaseOrder`/`SalesOrder` have no update endpoint at all for their priced fields.

---

## 5. Service logic

### 5.1 `payments/service.py::create_payment_account`

```python
async def create_payment_account(db: AsyncSession, payload: PaymentAccountCreate) -> PaymentAccount:
    method = await db.get(PaymentMethod, payload.payment_method_id)
    if method is None or not method.is_active:
        raise NotFoundException("Payment method not found")

    account = PaymentAccount(**payload.model_dump())
    db.add(account)
    await db.flush()

    if account.opening_balance != 0:
        debit = account.opening_balance if account.opening_balance > 0 else Decimal(0)
        credit = -account.opening_balance if account.opening_balance < 0 else Decimal(0)
        await ledger_service.post_entry(
            db, entry_date=date.today(), account=account.label,
            debit=debit, credit=credit, payment_account_id=account.id,
            reference_type="payment_account", reference_id=account.id,
        )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Payment account could not be saved") from exc

    return account
```
Plus `list_payment_accounts` (filter `is_active`, paginated, same shape as `crud.py`'s generic list), `update_payment_account` (partial update, `label`/`account_number` only), `soft_delete_payment_account` (`is_active = False`, commit) — all thin, mirroring `parties/service.py`'s equivalents.

### 5.2 `payments/service.py::get_account_balances`

Exact function given in §2.4.

### 5.3 `payments/service.py::create_payment_transaction`

```python
async def create_payment_transaction(db: AsyncSession, payload: PaymentTransactionCreate) -> PaymentTransaction:
    account = await get_active_payment_account(db, payload.payment_account_id)

    party = None
    if payload.party_id is not None:
        party = await parties_service.get_active_party(db, payload.party_id)

    txn = PaymentTransaction(**payload.model_dump())
    db.add(txn)
    await db.flush()

    # Account leg — always posted, signed from the account's own point of view (§2.3).
    await ledger_service.post_entry(
        db, entry_date=payload.transaction_date, account=account.label,
        debit=payload.amount if payload.direction == "in" else Decimal(0),
        credit=payload.amount if payload.direction == "out" else Decimal(0),
        payment_account_id=account.id,
        reference_type="payment_transaction", reference_id=txn.id,
    )

    # Party leg — only if linked, signed from the party's point of view, which is the
    # OPPOSITE debit/credit assignment from the account leg for the same direction (§2.3).
    if party is not None:
        await ledger_service.post_entry(
            db, entry_date=payload.transaction_date,
            account="Accounts Receivable" if payload.direction == "in" else "Accounts Payable",
            debit=payload.amount if payload.direction == "out" else Decimal(0),
            credit=payload.amount if payload.direction == "in" else Decimal(0),
            party_id=party.id,
            reference_type="payment_transaction", reference_id=txn.id,
        )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Payment transaction could not be saved") from exc

    return txn
```
Plus `list_payment_transactions` (paginated, optionally filterable by `payment_account_id`/`party_id` query params — read-only, no business logic) and `get_active_payment_account(db, account_id) -> PaymentAccount` (fetch, raise `PaymentAccountNotFound` if missing/inactive — used both by this function and by `dependencies.py::valid_payment_account`).

### 5.4 `payments/dependencies.py` — new file

```python
async def valid_payment_account(account_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> PaymentAccount:
    return await service.get_active_payment_account(db, account_id)
```
Used by the hand-written router's `GET/PUT/DELETE /payment-accounts/{account_id}` routes, mirroring `parties/dependencies.py::valid_party` exactly.

### 5.5 No changes to `ledger/service.py`, `parties/service.py`, `purchasing/service.py`, `sales/service.py`, `cargo/service.py`, `inventory/service.py`

`post_entry`'s signature already accepts `payment_account_id` once §3.2's migration lands — no signature change needed there, it's a plain keyword the function already forwards into `LedgerEntry(...)` construction (confirmed against the full function body in §1). Every other domain's service is untouched by this phase.

---

## 6. API surface

`payments/router.py` restructures to combine three sub-routers under one `router`, mirroring `cargo/router.py:72-75`:

```python
router = APIRouter()
router.include_router(payment_method_router)       # unchanged, generic CRUD
router.include_router(payment_account_router)       # new, hand-written
router.include_router(payment_transaction_router)   # new, hand-written
```

| Method | Path | Notes |
|---|---|---|
| GET/POST | `/payments/payment-methods`, `/payments/payment-methods/{id}` | unchanged |
| GET | `/payments/payment-accounts` | list, paginated |
| POST | `/payments/payment-accounts` | `create_payment_account` — posts opening-balance ledger row if non-zero |
| GET | `/payments/payment-accounts/{account_id}` | via `valid_payment_account` |
| PUT | `/payments/payment-accounts/{account_id}` | `label`/`account_number` only |
| DELETE | `/payments/payment-accounts/{account_id}` | soft delete |
| GET | `/payments/payment-accounts/balances` | `get_account_balances` — the "account balances view" `PLAN.md` asks for |
| GET | `/payments/payment-transactions` | list, paginated, optional `payment_account_id`/`party_id` filters |
| POST | `/payments/payment-transactions` | `create_payment_transaction` — posts one or two ledger rows (§2.3) |
| GET | `/payments/payment-transactions/{id}` | fetch-or-404 |

`GET /payments/payment-accounts/balances` must be registered on `payment_account_router` **before** `GET /payment-accounts/{account_id}` in route-declaration order, or FastAPI will match `balances` as an `account_id` path param first — the same ordering trap every path-param router with a sibling literal-path route has to watch for (no existing precedent for this specific trap in this codebase yet — new, called out because it's easy to get backwards once).

---

## 7. Migration

One Alembic revision, `alembic revision --autogenerate`, reviewed by eye (nullability/FK additions are exactly the class of change `CLAUDE.md` §2.5 flags autogenerate for). Expected diff, filename `2026-08-09_add_payments.py`, continuing the chain from head `943d3cd058b8`:

- `CREATE TABLE payment_account (id, payment_method_id FK, label, account_number, opening_balance NUMERIC(12,2), is_active)`
- `CREATE TABLE payment_transaction (id, payment_account_id FK, direction, amount NUMERIC(12,2), transaction_date, party_id FK nullable, reference_type nullable, reference_id nullable, note nullable, created_at)`
- `ALTER TABLE ledger_entry ADD COLUMN payment_account_id INTEGER NULL REFERENCES payment_account(id)`, plus its index — naming convention gives `payment_account_id_idx` per `POSTGRES_INDEXES_NAMING_CONVENTION["ix"]` (`models.py`), matching how `party_id`'s own index was named when it was added.

No changes to any other table.

---

## 8. Seed data (`backend/scripts/seed.py`)

Not required to satisfy this phase's done-when line (a `PaymentAccount` is created through the app, same reasoning `phase-5-backend.md` §8 gave for not seeding transactional rows), but a `seed_payment_accounts` helper mirroring `seed_payment_methods` (lines 39-46) — one `PaymentAccount` per seeded `PaymentMethod`, e.g. `label="Cash drawer"` under `Cash`, `label="Meezan Bank - main"` under `Bank` — would let manual testing of the balances view and the record-payment flow start from something other than an empty table. Optional, same restraint prior phases' specs applied to their own seed-script suggestions.

Manual dev/testing path: seed or create a `PaymentAccount` (`POST /payments/payment-accounts` against an existing `PaymentMethod` id, optionally with `opening_balance`) → `GET /payments/payment-accounts/balances` to confirm the opening balance shows up → create a `PaymentTransaction` with `direction="in"`, a `party_id` for an existing customer, and `reference_type="sales_order"`/`reference_id` pointing at a real invoice from Phase 4 → confirm `GET /payments/payment-accounts/balances` moved by `amount`, and `GET /parties/{party_id}/statement` shows the new row with `credit=amount` reducing their receivable.

---

## 9. Out of scope / open questions for later

- **No update/delete for `PaymentTransaction`** (§2.7) — correcting a mistaken payment means posting an offsetting transaction, not editing history. Consistent with how `PurchaseOrder`/`SalesOrder`/`CargoShipment` already work; not a gap this phase introduces.
- **`reference_type`/`reference_id` are not validated against the referenced row's existence** (§2.6) — a `PaymentTransactionCreate` with `reference_type="sales_order", reference_id=99999` (a nonexistent order) is accepted. Matches `LedgerEntry`'s own existing loose-reference precedent; revisit only if this proves confusing in practice, same posture `phase-5-backend.md` §9 took toward its own acceptable gaps.
- **A party linked to a `PaymentTransaction` gets no role check at all** (§2.8) — deliberate, not a gap.
- **The cargo agent's payable still has no `LedgerEntry` representation** (§1) — pre-existing, out of this phase's scope; a Phase 6 payment to a cargo agent will correctly move that party's balance from this phase forward, but there's no historical trail for shipments already created before Phase 6 existed.
- **No per-account full statement/history endpoint**, only the summary balances view (§2.4) — `PLAN.md`'s "Account balances view" phrase reads as a dashboard, not a party-statement-style drill-down; add one later if a real workflow needs it, following `get_party_statement`'s shape when it does.
- **`PaymentAccount.label` has no uniqueness constraint** — mirrors `Party.name`'s existing non-unique precedent, not `PaymentMethod.name`'s unique one; two accounts can share a label if the user creates them that way.

---

## 10. Implementation checklist

New:
- `backend/src/payments/constants.py` — `PaymentDirection`, `PaymentReferenceType`
- `backend/src/payments/exceptions.py` — `PaymentAccountNotFound`
- `backend/src/payments/dependencies.py` — `valid_payment_account`
- `backend/src/payments/service.py` — `create_payment_account`, `list_payment_accounts`, `update_payment_account`, `soft_delete_payment_account`, `get_account_balances`, `create_payment_transaction`, `list_payment_transactions`, `get_active_payment_account`
- `backend/migrations/versions/2026-08-09_add_payments.py`

Changed:
- `backend/src/payments/models.py` — add `PaymentAccount`, `PaymentTransaction`
- `backend/src/payments/schemas.py` — add all schemas in §4.1
- `backend/src/payments/router.py` — restructure into three combined sub-routers (§6)
- `backend/src/ledger/models.py` — add `LedgerEntry.payment_account_id`

Not changed (confirmed, not assumed — §1, §5.5):
- `backend/src/ledger/service.py`, `backend/src/ledger/schemas.py`
- `backend/src/parties/*`
- `backend/src/purchasing/*`, `backend/src/sales/*`, `backend/src/cargo/*`, `backend/src/inventory/*`
- `backend/src/main.py`
- `backend/src/crud.py`

Optional (§8, not required to satisfy this phase's done-when line):
- `backend/scripts/seed.py` — a `seed_payment_accounts` helper
