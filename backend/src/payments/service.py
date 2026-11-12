from datetime import date
from decimal import Decimal

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import ConflictException, NotFoundException
from src.expenses.models import Expense, ExpenseCategory
from src.parties.models import Party
from src.ledger import service as ledger_service
from src.dates import validate_date_range
from src.ledger.models import LedgerEntry
from src.pagination import PaginatedResponse, PaginationParams
from src.parties import service as parties_service
from src.payments.constants import PAYMENT_KINDS
from src.payments.exceptions import InvalidPaymentFilter, PaymentAccountNotFound
from src.payments.models import PaymentAccount, PaymentMethod, PaymentTransaction
from src.payments.schemas import (
    PaymentAccountBalanceRead,
    PaymentAccountCreate,
    PaymentAccountRead,
    PaymentAccountUpdate,
    PaymentKindTotalRead,
    PaymentTransactionCreate,
    PaymentTransactionListItem,
    PaymentTransactionListRead,
    PaymentTransactionRead,
)
from src.sales.utils import escape_like
from src.sorting import SortDirection, date_ordering
from src.payments.utils import money


async def get_active_payment_account(db: AsyncSession, account_id: int) -> PaymentAccount:
    account = await db.get(PaymentAccount, account_id)
    if not account or not account.is_active:
        raise PaymentAccountNotFound()
    return account


async def get_payment_transaction(db: AsyncSession, transaction_id: int) -> PaymentTransaction:
    txn = await db.get(PaymentTransaction, transaction_id)
    if not txn:
        raise NotFoundException("Payment transaction not found")
    return txn


async def list_payment_accounts(
    db: AsyncSession, pagination: PaginationParams
) -> PaginatedResponse[PaymentAccountRead]:
    offset = (pagination.page - 1) * pagination.page_size

    total = await db.scalar(
        select(func.count()).select_from(PaymentAccount).where(PaymentAccount.is_active.is_(True))
    )
    result = await db.execute(
        select(PaymentAccount)
        .where(PaymentAccount.is_active.is_(True))
        .order_by(PaymentAccount.id)
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = result.scalars().all()

    return PaginatedResponse[PaymentAccountRead](
        items=items, total=total or 0, page=pagination.page, page_size=pagination.page_size
    )


async def create_payment_account(db: AsyncSession, payload: PaymentAccountCreate) -> PaymentAccount:
    method = await db.get(PaymentMethod, payload.payment_method_id)
    if method is None or not method.is_active:
        raise NotFoundException("Payment method not found")

    account = PaymentAccount(**payload.model_dump())
    db.add(account)
    await db.flush()  # account.id is needed for the ledger entry below

    if account.opening_balance != 0:
        if account.opening_balance > 0:
            debit, credit = account.opening_balance, Decimal(0)
        else:
            debit, credit = Decimal(0), -account.opening_balance
        await ledger_service.post_entry(
            db,
            entry_date=date.today(),
            account="Payment Account Opening Balance",
            debit=debit,
            credit=credit,
            payment_account_id=account.id,
            reference_type="payment_account_opening_balance",
            reference_id=account.id,
        )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Payment account could not be saved") from exc
    await db.refresh(account)
    return account


async def update_payment_account(
    db: AsyncSession, account: PaymentAccount, payload: PaymentAccountUpdate
) -> PaymentAccount:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Payment account could not be saved") from exc
    await db.refresh(account)
    return account


async def soft_delete_payment_account(db: AsyncSession, account: PaymentAccount) -> None:
    account.is_active = False
    await db.commit()


async def get_account_balances(db: AsyncSession) -> list[PaymentAccountBalanceRead]:
    accounts = (
        await db.scalars(
            select(PaymentAccount).where(PaymentAccount.is_active.is_(True)).order_by(PaymentAccount.id)
        )
    ).all()
    sums = dict(
        (
            await db.execute(
                select(LedgerEntry.payment_account_id, func.sum(LedgerEntry.debit - LedgerEntry.credit))
                .where(LedgerEntry.payment_account_id.isnot(None))
                .group_by(LedgerEntry.payment_account_id)
            )
        ).all()
    )
    return [
        # NOT `a.opening_balance + sums[...]` — the opening balance is itself posted as a
        # ledger row (create_payment_account, reference_type="payment_account_opening_balance")
        # with payment_account_id set, so it's already inside `sums`. Adding the column value
        # again here would double-count it. (Confirmed by testing: parties/service.py's
        # get_party_statement has this exact double-count bug for opening_balance today —
        # not fixed here since parties/ is out of this phase's scope, but not repeated here.)
        PaymentAccountBalanceRead(
            id=a.id,
            label=a.label,
            payment_method_id=a.payment_method_id,
            balance=money(sums.get(a.id, Decimal(0))),
        )
        for a in accounts
    ]


async def create_payment_transaction(db: AsyncSession, payload: PaymentTransactionCreate) -> PaymentTransaction:
    account = await get_active_payment_account(db, payload.payment_account_id)

    party = None
    if payload.party_id is not None:
        party = await parties_service.get_active_party(db, payload.party_id)

    txn = PaymentTransaction(**payload.model_dump())
    db.add(txn)
    await db.flush()  # txn.id is needed by the ledger references below

    # Account leg — always posted, signed from the account's own point of view.
    await ledger_service.post_entry(
        db,
        entry_date=payload.transaction_date,
        account=account.label,
        debit=payload.amount if payload.direction == "in" else Decimal(0),
        credit=payload.amount if payload.direction == "out" else Decimal(0),
        payment_account_id=account.id,
        reference_type="payment_transaction",
        reference_id=txn.id,
    )

    # Party leg — only if linked, signed from the party's point of view, which is the
    # OPPOSITE debit/credit assignment from the account leg for the same direction:
    # credit reduces a receivable on "in", debit reduces a payable on "out" — matches
    # the sign convention parties.service.get_party_statement already relies on.
    if party is not None:
        await ledger_service.post_entry(
            db,
            entry_date=payload.transaction_date,
            account="Accounts Receivable" if payload.direction == "in" else "Accounts Payable",
            debit=payload.amount if payload.direction == "out" else Decimal(0),
            credit=payload.amount if payload.direction == "in" else Decimal(0),
            party_id=party.id,
            reference_type="payment_transaction",
            reference_id=txn.id,
        )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Payment transaction could not be saved") from exc

    return txn


async def list_payment_transactions(
    db: AsyncSession,
    pagination: PaginationParams,
    date_from: date | None = None,
    date_to: date | None = None,
    *,
    kind: str | None = None,
    payment_account_id: int | None = None,
    party_id: int | None = None,
    search: str | None = None,
    sort: SortDirection = "newest",
) -> PaymentTransactionListRead:
    offset = (pagination.page - 1) * pagination.page_size
    validate_date_range(date_from, date_to)
    if kind is not None and kind not in PAYMENT_KINDS:
        raise InvalidPaymentFilter(f"kind must be one of {', '.join(PAYMENT_KINDS)}")

    kind_expr = case(
        (PaymentTransaction.reference_type == "expense", "expense"),
        (and_(PaymentTransaction.party_id.is_not(None), PaymentTransaction.direction == "in"), "customer_receipt"),
        (PaymentTransaction.party_id.is_not(None), "supplier_payment"),
        else_="other",
    )
    filters = []
    if date_from is not None:
        filters.append(PaymentTransaction.transaction_date >= date_from)
    if date_to is not None:
        filters.append(PaymentTransaction.transaction_date <= date_to)
    if kind is not None:
        filters.append(kind_expr == kind)
    if payment_account_id is not None:
        filters.append(PaymentTransaction.payment_account_id == payment_account_id)
    if party_id is not None:
        filters.append(PaymentTransaction.party_id == party_id)
    if search is not None and search.strip():
        text_ = search.strip()
        pattern = f"%{escape_like(text_)}%"
        conditions = [
            PaymentTransaction.note.ilike(pattern, escape="\\"),
            Party.name.ilike(pattern, escape="\\"),
            Expense.description.ilike(pattern, escape="\\"),
        ]
        if text_.isdigit():
            conditions.append(PaymentTransaction.reference_id == int(text_))
        filters.append(or_(*conditions))

    joined = (
        select(PaymentTransaction)
        .select_from(PaymentTransaction)
        .outerjoin(Party, Party.id == PaymentTransaction.party_id)
        .outerjoin(Expense, and_(PaymentTransaction.reference_type == "expense", Expense.id == PaymentTransaction.reference_id))
    )
    counted = PaymentTransaction.shown_only.is_(False)  # reference-only rows are listed, never totalled

    total = await db.scalar(select(func.count()).select_from(joined.where(*filters).subquery()))
    shown_only_count = await db.scalar(
        select(func.count()).select_from(joined.where(*filters, PaymentTransaction.shown_only.is_(True)).subquery())
    )
    # totals and the per-kind breakdown: one grouped aggregate over the same filters
    money_in = func.coalesce(func.sum(case((PaymentTransaction.direction == "in", PaymentTransaction.amount), else_=0)), 0)
    money_out = func.coalesce(func.sum(case((PaymentTransaction.direction == "out", PaymentTransaction.amount), else_=0)), 0)
    agg = (
        await db.execute(
            select(kind_expr.label("kind"), func.count(), money_in, money_out)
            .select_from(PaymentTransaction)
            .outerjoin(Party, Party.id == PaymentTransaction.party_id)
            .outerjoin(Expense, and_(PaymentTransaction.reference_type == "expense", Expense.id == PaymentTransaction.reference_id))
            .where(*filters, counted)
            .group_by(kind_expr)
        )
    ).all()
    by_kind = {k: (n, money(Decimal(i)), money(Decimal(o))) for k, n, i, o in agg}
    total_in = sum((v[1] for v in by_kind.values()), Decimal(0))
    total_out = sum((v[2] for v in by_kind.values()), Decimal(0))

    rows = (
        await db.execute(
            select(
                PaymentTransaction,
                kind_expr.label("kind"),
                Party.name,
                PaymentAccount.label,
                ExpenseCategory.name,
                Expense.description,
            )
            .select_from(PaymentTransaction)
            .join(PaymentAccount, PaymentAccount.id == PaymentTransaction.payment_account_id)
            .outerjoin(Party, Party.id == PaymentTransaction.party_id)
            .outerjoin(Expense, and_(PaymentTransaction.reference_type == "expense", Expense.id == PaymentTransaction.reference_id))
            .outerjoin(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
            .where(*filters)
            .order_by(*date_ordering(PaymentTransaction.transaction_date, PaymentTransaction.id, sort))
            .offset(offset)
            .limit(pagination.page_size)
        )
    ).all()
    items = [
        PaymentTransactionListItem(
            **PaymentTransactionRead.model_validate(txn).model_dump(),
            kind=row_kind,
            party_name=party_name,
            account_label=account_label,
            expense_category=category,
            expense_description=description,
        )
        for txn, row_kind, party_name, account_label, category, description in rows
    ]

    return PaymentTransactionListRead(
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
        total_in=total_in,
        total_out=total_out,
        net=money(total_in - total_out),
        shown_only_count=shown_only_count or 0,
        by_kind=[
            PaymentKindTotalRead(kind=k, count=by_kind[k][0], total_in=by_kind[k][1], total_out=by_kind[k][2])
            for k in PAYMENT_KINDS
            if k in by_kind
        ],
    )
