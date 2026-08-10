# Phase 4 Frontend — Spec

Source of truth: `PLAN.md` (§ Phase 4 — Wholesale sales) for *what*, `CLAUDE.md` (§3) for *how*, `.claude/skills/frontend-design-system/SKILL.md` for *how it should look*, and `.claude/specs/phase-4-backend.md` for the backend design — but the API surface below (§1.1) is re-verified against the **actual running `backend/src/sales/`, `backend/src/parties/`, and `backend/src/inventory/` code**, not the design doc, exactly like the phase-1/2/3 frontend specs did for their phases. Where this doc and the backend spec draft disagree, trust §1.1.

**Done when** (verbatim from PLAN.md): you can invoice a customer, see stock drop, and pull up that party's full history and current balance on one screen.

At the time of writing, `frontend/` already has Phases 0–3 shipped in full — auth, the generic `CrudTable`/`CrudDrawer` engine, `ExchangeRate`/`PaymentMethod`/`CargoMode`/`CargoCostBasis` lookups on `/settings`, full `Category`/`Model`/`Item`/`Party` CRUD, hand-written `PurchaseOrder` and `CargoShipment` list/create/detail screens, and the `StockLotTable`/`ReceiveStockLotDialog`/`StockAdjustmentDialog` inventory screens from Phase 3 (including `useReceivedLineIds`, `useStockLots`, `stockLotKeys`). This spec is additive on top of that tree — nothing in the prior specs' scope gets removed or renamed. `PARTY_ROLE.CUSTOMER` / `PARTY_ROLE_OPTIONS` already include the `customer` role (added speculatively in Phase 1, unused until now).

---

## 1. Scope

Build, in this order (each step independently usable/testable before the next):

1. `utils/queryKeys.js` — add `salesOrderKeys`, and a `statement()` key on the existing `partyKeys`.
2. `utils/currencyUtils.js` — add `computeSaleAmount`, the PKR-direct equivalent of `computeRmbAmount` (no exchange-rate step, per §1.1).
3. `services/salesService.js`, `hooks/salesHooks/salesQueries.js`, `hooks/salesHooks/salesMutations.js`, `validations/salesSchemas.js` — the new domain's full data-access stack, mirroring `purchasingService.js`/`purchasingHooks/`'s shape (the closest analog — a transactional entity with lines, a party, and money — same relationship the backend spec draws between `sales/` and `purchasing/`).
4. `services/partyService.js` gets `getPartyStatement`; `hooks/partyHooks/partyQueries.js` gets `usePartyStatement` and `useCustomerParties` (the latter mirroring `useChinaVendorParties`/`useCargoAgentParties` exactly).
5. `components/sales/form/SalesOrderForm.jsx`, `components/sales/SalesOrderList.jsx`, `components/sales/SalesOrderDetail.jsx` — the three CLAUDE.md §3.3 names this domain, minus a separate `SalesOrderLineTable.jsx` (§2, decision 1).
6. `components/parties/PartyStatement.jsx` — the CLAUDE.md-named statement view; `components/parties/PartyCrudConfig.jsx` gets one changed column (name becomes a link into it).
7. Pages/containers: `pages/SalesOrdersPage.jsx` → `containers/SalesOrdersContainer.jsx`, `pages/SalesOrderCreatePage.jsx` → `containers/SalesOrderCreateContainer.jsx`, `pages/SalesOrderDetailPage.jsx` → `containers/SalesOrderDetailContainer.jsx` (three-file split, matching `PurchaseOrder*`); `pages/PartyDetailPage.jsx` → `containers/PartyDetailContainer.jsx` (the CLAUDE.md-named pair).
8. App shell — three new `/sales-orders*` routes and one new `/parties/:partyId` route in `App.jsx`, one new nav link in `Navbar.jsx`.

Out of scope, deferred per `PLAN.md`'s roadmap or this phase's own backend spec (§9 there): local-vendor party role and its reuse of these same screens (Phase 5), payment recording against a party's balance (Phase 6), any expenses/reporting work. Also out of scope this phase specifically (§2 below): a client-side FIFO/margin preview during order creation, a Yup stock-availability bound, an edit/void UI for a posted sale, and a cross-party receivables dashboard — none of these have a backing endpoint or a PLAN.md ask, so there is nothing to build them against yet.

### 1.1 Confirmed API surface (from running backend code, not the design draft)

Every route below requires `Authorization: Bearer <access_token>`, same as every route in Phases 0–3. Error bodies are the same dual shape `fetchClient.js` already handles: `{"detail": "..."}` for a domain `AppException`, `{"detail": [{"loc":..., "msg":...}]}` for a raw Pydantic validation failure. **Every `Decimal` field is still a JSON string** — `qty`, `rate_pkr`, `amount_pkr`, `cost_pkr`, `margin_pkr`, `total_pkr`, `total_margin_pkr`, `qty_consumed`, `unit_cost_pkr`, `opening_balance`, `debit`, `credit`, `running_balance`, `closing_balance` all serialize as strings (e.g. `"1200.00"`). Send back exactly what the form collected — never `Number()`-cast before it goes into a request body.

| Method | Path | Body / Query | Response | Status | Notes |
|---|---|---|---|---|---|
| POST | `/sales/sales-orders` | `SalesOrderCreate` | `SalesOrderRead` | 201 / 404 / 409 / 422 | **this *is* the invoice action** — nested create only, no separate line-create call |
| GET | `/sales/sales-orders?page=&page_size=` | — | `{items:[SalesOrderRead], total, page, page_size}` | 200 | no filter params exist (no `?party_id=`) |
| GET | `/sales/sales-orders/{id}` | — | `SalesOrderRead` | 200 / 404 | |
| GET | `/parties/{party_id}/statement` | — | `PartyStatementRead` | 200 / 404 | no query params — no pagination, no date range |

Path note: `sales_router` is declared as `APIRouter(prefix="/sales-orders", ...)` and mounted at `/sales` in `main.py` — full paths are the double-segment `/sales/sales-orders...` shown above, the same double-prefix shape `inventory/` already established (`/inventory/stock-lots`). `services/salesService.js` must use the full path, not just `/sales`.

**`SalesOrderCreate`** request body: `{party_id: int, order_date: "YYYY-MM-DD", lines: [{item_id: int, qty: "12.00", rate_pkr: "450.00"}]}` — `qty`/`rate_pkr` must be `> 0`, `lines` needs `min_length=1`.

**`SalesOrderRead`** response: `{id, party_id, order_date, created_at, lines: [SalesOrderLineRead], total_pkr, total_margin_pkr}`. `total_pkr`/`total_margin_pkr` are `@computed_field`s — **use them directly, don't resum client-side**, same rule Phase 2/3 already established for `amount_pkr`/`value_remaining_pkr`.

**`SalesOrderLineRead`**: `{id, item_id, qty, rate_pkr, consumptions: [SalesOrderLineLotRead], amount_pkr, cost_pkr, margin_pkr}` — `amount_pkr`/`cost_pkr`/`margin_pkr` are computed fields too. `consumptions` is the "which lot(s) this line drew from" list PLAN.md's Phase 4 wording asks for — never empty on a successfully created order (every line consumes at least one lot by construction).

**`SalesOrderLineLotRead`**: `{stock_lot_id, qty_consumed, unit_cost_pkr}` — `unit_cost_pkr` is the immutable `StockLot.landed_cost_pkr` snapshot at the moment of sale, not a live lookup.

**No `PUT`/`DELETE` on `/sales/sales-orders`, and no `SalesOrderUpdate` schema exists at all.** A sales order is write-once — same precedent Phase 1–3 already set for `PurchaseOrder`/`CargoShipment`/`StockLot`.

**Sales order create error cases, in the order the backend checks them** (`backend/src/sales/service.py`, per backend spec §5.1):

| Cause | Status | Detail |
|---|---|---|
| `party_id` doesn't resolve to an active party | 404 | "Party not found" (`PartyNotFound`, reused from `parties/exceptions.py`) |
| party found but doesn't hold the `customer` role | 422 | `PartyRoleMismatch` message |
| the same `item_id` appears on more than one line | 422 | "Each item may appear at most once per sales order — increase its qty instead" (`InvalidSalesOrderItem`) |
| an `item_id` doesn't resolve to an active item | 422 | `InvalidSalesOrderItem`, names the missing/inactive id(s) |
| an item's combined line `qty` exceeds its total `qty_remaining` across all lots | 422 | `f"Item {item_id}: need {qty_needed}, only {available} in stock"` (`InsufficientStock`) |
| DB integrity error on commit | 409 | generic conflict message |

**A successful create has two side effects beyond the response body, both worth invalidating for**: it decrements `StockLot.qty_remaining` for every lot the FIFO walk touched (via `inventory.consume_stock_fifo`), and it posts exactly one `LedgerEntry` — account `"Accounts Receivable"`, `debit = total_pkr`, `party_id` set — meaning the sold customer's `/parties/{id}/statement` changes immediately. Neither is reflected in `SalesOrderRead` itself; both are separately-cached data (`stockLotKeys`, `partyKeys.statement`) that a `useCreateSalesOrder` mutation must invalidate explicitly (§4).

**`PartyStatementRead`**: `{party: PartyRead, opening_balance, entries: [PartyStatementEntryRead], closing_balance}`. `PartyStatementEntryRead`: `{id, entry_date, account, debit, credit, reference_type, reference_id: int|null, running_balance}`. **Sign convention** (backend spec §2.6, confirmed in `parties/service.get_party_statement`): each entry's `running_balance = previous running + debit − credit`, seeded from `opening_balance`; `closing_balance` is the final running value. **Positive means the party owes the business (a receivable); negative means the business owes the party (a payable).** This holds uniformly regardless of which role(s) the party carries — a `customer`'s sale debits (increases) their balance, a future `china_vendor`/`local_vendor` purchase would credit (decrease) theirs, on the same signed number. Render this distinction in the UI (§7.4) rather than showing a bare signed number a bookkeeper has to mentally flip.

**`entries` is the full, unpaginated history for that party** — no `?page=`, no date filter. Fine at this business's current scale (backend spec §9); nothing to build pagination against yet.

**No `?party_id=` filter on `GET /sales/sales-orders`.** A customer's specific *invoices* are not independently listable by party this phase — their financial history is only visible via the ledger-derived statement (§7.4), which shows amounts and references but not per-line item/qty/margin detail. This is a real, named gap in the backend (backend spec §9's "no aggregate... per-party" note applies one level down too) — not something the frontend can paper over with a client-side filter, because `GET /sales/sales-orders` has no `page_size=100`-and-filter escape hatch here: past 100 total sales orders, a client-side filter would silently miss older ones for a party, unlike the `useChinaVendorParties`-style lookup filters elsewhere which only ever back a small dropdown, not a page's primary data. **Not built this phase** — flagged again in §2.

---

## 2. Decisions

Judgment calls this spec makes where `PLAN.md`/`CLAUDE.md` don't fully spell out the frontend shape, recorded here so they're reviewed once rather than re-derived mid-implementation. None of these were put to the user as an explicit either/or during this pass — each follows a precedent already established by Phases 1–3's actual shipped code (cited inline) or the backend spec's own reasoning.

1. **No standalone `SalesOrderLineTable.jsx` file, despite CLAUDE.md §3.3 naming one.** Verified against the actual repo, not the illustrative tree: neither `purchasing/` nor `cargo/` ever built the separate `PurchaseOrderLineTable.jsx`/`CargoAllocationTable.jsx` files CLAUDE.md's own §3.3 names for them — both inlined their line table directly into `PurchaseOrderDetail.jsx`/`CargoShipmentDetail.jsx`. `SalesOrderDetail.jsx` follows that established (not illustrative) precedent: one file, its own `<Table>` inline.
2. **No client-side FIFO/margin preview while building a sales order.** CLAUDE.md's own name for the (skipped, per decision 1) line-table file calls out "FIFO lot draw-down preview" — satisfied here by `SalesOrderDetail.jsx` rendering the server's actual `consumptions`/`cost_pkr`/`margin_pkr` *after* creation, not by a parallel client-side FIFO simulator during creation. Reasoning: which lot(s) a line will actually draw from depends on `StockLot.qty_remaining` at the instant the order commits, which can change between the user typing a quantity and hitting submit (another sale, another adjustment). A client-side simulation would risk showing a margin the server then doesn't honor — worse than showing nothing, and a bigger drift risk than the "never recompute a computed_field" rule Phase 2/3 already established for simpler cases (`amount_pkr`, `value_remaining_pkr`). `SalesOrderForm` shows only `amount_pkr` (`qty × rate_pkr`, no FIFO involved) live, exactly the scope `PurchaseOrderForm`'s own live preview already covers for RMB/PKR amounts.
3. **A non-blocking "In stock: N" hint per line, sourced from already-cached `useStockLots` data — but no Yup rule enforcing it.** Showing current `qty_remaining` next to the item picker helps avoid an obvious `InsufficientStock` 422 before it happens, at zero extra request cost (the same `page_size=100` stock-lot fetch `StockLotTable` already makes). It is **not** wired into `validations/salesSchemas.js` as a bound, unlike `buildStockAdjustmentSchema`'s `qty_delta` range check (phase-3-frontend spec §5.4) — that check validates against a single, already-fixed lot's fields passed in as a prop at dialog-open time; this one would validate against live, shared, multi-item stock that can go stale the moment a second browser tab or a concurrent request changes it. A Yup pass here would be false confidence, not real protection; the actual protection is the backend's `with_for_update()`-guarded check (backend spec §2.4), already surfaced as a toast via the existing generic error-handling path.
4. **Duplicate-item-per-line *is* enforced client-side, unlike the stock-quantity case above.** Unlike live stock, "does this form's own `lines` array repeat an `item_id`" is a pure function of the form's current values — no external state to go stale. `validations/salesSchemas.js` adds an array-level `.test()` mirroring the backend's own rule (§1.1, `InvalidSalesOrderItem`) verbatim, giving an inline error before submit instead of a round-trip 422.
5. **`PartyStatement.jsx` and its container are new, but `PartyCrudConfig.jsx`'s edit/delete flow is untouched.** The statement is an additive read view, not a replacement for the existing `CrudTable`-driven add/edit/deactivate flow on `/parties` — a party's `name`/`roles`/`contact`/`address`/`opening_balance` are still edited from the same drawer Phase 1 built. The only change to the existing screen is making the `name` cell a link into the new `/parties/:partyId` route, the same "ID becomes a link, rest of the row is unchanged" pattern `PurchaseOrderList`/`SalesOrderList` already use for their own primary column.
6. **No "record a sale for this customer" shortcut button on `PartyStatement.jsx`.** PLAN.md's literal ask for this phase is "pull up that party's full history and current balance on one screen" — a read screen. A `?party_id=` pre-fill on `/sales-orders/new` would be a small, real convenience, but nothing in this codebase has a query-param-prefill precedent yet (`PurchaseOrderForm`/`CargoShipmentForm` both start from a bare form every time) — adding one here on spec, for one call site, isn't worth introducing a new pattern that has no second consumer yet. Revisit if this turns out to be a real point of friction once the screen is in daily use.
7. **`GET /sales/sales-orders` is not filtered or cross-referenced by party on the sales list screen** (§1.1's last paragraph) — `SalesOrderList.jsx` lists every order, unfiltered, same shape as `PurchaseOrderList.jsx`. A customer's own invoice history, beyond the ledger-level amounts already visible on their statement, is out of scope this phase — it would need either a backend `?party_id=` filter (not present) or an unbounded client-side fetch-and-filter this list's data volume doesn't safely support (§1.1). Flagged as a real gap, not silently dropped.

---

## 3. Generic CRUD engine

No changes. `SalesOrder`/`SalesOrderLine`/`SalesOrderLineLot` are transactional, hand-written entities — like `PurchaseOrder`/`CargoShipment`/`StockLot`, they carry cross-table validation (role check, duplicate-item check, FIFO consumption) and a ledger post, exactly the case `PLAN.md`'s own rule reserves for hand-written services rather than the generic factory. None of the three backend models carry the `is_active` column the generic factory asserts on. `Party` itself continues to use its existing hand-written CRUD (unchanged this phase) plus the one new statement endpoint — Party was never on the generic factory to begin with (it needed role validation and the ledger-backed opening-balance post from Phase 1 onward).

---

## 4. Shared utility changes

### 4.1 `utils/queryKeys.js` additions

```javascript
export const salesOrderKeys = {
  all: ['salesOrders'],
  lists: () => [...salesOrderKeys.all, 'list'],
  list: (params) => [...salesOrderKeys.lists(), params],
  detail: (id) => [...salesOrderKeys.all, 'detail', id],
};
```

```javascript
// utils/queryKeys.js — partyKeys, changed
export const partyKeys = {
  all: ['parties'],
  lists: () => [...partyKeys.all, 'list'],
  list: (params) => [...partyKeys.lists(), params],
  statement: (id) => [...partyKeys.all, 'statement', id],  // new
};
```

No `partyKeys.detail(id)` is added — nothing reads a single party outside its statement this phase (the edit drawer works off the already-fetched list row, same as every other `CrudTable` entity), so there's nothing yet to key a bare party-detail cache entry against. Add one if a future phase needs it, not speculatively here.

### 4.2 `utils/currencyUtils.js` addition

```javascript
// Mirrors backend/src/sales/schemas.py's SalesOrderLineRead.amount_pkr exactly:
// qty × rate_pkr, entered directly in PKR with no exchange-rate step — unlike
// purchasing, wholesale sales are quoted in PKR to begin with (backend spec §3.1).
export function computeSaleAmount(qty, ratePkr) {
  return toMoney(Number(qty) * Number(ratePkr));
}
```

---

## 5. Sales domain — data access

### 5.1 `services/salesService.js` (new) — mirrors `purchasingService.js`'s shape

```javascript
import { fetchClient } from '@/middleware/fetchClient';
import { buildQueryString } from '@/utils/queryParams';

export async function listSalesOrders(params) {
  const { data } = await fetchClient.get(`/sales/sales-orders${buildQueryString(params)}`);
  return data;
}

export async function getSalesOrder(id) {
  const { data } = await fetchClient.get(`/sales/sales-orders/${id}`);
  return data;
}

export async function createSalesOrder(payload) {
  const { data } = await fetchClient.post('/sales/sales-orders', payload);
  return data;
}
```

### 5.2 `hooks/salesHooks/salesQueries.js` (new)

```javascript
import { useQuery } from '@tanstack/react-query';
import { salesOrderKeys } from '@/utils/queryKeys';
import { listSalesOrders, getSalesOrder } from '@/services/salesService';

export function useSalesOrders(params) {
  return useQuery({ queryKey: salesOrderKeys.list(params), queryFn: () => listSalesOrders(params) });
}

export function useSalesOrder(id) {
  return useQuery({
    queryKey: salesOrderKeys.detail(id),
    queryFn: () => getSalesOrder(id),
    enabled: Boolean(id),
  });
}
```

### 5.3 `hooks/salesHooks/salesMutations.js` (new)

```javascript
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { salesOrderKeys, stockLotKeys, partyKeys } from '@/utils/queryKeys';
import * as salesService from '@/services/salesService';

export function useCreateSalesOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: salesService.createSalesOrder,
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: salesOrderKeys.lists() });
      // A sale consumes StockLot.qty_remaining via FIFO (§1.1) — the inventory
      // view must reflect the drawdown without a manual refresh. Invalidate the
      // whole key space (lists + any cached detail), same reasoning the phase-3
      // spec used for a receive's effect on purchaseOrderKeys.
      queryClient.invalidateQueries({ queryKey: stockLotKeys.all });
      // Posts one LedgerEntry against this party (§1.1) — if their statement is
      // open in another tab, it must pick up the new entry and balance.
      queryClient.invalidateQueries({ queryKey: partyKeys.statement(variables.party_id) });
    },
  });
}
```

### 5.4 `validations/salesSchemas.js` (new)

```javascript
import { object, string, number, array } from 'yup';

export const salesOrderLineSchema = object({
  item_id: number().typeError('Select an item').required('Select an item'),
  qty: number().typeError('Quantity must be a number').positive('Quantity must be positive').required('Quantity is required'),
  rate_pkr: number().typeError('Rate must be a number').positive('Rate must be positive').required('Rate is required'),
});

export const salesOrderCreateSchema = object({
  party_id: number().typeError('Select a customer').required('Select a customer'),
  order_date: string().required('Order date is required'),
  lines: array()
    .of(salesOrderLineSchema)
    .min(1, 'Add at least one line')
    // Mirrors the backend's own rule verbatim (§1.1 / backend spec §2.3) — a pure
    // function of this form's own values, safe to enforce client-side unlike the
    // stock-quantity case (§2, decision 3).
    .test(
      'unique-items',
      'Each item may appear at most once per sales order — increase its qty instead',
      (lines) => {
        if (!lines) return true;
        const ids = lines.map((line) => line.item_id).filter((id) => id !== undefined && id !== '');
        return new Set(ids).size === ids.length;
      },
    ),
});
```

---

## 6. Parties domain — statement additions

### 6.1 `services/partyService.js` addition

```javascript
export async function getPartyStatement(id) {
  const { data } = await fetchClient.get(`/parties/${id}/statement`);
  return data;
}
```

### 6.2 `hooks/partyHooks/partyQueries.js` additions

```javascript
import { getPartyStatement } from '@/services/partyService'; // add to existing import

export function usePartyStatement(id) {
  return useQuery({
    queryKey: partyKeys.statement(id),
    queryFn: () => getPartyStatement(id),
    enabled: Boolean(id),
  });
}

// Same client-side role-filter pattern as useChinaVendorParties/useCargoAgentParties
// (phase-1/2-frontend specs), for the sales order form's customer picker.
export function useCustomerParties() {
  const query = useParties(LOOKUP_PAGE);
  const customers = (query.data?.items ?? []).filter((party) => party.roles.includes(PARTY_ROLE.CUSTOMER));
  return { ...query, customers };
}
```

### 6.3 `components/parties/PartyCrudConfig.jsx` — `name` column becomes a link

```jsx
// components/parties/PartyCrudConfig.jsx — changed
import { Link } from 'react-router-dom';
// ...existing imports unchanged

export const partyCrudConfig = {
  // ...unchanged
  columns: [
    {
      key: 'name',
      label: 'Name',
      render: (row) => (
        <Link to={`/parties/${row.id}`} className="font-medium text-primary hover:underline">
          {row.name}
        </Link>
      ),
    },
    { key: 'roles', label: 'Roles', render: (row) => <PartyRoleBadges roles={row.roles} /> },
    { key: 'contact', label: 'Contact' },
  ],
  // ...unchanged
};
```

Edit/delete actions on the row are untouched — `CrudTable`'s Actions column is separate from this cell, same as `PurchaseOrderList`'s own ID-as-link column coexists with its non-editable row (§2, decision 5).

---

## 7. Components

### 7.1 `components/sales/form/SalesOrderForm.jsx` (new) — mirrors `PurchaseOrderForm.jsx`'s shape, minus the exchange-rate step

```jsx
import { useForm, useFieldArray, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FormField, FormSelect } from '@/components/custom';
import { salesOrderCreateSchema } from '@/validations/salesSchemas';
import { useCreateSalesOrder } from '@/hooks/salesHooks/salesMutations';
import { useCustomerParties } from '@/hooks/partyHooks/partyQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { useCategories } from '@/hooks/catalogHooks/categoryQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';
import { useStockLots } from '@/hooks/inventoryHooks/inventoryQueries';
import { toMoney, computeSaleAmount, formatPKR } from '@/utils/currencyUtils';

const LOOKUP_PAGE = { page: 1, page_size: 100 };
const EMPTY_LINE = { item_id: '', qty: '', rate_pkr: '' };
const todayIso = () => new Date().toISOString().slice(0, 10);

export function SalesOrderForm({ onSuccess }) {
  const { customers } = useCustomerParties();
  const { data: itemsData } = useItems(LOOKUP_PAGE);
  const { data: categoriesData } = useCategories(LOOKUP_PAGE);
  const { data: modelsData } = useModels(LOOKUP_PAGE);
  // Informational only — never validated against in Yup (§2, decision 3): stock is
  // live, shared, external state that can change between typing and submit. The
  // authoritative check is the backend's own InsufficientStock 422, already toasted
  // generically by fetchClient on submit failure.
  const { data: stockLotsData } = useStockLots({ page: 1, page_size: 100 });

  const categoryNameById = Object.fromEntries((categoriesData?.items ?? []).map((c) => [c.id, c.name]));
  const modelNameById = Object.fromEntries((modelsData?.items ?? []).map((m) => [m.id, m.name]));
  const itemOptions = (itemsData?.items ?? []).map((item) => ({
    value: String(item.id),
    label: `${modelNameById[item.model_id] ?? '?'} · ${categoryNameById[item.category_id] ?? '?'} — ${item.sku}${item.variant ? ` (${item.variant})` : ''}`,
  }));
  const customerOptions = customers.map((p) => ({ value: String(p.id), label: p.name }));
  const availableByItemId = (stockLotsData?.items ?? []).reduce((acc, lot) => {
    const key = String(lot.item_id);
    acc[key] = (acc[key] ?? 0) + Number(lot.qty_remaining);
    return acc;
  }, {});

  const {
    control,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(salesOrderCreateSchema, {}, { raw: true }),
    defaultValues: { party_id: '', order_date: todayIso(), lines: [EMPTY_LINE] },
  });
  const { fields, append, remove } = useFieldArray({ control, name: 'lines' });
  const createMutation = useCreateSalesOrder();

  const lines = watch('lines') ?? [];
  const rows = fields.map((field, index) => ({ ...field, ...(lines[index] ?? {}) }));
  const totalPkr = toMoney(rows.reduce((sum, row) => sum + computeSaleAmount(row.qty, row.rate_pkr), 0));

  const onSubmit = async (values) => {
    try {
      const created = await createMutation.mutateAsync({
        party_id: values.party_id,
        order_date: values.order_date,
        lines: values.lines.map(({ item_id, qty, rate_pkr }) => ({ item_id, qty, rate_pkr })),
      });
      onSuccess?.(created);
    } catch {
      // fetchClient already toasted the backend's error detail (role mismatch,
      // duplicate item, insufficient stock) — keep the form open to fix and retry.
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
      <div className="grid gap-4 md:grid-cols-2">
        <Controller
          name="party_id"
          control={control}
          render={({ field }) => (
            <FormSelect
              {...field}
              label="Customer"
              placeholder="Select a customer"
              options={customerOptions}
              error={errors.party_id?.message}
            />
          )}
        />
        <Controller
          name="order_date"
          control={control}
          render={({ field }) => (
            <FormField {...field} type="date" label="Order date" error={errors.order_date?.message} />
          )}
        />
      </div>

      <div className="flex flex-col gap-3">
        {rows.map((row, index) => (
          <div key={row.id} className="grid gap-3 rounded-lg border p-3 md:grid-cols-[2fr_1fr_1fr_1fr_auto] md:items-start">
            <div className="flex flex-col gap-1">
              <Controller
                name={`lines.${index}.item_id`}
                control={control}
                render={({ field }) => (
                  <FormSelect
                    {...field}
                    label="Item"
                    placeholder="Select an item"
                    options={itemOptions}
                    error={errors.lines?.[index]?.item_id?.message}
                  />
                )}
              />
              {row.item_id && (
                <span className="text-xs text-muted-foreground">In stock: {availableByItemId[row.item_id] ?? 0}</span>
              )}
            </div>
            <Controller
              name={`lines.${index}.qty`}
              control={control}
              render={({ field }) => (
                <FormField {...field} type="number" step="0.01" label="Qty" error={errors.lines?.[index]?.qty?.message} />
              )}
            />
            <Controller
              name={`lines.${index}.rate_pkr`}
              control={control}
              render={({ field }) => (
                <FormField
                  {...field}
                  type="number"
                  step="0.01"
                  label="Rate (PKR)"
                  error={errors.lines?.[index]?.rate_pkr?.message}
                />
              )}
            />
            <div className="flex flex-col justify-end text-sm text-muted-foreground">
              <span>{formatPKR(computeSaleAmount(row.qty, row.rate_pkr))}</span>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label="Remove line"
              onClick={() => remove(index)}
              disabled={rows.length === 1}
              className="justify-self-start md:justify-self-auto"
            >
              <Trash2 className="text-destructive" />
            </Button>
          </div>
        ))}
        {/* react-hook-form places a whole-array Yup .test() error under errors.lines.root,
            not errors.lines, whenever the array also has per-index registered fields
            (lines.0.item_id, etc.) — @hookform/resolvers' toNestErrors nests it there
            to avoid colliding with the per-item error shape (confirmed against the
            installed @hookform/resolvers/yup source during manual testing). */}
        {errors.lines?.root?.message && <p className="text-sm text-destructive">{errors.lines.root.message}</p>}
        <Button type="button" variant="outline" size="sm" onClick={() => append(EMPTY_LINE)} className="self-start">
          <Plus /> Add line
        </Button>
      </div>

      <div className="flex justify-end border-t pt-4 text-sm">
        <span>
          Total: <strong>{formatPKR(totalPkr)}</strong>
        </span>
      </div>

      <Button type="submit" size="lg" disabled={isSubmitting} className="self-end">
        {isSubmitting ? 'Saving…' : 'Create sales order'}
      </Button>
    </form>
  );
}
```

`errors.lines?.root?.message` (rather than `errors.lines?.[index]?...`) is where the array-level `.test('unique-items', ...)` failure surfaces — react-hook-form's `useFieldArray` reserves the bare `errors.lines` shape for per-index errors (`errors.lines[i].item_id`, etc.), so `@hookform/resolvers`' `toNestErrors` nests any whole-array Yup error (this `.test()`, and `array().min(1, ...)`'s failure too) under a `.root` key specifically to avoid colliding with that per-index shape. Confirmed empirically during manual browser testing: `errors.lines?.message` silently never fires (validation still blocks submission correctly, but no message renders) — `.root.message` is the actual path.

### 7.2 `components/sales/SalesOrderList.jsx` (new) — mirrors `PurchaseOrderList.jsx`

```jsx
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Loader2, Inbox, Receipt } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { PaginationControls } from '@/components/common/PaginationControls';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { useSalesOrders } from '@/hooks/salesHooks/salesQueries';
import { useParties } from '@/hooks/partyHooks/partyQueries';

const DEFAULT_PAGE_SIZE = 20;
const LOOKUP_PAGE = { page: 1, page_size: 100 };

export function SalesOrderList() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError } = useSalesOrders({ page, page_size: DEFAULT_PAGE_SIZE });
  const { data: partiesData } = useParties(LOOKUP_PAGE);

  const customerNameById = Object.fromEntries((partiesData?.items ?? []).map((p) => [p.id, p.name]));
  const orders = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Receipt className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Sales Orders</CardTitle>
            <CardDescription>Every invoice to a wholesale customer, FIFO-costed against the lots it drew from.</CardDescription>
          </div>
        </div>
        <CardAction>
          <Button size="sm" asChild>
            <Link to="/sales-orders/new">
              <Plus />
              New sales order
            </Link>
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>ID</TableHead>
                <TableHead>Customer</TableHead>
                <TableHead>Order date</TableHead>
                <TableHead className="text-right">Total PKR</TableHead>
                <TableHead className="text-right">Margin PKR</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={5} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={5} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && orders.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No sales orders yet — create the first one above.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {orders.map((order) => (
                <TableRow key={order.id} className="hover:bg-muted/40">
                  <TableCell>
                    <Link to={`/sales-orders/${order.id}`} className="font-medium text-primary hover:underline">
                      #{order.id}
                    </Link>
                  </TableCell>
                  <TableCell>{customerNameById[order.party_id] ?? `Party #${order.party_id}`}</TableCell>
                  <TableCell>{order.order_date}</TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={order.total_pkr} />
                  </TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={order.total_margin_pkr} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <PaginationControls page={page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={setPage} />
      </CardContent>
    </Card>
  );
}
```

### 7.3 `components/sales/SalesOrderDetail.jsx` (new) — mirrors `PurchaseOrderDetail.jsx`, inline line table (§2, decision 1)

```jsx
import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { useCategories } from '@/hooks/catalogHooks/categoryQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';

const LOOKUP_PAGE = { page: 1, page_size: 100 };

function itemLabel(item, categoryNameById, modelNameById) {
  if (!item) return null;
  const parts = [modelNameById[item.model_id], categoryNameById[item.category_id], item.sku];
  return parts.filter(Boolean).join(' · ') + (item.variant ? ` (${item.variant})` : '');
}

export function SalesOrderDetail({ order }) {
  const { data: partiesData } = useParties(LOOKUP_PAGE);
  const { data: itemsData } = useItems(LOOKUP_PAGE);
  const { data: categoriesData } = useCategories(LOOKUP_PAGE);
  const { data: modelsData } = useModels(LOOKUP_PAGE);

  const customerNameById = Object.fromEntries((partiesData?.items ?? []).map((p) => [p.id, p.name]));
  const itemById = Object.fromEntries((itemsData?.items ?? []).map((i) => [i.id, i]));
  const categoryNameById = Object.fromEntries((categoriesData?.items ?? []).map((c) => [c.id, c.name]));
  const modelNameById = Object.fromEntries((modelsData?.items ?? []).map((m) => [m.id, m.name]));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Sales Order #{order.id}</h2>
          <p className="text-sm text-muted-foreground">
            {customerNameById[order.party_id] ?? `Party #${order.party_id}`} · {order.order_date}
          </p>
        </div>
        <Badge variant={Number(order.total_margin_pkr) >= 0 ? 'secondary' : 'destructive'}>
          Margin <CurrencyAmount value={order.total_margin_pkr} className="ml-1" />
        </Badge>
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead>Item</TableHead>
              <TableHead className="text-right">Qty</TableHead>
              <TableHead className="text-right">Rate (PKR)</TableHead>
              <TableHead className="text-right">Amount (PKR)</TableHead>
              <TableHead className="text-right">Cost (PKR)</TableHead>
              <TableHead className="text-right">Margin (PKR)</TableHead>
              <TableHead>Drawn from</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {order.lines.map((line) => (
              <TableRow key={line.id} className="hover:bg-muted/40">
                <TableCell>
                  {itemLabel(itemById[line.item_id], categoryNameById, modelNameById) ?? `Item #${line.item_id}`}
                </TableCell>
                <TableCell className="text-right">{line.qty}</TableCell>
                <TableCell className="text-right">
                  <CurrencyAmount value={line.rate_pkr} />
                </TableCell>
                <TableCell className="text-right">
                  <CurrencyAmount value={line.amount_pkr} />
                </TableCell>
                <TableCell className="text-right">
                  <CurrencyAmount value={line.cost_pkr} />
                </TableCell>
                <TableCell className="text-right">
                  <CurrencyAmount value={line.margin_pkr} />
                </TableCell>
                <TableCell>
                  <div className="flex flex-col gap-0.5 text-xs text-muted-foreground">
                    {line.consumptions.map((c) => (
                      <span key={c.stock_lot_id}>
                        Lot #{c.stock_lot_id}: {c.qty_consumed} @ <CurrencyAmount value={c.unit_cost_pkr} />
                      </span>
                    ))}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex justify-end gap-6 border-t pt-4 text-sm">
        <span>
          Total: <strong><CurrencyAmount value={order.total_pkr} /></strong>
        </span>
        <span>
          Total margin: <strong><CurrencyAmount value={order.total_margin_pkr} /></strong>
        </span>
      </div>
    </div>
  );
}
```

### 7.4 `components/parties/PartyStatement.jsx` (new)

```jsx
import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { PartyRoleBadges } from '@/components/parties/PartyRoleBadges';

// Sign convention per backend spec §2.6: positive closing_balance means the party
// owes the business (receivable); negative means the business owes the party
// (payable). Surfaced as a label so nobody has to mentally flip the sign.
function balanceLabel(value) {
  const num = Number(value);
  if (num > 0) return 'Owes us';
  if (num < 0) return 'We owe them';
  return 'Settled';
}

export function PartyStatement({ statement }) {
  const { party, opening_balance, entries, closing_balance } = statement;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">{party.name}</h2>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <PartyRoleBadges roles={party.roles} />
            {party.contact && <span className="text-sm text-muted-foreground">{party.contact}</span>}
          </div>
        </div>
        <div className="text-right">
          <Badge variant={Number(closing_balance) >= 0 ? 'secondary' : 'destructive'}>
            {balanceLabel(closing_balance)}
          </Badge>
          <p className="mt-1 text-lg font-semibold text-foreground">
            <CurrencyAmount value={Math.abs(Number(closing_balance))} />
          </p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead>Date</TableHead>
              <TableHead>Account</TableHead>
              <TableHead>Reference</TableHead>
              <TableHead className="text-right">Debit</TableHead>
              <TableHead className="text-right">Credit</TableHead>
              <TableHead className="text-right">Running balance</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow className="bg-muted/30">
              <TableCell colSpan={5} className="font-medium text-foreground">
                Opening balance
              </TableCell>
              <TableCell className="text-right font-medium text-foreground">
                <CurrencyAmount value={opening_balance} />
              </TableCell>
            </TableRow>
            {entries.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                  No ledger activity yet.
                </TableCell>
              </TableRow>
            )}
            {entries.map((entry) => (
              <TableRow key={entry.id} className="hover:bg-muted/40">
                <TableCell>{entry.entry_date}</TableCell>
                <TableCell>{entry.account}</TableCell>
                <TableCell className="text-muted-foreground">
                  {entry.reference_type ? `${entry.reference_type} #${entry.reference_id}` : '—'}
                </TableCell>
                <TableCell className="text-right">
                  {Number(entry.debit) > 0 ? <CurrencyAmount value={entry.debit} /> : '—'}
                </TableCell>
                <TableCell className="text-right">
                  {Number(entry.credit) > 0 ? <CurrencyAmount value={entry.credit} /> : '—'}
                </TableCell>
                <TableCell className="text-right">
                  <CurrencyAmount value={entry.running_balance} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
```

`reference_type`/`reference_id` render as `"sales_order #118"` etc. — raw backend strings, same "display the code, not a friendly label" tradeoff `PurchaseOrderList`'s status badge already accepts for its own raw string, since a lookup table mapping every possible `reference_type` to prose isn't worth building for one column.

---

## 8. Pages / containers

```
pages/SalesOrdersPage.jsx        → containers/SalesOrdersContainer.jsx        (page header + SalesOrderList)
pages/SalesOrderCreatePage.jsx   → containers/SalesOrderCreateContainer.jsx   (page header + Card + SalesOrderForm)
pages/SalesOrderDetailPage.jsx   → containers/SalesOrderDetailContainer.jsx   (:orderId param → SalesOrderDetail)
pages/PartyDetailPage.jsx        → containers/PartyDetailContainer.jsx        (:partyId param → PartyStatement)
```

### 8.1 `containers/SalesOrdersContainer.jsx` (new)

```jsx
import { SalesOrderList } from '@/components/sales/SalesOrderList';

export function SalesOrdersContainer() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Sales Orders</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Invoice a wholesale customer — stock is deducted FIFO and posts straight to their balance.
        </p>
      </div>
      <SalesOrderList />
    </div>
  );
}
```

### 8.2 `containers/SalesOrderCreateContainer.jsx` (new)

```jsx
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { SalesOrderForm } from '@/components/sales/form/SalesOrderForm';

export function SalesOrderCreateContainer() {
  const navigate = useNavigate();

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">New Sales Order</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Pick a customer, add lines with qty and PKR rate — stock is drawn oldest lot first.
        </p>
      </div>
      <Card>
        <CardHeader className="border-b [.border-b]:pb-4">
          <CardTitle className="text-base">Order details</CardTitle>
          <CardDescription>At least one line is required; each item may appear only once.</CardDescription>
        </CardHeader>
        <CardContent>
          <SalesOrderForm onSuccess={(order) => navigate(`/sales-orders/${order.id}`)} />
        </CardContent>
      </Card>
    </div>
  );
}
```

### 8.3 `containers/SalesOrderDetailContainer.jsx` (new)

```jsx
import { useParams, Link } from 'react-router-dom';
import { Loader2, ArrowLeft } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { SalesOrderDetail } from '@/components/sales/SalesOrderDetail';
import { useSalesOrder } from '@/hooks/salesHooks/salesQueries';

export function SalesOrderDetailContainer() {
  const { orderId } = useParams();
  const id = Number(orderId);
  const isValidId = Number.isInteger(id) && id > 0;

  const { data: order, isLoading, isError } = useSalesOrder(isValidId ? id : undefined);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:py-10">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Sales Order</h1>
          <p className="mt-1 text-sm text-muted-foreground">Immutable once created — no edit or void this phase.</p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link to="/sales-orders">
            <ArrowLeft />
            Back to list
          </Link>
        </Button>
      </div>

      <Card>
        <CardContent className="py-6">
          {!isValidId || isError ? (
            <p className="py-10 text-center text-destructive">Sales order not found.</p>
          ) : isLoading ? (
            <div className="flex flex-col items-center justify-center gap-2 py-10 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
              Loading…
            </div>
          ) : (
            <SalesOrderDetail order={order} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

### 8.4 `containers/PartyDetailContainer.jsx` (new)

```jsx
import { useParams, Link } from 'react-router-dom';
import { Loader2, ArrowLeft } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { PartyStatement } from '@/components/parties/PartyStatement';
import { usePartyStatement } from '@/hooks/partyHooks/partyQueries';

export function PartyDetailContainer() {
  const { partyId } = useParams();
  const id = Number(partyId);
  const isValidId = Number.isInteger(id) && id > 0;

  const { data: statement, isLoading, isError } = usePartyStatement(isValidId ? id : undefined);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:py-10">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Party Statement</h1>
          <p className="mt-1 text-sm text-muted-foreground">Full ledger history and running balance for one party.</p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link to="/parties">
            <ArrowLeft />
            Back to parties
          </Link>
        </Button>
      </div>

      <Card>
        <CardContent className="py-6">
          {!isValidId || isError ? (
            <p className="py-10 text-center text-destructive">Party not found.</p>
          ) : isLoading ? (
            <div className="flex flex-col items-center justify-center gap-2 py-10 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
              Loading…
            </div>
          ) : (
            <PartyStatement statement={statement} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

### 8.5 The four page files — same two-line shape every prior page follows

```jsx
// pages/SalesOrdersPage.jsx
import { SalesOrdersContainer } from '@/containers/SalesOrdersContainer';
export function SalesOrdersPage() {
  return <SalesOrdersContainer />;
}
```
```jsx
// pages/SalesOrderCreatePage.jsx
import { SalesOrderCreateContainer } from '@/containers/SalesOrderCreateContainer';
export function SalesOrderCreatePage() {
  return <SalesOrderCreateContainer />;
}
```
```jsx
// pages/SalesOrderDetailPage.jsx
import { SalesOrderDetailContainer } from '@/containers/SalesOrderDetailContainer';
export function SalesOrderDetailPage() {
  return <SalesOrderDetailContainer />;
}
```
```jsx
// pages/PartyDetailPage.jsx
import { PartyDetailContainer } from '@/containers/PartyDetailContainer';
export function PartyDetailPage() {
  return <PartyDetailContainer />;
}
```

---

## 9. App shell updates

### 9.1 `App.jsx` — new routes

```jsx
<Route element={<ProtectedRoute />}>
  <Route path="/settings" element={<SettingsPage />} />
  <Route path="/catalog" element={<CatalogPage />} />
  <Route path="/parties" element={<PartiesPage />} />
  <Route path="/parties/:partyId" element={<PartyDetailPage />} />                 {/* new */}
  <Route path="/purchase-orders" element={<PurchaseOrdersPage />} />
  <Route path="/purchase-orders/new" element={<PurchaseOrderCreatePage />} />
  <Route path="/purchase-orders/:orderId" element={<PurchaseOrderDetailPage />} />
  <Route path="/cargo-shipments" element={<CargoShipmentsPage />} />
  <Route path="/cargo-shipments/new" element={<CargoShipmentCreatePage />} />
  <Route path="/cargo-shipments/:shipmentId" element={<CargoShipmentDetailPage />} />
  <Route path="/inventory" element={<InventoryPage />} />
  <Route path="/sales-orders" element={<SalesOrdersPage />} />                     {/* new */}
  <Route path="/sales-orders/new" element={<SalesOrderCreatePage />} />            {/* new */}
  <Route path="/sales-orders/:orderId" element={<SalesOrderDetailPage />} />       {/* new */}
  <Route path="/" element={<Navigate to="/purchase-orders" replace />} />
</Route>
```

Default landing route stays `/purchase-orders` — not re-litigated here, same reasoning the phase-2/3 specs already carried forward: placing stock orders remains the most frequent action, ahead of both checking inventory and invoicing a sale, for this business at its current scale.

### 9.2 `Navbar.jsx` — `NAV_LINKS`

Inserted right after "Inventory," matching the business's actual pipeline order (purchase → ship → receive/hold in stock → **sell** → parties/catalog are supporting master data):

```javascript
const NAV_LINKS = [
  { to: '/purchase-orders', label: 'Purchase Orders' },
  { to: '/cargo-shipments', label: 'Cargo Shipments' },
  { to: '/inventory', label: 'Inventory' },
  { to: '/sales-orders', label: 'Sales Orders' },
  { to: '/parties', label: 'Parties' },
  { to: '/catalog', label: 'Catalog' },
  { to: '/settings', label: 'Settings' },
];
```

Seven links now fit the same collapsing hamburger pattern Phase 0 built and Phases 1–3 already stretched to six — verify the mobile menu still opens/closes cleanly with seven entries plus sign-out, at ~375px, per CLAUDE.md §3.7.

---

## 10. Testing checklist (manual, matches PLAN.md's "done when")

1. On `/parties`, add a new party with the **Customer** role (name, contact optional, `opening_balance` left at 0) — confirm it appears in the list and its name is now a link.
2. Build a sellable lot: run Phase 1's PO flow → Phase 2's cargo-shipment flow → Phase 3's Receive action, ending with at least one `StockLot` with `qty_remaining > 0` for some item.
3. Go to `/sales-orders/new` — confirm the customer dropdown lists only the party added in step 1 (not any `china_vendor`/`cargo_agent`-only parties), and the item picker's "In stock" hint shows the correct remaining qty for the item received in step 2 once selected.
4. Add a second line for the **same item** already used on line 1 — confirm the inline Yup error ("Each item may appear at most once…") fires before any request goes out; remove the duplicate line.
5. Submit a valid order (qty at or under the shown "In stock" figure) — confirm it redirects to `/sales-orders/{id}` showing the item, qty, rate, amount, cost, margin, and at least one "Lot #… : qty @ rate" entry under "Drawn from."
6. Immediately check `/inventory` — confirm the sold item's lot(s) show reduced `qty_remaining`/`value_remaining_pkr` with no manual refresh needed (query invalidation working end-to-end).
7. Immediately check `/parties/{customerId}` — confirm a new "Accounts Receivable" row appears in the statement table with the order's `total_pkr` as its debit, the running balance reflects it, and the header balance badge now reads "Owes us" with that amount.
8. Attempt to sell more of an item than is currently in stock — confirm the backend's 422 ("need X, only Y in stock") surfaces as a toast and the form stays open with the entered values intact.
9. Attempt to create a sales order against a party that does **not** hold the `customer` role by hitting the endpoint directly (or temporarily removing the role) — confirm the role-mismatch error toasts cleanly.
10. On `/sales-orders`, confirm the new order appears with correct customer name, order date, total PKR, and margin PKR; open it again from the list link and confirm the detail matches.
11. Open a `PartyStatement` for a party with **zero** ledger activity (a freshly created customer with `opening_balance = 0`) — confirm it renders "No ledger activity yet," an opening balance row of ₨0.00, and a "Settled" badge rather than erroring.
12. Resize to ~375px, ~768px, ~1280px: `Navbar` still collapses correctly with 7 links + sign-out; `SalesOrderForm`'s line grid stacks to one column below `md`; `SalesOrderList`/`SalesOrderDetail`/`PartyStatement` tables all scroll inside their own `overflow-x-auto` container rather than widening the page body.
