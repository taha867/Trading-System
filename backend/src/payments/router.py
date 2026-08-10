from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.crud import build_crud_router
from src.database import get_db
from src.pagination import PaginatedResponse, PaginationParams
from src.payments import service
from src.payments.dependencies import valid_payment_account, valid_payment_transaction
from src.payments.models import PaymentAccount, PaymentMethod, PaymentTransaction
from src.payments.schemas import (
    PaymentAccountBalanceRead,
    PaymentAccountCreate,
    PaymentAccountRead,
    PaymentAccountUpdate,
    PaymentMethodCreate,
    PaymentMethodRead,
    PaymentMethodUpdate,
    PaymentTransactionCreate,
    PaymentTransactionRead,
)

payment_method_router = build_crud_router(
    model=PaymentMethod,
    create_schema=PaymentMethodCreate,
    read_schema=PaymentMethodRead,
    update_schema=PaymentMethodUpdate,
    prefix="/payment-methods",
    tags=["payments"],
)

payment_account_router = APIRouter(prefix="/payment-accounts", tags=["payments"])


@payment_account_router.get("", response_model=PaginatedResponse[PaymentAccountRead])
async def list_payment_accounts(
    pagination: Annotated[PaginationParams, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.list_payment_accounts(db, pagination)


@payment_account_router.post("", response_model=PaymentAccountRead, status_code=201)
async def create_payment_account(
    payload: PaymentAccountCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.create_payment_account(db, payload)


# Declared before "/{account_id}" — a literal path segment must come first in this
# router, or FastAPI matches "balances" as account_id and 422s on int coercion.
@payment_account_router.get("/balances", response_model=list[PaymentAccountBalanceRead])
async def get_account_balances(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.get_account_balances(db)


@payment_account_router.get("/{account_id}", response_model=PaymentAccountRead)
async def get_payment_account(
    account: Annotated[PaymentAccount, Depends(valid_payment_account)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return account


@payment_account_router.put("/{account_id}", response_model=PaymentAccountRead)
async def update_payment_account(
    payload: PaymentAccountUpdate,
    account: Annotated[PaymentAccount, Depends(valid_payment_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.update_payment_account(db, account, payload)


@payment_account_router.delete("/{account_id}", status_code=204)
async def soft_delete_payment_account(
    account: Annotated[PaymentAccount, Depends(valid_payment_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    await service.soft_delete_payment_account(db, account)


payment_transaction_router = APIRouter(prefix="/payment-transactions", tags=["payments"])


@payment_transaction_router.post("", response_model=PaymentTransactionRead, status_code=201)
async def create_payment_transaction(
    payload: PaymentTransactionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.create_payment_transaction(db, payload)


@payment_transaction_router.get("", response_model=PaginatedResponse[PaymentTransactionRead])
async def list_payment_transactions(
    pagination: Annotated[PaginationParams, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.list_payment_transactions(db, pagination)


@payment_transaction_router.get("/{payment_transaction_id}", response_model=PaymentTransactionRead)
async def get_payment_transaction(
    txn: Annotated[PaymentTransaction, Depends(valid_payment_transaction)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return txn


router = APIRouter()
router.include_router(payment_method_router)
router.include_router(payment_account_router)
router.include_router(payment_transaction_router)
