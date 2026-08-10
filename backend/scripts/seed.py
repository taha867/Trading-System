import argparse
import asyncio
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from src.auth.models import User
from src.cargo.models import CargoCostBasis, CargoMode
from src.database import SessionLocal
from src.parties.models import Party
from src.payments.models import PaymentAccount, PaymentMethod
from src.purchasing.models import ExchangeRate
from src.security import hash_password

STARTER_PAYMENT_METHODS = ["Bank", "JazzCash", "Easypaisa", "Cash"]
STARTER_PAYMENT_ACCOUNTS = {
    "Bank": "Meezan Bank - main",
    "JazzCash": "JazzCash - 0300-0000000",
    "Easypaisa": "Easypaisa - 0300-0000000",
    "Cash": "Cash drawer",
}
STARTER_CARGO_MODES = ["Sea", "Air"]
STARTER_CARGO_COST_BASES = [("Weight", "weight"), ("CBM", "cbm"), ("Piece", "piece")]


async def seed_user(session, username: str, password: str) -> None:
    existing = await session.scalar(select(User).where(User.username == username))
    if existing:
        print(f"User '{username}' already exists, skipping.")
        return
    session.add(User(username=username, password_hash=hash_password(password)))
    print(f"Created user '{username}'.")


async def seed_exchange_rate(session, rate_date: date, rate: Decimal) -> None:
    existing = await session.scalar(select(ExchangeRate).where(ExchangeRate.rate_date == rate_date))
    if existing:
        print(f"ExchangeRate for {rate_date} already exists, skipping.")
        return
    session.add(ExchangeRate(rate_date=rate_date, rate=rate))
    print(f"Created ExchangeRate {rate_date} -> {rate}.")


async def seed_payment_methods(session) -> None:
    for name in STARTER_PAYMENT_METHODS:
        existing = await session.scalar(select(PaymentMethod).where(PaymentMethod.name == name))
        if existing:
            print(f"PaymentMethod '{name}' already exists, skipping.")
            continue
        session.add(PaymentMethod(name=name))
        print(f"Created PaymentMethod '{name}'.")


async def seed_payment_accounts(session) -> None:
    for method_name, label in STARTER_PAYMENT_ACCOUNTS.items():
        method = await session.scalar(select(PaymentMethod).where(PaymentMethod.name == method_name))
        if method is None:
            continue
        existing = await session.scalar(select(PaymentAccount).where(PaymentAccount.label == label))
        if existing:
            print(f"PaymentAccount '{label}' already exists, skipping.")
            continue
        session.add(PaymentAccount(payment_method_id=method.id, label=label, opening_balance=Decimal(0)))
        print(f"Created PaymentAccount '{label}'.")


async def seed_cargo_modes(session) -> None:
    for name in STARTER_CARGO_MODES:
        existing = await session.scalar(select(CargoMode).where(CargoMode.name == name))
        if existing:
            print(f"CargoMode '{name}' already exists, skipping.")
            continue
        session.add(CargoMode(name=name))
        print(f"Created CargoMode '{name}'.")


async def seed_cargo_cost_bases(session) -> None:
    for name, code in STARTER_CARGO_COST_BASES:
        existing = await session.scalar(select(CargoCostBasis).where(CargoCostBasis.code == code))
        if existing:
            print(f"CargoCostBasis '{name}' already exists, skipping.")
            continue
        session.add(CargoCostBasis(name=name, code=code))
        print(f"Created CargoCostBasis '{name}' ({code}).")


async def seed_china_vendor(session, name: str) -> None:
    existing = await session.scalar(select(Party).where(Party.name == name))
    if existing:
        print(f"Party '{name}' already exists, skipping.")
        return
    session.add(Party(name=name, roles=["china_vendor"], opening_balance=Decimal(0)))
    print(f"Created Party '{name}' (china_vendor).")


async def main(username: str, password: str, rate: Decimal, rate_date: date, vendor_name: str | None) -> None:
    async with SessionLocal() as session:
        await seed_user(session, username, password)
        await seed_exchange_rate(session, rate_date, rate)
        await seed_payment_methods(session)
        await session.flush()  # PaymentMethod rows need an id before seed_payment_accounts looks them up
        await seed_payment_accounts(session)
        await seed_cargo_modes(session)
        await seed_cargo_cost_bases(session)
        if vendor_name:
            await seed_china_vendor(session, vendor_name)
        await session.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Seed Phase 0/1/2 data: user, exchange rate, payment methods, cargo modes/cost "
            "bases, optional China vendor party."
        )
    )
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--rate", required=True, type=Decimal, help="Today's RMB->PKR rate")
    parser.add_argument("--rate-date", type=date.fromisoformat, default=date.today())
    parser.add_argument(
        "--vendor-name", default=None, help="Optional: seed a china_vendor Party with this name (real name, not fabricated)"
    )
    args = parser.parse_args()

    asyncio.run(main(args.username, args.password, args.rate, args.rate_date, args.vendor_name))
