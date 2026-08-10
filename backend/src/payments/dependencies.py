from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.payments import service
from src.payments.models import PaymentAccount, PaymentTransaction


async def valid_payment_account(account_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> PaymentAccount:
    return await service.get_active_payment_account(db, account_id)


async def valid_payment_transaction(
    payment_transaction_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> PaymentTransaction:
    return await service.get_payment_transaction(db, payment_transaction_id)
