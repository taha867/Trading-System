# Phase 0 Backend — Implementation Plan (executed)

## Context

`PLAN.md` defines Phase 0 ("Foundation") and `.claude/specs/phase-0-backend.md` contains the full design for it — folder structure, models, schemas, the generic CRUD factory, auth flow, migrations, and a seed script — reviewed and confirmed with the user (including the three decisions in the spec's §12: no `Setting` table yet, no `/auth/register` endpoint, and the generic CRUD routes are auth-gated).

This plan executed that spec end to end: scaffolded the FastAPI app, stood up Postgres via Docker Compose, wired the generic CRUD engine, and reached the spec's "done when" (log in, add today's RMB→PKR rate, add/edit a payment method — all through the generic table+form pattern, backend side). **Status: complete and verified** — see §11 walkthrough results at the bottom.

Two implementation choices were confirmed directly with the user (not in the original spec):
- **Postgres**: a dedicated `docker-compose.yml` spins up Postgres 16 for local dev — no dependency on the machine's existing system Postgres install or sudo access.
- **Testing**: manual verification only, per spec §11 (curl against the running server). No pytest suite in Phase 0.

## Approach

Built bottom-up, matching the spec's §1 ordering: skeleton → shared foundation → auth → generic CRUD factory → domain models wired to the factory → main.py wiring → migrations → seed → manual verification.

### 1. Docker Compose for Postgres

`backend/docker-compose.yml` — single `postgres:16` service, named volume, env-driven credentials (`POSTGRES_USER=trading`, `POSTGRES_PASSWORD=trading`, `POSTGRES_DB=trading_dev` — local dev defaults, not secrets). **Deviation from the original spec draft**: the host already runs its own system Postgres 16 service bound to port 5432, so the container maps to host port **55432** instead (`"55432:5432"`). `DATABASE_URL=postgresql+asyncpg://trading:trading@localhost:55432/trading_dev`.

### 2. Project skeleton & dependencies

- `backend/requirements/base.txt`: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic`, `pydantic-settings`, `bcrypt`, `pyjwt`, `python-multipart`.
- `backend/requirements/dev.txt`: `-r base.txt` + `ruff`.
- `backend/requirements/prod.txt`: `-r base.txt`.
- venv at `backend/.venv`, `dev.txt` installed.
- `backend/.env` (gitignored) + `backend/.env.example` (committed, placeholder secret): `DATABASE_URL`, `CORS_ORIGINS`, `ENVIRONMENT`, `JWT_SECRET_KEY` (generated via `secrets.token_urlsafe(32)`), `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`.
- `backend/.gitignore`: `.venv/`, `.env`, `__pycache__/`, `*.pyc`.

**Deviation from the original spec draft**: the spec suggested `passlib[bcrypt]` for password hashing. During implementation, seeding a user failed — `passlib` 1.7.4 (unmaintained since 2020) is incompatible with `bcrypt` 5.x (removed the `__about__` attribute passlib's backend probe depends on, and hit a stricter 72-byte check passlib's self-test doesn't handle). Rather than pin `bcrypt` to an old version indefinitely, `src/security.py` uses the `bcrypt` package directly (`bcrypt.hashpw`/`bcrypt.checkpw`) — simpler and actively maintained. `passlib` was dropped from dependencies entirely.

### 3. Shared foundation (spec §3)

Built as specified: `src/models.py` (`Base` + Postgres naming convention), `src/config.py` (`Config(BaseSettings)` — `DATABASE_URL` typed as plain `str`, not `PostgresDsn`, to avoid scheme-validation friction with the `+asyncpg` driver suffix across pydantic versions), `src/database.py` (async engine + `get_db()`), `src/exceptions.py` (`AppException`, `NotFoundException`, `ConflictException`), `src/pagination.py` (`PaginationParams` with `Field(ge=1)`/`Field(ge=1, le=100)` bounds, `PaginatedResponse[T]`), `src/security.py` (bcrypt + PyJWT, see deviation above), `src/middlewares/{__init__,cors,request_context,logging}.py` per CLAUDE.md §2.3.

### 4. `auth/` domain (spec §4)

`src/auth/{models,schemas,service,dependencies,router,constants,exceptions}.py` built exactly as specified: `User` model, `InvalidCredentials`/`TokenExpired`/`TokenInvalid` exceptions (the latter two distinguished via `jwt.ExpiredSignatureError` vs other `jwt.PyJWTError` subclasses, so an expired token reports "Token has expired" rather than a generic invalid message), `UserRead`/`LoginRequest`/`TokenPair`/`RefreshRequest` schemas, `authenticate_user`/`issue_token_pair`/`refresh_access_token` service functions, `get_current_user` dependency (OAuth2 bearer scheme), and `POST /login`, `POST /refresh`, `GET /me` routes.

### 5. Generic CRUD factory (spec §5)

`src/crud.py` — `build_crud_router(model, create_schema, read_schema, update_schema, prefix, tags)`. List is paginated (`is_active=True` only) and auth-gated; create/update catch `IntegrityError` on commit and translate to `ConflictException` (409, not a raw 500); get/update/delete 404 via a shared `_get_active_or_404` helper; soft-delete only sets `is_active = False`. Asserts `hasattr(model, "is_active")` at router-build time per the spec's fail-loudly note.

**Implementation detail resolved via Context7** (not in the original spec): pagination query params use FastAPI's `Annotated[PaginationParams, Query()]` pattern (Query Parameter Models, stable since FastAPI 0.115) rather than `Depends()` — confirmed against current FastAPI docs since a bare Pydantic model isn't Depends-compatible the way a plain function is.

### 6. Domain models on the factory (spec §6)

- `src/purchasing/{models,schemas,router}.py` — `ExchangeRate` (`rate_date` unique, `Numeric(10,4)` rate, `is_active`); router via `build_crud_router(prefix="/exchange-rates", tags=["purchasing"])`.
- `src/payments/{models,schemas,router}.py` — `PaymentMethod` (`name` unique, `is_active`); router via `build_crud_router(prefix="/payment-methods", tags=["payments"])`.
- `src/ledger/models.py` — `LedgerEntry` model only, no router/schemas/service (schema-only per PLAN.md Phase 0).

**Minor deviation**: skipped empty placeholder `constants.py`/`exceptions.py`/`service.py` files for `purchasing`/`payments`/`ledger` — Phase 0 has no domain-specific constants or exceptions beyond what the generic factory and shared `src/exceptions.py` already provide, so empty stub files were left out rather than scaffolded ahead of need.

### 7. `main.py` wiring (spec §7)

`FastAPI()` instance, `register_middlewares(app)`, `AppException` exception handler translating to a JSON `{"detail": ...}` body with the right status code, and all three routers mounted (`/auth`, `/purchasing`, `/payments`). Domain routers already carry their own tags from `build_crud_router`, so `include_router` for `purchasing`/`payments` passes `prefix` only (not a duplicate `tags=`) to avoid doubled tags in the OpenAPI schema.

### 8. Migrations (spec §8)

`alembic init -t async migrations` run inside `backend/`; `env.py` wired to import all domain models and set `target_metadata = Base.metadata`, plus pulls `sqlalchemy.url` from `src.config.settings.DATABASE_URL` (so the same `.env` drives both the app and Alembic — no separate URL to keep in sync). One migration generated and hand-reviewed, then renamed to `migrations/versions/2026-08-07_initial_schema.py`. Reviewed and confirmed: `exchange_rate.rate` is `Numeric(10,4)`, `ledger_entry.debit`/`credit` are `Numeric(12,2)`, all constraint names follow the naming convention (`exchange_rate_pkey`, `user_username_key`, etc.).

### 9. Seed script (spec §9)

`backend/scripts/seed.py` — idempotent (checks existence before insert, safe to re-run): one `User` from `--username`/`--password` CLI args (bcrypt-hashed, never hardcoded), one `ExchangeRate` for `--rate-date` (defaults to today) from `--rate`, and four `PaymentMethod` rows (`Bank`, `JazzCash`, `Easypaisa`, `Cash`).

### 10. Bring-up & manual verification — all passed

1. `docker compose up -d` → Postgres container healthy on port 55432.
2. `alembic upgrade head` → clean, all four tables created with correct types/constraints.
3. `python -m scripts.seed --username admin --password ... --rate 39.50` → created user + exchange rate + 4 payment methods; re-run confirmed idempotent (all "already exists, skipping").
4. `uvicorn src.main:app` → boots cleanly, `/docs` and `/openapi.json` serve all 13 routes with correct tags and response models.
5. Full curl walkthrough against the running server:
   - Login with seeded credentials → token pair; wrong password → 401.
   - Unauthenticated `GET /purchasing/exchange-rates` → 401.
   - `GET /auth/me` with valid token → 200 with correct user.
   - `POST /purchasing/exchange-rates` on a new date → 201; same date as the seeded row → clean 409 (`{"detail":"ExchangeRate already exists"}`), not a raw 500.
   - `POST`/`PUT`/`DELETE` on `/payments/payment-methods` → create/update round-trip correctly; soft-deleted row disappears from the list endpoint but remains in the table with `is_active=false` (confirmed via direct `psql` query).
   - `POST /auth/refresh` with a valid refresh token → new access token that itself authenticates successfully against `/auth/me`.
   - Garbage token → 401; deliberately expired token (crafted with a −1s expiry) → 401 with `{"detail":"Token has expired"}`, distinct from the generic invalid-token message.

All test data created during verification (`Test Wallet Renamed` payment method, the `2026-08-06` exchange rate) was cleaned up afterward; the seeded Phase 0 baseline data (`admin` user, `2026-08-07` rate, four payment methods) remains in the database.

## Files created

All under `backend/`:
```
docker-compose.yml, .env, .env.example, .gitignore, alembic.ini, logging.ini (from alembic init)
requirements/{base,dev,prod}.txt
migrations/{env.py, script.py.mako, versions/2026-08-07_initial_schema.py}
scripts/{__init__,seed}.py
src/{__init__,config,models,database,exceptions,pagination,security,crud,main}.py
src/middlewares/{__init__,cors,request_context,logging}.py
src/auth/{__init__,models,schemas,service,dependencies,router,constants,exceptions}.py
src/purchasing/{__init__,models,schemas,router}.py
src/payments/{__init__,models,schemas,router}.py
src/ledger/{__init__,models}.py
```

## How to run it

```bash
cd backend
docker compose up -d                 # Postgres on localhost:55432
./.venv/bin/alembic upgrade head     # only needed once / after new migrations
./.venv/bin/uvicorn src.main:app --reload --port 8001   # 8000 was occupied by another local service
```

Seeded login: username `admin`, password as set at seed time. Interactive docs at `http://127.0.0.1:8001/docs`.
