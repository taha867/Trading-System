# Phase 5 Frontend — Spec

Source of truth: `PLAN.md` (§ Phase 5 — Local vendors) for *what*, `CLAUDE.md` (§3) for *how*, and `.claude/specs/phase-5-backend.md` for the backend design — but the API surface below (§1.1) is re-verified against the **actual running `backend/src/purchasing/`, `backend/src/parties/`, `backend/src/sales/`, and `backend/src/cargo/` code**, not the design doc, exactly like the phase-1/2/3/4 frontend specs did for their phases. Where this doc and the backend spec draft disagree, trust §1.1 — and note one confirmed divergence there (`cargo/service.py`, called out explicitly).

**Done when** (verbatim from PLAN.md): the same party record can appear as the vendor on one order and the customer on another, with one balance. PLAN.md is explicit that this phase ships **no new screens** — "if this phase needs a new screen, that's a sign the `Party` role model from Phase 0 needs revisiting — it shouldn't." This spec follows that literally: every change below is an edit inside a file `/purchase-orders`, `/sales-orders`, or `/parties` already renders — no new route, no new page/container/component file, no new nav link.

At the time of writing, `frontend/` already has Phases 0–4 shipped in full — auth, the generic `CrudTable`/`CrudDrawer` engine, all lookup CRUD, `PurchaseOrder`/`CargoShipment`/`StockLot`/`SalesOrder` hand-written screens, and `PartyStatement`. This spec is additive/modifying on top of that tree — nothing in the prior specs' scope gets removed or renamed, and (per §2 below) most of it turns out to need **no change at all**, because Phase 1 already built the `Party` role system generically enough to absorb this.

---

## 1. Scope

Build, in this order (each step independently usable/testable before the next):

1. `utils/constants.js` — add `PURCHASE_ORDER_SOURCE`/`PURCHASE_ORDER_SOURCE_OPTIONS`. (`PARTY_ROLE.LOCAL_VENDOR`/`PARTY_ROLE_OPTIONS` already include it — confirmed, zero change, §2 decision 1.)
2. `hooks/partyHooks/partyQueries.js` — add `useLocalVendorParties()`, the fourth instance of the existing client-side role-filter pattern.
3. `validations/purchasingSchemas.js` — `purchaseOrderCreateSchema` gains a `source` field and a cross-field rule requiring the correct rate field per line, mirroring the backend's own `model_validator` (backend spec §2.3).
4. `components/purchasing/form/PurchaseOrderForm.jsx` — the one component that actually changes shape this phase: a source selector, a source-conditional vendor lookup, a source-conditional exchange-rate gate, and a source-conditional rate field per line.
5. `components/purchasing/PurchaseOrderList.jsx` / `PurchaseOrderDetail.jsx` — one new column/badge each, surfacing `source`.
6. Everything else — confirmed against the real code in §2 to need **no change**: `PartyCrudConfig.jsx`, `PartyRoleBadges.jsx`, `validations/partySchemas.js`, `SalesOrderForm.jsx`, `validations/salesSchemas.js`, the cargo "attach open POs" picker, `services/purchasingService.js`, `hooks/purchasingHooks/purchasingMutations.js`, `utils/queryKeys.js`, `utils/currencyUtils.js`, `App.jsx`, `Navbar.jsx`.

Out of scope, per PLAN.md's roadmap and this phase's own backend spec (§9 there): `PaymentAccount`/`PaymentTransaction` (Phase 6), expenses/reporting, any `PurchaseOrder.source` edit-after-create UI (no backend route exists — §1.1), and any UI guard against a dual-role (`china_vendor` + `local_vendor`) party picking the "wrong" source for a given vendor (backend spec §9 flags this as accepted for a solo operator; §2 decision 9 below explains why the frontend's own filtered dropdowns already close most of that gap without extra code).

### 1.1 Confirmed API surface (from running backend code, not the design draft)

Every route below requires `Authorization: Bearer <access_token>`, same as every prior phase. Error bodies are the same dual shape `fetchClient.js` already handles: `{"detail": "..."}` for a domain `AppException`, `{"detail": [{"loc":..., "msg":...}]}` for a raw Pydantic validation failure. **Every `Decimal` field is still a JSON string** in responses — `qty`, `rate_rmb`, `rate_pkr`, `landed_cost_pkr`, `amount_rmb`, `amount_pkr`, `amount_landed_pkr`, `total_rmb`, `total_pkr` all serialize as strings when present. Send back exactly what the form collected.

**No new routes.** `POST /purchasing/purchase-orders`'s body gains one optional field; its response and the two `GET`s gain one field each. `sales/router.py` and `sales/schemas.py` are confirmed byte-for-byte unchanged — no request/response shape to update on the sales side at all, only which parties can succeed against the existing role check.

**`PurchaseOrderCreate` request body** (`backend/src/purchasing/schemas.py:63-78`):
```json
{
  "party_id": 1,
  "order_date": "2026-08-08",
  "source": "china",
  "lines": [
    { "item_id": 1, "qty": "10.00", "rate_rmb": "5.50", "rate_pkr": null }
  ]
}
```
`source` is `"china" | "local"`, **optional, defaults to `"china"`** — every existing Phase 1 request body (no `source` key at all) still works unchanged. Each line carries **both** `rate_rmb` and `rate_pkr` as optional/nullable fields (each `gt=0, decimal_places=2` when present); a `@model_validator(mode="after")` on `PurchaseOrderCreate` enforces exactly one is set, matching `source` — a china line must set `rate_rmb` and leave `rate_pkr` unset, a local line the reverse. The actual error message (not just the design doc's illustrative text) is per-line-indexed: `"line {i}: china-sourced lines must set rate_rmb, not rate_pkr"` / `"line {i}: local-sourced lines must set rate_pkr, not rate_rmb"` — surfaces as a 422 the same way every other Pydantic validation error does, no special-case handling needed in `fetchClient.js`.

**`PurchaseOrderRead` response** (`backend/src/purchasing/schemas.py:81-106`):
```json
{
  "id": 1, "party_id": 1, "order_date": "2026-08-08",
  "source": "china", "status": "draft",
  "lines": [
    { "id": 1, "item_id": 1, "qty": "10.00", "rate_rmb": "5.50", "rate_pkr": "154.00",
      "landed_cost_pkr": null, "amount_rmb": "55.00", "amount_pkr": "1540.00", "amount_landed_pkr": null }
  ],
  "total_rmb": "55.00", "total_pkr": "1540.00"
}
```
For a **local** order, every line comes back with `rate_rmb: null`, `amount_rmb: null`, and — the one genuinely new behavior this phase adds — `landed_cost_pkr` and `amount_landed_pkr` **already populated at creation**, equal to `rate_pkr`/`amount_pkr`, with `status: "allocated"` from the first response, never `"draft"`. There is no cargo step to wait for. `PurchaseOrderDetail.jsx` already renders each of these columns independently and shows `—` for a `null` (established in the phase-2 spec, "both `null` on a line whose PO hasn't been through a shipment yet — render `—`, don't coerce to `0`") — a local order simply exercises the "populated immediately" branch of logic that already exists for a china order post-shipment. No new null-handling code is needed, only the source badge (§4.2).

**`total_rmb` nullability is not a reliable proxy for `source === "local"`** — worth calling out because it would be an easy, wrong shortcut. The actual implementation keys `total_rmb` off "does any line lack `amount_rmb`" (a defensive choice explained in-code, not the design doc's literal `source == "local"` check) rather than off `source` directly. In practice every order created through this UI has `total_rmb == null` if and only if `source == "local"`, because the create-time validator above guarantees a china order's lines always carry `rate_rmb`. But the frontend should render off the `source` field directly wherever it's choosing UI copy/labels (§4.2), and treat `total_rmb === null` purely as "nothing to show in this cell," not as a semantic signal of source.

**PO creation error cases, per source** (`backend/src/purchasing/service.py:23-111`):

| Cause | Status | Applies to |
|---|---|---|
| `party_id` doesn't resolve to an active party | 404 | both |
| vendor's `roles` doesn't include the role matching `source` (`china_vendor` for `"china"`, `local_vendor` for `"local"` — **exact match, not either-or**) | 422 | both |
| no active `ExchangeRate` row for `order_date` | 422 | **china only** — a local order never looks this up |
| a line's rate field doesn't match `source` (§ above) | 422 | both |
| any `item_id` doesn't resolve to an active item | 422 | both |
| residual `IntegrityError` | 409 | both |

**Role check is an exact match per source, not "either role is fine.·"** A party holding only `china_vendor` will get a 422 if you try to create a `source: "local"` order against it, and vice versa — `purchasing.service.create_purchase_order` calls the existing `ensure_role` (single, exact role), not the new `ensure_any_role` (backend spec §2.6). This is relevant to §2 decision 9 below: because the frontend's vendor dropdown is *already* filtered to parties holding the matching role per source, the UI structurally cannot submit a mismatched combination — the 422 case above can only be hit by editing the request by hand.

**`ensure_any_role(party, roles)`** (`backend/src/parties/service.py:37-41`) is the one new backend function this phase adds, used only by `sales.service.create_sales_order` (`backend/src/sales/service.py:26`): `ensure_any_role(customer, (PartyRole.CUSTOMER, PartyRole.LOCAL_VENDOR))`. This is the entire backend change on the sales side — no schema, no router change. Concretely: **a party is sellable-to via the existing sales screen if it holds `customer` OR `local_vendor`.** Since `SalesOrderForm.jsx` already sources its customer dropdown from `useCustomerParties()` (filters on `PARTY_ROLE.CUSTOMER` only, client-side, §5), a `local_vendor`-only party will **not** appear there yet — see §5.1 for why that's a documentation fix, not a code fix.

**Confirmed divergence from `.claude/specs/phase-5-backend.md`:** that doc's §1/§2.5/§3.3/§5.4/§10 assert "`cargo/` needs zero code changes." The shipped code doesn't match that — `cargo/service.py`'s PO-attach loop (`cargo/service.py:46-57`) was changed to check `line.purchase_order.source == "local"` explicitly, in addition to the pre-existing `status != "draft"` check, raising `PurchaseOrderNotOpen` with an updated message: `"...(local-sourced orders skip cargo entirely; china-sourced orders must be in 'draft' status)"`. This has **no frontend implication** — `CargoShipmentForm`'s "attach open POs" picker already filters client-side on `status === "draft"` (phase-2 spec §1.1/§2), and a local order is created with `status: "allocated"` from the start (never `"draft"`), so it was already excluded by that existing filter before this backend hardening was added. Flagged here only so a future reader isn't surprised to find `cargo/` touched when this spec (and the backend spec) both say it shouldn't need to be.

**No seed-script support.** `backend/scripts/seed.py` still only has `seed_china_vendor`/`--vendor-name` — no `--local-vendor-name` flag or `seed_local_vendor` function exists. A `local_vendor` party for manual testing must be created by hand through the `/parties` screen (§6, testing checklist step 1) — there is no seed shortcut.

---

## 2. Decisions

Judgment calls this spec makes where PLAN.md/CLAUDE.md don't fully spell out the frontend shape. Several of these are "confirmed no-op" findings from reading the actual shipped code rather than the phase-1/phase-4 spec drafts, which turn out to matter as much as the real code changes below.

1. **`PARTY_ROLE.LOCAL_VENDOR` and `PARTY_ROLE_OPTIONS` already include it — added speculatively back in Phase 1, unused until now.** Confirmed against `frontend/src/utils/constants.js:13-25`. Zero change needed for the role to be selectable, labeled ("Local Vendor"), or badge-rendered anywhere in the app.
2. **There is no hand-written `PartyForm.jsx` to touch** — a possible stale assumption CLAUDE.md's own illustrative `components/parties/form/` tree entry could suggest. Party create/edit runs entirely through the generic `CrudTable`/`CrudDrawer` engine, configured by `components/parties/PartyCrudConfig.jsx`, whose `roles` field is a `multiselect` driven directly off `PARTY_ROLE_OPTIONS` (not a hardcoded list of `<Checkbox>`es per role). Confirmed: adding a party with role `local_vendor` already works today, with the same drawer Phase 1 shipped. Same for `validations/partySchemas.js` (`roles: array().of(string().oneOf(Object.values(PARTY_ROLE)))` — generic over whatever's in the enum) and `components/parties/PartyRoleBadges.jsx` (renders any role via a `LABEL_BY_VALUE` map built from `PARTY_ROLE_OPTIONS`, not a per-role switch).
3. **Source is a `FormSelect` with two options, not a new toggle/segmented-control component.** A binary china/local choice could justify a bespoke control, but this codebase has exactly one pattern for "pick one of a small fixed set" (`FormSelect` — used for vendor, item, order-date-adjacent pickers everywhere) and introducing a second pattern for one field isn't worth it. `PURCHASE_ORDER_SOURCE_OPTIONS` (§3) follows the exact same `{value, label}` shape as `PARTY_ROLE_OPTIONS`/`CARGO_COST_BASIS_CODE_OPTIONS`.
4. **The rate-matches-source cross-field rule is one `array().test()` on `lines`, not a Yup `context`-based per-field `.when()`.** Yup's `.when()` reaches sibling fields *within the same object*, not a parent's siblings from inside an array-of-objects — reaching `source` from inside each line item would need `yupResolver`'s `context` option threaded through `useForm`, which only usefully updates if `context` is kept in sync with `watch('source')` on every render (a second source of truth for the same value). Simpler and just as correct: keep each line's `rate_rmb`/`rate_pkr` both optional-but-positive-if-present at the per-line level, and add one `.test()` on the `lines` array itself that reads `this.parent.source` (a true sibling access, since `lines` and `source` are both direct children of `purchaseOrderCreateSchema`) and checks every line has the rate matching `source`. This mirrors the backend's own `model_validator` shape exactly — one cross-field rule, checked once, not scattered per-field — and surfaces as `errors.lines.root.message`, the same nesting `@hookform/resolvers`' `toNestErrors` already uses for the sales domain's whole-array `unique-items` test (phase-4 spec §7.1's documented behavior).
5. **Switching `source` resets `party_id` and `lines` back to their defaults.** A vendor selected while `source: "china"` was active is drawn from `useChinaVendorParties()` and is very likely not a `local_vendor`-role party (and vice versa) — leaving a stale selection in place would just produce the 422 role-mismatch case at submit for no reason. Likewise, a `rate_rmb` typed in for a china line is meaningless once switched to local (the schema would want `rate_pkr` instead). Resetting both on source-change keeps the form always internally consistent, at the cost of losing in-progress line data on a source switch — acceptable since switching source mid-entry is expected to be rare (a user picks "buying from China" or "buying locally" before they start typing lines, not partway through).
6. **`useExchangeRateForDate` is still called unconditionally** (Rules of Hooks — it can't be called only when `source === "china"`), but its result only gates the submit button and renders the "no rate" warning when `source === "china"`. For a local order the hook still fetches in the background (harmless — it's the same cached `page_size=100` exchange-rate page every other screen already shares) but its result is simply unused.
7. **`computeSaleAmount(qty, ratePkr)` (already in `utils/currencyUtils.js`, added in Phase 4) is reused verbatim for a local line's live preview**, not a new duplicate function. It's already exactly the right shape — `qty × rate_pkr`, no exchange-rate step — because sales lines and local-purchase lines are both quoted directly in PKR. `computeRmbAmount`/`computePkrAmount` stay reserved for the china path.
8. **Selling to a local vendor via the existing `SalesOrderForm` needs no code change — it's a data-tagging convention, documented, not built.** `sales.service.create_sales_order`'s role check now accepts `customer` OR `local_vendor` (§1.1), but `SalesOrderForm`'s customer dropdown is sourced from `useCustomerParties()`, which filters strictly on `PARTY_ROLE.CUSTOMER`. A `local_vendor`-only party is therefore invisible in that dropdown today — not broken, just not reachable, because nothing in this phase's scope asks the sales screen's *picker* to widen (PLAN.md's ask is role flexibility on the `Party`/`PurchaseOrder` side; the backend's own role check is already widened defensively for when this is needed). The practical answer, and what the testing checklist (§6) exercises: **tag the party with both `local_vendor` and `customer` roles** at creation (the roles field is already a multiselect, §2.2) if you intend to both buy from and sell to them. This is called out explicitly rather than left as a silent gap, because it's the one place "no new screens" could otherwise read as "sales to local vendors doesn't work" — it does, once the party carries the right role combination.
9. **No UI guard against a dual-role party picking the "wrong" `source`.** Backend spec §9 flags this as an open risk (a party holding both `china_vendor` and `local_vendor` could have the wrong `source` selected and still succeed, silently posting to the wrong pricing flow). The frontend doesn't add a warning for this — but it does structurally prevent the more common mistake: because the vendor dropdown is *already* filtered to `useChinaVendorParties()` or `useLocalVendorParties()` depending on the selected `source` (§4.1), a party lacking the role required by the currently-selected `source` **cannot be selected at all** through this form. The only way to hit the "wrong role for this source" 422 is to already hold both roles and deliberately pick the less-intended one — the exact residual gap the backend spec already accepted as fine for a single-operator system.
10. **No `source`-correction / PO-edit UI.** Matches the backend precedent already established for `PurchaseOrder` in every prior phase (no `PUT`, no `PurchaseOrderUpdate` schema at all) — a PO created with the wrong `source` is fixed by creating a new one, same as any other PO mistake.

---

## 3. `utils/constants.js` addition

```javascript
// utils/constants.js — new, alongside PARTY_ROLE (that one is unchanged — local_vendor
// has been present since Phase 1, see §2 decision 1).
export const PURCHASE_ORDER_SOURCE = {
  CHINA: 'china',
  LOCAL: 'local',
};

export const PURCHASE_ORDER_SOURCE_OPTIONS = [
  { value: PURCHASE_ORDER_SOURCE.CHINA, label: 'China (RMB)' },
  { value: PURCHASE_ORDER_SOURCE.LOCAL, label: 'Local vendor (PKR)' },
];
```

---

## 4. Purchasing domain — the actual work this phase

### 4.1 `validations/purchasingSchemas.js` — changed

```javascript
import { object, string, number, array } from 'yup';
import { PURCHASE_ORDER_SOURCE } from '@/utils/constants';

export const purchaseOrderLineSchema = object({
  item_id: number().typeError('Select an item').required('Select an item'),
  qty: number().typeError('Quantity must be a number').positive('Quantity must be positive').required('Quantity is required'),
  // Both optional at the per-line level — which one is actually required depends on
  // the parent order's `source`, enforced once below (§2 decision 4), not per field,
  // mirroring the backend's own model_validator (phase-5-backend.md §2.3).
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
    // Sibling access via this.parent — `lines` and `source` are both direct children
    // of this same object schema (§2 decision 4), not nested context.
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

### 4.2 `components/purchasing/form/PurchaseOrderForm.jsx` — changed

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
import { computeRmbAmount, computePkrAmount, computeSaleAmount, formatRMB, formatPKR } from '@/utils/currencyUtils';
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

  const { control, handleSubmit, watch, setValue, formState: { errors, isSubmitting } } = useForm({
    resolver: yupResolver(purchaseOrderCreateSchema, {}, { raw: true }),
    defaultValues: { party_id: '', order_date: todayIso(), source: PURCHASE_ORDER_SOURCE.CHINA, lines: [EMPTY_LINE] },
  });
  const { fields, append, remove, replace } = useFieldArray({ control, name: 'lines' });
  const createMutation = useCreatePurchaseOrder();

  const source = watch('source');
  const isChina = source === PURCHASE_ORDER_SOURCE.CHINA;
  const orderDate = watch('order_date');
  const lines = watch('lines');
  // Always called (Rules of Hooks) — only used to gate submit / render the warning
  // when isChina is true (§2 decision 6). A local order never needs this lookup.
  const { rate: exchangeRate, isLoading: isRateLoading } = useExchangeRateForDate(orderDate);

  const vendorOptions = (isChina ? chinaVendors : localVendors).map((v) => ({ value: String(v.id), label: v.name }));

  const totals = lines.reduce((acc, line) => ({
    rmb: acc.rmb + (isChina ? computeRmbAmount(line.qty, line.rate_rmb) : 0),
    pkr: acc.pkr + (isChina
      ? (exchangeRate ? computePkrAmount(line.qty, line.rate_rmb, exchangeRate.rate) : 0)
      : computeSaleAmount(line.qty, line.rate_pkr)),
  }), { rmb: 0, pkr: 0 });

  // Switching source invalidates the previously selected vendor and any entered
  // rates (§2 decision 5) — a china-role vendor and an RMB rate mean nothing once
  // switched to local, and vice versa.
  const handleSourceChange = (field, value) => {
    field.onChange(value);
    setValue('party_id', '');
    replace([EMPTY_LINE]);
  };

  const onSubmit = async (values) => {
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
              label={isChina ? 'Vendor (China)' : 'Vendor (Local)'}
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
        {fields.map((field, index) => (
          <div key={field.id} className="grid gap-3 rounded-lg border p-3 md:grid-cols-[2fr_1fr_1fr_auto_auto]">
            <Controller name={`lines.${index}.item_id`} control={control} render={({ field: f }) => (
              <FormSelect {...f} label="Item" options={itemOptions} error={errors.lines?.[index]?.item_id?.message} />
            )} />
            <Controller name={`lines.${index}.qty`} control={control} render={({ field: f }) => (
              <FormField {...f} type="number" step="0.01" label="Qty" error={errors.lines?.[index]?.qty?.message} />
            )} />
            {isChina ? (
              <Controller name={`lines.${index}.rate_rmb`} control={control} render={({ field: f }) => (
                <FormField {...f} type="number" step="0.01" label="Rate (RMB)" error={errors.lines?.[index]?.rate_rmb?.message} />
              )} />
            ) : (
              <Controller name={`lines.${index}.rate_pkr`} control={control} render={({ field: f }) => (
                <FormField {...f} type="number" step="0.01" label="Rate (PKR)" error={errors.lines?.[index]?.rate_pkr?.message} />
              )} />
            )}
            <div className="flex flex-col justify-end text-sm text-muted-foreground">
              {isChina ? (
                <>
                  <span>{formatRMB(computeRmbAmount(lines[index]?.qty, lines[index]?.rate_rmb))}</span>
                  {exchangeRate && <span>{formatPKR(computePkrAmount(lines[index]?.qty, lines[index]?.rate_rmb, exchangeRate.rate))}</span>}
                </>
              ) : (
                <span>{formatPKR(computeSaleAmount(lines[index]?.qty, lines[index]?.rate_pkr))}</span>
              )}
            </div>
            <Button type="button" variant="ghost" size="icon-sm" onClick={() => remove(index)} disabled={fields.length === 1}>
              <Trash2 className="text-destructive" />
            </Button>
          </div>
        ))}
        {/* Whole-array test() failure (rate-matches-source) nests here, same
            @hookform/resolvers toNestErrors behavior the sales domain's unique-items
            test already documents (phase-4-frontend.md §7.1). */}
        {errors.lines?.root?.message && <p className="text-sm text-destructive">{errors.lines.root.message}</p>}
        <Button type="button" variant="outline" size="sm" onClick={() => append(EMPTY_LINE)} className="self-start">
          <Plus /> Add line
        </Button>
      </div>

      <div className="flex justify-end gap-6 border-t pt-4 text-sm">
        {isChina && <span>Total RMB: <strong>{formatRMB(totals.rmb)}</strong></span>}
        <span>Total PKR: <strong>{formatPKR(totals.pkr)}</strong></span>
      </div>

      <Button type="submit" disabled={isSubmitting || (isChina && !exchangeRate)} className="self-end">
        {isSubmitting ? 'Saving…' : 'Create purchase order'}
      </Button>
    </form>
  );
}
```

Everything not shown as changed above (the item/category/model lookups, `useFieldArray` wiring, the responsive grid classes, the submit-disabled pattern) is byte-identical to the Phase 1 version — the diff is isolated to exactly the source-conditional pieces this phase needs, same discipline the backend spec used for `create_purchase_order`'s own branch (backend spec §5.1).

### 4.3 `components/purchasing/PurchaseOrderList.jsx` / `PurchaseOrderDetail.jsx` — one badge each

`PurchaseOrderList.jsx` gains a `Source` column next to the existing `status` badge column:
```jsx
<TableHead>Source</TableHead>
// ...
<TableCell>
  <Badge variant={order.source === 'local' ? 'outline' : 'secondary'}>
    {order.source === 'local' ? 'Local' : 'China'}
  </Badge>
</TableCell>
```
`PurchaseOrderDetail.jsx` gains the same badge next to its existing status badge in the header. No other change to either file — the `landed_cost_pkr`/`amount_landed_pkr`/`rate_rmb`/`amount_rmb` columns Phase 2 added already render `null` as `—` independently per cell (phase-2 spec's established convention), which is exactly the behavior a local order's response needs (§1.1) with zero additional null-handling logic.

### 4.4 Confirmed unchanged — `services/purchasingService.js`, `hooks/purchasingHooks/purchasingMutations.js`, `utils/queryKeys.js`, `utils/currencyUtils.js`

- `services/purchasingService.js::createPurchaseOrder` passes its payload through opaquely (`fetchClient.post('/purchasing/purchase-orders', payload)`) — the new `source` key needs no service-layer change.
- `hooks/purchasingHooks/purchasingMutations.js::useCreatePurchaseOrder` already invalidates `purchaseOrderKeys.lists()` on success — sufficient for a local order's immediate `"allocated"` status and pre-set `landed_cost_pkr` to show up correctly on the next list/detail fetch, no new invalidation target needed (unlike Phase 3/4, a local PO create has no side effect on `stockLotKeys` or `partyKeys.statement` — it posts the same single `"Accounts Payable"` ledger entry a china PO already posts, already covered by the existing party-statement `GET` being un-cached-by-key here since `partyKeys.statement` is only invalidated by mutations that already know the affected `party_id` up front; a purchase order's ledger effect on that vendor's statement is picked up the next time `/parties/{id}` is visited, same as it already works for china orders today — not a new gap this phase introduces).
- `utils/queryKeys.js` — `purchaseOrderKeys`/`partyKeys` already sufficient; no new key needed.
- `utils/currencyUtils.js` — no new export; `computeSaleAmount` (already shipped in Phase 4) is reused as-is (§2 decision 7).

---

## 5. Parties domain

### 5.1 `hooks/partyHooks/partyQueries.js` addition

```javascript
// Fourth instance of the same client-side role-filter pattern as
// useChinaVendorParties/useCargoAgentParties/useCustomerParties.
export function useLocalVendorParties() {
  const query = useParties(LOOKUP_PAGE);
  const vendors = (query.data?.items ?? []).filter((party) => party.roles.includes(PARTY_ROLE.LOCAL_VENDOR));
  return { ...query, vendors };
}
```

### 5.2 Confirmed unchanged (§2 decisions 1–2)

`utils/constants.js` (`PARTY_ROLE`/`PARTY_ROLE_OPTIONS`), `validations/partySchemas.js`, `components/parties/PartyCrudConfig.jsx`, `components/parties/PartyRoleBadges.jsx` — all already generic over whatever's in `PARTY_ROLE`, and `local_vendor` has been a member since Phase 1. Adding a party with `roles: ["local_vendor"]`, or `roles: ["local_vendor", "customer"]` for one that both sells to and buys from the business, already works today through the existing `/parties` `CrudTable`/`CrudDrawer` screen with no code change.

---

## 6. Sales and cargo domains — confirmed unchanged

**Sales:** `validations/salesSchemas.js` and `components/sales/form/SalesOrderForm.jsx` are unchanged. The backend's `ensure_any_role(customer, (CUSTOMER, LOCAL_VENDOR))` (§1.1) means a `local_vendor`-only party *could* succeed against `POST /sales/sales-orders`, but `SalesOrderForm`'s customer dropdown only ever offers parties from `useCustomerParties()` (filtered on `PARTY_ROLE.CUSTOMER`). Per §2 decision 8, the resolution is a **tagging convention, not a code change**: give a party both `local_vendor` and `customer` roles at creation if you intend to sell surplus back to them, and they'll appear in the sales screen's picker exactly like any other customer. This is stated explicitly in the testing checklist (§7) since it's easy to read PLAN.md's "reuse the Phase 4 sales screen for selling surplus to them" as implying a code change on the sales side, when the actual mechanism is the `Party.roles` array already supporting more than one role per party.

**Cargo:** `components/cargo/form/CargoShipmentForm.jsx`'s "attach open POs" picker already filters client-side on `status === "draft"` (phase-2 spec §1.1). A local order is created with `status: "allocated"` (§1.1), so it's excluded from that picker automatically, with no frontend change — matching the backend's own design intent even though the backend's enforcement of it was implemented slightly differently than its own spec claimed (§1.1's divergence note).

---

## 7. App shell — confirmed unchanged

`App.jsx`'s routes and `Navbar.jsx`'s `NAV_LINKS` need no change — no new screen, no new route, confirmed against the current files (`/purchase-orders`, `/purchase-orders/new`, `/purchase-orders/:orderId`, `/sales-orders*`, `/parties*`, catalog/cargo/inventory/settings — the full existing set already covers everything this phase touches).

---

## 8. Testing checklist (manual, matches PLAN.md's "done when")

1. On `/parties`, add a new party with roles **Local Vendor** and **Customer** both checked (no seed-script shortcut exists for this — §1.1) — confirm both role badges render on the row.
2. Go to `/purchase-orders/new`. Confirm `Source` defaults to "China (RMB)", the vendor dropdown and required-rate behavior match Phase 1 exactly (regression check) — an exchange-rate warning appears/disables submit if today has no rate, same as before.
3. Switch `Source` to "Local vendor (PKR)" — confirm the vendor dropdown now lists the party from step 1 (and not any china-only vendor), the exchange-rate warning disappears entirely (it's not applicable), and each line shows a single "Rate (PKR)" field instead of "Rate (RMB)". Confirm any previously entered vendor/lines were cleared by the switch (§2 decision 5).
4. Add two lines with real items, qty, and PKR rate — confirm the live per-line and total PKR preview updates (no RMB total shown at all for a local order) — then submit.
5. Confirm the created order's detail page shows `Source: Local`, `status: allocated` **immediately** (never `draft`), and every line's landed cost already populated equal to its PKR rate — with no cargo-shipment step in between.
6. Go to `/cargo-shipments/new` and open the "attach open POs" picker — confirm the local order from step 5 does **not** appear (only `draft`-status china orders do).
7. Use Phase 3's Receive action on the local order's line(s) directly from its detail page — confirm it succeeds immediately (no landed-cost-missing error), producing a `StockLot`.
8. On `/sales-orders/new`, confirm the customer dropdown includes the party from step 1 (because it also holds the `customer` role) — sell some of the stock received in step 7 back to that same party.
9. Open `/parties/{id}` for that party — confirm the statement shows **both** an "Accounts Payable" entry (from the local purchase) and an "Accounts Receivable" entry (from the sale), combined into one running/closing balance.
10. Repeat step 1 with a party tagged **Local Vendor only** (no `customer` role) — confirm it's absent from the `/sales-orders/new` customer dropdown, demonstrating the tagging convention from §2 decision 8/§6 concretely rather than just asserting it.
11. Attempt to create a local-sourced PO against a `china_vendor`-only party by temporarily editing that party's roles — confirm it disappears from the local-source vendor dropdown the moment the role is removed (client-side filter working), consistent with §2 decision 9's "can't even select the wrong vendor" claim.
12. Resize to ~375px, ~768px, ~1280px: the form's now-three-column top row (`Source`/`Vendor`/`Order date`) stacks to one column below `md`; the per-line grid and both list/detail tables (now with the extra Source column) still scroll inside their own `overflow-x-auto` container rather than widening the page, per CLAUDE.md §3.7.
