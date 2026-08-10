# Phase 0 Backend — Spec

Source of truth: `PLAN.md` (§ Phase 0 — Foundation, § Architecture decisions) for *what*, `CLAUDE.md` (§2) for *how*. This document is the bridge between the two at implementation-detail level, scoped to `backend/` only. Nothing here overrides either file — if a conflict appears, PLAN.md wins on data model, CLAUDE.md wins on code shape.

**Done when** (verbatim from PLAN.md): you can log in, add today's RMB→PKR rate, and add/edit a payment method — all through the generic table+form, nothing hard-coded.

---

## 1. Scope

Build, in this order (each step is independently testable before moving to the next):

1. Project skeleton — `src/`-layout, config, database session, Alembic (async).
2. Shared foundation — `src/models.py` (Base + naming convention), `src/exceptions.py`, `src/pagination.py`, `src/middlewares/`.
3. `auth/` domain — `User` model, JWT login/refresh, password hashing. No registration endpoint required yet (single user, seeded), but keep the service function shape ready for Phase-later multi-user (per PLAN.md "Auth now, even solo").
4. `src/crud.py` — the generic CRUD router/service factory (Principle 3).
5. Lookup domains built *on* the generic factory: `ExchangeRate` (lives under a domain — see §4.1 for placement decision) and `PaymentMethod` (`payments/`).
6. `ledger/` domain — `LedgerEntry` model only, no router yet (schema-only per PLAN.md; nothing writes to it until Phase 1+).
7. `main.py` wiring — middleware registration, router inclusion.
8. Seed script — initial `User`, a starter `ExchangeRate` row, starter `PaymentMethod` rows.

Out of scope for Phase 0 (explicitly deferred to later phases per PLAN.md roadmap): `Party`, `Category`/`Model`/`Item`, `PurchaseOrder`, anything cargo/inventory/sales/expenses. Do not scaffold empty domain packages for these now — CLAUDE.md's structure is a target shape to grow into, not a checklist to pre-create.

---

## 2. Folder structure delivered by Phase 0

Per CLAUDE.md §2.1, only the pieces Phase 0 actually needs — no placeholder domains:

```
backend/
├── migrations/
│   ├── versions/
│   │   └── 2026-08-07_initial_schema.py       # User, ExchangeRate, PaymentMethod, LedgerEntry
│   ├── env.py
│   └── script.py.mako
├── src/
│   ├── auth/
│   │   ├── router.py           # /auth/login, /auth/refresh
│   │   ├── schemas.py          # UserRead, LoginRequest, TokenPair, RefreshRequest
│   │   ├── models.py           # User
│   │   ├── service.py          # authenticate_user, create_access_token, create_refresh_token, verify + decode
│   │   ├── dependencies.py     # get_current_user (Depends), oauth2 bearer scheme
│   │   ├── constants.py        # token type literals, expiry constants
│   │   └── exceptions.py       # InvalidCredentials, TokenExpired, TokenInvalid
│   ├── payments/
│   │   ├── router.py           # generic CRUD router for PaymentMethod (mounted via src/crud.py factory)
│   │   ├── schemas.py          # PaymentMethodCreate/Read/Update
│   │   ├── models.py           # PaymentMethod
│   │   ├── service.py          # thin — delegates to generic crud.py service functions
│   │   ├── constants.py
│   │   └── exceptions.py
│   ├── purchasing/
│   │   ├── router.py           # generic CRUD router for ExchangeRate ONLY in Phase 0
│   │   ├── schemas.py          # ExchangeRateCreate/Read/Update
│   │   ├── models.py           # ExchangeRate
│   │   ├── service.py
│   │   ├── constants.py
│   │   └── exceptions.py
│   ├── ledger/
│   │   ├── models.py           # LedgerEntry — schema only, no router/service/schemas.py yet
│   │   └── constants.py        # account name conventions, reference_type literals (documented, unused until Phase 1)
│   ├── middlewares/
│   │   ├── __init__.py
│   │   ├── cors.py
│   │   ├── request_context.py
│   │   └── logging.py
│   ├── config.py
│   ├── models.py
│   ├── exceptions.py
│   ├── pagination.py
│   ├── database.py
│   ├── security.py             # password hashing (passlib/bcrypt) + JWT encode/decode helpers — shared, not auth-only business logic
│   ├── crud.py
│   └── main.py
├── scripts/
│   └── seed.py                 # seeds User, ExchangeRate, PaymentMethod
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── logging.ini
├── alembic.ini
└── .env
```

Notes on placement decisions (per CLAUDE.md §2.1's "where a lookup entity lives" rule):

- **`ExchangeRate` → `purchasing/`.** CLAUDE.md is explicit: "`ExchangeRate` lives in `purchasing/` (it's read at PO-line creation)." Phase 0 stands this package up early, containing *only* `ExchangeRate`, because Phase 1 will add `PurchaseOrder`/`PurchaseOrderLine` to the same package later. This is the one deliberate exception to "don't scaffold ahead" — the entity itself is explicitly Phase-0-scoped by PLAN.md, and CLAUDE.md has already named its home.
- **`PaymentMethod` → `payments/`.** CLAUDE.md: "`PaymentMethod` lives in `payments/` (alongside the `PaymentAccount` instances built from it)." `PaymentAccount` doesn't exist until Phase 6 — `payments/` in Phase 0 contains only `PaymentMethod`.
- **`Setting`** — PLAN.md's Phase 0 entity list names `Setting`, but nothing in Phase 0's "done when" or Build description exercises it (no settings screen, no config value read from it). CLAUDE.md says app-wide `Setting` is "a table owned by `src/config.py`'s domain (no dedicated package)." **Decision needed from user before implementation** — see §7, Open Question 1.
- **`User` → `auth/`.** Standard placement, matches CLAUDE.md's package list.
- **`LedgerEntry` → `ledger/`.** Model only. Per CLAUDE.md, `ledger/` is one-way (everyone imports into it, it imports nothing back) — in Phase 0 nothing imports into it yet since no domain posts entries until Phase 1's sales/purchasing. No router: PLAN.md's Phase 0 entity list marks it explicitly "(schema only)".

---

## 3. Shared foundation

### 3.1 `src/config.py`

```python
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    DATABASE_URL: PostgresDsn
    CORS_ORIGINS: list[str] = []
    ENVIRONMENT: str = "development"
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"

settings = Config()
```

Fails at import time (app boot) if `DATABASE_URL` or `JWT_SECRET_KEY` is missing — per CLAUDE.md §2.6, a missing required setting must fail on boot, not on first request.

### 3.2 `src/models.py`

Exactly the naming-convention `Base` from CLAUDE.md §2.1 — copy verbatim, no deviation:

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)
```

Every domain's `models.py` imports `Base` from here — never defines its own `DeclarativeBase`.

### 3.3 `src/database.py`

Per CLAUDE.md §2.5, async engine + `async_sessionmaker`, one session per request:

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.config import settings

engine = create_async_engine(str(settings.DATABASE_URL), echo=settings.ENVIRONMENT == "development")
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
```

### 3.4 `src/exceptions.py`

Shared base + error-response schema every domain exception subclasses:

```python
class AppException(Exception):
    status_code: int = 400
    detail: str = "An error occurred"

class NotFoundException(AppException):
    status_code = 404

class ConflictException(AppException):
    status_code = 409
```

A single exception handler in `main.py` catches `AppException` and translates it to `HTTPException(status_code=exc.status_code, detail=exc.detail)` — this is what lets domain `exceptions.py` files (e.g. `auth/exceptions.py`'s `InvalidCredentials(AppException)`) stay framework-agnostic while routers still return a real JSON error body.

### 3.5 `src/pagination.py`

Shared params/response wrapper, reused by the generic CRUD list endpoint and every future domain list endpoint:

```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
```

`PaginationParams` is consumed via `Annotated[PaginationParams, Depends()]` in the generic CRUD router (CLAUDE.md §2.2: "Use `Depends()` for anything cross-cutting... shared query params like pagination").

### 3.6 `src/security.py`

Framework-agnostic password + token primitives, shared by `auth/service.py` but not auth *business logic* itself (no DB access here):

- `hash_password(plain: str) -> str` / `verify_password(plain: str, hashed: str) -> bool` — via `passlib[bcrypt]`.
- `create_token(subject: str, expires_delta: timedelta, token_type: Literal["access", "refresh"]) -> str` — via `python-jose` or `pyjwt`.
- `decode_token(token: str) -> dict` — raises on expiry/invalid signature; `auth/dependencies.py` catches and re-raises as `TokenExpired`/`TokenInvalid`.

### 3.7 Middleware (`src/middlewares/`)

Exact shape from CLAUDE.md §2.3 — `register_middlewares(app)` called once from `main.py`, LIFO order respected (CORS added first, request-context added last so it wraps everything). All three files (`cors.py`, `request_context.py`, `logging.py`) are copied as specified in CLAUDE.md with no Phase-0-specific changes.

---

## 4. Domain: `auth/`

### 4.1 `User` model

| Field | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `username` | `str`, unique | login identifier |
| `password_hash` | `str` | never serialized in any `Read` schema |
| `is_active` | `bool`, default `True` | soft-delete flag (CLAUDE.md §4 non-negotiable, even though Phase 0 has no "delete a user" flow) |
| `created_at` | `datetime`, server default `now()` | |

```python
# src/auth/models.py
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from src.models import Base

class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### 4.2 Schemas (`auth/schemas.py`)

```python
from pydantic import BaseModel, ConfigDict

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    is_active: bool

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str
```

No `UserCreate`/registration schema in Phase 0 — the single user is seeded (§6), not self-registered. (Frontend's `SignUpPage.jsx` from CLAUDE.md §3.3 is kept as a stub per that file's own note — "kept even for a single user today" — but its backend endpoint is not part of Phase 0's "done when" and is deliberately not built yet. See Open Question 2 in §7 if the frontend phase needs it sooner.)

### 4.3 Service (`auth/service.py`)

- `authenticate_user(db, username, password) -> User` — looks up by username, verifies password via `src.security.verify_password`, raises `InvalidCredentials` (domain exception) on any failure — same error for "no such user" and "wrong password" (don't leak which one).
- `issue_token_pair(user: User) -> TokenPair` — calls `src.security.create_token` twice (access + refresh), returns both.
- `refresh_access_token(db, refresh_token: str) -> TokenPair` — decodes, validates token type is `"refresh"`, re-fetches the user (confirms still `is_active`), issues a new pair.

### 4.4 Dependencies (`auth/dependencies.py`)

```python
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    payload = decode_token(token)   # raises TokenExpired / TokenInvalid
    user = await db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise TokenInvalid()
    return user
```

Every future protected route (Phase 1 onward) depends on this. Phase 0 itself doesn't have protected *business* routes yet since the only CRUD entities (`ExchangeRate`, `PaymentMethod`) are meant to be reachable from a logged-in single-user app — **decision needed**: should the generic CRUD routes require `get_current_user` in Phase 0, or is that deferred until the frontend's `ProtectedRoute` exists? See Open Question 3, §7. Default assumption used in this spec unless told otherwise: **yes, gate them** — PLAN.md's "done when" says "you can log in... and add/edit a payment method," implying login precedes CRUD access, and CLAUDE.md's request lifecycle (§1) lists `Depends()` injecting "the current user" as standard for every endpoint once auth exists — which, as of Phase 0, it does.

### 4.5 Router (`auth/router.py`)

```python
router = APIRouter()

@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await service.authenticate_user(db, payload.username, payload.password)
    return service.issue_token_pair(user)

@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    return await service.refresh_access_token(db, payload.refresh_token)

@router.get("/me", response_model=UserRead)
async def me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user
```

Mounted in `main.py` as `app.include_router(auth_router, prefix="/auth", tags=["auth"])`.

---

## 5. Generic CRUD engine — `src/crud.py`

This is the Phase 0 centerpiece per PLAN.md Principle 3 and roadmap line: "The generic CRUD engine itself, proven on one real table" (in practice, Phase 0 proves it on two: `ExchangeRate` and `PaymentMethod`).

### 5.1 Factory shape

A function that takes a SQLAlchemy model + its three Pydantic schemas and returns a ready-to-mount `APIRouter`:

```python
# src/crud.py
from typing import Type, TypeVar
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.pagination import PaginationParams, PaginatedResponse
from src.auth.dependencies import get_current_user

ModelT = TypeVar("ModelT")
CreateT = TypeVar("CreateT", bound=BaseModel)
ReadT = TypeVar("ReadT", bound=BaseModel)
UpdateT = TypeVar("UpdateT", bound=BaseModel)

def build_crud_router(
    *,
    model: Type[ModelT],
    create_schema: Type[CreateT],
    read_schema: Type[ReadT],
    update_schema: Type[UpdateT],
    prefix: str,
    tags: list[str],
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=tags)

    @router.get("", response_model=PaginatedResponse[read_schema])
    async def list_items(
        pagination: Annotated[PaginationParams, Depends()],
        db: Annotated[AsyncSession, Depends(get_db)],
        _: Annotated[User, Depends(get_current_user)],
    ):
        ...  # SELECT * WHERE is_active = true, offset/limit, plus a COUNT(*) for total

    @router.post("", response_model=read_schema, status_code=201)
    async def create_item(
        payload: create_schema,
        db: Annotated[AsyncSession, Depends(get_db)],
        _: Annotated[User, Depends(get_current_user)],
    ):
        ...  # model(**payload.model_dump()); db.add; await db.commit; await db.refresh

    @router.get("/{item_id}", response_model=read_schema)
    async def get_item(item_id: int, db: ..., _: ...):
        ...  # 404 via shared NotFoundException if missing or is_active=False

    @router.put("/{item_id}", response_model=read_schema)
    async def update_item(item_id: int, payload: update_schema, db: ..., _: ...):
        ...  # partial update: model_dump(exclude_unset=True)

    @router.delete("/{item_id}", status_code=204)
    async def soft_delete_item(item_id: int, db: ..., _: ...):
        ...  # sets is_active = False, does NOT issue DELETE FROM

    return router
```

### 5.2 Non-negotiables baked into the factory (CLAUDE.md §4 / PLAN.md "Decide early")

- **Soft delete only.** The `DELETE` endpoint is really an `UPDATE ... SET is_active = false`. The factory assumes every model passed to it declares `is_active: Mapped[bool]` — this is an implicit contract; if a future model omits the field, the factory should fail loudly at router-build time (an `assert hasattr(model, "is_active")` at the top of `build_crud_router`), not silently 500 at request time.
- **List/get exclude soft-deleted rows by default.** No query param to include inactive rows in Phase 0 — add one only when a real screen needs it.
- **Auth-gated.** Every generated route depends on `get_current_user` (see §4.4's open question — this spec assumes yes).
- **`response_model` always set**, per CLAUDE.md §2.2 — the factory's signature forces this; there's no code path that skips it.

### 5.3 What is *not* generic

Per PLAN.md Principle 3 and CLAUDE.md §2.1: "Transactional entities... get hand-written endpoints because they carry business logic — don't force those through the generic factory." Phase 0 has no transactional entities yet, so this rule doesn't bite until Phase 1's `PurchaseOrder`. Noted here only so the factory isn't over-generalized to anticipate business rules it will never need (e.g. don't add a "custom validation hook" param to `build_crud_router` speculatively — YAGNI until a phase actually needs it).

### 5.4 How a domain wires the factory

```python
# src/purchasing/router.py
from src.crud import build_crud_router
from src.purchasing.models import ExchangeRate
from src.purchasing.schemas import ExchangeRateCreate, ExchangeRateRead, ExchangeRateUpdate

router = build_crud_router(
    model=ExchangeRate,
    create_schema=ExchangeRateCreate,
    read_schema=ExchangeRateRead,
    update_schema=ExchangeRateUpdate,
    prefix="/exchange-rates",
    tags=["purchasing"],
)
```

```python
# src/payments/router.py
from src.crud import build_crud_router
from src.payments.models import PaymentMethod
from src.payments.schemas import PaymentMethodCreate, PaymentMethodRead, PaymentMethodUpdate

router = build_crud_router(
    model=PaymentMethod,
    create_schema=PaymentMethodCreate,
    read_schema=PaymentMethodRead,
    update_schema=PaymentMethodUpdate,
    prefix="/payment-methods",
    tags=["payments"],
)
```

Each domain's `router.py` is now a 10-line file — matching CLAUDE.md §2.2's "thin router" rule trivially, since the factory *is* the logic.

---

## 6. Domain models & schemas: `ExchangeRate`, `PaymentMethod`, `LedgerEntry`

### 6.1 `ExchangeRate` (`purchasing/models.py`)

Per PLAN.md § Currency handling: keyed by date, RMB→PKR, `Numeric(10,4)` for the rate itself (not `Numeric(12,2)` — that's for RMB/PKR amounts, not the rate).

| Field | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `rate_date` | `date`, unique | one rate per calendar day |
| `rate` | `Numeric(10,4)` | RMB→PKR |
| `is_active` | `bool`, default `True` | soft delete |

```python
from datetime import date
from decimal import Decimal
from sqlalchemy import Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column
from src.models import Base

class ExchangeRate(Base):
    __tablename__ = "exchange_rate"
    id: Mapped[int] = mapped_column(primary_key=True)
    rate_date: Mapped[date] = mapped_column(Date, unique=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    is_active: Mapped[bool] = mapped_column(default=True)
```

```python
# purchasing/schemas.py
from datetime import date
from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field

class ExchangeRateCreate(BaseModel):
    rate_date: date
    rate: Annotated[Decimal, Field(gt=0, decimal_places=4)]

class ExchangeRateRead(ExchangeRateCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool

class ExchangeRateUpdate(BaseModel):
    rate: Annotated[Decimal, Field(gt=0, decimal_places=4)] | None = None
```

Uniqueness on `rate_date` means a duplicate-date `POST` must surface as a clean `409`, not a raw `IntegrityError` — the generic factory's `create_item` should catch `IntegrityError` on commit and re-raise as the shared `ConflictException` (§3.4). This is generic factory behavior, not `ExchangeRate`-specific, since `PaymentMethod` below has the same shape of constraint.

### 6.2 `PaymentMethod` (`payments/models.py`)

Lookup table for payment rails (Bank/JazzCash/Easypaisa/Cash) — instantiated into concrete `PaymentAccount` rows starting Phase 6, per CLAUDE.md.

| Field | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `name` | `str`, unique | e.g. "Bank", "JazzCash", "Easypaisa", "Cash" |
| `is_active` | `bool`, default `True` | soft delete |

```python
from sqlalchemy.orm import Mapped, mapped_column
from src.models import Base

class PaymentMethod(Base):
    __tablename__ = "payment_method"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
```

```python
# payments/schemas.py
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field

class PaymentMethodCreate(BaseModel):
    name: Annotated[str, Field(max_length=64)]

class PaymentMethodRead(PaymentMethodCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool

class PaymentMethodUpdate(BaseModel):
    name: Annotated[str, Field(max_length=64)] | None = None
```

### 6.3 `LedgerEntry` (`ledger/models.py`) — schema only

Per PLAN.md § The ledger and its explicit Phase 0 note "(schema only)": the table exists so its foreign keys are available to Alembic and so later phases don't need a schema-changing migration to *add* the table, only to start writing to it. No router, no Pydantic schemas, no service function in Phase 0.

| Field | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `entry_date` | `date` | |
| `account` | `str` | e.g. `"Bank-Meezan"`, `"Cash"` — free text in Phase 0, not yet an FK (accounts don't exist as rows until Phase 6's `PaymentAccount`) |
| `debit` | `Numeric(12,2)`, default `0` | |
| `credit` | `Numeric(12,2)`, default `0` | |
| `reference_type` | `str` | e.g. `"sales_order"` — nullable in Phase 0 since nothing posts yet |
| `reference_id` | `int`, nullable | |
| `party_id` | `int`, nullable, **no FK constraint yet** | `Party` table doesn't exist until Phase 1; adding the FK now is impossible. Add the constraint in the Phase-1 migration that creates `Party`, not before. |
| `created_at` | `datetime`, server default `now()` | |

```python
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Numeric, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from src.models import Base

class LedgerEntry(Base):
    __tablename__ = "ledger_entry"
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_date: Mapped[date] = mapped_column(Date)
    account: Mapped[str]
    debit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    credit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    reference_type: Mapped[str | None] = mapped_column(nullable=True)
    reference_id: Mapped[int | None] = mapped_column(nullable=True)
    party_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

No `is_active` on `LedgerEntry` — per PLAN.md, the ledger is append-only by design; "soft delete everywhere" (CLAUDE.md §4) doesn't apply to a table that's never supposed to be edited or removed, only appended to. This is a deliberate, named exception, not an oversight.

---

## 7. `main.py`

```python
from fastapi import FastAPI
from src.middlewares import register_middlewares
from src.exceptions import AppException
from src.auth.router import router as auth_router
from src.purchasing.router import router as purchasing_router
from src.payments.router import router as payments_router

app = FastAPI(title="Trading System")
register_middlewares(app)

@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(purchasing_router, prefix="/purchasing", tags=["purchasing"])
app.include_router(payments_router, prefix="/payments", tags=["payments"])
```

Note `purchasing_router` and `payments_router` are already prefixed *inside* their own `router.py` (from the `build_crud_router(prefix=...)` call in §5.4) with the resource path (`/exchange-rates`, `/payment-methods`); `include_router`'s `prefix` here adds the domain-level segment, giving final paths `/purchasing/exchange-rates` and `/payments/payment-methods` — consistent with CLAUDE.md §2.2's one-line-per-domain pattern.

---

## 8. Migrations

- `alembic init -t async migrations` run once, `alembic.ini`'s `script_location = migrations` (CLAUDE.md §2.5).
- One migration for Phase 0: `2026-08-07_initial_schema.py`, autogenerated then hand-reviewed, creating `user`, `exchange_rate`, `payment_method`, `ledger_entry` in one batch — per CLAUDE.md's "batch one migration per feature, not per coding session."
- Review the autogenerated `Numeric(10,4)` / `Numeric(12,2)` precision by eye before applying, per CLAUDE.md's explicit warning that autogenerate misses precision changes.

---

## 9. Seed script (`scripts/seed.py`)

Run manually (`python -m scripts.seed`), idempotent (checks existence before inserting):

- One `User` — username/password from environment or CLI prompt, never hardcoded in the script itself.
- One `ExchangeRate` row for today's date (`2026-08-07`), rate value provided via CLI arg or prompt — no fabricated real-world exchange rate hardcoded into source.
- Starter `PaymentMethod` rows: `"Bank"`, `"JazzCash"`, `"Easypaisa"`, `"Cash"` — these names come directly from PLAN.md Phase 6's parenthetical list, safe to hardcode since they're the domain's actual lookup values, not sensitive/variable data.

---

## 10. API surface summary

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/login` | none | returns access + refresh token |
| POST | `/auth/refresh` | none (refresh token in body) | rotates access token |
| GET | `/auth/me` | bearer | current user info |
| GET | `/purchasing/exchange-rates` | bearer | paginated list |
| POST | `/purchasing/exchange-rates` | bearer | create |
| GET | `/purchasing/exchange-rates/{id}` | bearer | fetch one |
| PUT | `/purchasing/exchange-rates/{id}` | bearer | partial update |
| DELETE | `/purchasing/exchange-rates/{id}` | bearer | soft delete |
| GET/POST/GET/PUT/DELETE | `/payments/payment-methods[/…]` | bearer | same generic shape as above |

---

## 11. Testing checklist (manual, matches PLAN.md's "done when")

1. `alembic upgrade head` runs clean against a fresh Postgres database.
2. `python -m scripts.seed` creates the user + starter rows without error, and is safely re-runnable.
3. `POST /auth/login` with seeded credentials returns a token pair; wrong password returns 401 with a generic message.
4. `GET /purchasing/exchange-rates` without a bearer token returns 401.
5. With a valid token: `POST /purchasing/exchange-rates` with today's date + a rate succeeds (201); repeating the same date returns 409, not a 500.
6. `POST /payments/payment-methods` with a new name succeeds; `PUT` on it updates the name; `DELETE` sets `is_active=False` and it disappears from the default `GET` list but the row still exists in the database.
7. `GET /auth/me` with an expired access token returns 401; `POST /auth/refresh` with a valid refresh token returns a new working access token.

---

## 12. Decisions (confirmed with user)

1. **`Setting` table** — deferred entirely. Not built in Phase 0; revisit when a later phase actually needs a persisted setting.
2. **Registration endpoint** — seed-script only. No `/auth/register` route in Phase 0; the frontend's `SignUpPage.jsx` stays a non-functional stub until a later phase.
3. **Auth-gating the generic CRUD routes** — confirmed yes. `ExchangeRate`/`PaymentMethod` endpoints require a bearer token via `get_current_user`, as written in §4.4/§5.2.
