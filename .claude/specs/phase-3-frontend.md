# Phase 3 Frontend — Spec

Source of truth: `PLAN.md` (§ Phase 3 — Inventory / warehouse) for *what*, `CLAUDE.md` (§3) for *how*, `.claude/skills/frontend-design-system/SKILL.md` for *how it should look*, and `.claude/specs/phase-3-backend.md` for the backend design — but the API surface below (§1.1) is re-verified against the **actual running `backend/src/inventory/` and `backend/src/purchasing/` code**, not the design doc, exactly like the phase-1 and phase-2 frontend specs did for their phases. Where this doc and the backend spec draft disagree, trust §1.1.

**Done when** (verbatim from PLAN.md): for any model, you can see exactly how many units you hold, split by which lot they came in on and at what cost.

At the time of writing, `frontend/` already has Phases 0–2 shipped in full — auth, the generic `CrudTable`/`CrudDrawer` engine, `ExchangeRate`/`PaymentMethod`/`CargoMode`/`CargoCostBasis` lookups on `/settings`, full `Category`/`Model`/`Item`/`Party` CRUD, hand-written `PurchaseOrder` list/create/detail screens (including the `landed_cost_pkr`/`amount_landed_pkr` columns Phase 2 added — `components/purchasing/PurchaseOrderDetail.jsx:50-51,73-78`), and hand-written `CargoShipment` list/create/detail screens. This spec is additive on top of that tree — nothing in the prior specs' scope gets removed or renamed.

---

## 1. Scope

Build, in this order (each step independently usable/testable before the next):

1. `utils/queryParams.js` — widen `buildQueryString` to pass through arbitrary filter params, not just `page`/`page_size`. Required before anything else in this phase: it's the first domain whose list endpoints take real filters (`item_id`, `include_depleted`, `stock_lot_id`) rather than just pagination.
2. `utils/queryKeys.js` gets `stockLotKeys`/`stockMovementKeys`.
3. `services/inventoryService.js`, `hooks/inventoryHooks/inventoryQueries.js`, `hooks/inventoryHooks/inventoryMutations.js`, `validations/inventorySchemas.js` — the new domain's full data-access stack, mirroring `cargoService.js`/`cargoHooks/`'s shape.
4. `components/purchasing/PurchaseOrderDetail.jsx` gets one new column, **Receive** — a per-line action that turns a landed-cost line into a `StockLot`. Confirmed with user: this lives on the existing PO detail page, not a new cross-PO receivable-lines queue (§2, decision 1).
5. `components/inventory/ReceiveStockLotDialog.jsx` — the dialog `PurchaseOrderDetail`'s new Receive button opens.
6. `components/inventory/StockLotTable.jsx` + `components/inventory/StockAdjustmentDialog.jsx` + `components/inventory/form/StockAdjustmentForm.jsx` — the stock-on-hand view and its manual-adjustment action, per CLAUDE.md §3.3's named files for this domain.
7. Pages/containers: `pages/InventoryPage.jsx` → `containers/InventoryContainer.jsx`.
8. App shell — new `/inventory` route in `App.jsx`, new nav link in `Navbar.jsx`. Default landing route (`/purchase-orders`) is unchanged — same reasoning as the phase-2 spec's decision 4, not re-litigated here.

Out of scope, deferred per PLAN.md's roadmap or this phase's own backend spec (§9 there): FIFO stock **consumption** (Phase 4, when a sale draws down a lot), a party-facing view of inventory value, any `sales/`/`payments`/`expenses`/`reporting` work. Also out of scope this phase specifically (§8 below): a dedicated stock-movement audit-trail screen, a bulk "receive every line on this PO" action, and any un-receive/undo UI — none of these have a backing endpoint (backend spec §9), so there is nothing for the frontend to call.

### 1.1 Confirmed API surface (from running backend code, not the design draft)

Every route below requires `Authorization: Bearer <access_token>`, same as every route in Phases 0–2. Error bodies are the same dual shape `fetchClient.js` already handles: `{"detail": "..."}` for a domain `AppException`, `{"detail": [{"loc":..., "msg":...}]}` for a raw Pydantic validation failure.

**Every `Decimal` field is still a JSON string** (unchanged global gotcha): `qty_received`, `qty_remaining`, `landed_cost_pkr`, `value_remaining_pkr`, `qty_delta` all serialize as strings (e.g. `"12.00"`). Send back exactly what the form collected — never `Number()`-cast before it goes into a request body.

| Method | Path | Body / Query | Response | Status | Notes |
|---|---|---|---|---|---|
| POST | `/inventory/stock-lots` | `{purchase_order_line_id, received_date}` | `StockLotRead` | 201 / 404 / 409 / 422 | **this *is* the Receive action** |
| GET | `/inventory/stock-lots?page=&page_size=&item_id=&include_depleted=` | — | `{items:[StockLotRead], total, page, page_size}` | 200 | `item_id` and `include_depleted` are plain query params, not a pagination sub-model — verified in `backend/src/inventory/router.py:32-45`, which switches `PaginationParams` from `Query()` to `Depends()` specifically so these two params can sit alongside it (a FastAPI 0.141.1 quirk documented in-code) |
| GET | `/inventory/stock-lots/{id}` | — | `StockLotRead` | 200 / 404 | |
| POST | `/inventory/stock-movements` | `{stock_lot_id, qty_delta, reason, movement_date}` | `StockMovementRead` | 201 / 404 / 422 / 409 | the manual adjustment action |
| GET | `/inventory/stock-movements?page=&page_size=&stock_lot_id=` | — | `{items:[StockMovementRead], total, page, page_size}` | 200 | not called by any screen this phase (§8) |

`StockLotRead`: `{id, purchase_order_line_id, item_id, qty_received, qty_remaining, landed_cost_pkr, received_date, value_remaining_pkr}` — `value_remaining_pkr` is a `@computed_field` (`qty_remaining × landed_cost_pkr`, server-rounded), **use it directly, don't recompute it client-side**, same rule as `PurchaseOrderLineRead.amount_pkr`.

`StockMovementRead`: `{id, stock_lot_id, movement_type: "receipt"|"adjustment", qty_delta, reason, movement_date, created_at}`.

**No `PUT`/`DELETE` on either resource, and no partial receiving.** `StockLotReceiveCreate` takes only `purchase_order_line_id` + `received_date` — the received quantity is always the line's full `qty`, never user-entered (backend spec §2.3). There is no way to receive "half a line," and no way to un-receive one.

**Receive error cases, in the order the backend checks them** (`backend/src/inventory/service.py:26-35`):

| Cause | Status | Detail |
|---|---|---|
| `purchase_order_line_id` doesn't resolve to a line | 404 | "Purchase order line not found" |
| that line's `landed_cost_pkr` is still `null` (never went through a cargo shipment) | 422 | "This line has no landed cost yet — attach it to a cargo shipment before receiving" |
| a `StockLot` already exists for this line | 409 | "This purchase order line has already been received into a stock lot" |

**Adjustment error cases** (`backend/src/inventory/service.py:90-101`):

| Cause | Status | Detail |
|---|---|---|
| `stock_lot_id` doesn't resolve to a lot | 404 | "Stock lot not found" |
| `qty_delta == 0` | 422 | "Adjustment quantity must be non-zero" |
| `qty_remaining + qty_delta` falls outside `[0, qty_received]` | 422 | names the resulting value and the valid range |

**Receiving a line has two side effects beyond creating the lot, both worth invalidating for** (`service.py:58-78`): it posts a `LedgerEntry` (not surfaced anywhere in this frontend phase — no ledger screen exists yet) and, once every line on the parent PO has a lot, flips `PurchaseOrder.status` to `"received"`. **`PurchaseOrder.status` now has three values, `"draft" | "allocated" | "received"`, not just two.** Every screen rendering `order.status` as a bare string badge (`PurchaseOrderList.jsx:97`, `PurchaseOrderDetail.jsx:37`) already handles this correctly with zero changes.

**No `?purchase_order_line_id=` filter exists on `GET /inventory/stock-lots`** — only `item_id` and `include_depleted`. Determining "which lines on this PO are already received" is therefore a client-side derivation (§5.1), the same client-side-filter pattern Phase 1/2 already established for `useChinaVendorParties`/`useDraftPurchaseOrders`/`useCargoAgentParties`: fetch one `page_size=100` page and filter/index it in memory. Same accepted limitation carried forward: past 100 stock lots total, a just-received line could stop showing as "Received" until an older lot ages out of that page. Revisit if this business ever holds more than 100 concurrent lots — not expected at this stage.

---

## 2. Decisions (confirmed with user)

1. **The Receive action lives as a per-line button on the existing `PurchaseOrderDetail` page — not a new cross-PO "receivable lines" queue screen.** Confirmed with user (two options were presented: a `PurchaseOrderDetail` button vs. a dedicated `/inventory/receive` queue page). This is also what the backend spec itself suggests (§6.2 there): "the frontend's Receive screen reconciles `GET /purchasing/purchase-orders` ... against `GET /inventory/stock-lots`" — ordinary container-level composition on a page that already has the PO's lines and their `landed_cost_pkr` loaded, not a new page. It also matches CLAUDE.md §3.2's given frontend tree, which names `InventoryPage.jsx` for the stock view and nothing else for inventory.
2. **The stock view (`StockLotTable`) fetches one `page_size=100` page per render, not a paginated `PaginationControls` list.** Grouping by Model → Item (PLAN.md's own wording for this phase's "done when") requires the *whole* result set in memory at once — paginating the underlying list would silently split a model's lots across pages and break the grouping. Same accepted-limitation shape as `useDraftPurchaseOrders`/`useCargoAgentParties`: fine at this business's scale, revisit (server-side grouping, or a real "on-hand by model" endpoint — backend spec §9 flags this as a possible future addition) if lot count ever approaches 100.
3. **`StockAdjustmentDialog` is a `Dialog`, not a `Sheet`, even though it wraps a form.** This looks like it contradicts the design skill's "`Sheet` for add/edit, `Dialog` for confirmations" rule (`frontend-design-system/SKILL.md` §"Dialogs") — but that rule describes the generic `CrudDrawer`/`ConfirmDialog` pair for entity CRUD. A stock adjustment isn't editing a `StockLot` entity (its own fields — `qty_received`, `landed_cost_pkr`, `received_date` — are immutable); it's a one-off transactional action *about* an existing lot, the same category of thing as `PurchaseOrderDetail`'s new Receive button. CLAUDE.md §3.3 itself already names this exact file `StockAdjustmentDialog.jsx`, not `StockAdjustmentSheet.jsx` — followed literally here rather than reopened.
4. **No dedicated stock-movement history screen this phase.** `GET /inventory/stock-movements` is wired in `inventoryQueries.js` (§4.2) so it exists for a future phase to use, but nothing renders it yet — PLAN.md's own wording for this phase asks for a "manual adjustment screen," not an audit-trail view. Revisit once a phase needs to show "why did this lot's quantity change over time" (most naturally alongside the Phase 8 analytics work, or sooner if the business wants it).

---

## 3. Generic CRUD engine

No changes. `StockLot`/`StockMovement` are transactional, hand-written entities — like `PurchaseOrder`/`CargoShipment`, they carry cross-table validation (a receive checks the line's allocation state and uniqueness; an adjustment checks bounds against the lot's own quantities) and, for `StockLot`, a ledger post, exactly the case `PLAN.md`'s own rule reserves for hand-written services rather than the generic factory. Neither backend model even has the `is_active` column the generic factory asserts on.

---

## 4. Shared utility changes

### 4.1 `utils/queryParams.js` — `buildQueryString` widens to pass through filters

Every prior domain's list endpoint took only `page`/`page_size` (verified: `catalogService.js`, `partyService.js`, `purchasingService.js`, `cargoService.js` all call `buildQueryString(params)` with a plain `{page, page_size}` object). This phase's `GET /inventory/stock-lots` is the first endpoint with real filters (`item_id`, `include_depleted`), and `GET /inventory/stock-movements` has one too (`stock_lot_id`) — so `buildQueryString` needs to carry arbitrary extra params through, not just the two it knows about today.

```javascript
// utils/queryParams.js — changed
const DEFAULT_PAGE = 1;
const DEFAULT_PAGE_SIZE = 20;
const MIN_PAGE_SIZE = 1;
const MAX_PAGE_SIZE = 100;

export function buildQueryString({ page = DEFAULT_PAGE, page_size = DEFAULT_PAGE_SIZE, ...filters } = {}) {
  const clampedPage = Math.max(1, page);
  const clampedPageSize = Math.min(MAX_PAGE_SIZE, Math.max(MIN_PAGE_SIZE, page_size));

  const params = new URLSearchParams({
    page: String(clampedPage),
    page_size: String(clampedPageSize),
  });

  // Any other truthy/defined filter (item_id, include_depleted, stock_lot_id, and
  // whatever a later domain's list endpoint needs) rides along unchanged — omit
  // null/undefined/empty-string so an unset filter never becomes a literal
  // "?item_id=undefined" in the URL.
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value));
    }
  });

  return `?${params.toString()}`;
}
```

Backward compatible: every existing call site passes only `{page, page_size}`, so `filters` is always `{}` for them and the output string is byte-for-byte unchanged. No other service file needs to change because of this edit.

### 4.2 `utils/queryKeys.js` additions

```javascript
export const stockLotKeys = {
  all: ['stockLots'],
  lists: () => [...stockLotKeys.all, 'list'],
  list: (params) => [...stockLotKeys.lists(), params],
  detail: (id) => [...stockLotKeys.all, 'detail', id],
};

export const stockMovementKeys = {
  all: ['stockMovements'],
  lists: () => [...stockMovementKeys.all, 'list'],
  list: (params) => [...stockMovementKeys.lists(), params],
};
```

---

## 5. Inventory domain — data access

### 5.1 `services/inventoryService.js` (new) — mirrors `cargoService.js`'s shape

```javascript
import { fetchClient } from '@/middleware/fetchClient';
import { buildQueryString } from '@/utils/queryParams';

export async function listStockLots({ page, page_size, item_id, include_depleted } = {}) {
  const qs = buildQueryString({ page, page_size, item_id, include_depleted: include_depleted || undefined });
  const { data } = await fetchClient.get(`/inventory/stock-lots${qs}`);
  return data;
}

export async function getStockLot(id) {
  const { data } = await fetchClient.get(`/inventory/stock-lots/${id}`);
  return data;
}

export async function receiveStockLot(payload) {
  const { data } = await fetchClient.post('/inventory/stock-lots', payload);
  return data;
}

export async function listStockMovements({ page, page_size, stock_lot_id } = {}) {
  const qs = buildQueryString({ page, page_size, stock_lot_id });
  const { data } = await fetchClient.get(`/inventory/stock-movements${qs}`);
  return data;
}

export async function createStockMovement(payload) {
  const { data } = await fetchClient.post('/inventory/stock-movements', payload);
  return data;
}
```

`include_depleted: include_depleted || undefined` keeps the default (`false`/unset) request URL clean — `buildQueryString` already drops `undefined`, so a `false` toggle produces `?page=1&page_size=100` with no `include_depleted` at all, same as never having sent it (the backend's own default is `False`).

### 5.2 `hooks/inventoryHooks/inventoryQueries.js` (new)

```javascript
import { useQuery } from '@tanstack/react-query';
import { stockLotKeys, stockMovementKeys } from '@/utils/queryKeys';
import { listStockLots, getStockLot, listStockMovements } from '@/services/inventoryService';

export function useStockLots(params) {
  return useQuery({ queryKey: stockLotKeys.list(params), queryFn: () => listStockLots(params) });
}

export function useStockLot(id) {
  return useQuery({
    queryKey: stockLotKeys.detail(id),
    queryFn: () => getStockLot(id),
    enabled: Boolean(id),
  });
}

export function useStockMovements(params) {
  return useQuery({ queryKey: stockMovementKeys.list(params), queryFn: () => listStockMovements(params) });
}

// Derived, not a separate backend call — no ?purchase_order_line_id= filter exists on
// GET /inventory/stock-lots (§1.1), so this fetches every lot and returns the set of
// already-received line ids, for PurchaseOrderDetail's per-line Receive button (§6).
//
// include_depleted: true is not optional here — a lot fully consumed by a future
// Phase 4 sale must still count as "this line was received." Dropping this flag would
// make an already-received line's Receive button silently reappear once its lot hits
// zero, which is wrong: receipt state is "does a lot exist," never "is it non-empty"
// (backend spec §2.1).
export function useReceivedLineIds() {
  const query = useStockLots({ page: 1, page_size: 100, include_depleted: true });
  const ids = new Set((query.data?.items ?? []).map((lot) => lot.purchase_order_line_id));
  return { ...query, ids };
}
```

### 5.3 `hooks/inventoryHooks/inventoryMutations.js` (new)

```javascript
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { stockLotKeys, stockMovementKeys, purchaseOrderKeys } from '@/utils/queryKeys';
import * as inventoryService from '@/services/inventoryService';

export function useReceiveStockLot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: inventoryService.receiveStockLot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: stockLotKeys.lists() });
      // A receive can flip the parent PO's status to "received" once its last line
      // lands (§1.1) — invalidate the whole purchaseOrders key space (lists + every
      // cached detail) so an open PurchaseOrderDetail tab picks this up, same
      // reasoning as the phase-2 spec's cargo-shipment-create invalidation.
      queryClient.invalidateQueries({ queryKey: purchaseOrderKeys.all });
    },
  });
}

export function useCreateStockMovement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: inventoryService.createStockMovement,
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: stockLotKeys.lists() });
      queryClient.invalidateQueries({ queryKey: stockLotKeys.detail(variables.stock_lot_id) });
      queryClient.invalidateQueries({ queryKey: stockMovementKeys.lists() });
    },
  });
}
```

### 5.4 `validations/inventorySchemas.js` (new)

```javascript
import { object, string, number } from 'yup';

export const stockLotReceiveSchema = object({
  received_date: string().required('Received date is required'),
});

// A factory, not a static schema — the valid qty_delta range depends on the specific
// lot's qty_remaining/qty_received, which StockAdjustmentForm already has as a prop
// (unlike CargoShipmentForm's basis-value rule, which needed a value from a query
// cache the form couldn't see — phase-2-frontend spec §2 decision 6 — this rule has
// everything it needs right on the component, so it's expressed as Yup, not a
// computed disabled boolean).
export function buildStockAdjustmentSchema(lot) {
  return object({
    qty_delta: number()
      .typeError('Enter a number')
      .required('Enter a quantity change')
      .notOneOf([0], 'Adjustment quantity must be non-zero')
      .test('within-bounds', `Resulting quantity must stay between 0 and ${lot.qty_received}`, (value) => {
        if (value == null) return true; // required() already reports the empty case
        const resultingQty = Number(lot.qty_remaining) + value;
        return resultingQty >= 0 && resultingQty <= Number(lot.qty_received);
      }),
    reason: string().required('Reason is required').max(255, 'Max 255 characters'),
    movement_date: string().required('Movement date is required'),
  });
}
```

`purchase_order_line_id` isn't in `stockLotReceiveSchema` — it's supplied by the component from the `line` it already has in scope, not typed by the user, so there's nothing for Yup to validate there (same reasoning `CrudDrawer`/`CargoShipmentForm` already apply to any id the component derives rather than collects).

---

## 6. Purchasing domain change — `PurchaseOrderDetail.jsx` gets a Receive column

One column added after the existing "Amount landed" column (`components/purchasing/PurchaseOrderDetail.jsx:50-51,73-78`), plus local dialog state:

```jsx
// components/purchasing/PurchaseOrderDetail.jsx — changed
import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { CheckCircle2 } from 'lucide-react';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { ReceiveStockLotDialog } from '@/components/inventory/ReceiveStockLotDialog';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { useCategories } from '@/hooks/catalogHooks/categoryQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';
import { useReceivedLineIds } from '@/hooks/inventoryHooks/inventoryQueries';

// ...inside PurchaseOrderDetail({ order }):
const { ids: receivedLineIds } = useReceivedLineIds();
const [receivingLine, setReceivingLine] = useState(null);
```

```jsx
<TableHead>Landed cost/unit</TableHead>
<TableHead className="text-right">Amount landed</TableHead>
<TableHead>Receive</TableHead>   {/* new */}
```

```jsx
<TableCell>
  {line.landed_cost_pkr == null ? (
    '—'
  ) : receivedLineIds.has(line.id) ? (
    <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
      <CheckCircle2 className="size-4 text-primary" />
      Received
    </span>
  ) : (
    <Button size="sm" variant="outline" onClick={() => setReceivingLine(line)}>
      Receive
    </Button>
  )}
</TableCell>
```

And, after the closing `</div>` of the component's outer wrapper:

```jsx
{receivingLine && (
  <ReceiveStockLotDialog
    open={Boolean(receivingLine)}
    onOpenChange={(open) => !open && setReceivingLine(null)}
    line={receivingLine}
    itemLabel={itemLabel(itemById[receivingLine.item_id], categoryNameById, modelNameById) ?? `Item #${receivingLine.item_id}`}
  />
)}
```

`itemLabel(...)` is the helper already defined at the top of this file (`PurchaseOrderDetail.jsx:11-15`) — reused as-is, not duplicated. No changes needed to `PurchaseOrderList.jsx` — its `status` badge already renders whatever string the backend returns; `"received"` displays with zero code changes, same as Phase 2's note for `"allocated"`.

---

## 7. Inventory domain — components

### 7.1 `components/inventory/ReceiveStockLotDialog.jsx` (new)

A `Dialog` (not a `Sheet` — same "one-off transactional action" reasoning as §2 decision 3) with a single date field, defaulting to today:

```jsx
import { useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { FormField } from '@/components/custom';
import { stockLotReceiveSchema } from '@/validations/inventorySchemas';
import { useReceiveStockLot } from '@/hooks/inventoryHooks/inventoryMutations';

const todayIso = () => new Date().toISOString().slice(0, 10);

export function ReceiveStockLotDialog({ open, onOpenChange, line, itemLabel }) {
  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(stockLotReceiveSchema, {}, { raw: true }),
    defaultValues: { received_date: todayIso() },
  });
  const receiveMutation = useReceiveStockLot();

  useEffect(() => {
    if (open) reset({ received_date: todayIso() });
  }, [open, reset]);

  const onSubmit = async (values) => {
    try {
      await receiveMutation.mutateAsync({ purchase_order_line_id: line.id, received_date: values.received_date });
      onOpenChange(false);
    } catch {
      // fetchClient already toasted the backend's error detail (not yet allocated,
      // or already received by a second tab — §1.1) — keep the dialog open so the
      // user can see it and cancel or retry.
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Receive into stock</DialogTitle>
          <DialogDescription>
            {itemLabel} · qty {line.qty} — creates one stock lot for the full line quantity at its landed cost.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <Controller
            name="received_date"
            control={control}
            render={({ field }) => (
              <FormField {...field} type="date" label="Received date" error={errors.received_date?.message} />
            )}
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Receiving…' : 'Receive'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

No separate `form/` file for this one — it's a single field, the same scale as `ConfirmDialog` (which also has no `form/` subfile) rather than a multi-field domain form.

### 7.2 `components/inventory/form/StockAdjustmentForm.jsx` (new)

```jsx
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { DialogFooter, DialogClose } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { FormField } from '@/components/custom';
import { buildStockAdjustmentSchema } from '@/validations/inventorySchemas';
import { useCreateStockMovement } from '@/hooks/inventoryHooks/inventoryMutations';

const todayIso = () => new Date().toISOString().slice(0, 10);

export function StockAdjustmentForm({ lot, onSuccess }) {
  const schema = buildStockAdjustmentSchema(lot);
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(schema, {}, { raw: true }),
    defaultValues: { qty_delta: '', reason: '', movement_date: todayIso() },
  });
  const createMutation = useCreateStockMovement();

  const onSubmit = async (values) => {
    try {
      await createMutation.mutateAsync({ stock_lot_id: lot.id, ...values });
      onSuccess?.();
    } catch {
      // fetchClient already toasted the backend's error detail (out-of-range
      // adjustment — §1.1) — keep the form open to fix and retry.
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <Controller
        name="qty_delta"
        control={control}
        render={({ field }) => (
          <FormField
            {...field}
            type="number"
            step="0.01"
            label="Quantity change"
            placeholder="e.g. -2 for damage, +3 for a recount"
            error={errors.qty_delta?.message}
          />
        )}
      />
      <Controller
        name="reason"
        control={control}
        render={({ field }) => (
          <FormField {...field} label="Reason" placeholder="Damaged in storage, recount, …" error={errors.reason?.message} />
        )}
      />
      <Controller
        name="movement_date"
        control={control}
        render={({ field }) => (
          <FormField {...field} type="date" label="Movement date" error={errors.movement_date?.message} />
        )}
      />
      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline">
            Cancel
          </Button>
        </DialogClose>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Saving…' : 'Save adjustment'}
        </Button>
      </DialogFooter>
    </form>
  );
}
```

`DialogClose asChild` is used for Cancel here (rather than a passed-down `onOpenChange`, as `ReceiveStockLotDialog` uses) because this form is a separate component nested inside `StockAdjustmentDialog`'s `Dialog` tree — `DialogClose` reads the ancestor `Dialog`'s context directly, so no prop threading is needed for the cancel path.

### 7.3 `components/inventory/StockAdjustmentDialog.jsx` (new)

```jsx
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { StockAdjustmentForm } from '@/components/inventory/form/StockAdjustmentForm';

export function StockAdjustmentDialog({ open, onOpenChange, lot }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Adjust stock lot #{lot.id}</DialogTitle>
          <DialogDescription>
            Recount, damage, or loss — currently {lot.qty_remaining} of {lot.qty_received} remaining.
          </DialogDescription>
        </DialogHeader>
        <StockAdjustmentForm lot={lot} onSuccess={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}
```

### 7.4 `components/inventory/StockLotTable.jsx` (new) — the centerpiece of Phase 3

Groups the flat `GET /inventory/stock-lots` response by `Model → Item` client-side (§2 decision 2), preserving the backend's own `(item_id, received_date, id)` ordering (`backend/src/inventory/service.py:141` — oldest lot first per item) so old and new stock render adjacent, exactly PLAN.md's wording:

```jsx
import { Fragment, useState } from 'react';
import { Loader2, Inbox, Boxes, SlidersHorizontal } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { StockAdjustmentDialog } from '@/components/inventory/StockAdjustmentDialog';
import { useStockLots } from '@/hooks/inventoryHooks/inventoryQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';
import { useCategories } from '@/hooks/catalogHooks/categoryQueries';

const LOOKUP_PAGE = { page: 1, page_size: 100 };

function itemSubLabel(item, categoryNameById) {
  if (!item) return null;
  const parts = [categoryNameById[item.category_id], item.sku].filter(Boolean);
  return parts.join(' · ') + (item.variant ? ` (${item.variant})` : '');
}

export function StockLotTable() {
  const [includeDepleted, setIncludeDepleted] = useState(false);
  const [adjustingLot, setAdjustingLot] = useState(null);

  // page_size=100, unpaginated in the UI, on purpose — grouping by model needs the
  // whole set at once (§2 decision 2). Not the same accepted-limitation shape as a
  // one-off client-side filter elsewhere: past 100 total lots this view starts
  // silently dropping the newest ones rather than just missing a filter match.
  const { data, isLoading, isError } = useStockLots({ page: 1, page_size: 100, include_depleted: includeDepleted });
  const { data: itemsData } = useItems(LOOKUP_PAGE);
  const { data: modelsData } = useModels(LOOKUP_PAGE);
  const { data: categoriesData } = useCategories(LOOKUP_PAGE);

  const itemById = Object.fromEntries((itemsData?.items ?? []).map((i) => [i.id, i]));
  const modelNameById = Object.fromEntries((modelsData?.items ?? []).map((m) => [m.id, m.name]));
  const categoryNameById = Object.fromEntries((categoriesData?.items ?? []).map((c) => [c.id, c.name]));
  const lots = data?.items ?? [];

  const groupIndex = new Map();
  const groups = [];
  for (const lot of lots) {
    const item = itemById[lot.item_id];
    const modelId = item?.model_id ?? 'unknown';
    const key = `${modelId}:${lot.item_id}`;
    if (!groupIndex.has(key)) {
      groupIndex.set(key, groups.length);
      groups.push({ modelId, itemId: lot.item_id, item, lots: [] });
    }
    groups[groupIndex.get(key)].lots.push(lot);
  }
  groups.sort((a, b) => (modelNameById[a.modelId] ?? '').localeCompare(modelNameById[b.modelId] ?? ''));

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-4">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Boxes className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Inventory</CardTitle>
            <CardDescription>Stock on hand, model by model — every lot at the rate it landed.</CardDescription>
          </div>
        </div>
        <CardAction>
          <label className="flex items-center gap-2 text-sm font-normal text-muted-foreground">
            <Checkbox checked={includeDepleted} onCheckedChange={setIncludeDepleted} />
            Show depleted lots
          </label>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>Received</TableHead>
                <TableHead className="text-right">Qty received</TableHead>
                <TableHead className="text-right">Qty remaining</TableHead>
                <TableHead className="text-right">Landed cost/unit</TableHead>
                <TableHead className="text-right">Value remaining</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && groups.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No stock received yet — receive a purchase order line from its detail page.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {!isLoading &&
                !isError &&
                groups.map((group) => (
                  <Fragment key={`${group.modelId}:${group.itemId}`}>
                    <TableRow className="bg-muted/30">
                      <TableCell colSpan={4} className="font-medium text-foreground">
                        {modelNameById[group.modelId] ?? `Model #${group.modelId}`}
                        {itemSubLabel(group.item, categoryNameById) && (
                          <span className="ml-2 font-normal text-muted-foreground">
                            {itemSubLabel(group.item, categoryNameById)}
                          </span>
                        )}
                      </TableCell>
                      <TableCell colSpan={2} className="text-right font-medium text-foreground">
                        {group.lots.reduce((sum, lot) => sum + Number(lot.qty_remaining), 0)} on hand
                      </TableCell>
                    </TableRow>
                    {group.lots.map((lot) => (
                      <TableRow key={lot.id} className="hover:bg-muted/40">
                        <TableCell>{lot.received_date}</TableCell>
                        <TableCell className="text-right">{lot.qty_received}</TableCell>
                        <TableCell className="text-right">{lot.qty_remaining}</TableCell>
                        <TableCell className="text-right">
                          <CurrencyAmount value={lot.landed_cost_pkr} />
                        </TableCell>
                        <TableCell className="text-right">
                          <CurrencyAmount value={lot.value_remaining_pkr} />
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label={`Adjust stock lot #${lot.id}`}
                            onClick={() => setAdjustingLot(lot)}
                          >
                            <SlidersHorizontal />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </Fragment>
                ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>

      {adjustingLot && (
        <StockAdjustmentDialog
          open={Boolean(adjustingLot)}
          onOpenChange={(open) => !open && setAdjustingLot(null)}
          lot={adjustingLot}
        />
      )}
    </Card>
  );
}
```

The "on hand" total per group is a plain `Number()` sum for display only — never sent back to the server, same reasoning `CargoShipmentForm`'s live allocation preview already applies to its own client-side arithmetic (phase-2-frontend spec §8.1). Group rows use `colSpan` the same way `PurchaseOrderList`'s loading/error/empty rows already do, not a new pattern.

---

## 8. Pages / containers

```
pages/InventoryPage.jsx        → containers/InventoryContainer.jsx    (page header + StockLotTable)
```

```jsx
// containers/InventoryContainer.jsx
import { StockLotTable } from '@/components/inventory/StockLotTable';

export function InventoryContainer() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Inventory</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Stock on hand, lot by lot — receive a line from its purchase order to add to this view.
        </p>
      </div>
      <StockLotTable />
    </div>
  );
}
```

```jsx
// pages/InventoryPage.jsx
import { InventoryContainer } from '@/containers/InventoryContainer';

export function InventoryPage() {
  return <InventoryContainer />;
}
```

Same two-file shape every other Phase 1/2 top-level page already follows (e.g. `CargoShipmentsPage.jsx` → `CargoShipmentsContainer.jsx`) — no third `:id` route this phase, since `StockLot`/`StockMovement` have no standalone detail page (a lot's full detail is already visible inline in `StockLotTable`).

---

## 9. App shell updates

### 9.1 `App.jsx` — new route

```jsx
<Route element={<ProtectedRoute />}>
  <Route path="/settings" element={<SettingsPage />} />
  <Route path="/catalog" element={<CatalogPage />} />
  <Route path="/parties" element={<PartiesPage />} />
  <Route path="/purchase-orders" element={<PurchaseOrdersPage />} />
  <Route path="/purchase-orders/new" element={<PurchaseOrderCreatePage />} />
  <Route path="/purchase-orders/:orderId" element={<PurchaseOrderDetailPage />} />
  <Route path="/cargo-shipments" element={<CargoShipmentsPage />} />
  <Route path="/cargo-shipments/new" element={<CargoShipmentCreatePage />} />
  <Route path="/cargo-shipments/:shipmentId" element={<CargoShipmentDetailPage />} />
  <Route path="/inventory" element={<InventoryPage />} />   {/* new */}
  <Route path="/" element={<Navigate to="/purchase-orders" replace />} />
</Route>
```

Default landing route stays `/purchase-orders` — same "screen you open the next morning" reasoning as the phase-2 spec's decision 4; placing stock orders remains more frequent than checking on-hand inventory for this business. Not re-litigated here.

### 9.2 `Navbar.jsx` — `NAV_LINKS`

Inserted right after "Cargo Shipments," matching the business's actual pipeline order (purchase → ship → **receive/hold in stock** → parties/catalog are supporting master data):

```javascript
const NAV_LINKS = [
  { to: '/purchase-orders', label: 'Purchase Orders' },
  { to: '/cargo-shipments', label: 'Cargo Shipments' },
  { to: '/inventory', label: 'Inventory' },
  { to: '/parties', label: 'Parties' },
  { to: '/catalog', label: 'Catalog' },
  { to: '/settings', label: 'Settings' },
];
```

Six links now fit the same collapsing hamburger pattern Phase 0 built and Phases 1–2 already stretched to five — verify the mobile menu still opens/closes cleanly with six entries plus sign-out, at ~375px, per CLAUDE.md §3.7.

---

## 10. Testing checklist (manual, matches PLAN.md's "done when")

1. Run Phase 1's PO flow, then Phase 2's cargo-shipment flow, on a fresh draft PO with at least two lines for two different items under the same Model — confirm both lines end up with a non-null `landed_cost_pkr` on `/purchase-orders/{id}`.
2. On that PO's detail page, confirm each eligible line now shows a **Receive** button (not "—") in the new column.
3. Click **Receive** on one line — confirm the dialog opens with today's date pre-filled, shows the item label and qty, and submitting it closes the dialog and flips that line's cell to a "Received" badge with no page reload.
4. Click **Receive** on the PO's last remaining line — confirm the PO's status badge (top of the page) flips from "allocated" to "received" without a manual refresh (query invalidation working end-to-end).
5. Navigate to `/inventory` — confirm the two just-received lots appear, grouped under their shared Model, each item's row block showing its own lots with received date, qty received/remaining (equal, since nothing's been adjusted yet), landed cost/unit, and value remaining; confirm the "on hand" total in the group header row matches the sum you'd expect.
6. Click the adjust icon on one lot, enter a negative `qty_delta` larger in magnitude than `qty_remaining` (e.g. `-999`) — confirm the inline Yup error fires before any request goes out ("Resulting quantity must stay between 0 and …").
7. Enter a valid negative adjustment (e.g. `-1`, reason "damaged in storage") — confirm it submits, the dialog closes, and the lot's `qty_remaining`/`value_remaining_pkr` update in the table without a manual refresh.
8. Toggle "Show depleted lots" on/off — confirm the list re-fetches (loading state flashes) and a lot adjusted down to exactly `0` only appears when the toggle is on.
9. Attempt to receive the same line twice (open the Receive dialog again on an already-received line, or hit the endpoint directly) — confirm the 409 "already received" toast surfaces cleanly and the UI doesn't show a duplicate lot.
10. Attempt to receive a line whose PO hasn't been through a cargo shipment yet (a fresh draft PO, no shipment) — confirm no Receive button renders for that line at all (its "Landed cost/unit" cell is still "—").
11. Resize to ~375px, ~768px, ~1280px: `Navbar` still collapses correctly with 6 links + sign-out; the Receive dialog and the adjustment dialog both stay readable and don't overflow at phone width; `StockLotTable` scrolls inside its own `overflow-x-auto` container rather than widening the page body.
