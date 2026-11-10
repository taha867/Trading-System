# Multi-User Analysis How Login Works Today and How to Make It Multi-User

> **Addendum (2026-11-10):** the sales and purchase search, detail and "Other entries" endpoints added since this was written are open to every logged-in user, and the detail pages show cost and margin. Any per-role restriction designed here must cover them. The Neon connection string was exposed in a tracked script and in a chat transcript: rotate the password.

Written 2026-10-07. This file answers three questions in plain words:

1. Does the app have hardcoded credentials?
2. How does the app work overall right now?
3. How do we turn it from one user into many users?

Everything here comes from reading the root docs (`PLAN.md`, `CLAUDE.md`, `EXAMPLE_STRUCTURE.md`, `MARKETING_PLAN.md`) and the backend and frontend code. File paths are given so you can check anything yourself. Nothing in the code was changed.

---

## 1. Short answers

**"Is the app hardcoded to one user's credentials?"** Mostly no.

- The backend has a real `user` table. Passwords are stored as bcrypt hashes. Login gives back JWT tokens.
- No username or password is written inside the backend or frontend source code.
- The login form starts empty. There is no "skip login" flag.

**"Then why is it single-user?"** Because there is no way to create a second user from the app.

- The one user is created by running a script by hand.
- There is no sign-up, no "add user" screen, no change-password, and no roles.
- Nothing records *who* made a sale, payment or expense.

So you are partly right. It behaves like a single-user app, but the reason is missing features, not hardcoded login.

---

## 2. Where credentials are written down

These are the places where secrets or passwords appear. None of them is in the application logic.

| Where | What is there | Is it committed to git? | Risk |
|---|---|---|---|
| `backend/credentials.md` | The seeded login (`admin` plus a password) and the seed command | No, it is gitignored | Plain text password sitting in your folder |
| `frontend/credentials.md` | The same login, written down again | No, it is gitignored | Same as above |
| `docker-compose.yml` | Postgres user, password and database name are all `trading`, on port 55432 | **Yes** | Fine on your laptop, never use these in production |
| `backend/.env.example` | A placeholder `JWT_SECRET_KEY=change-me-...` and a `trading:trading` database URL | Yes | Only a placeholder, but never copy it as-is into production |
| `backend/.env` | Your real secrets: a 43-character JWT secret and the database URL | No, it is gitignored | Normal and fine, just keep it private |

What to do about it:

- If the password in `credentials.md` is a real one, change it before the app is on the internet. (A script in `scripts/` can create users, so you can make a new one and deactivate the old one.)
- Do not commit `credentials.md` or `.env`.
- Before going live, use a strong database password and do not use the `docker-compose.yml` values.

---

## 3. How the app works today

### 3.1 The big picture

```
Browser (React)  ->  FastAPI backend  ->  PostgreSQL
```

- **Frontend:** React 19 + Vite. Layers go `pages -> containers -> components -> hooks -> services -> fetchClient`.
- **Backend:** FastAPI + async SQLAlchemy. Each business area is its own folder with a router, schemas, models and service.
- **Business:** you buy mobile accessories from China in RMB, ship them by cargo, hold stock in lots, sell wholesale in PKR, and track money through one ledger.

### 3.2 Backend areas (folders in `backend/src/`)

| Area | What it holds |
|---|---|
| `auth` | `User`, login and refresh |
| `catalog` | Category, Brand, Model, Item (SKU) |
| `parties` | One `Party` table for China vendors, cargo agents, customers and local vendors (a party can have several roles) |
| `purchasing` | Exchange rates, purchase orders and their lines (rate is saved at creation time) |
| `cargo` | Cargo modes, cost bases, shipments, and how cargo cost is split across PO lines |
| `inventory` | Stock lots and stock movements |
| `sales` | Sales orders and lines, with FIFO stock use |
| `payments` | Payment methods, accounts and transactions |
| `expenses` | Expense categories, expenses and recurring templates |
| `ledger` | One append-only money record. Everything posts here |
| `reporting` | Dashboard, sell-through, margin and reorder reports |

Key rules that already work:

- **Money is `Decimal`/`Numeric`**, never float.
- **Soft delete:** records get `is_active = false`, they are not removed.
- **Ledger:** a service adds the ledger row and its own rows, then commits once, so they succeed or fail together.
- **FIFO:** a sale takes stock from the oldest lot first.

### 3.3 How login works now

1. The login form sends `username` and `password` to `POST /auth/login`.
2. The backend finds the user, checks the user is active and checks the bcrypt hash.
3. It returns two tokens:
   - an **access token** that lasts 30 minutes,
   - a **refresh token** that lasts 7 days.
4. The frontend saves both in the browser's `localStorage`.
5. Every later request sends `Authorization: Bearer <access token>`.
6. If the backend answers 401, the frontend uses the refresh token once to get a new pair and retries the request. If that fails, the user is sent to the sign-in page.
7. On page load the frontend calls `GET /auth/me` to find out who is logged in.

Every route except `/auth/login` and `/auth/refresh` needs a valid token. (The API docs pages `/docs`, `/redoc` and `/openapi.json` are also open.)

### 3.4 What is missing

| Missing piece | Effect today |
|---|---|
| Endpoint to create users | The only way to add a user is running `python -m scripts.seed --username ... --password ...` by hand |
| Change password, forgot password, reset password | None exist. The frontend forms are stubs that only show a "not available yet" message |
| Sign-up | The frontend page is a stub. There is no backend endpoint |
| Roles | `User` only has `id`, `username`, `password_hash`, `is_active`, `created_at` |
| Real use of the current user | Every route has `_current_user` but never reads it, so any logged-in user can do anything |
| "Who did this" columns | No table has `created_by`. `LedgerEntry` only has `created_at` |
| Server-side logout | Sign-out only deletes tokens in the browser |
| Refresh token revocation | Refresh tokens are stateless, so a stolen one works until it expires (7 days) |
| Clearing the data cache on sign-out | User B on the same browser could briefly see User A's cached data |
| Role-based screens | The navigation is the same for everyone. "Role" in the frontend only means party roles (china_vendor etc.), not user roles |

Small extra things noticed:

- After login the app goes to `/settings`, not `/dashboard`.
- The "where you came from" page (`state.from`) is saved but never used.
- `is_active` comes back from `/auth/me` but nothing on the frontend reads it.

### 3.5 Two things not yet verified

The analysis did not confirm these, so check them before relying on them:

1. **Cargo ledger posting.** The cargo service has no direct call to post a ledger row. It may be handled elsewhere, or it may not post at all.
2. **Reset-password form.** It was probably a stub like the others, but the file was not read in full.

---

## 4. Which kind of multi-user do you want?

"Multi-user" can mean two very different things. Pick one before building.

### Option A: staff sharing one business (recommended)

Your father's business stays the one business. Extra people, like a bookkeeper or a second location, log in with their own accounts. Everyone sees the same stock, parties, orders and ledger. What differs is who can do what, and who did what.

This matches `PLAN.md`: "a bookkeeper or a second location is exactly the kind of future need described in this business."

### Option B: separate businesses (multi-tenant)

Each business has its own private data. Business 1 never sees Business 2's items, parties or sales. This is how you would turn the app into a product for other shops. It is a much bigger change (see section 6).

---

## 5. Plan for Option A (staff sharing one business)

### 5.1 Backend steps

**Step 1: Add a role to `User`.**
- New column `role` with values like `admin` and `staff`.
- Migration sets your existing user as `admin`.
- Follow the repo's migration rules: one migration for the feature, descriptive date-based filename, reviewed by eye.

**Step 2: Real authorization.**
- Add `require_admin` in `src/auth/dependencies.py`, built on `get_current_user`.
- Replace `_current_user` with a real `current_user` parameter where the user is needed.
- Decide which actions are admin-only (see section 5.3).

**Step 3: User management endpoints (admin only).**
- `POST /auth/users` create a user (hash the password the same way `scripts/seed.py` does)
- `GET /auth/users` list users
- `PATCH /auth/users/{id}` change role or details
- Deactivate a user (set `is_active = false`, do not delete)
- Admin reset of another user's password
- `POST /auth/change-password` for any logged-in user to change their own

All follow the usual shape: Pydantic `Create/Read/Update` schemas, a thin router, logic in `service.py`, and `response_model` set. Never return `password_hash`.

**Step 4: "Who did it" columns.**
- Add `created_by` (foreign key to `user.id`) to: `PurchaseOrder`, `SalesOrder`, `PaymentTransaction`, `Expense`, `StockMovement`, `LedgerEntry`.
- Fill it in the service layer from the current user, in the same transaction.
- Add it to the `Read` schemas, ideally with the username so the UI can show it.
- Existing rows can stay `NULL` (or point to the first admin) in the migration.

**Step 5: Tighten sessions.**
- Already done: every request checks the user exists and is active, so deactivating a user blocks their access within 30 minutes (when the access token expires) or immediately on the next call.
- Optional: add a `token_version` on `User` that is stored in the token and bumped on password change or deactivation, so old tokens stop working at once.
- Optional: shorter access token lifetime.

**Step 6: Housekeeping.**
- Turn off or protect `/docs` and `/openapi.json` in production.
- Update the seed script so it can create an admin with a role.

### 5.2 Frontend steps

1. **Auth data.** Make `/auth/me` return `role` and carry it through `authService.js`, the reducer and `useAuth()`. Add helpers like `isAdmin`.
2. **Clear the cache.** Call `queryClient.clear()` on sign-in and sign-out so one user never sees another's cached data.
3. **Users screen.** New `/users` route (admin only), following `CLAUDE.md`:
   - `pages/UsersPage.jsx`, `containers/UsersContainer.jsx`
   - `components/users/` with a `UserForm`
   - `services/userService.js`, `hooks/userHooks/` (queries and mutations)
   - `userKeys` in `utils/queryKeys.js`, `validations/userSchemas.js`
   - Can reuse `CrudTable` and `CrudDrawer` with a `UserCrudConfig`.
4. **Role-gated navigation.** Add a `roles` field to each entry in `NAV_LINKS` (`utils/constants.js`), filter them in `Sidebar.jsx` and `BottomNav.jsx`, and add a role-aware route guard next to `ProtectedRoute`.
5. **Hide actions staff cannot use.** Delete, edit, adjust or settings buttons should be hidden or disabled by role. The backend still enforces the rule, the UI just avoids confusing errors.
6. **Sign-up page.** Either remove the public sign-up page, or turn it into the admin-only "create user" form. Public self-signup is not recommended for a business app.
7. **Password pages.** Wire up a change-password form (listed in `CLAUDE.md` but not built). Forgot and reset password need email or an admin reset flow, so the simplest start is admin reset only.
8. **Show who did it.** Add a "Created by" field on purchase order, sales, payment, expense and stock adjustment screens, and optionally a filter by user.
9. **Small fixes.** Go back to the page the user came from after login, handle deactivated users, and show the role in the navbar user menu.

### 5.3 Decide: what should staff NOT be able to do?

You need to choose this. Suggested starting point:

| Action | Admin | Staff |
|---|---|---|
| Manage users | Yes | No |
| Change shop settings and exchange rates | Yes | No |
| Delete or deactivate parties, items and lookups | Yes | No |
| Edit or deactivate payment accounts | Yes | No |
| Stock adjustments and damage write-offs | Yes | Maybe |
| Create purchase orders, sales, payments, expenses | Yes | Yes |
| View dashboard, profit margins and reports | Yes | Maybe (margins can be sensitive) |

### 5.4 Suggested order of work

1. Backend: role column, `require_admin`, user endpoints, change-password. Test with curl or the API docs.
2. Backend: `created_by` columns and filling them in services.
3. Frontend: cache clearing, role in auth, `/users` screen, role-gated nav.
4. Frontend: "created by" display and password pages.
5. Security pass: secrets, `/docs`, token behaviour, deactivation test.

### 5.5 How to check it works

- Create a staff user, log in as them, and confirm admin-only screens and endpoints are blocked (UI hidden and API returning 403).
- Create a sale as staff and confirm `created_by` is saved and shown.
- Deactivate that user and confirm they can no longer use the app.
- Sign out as one user and sign in as another in the same browser, and confirm no old data appears.
- Check on phone, tablet and desktop widths, per `CLAUDE.md`.

---

## 6. If you choose Option B (separate businesses)

This is a large change. Every part of the data layer is touched.

- Add `tenant_id` to **every** table.
- Every query in every `src/*/service.py`, the generic `src/crud.py`, each `dependencies.py` "fetch by id" helper, the reporting queries and the ledger statements must filter by tenant. A missed filter means one business can read another's data.
- `User` gets a `tenant_id`, and the JWT carries it.
- The `Setting` table is one row (id 1) today. It would become one row per tenant.
- Unique rules that would break, because they are unique across the whole table today. Each would need to become unique per tenant, for example `(tenant_id, name)`:
  - `user.username`
  - `category.name`, `brand.name`
  - `item.sku`
  - `exchange_rate.rate_date`
  - `cargo_mode.name`, `cargo_cost_basis.name` and `.code`
  - `payment_method.name`
  - `expense_category.name`
- Not a problem: `Party.name` has no unique rule, and the one-to-one links like `cargo_allocation.purchase_order_line_id` stay valid.
- `scripts/seed.py` and the import scripts look rows up by bare name or code, so they need tenant awareness.
- Alternatives that reduce the query changes: one database per business, or PostgreSQL row-level security. The unique rules still need review either way.

Only choose this if you plan to give the app to other businesses.

---

## 7. Decisions needed from you

1. **Option A or B?** (A is recommended.)
2. **Roles:** is `admin` and `staff` enough, or do you want more (for example a read-only `viewer`)?
3. **Staff permissions:** use the table in 5.3, or change it.
4. **Who creates users:** admin only (recommended), or public self-sign-up?
5. **Forgot password:** admin reset only for now, or email-based reset later?

Once you answer these, the next step is a detailed implementation plan. No code will be changed until you approve it.
