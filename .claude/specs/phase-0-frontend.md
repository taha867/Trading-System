# Phase 0 Frontend — Spec

Source of truth: `PLAN.md` (§ Phase 0 — Foundation) for *what*, `CLAUDE.md` (§3) for *how*, and `.claude/specs/phase-0-backend.md` for the actual API surface this frontend talks to (verified against the implemented `backend/src/` code, not just the backend spec draft — see §1.1). Nothing here overrides any of the three; if a conflict appears, PLAN.md wins on data model, CLAUDE.md wins on code shape, and the backend spec/code wins on API contract.

**Done when** (verbatim from PLAN.md): you can log in, add today's RMB→PKR rate, and add/edit a payment method — all through the generic table+form, nothing hard-coded.

At the time of writing, `frontend/` is empty — this is a from-scratch build, not a retrofit.

---

## 1. Scope

Build, in this order (each step is independently usable/testable before moving to the next):

1. Project skeleton — Vite + React 19, `@/` alias, Tailwind v4, shadcn/ui init, ESLint.
2. `middleware/fetchClient.js` — the one HTTP client, including 401-refresh-and-retry.
3. Auth foundation — `contexts/authContext.jsx`, `reducers/authReducer.js`, `utils/tokenUtils.js`, `hooks/authHooks/` (queries + mutations), `services/authService.js`, `validations/authSchemas.js`.
4. Auth UI — `SignInPage`/`SignInForm` (functional), `SignUpPage`/`ForgotPasswordPage`/`ResetPasswordPage` (non-functional stubs, per §7 decision), `AuthLayout`.
5. Route protection — `components/common/ProtectedRoute.jsx`, `AuthRouteProtection.jsx`, `AuthFallback.jsx`, `AppInitializer.jsx`.
6. App shell — `App.jsx` routing (Public / AuthRoute / ProtectedRoute groups), `Navbar.jsx` (collapsible below `md`), `Footer.jsx`.
7. Generic CRUD engine (frontend half of PLAN.md Principle 3) — `components/common/CrudTable.jsx` + `CrudDrawer.jsx`, config-driven.
8. The two Phase 0 lookups wired to the engine — Exchange Rates and Payment Methods, both under one tabbed `SettingsPage` (per §7 decision).
9. Supporting domain slices for both lookups — `hooks/purchasingHooks/`, `services/purchasingService.js`, `validations/purchasingSchemas.js` for `ExchangeRate`; `hooks/paymentsHooks/`, `services/paymentsService.js`, `validations/paymentsSchemas.js` for `PaymentMethod`.
10. `utils/queryKeys.js`, `utils/constants.js`, `utils/queryParams.js` — shared plumbing the above depends on.

Out of scope for Phase 0 (deferred to later phases per PLAN.md roadmap, matching the backend spec's own exclusions): `parties/`, `catalog/`, `purchasing` beyond `ExchangeRate`, `cargo/`, `inventory/`, `sales/`, `payments` beyond `PaymentMethod`, `expenses/`, `reporting/`. Do not scaffold empty domain folders for these now.

### 1.1 Confirmed API surface (from running backend code, not just its spec)

| Method | Path | Auth | Request body | Response |
|---|---|---|---|---|
| POST | `/auth/login` | none | `{username, password}` | `{access_token, refresh_token, token_type}` |
| POST | `/auth/refresh` | none | `{refresh_token}` | `{access_token, refresh_token, token_type}` |
| GET | `/auth/me` | bearer | — | `{id, username, is_active}` |
| GET | `/purchasing/exchange-rates?page=&page_size=` | bearer | — | `{items: [{id, rate_date, rate, is_active}], total, page, page_size}` |
| POST | `/purchasing/exchange-rates` | bearer | `{rate_date, rate}` | `{id, rate_date, rate, is_active}` (201; 409 on duplicate `rate_date`) |
| PUT | `/purchasing/exchange-rates/{id}` | bearer | `{rate?}` | same shape |
| DELETE | `/purchasing/exchange-rates/{id}` | bearer | — | 204, soft delete |
| GET | `/payments/payment-methods?page=&page_size=` | bearer | — | `{items: [{id, name, is_active}], total, page, page_size}` |
| POST | `/payments/payment-methods` | bearer | `{name}` | `{id, name, is_active}` (201; 409 on duplicate `name`) |
| PUT | `/payments/payment-methods/{id}` | bearer | `{name?}` | same shape |
| DELETE | `/payments/payment-methods/{id}` | bearer | — | 204, soft delete |

Notes carried over from the backend implementation, not just its spec draft:

- No `/auth/register`, forgot-password, or reset-password endpoints exist. The corresponding frontend pages must not call a real service function.
- `PaginationParams` bounds are `page >= 1`, `1 <= page_size <= 100` — the frontend's pagination controls should not offer a page size outside that range (default `20`, matching the backend default).
- `rate` is `Numeric(10,4)`, transported as a JSON string by Pydantic/FastAPI for `Decimal` fields — the frontend must treat exchange-rate values as strings through the fetch/service layer and only parse for display formatting, never for the request body (send back what the form collected, not a re-serialized float).
- Every error body is `{"detail": "..."}` (from `AppException`'s handler) — `fetchClient.js`'s toast-on-error path reads `detail`, not a nested `errors` array.

---

## 2. Folder structure delivered by Phase 0

Per CLAUDE.md §3.2–3.3, only the pieces Phase 0 actually needs:

```
frontend/
├── index.html
├── vite.config.js              # @/ alias -> ./src, react-compiler babel plugin
├── jsconfig.json                # matches @/ alias
├── tailwind.config.js
├── postcss.config.js
├── components.json              # shadcn/ui: style new-york, aliases @/components, @/lib, @/hooks
├── eslint.config.js
├── .env                          # VITE_API_BASE_URL — gitignored
├── .env.example                  # committed placeholder
├── .gitignore
└── src/
    ├── main.jsx                 # createRoot, QueryClientProvider, AuthProvider, BrowserRouter
    ├── App.jsx                  # <Routes>: Public / AuthRoute / ProtectedRoute groups
    ├── index.css                # Tailwind entry + design tokens
    │
    ├── pages/
    │   ├── SettingsPage.jsx             # tabbed: Exchange Rates | Payment Methods
    │   └── AuthPages/
    │       ├── SignInPage.jsx           # functional
    │       ├── SignUpPage.jsx           # stub — see §7
    │       ├── ForgotPasswordPage.jsx   # stub
    │       └── ResetPasswordPage.jsx    # stub
    │
    ├── containers/
    │   └── SettingsContainer.jsx        # reads ?tab= query param, composes the two CrudTable configs
    │
    ├── components/
    │   ├── ui/                    # shadcn primitives: button, dialog, input, table, tabs, select, form, sonner/toast
    │   ├── custom/
    │   │   ├── FormField.jsx / FormSelect.jsx / index.js
    │   ├── common/
    │   │   ├── ProtectedRoute.jsx
    │   │   ├── AuthRouteProtection.jsx     # redirects an already-authed user away from /sign-in
    │   │   ├── AuthFallback.jsx            # Suspense fallback while auth state resolves on first load
    │   │   ├── AppInitializer.jsx          # reads the "am I logged in" promise via use()
    │   │   ├── CrudTable.jsx               # config-driven table + pagination + row actions
    │   │   ├── CrudDrawer.jsx              # config-driven add/edit drawer (react-hook-form + Yup inside)
    │   │   ├── PaginationControls.jsx
    │   │   ├── ConfirmDeleteDialog.jsx
    │   │   └── ToastNotification.jsx
    │   ├── auth/
    │   │   ├── AuthLayout.jsx
    │   │   ├── SignIn.jsx
    │   │   ├── SignUp.jsx / ForgotPassword.jsx / ResetPassword.jsx     # stub wrappers
    │   │   └── form/
    │   │       ├── SignInForm.jsx           # functional
    │   │       └── SignUpForm.jsx / ForgotPasswordForm.jsx / ResetPasswordForm.jsx   # render-only stubs
    │   ├── purchasing/
    │   │   └── ExchangeRateCrudConfig.js    # column defs + Yup schema ref, consumed by CrudTable/CrudDrawer
    │   ├── payments/
    │   │   └── PaymentMethodCrudConfig.js
    │   ├── Navbar.jsx
    │   └── Footer.jsx
    │
    ├── hooks/
    │   ├── authHooks/
    │   │   ├── authHooks.js        # useAuth() context accessor
    │   │   └── authMutations.js    # useSignIn, useSignOut, useRefreshToken
    │   ├── purchasingHooks/
    │   │   ├── purchasingQueries.js    # useExchangeRates(params)
    │   │   └── purchasingMutations.js  # useCreateExchangeRate, useUpdateExchangeRate, useDeleteExchangeRate
    │   └── paymentsHooks/
    │       ├── paymentsQueries.js      # usePaymentMethods(params)
    │       └── paymentsMutations.js    # useCreatePaymentMethod, useUpdatePaymentMethod, useDeletePaymentMethod
    │
    ├── services/
    │   ├── authService.js
    │   ├── purchasingService.js
    │   └── paymentsService.js
    │
    ├── middleware/
    │   └── fetchClient.js
    │
    ├── contexts/
    │   └── authContext.jsx
    │
    ├── reducers/
    │   └── authReducer.js
    │
    ├── validations/
    │   ├── authSchemas.js          # signIn only, functionally; signUp/forgot/reset schemas exist but forms never submit them
    │   ├── purchasingSchemas.js    # exchangeRateCreate/Update
    │   ├── paymentsSchemas.js      # paymentMethodCreate/Update
    │   └── commonSchemas.js
    │
    ├── utils/
    │   ├── constants.js            # HTTP_STATUS, TOAST_MESSAGES — no domain enums yet (PARTY_ROLE etc. start Phase 1+)
    │   ├── queryKeys.js            # authKeys, exchangeRateKeys, paymentMethodKeys
    │   ├── queryParams.js          # buildQueryString({page, page_size})
    │   └── tokenUtils.js           # getToken/getRefreshToken/storeToken/removeTokens/hasValidRefreshToken
    │
    └── lib/
        └── utils.js                # shadcn's cn()
```

Deliberately absent from this tree, even though CLAUDE.md's full target structure names them: `currencyUtils.js` (RMB→PKR *preview* math is a Phase 1 concern — a purchase-order line, not a bare exchange-rate row), `CurrencyAmount.jsx`, `fifoPreviewUtils.js`, `formSubmitWithToast.js`, and every domain folder under `components/`/`hooks/`/`services/`/`validations/` besides `auth`, `purchasing`, `payments`. Growing into the rest of CLAUDE.md's tree happens phase by phase, per that file's own framing.

---

## 3. Decisions (confirmed with user)

1. **Where Phase 0's lookup CRUD screens live** — one `/settings` route, tabbed (`SettingsPage` → `SettingsContainer` → a "Exchange Rates" tab and a "Payment Methods" tab, each rendering `CrudTable` with its own config). Chosen over separate top-level nav items so later lookups (`Category`, `CargoMode`, `CargoCostBasis`, `ExpenseCategory`, per PLAN.md Principle 3) add a tab, not a nav item — keeps `Navbar.jsx` from growing one entry per lookup type across phases.
2. **Auth stub pages** — `SignUpPage`, `ForgotPasswordPage`, `ResetPasswordPage` are built now as non-functional stubs: real routes, real layout/form UI, but their submit handlers do not call a service (no backend endpoint exists — §1.1). Matches CLAUDE.md §3.3's own note that `SignUpPage` is "kept even for a single user today." A submit attempt should surface a "not available yet" toast/message rather than silently doing nothing or throwing.

No other open questions — the rest of this spec follows directly from CLAUDE.md §3 and the confirmed backend contract.

---

## 4. `middleware/fetchClient.js`

The one thing allowed to call `fetch` (CLAUDE.md §3.4 point 5). Phase 0 is where this gets built for real, since every later domain's `services/*.js` depends on it existing correctly:

- Base URL from `import.meta.env.VITE_API_BASE_URL`.
- Injects `Authorization: Bearer <access_token>` from `utils/tokenUtils.js` on every request except `/auth/login` and `/auth/refresh`.
- On a `401` (any request except `/auth/refresh` itself): pause the failing call, call `POST /auth/refresh` with the stored refresh token, and on success retry the original request once with the new access token. Concurrent 401s while a refresh is already in flight must share one refresh call (single-flight lock — a `Promise` held in module scope, not a new refresh request per concurrent 401). If the refresh itself fails (expired/invalid refresh token), clear tokens via `removeTokens()` and redirect to `/sign-in`.
- Timeout via `AbortSignal.timeout(...)` (or an `AbortController` + `setTimeout` if broader browser support is needed) — a hung request must not spin forever.
- Toasts: a network/5xx/4xx failure shows `react-hot-toast` with the backend's `detail` string (§1.1); a successful mutation's toast is left to the calling hook/service to decide (not every successful `GET` should toast).
- Normalized return shape: `{data, status, ok, headers}` — services unwrap `.data`, never see a raw `Response`.

---

## 5. Auth (`contexts/authContext.jsx`, `hooks/authHooks/`, `services/authService.js`)

### 5.1 `services/authService.js`

Pure functions, no React, mirroring §1.1 exactly:

```javascript
export async function signIn({ username, password }) {
  const { data } = await fetchClient.post('/auth/login', { username, password });
  return data; // { access_token, refresh_token, token_type }
}

export async function refreshToken(refresh_token) {
  const { data } = await fetchClient.post('/auth/refresh', { refresh_token });
  return data;
}

export async function fetchCurrentUser() {
  const { data } = await fetchClient.get('/auth/me');
  return data; // { id, username, is_active }
}
```

### 5.2 `contexts/authContext.jsx` + `reducers/authReducer.js`

Holds `{ user, status: 'idle' | 'authenticating' | 'authenticated' | 'unauthenticated' }`. On mount, `AppInitializer.jsx` (§2) reads a promise that: checks `tokenUtils.hasValidRefreshToken()`, and if present, calls `fetchCurrentUser()` to hydrate `user` before rendering protected routes — this is the `use()`-driven skeleton CLAUDE.md §3.6 describes, not a `useEffect`+`useState` combo.

### 5.3 `hooks/authHooks/authMutations.js`

- `useSignIn()` — calls `authService.signIn`, on success stores both tokens via `tokenUtils.storeToken`, dispatches `authenticated` with the user fetched from `/auth/me`, and navigates to the post-login landing route (there is no `DashboardPage` yet in Phase 0 — land on `/settings`).
- `useSignOut()` — clears tokens, dispatches `unauthenticated`, navigates to `/sign-in`. No backend call — Phase 0 has no logout/token-revocation endpoint; this is a client-side-only sign-out.
- `useRefreshToken()` exists for symmetry with CLAUDE.md's naming convention, but in practice `fetchClient.js`'s own refresh-and-retry logic (§4) is what actually triggers a refresh — this hook is for any component that needs to trigger one explicitly (none do, in Phase 0).

### 5.4 `validations/authSchemas.js`

```javascript
import { object, string } from 'yup';

export const signInSchema = object({
  username: string().required(),
  password: string().required(),
});
```

`signUpSchema`/`forgotPasswordSchema`/`resetPasswordSchema` are written now (mirroring the stub forms' fields — username/email, password, password+confirm) so the stub forms have real inline validation even though submission goes nowhere, per §3's decision — a stub shouldn't feel broken, just unavailable past the point of clicking submit.

---

## 6. Route protection & app shell

### 6.1 `App.jsx`

Three route groups, per CLAUDE.md §3.3's page-file comment:

```jsx
<Routes>
  {/* Public/AuthRoute — redirect to /settings if already authenticated */}
  <Route element={<AuthRouteProtection />}>
    <Route path="/sign-in" element={<SignInPage />} />
    <Route path="/sign-up" element={<SignUpPage />} />
    <Route path="/forgot-password" element={<ForgotPasswordPage />} />
    <Route path="/reset-password" element={<ResetPasswordPage />} />
  </Route>

  {/* Protected — redirect to /sign-in if not authenticated */}
  <Route element={<ProtectedRoute />}>
    <Route path="/settings" element={<SettingsPage />} />
    <Route path="/" element={<Navigate to="/settings" replace />} />
  </Route>

  <Route path="*" element={<Navigate to="/settings" replace />} />
</Routes>
```

There is no public landing page in Phase 0 (`Home.jsx` exists in CLAUDE.md's target tree but nothing in PLAN.md's "done when" needs it yet) — root `/` redirects straight into the one protected screen that exists.

### 6.2 `ProtectedRoute.jsx` / `AuthRouteProtection.jsx`

Both read `useAuth()` from `authContext`. `ProtectedRoute` renders `<Outlet />` when `status === 'authenticated'`, redirects to `/sign-in` (preserving the attempted path for a post-login bounce-back) otherwise. `AuthRouteProtection` is the mirror image. Both must wait for `status !== 'idle'` (i.e. `AppInitializer`'s hydration promise resolved) before deciding — redirecting to `/sign-in` on first paint just because the token hasn't been checked yet would bounce a genuinely logged-in user.

### 6.3 `Navbar.jsx`

Per CLAUDE.md §3.7: a mobile menu (hamburger + slide-down/drawer) below `md`, full horizontal nav at `md` and above. Phase 0's link list is short — just "Settings" and a sign-out action — but the collapsing behavior itself must be built now, not deferred, since CLAUDE.md treats responsiveness as non-negotiable from the first screen, not something retrofitted once there are nine domains to fit.

---

## 7. Generic CRUD engine — `CrudTable.jsx` + `CrudDrawer.jsx`

Frontend half of PLAN.md Principle 3: "one `<CrudTable schema=... />` component... New lookup type = new config object, not a new page." This is the Phase 0 centerpiece on the frontend, same as `src/crud.py` is on the backend.

### 7.1 Config shape

Each lookup gets one config object (`ExchangeRateCrudConfig.js`, `PaymentMethodCrudConfig.js`) with the same shape so `CrudTable`/`CrudDrawer` never branch on which lookup they're rendering:

```javascript
// components/purchasing/ExchangeRateCrudConfig.js
export const exchangeRateCrudConfig = {
  queryKey: exchangeRateKeys,               // from utils/queryKeys.js
  useList: useExchangeRates,                 // hooks/purchasingHooks/purchasingQueries.js
  useCreate: useCreateExchangeRate,
  useUpdate: useUpdateExchangeRate,
  useDelete: useDeleteExchangeRate,
  columns: [
    { key: 'rate_date', label: 'Date', type: 'date' },
    { key: 'rate', label: 'RMB → PKR', type: 'decimal' },
  ],
  createSchema: exchangeRateCreateSchema,    // validations/purchasingSchemas.js
  updateSchema: exchangeRateUpdateSchema,
  fields: [
    { name: 'rate_date', label: 'Date', component: 'date', editableOnUpdate: false },  // rate_date is unique+immutable per row once created
    { name: 'rate', label: 'RMB → PKR rate', component: 'number', step: '0.0001' },
  ],
};
```

```javascript
// components/payments/PaymentMethodCrudConfig.js
export const paymentMethodCrudConfig = {
  queryKey: paymentMethodKeys,
  useList: usePaymentMethods,
  useCreate: useCreatePaymentMethod,
  useUpdate: useUpdatePaymentMethod,
  useDelete: useDeletePaymentMethod,
  columns: [{ key: 'name', label: 'Name', type: 'text' }],
  createSchema: paymentMethodCreateSchema,
  updateSchema: paymentMethodUpdateSchema,
  fields: [{ name: 'name', label: 'Name', component: 'text' }],
};
```

`rate_date` is marked `editableOnUpdate: false` because the backend's `ExchangeRateUpdate` schema (§1.1) doesn't even accept `rate_date` — only `rate` — so `CrudDrawer`'s edit mode must render it read-only rather than let a user edit a field the `PUT` call would silently drop.

### 7.2 `CrudTable.jsx`

Given a config: fetches via `config.useList({ page, page_size })`, renders `columns` against `items`, wraps the table in `overflow-x-auto` (CLAUDE.md §3.7 — even a 2-column table gets this treatment on principle, since a future lookup config might add columns), renders `PaginationControls` off `total`/`page`/`page_size`, and an "Add" button that opens `CrudDrawer` in create mode. Each row gets Edit (opens `CrudDrawer` in update mode) and Delete (opens `ConfirmDeleteDialog`, then calls `config.useDelete`) actions.

### 7.3 `CrudDrawer.jsx`

A shadcn `Sheet`/`Dialog` wrapping a `react-hook-form` instance resolved against `config.createSchema` (create mode) or `config.updateSchema` (update mode), rendering `config.fields` through `FormField`/`FormSelect` per their `component` type. On submit, calls `config.useCreate`/`config.useUpdate`; both mutations invalidate `config.queryKey.lists()` on success (CLAUDE.md §3.4 point 3) so the table behind the drawer refetches without a manual `refetch()` call anywhere in this component.

### 7.4 Mutation invalidation (`utils/queryKeys.js`)

```javascript
export const exchangeRateKeys = {
  all: ['exchangeRates'],
  lists: () => [...exchangeRateKeys.all, 'list'],
  list: (params) => [...exchangeRateKeys.lists(), params],
};

export const paymentMethodKeys = {
  all: ['paymentMethods'],
  lists: () => [...paymentMethodKeys.all, 'list'],
  list: (params) => [...paymentMethodKeys.lists(), params],
};
```

Both `purchasingMutations.js` and `paymentsMutations.js` invalidate through these factories exclusively — never a hand-built `['exchangeRates']` array inline in a mutation, per CLAUDE.md §3.4 point 3.

---

## 8. Forms & validation detail

### 8.1 `validations/purchasingSchemas.js`

```javascript
import { object, string, number } from 'yup';

export const exchangeRateCreateSchema = object({
  rate_date: string().required('Date is required'),
  rate: number().typeError('Rate must be a number').positive().required(),
});

export const exchangeRateUpdateSchema = exchangeRateCreateSchema
  .pick(['rate'])
  .partial();
```

Mirrors the backend's actual constraint (§1.1: `ExchangeRateUpdate` only accepts `rate`) via `.pick()` rather than `.partial()` alone — a plain `.partial()` on the full create schema would make `rate_date` an *optional-but-still-accepted* field on update, which doesn't match the backend contract at all (`PUT` silently ignores a `rate_date` in the body, since `ExchangeRateUpdate` doesn't declare it — CLAUDE.md §3.5's "Yup is the courtesy layer" principle means the courtesy layer should reflect that a submitted `rate_date` on update is pointless, not merely optional).

### 8.2 `validations/paymentsSchemas.js`

```javascript
import { object, string } from 'yup';

export const paymentMethodCreateSchema = object({
  name: string().required().max(64),
});

export const paymentMethodUpdateSchema = paymentMethodCreateSchema.partial();
```

`.partial()` alone is correct here since `PaymentMethodUpdate` (§1.1) genuinely mirrors `PaymentMethodCreate` with every field optional — no `.pick()` needed, unlike §8.1.

### 8.3 Responsive check (CLAUDE.md §3.7)

Both `CrudDrawer` instances (exchange rate: 2 fields; payment method: 1 field) stack to a single column below `md` by default since neither ever reaches a `grid md:grid-cols-2` layout to begin with — verify at ~375px anyway per CLAUDE.md's three-width rule, since the drawer/sheet width itself (not just the field grid) is a common mobile-overflow spot shadcn's `Sheet` doesn't guarantee out of the box.

---

## 9. Testing checklist (manual, matches PLAN.md's "done when")

1. `npm run dev` serves the app at `http://localhost:5173` (matching backend's seeded `CORS_ORIGINS`).
2. Visiting `/` while logged out redirects to `/sign-in`; visiting `/sign-in` while logged in redirects to `/settings`.
3. Signing in with the seeded user's credentials succeeds, lands on `/settings`, and a subsequent page refresh stays logged in (token persisted, `AppInitializer` rehydrates).
4. Signing in with a wrong password shows a toast with the backend's generic invalid-credentials message, not a raw network error.
5. On the "Exchange Rates" tab: adding today's date + a rate succeeds, appears in the table without a manual refresh; re-adding the same date surfaces the backend's 409 as an inline or toast error, not a silent failure.
6. On the "Payment Methods" tab: adding a new method succeeds and appears in the table; editing its name updates in place; deleting it removes it from the table (soft delete — the row still exists server-side per the backend checklist, but this frontend has no "show inactive" toggle in Phase 0 to verify that visually).
7. Manually expire/clear the access token in devtools storage while leaving the refresh token valid, then trigger any list fetch — the request should transparently refresh and succeed without the user noticing (one visible network 401 followed by a successful retry, no redirect to `/sign-in`).
8. Clear both tokens and trigger a fetch — the app redirects to `/sign-in` instead of hanging or looping.
9. Resize to ~375px, ~768px, ~1280px on `/settings`: `Navbar` collapses correctly below `md`, both `CrudTable`s stay within the viewport width (scrolling inside their own container if needed, never widening the page body), and the add/edit drawer is usable at the narrowest width.
10. Visit `/sign-up`, `/forgot-password`, `/reset-password` directly: each renders a real form with working inline Yup validation, and submitting shows a "not available yet"-style message rather than a silent no-op or a thrown error.
