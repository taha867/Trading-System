# CLAUDE.md — Coding Standards & Architecture

This file governs *how* code gets written in this repo. `PLAN.md` governs *what* gets built and in which phase. Read both — PLAN.md tells you which entities exist in the phase you're on; this file tells you the shape the code for them should take.

Stack: **FastAPI** (backend, `src/`-layout per `zhanymkanov/fastapi-best-practices`) · **PostgreSQL** via **SQLAlchemy 2.0 (async)** · **Pydantic v2** (backend validation) · **React 19 + Vite** (frontend) · **React Router v7** · **TanStack Query v5** · **react-hook-form + Yup** (frontend validation) · **shadcn/ui** (Radix + Tailwind v4) · **react-hot-toast** · **jwt-decode**.

Sources for the patterns below: official FastAPI docs (`fastapi.tiangolo.com`), `zhanymkanov/fastapi-best-practices`, official React docs (`react.dev`), Pydantic v2 docs, Yup (`jquense/yup`), SQLAlchemy 2.0 async docs — fetched via Context7, not memorized. When in doubt about a library detail, re-fetch rather than guess; these libraries move.

This is a two-app repo, split at the root — nothing backend-related belongs under `frontend/`, and nothing frontend-related belongs under `backend/`:

```
shakeel/                  # repo root
├── PLAN.md               # what to build, phase by phase
├── CLAUDE.md              # this file — how to build it
├── backend/                # FastAPI app — full tree in §2.1
└── frontend/                # React app — full tree in §3.2–3.3
```

Every backend tree in §2 starts *inside* `backend/`; every frontend tree in §3 starts *inside* `frontend/`. The two apps talk to each other over HTTP only (`frontend/src/middleware/fetchClient.js` → `VITE_API_BASE_URL` → the FastAPI app) — no shared imports, no reaching across the boundary.

---

## 1. Architecture overview

Three layers, one direction of dependency, always:

```
React component ──> React Query hook ──> API client ──> FastAPI router ──> service ──> SQLAlchemy model ──> PostgreSQL
     ▲                                         │
     └──────────── Yup validates ──────────────┘   (client-side, UX only)
                                                          Pydantic validates (server-side, the real gate)
```

**Validation happens twice, on purpose, and they are not equal.** Yup on the frontend exists so a user gets an inline error before a network round-trip — it is a courtesy. Pydantic on the backend is the actual gate; it re-validates everything as if the frontend didn't exist, because a future script, a curl call, or a bug in a form should never be able to write bad data. Never relax a Pydantic constraint "because Yup already checks it."

**Backend request lifecycle**, every endpoint, no exceptions:

1. `APIRouter` route receives the request; path/query params and body are typed with Pydantic `Create`/`Update` schemas — invalid input never reaches your function body.
2. `Depends()` injects a database session and (later, once auth exists) the current user.
3. The router calls a **service function** — the router itself contains no business logic, only orchestration (call service, translate service errors to `HTTPException`, return the `Read` schema).
4. The service function talks to SQLAlchemy models and returns plain Python objects/ORM instances.
5. FastAPI serializes the return value through the endpoint's `response_model` (a Pydantic `Read` schema) — this is also a second, cheap defense against ever leaking a field you didn't mean to (a password hash, an internal cost field).

Keeping business logic in services and out of routers is what makes the generic CRUD engine from `PLAN.md` possible: transactional endpoints are hand-written services; lookup-table endpoints are the *same* generic service parameterized by model, reused across every dynamic CRUD (categories, cargo modes, payment methods, expense types).

**Frontend data lifecycle**, every screen (see §3 for why it's split this many ways):

1. A **page** (`pages/`) renders a route and nothing else — no data fetching, no business logic.
2. A **container** (`containers/`) does the route-level work: reads/validates URL params, sets up Suspense/error boundaries, and composes the domain components that make up the screen.
3. **Domain components** (`components/<domain>/`) render the UI and hold local/presentational state; forms among them use **react-hook-form** with a **Yup** resolver.
4. **Domain hooks** (`hooks/<domain>Hooks/`) are the only things allowed to call TanStack Query — `*Queries.js` for reads, `*Mutations.js` for writes — and they're what components actually import.
5. **Domain services** (`services/<domain>Service.js`) are the only things allowed to know an API shape — pure functions, no React, no hooks — called exclusively by the hooks layer.
6. **One shared `middleware/fetchClient.js`** is the only thing allowed to call `fetch` — every service routes through it, which is what makes the 401-refresh-and-retry logic and toast notifications exist in exactly one place instead of every service reimplementing them.
7. A Yup schema that mirrors the backend's Pydantic `Create`/`Update` schema field-for-field guards the form before any of this runs — same required fields, same string lengths, same numeric bounds. If a Pydantic constraint changes, the matching Yup schema changes in the same commit.

---

## 2. Backend

### 2.1 Folder structure

This uses the domain-package layout documented in `zhanymkanov/fastapi-best-practices` ("FastAPI Best Practices and Conventions", explicitly modeled on Netflix's Dispatch) — the structure most FastAPI teams converge on once a project outgrows the official tutorial's flat `routers/` folder. It takes the same idea as FastAPI's own "Bigger Applications" docs (one subpackage per concern) and pushes it further: **every domain package carries its own full slice** — router, schemas, models, service, dependencies, constants, exceptions, utils — instead of routers living in one place and models in another. Cross-domain, framework-wide concerns live as flat modules directly under `src/`, sitting beside the domain packages rather than nested under a `core/`:

```
backend/
├── migrations/                    # `alembic init -t async migrations` — async template, see §2.4
│   ├── versions/
│   │   └── 2026-08-07_add_party_table.py   # descriptive date-based filenames, not Alembic's default hash
│   ├── env.py
│   └── script.py.mako
├── src/
│   ├── auth/                      # User, login/refresh-token issuance — what the frontend's auth flow talks to
│   ├── parties/                   # Party — ONE table, multi-role (china_vendor/cargo_agent/customer/local_vendor).
│   │                               #   No separate party-ledger table: a party's balance/history is a query over
│   │                               #   ledger.LedgerEntry filtered by party_id (PLAN.md Principle 4)
│   ├── catalog/                   # Category, Model, Item
│   │   ├── router.py             # APIRouter, thin — calls service.py — the "routes" layer
│   │   ├── schemas.py            # Pydantic Create / Read / Update
│   │   ├── models.py             # SQLAlchemy ORM classes
│   │   ├── service.py            # business logic, talks to models.py
│   │   ├── dependencies.py       # domain-local Depends() (e.g. resolve Item by id)
│   │   ├── constants.py          # error codes, enum-like literals for this domain
│   │   └── exceptions.py         # domain-specific exceptions (caught by router.py)
│   ├── purchasing/                # PurchaseOrder, PurchaseOrderLine — references Party by id, doesn't own it
│   ├── cargo/                     # CargoMode, CargoCostBasis, CargoShipment, CargoAllocation
│   ├── inventory/                  # StockLot, StockMovement
│   ├── sales/                      # SalesOrder, SalesOrderLine — references Party by id, doesn't own it
│   ├── payments/                   # PaymentAccount, PaymentTransaction
│   ├── expenses/                   # ExpenseCategory, Expense, RecurringExpenseTemplate
│   ├── ledger/                     # LedgerEntry — written to by every domain above, owned by none
│   ├── middlewares/                # ASGI/HTTP middleware — cross-cutting, runs before any router. See §2.3
│   │   ├── __init__.py            # register_middlewares(app) — the single call main.py makes
│   │   ├── cors.py                # CORSMiddleware config, sourced from src/config.py's CORS_ORIGINS
│   │   ├── request_context.py     # request-id generation + injection, for log correlation
│   │   └── logging.py             # structured access-log middleware (method, path, status, duration)
│   ├── config.py                  # global Config(BaseSettings) — DATABASE_URL, CORS, environment
│   ├── models.py                  # shared DeclarativeBase + Postgres naming-convention metadata
│   ├── exceptions.py              # shared exception base classes, error response schema
│   ├── pagination.py              # shared pagination params/response wrapper, reused by every list endpoint
│   ├── database.py                # async engine, async_sessionmaker, get_db() dependency
│   ├── crud.py                    # generic CRUD router/service factory (Principle 3, PLAN.md)
│   └── main.py                    # creates FastAPI(), registers middlewares, includes every domain's router
├── requirements/
│   ├── base.txt                  # installed everywhere
│   ├── dev.txt                   # + lint tools, imports base.txt
│   └── prod.txt                  # imports base.txt, nothing extra
├── templates/                     # server-rendered email/PDF templates (invoices, statements) if needed
├── logging.ini
├── alembic.ini                    # script_location = migrations
└── .env                           # never committed
```

Each domain package is self-contained and importable on its own (`from src.catalog import service`) — that's what lets a domain carry its own `constants.py`/`exceptions.py` without polluting a shared one. Two packages are deliberately one-way:

- `ledger/` — every other domain imports *into* it (to post an entry) but it never imports back. That's what keeps the ledger trustworthy as an audit trail rather than something every module reads and reinterprets.
- `parties/` — `purchasing/`, `cargo/`, and `sales/` all import `Party` by id from here; `parties/` never imports them. This is the backend half of PLAN.md's Principle 2 — a China vendor, a cargo agent, a customer, and a local vendor are one `Party` with roles, not four owned copies scattered across the domains that happen to transact with them.

**Where a Phase 0-style lookup entity lives**: a lookup table belongs in the domain that primarily consumes it, not in a domain of its own — `ExchangeRate` lives in `purchasing/` (it's read at PO-line creation), `PaymentMethod` lives in `payments/` (alongside the `PaymentAccount` instances built from it), and app-wide `Setting` lives as a table owned by `src/config.py`'s domain (no dedicated package). The exception is exactly the two cases above — a lookup genuinely shared by domains that shouldn't own each other's data (`parties/`) or that everything writes into but nothing should reinterpret (`ledger/`) — those get their own package specifically *because* sharing them by reference (not duplication) is the point.

Two details worth carrying over deliberately from that reference structure:

- **Give SQLAlchemy's `MetaData` an explicit index/constraint naming convention** in `src/models.py`, so every migration produces predictable, greppable constraint names instead of Alembic's autogenerated ones:

```python
# src/models.py
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

- **Split `requirements/` by environment** (`base.txt` / `dev.txt` / `prod.txt`) rather than one flat `requirements.txt` — `dev.txt` pulls in linters and local-dev tooling on top of `base.txt`; `prod.txt` stays minimal. Keeps a stray dev-only dependency from ever reaching the production image.

### 2.2 FastAPI conventions

- **Routers are thin.** A router function does exactly three things: validate input (via the Pydantic parameter type — already done by the time your code runs), call one service function, and return. If a router function is more than ~10 lines, logic has leaked into it that belongs in `service.py`.
- **Always set `response_model`** on every route. It's your outbound contract and it silently strips fields the schema doesn't declare — an actual safety net, not decoration.
- **Use `Depends()` for anything cross-cutting** — the DB session, the current user once auth exists, shared query params like pagination. Don't reconstruct a session or re-parse a param inside a route body.
- **Use `Annotated[Type, Depends(...)]` / `Annotated[Type, Header()]`** for dependency and parameter declarations — this is the current FastAPI idiom, not the older default-value style.
- **One `APIRouter` per domain**, included in `main.py` with its own `prefix` and `tags`, matching the folder structure above — every domain adds one line to `main.py`, nothing more (the full `main.py`, including middleware registration, is in §2.3):

```python
app.include_router(catalog_router, prefix="/catalog", tags=["catalog"])
app.include_router(purchasing_router, prefix="/purchasing", tags=["purchasing"])
```

- **Raise `HTTPException` from services, not bare exceptions** — or better, raise a domain exception in the service and translate it to `HTTPException` in the router, so the service layer stays framework-agnostic and testable without spinning up FastAPI.
- **Push repeated "does this exist" checks into a dependency**, not into every route body — this is what `dependencies.py` in each domain package is for:

```python
# src/catalog/dependencies.py
from fastapi import Depends
from src.catalog import service
from src.catalog.exceptions import ItemNotFound

async def valid_item(item_id: int) -> Item:
    item = await service.get_by_id(item_id)
    if not item:
        raise ItemNotFound()
    return item
```

```python
# src/catalog/router.py
@router.get("/items/{item_id}", response_model=ItemRead)
async def get_item(item: Item = Depends(valid_item)):
    return item

@router.put("/items/{item_id}", response_model=ItemRead)
async def update_item(update: ItemUpdate, item: Item = Depends(valid_item)):
    return await service.update(item, update)
```

Every route that touches `item_id` reuses `valid_item` instead of re-writing the same "fetch or 404" three times — and the same shape applies to `valid_purchase_order`, `valid_party`, `valid_stock_lot`, anywhere a route path carries an id.

### 2.3 Middleware

Middleware runs before any router sees the request and after any router produces a response — it's for concerns that apply to *every* endpoint, not one domain's business logic. Keep each concern in its own file under `src/middlewares/`, registered from one place:

```python
# src/middlewares/__init__.py
from fastapi import FastAPI
from src.config import settings
from src.middlewares.cors import add_cors_middleware
from src.middlewares.request_context import RequestContextMiddleware
from src.middlewares.logging import AccessLogMiddleware

def register_middlewares(app: FastAPI) -> None:
    # add_middleware() stacks LIFO: the LAST one added runs FIRST on the way in,
    # and LAST on the way out — so request-id must be added last to wrap everything else.
    add_cors_middleware(app, origins=settings.CORS_ORIGINS)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestContextMiddleware)
```

```python
# src/middlewares/cors.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def add_cors_middleware(app: FastAPI, origins: list[str]) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

```python
# src/middlewares/request_context.py
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response
```

```python
# src/main.py
from fastapi import FastAPI
from src.middlewares import register_middlewares
from src.catalog.router import router as catalog_router

app = FastAPI(title="Trading System")
register_middlewares(app)
app.include_router(catalog_router, prefix="/catalog", tags=["catalog"])
```

`request_context.py`'s request id isn't a column on `LedgerEntry` — PLAN.md's ledger schema doesn't have one — it's what you put in the log line a ledger-affecting service (§4) writes alongside its commit, so a specific `LedgerEntry` row can be traced back to the HTTP request that created it via logs, without adding a field to the table itself.

### 2.4 Pydantic conventions

- **Three schemas per entity, minimum**: `XCreate` (what the client sends to create), `XRead` (what the API returns — includes `id`, timestamps, computed fields), `XUpdate` (usually every field optional). Never reuse `XCreate` as a response model — that's how internal-only fields leak.
- **`XRead` needs `model_config = ConfigDict(from_attributes=True)`** so it can be built directly from a SQLAlemy ORM instance (`XRead.model_validate(db_item)`), not a manual dict.
- **Use `Annotated[type, Field(...)]` for constraints**, not bare `Field()` defaults, and prefer it over ad hoc `@field_validator` when a plain bound (`gt=0`, `max_length=120`) will do:

```python
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field

class ItemCreate(BaseModel):
    category_id: int
    model_id: int
    sku: Annotated[str, Field(max_length=64)]
    variant: Annotated[str | None, Field(max_length=64)] = None

class ItemRead(ItemCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int

class ItemUpdate(BaseModel):
    variant: Annotated[str | None, Field(max_length=64)] = None
```

- **Reach for `@field_validator` only for cross-field or business-rule checks** money constraints can't express alone — e.g. "a `PurchaseOrderLine.rate_rmb` must be positive" is a `Field(gt=0)`; "a `CargoShipment.cost_basis` must match one of the active `CargoCostBasis` codes" is a validator that queries or checks against a known set.
- **Money is `Decimal`, never `float`**, on every schema that touches RMB, PKR, or any ledger amount — mirror the database's `Numeric` columns exactly so a schema round-trip never silently rounds real currency.

### 2.5 SQLAlchemy (2.0, async) conventions

- **Async engine + `async_sessionmaker`, one session per request**, injected via `Depends`:

```python
# src/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

engine = create_async_engine(settings.database_url, echo=settings.debug)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
```

- **Declare models with `Mapped[]` / `mapped_column()`**, the SQLAlchemy 2.0 typed style — not the legacy `Column(...)` class-attribute style:

```python
# src/catalog/models.py
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models import Base  # shared DeclarativeBase with the naming convention, not a local one

class Item(Base):
    __tablename__ = "item"
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"))
    sku: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)   # soft delete flag, see §4
```

- **Wrap writes in `async with session.begin():`** so a partially-applied multi-table write (e.g. a sale that touches `SalesOrder`, `SalesOrderLine`, `StockLot`, and `LedgerEntry` in one action) can't commit half-finished.
- **Load relationships explicitly with `selectinload`/`joinedload`** on the query that needs them — never rely on lazy-load inside an async context, it will throw. This matters a lot for the cargo → PO-line allocation and stock-lot → sales-line consumption joins, which are the two places this system's queries get genuinely relational.
- **Never call a synchronous ORM session from inside an `async def`.** It blocks the event loop and can deadlock the connection pool under load — this is the single most common mistake when a route or service is copy-pasted from sync SQLAlchemy examples. Every session in this codebase is an `AsyncSession`, no exceptions.
- **Migrations live in `migrations/`, not the default `alembic/`.** Set it up with the async template so it matches the async engine from day one: `alembic init -t async migrations`, with `alembic.ini`'s `script_location` pointed at it. Use descriptive, date-prefixed revision filenames (`2026-08-07_add_party_table.py`) instead of Alembic's default autogenerated hash — that's what makes `git log migrations/versions/` readable months later. Every schema change is a migration, generated (`alembic revision --autogenerate`) and reviewed by eye before applying — autogenerate misses some constraint changes, especially on `Numeric` precision. Batch one migration per feature, not per coding session — five tiny migrations for one `PurchaseOrderLine` field is noise later.

### 2.6 Settings & config

Use `pydantic-settings` for `src/config.py` — a `Config(BaseSettings)` class reading from `.env`, typed, validated at startup (a missing `DATABASE_URL` should fail immediately on boot, not on the first query). Keep it decoupled rather than one growing monolith: global, cross-domain settings (`DATABASE_URL`, `CORS_ORIGINS`, `ENVIRONMENT`) live in `src/config.py`; a domain that genuinely needs its own settings (e.g. `payments/config.py` for a payment-gateway webhook secret, once one exists) gets its own small `BaseSettings` subclass instead of bloating the global one:

```python
# src/payments/config.py
from pydantic_settings import BaseSettings

class PaymentsConfig(BaseSettings):
    WEBHOOK_SECRET: str | None = None

payments_settings = PaymentsConfig()
```

```python
# src/config.py
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    DATABASE_URL: PostgresDsn
    CORS_ORIGINS: list[str] = []
    ENVIRONMENT: str = "development"

settings = Config()
```

---

## 3. Frontend

### 3.1 Stack

React 19 + Vite · React Router v7 · TanStack Query v5 · react-hook-form + Yup resolver · shadcn/ui (Radix + Tailwind v4) · react-hot-toast · jwt-decode.

This is a **layered-by-responsibility** structure, not the feature-first one — the layers (`pages/` → `containers/` → `components/` → `hooks/` → `services/` → `middleware/`) are fixed and shared by every domain, and *within* each layer things subdivide by domain (`auth`, `parties`, `catalog`, `purchasing`, `cargo`, `inventory`, `sales`, `payments`, `expenses`, `reporting`). The rule of thumb: if you're asking "where does X live," first find the layer (is it a route? a query? a raw API call?), then find the domain folder inside it.

### 3.2 Root config

```
frontend/
├── src/
├── index.html
├── vite.config.js        # @/ alias → ./src, react-compiler babel plugin
├── jsconfig.json         # matches @/ alias for editor intellisense
├── tailwind.config.js
├── postcss.config.js
├── components.json       # shadcn/ui config (style: new-york, aliases: @/components, @/lib, @/hooks)
├── eslint.config.js
└── .env                  # VITE_API_BASE_URL, etc. — never committed
```

Use the `@/` alias from the start (`@/components/...`, `@/hooks/...`) — it's wired in `vite.config.js` and `jsconfig.json` already, and the shadcn CLI generates its output against it, so there's no reason to fall back to `../../../` relative imports on a fresh project.

### 3.3 `src/` layout

```
src/
├── main.jsx                # ReactDOM.createRoot, wraps App with QueryClientProvider etc.
├── App.jsx                 # all routing lives here: <Routes> with Public / AuthRoute / ProtectedRoute groups
├── index.css                # Tailwind entry + design tokens/CSS variables
│
├── pages/                   # one thin file per route — renders a container, nothing else
│   ├── DashboardPage.jsx           # Phase 8 landing: balance statement + sell-through chart
│   ├── CatalogPage.jsx
│   ├── PartiesPage.jsx / PartyDetailPage.jsx        # party statement — full history + balance
│   ├── PurchaseOrdersPage.jsx / PurchaseOrderCreatePage.jsx
│   ├── CargoShipmentsPage.jsx / CargoShipmentCreatePage.jsx
│   ├── InventoryPage.jsx
│   ├── SalesOrdersPage.jsx / SalesOrderCreatePage.jsx
│   ├── PaymentsPage.jsx
│   ├── ExpensesPage.jsx
│   └── AuthPages/
│       ├── SignInPage.jsx
│       ├── SignUpPage.jsx           # kept even for a single user today — see PLAN.md, "Decide early, revisit rarely" → "Auth now, even solo"
│       ├── ForgotPasswordPage.jsx
│       └── ResetPasswordPage.jsx
│
├── containers/              # route-level orchestration: reads URL params, validates them,
│   │                          sets up Suspense boundaries, composes components together
│   ├── PartyDetailContainer.jsx           # partyId param -> party + its ledger history
│   ├── PurchaseOrderContainer.jsx         # orderId param -> PO + lines + cargo allocation
│   ├── SalesOrderContainer.jsx
│   └── DashboardContainer.jsx
│
├── components/              # grouped by domain, plus shared "common"/"custom"/"ui" folders
│   ├── ui/                   # shadcn/ui primitives (button, dialog, input, select, tabs, ...) — generated, rarely hand-edited
│   ├── custom/                # reusable form-field wrappers on top of ui/, wired to react-hook-form
│   │   └── FormField.jsx / FormSelect.jsx / FormFileInput.jsx / index.js   # barrel export
│   ├── common/                 # cross-domain shared components
│   │   ├── ProtectedRoute.jsx / AuthRouteProtection.jsx / AuthFallback.jsx / AppInitializer.jsx
│   │   ├── CrudTable.jsx / CrudDrawer.jsx     # the generic config-driven CRUD engine (PLAN.md Principle 3) —
│   │   │                                        every lookup screen (categories, cargo modes, payment methods,
│   │   │                                        expense types) is this pair plus a config object, not a new page
│   │   ├── PaginationControls.jsx / ConfirmDeleteDialog.jsx / ToastNotification.jsx
│   │   └── CurrencyAmount.jsx                 # RMB/PKR-aware amount display, backs §4's "money is Decimal" rule on the UI side
│   ├── auth/
│   │   ├── SignIn.jsx / SignUp.jsx / ForgotPassword.jsx / ResetPassword.jsx / AuthLayout.jsx
│   │   └── form/                # SignInForm, SignUpForm, ForgotPasswordForm, ResetPasswordForm, ChangePasswordForm
│   ├── parties/
│   │   ├── PartyList.jsx / PartyStatement.jsx / PartyRoleBadges.jsx / PartyInitializer.jsx (skeleton/suspense fallback)
│   │   └── form/                # PartyForm.jsx — one form, `roles` multi-select (china_vendor/cargo_agent/customer/local_vendor)
│   ├── catalog/
│   │   ├── CategoryList.jsx / ModelList.jsx / ItemList.jsx
│   │   └── form/                # CategoryForm, ModelForm, ItemForm
│   ├── purchasing/
│   │   ├── PurchaseOrderList.jsx / PurchaseOrderDetail.jsx / PurchaseOrderLineTable.jsx (live RMB→PKR conversion)
│   │   └── form/                # PurchaseOrderForm.jsx
│   ├── cargo/
│   │   ├── CargoShipmentList.jsx / CargoAllocationTable.jsx (cost split preview by weight/CBM/piece)
│   │   └── form/                # CargoShipmentForm.jsx
│   ├── inventory/
│   │   ├── StockLotTable.jsx (model-wise, old lot vs new lot side by side) / StockAdjustmentDialog.jsx
│   │   └── form/                # StockAdjustmentForm.jsx
│   ├── sales/
│   │   ├── SalesOrderList.jsx / SalesOrderDetail.jsx / SalesOrderLineTable.jsx (FIFO lot draw-down preview)
│   │   └── form/                # SalesOrderForm.jsx
│   ├── payments/
│   │   ├── PaymentAccountList.jsx / PaymentTransactionList.jsx
│   │   └── form/                # PaymentForm.jsx
│   ├── expenses/
│   │   ├── ExpenseList.jsx / RecurringExpenseList.jsx
│   │   └── form/                # ExpenseForm.jsx
│   ├── reporting/               # Phase 8 — reads other domains' data, owns none
│   │   ├── BalanceStatement.jsx / SellThroughChart.jsx / ReorderPriorityTable.jsx
│   ├── home/Home.jsx
│   ├── Navbar.jsx
│   └── Footer.jsx
│
├── hooks/                   # one subfolder per domain; each domain splits queries vs mutations
│   ├── authHooks/
│   │   ├── authHooks.js          # useAuth() context accessor + derived hooks
│   │   └── authMutations.js      # useSignIn, useSignUp, useSignOut, useRefreshToken
│   ├── partyHooks/
│   │   ├── partyQueries.js       # useParties, usePartyDetail, usePartyLedger
│   │   └── partyMutations.js     # useCreateParty, useUpdateParty, useDeactivateParty
│   ├── catalogHooks/       (categoryQueries/Mutations, modelQueries/Mutations, itemQueries/Mutations)
│   ├── purchasingHooks/    (purchaseOrderQueries.js, purchaseOrderMutations.js)
│   ├── cargoHooks/         (cargoQueries.js, cargoMutations.js)
│   ├── inventoryHooks/     (inventoryQueries.js, inventoryMutations.js)
│   ├── salesHooks/         (salesQueries.js, salesMutations.js)
│   ├── paymentsHooks/      (paymentsQueries.js, paymentsMutations.js)
│   ├── expensesHooks/      (expensesQueries.js, expensesMutations.js)
│   ├── reportingHooks/     (reportingQueries.js — read-only, this domain has no mutations)
│   └── useImperativeDialog.js    # generic reusable hook, not domain-specific
│
├── services/                 # one file per domain — pure API-call functions, no React.
│   │                           each function: build query string -> call fetchClient -> shape/return response.data
│   ├── authService.js
│   ├── partyService.js
│   ├── catalogService.js
│   ├── purchasingService.js
│   ├── cargoService.js
│   ├── inventoryService.js
│   ├── salesService.js
│   ├── paymentsService.js
│   ├── expensesService.js
│   └── reportingService.js
│
├── middleware/
│   └── fetchClient.js         # single low-level fetch wrapper for the whole app:
│                                 base URL, auth header injection, 401 → refresh-token-and-retry
│                                 (single-flight refresh lock), timeout via AbortSignal, toast on
│                                 success/error, normalized {data, status, ok, headers} return shape
│
├── contexts/
│   └── authContext.jsx        # React context + provider for current user/auth state
│
├── reducers/
│   └── authReducer.js          # reducer consumed by authContext
│
├── validations/                # one schema file per domain (Yup), imported by forms and containers
│   ├── authSchemas.js
│   ├── partySchemas.js
│   ├── catalogSchemas.js       # categoryCreate/Update, modelCreate/Update, itemCreate/Update
│   ├── purchasingSchemas.js
│   ├── cargoSchemas.js
│   ├── inventorySchemas.js
│   ├── salesSchemas.js
│   ├── paymentsSchemas.js
│   ├── expensesSchemas.js
│   └── commonSchemas.js
│
├── utils/                     # pure helper functions, grouped by concern (not by domain necessarily)
│   ├── constants.js             # enums: PARTY_ROLE, PURCHASE_ORDER_STATUS, CARGO_MODE, CARGO_COST_BASIS,
│   │                              STOCK_MOVEMENT_TYPE, PAYMENT_DIRECTION, HTTP_STATUS, TOAST_MESSAGES
│   ├── queryKeys.js              # centralized TanStack Query key factories per domain
│   │                              (e.g. partyKeys, purchaseOrderKeys, stockLotKeys — each with .all/.lists()/.list()/.detail())
│   ├── queryParams.js             # buildQueryString(options)
│   ├── tokenUtils.js               # getToken/getRefreshToken/storeToken/removeTokens/hasValidRefreshToken
│   ├── currencyUtils.js             # formatRMB/formatPKR, RMB→PKR preview math mirroring backend snapshot logic
│   └── fifoPreviewUtils.js, formSubmitWithToast.js
│
└── lib/
    └── utils.js                 # shadcn's cn() classnames helper (kept separate from utils/, which is app logic)
```

### 3.4 Layering & conventions

1. **Layering is one-directional**: `pages/` (route entry, no logic) → `containers/` (param parsing, Suspense/error boundaries, composition) → `components/<domain>/` (presentational + local state) → `hooks/<domain>Hooks/` (TanStack Query queries/mutations) → `services/<domain>Service.js` (raw API calls) → `middleware/fetchClient.js` (the one shared HTTP client). A component never imports a service directly, and a service never imports a hook — each layer only talks to the one below it.
2. **Domain-first grouping inside `components/`, `hooks/`, `services/`, `validations/`** — each business domain (`auth`, `parties`, `catalog`, `purchasing`, `cargo`, `inventory`, `sales`, `payments`, `expenses`, `reporting`) gets its own folder/file so a feature stays co-located; `common/`, `custom/`, and `ui/` hold the cross-domain and generic pieces, including the `CrudTable`/`CrudDrawer` pair every dynamic lookup screen reuses.
3. **Queries vs. mutations split**: every domain's `hooks/` folder separates read hooks (`*Queries.js`) from write hooks (`*Mutations.js`), and mutations always invalidate through the centralized `utils/queryKeys.js` factory rather than hand-built key arrays — this is what keeps a `PurchaseOrderForm` submission correctly invalidating the `PurchaseOrderList` and the `StockLotTable` it eventually feeds, without every mutation needing to know every screen that might be showing stale data.
4. **`ui/` vs. `custom/`**: `ui/` is shadcn-generated primitives — don't hand-roll logic there, regenerate via the shadcn CLI instead. `custom/` wraps those primitives into form-aware components (`FormField` wired to `react-hook-form`'s `Controller`, etc.) — this is the layer that actually knows about form state.
5. **One fetch client**: every network call funnels through `middleware/fetchClient.js`, which centralizes auth headers, 401/refresh-token retry, timeouts, and toast notifications. `services/*.js` never call `fetch` directly — if a new service file has a raw `fetch(...)` in it, that's a review flag.

### 3.5 Forms & validation (react-hook-form + Yup)

Forms use **react-hook-form** for field state and submission, with a **Yup** resolver for validation — not raw `useState`-per-field, and not React 19's `useActionState` for this role (react-hook-form's `formState.isSubmitting`/`errors` already cover what `useActionState` would give you, and running both would just be two sources of truth for the same pending/error state):

```jsx
// components/parties/form/PartyForm.jsx
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { partyCreateSchema } from '@/validations/partySchemas';
import { useCreateParty } from '@/hooks/partyHooks/partyMutations';
import { FormField, FormSelect } from '@/components/custom';

export function PartyForm({ onSuccess }) {
  const { control, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: yupResolver(partyCreateSchema),
    defaultValues: { name: '', roles: [] },
  });
  const { mutateAsync: createParty } = useCreateParty();

  const onSubmit = async (values) => {
    await createParty(values);   // fetchClient toasts success/error; mutation invalidates partyKeys
    onSuccess?.();
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <Controller name="name" control={control} render={({ field }) => (
        <FormField {...field} label="Party name" error={errors.name?.message} />
      )} />
      <Controller name="roles" control={control} render={({ field }) => (
        <FormSelect {...field} label="Roles" multiple options={PARTY_ROLE_OPTIONS} error={errors.roles?.message} />
      )} />
      <button type="submit" disabled={isSubmitting}>Save</button>
    </form>
  );
}
```

```javascript
// validations/partySchemas.js
import { object, string, array } from 'yup';

const partyRoleField = array().of(string().oneOf(['china_vendor', 'cargo_agent', 'customer', 'local_vendor']))
  .min(1, 'Select at least one role');

export const partyCreateSchema = object({
  name: string().required().max(120),
  roles: partyRoleField,
});

// mirrors backend PartyUpdate — every field optional
export const partyUpdateSchema = partyCreateSchema.partial();
```

Yup conventions to keep consistent across every `validations/<domain>Schemas.js` file:

- **Build small reusable field validators, then compose** with `.shape()`/`.concat()` — don't repeat the same `string().required().max(120)` across five domain schema files.
- **Use `.pick()` / `.omit()`** rather than hand-duplicating a schema when a form only needs a subset of a bigger entity's fields.
- **Use `.partial()`** for every `*Update` schema instead of writing it by hand — it should always be a strict subset of the matching `*Create` schema, never a divergent one.
- **Use `.exact()`** on forms where a stray field indicates a bug (a mis-bound `Controller` name) rather than silently accepting it.
- **Watch the nested-optional-object gotcha**: Yup casts before validating, so an object field with its own `required()` children needs `.default(undefined)` or `.nullable()` at the parent, or a genuinely optional nested object fails validation on missing input. This will bite the `CargoShipmentForm`'s optional per-line allocation override if not handled explicitly.
- **Yup is the courtesy layer, Pydantic is the gate** (§1) — never encode a rule in a `validations/*Schemas.js` file that isn't also enforced by the matching backend schema in `src/<domain>/schemas.py`.

### 3.6 React 19 features, used deliberately (not by default)

React 19 is in the stack for specific wins, not to replace react-hook-form/TanStack Query wholesale:

- **React Compiler** (wired via the babel plugin in `vite.config.js`) handles memoization automatically — don't reach for manual `useMemo`/`useCallback` in new components purely for referential stability; let the compiler do it, and only hand-optimize where profiling actually shows a problem.
- **`useOptimistic`** for the handful of interactions where waiting on a round-trip would feel laggy and a rollback-on-failure is acceptable — e.g. toggling a `PurchaseOrderLine` as "received," or removing a `SalesOrderLine` row before submit. This sits inside the domain component, on top of the mutation from the hooks layer, not as a replacement for it.
- **`use()`** for reading a Suspense-boundary promise or context conditionally (e.g. a `PartyInitializer`/`CommentInitializer`-style skeleton component reading a promise passed down from its container) instead of a `useEffect` + `useState` combo.

### 3.7 Responsive design

Every screen must work on a phone, not just a desk — whoever's checking stock in the storage area or confirming a sale with a walk-in customer is far more likely to have a phone in hand than to be sitting at the desktop that has the PurchaseOrders screen open. Responsiveness is not optional polish here; treat it the same as any other non-negotiable in §4.

- **Mobile-first, always.** Write the unprefixed Tailwind classes for the smallest screen first, then layer on `sm:`/`md:`/`lg:` for wider ones — never the reverse (styling for desktop and trying to patch mobile in after). shadcn/ui's primitives are unstyled Radix underneath; responsiveness is never inherited for free, it's on whoever builds each `components/<domain>/` piece to add the breakpoint classes.
- **Every form (§3.5) stacks to a single column below `md`.** A `PurchaseOrderForm` or `SalesOrderForm` laid out `grid md:grid-cols-2` on desktop needs to fall back to one column, full-width inputs, on a phone — not shrink the two-column grid until it's unreadable.
- **Tables are the highest-risk component** — `CrudTable`, `PurchaseOrderLineTable`, `SalesOrderLineTable`, `StockLotTable` all carry enough columns (qty, RMB rate, PKR rate, landed cost, margin, ...) that they will overflow a phone screen. Pick one deliberately per table, don't let it default to breaking the layout: wrap it in `overflow-x-auto` on its own container so it scrolls horizontally without ever widening the page body, or collapse it to a stacked card layout below `sm` for tables where horizontal scrolling would hide the one column (usually the total) a phone user actually needs.
- **Navigation collapses.** `Navbar.jsx` needs a mobile menu state below `md` — a desktop-width nav bar with nine domains (`parties`, `catalog`, `purchasing`, `cargo`, `inventory`, `sales`, `payments`, `expenses`, `reporting`) will not fit a phone's width un-collapsed.
- **Check at three widths before calling a screen done**: ~375px (phone), ~768px (tablet), ~1280px (desktop) — not just a resized desktop browser window, and not just the widest one because it's the one open while building.

---

## 4. Non-negotiables (cross-cutting, from PLAN.md)

These apply in every domain, front and back, regardless of phase:

- **Soft delete everywhere.** Every table gets `is_active: Mapped[bool]`; the generic CRUD factory's "delete" endpoint sets it `False`, never `DELETE FROM`. History (an old PO referencing a since-retired vendor) must never break.
- **Money is `Decimal`/`Numeric`, never `float`**, backend schema through database column through frontend display formatting (`utils/currencyUtils.js`, `components/common/CurrencyAmount.jsx`).
- **Every ledger-affecting action posts a `LedgerEntry` in the same transaction as its domain write** — a sale, a payment, an expense. If a service function can commit its own table without also committing a ledger row, that's a bug, not a later cleanup task.
- **FIFO for stock consumption** — a `SalesOrderLine` service must consume `StockLot` rows oldest-received-first, not average across lots.
- **Snapshot, don't recompute, historical rates** — a `PurchaseOrderLine`'s `rate_pkr` is stored at creation time from that day's `ExchangeRate`, never recalculated from "today's" rate later.

---

## 5. How this file relates to PLAN.md

`PLAN.md` tells you *what* to build this phase — which entities, which screens, which "done when" line to satisfy. This file tells you *how* to write it once you know what it is. When they seem to conflict, PLAN.md's Architecture Decisions section (Party roles, the ledger, lot-based costing) wins on data model; this file wins on code shape and library usage.
