from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.crud import build_crud_router
from src.database import get_db
from src.expenses import service
from src.expenses.dependencies import valid_expense, valid_recurring_expense_template
from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate
from src.expenses.schemas import (
    ExpenseCategoryCreate,
    ExpenseCategoryRead,
    ExpenseCategoryUpdate,
    ExpenseCreate,
    ExpenseRead,
    RecurringExpenseTemplateCreate,
    RecurringExpenseTemplateRead,
    RecurringExpenseTemplateUpdate,
)
from src.pagination import PaginatedResponse, PaginationParams

expense_category_router = build_crud_router(
    model=ExpenseCategory,
    create_schema=ExpenseCategoryCreate,
    read_schema=ExpenseCategoryRead,
    update_schema=ExpenseCategoryUpdate,
    prefix="/expense-categories",
    tags=["expenses"],
)

recurring_expense_template_router = build_crud_router(
    model=RecurringExpenseTemplate,
    create_schema=RecurringExpenseTemplateCreate,
    read_schema=RecurringExpenseTemplateRead,
    update_schema=RecurringExpenseTemplateUpdate,
    prefix="/recurring-expense-templates",
    tags=["expenses"],
)

# Shares its prefix with recurring_expense_template_router above (see phase-7-backend.md §2.3) —
# a new arrangement for this codebase, but safe: "/{template_id}/generate" never collides with
# the generic router's "/{template_id}" by path shape, regardless of include_router order.
recurring_expense_generate_router = APIRouter(prefix="/recurring-expense-templates", tags=["expenses"])


@recurring_expense_generate_router.post("/{template_id}/generate", response_model=ExpenseRead, status_code=201)
async def generate_expense(
    template: Annotated[RecurringExpenseTemplate, Depends(valid_recurring_expense_template)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    period: date | None = Query(default=None),
):
    return await service.generate_expense_from_template(db, template, period or date.today())


expense_router = APIRouter(prefix="/entries", tags=["expenses"])


@expense_router.get("", response_model=PaginatedResponse[ExpenseRead])
async def list_expenses(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    category_id: Annotated[int | None, Query()] = None,
    payment_account_id: Annotated[int | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
):
    # Not Annotated[PaginationParams, Query()] here, unlike every other list route in this
    # codebase — mixing that model-exploding Query() with additional sibling Query() scalar
    # params breaks FastAPI's explosion for the model entirely (reproduced empirically against
    # this repo's FastAPI version; regardless of parameter order). Building PaginationParams by
    # hand from plain scalar params, matching its own field constraints, sidesteps the bug while
    # keeping identical validation/defaults.
    pagination = PaginationParams(page=page, page_size=page_size)
    return await service.list_expenses(
        db, pagination, category_id=category_id, payment_account_id=payment_account_id, status=status
    )


@expense_router.post("", response_model=ExpenseRead, status_code=201)
async def create_expense(
    payload: ExpenseCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.create_expense(db, payload)


@expense_router.get("/{expense_id}", response_model=ExpenseRead)
async def get_expense(
    expense: Annotated[Expense, Depends(valid_expense)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return expense


@expense_router.post("/{expense_id}/confirm", response_model=ExpenseRead)
async def confirm_expense(
    expense: Annotated[Expense, Depends(valid_expense)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.confirm_expense(db, expense)


@expense_router.delete("/{expense_id}", status_code=204)
async def discard_expense(
    expense: Annotated[Expense, Depends(valid_expense)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    await service.discard_expense(db, expense)


router = APIRouter()
router.include_router(expense_category_router)
router.include_router(recurring_expense_template_router)
router.include_router(recurring_expense_generate_router)
router.include_router(expense_router)
