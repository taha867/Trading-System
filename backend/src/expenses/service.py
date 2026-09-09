from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import ConflictException, NotFoundException
from src.expenses.exceptions import ExpenseNotFound, RecurringExpenseTemplateNotFound
from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate
from src.expenses.schemas import ExpenseCreate, ExpenseListRead, ExpenseUpdate
from src.ledger.models import LedgerEntry
from src.pagination import PaginationParams
from src.payments import service as payments_service
from src.payments.models import PaymentTransaction
from src.payments.schemas import PaymentTransactionCreate
from src.payments.utils import money as payment_money


async def get_active_expense_category(db: AsyncSession, category_id: int) -> ExpenseCategory:
    category = await db.get(ExpenseCategory, category_id)
    if category is None or not category.is_active:
        raise NotFoundException("Expense category not found")
    return category


async def get_expense(db: AsyncSession, expense_id: int) -> Expense:
    expense = await db.get(Expense, expense_id)
    if expense is None:
        raise ExpenseNotFound()
    return expense


async def get_active_recurring_expense_template(db: AsyncSession, template_id: int) -> RecurringExpenseTemplate:
    template = await db.get(RecurringExpenseTemplate, template_id)
    if template is None or not template.is_active:
        raise RecurringExpenseTemplateNotFound()
    return template


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


async def confirm_expense(db: AsyncSession, expense: Expense) -> Expense:
    if expense.status != "draft":
        raise ConflictException("Expense is not in draft status")
    expense.status = "confirmed"
    await _post_expense_payment(db, expense)
    return expense


async def discard_expense(db: AsyncSession, expense: Expense) -> None:
    if expense.status != "draft":
        raise ConflictException("Only a draft expense can be discarded")
    await db.delete(expense)
    await db.commit()


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


async def list_expenses(
    db: AsyncSession,
    pagination: PaginationParams,
    *,
    category_id: int | None = None,
    payment_account_id: int | None = None,
    status: str | None = None,
    recurring_template_id: int | None = None,
    expense_date_from: date | None = None,
    expense_date_to: date | None = None,
) -> ExpenseListRead:
    offset = (pagination.page - 1) * pagination.page_size

    filters = []
    if category_id is not None:
        filters.append(Expense.category_id == category_id)
    if payment_account_id is not None:
        filters.append(Expense.payment_account_id == payment_account_id)
    if status is not None:
        filters.append(Expense.status == status)
    if recurring_template_id is not None:
        filters.append(Expense.recurring_template_id == recurring_template_id)
    if expense_date_from is not None:
        filters.append(Expense.expense_date >= expense_date_from)
    if expense_date_to is not None:
        filters.append(Expense.expense_date <= expense_date_to)

    total = await db.scalar(select(func.count()).select_from(Expense).where(*filters))
    # Same filters, no offset/limit — the filter bar's "total spent" has to sum every
    # matching row, not just the page being rendered.
    total_amount = await db.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(*filters))
    result = await db.execute(
        select(Expense)
        .where(*filters)
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = result.scalars().all()

    return ExpenseListRead(
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
        total_amount=payment_money(total_amount or Decimal(0)),
    )


async def update_expense(db: AsyncSession, expense: Expense, payload: ExpenseUpdate) -> Expense:
    updates = payload.model_dump(exclude_unset=True)

    if "category_id" in updates:
        await get_active_expense_category(db, updates["category_id"])
    account = None
    if "payment_account_id" in updates:
        account = await payments_service.get_active_payment_account(db, updates["payment_account_id"])

    for field, value in updates.items():
        setattr(expense, field, value)

    # A draft has never posted anything (see generate_expense_from_template) — a plain
    # field update is all that's needed. A confirmed expense already moved money via
    # exactly one PaymentTransaction + one LedgerEntry (see _post_expense_payment); per
    # this app's convention (no soft-delete/void column on either table, unlike every
    # other domain — see CLAUDE.md's ledger non-negotiables), those two rows are kept
    # in sync in place rather than reversed-and-recreated, so every report reading
    # either table stays consistent with the corrected expense.
    if expense.status == "confirmed":
        txn = await db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.reference_type == "expense", PaymentTransaction.reference_id == expense.id
            )
        )
        if txn is not None:
            if account is None:
                account = await payments_service.get_active_payment_account(db, expense.payment_account_id)
            txn.payment_account_id = expense.payment_account_id
            txn.amount = expense.amount
            txn.transaction_date = expense.expense_date
            txn.note = expense.description

            entry = await db.scalar(
                select(LedgerEntry).where(
                    LedgerEntry.reference_type == "payment_transaction", LedgerEntry.reference_id == txn.id
                )
            )
            if entry is not None:
                entry.account = account.label
                entry.credit = expense.amount
                entry.payment_account_id = expense.payment_account_id
                entry.entry_date = expense.expense_date

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Expense could not be saved") from exc
    await db.refresh(expense)
    return expense
