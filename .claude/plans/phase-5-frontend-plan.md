# Implement Phase 5 Frontend — Local Vendor Purchase Orders

## Context

`.claude/specs/phase-5-frontend.md` is a fully-written, code-verified spec for Phase 5 of the trading-system app ("Local Vendors" per `PLAN.md`). The backend already supports a `PurchaseOrder.source` of `"china"` (existing RMB/exchange-rate flow) or `"local"` (a new PKR-direct flow with no exchange-rate step, landed cost pre-set at creation). PLAN.md is explicit that this phase ships **no new screens** — everything lives inside the existing `/purchase-orders` form/list/detail and, via a data-tagging convention only, the existing `/sales-orders` and `/parties` screens.

This plan implements exactly that spec. Two rounds of verification already happened before writing it:
1. Two Explore agents confirmed the exact current content of every touched file, cross-referenced for hidden dependents, and checked the `FormSelect`/`Badge`/`frontend-design-system` skill conventions.
2. A Plan agent reconciled the spec's illustrative code against the real current files and caught three real regressions the spec's draft would have introduced (detailed in §4 below), plus confirmed two RHF/Yup mechanics that looked risky are actually safe and already proven elsewhere in this codebase.

The result is a small, surgical change: **6 existing files edited, 0 new files, 0 new routes.** No party/sales code needs to change at all — `local_vendor` has been a valid `PARTY_ROLE` since Phase 1, and the generic `CrudTable`/`CrudDrawer` engine already handles it for free.

## Approach

Build in this order — each step is independently sane before the next:

### 1. `frontend/src/utils/constants.js`

Add, alongside the existing `PARTY_ROLE`/`CARGO_COST_BASIS_CODE` pattern:

```javascript
export const PURCHASE_ORDER_SOURCE = {
  CHINA: 'china',
  LOCAL: 'local',
};

export const PURCHASE_ORDER_SOURCE_OPTIONS = [
  { value: PURCHASE_ORDER_SOURCE.CHINA, label: 'China (RMB)' },
  { value: PURCHASE_ORDER_SOURCE.LOCAL, label: 'Local vendor (PKR)' },
];
```

`PARTY_ROLE.LOCAL_VENDOR`/`PARTY_ROLE_OPTIONS` already include local vendor — no change needed there.

### 2. `frontend/src/hooks/partyHooks/partyQueries.js`

Add a fourth role-filter hook, identical in shape to the existing `useChinaVendorParties`/`useCargoAgentParties`/`useCustomerParties` (no new imports needed — `PARTY_ROLE` and `useParties`/`LOOKUP_PAGE` are already in scope):

```javascript
// Same client-side role-filter pattern as useChinaVendorParties/useCargoAgentParties/
// useCustomerParties, for the local vendor path of the purchase order form.
export function useLocalVendorParties() {
  const query = useParties(LOOKUP_PAGE);
  const vendors = (query.data?.items ?? []).filter((party) => party.roles.includes(PARTY_ROLE.LOCAL_VENDOR));
  return { ...query, vendors };
}
```

### 3. `frontend/src/validations/purchasingSchemas.js`

Change `purchaseOrderLineSchema` (both rate fields become optional-but-positive-if-present) and `purchaseOrderCreateSchema` (add `source`, add a cross-field `.test()` mirroring the backend's own model_validator):

```javascript
import { object, string, number, array } from 'yup';
import { PURCHASE_ORDER_SOURCE } from '@/utils/constants';

export const purchaseOrderLineSchema = object({
  item_id: number().typeError('Select an item').required('Select an item'),
  qty: number().typeError('Quantity must be a number').positive('Quantity must be positive').required('Quantity is required'),
  rate_rmb: number().typeError('Rate must be a number').positive('Rate must be positive').nullable().default(null),
  rate_pkr: number().typeError('Rate must be a number').positive('Rate must be positive').nullable().default(null),
});

export const purchaseOrderCreateSchema = object({
  party_id: number().typeError('Select a vendor').required('Select a vendor'),
  order_date: string().required('Order date is required'),
  source: string().oneOf(Object.values(PURCHASE_ORDER_SOURCE)).required(),
  lines: array()
    .of(purchaseOrderLineSchema)
    .min(1, 'Add at least one line')
    .test(
      'rate-matches-source',
      'Enter a rate for every line — RMB for a China order, PKR for a local vendor order',
      function (lines) {
        const { source } = this.parent;
        if (!lines) return true;
        return lines.every((line) =>
          source === PURCHASE_ORDER_SOURCE.CHINA ? Number(line.rate_rmb) > 0 : Number(line.rate_pkr) > 0,
        );
      },
    ),
});
```

**Verified safe** (Plan-agent review read `@hookform/resolvers/yup`'s actual source): `{ raw: true }` on `yupResolver` only affects what gets returned in the *success* branch (cast vs. raw values) — it has zero effect on how `schema.validate()` runs, so `this.parent.source` sibling access inside the `.test()` works exactly as expected. This exact pattern (array-level `.test()`, sibling data, `{raw:true}` resolver) is already shipped and working in `salesSchemas.js`'s `unique-items` test — not new, unproven ground. Must stay a `function (lines) {...}`, not an arrow function, since Yup binds `this` via `function` invocation.

### 4. `frontend/src/components/purchasing/form/PurchaseOrderForm.jsx` — the main change

Add a `Source` selector, a source-conditional vendor lookup, a source-conditional exchange-rate gate, and a source-conditional single rate field per line. **Reconciled against the real current file** (not the spec's simplified illustrative draft) to preserve three things the spec's draft would have silently dropped:

- The `rows = fields.map((field, index) => ({ ...field, ...(lines[index] ?? {}) }))` defensive re-pairing pattern (guards against transient row mis-pairing after `remove()`) — map over `rows`, not raw `fields`.
- The two-stage `rawTotals` → `toMoney(rawTotals.rmb)`/`toMoney(rawTotals.pkr)` rounding on the totals row (avoids float-drift artifacts summing several already-rounded per-line amounts).
- The `try { await createMutation.mutateAsync(...) } catch { /* fetchClient already toasted */ }` wrapper in `onSubmit`, so a 422 (role mismatch, missing rate, dead item) leaves the form open with data intact instead of throwing out of `handleSubmit`.

Full reconciled file:

```jsx
import { useForm, useFieldArray, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FormField, FormSelect } from '@/components/custom';
import { purchaseOrderCreateSchema } from '@/validations/purchasingSchemas';
import { useCreatePurchaseOrder } from '@/hooks/purchasingHooks/purchasingMutations';
import { useExchangeRateForDate } from '@/hooks/purchasingHooks/purchasingQueries';
import { useChinaVendorParties, useLocalVendorParties } from '@/hooks/partyHooks/partyQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { useCategories } from '@/hooks/catalogHooks/categoryQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';
import { toMoney, computeRmbAmount, computePkrAmount, computeSaleAmount, formatRMB, formatPKR } from '@/utils/currencyUtils';
import { PURCHASE_ORDER_SOURCE, PURCHASE_ORDER_SOURCE_OPTIONS } from '@/utils/constants';

const LOOKUP_PAGE = { page: 1, page_size: 100 };
const EMPTY_LINE = { item_id: '', qty: '', rate_rmb: '', rate_pkr: '' };
const todayIso = () => new Date().toISOString().slice(0, 10);

export function PurchaseOrderForm({ onSuccess }) {
  const { vendors: chinaVendors } = useChinaVendorParties();
  const { vendors: localVendors } = useLocalVendorParties();
  const { data: itemsData } = useItems(LOOKUP_PAGE);
  const { data: categoriesData } = useCategories(LOOKUP_PAGE);
  const { data: modelsData } = useModels(LOOKUP_PAGE);

  const categoryNameById = Object.fromEntries((categoriesData?.items ?? []).map((c) => [c.id, c.name]));
  const modelNameById = Object.fromEntries((modelsData?.items ?? []).map((m) => [m.id, m.name]));
  const itemOptions = (itemsData?.items ?? []).map((item) => ({
    value: String(item.id),
    label: `${modelNameById[item.model_id] ?? '?'} · ${categoryNameById[item.category_id] ?? '?'} — ${item.sku}${item.variant ? ` (${item.variant})` : ''}`,
  }));

  const {
    control,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(purchaseOrderCreateSchema, {}, { raw: true }),
    defaultValues: { party_id: '', order_date: todayIso(), source: PURCHASE_ORDER_SOURCE.CHINA, lines: [EMPTY_LINE] },
  });
  const { fields, append, remove, replace } = useFieldArray({ control, name: 'lines' });
  const createMutation = useCreatePurchaseOrder();

  const source = watch('source');
  const isChina = source === PURCHASE_ORDER_SOURCE.CHINA;
  const orderDate = watch('order_date');
  const lines = watch('lines') ?? [];
  // Always called (Rules of Hooks) — only used to gate submit / render the warning
  // when isChina is true. A local order never needs this lookup.
  const { rate: exchangeRate, isLoading: isRateLoading } = useExchangeRateForDate(orderDate);

  const vendorOptions = (isChina ? chinaVendors : localVendors).map((v) => ({ value: String(v.id), label: v.name }));

  // Pair each rendered field with its live watched values defensively, so a
  // remove() mid-edit can't transiently mis-pair a row with another row's numbers.
  const rows = fields.map((field, index) => ({ ...field, ...(lines[index] ?? {}) }));

  const rawTotals = rows.reduce(
    (acc, row) => ({
      rmb: acc.rmb + (isChina ? computeRmbAmount(row.qty, row.rate_rmb) : 0),
      pkr: acc.pkr + (isChina
        ? (exchangeRate ? computePkrAmount(row.qty, row.rate_rmb, exchangeRate.rate) : 0)
        : computeSaleAmount(row.qty, row.rate_pkr)),
    }),
    { rmb: 0, pkr: 0 },
  );
  const totals = { rmb: toMoney(rawTotals.rmb), pkr: toMoney(rawTotals.pkr) };

  // Switching source invalidates the previously selected vendor and any entered
  // rates — a china-role vendor and an RMB rate mean nothing once switched to
  // local, and vice versa.
  const handleSourceChange = (field, value) => {
    field.onChange(value);
    setValue('party_id', '');
    replace([EMPTY_LINE]);
  };

  const onSubmit = async (values) => {
    try {
      const created = await createMutation.mutateAsync({
        party_id: values.party_id,
        order_date: values.order_date,
        source: values.source,
        lines: values.lines.map(({ item_id, qty, rate_rmb, rate_pkr }) =>
          values.source === PURCHASE_ORDER_SOURCE.CHINA
            ? { item_id, qty, rate_rmb }
            : { item_id, qty, rate_pkr },
        ),
      });
      onSuccess?.(created);
    } catch {
      // fetchClient already toasted the backend's error detail (role mismatch,
      // missing exchange rate, dead item id) — keep the form open to fix and retry.
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
      <div className="grid gap-4 md:grid-cols-3">
        <Controller
          name="source"
          control={control}
          render={({ field }) => (
            <FormSelect
              {...field}
              label="Source"
              options={PURCHASE_ORDER_SOURCE_OPTIONS}
              onChange={(value) => handleSourceChange(field, value)}
              error={errors.source?.message}
            />
          )}
        />
        <Controller
          name="party_id"
          control={control}
          render={({ field }) => (
            <FormSelect
              {...field}
              label={isChina ? 'Vendor (china vendor)' : 'Vendor (local vendor)'}
              placeholder="Select a vendor"
              options={vendorOptions}
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

      {isChina && !isRateLoading && !exchangeRate && (
        <p className="text-sm text-destructive">
          No exchange rate is set for {orderDate}. Add one in Settings → Exchange Rates before submitting.
        </p>
      )}

      <div className="flex flex-col gap-3">
        {rows.map((row, index) => (
          <div key={row.id} className="grid gap-3 rounded-lg border p-3 md:grid-cols-[2fr_1fr_1fr_auto_auto] md:items-start">
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
            <Controller
              name={`lines.${index}.qty`}
              control={control}
              render={({ field }) => (
                <FormField {...field} type="number" step="0.01" label="Qty" error={errors.lines?.[index]?.qty?.message} />
              )}
            />
            {isChina ? (
              <Controller
                name={`lines.${index}.rate_rmb`}
                control={control}
                render={({ field }) => (
                  <FormField {...field} type="number" step="0.01" label="Rate (RMB)" error={errors.lines?.[index]?.rate_rmb?.message} />
                )}
              />
            ) : (
              <Controller
                name={`lines.${index}.rate_pkr`}
                control={control}
                render={({ field }) => (
                  <FormField {...field} type="number" step="0.01" label="Rate (PKR)" error={errors.lines?.[index]?.rate_pkr?.message} />
                )}
              />
            )}
            <div className="flex flex-col justify-end gap-0.5 text-sm text-muted-foreground">
              {isChina ? (
                <>
                  <span>{formatRMB(computeRmbAmount(row.qty, row.rate_rmb))}</span>
                  {exchangeRate && <span>{formatPKR(computePkrAmount(row.qty, row.rate_rmb, exchangeRate.rate))}</span>}
                </>
              ) : (
                <span>{formatPKR(computeSaleAmount(row.qty, row.rate_pkr))}</span>
              )}
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
        {/* Whole-array Yup .test() failure (rate-matches-source) nests here — same
            @hookform/resolvers toNestErrors behavior salesSchemas.js's unique-items
            test already relies on, not new-only-to-this-phase mechanics. */}
        {errors.lines?.root?.message && <p className="text-sm text-destructive">{errors.lines.root.message}</p>}
        <Button type="button" variant="outline" size="sm" onClick={() => append(EMPTY_LINE)} className="self-start">
          <Plus /> Add line
        </Button>
      </div>

      <div className="flex justify-end gap-6 border-t pt-4 text-sm">
        {isChina && (
          <span>
            Total RMB: <strong>{formatRMB(totals.rmb)}</strong>
          </span>
        )}
        <span>
          Total PKR: <strong>{formatPKR(totals.pkr)}</strong>
        </span>
      </div>

      <Button type="submit" size="lg" disabled={isSubmitting || (isChina && !exchangeRate)} className="self-end">
        {isSubmitting ? 'Saving…' : 'Create purchase order'}
      </Button>
    </form>
  );
}
```

**Verified safe** (Plan-agent review read `react-hook-form`'s own type declarations and `FormSelect.jsx`'s source):
- `replace` is a real, first-class `useFieldArray` return value ("replace the entire field array values", used as `replace([{...}])`) — the correct wholesale-reset API, not `remove()`+`append()`.
- `FormSelect` destructures its own `onChange` prop and forwards it straight to Radix's `Select` — it has no RHF awareness, so `<FormSelect {...field} onChange={...} />` fully *shadows* `field.onChange`, it does not auto-chain. `handleSourceChange` must call `field.onChange(value)` itself (it does, as the first line) or RHF's form state for `source` would silently stop updating on selection.

### 5. `frontend/src/components/purchasing/PurchaseOrderList.jsx`

Add a `Source` column: one `<TableHead>Source</TableHead>` after `Status` in the header row, bump all three `colSpan={5}` occurrences (loading/error/empty states) to `colSpan={6}`, and add one cell per data row after the status cell:

```jsx
<TableCell>
  <Badge variant="secondary">{order.source === 'local' ? 'Local' : 'China'}</Badge>
</TableCell>
```

`Badge` is already imported in this file. **Use `variant="secondary"` unconditionally for both values** — verified against every other status/role/cost-basis badge in `purchasing/`, `parties/`, `cargo/` (all use plain `secondary`, differentiated by label text only; `destructive` is reserved specifically for a genuinely negative state like `PartyStatement.jsx`'s "we owe them" balance, which doesn't apply here). This corrects the spec document's own draft, which had proposed `variant={order.source === 'local' ? 'outline' : 'secondary'}` — a color distinction the actual codebase convention and `.claude/skills/frontend-design-system/SKILL.md` (a new status color needs deliberate OKLCH-hue justification against the primary indigo/gold pair) don't support for a two-value label-only distinction.

### 6. `frontend/src/components/purchasing/PurchaseOrderDetail.jsx`

Add the same badge next to the existing status badge, wrapped together so `justify-between` on the outer header row doesn't push them apart:

```jsx
<div className="flex items-center gap-2">
  <Badge variant="secondary">{order.status}</Badge>
  <Badge variant="secondary">{order.source === 'local' ? 'Local' : 'China'}</Badge>
</div>
```

This replaces the current lone `<Badge variant="secondary">{order.status}</Badge>` sibling in the header block. No other change to this file — every `rate_rmb`/`amount_rmb`/`landed_cost_pkr`/`amount_landed_pkr` cell already renders `—` independently for a `null` value via existing per-cell checks, which is exactly what a local order's response (null RMB fields, pre-populated landed-cost fields) needs with zero additional code.

## Confirmed unchanged — no edits needed

Verified against the real current code, not assumed: `services/purchasingService.js` (payload passthrough, no shape assumptions), `hooks/purchasingHooks/purchasingMutations.js` (`useCreatePurchaseOrder`'s invalidation is already sufficient), `utils/queryKeys.js`, `utils/currencyUtils.js` (`computeSaleAmount` already exists and is reused as-is for the local-line preview — no new function), `components/parties/PartyCrudConfig.jsx`, `components/parties/PartyRoleBadges.jsx`, `validations/partySchemas.js` (all already generic over `PARTY_ROLE`, `local_vendor` has worked since Phase 1), `components/sales/form/SalesOrderForm.jsx`, `validations/salesSchemas.js` (selling to a local vendor works once that party also carries the `customer` role — a tagging convention, not a code change), `App.jsx`, `Navbar.jsx` (no new route/nav entry).

## Verification

1. Start the frontend dev server (`npm run dev` in `frontend/`) and the backend (already implemented per the spec's confirmed API surface).
2. On `/parties`, add a party with roles **Local Vendor** + **Customer** both checked (no seed-script shortcut exists for this).
3. On `/purchase-orders/new`: confirm `Source` defaults to "China (RMB)" and the existing china flow is unaffected (regression check) — vendor dropdown, exchange-rate warning/gate, RMB rate field all behave exactly as before.
4. Switch `Source` to "Local vendor (PKR)": confirm the vendor dropdown now lists only the local-vendor party from step 2, the exchange-rate warning disappears, each line shows "Rate (PKR)" instead of "Rate (RMB)", and any previously entered vendor/lines were cleared.
5. Add lines and submit a local order — confirm the resulting detail page shows a "Local" badge, `status: allocated` immediately (never `draft`), and landed cost already populated per line with no cargo-shipment step.
6. Confirm the local order does **not** appear in `/cargo-shipments/new`'s "attach open POs" picker.
7. Receive the local order's line(s) directly via the existing Receive action — confirm it succeeds immediately.
8. On `/sales-orders/new`, confirm the same party (tagged with `customer`) appears in the customer dropdown; sell some of the received stock back to them.
9. On `/parties/{id}`, confirm the statement shows both an "Accounts Payable" entry (from the local purchase) and an "Accounts Receivable" entry (from the sale) combined into one balance.
10. On `/purchase-orders`, confirm the list's new Source column shows "China"/"Local" correctly for existing and new orders.
11. Resize to ~375px/~768px/~1280px: confirm the form's now-three-column top row stacks to one column below `md`, and both list/detail tables (with the extra Source column) still scroll inside their own `overflow-x-auto` container.
