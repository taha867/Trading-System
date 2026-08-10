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
