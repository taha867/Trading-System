# Phase 8 Frontend — Spec

Governed by `PLAN.md` (what) and `CLAUDE.md` (how the code is shaped) and `.claude/skills/frontend-design-system/SKILL.md` (how it should look). This document plans the frontend build for Phase 8 — Balance statement, fast/slow-mover chart, reorder priority, margin report — against the backend already fully implemented and reviewed in `.claude/specs/phase-8-backend.md`, confirmed live on disk at `backend/src/reporting/{constants,schemas,service,router}.py` and wired into `backend/src/main.py`. Every citation to `frontend/src` below was verified by reading the actual current code, not by assuming it matches an earlier phase's spec. Library-specific claims (TanStack Query v5's callback removal, the `enabled: false` lazy-query pattern, shadcn's `chart` component) were checked against current docs via Context7, not recalled from training data — cited inline where they matter.

**Done when** (from `PLAN.md`): *the dashboards this was all for* — you can open one screen and know where the business stands, and one chart to know what to reorder from China next.

---

## 1. Scope & confirmed API surface

`find frontend/src -iname '*report*'` returns nothing, and grepping the whole tree for `window_days`/`Dashboard`/`chart` (case-insensitive) turns up zero application code — only shadcn's pre-wired `--chart-1`..`--chart-5` CSS tokens in `frontend/src/index.css:29-33,82-86,119-123` (theme scaffolding from Phase 0, not evidence any chart has ever been built). This phase's frontend is **100% new work**, the same starting point every other domain's frontend spec had on day one.

`CLAUDE.md` §3.3 already names most of the target files: `pages/DashboardPage.jsx` ("Phase 8 landing: balance statement + sell-through chart"), `containers/DashboardContainer.jsx`, `components/reporting/BalanceStatement.jsx` / `SellThroughChart.jsx` / `ReorderPriorityTable.jsx`, `hooks/reportingHooks/reportingQueries.js` ("read-only, this domain has no mutations"). §3.3's `validations/` tree confirms the omission is deliberate too — it lists a schema file for every other domain (`authSchemas.js` … `expensesSchemas.js`, `commonSchemas.js`) but no `reportingSchemas.js` at all, matching the fact that Phase 8 has no create/update form anywhere (§2 decision 6). This spec follows all of that exactly, and adds one file `CLAUDE.md`'s illustrative tree doesn't name — `MarginReportTable.jsx` (§2 decision 4) — the same kind of considered addition Phase 7's frontend spec made for its `*CrudConfig.js` files (`phase-7-frontend.md` §1: "the same way `ExchangeRateCrudConfig.js`/… all exist today without being named in CLAUDE.md's illustrative tree — an established, not a new, omission").

### 1.1 Confirmed API surface (from `phase-8-backend.md`, cross-checked against `backend/src/reporting/schemas.py` and `router.py` live on disk)

| Method | Path | Query params | Response | Side effect |
|---|---|---|---|---|
| GET | `/reporting/balance-statement` | none | `BalanceStatementRead` | none — pure read |
| GET | `/reporting/sell-through` | `?window_days=` (1–730, default 30) | `SellThroughRead` | none — pure read |
| GET | `/reporting/reorder-priority` | `?window_days=` (1–730, default 30) | `ReorderPriorityRead` | **writes `Model.priority`, every call** (`phase-8-backend.md` §2.5) |
| GET | `/reporting/margin` | `?window_days=` (1–730, default 30) | `MarginReportRead` | none — pure read |

Every route requires auth (`Depends(get_current_user)`, `router.py:6-49`) — nothing new there, matches every other domain.

**Schema shapes** (`backend/src/reporting/schemas.py:1-75`, verified directly):
- `BalanceStatementRead`: `as_of: date`, `cash_accounts: PaymentAccountBalanceRead[]` (reused verbatim from `payments/schemas.py:48-52` — `{id, label, payment_method_id, balance}`), `total_cash_pkr`, `party_balances: PartyBalanceRead[]` (`{party_id, name, roles, balance_pkr}` — positive = receivable, negative = payable), `total_receivable_pkr`, `total_payable_pkr`, `inventory_value_pkr`, `net_position_pkr`.
- `SellThroughRead`: `window_days`, `start_date`, `end_date`, `entries: SellThroughEntryRead[]` (`{model_id, model_name, qty_sold, rank}` — rank 1 = fastest mover, **every active `Model` appears**, zero-sale ones at `qty_sold=0`, ranked last).
- `ReorderPriorityRead`: identical shape to `SellThroughRead` except each entry's `rank` field is renamed `priority`, and the values it returns are exactly the values just written to `Model.priority` server-side.
- `MarginReportRead`: `window_days`, `start_date`, `end_date`, `entries: MarginReportEntryRead[]` (`{item_id, sku, model_id, model_name, qty_sold, revenue_pkr, cost_pkr, margin_pkr, margin_pct}` — **only items with at least one sale in the window appear**, not a zero-row per item), `total_revenue_pkr`, `total_cost_pkr`, `total_margin_pkr`.

No pagination envelope (`{items, total, page, page_size}`) on any of these four — every payload is one bounded object, confirmed by `phase-8-backend.md` §3.2's own note that `pagination.py` is untouched this phase. This is the same shape `GET /payments/payment-accounts/balances` already established on the frontend (§1.2 below) — not a new pattern to invent.

### 1.2 Existing precedent this spec builds directly on

- **`paymentAccountKeys.balances()`** (`frontend/src/utils/queryKeys.js:89-94`) + **`usePaymentAccountBalances()`** (`frontend/src/hooks/paymentsHooks/paymentsQueries.js:24-29`) + **`getPaymentAccountBalances()`** (`frontend/src/services/paymentsService.js:44-47`, explicit comment: *"Returns a plain array, not `{items,total,...}` … don't wrap or paginate this"*) — the exact bare-key/no-params/non-paginated shape all four reporting hooks follow.
- **`PartyStatement.jsx`'s `balanceLabel()` helper** (`frontend/src/components/parties/PartyStatement.jsx:9-14`) and its signed-balance rendering (`:29-36`: a `Badge` colored by sign + `CurrencyAmount value={Math.abs(...)}`) — the exact pattern `BalanceStatement.jsx`'s party section reuses for `PartyBalanceRead.balance_pkr`, which has the identical sign convention (`phase-8-backend.md` §2.2 explicitly matches `create_party`'s existing convention).
- **`PartyCrudConfig.jsx:22-24`**'s `<Link to={`/parties/${row.id}`} className="font-medium text-primary hover:underline">` — the precedent for making a party name in `BalanceStatement.jsx`'s table clickable through to its existing statement page, rather than a dead label.
- **`StockLotTable.jsx:75-159`** — the only precedent in this codebase for a `Card` housing a filter control in `CardAction` next to a data table with full loading/error/empty states; every reporting table below follows this shape.
- **`ModelCrudConfig.js:18,26-30`** — `Model.priority` is **already** a visible column and a manually-editable field in Catalog's `CrudTable`-driven Model list (comment at `:27`: `"Priority (used for reorder ranking from Phase 8)"`) — this phase is that field's first real, automated writer, and §8 below covers the resulting cross-domain interaction explicitly.
- **`App.jsx:57,60`** — `/` and `*` both currently redirect to `/purchase-orders`; this is the one existing routing decision Phase 8 changes (§7.1).

---

## 2. Decisions

1. **`/dashboard` becomes the new landing page** — `CLAUDE.md` §3.3 names `DashboardPage.jsx` first in its `pages/` tree with the annotation "Phase 8 landing," and `PLAN.md`'s own Phase 8 done-when line ("the dashboards this was all for") reads as *the* entry point, not one more item bolted onto an existing nav. Both `App.jsx:57`'s `/` redirect and `:60`'s catch-all `*` redirect move from `/purchase-orders` to `/dashboard` (§7.1); `Navbar.jsx`'s `NAV_LINKS` gets a new **first** entry, `{ to: '/dashboard', label: 'Dashboard' }` (§7.2) — first because it's the landing page, not because of any existing ordering convention (the current nine entries have no other ordering rule to preserve here).

2. **The write-on-`GET` endpoint (`/reporting/reorder-priority`) is called from a *lazy* `useQuery` (`enabled: false`), triggered only by an explicit "Recalculate" button press via the `refetch()` it returns — never on mount, never on window refocus.** `phase-8-backend.md` §2.5/§8 explicitly hands this decision to the frontend spec, flagging that a default-configured `useQuery` would silently re-write `Model.priority` on every background window-focus refetch. Two library facts confirmed via Context7 against the installed `@tanstack/react-query@^5.101.4` (docs checked at `/tanstack/query/v5.90.3`) shape the implementation:
   - `enabled: false` prevents automatic fetch-on-mount *and* background refetch, but the query's own `refetch()` still works to fetch on demand — the documented "manually triggered query" pattern, not a workaround.
   - `refetchOnWindowFocus: false` is set anyway, belt-and-suspenders, in case a future change ever flips `enabled` back on inadvertently.
   
   This resolves the tension `CLAUDE.md` §3.2 creates on its own: `reportingHooks/` is declared query-only, no mutations file — so this can't be a `useMutation` even though it behaves like one. A lazy `useQuery` whose `refetch` is exposed to a button's `onClick` satisfies both constraints at once: it's textually a query (satisfying `CLAUDE.md`), and it never fires without a deliberate user action (satisfying the backend spec's safety concern).

3. **`ReorderPriorityTable.jsx` renders from `/reporting/sell-through`'s data (via `useSellThrough`), not from the write-triggering `/reporting/reorder-priority` query.** The two endpoints compute the *identical* ranking (`phase-8-backend.md` §4.3's shared `_rank_models_by_sell_through` helper) — `SellThroughEntryRead.rank` and `ReorderPriorityEntryRead.priority` are the same number for the same `window_days`, one endpoint just also persists it. So the table the user actually looks at every time they open the dashboard is always the side-effect-free read; the lazy write-triggering query (decision 2) exists purely to *commit* that ranking to `Model.priority` when the user asks, and its own returned data is never rendered directly — only used to confirm the write succeeded (§5.2, §6.3).

4. **`MarginReportTable.jsx` is added under `components/reporting/`, even though `CLAUDE.md` §3.3's illustrative `reporting/` tree names only `BalanceStatement.jsx`/`SellThroughChart.jsx`/`ReorderPriorityTable.jsx`.** `phase-8-backend.md` §2.6 flagged this exact gap already: *"this endpoint's exact frontend consumer is left to the Phase 8 frontend spec."* Leaving `GET /reporting/margin` with zero UI consumer would mean a fully-built, reviewed backend endpoint nobody can reach — `PLAN.md`'s Phase 8 line explicitly lists "Margin report" as one of the four things this phase builds. Precedent for CLAUDE.md's tree being illustrative rather than exhaustive already exists (§1 above, `*CrudConfig.js` files, `phase-7-frontend.md` §1) — adding one clearly-scoped file here is the same kind of considered gap-fill, not a deviation from the plan.

5. **Every reporting screen gets its own independent `window_days` selector; there is no single dashboard-wide window control.** The backend itself treats `window_days` as a genuinely per-endpoint parameter — `phase-8-backend.md` §2.2 makes the same point about the balance statement's three sections ("there is no single 'the balance statement' SQL statement"). A user reasonably wants "this week's hot sellers" (7-day sell-through) sitting next to "this quarter's margin" (90-day margin) on the same screen — forcing one shared window would serve neither well. Each of `SellThroughChart`, `ReorderPriorityTable`, `MarginReportTable` keeps its own local `windowDays` state (default `30`, matching `backend/src/reporting/constants.py`'s `DEFAULT_WINDOW_DAYS`), so the three sections' fetches are fully independent.

6. **The `window_days` selector is a fixed-preset `FormSelect`, not a free-numeric-input field, and needs no Yup schema.** `validations/commonSchemas.js` (6 lines, only `usernameField`/`passwordField`) confirms there's no existing date-range/window validator to reuse, and `CLAUDE.md` §3.5's Yup convention is framed entirely around react-hook-form submissions — there is no form here (§1, §4.6's Settings-tab precedent doesn't apply either, since these screens aren't CRUD). A new `WINDOW_DAYS_OPTIONS` constant (`{7, 30, 90, 180}` days, following the exact `OBJECT`/`_OPTIONS` pairing every other entry in `utils/constants.js` uses, e.g. `PARTY_ROLE`/`PARTY_ROLE_OPTIONS`) backs a plain controlled `FormSelect`, local `useState`, no `react-hook-form` involved at all — reporting has nothing to submit.

7. **A new charting dependency is required — `recharts`, added via `npx shadcn@latest add chart`, not hand-picked.** Confirmed via `frontend/package.json:12-31`: no `recharts`/`chart.js`/`victory`/any `d3*` package exists today. Confirmed via Context7 against shadcn's current docs: `npx shadcn@latest add chart` is the documented install path, and it pulls in `recharts` as a dependency automatically alongside a `components/ui/chart.jsx` wrapper (`ChartContainer`, `ChartTooltip`, `ChartTooltipContent`, `ChartConfig`) that reads its series colors from CSS variables named `--color-<seriesKey>`, resolved from a `chartConfig` object passed to `ChartContainer`. This is *why* `index.css:29-33,82-86,119-123`'s `--chart-1`..`--chart-5` tokens already exist — Phase 0's theme scaffolding anticipated this exact component, unused until now. Running the CLI (rather than `npm install recharts` by hand) is the correct move because it also drops in the already-themed wrapper component, matching how every other shadcn primitive in this repo was added (`CLAUDE.md` §3.1: "If a new primitive is needed, install it via `npx shadcn@latest add <name>`"). The CLI's generated file ships a `"use client"` pragma at the top (a Next.js React-Server-Components directive) — harmless but meaningless under Vite; strip it, the same way `frontend-design-system/SKILL.md` already instructs stripping every new shadcn file's unused `import * as React from "react"`.

8. **`SellThroughChart.jsx` charts only the top 10 fastest movers, sorted descending by `qty_sold`** — not all active `Model`s. `SellThroughRead.entries` includes *every* active model (`phase-8-backend.md` §2.4, zero-sale ones included and ranked last) — rendering all of them as bars would be unreadable on a phone screen and mostly empty bars past the first handful. The *full* ranked list (fast **and** slow movers, per `PLAN.md`'s "fast/slow-mover chart" wording) is still fully visible immediately below in `ReorderPriorityTable` (decision 3) — nothing is hidden from the page, just from this one chart.

9. **`BalanceStatement.jsx` renders `data.cash_accounts` directly from its own endpoint's payload — it does not additionally call `usePaymentAccountBalances()`.** `phase-8-backend.md` §4.2 confirms `get_balance_statement` calls `payments_service.get_account_balances(db)` itself and returns the result verbatim as `cash_accounts` — the data is already identical, so a second frontend call would be a redundant round-trip fetching the same rows through a second code path. (This does mean `BalanceStatement.jsx`'s cash-accounts figures can be one query-cache generation "behind" `/payments`' own balances list if a payment posts between the two screens being open — an accepted staleness window, not different from any other two independently-cached reads of the same server truth elsewhere in this app.)

10. **Two-control `CardHeader`/`CardAction` combinations (a window-selector *and* a button, in `ReorderPriorityTable.jsx`) need an explicit mobile-stacking wrapper — this is new ground, not copied precedent.** `components/ui/card.jsx:63-76`'s `CardAction` is pinned to a fixed grid cell (`col-start-2 row-span-2 row-start-1 self-start justify-self-end`) with no responsive stacking of its own; every existing usage (`CrudTable.jsx`'s single "Add" button, `StockLotTable.jsx`'s single checkbox label) only ever puts **one** control there, so this fixed-width cell has never had two side-by-side controls fight for space on a narrow screen before. `ReorderPriorityTable.jsx`'s `CardAction` wraps its `FormSelect` + `Button` in `flex flex-col items-stretch gap-2 sm:flex-row sm:items-center` (§5.3) so they stack vertically inside their own column below `sm` rather than squeezing horizontally — a self-contained fix inside the new component, no change to the shared `Card` primitive.

---

## 3. Shared utility changes

### 3.1 `utils/queryKeys.js` additions

```js
// Every reporting endpoint is a single bounded object/array, never a paginated
// list (§1.1) — no domain here ever needs .lists()/.list(params)/.detail(id).
// Shaped after paymentAccountKeys.balances() (queryKeys.js:89-94), the existing
// precedent for a bare, params-varying, non-list key.
export const reportingKeys = {
  all: ['reporting'],
  balanceStatement: () => [...reportingKeys.all, 'balance-statement'],
  sellThrough: (windowDays) => [...reportingKeys.all, 'sell-through', windowDays],
  reorderPriority: (windowDays) => [...reportingKeys.all, 'reorder-priority', windowDays],
  margin: (windowDays) => [...reportingKeys.all, 'margin', windowDays],
};
```
Appended after `expenseKeys` (`queryKeys.js:114-118`, the current last entry).

### 3.2 `utils/constants.js` additions

```js
export const WINDOW_DAYS_OPTIONS = [
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
  { value: '180', label: 'Last 180 days' },
];

// Mirrors backend/src/reporting/constants.py's DEFAULT_WINDOW_DAYS exactly —
// keep the two in sync if that value ever changes.
export const DEFAULT_WINDOW_DAYS = 30;
```
Appended after `EXPENSE_STATUS_OPTIONS` (`constants.js:101-104`, current end of file). No `MIN_WINDOW_DAYS`/`MAX_WINDOW_DAYS` mirrored on the frontend — the preset list never lets a user construct an out-of-bounds value, so there's nothing client-side to clamp against (§2 decision 6).

---

## 4. Data access — `services/reportingService.js`, `hooks/reportingHooks/reportingQueries.js`

### 4.1 `services/reportingService.js` (new)

```js
import { fetchClient } from '@/middleware/fetchClient';

// No buildQueryString reuse (utils/queryParams.js:6-26) — that helper always
// force-injects page/page_size into the query string (it's built for the
// paginated list endpoints every other domain has), and every endpoint here
// takes at most one non-paginated `window_days` param. A plain template
// literal is clearer than fighting a pagination-shaped helper into this shape.

export async function getBalanceStatement() {
  const { data } = await fetchClient.get('/reporting/balance-statement');
  return data; // BalanceStatementRead — no params, always "as of now"
}

export async function getSellThrough(windowDays) {
  const { data } = await fetchClient.get(`/reporting/sell-through?window_days=${windowDays}`);
  return data; // SellThroughRead
}

// Calling this WRITES Model.priority server-side, every time (phase-8-backend.md
// §2.5). Only ever invoke it from hooks/reportingHooks/reportingQueries.js's
// useRecalculateReorderPriority, and only ever fire that hook's refetch() from
// an explicit user action (components/reporting/ReorderPriorityTable.jsx's
// "Recalculate" button) — never from a query that runs on mount or refocus.
export async function recalculateReorderPriority(windowDays) {
  const { data } = await fetchClient.get(`/reporting/reorder-priority?window_days=${windowDays}`);
  return data; // ReorderPriorityRead
}

export async function getMarginReport(windowDays) {
  const { data } = await fetchClient.get(`/reporting/margin?window_days=${windowDays}`);
  return data; // MarginReportRead
}
```

### 4.2 `hooks/reportingHooks/reportingQueries.js` (new) — the only file in this domain's `hooks/` folder, per `CLAUDE.md` §3.2

```js
import { useQuery } from '@tanstack/react-query';
import { reportingKeys } from '@/utils/queryKeys';
import {
  getBalanceStatement,
  getSellThrough,
  recalculateReorderPriority,
  getMarginReport,
} from '@/services/reportingService';

export function useBalanceStatement() {
  return useQuery({
    queryKey: reportingKeys.balanceStatement(),
    queryFn: getBalanceStatement,
  });
}

export function useSellThrough(windowDays) {
  return useQuery({
    queryKey: reportingKeys.sellThrough(windowDays),
    queryFn: () => getSellThrough(windowDays),
  });
}

export function useMarginReport(windowDays) {
  return useQuery({
    queryKey: reportingKeys.margin(windowDays),
    queryFn: () => getMarginReport(windowDays),
  });
}

// Deliberately lazy (§2 decision 2) — enabled:false means this never fetches
// on mount and never refetches in the background; refetchOnWindowFocus:false
// is redundant with enabled:false today but kept as a second guard against a
// future edit accidentally flipping `enabled` on. The ONLY caller of this
// hook's `refetch` is components/reporting/ReorderPriorityTable.jsx's
// "Recalculate" button (§5.3) — nothing else in this file, or anywhere else,
// should ever import recalculateReorderPriority directly.
//
// No onSuccess/onError here: TanStack Query v5 removed those callbacks from
// useQuery entirely (kept only on useMutation) — confirmed against the v5
// migration guide via Context7. Whatever needs to run after a successful
// recalculation (invalidating Catalog's Model list, §8) happens in the
// component, after awaiting the refetch() promise this hook returns.
export function useRecalculateReorderPriority(windowDays) {
  return useQuery({
    queryKey: reportingKeys.reorderPriority(windowDays),
    queryFn: () => recalculateReorderPriority(windowDays),
    enabled: false,
    refetchOnWindowFocus: false,
  });
}
```
No `hooks/reportingHooks/reportingMutations.js` file at all (§2 decision 2, `CLAUDE.md` §3.2's explicit "this domain has no mutations" note) — and no `validations/reportingSchemas.js` either (§2 decision 6).

---

## 5. Components — `components/reporting/`

### 5.1 `components/reporting/BalanceStatement.jsx` (new)

```jsx
import { Landmark, Wallet, Users2, Boxes, Loader2, Inbox } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { useBalanceStatement } from '@/hooks/reportingHooks/reportingQueries';

// Same sign convention + labeling PartyStatement.jsx already established for
// PartyBalanceRead.balance_pkr (positive = receivable/"Owes us", negative =
// payable/"We owe them") — duplicated locally rather than imported, matching
// this codebase's per-component small-helper convention (mirrors the backend's
// own money() duplication across domains, phase-8-backend.md §1/§3.3).
function balanceLabel(value) {
  const num = Number(value);
  if (num > 0) return 'Owes us';
  if (num < 0) return 'We owe them';
  return 'Settled';
}

function SummaryTile({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border p-4">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Icon className="size-4.5" />
      </span>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-lg font-semibold text-foreground">
          <CurrencyAmount value={value} />
        </p>
      </div>
    </div>
  );
}

export function BalanceStatement() {
  const { data, isLoading, isError } = useBalanceStatement();

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-4">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Landmark className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Balance Statement</CardTitle>
            <CardDescription>Where the business stands right now — cash, who owes what, stock on hand.</CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-6">
        {isLoading && (
          <div className="flex h-32 flex-col items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            Loading…
          </div>
        )}
        {isError && <div className="flex h-32 items-center justify-center text-destructive">Failed to load.</div>}

        {!isLoading && !isError && data && (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <SummaryTile icon={Wallet} label="Cash on hand" value={data.total_cash_pkr} />
              <SummaryTile icon={Users2} label="Net receivable" value={data.total_receivable_pkr - data.total_payable_pkr} />
              <SummaryTile icon={Boxes} label="Inventory value" value={data.inventory_value_pkr} />
              <SummaryTile icon={Landmark} label="Net position" value={data.net_position_pkr} />
            </div>
            <p className="text-xs text-muted-foreground">As of {data.as_of}</p>

            <div>
              <h3 className="mb-2 text-sm font-medium text-foreground">Cash / bank / wallet accounts</h3>
              <div className="overflow-x-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/50">
                      <TableHead>Account</TableHead>
                      <TableHead className="text-right">Balance</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.cash_accounts.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={2} className="h-24 text-center text-muted-foreground">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <Inbox className="size-5 text-muted-foreground/60" />
                            No active accounts.
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                    {data.cash_accounts.map((account) => (
                      <TableRow key={account.id} className="hover:bg-muted/40">
                        <TableCell>{account.label}</TableCell>
                        <TableCell className="text-right">
                          <CurrencyAmount value={account.balance} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-medium text-foreground">Receivables & payables by party</h3>
              <div className="overflow-x-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/50">
                      <TableHead>Party</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.party_balances.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={3} className="h-24 text-center text-muted-foreground">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <Inbox className="size-5 text-muted-foreground/60" />
                            Every party is settled — nothing outstanding.
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                    {data.party_balances.map((party) => (
                      <TableRow key={party.party_id} className="hover:bg-muted/40">
                        <TableCell>
                          <Link to={`/parties/${party.party_id}`} className="font-medium text-primary hover:underline">
                            {party.name}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <Badge variant={Number(party.balance_pkr) >= 0 ? 'secondary' : 'destructive'}>
                            {balanceLabel(party.balance_pkr)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <CurrencyAmount value={Math.abs(Number(party.balance_pkr))} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
```
`net_position_pkr` is shown as its own tile even though it's arithmetically derivable from the other three (`phase-8-backend.md` §2.2's own reasoning: *"'know where the business stands' reads as wanting one bottom-line number, not just three disconnected sections a user has to add up by hand"*) — the frontend inherits that reasoning rather than re-deriving it.

### 5.2 `components/reporting/SellThroughChart.jsx` (new)

```jsx
import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts';
import { TrendingUp, Loader2, Inbox } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
import { FormSelect } from '@/components/custom';
import { useSellThrough } from '@/hooks/reportingHooks/reportingQueries';
import { WINDOW_DAYS_OPTIONS, DEFAULT_WINDOW_DAYS } from '@/utils/constants';

const TOP_N = 10;

const chartConfig = {
  qty_sold: { label: 'Units sold', color: 'var(--chart-1)' },
};

export function SellThroughChart() {
  const [windowDays, setWindowDays] = useState(String(DEFAULT_WINDOW_DAYS));
  const { data, isLoading, isError } = useSellThrough(Number(windowDays));

  // Every active Model comes back, ranked 1..N (phase-8-backend.md §2.3/§2.4) —
  // only the top N fastest movers get charted here (§2 decision 8); the full
  // ranked list, fast AND slow, is already fully visible in
  // ReorderPriorityTable right below this card.
  const topEntries = (data?.entries ?? []).slice(0, TOP_N);

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-4">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <TrendingUp className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Fast Movers</CardTitle>
            <CardDescription>Top {TOP_N} models by units sold in the selected window.</CardDescription>
          </div>
        </div>
        <CardAction>
          <FormSelect
            name="sell_through_window"
            options={WINDOW_DAYS_OPTIONS}
            value={windowDays}
            onChange={setWindowDays}
            className="w-full sm:w-40"
          />
        </CardAction>
      </CardHeader>

      <CardContent>
        {isLoading && (
          <div className="flex h-72 flex-col items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            Loading…
          </div>
        )}
        {isError && <div className="flex h-72 items-center justify-center text-destructive">Failed to load.</div>}
        {!isLoading && !isError && topEntries.length === 0 && (
          <div className="flex h-72 flex-col items-center justify-center gap-2 text-muted-foreground">
            <Inbox className="size-6 text-muted-foreground/60" />
            No sales in this window yet.
          </div>
        )}
        {!isLoading && !isError && topEntries.length > 0 && (
          <ChartContainer config={chartConfig} className="h-72 w-full">
            <BarChart data={topEntries} layout="vertical" margin={{ left: 12 }}>
              <CartesianGrid horizontal={false} />
              <XAxis type="number" dataKey="qty_sold" hide />
              <YAxis type="category" dataKey="model_name" tickLine={false} axisLine={false} width={120} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="qty_sold" fill="var(--color-qty_sold)" radius={4} />
            </BarChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
```
`layout="vertical"` (recharts' naming for *horizontal bars*, category axis on the left) reads better than vertical bars once model names are involved — a long product name under a skinny vertical bar truncates or wraps badly, especially at ~375px; horizontal bars keep the full label readable in one line. Verify at ~375px that `width={120}`'s label column doesn't crowd out the bars entirely for a long model name — truncate with a custom tick formatter if it does (§9).

### 5.3 `components/reporting/ReorderPriorityTable.jsx` (new)

```jsx
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ListOrdered, RefreshCw, Loader2, Inbox } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { FormSelect } from '@/components/custom';
import { useSellThrough, useRecalculateReorderPriority } from '@/hooks/reportingHooks/reportingQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';
import { modelKeys } from '@/utils/queryKeys';
import { WINDOW_DAYS_OPTIONS, DEFAULT_WINDOW_DAYS } from '@/utils/constants';

const LOOKUP_PAGE = { page: 1, page_size: 100 };

export function ReorderPriorityTable() {
  const [windowDays, setWindowDays] = useState(String(DEFAULT_WINDOW_DAYS));
  const queryClient = useQueryClient();

  // Read-only ranking (§2 decision 3) — this is what the table always renders,
  // and it never writes anything.
  const { data, isLoading, isError } = useSellThrough(Number(windowDays));
  // Lazy (§2 decision 2) — only ever runs when "Recalculate" below is pressed.
  const { refetch: recalculate, isFetching: isRecalculating } = useRecalculateReorderPriority(Number(windowDays));
  // For the "Saved priority" column — Model.priority as Catalog currently has
  // it stored, so a user can see whether it's drifted from the live ranking
  // before choosing to commit (i.e. click Recalculate).
  const { data: modelsData } = useModels(LOOKUP_PAGE);

  const savedPriorityByModelId = Object.fromEntries((modelsData?.items ?? []).map((m) => [m.id, m.priority]));
  const entries = data?.entries ?? [];

  const handleRecalculate = async () => {
    const result = await recalculate();
    // fetchClient already toasted a failure — only invalidate Catalog's Model
    // list (ModelCrudConfig.js:18,26-30 shows priority there, §8) on success,
    // so a failed recalculation doesn't cause a pointless extra refetch.
    if (!result.isError) {
      queryClient.invalidateQueries({ queryKey: modelKeys.lists() });
    }
  };

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-4">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <ListOrdered className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Reorder Priority</CardTitle>
            <CardDescription>Ranked by sell-through — rank 1 reorders first from China next.</CardDescription>
          </div>
        </div>
        {/* Two controls in one CardAction cell — stacks below sm, §2 decision 10 */}
        <CardAction className="flex w-full flex-col items-stretch gap-2 sm:w-auto sm:flex-row sm:items-center">
          <FormSelect
            name="reorder_window"
            options={WINDOW_DAYS_OPTIONS}
            value={windowDays}
            onChange={setWindowDays}
            className="w-full sm:w-40"
          />
          <Button size="sm" variant="outline" disabled={isRecalculating} onClick={handleRecalculate}>
            <RefreshCw className={isRecalculating ? 'animate-spin' : ''} />
            {isRecalculating ? 'Saving…' : 'Recalculate'}
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent>
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead className="w-16">Rank</TableHead>
                <TableHead>Model</TableHead>
                <TableHead className="text-right">Units sold</TableHead>
                <TableHead className="text-right">Saved priority</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={4} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={4} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && entries.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No active models.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {entries.map((entry) => {
                const saved = savedPriorityByModelId[entry.model_id];
                const isStale = saved !== undefined && saved !== entry.rank;
                return (
                  <TableRow key={entry.model_id} className="hover:bg-muted/40">
                    <TableCell className="font-medium text-foreground">{entry.rank}</TableCell>
                    <TableCell>{entry.model_name}</TableCell>
                    <TableCell className="text-right">{entry.qty_sold}</TableCell>
                    <TableCell className="text-right">
                      {saved === undefined ? '—' : <Badge variant={isStale ? 'outline' : 'secondary'}>{saved}</Badge>}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
```
The "Saved priority" column's `outline` badge (drifted from the live ranking) vs. `secondary` badge (matches) is a genuinely new visual signal this codebase hasn't needed before — it directly surfaces §8's cross-domain fact (Catalog's `Model.priority` field can be manually edited, or simply stale from an earlier window/recalculation) instead of leaving it invisible.

### 5.4 `components/reporting/MarginReportTable.jsx` (new)

```jsx
import { useState } from 'react';
import { PieChart, Loader2, Inbox } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableFooter } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { FormSelect } from '@/components/custom';
import { useMarginReport } from '@/hooks/reportingHooks/reportingQueries';
import { WINDOW_DAYS_OPTIONS, DEFAULT_WINDOW_DAYS } from '@/utils/constants';

export function MarginReportTable() {
  const [windowDays, setWindowDays] = useState(String(DEFAULT_WINDOW_DAYS));
  const { data, isLoading, isError } = useMarginReport(Number(windowDays));
  const entries = data?.entries ?? [];

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-4">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <PieChart className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Margin by Item</CardTitle>
            <CardDescription>Sale rate vs. landed cost, per item, for items sold in the selected window.</CardDescription>
          </div>
        </div>
        <CardAction>
          <FormSelect
            name="margin_window"
            options={WINDOW_DAYS_OPTIONS}
            value={windowDays}
            onChange={setWindowDays}
            className="w-full sm:w-40"
          />
        </CardAction>
      </CardHeader>

      <CardContent>
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>SKU</TableHead>
                <TableHead>Model</TableHead>
                <TableHead className="text-right">Qty sold</TableHead>
                <TableHead className="text-right">Revenue</TableHead>
                <TableHead className="text-right">Cost</TableHead>
                <TableHead className="text-right">Margin</TableHead>
                <TableHead className="text-right">Margin %</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && entries.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No items sold in this window.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {entries.map((entry) => (
                <TableRow key={entry.item_id} className="hover:bg-muted/40">
                  <TableCell>{entry.sku}</TableCell>
                  <TableCell>{entry.model_name}</TableCell>
                  <TableCell className="text-right">{entry.qty_sold}</TableCell>
                  <TableCell className="text-right"><CurrencyAmount value={entry.revenue_pkr} /></TableCell>
                  <TableCell className="text-right"><CurrencyAmount value={entry.cost_pkr} /></TableCell>
                  <TableCell className="text-right"><CurrencyAmount value={entry.margin_pkr} /></TableCell>
                  <TableCell className="text-right">{entry.margin_pct.toFixed(1)}%</TableCell>
                </TableRow>
              ))}
            </TableBody>
            {!isLoading && !isError && entries.length > 0 && (
              <TableFooter>
                <TableRow>
                  <TableCell colSpan={3} className="font-medium text-foreground">Total</TableCell>
                  <TableCell className="text-right font-medium">
                    <CurrencyAmount value={data.total_revenue_pkr} />
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    <CurrencyAmount value={data.total_cost_pkr} />
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    <CurrencyAmount value={data.total_margin_pkr} />
                  </TableCell>
                  <TableCell />
                </TableRow>
              </TableFooter>
            )}
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
```
No pagination controls — `MarginReportRead.entries` is one row per item sold in the window, unpaginated (§1.1), matching how `BalanceStatement`'s two tables and `SellThroughChart`'s data are consumed elsewhere on this page.

---

## 6. Page / container

### 6.1 `containers/DashboardContainer.jsx` (new)

```jsx
import { BalanceStatement } from '@/components/reporting/BalanceStatement';
import { SellThroughChart } from '@/components/reporting/SellThroughChart';
import { ReorderPriorityTable } from '@/components/reporting/ReorderPriorityTable';
import { MarginReportTable } from '@/components/reporting/MarginReportTable';

export function DashboardContainer() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8 sm:py-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          One screen for where the business stands, and what to reorder from China next.
        </p>
      </div>

      <BalanceStatement />
      <SellThroughChart />
      <ReorderPriorityTable />
      <MarginReportTable />
    </div>
  );
}
```
Ordering follows `CLAUDE.md` §3.3's own annotation of what belongs "on the landing page" first (`BalanceStatement` + `SellThroughChart`), then the two supporting/detail sections (`ReorderPriorityTable`, `MarginReportTable`) below — the same "primary list above secondary/supporting list" stacking `ExpensesContainer.jsx` already established (`RecurringExpenseList` above `ExpenseList`, `phase-7-frontend.md` §8.1). No `Suspense` boundary and no URL params to read — same reasoning `PaymentsContainer.jsx`/`ExpensesContainer.jsx` already used for their own container files (no detail route exists anywhere in this domain).

### 6.2 `pages/DashboardPage.jsx` (new) — the same two-line shape every page file follows

```jsx
import { DashboardContainer } from '@/containers/DashboardContainer';

export function DashboardPage() {
  return <DashboardContainer />;
}
```

---

## 7. App shell updates

### 7.1 `App.jsx` — new route + redirect targets change

```jsx
import { DashboardPage } from '@/pages/DashboardPage';
// ...
<Route element={<ProtectedRoute />}>
  <Route path="/dashboard" element={<DashboardPage />} />
  <Route path="/settings" element={<SettingsPage />} />
  {/* ...every other existing route, unchanged... */}
  <Route path="/" element={<Navigate to="/dashboard" replace />} />
</Route>

<Route path="*" element={<Navigate to="/dashboard" replace />} />
```
Two changes to existing lines, both in `App.jsx`: the `/` redirect (currently `App.jsx:57`, target changes from `/purchase-orders` to `/dashboard`) and the catch-all `*` redirect (currently `App.jsx:60`, same change) — plus one new `<Route path="/dashboard" .../>` inserted as the *first* route inside the `ProtectedRoute` group (§2 decision 1). No other route changes.

### 7.2 `Navbar.jsx` — `NAV_LINKS`, new first entry

```js
const NAV_LINKS = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/purchase-orders', label: 'Purchase Orders' },
  { to: '/cargo-shipments', label: 'Cargo Shipments' },
  { to: '/inventory', label: 'Inventory' },
  { to: '/sales-orders', label: 'Sales Orders' },
  { to: '/payments', label: 'Payments' },
  { to: '/expenses', label: 'Expenses' },
  { to: '/parties', label: 'Parties' },
  { to: '/catalog', label: 'Catalog' },
  { to: '/settings', label: 'Settings' },
];
```
Both the desktop nav (`Navbar.jsx:70-74`) and the mobile drawer (`:99-109`) render from this same array, so this one edit reaches both — no separate mobile-specific change needed, confirmed by reading `Navbar.jsx` in full (§1.2).

---

## 8. Cross-domain note: `Model.priority` now has two writers

`Model.priority` (`backend/src/catalog/models.py`) has been a manually-editable field in Catalog's `CrudTable` since Phase 1 — `ModelCrudConfig.js:26-30` still exposes it as a plain `number` input, labeled *"Priority (used for reorder ranking from Phase 8)"*, with no `readOnly`/`disabled` flag. This phase makes `GET /reporting/reorder-priority` a **second** writer of that same column, and the two can now disagree: a user who manually types `priority = 1` for a slow-moving model in Catalog will have that value silently overwritten the next time anyone clicks **Recalculate** on `/dashboard`, and conversely a value `Recalculate` just wrote can be manually overwritten afterward in Catalog with no warning either direction.

This spec does **not** change `ModelCrudConfig.js` to make the field read-only or add a warning — that's a real product decision (should manual overrides be allowed to "pin" a model's priority against the next recalculation, or should Catalog's field become purely informational?) that belongs to whoever owns the product, not something to decide unilaterally while writing Phase 8's dashboard. What this spec *does* do: `ReorderPriorityTable.jsx`'s "Saved priority" column (§5.3) surfaces the drift visibly (an `outline` badge whenever the stored value and the live ranking disagree) rather than leaving it a silent, invisible race — and `handleRecalculate`'s `modelKeys.lists()` invalidation (§5.3) makes sure Catalog's own list reflects a `Recalculate` click immediately rather than showing a stale value until its next unrelated refetch.

---

## 9. Out of scope / known limitations

- **No historical/point-in-time dashboard.** `GET /reporting/balance-statement` has no `?as_of=` filter at all (`phase-8-backend.md` §8's own flagged future extension) — `BalanceStatement.jsx` can only ever show "now," matching the backend exactly.
- **`SellThroughChart.jsx`'s Y-axis label width (`width={120}`) is a fixed guess, not measured against real model names.** If a real model name is long enough to wrap or get clipped at that width on a ~375px screen, the fix is a `tickFormatter` that truncates with an ellipsis (recharts supports this on `<YAxis>` directly) — not built here since there's no real catalog data yet to size against; flagged for the first real design pass once actual `Model.name` values exist.
- **No caching/staleness controls tuned per report.** All four hooks use TanStack Query's plain defaults (apart from the lazy write-triggering one, §2 decision 2) — `staleTime`/`gcTime` are whatever the app's global `QueryClientProvider` defaults are. Acceptable at this system's scale (`phase-8-backend.md` §8 makes the identical point about the backend having zero result caching) — revisit only if these four queries' request volume ever becomes a real cost.
- **`Model.priority`'s dual-writer situation (§8) is surfaced, not resolved.** Whether Catalog's manual field should be locked, hidden, or left exactly as-is once Phase 8 ships is an open product question, not a frontend implementation gap.
- **No drill-through from `MarginReportTable`/`ReorderPriorityTable` rows to a per-item or per-model detail page.** Neither `Item` nor `Model` has a dedicated detail route anywhere in this app today (only Catalog's flat `CrudTable` list) — nothing to link to yet.
- **`SellThroughChart`'s top-10 cutoff (§2 decision 8) is a fixed constant, not user-configurable.** If a business with many more than 10 actively-selling models ever needs to see further down the fast-mover list from the chart itself (rather than scrolling `ReorderPriorityTable`), `TOP_N` is the one constant to change — not built as a control here since there's no evidence yet that 10 is too few.

---

## 10. Testing checklist (manual, matches `PLAN.md`'s "done when")

1. Sign in → confirm you land on `/dashboard` automatically (redirect from `/`), and the **Dashboard** nav link (first entry, both desktop and the `md:hidden` mobile drawer) is active.
2. `BalanceStatement`: confirm `Cash on hand` matches `GET /payments/payment-accounts/balances`'s sum exactly (visible on `/payments`), confirm a customer with an outstanding invoice shows `Owes us` with the correct amount and its name links through to `/parties/:id`, and confirm `Net position` is arithmetically `total_cash + total_receivable - total_payable + inventory_value`.
3. `SellThroughChart`: switch the window selector through `7/30/90/180` days — confirm the bars re-fetch and re-render for each, confirm at most 10 bars ever show, and confirm a model with zero sales in a very short window (e.g. `7` days right after seeding) simply doesn't appear in the chart (it's still in `ReorderPriorityTable` below, at `qty_sold=0`).
4. `ReorderPriorityTable`: confirm the table's `rank`/`qty_sold` columns match `SellThroughChart`'s underlying data for the same window, and confirm the "Saved priority" column initially shows `—` or a `secondary` badge for a model whose `Model.priority` already happens to match its live rank.
5. Click **Recalculate** → confirm the button shows "Saving…" while pending, confirm `GET /catalog/models` (via a quick trip to `/catalog`) shows each active model's `priority` now equal to its rank from step 4, and confirm every "Saved priority" badge in the table flips from `outline` (if it was drifted) to `secondary` (matches) without a full page reload.
6. Click **Recalculate** a second time with no sales activity in between → confirm the response and the table are unchanged (idempotence, `phase-8-backend.md` §2.3/§2.5's own guarantee) and no spurious 4xx/5xx toast appears.
7. On `/catalog`, manually edit a model's `Priority` field to an arbitrary number, save, then return to `/dashboard` → confirm `ReorderPriorityTable`'s "Saved priority" badge for that model now reads `outline` (drifted from the live ranking) — confirms §8's cross-domain note is visibly true, not just theoretical.
8. `MarginReportTable`: confirm an item with a known sale in the selected window shows `revenue_pkr = qty * rate_pkr` and `margin_pkr = revenue_pkr - cost_pkr` matching the same sale's numbers visible on its `SalesOrderDetail` page, and confirm the footer row's totals equal the column sums.
9. Switch `MarginReportTable`'s window to one that provably excludes a known sale (e.g. `7` days on data older than a week) → confirm that item disappears from the table entirely (no zero-value row, per `phase-8-backend.md` §2.6).
10. Resize to ~375px / ~768px / ~1280px: `ReorderPriorityTable`'s window-selector-plus-button `CardAction` stacks vertically below `sm` rather than crowding the title (§2 decision 10); every table scrolls horizontally inside its own container rather than widening the page; the summary-tile grid in `BalanceStatement` collapses to one column below `sm`; the new "Dashboard" nav entry appears correctly in the collapsed mobile menu.

---

## 11. Implementation checklist

New:
- `frontend/src/services/reportingService.js`
- `frontend/src/hooks/reportingHooks/reportingQueries.js`
- `frontend/src/components/reporting/BalanceStatement.jsx`
- `frontend/src/components/reporting/SellThroughChart.jsx`
- `frontend/src/components/reporting/ReorderPriorityTable.jsx`
- `frontend/src/components/reporting/MarginReportTable.jsx`
- `frontend/src/containers/DashboardContainer.jsx`
- `frontend/src/pages/DashboardPage.jsx`
- `frontend/src/components/ui/chart.jsx` — generated by `npx shadcn@latest add chart` (§2 decision 7), strip its `"use client"` pragma and unused `React` import per this codebase's existing convention for every shadcn-generated file

Changed:
- `frontend/src/utils/queryKeys.js` — §3.1 `reportingKeys` addition
- `frontend/src/utils/constants.js` — §3.2 `WINDOW_DAYS_OPTIONS`/`DEFAULT_WINDOW_DAYS` addition
- `frontend/src/App.jsx` — new `/dashboard` route, `/` and `*` redirect targets change (§7.1)
- `frontend/src/components/Navbar.jsx` — new first `NAV_LINKS` entry (§7.2)
- `frontend/package.json` — `recharts` added as a dependency (via the shadcn CLI, not a hand-picked version, §2 decision 7)

Not changed (confirmed, not assumed):
- `backend/` — entire tree, already implemented and reviewed in `phase-8-backend.md`
- `frontend/src/components/catalog/ModelCrudConfig.js` — the dual-writer situation is surfaced (§8), not fixed, by deliberate choice
- `frontend/src/validations/*` — no `reportingSchemas.js`, by deliberate choice (§2 decision 6)
- `frontend/src/containers/SettingsContainer.jsx` — no reporting-related Settings tab; this domain has no lookup-table CRUD to host there
- Every other domain's frontend code (auth, parties, catalog, purchasing, cargo, inventory, sales, payments, expenses) apart from the two Catalog/Navbar citations above
