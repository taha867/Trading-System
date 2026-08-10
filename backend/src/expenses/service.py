from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import ConflictException, NotFoundException
from src.expenses.exceptions import ExpenseNotFound, RecurringExpenseTemplateNotFound
from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate
from src.expenses.schemas import ExpenseCreate, ExpenseRead
from src.pagination import PaginatedResponse, PaginationParams
from src.payments import service as payments_service
from src.payments.models import PaymentTransaction
from src.payments.schemas import PaymentTransactionCreate


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
) -> PaginatedResponse[ExpenseRead]:
    offset = (pagination.page - 1) * pagination.page_size

    filters = []
    if category_id is not None:
        filters.append(Expense.category_id == category_id)
    if payment_account_id is not None:
        filters.append(Expense.payment_account_id == payment_account_id)
    if status is not None:
        filters.append(Expense.status == status)

    total = await db.scalar(select(func.count()).select_from(Expense).where(*filters))
    result = await db.execute(
        select(Expense)
        .where(*filters)
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = result.scalars().all()

    return PaginatedResponse[ExpenseRead](
        items=items, total=total or 0, page=pagination.page, page_size=pagination.page_size
    )
