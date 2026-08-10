# Phase 1 Frontend — Spec

Source of truth: `PLAN.md` (§ Phase 1 — Catalog & China purchasing) for *what*, `CLAUDE.md` (§3) for *how*, and `.claude/specs/phase-1-backend.md` for the backend spec draft — but the API surface table below (§1.1) is re-verified against the **actual running `backend/src/` code**, not the draft, exactly like the phase-0-frontend spec did for Phase 0. Where this doc and the backend spec draft disagree, trust §1.1.

**Done when** (verbatim from PLAN.md): you can create a PO against a real vendor, in RMB, and see the PKR cost per line and total — solves "how will we buy stock and at what rate."

At the time of writing, `frontend/` already has Phase 0 shipped in full (auth, `fetchClient`, the generic `CrudTable`/`CrudDrawer` engine, `ExchangeRate` + `PaymentMethod` lookups under a tabbed `/settings`). This spec is additive on top of that tree — nothing in §2 of the phase-0 spec gets removed or renamed.

---

## 1. Scope

Build, in this order (each step independently usable/testable before the next):

1. Generic CRUD engine extensions — `CrudDrawer`'s field dispatch grows two new `component` types (`select`, `multiselect`) and one new flag (`hideOnCreate`); `CrudTable`'s column rendering grows an optional `render(row)` escape hatch. Needed before any Phase 1 lookup screen can be built, since Item and Party both need field types Phase 0 never required.
2. `utils/constants.js` gets `PARTY_ROLE`/`PARTY_ROLE_OPTIONS`; `utils/queryKeys.js` gets `categoryKeys`/`modelKeys`/`itemKeys`/`partyKeys`/`purchaseOrderKeys`.
3. Catalog domain — `Category`, `Model`, `Item` CRUD, all three through the generic engine, on one tabbed `/catalog` page.
4. Parties domain — full `Party` CRUD (all 4 roles selectable, only `china_vendor` actually used yet) on `/parties`.
5. `utils/currencyUtils.js` + `components/common/CurrencyAmount.jsx` — the RMB→PKR preview math the PO form and PO detail screen both need. Deferred from Phase 0 (§9 of that spec) to here, since this is the first screen that actually needs it.
6. Purchasing domain, `PurchaseOrder` half — hand-written (not generic-engine) screens: list, create form (dynamic line items, live exchange-rate lookup, live RMB/PKR preview), read-only detail.
7. App shell — new routes in `App.jsx`, new nav links in `Navbar.jsx`, new default landing route.

Out of scope, deferred to later phases per PLAN.md's roadmap: `cargo/`, `inventory/`, `sales/`, anything beyond `PaymentMethod` in `payments/`, `expenses/`, `reporting/`, `PartyStatement` (needs the ledger-by-party query, Phase 4), any PO edit/delete/status-transition UI (no such backend route exists — §1.1).

### 1.1 Confirmed API surface (from running backend code, not the spec draft)

Every route below requires `Authorization: Bearer <access_token>` — **there is no unauthenticated route anywhere in Phase 1**, including list/detail `GET`s. Every error body is `{"detail": "..."}`, handled the same way `fetchClient.js` already handles it (phase-0 spec §1.1's note carries over unchanged).

**Global gotcha — every `Decimal` field is a JSON string, not a number.** Verified against pydantic 2.13.4 in `backend/.venv`: `opening_balance`, `rate`, `qty`, `rate_rmb`, `rate_pkr`, `amount_rmb`, `amount_pkr`, `total_rmb`, `total_pkr` all serialize as strings (e.g. `"12.50"`). Never `JSON.parse`/coerce these to `Number` before sending them back in a request body — send back what the form collected. This is the same rule the phase-0 spec already established for `rate`; it now applies to a longer list of fields.

**Global gotcha — numeric-string FK fields are fine to send as strings.** Verified empirically (`M.model_validate_json('{"category_id": "3"}')` → `category_id=3`): Pydantic v2's lax mode coerces a numeric string to `int` for plain `int` fields (as opposed to `Decimal` fields, which stay strings both ways). So a `<select>`'s string value for `category_id`/`model_id`/`item_id`/`party_id` can be sent as-is — no `Number()` cast needed anywhere in this spec.

**Global gotcha — every list endpoint below is `{items, total, page, page_size}` with NO server-side filter or sort param**, ordered by `id` ascending only (`backend/src/crud.py:56`, same for the hand-written `PurchaseOrder` list). Concretely, this means: there is no `?role=china_vendor` filter on `GET /parties`, no `?rate_date=` filter on `GET /purchasing/exchange-rates`, no `?category_id=` filter on `GET /catalog/items`. Every place this spec needs "find the row matching X" (today's exchange rate, china-vendor parties, an item's category/model name), the frontend fetches one page at `page_size=100` and filters/maps client-side. **This is a deliberate, confirmed-with-user scope decision for Phase 1** (§2, decision 1) — it silently stops working once any of these tables grows past 100 rows, which is acceptable for how small this business's catalog/party/rate tables are expected to stay for a while, but should be revisited (server-side filtering, or a searchable combobox instead of a plain `<select>`) if that changes.

| Method | Path | Body | Response | Status | Notes |
|---|---|---|---|---|---|
| GET | `/catalog/categories?page=&page_size=` | — | `{items:[{id,name,is_active}], total, page, page_size}` | 200 | |
| POST | `/catalog/categories` | `{name}` (max 120) | `CategoryRead` | 201 / 409 | 409 on duplicate `name` |
| PUT | `/catalog/categories/{id}` | `{name?}` | `CategoryRead` | 200 / 404 / 409 | |
| DELETE | `/catalog/categories/{id}` | — | — | 204 / 404 | soft delete |
| GET | `/catalog/models?page=&page_size=` | — | `{items:[{id,name,priority,is_active}], total, page, page_size}` | 200 | |
| POST | `/catalog/models` | `{name}` (max 120) | `ModelRead` | 201 / 409 | **`priority` is NOT accepted on create** — always starts at `0` |
| PUT | `/catalog/models/{id}` | `{name?, priority?}` | `ModelRead` | 200 / 404 / 409 | `priority` is only ever settable here |
| DELETE | `/catalog/models/{id}` | — | — | 204 / 404 | soft delete |
| GET | `/catalog/items?page=&page_size=` | — | `{items:[{id,category_id,model_id,sku,variant,is_active}], total, page, page_size}` | 200 | |
| POST | `/catalog/items` | `{category_id, model_id, sku (max 64), variant? (max 64)}` | `ItemRead` | 201 / **409** | **A bad/deleted `category_id` or `model_id` returns 409 `"Item already exists"`, not 404/422** — the generic factory collapses every `IntegrityError` (unique *and* FK violations alike) into that one misleading message. See §5.3. |
| PUT | `/catalog/items/{id}` | `{category_id?, model_id?, variant?}` | `ItemRead` | 200 / 404 / 409 | **`sku` is not updatable** — absent from `ItemUpdate` entirely |
| DELETE | `/catalog/items/{id}` | — | — | 204 / 404 | soft delete |
| GET | `/parties?page=&page_size=` | — | `{items:[PartyRead], total, page, page_size}` | 200 | **No role filter** — returns all parties regardless of role |
| POST | `/parties` | `{name (max120), contact?(max64), address?(max255), roles:[PartyRole] (min 1), opening_balance?:Decimal=0}` | `PartyRead` | 201 / 409 | posts a `LedgerEntry` in the same transaction if `opening_balance != 0` |
| GET | `/parties/{id}` | — | `PartyRead` | 200 / 404 | |
| PUT | `/parties/{id}` | `{name?, contact?, address?, roles?:[PartyRole] (min 1 if present)}` | `PartyRead` | 200 / 404 / 409 | **`opening_balance` cannot be updated** — write-once, absent from `PartyUpdate` |
| DELETE | `/parties/{id}` | — | — | 204 / 404 | soft delete |
| GET | `/purchasing/exchange-rates?page=&page_size=` | — | (unchanged from Phase 0) | 200 | reused as-is for the PO form's rate lookup |
| POST | `/purchasing/purchase-orders` | `{party_id:int, order_date:date, lines:[{item_id:int, qty:Decimal(gt=0,2dp), rate_rmb:Decimal(gt=0,2dp)}] (min 1)}` | `PurchaseOrderRead` | 201 / 404 / 422 / 409 | see error table below |
| GET | `/purchasing/purchase-orders?page=&page_size=` | — | `{items:[PurchaseOrderRead], total, page, page_size}` | 200 | |
| GET | `/purchasing/purchase-orders/{id}` | — | `PurchaseOrderRead` | 200 / 404 | |

`PurchaseOrderRead`: `{id, party_id, order_date, status:"draft", lines:[PurchaseOrderLineRead], total_rmb, total_pkr}`. `PurchaseOrderLineRead`: `{id, item_id, qty, rate_rmb, rate_pkr, amount_rmb, amount_pkr}`. `total_rmb`/`total_pkr`/`amount_rmb`/`amount_pkr` are **server-computed on every response, never stored** — always present, never need a separate fetch. `status` is always `"draft"` — Phase 1 has no status-transition route, so the frontend never needs to render a status picker, only display the value.

**PO creation error cases, in the order the backend checks them:**

| Cause | Status | Detail |
|---|---|---|
| `party_id` doesn't resolve to an active `Party` | 404 | "Party not found" |
| that party's `roles` doesn't include `china_vendor` | 422 | (`PartyRoleMismatch`) |
| no active `ExchangeRate` row with `rate_date == order_date` (**exact match, no "most recent prior rate" fallback**) | 422 | "No exchange rate is set for this order's date" |
| any `item_id` in `lines` doesn't resolve to an active `Item` | 422 | lists the offending id(s) |
| anything else (residual `IntegrityError`) | 409 | generic conflict |

There is **no `PUT`/`DELETE` on `PurchaseOrder`** — once created, a PO is permanent and immutable for the rest of Phase 1. The form has exactly one shot to get it right; there's no edit-after-create flow to build.

---

## 2. Decisions (confirmed with user)

1. **Exchange-rate lookup for the PO form** — fetch `GET /purchasing/exchange-rates?page=1&page_size=100` and search client-side for an exact `rate_date` match against the PO's `order_date`. If not found, the form shows an inline warning and disables submit rather than letting the user hit the backend's 422. This is the single-page approach, not the bounded-multi-page alternative — acceptable because a solo daily-rate cadence keeps this table well under 100 rows for a long time. Revisit (multi-page search, or a backend `?rate_date=` filter) if that stops being true. The same "fetch one `page_size=100` page, filter client-side" pattern is reused for china-vendor parties (§6) and for populating the item/category/model pickers (§4.3, §7.3) — one limitation, applied consistently, not four separate ones.
2. **Party screen scope** — build the full generic `Party` screen now: name, contact, address, a roles multi-select offering all 4 `PartyRole` values, and `opening_balance`. Not a china-vendor-scoped stub. This matches CLAUDE.md's own framing ("one form, `roles` multi-select") and PLAN.md Phase 5's expectation that this exact screen gets reused unchanged when `customer`/`local_vendor` roles start getting used.
3. **Catalog nav layout** — one tabbed `/catalog` route (`Categories | Models | Items`), mirroring Phase 0's tabbed `/settings` exactly, rather than three separate top-level nav entries.
4. **Extend the generic engine, don't bypass it** — `Category`, `Model`, `Item`, and `Party` all stay on `CrudTable`/`CrudDrawer`. The engine grows two new field-`component` types (`select`, `multiselect`) and a `hideOnCreate` flag rather than Item/Party getting bespoke forms. `PurchaseOrder` is the one entity in this phase that does **not** go through the engine — it was never a candidate to (CLAUDE.md's own line: "Transactional entities... get hand-written endpoints because they carry business logic — don't force those through the generic factory" applies identically on the frontend side).

Additional calls made while writing this spec (not asked separately — low-stakes, reversible, and directly implied by the decisions above):

5. **`Item`'s CRUD config is a hook, not a plain object.** Every other lookup config in this codebase (`ExchangeRateCrudConfig`, `PaymentMethodCrudConfig`, and the new `CategoryCrudConfig`/`ModelCrudConfig`/`PartyCrudConfig`) is a static, module-scope object — nothing in them depends on another query's result. `Item` is the exception: its `category_id`/`model_id` select options and its table's category/model-name columns both need `Category`/`Model` lists fetched first. So `ItemCrudConfig.js` exports `useItemCrudConfig()`, called once inside the Items tab (§4.4), which builds and returns the same config shape everything else uses. `CrudTable`/`CrudDrawer` themselves stay unaware of the difference — they just receive a config object either way.
6. **Hook file granularity: keep Phase 0's domain-level split for `purchasing`, use CLAUDE.md's explicit per-entity split for `catalog`.** CLAUDE.md's own §3.3 tree spells out `catalogHooks/` as `categoryQueries.js`/`categoryMutations.js`/`modelQueries.js`/`modelMutations.js`/`itemQueries.js`/`itemMutations.js` (one query/mutation file pair per entity) but spells out `purchasingHooks/` differently in its own illustrative example. Phase 0 already shipped `purchasingHooks/purchasingQueries.js` + `purchasingMutations.js` as one domain-level pair covering `ExchangeRate`; this spec extends those same two files with `PurchaseOrder` hooks rather than fragmenting a working pair into new per-entity files. `partyHooks/partyQueries.js` + `partyMutations.js` follows CLAUDE.md's explicit domain-level naming for that domain (Party is the only entity there, so there's no granularity choice to make). Net effect: this repo has two hook-file granularities side by side, by design, because CLAUDE.md's own example tree shows both — don't "fix" this into false uniformity later.
7. **Default landing route changes from `/settings` to `/purchase-orders`.** Phase 0's `/` redirect target was `/settings` because that was the only screen that existed. PLAN.md Principle 1 — "each phase ends with a screen you open the next morning to run part of the real business" — makes `/purchase-orders` the actual daily-use screen for Phase 1; `/settings` and `/catalog` are supporting config screens, not where a session starts.

---

## 3. Generic CRUD engine extensions

### 3.1 `CrudDrawer.jsx` — new field types and the `hideOnCreate` flag

Three changes to the existing component (full current source already in the repo — this section describes deltas, not a rewrite):

**a) `buildDefaultValues` grows per-component defaults**, since `multiselect` needs `[]` not `''`, and `select` needs its value stringified (Radix `Select` matches against `SelectItem value="..."` strings, but a row's `category_id` comes back as a JSON number):

```javascript
function buildDefaultValues(fields, row) {
  return fields.reduce((acc, field) => {
    if (field.component === 'multiselect') {
      acc[field.name] = row?.[field.name] ?? field.defaultValue ?? [];
    } else if (field.component === 'select') {
      acc[field.name] = row?.[field.name] != null ? String(row[field.name]) : (field.defaultValue ?? '');
    } else {
      acc[field.name] = row?.[field.name] ?? field.defaultValue ?? '';
    }
    return acc;
  }, {});
}
```

**b) The field-rendering loop filters out `hideOnCreate` fields in create mode, and dispatches on `component`** instead of always rendering `FormField`:

```jsx
{config.fields
  .filter((field) => !(mode !== 'edit' && field.hideOnCreate))
  .map((field) => (
    <Controller
      key={field.name}
      name={field.name}
      control={control}
      disabled={isEdit && field.editableOnUpdate === false}
      render={({ field: rhfField }) => {
        if (field.component === 'select') {
          return <FormSelect {...rhfField} label={field.label} options={field.options} error={errors[field.name]?.message} />;
        }
        if (field.component === 'multiselect') {
          return <FormMultiSelect {...rhfField} label={field.label} options={field.options} error={errors[field.name]?.message} />;
        }
        return (
          <FormField
            {...rhfField}
            type={inputTypeFor(field.component)}
            step={field.step}
            label={field.label}
            error={errors[field.name]?.message}
          />
        );
      }}
    />
  ))}
```

`hideOnCreate` is `Model.priority`'s exact use case (§4.2) — `ModelCreate` has no `priority` field at all, so rendering (and registering) it in create mode would collect a value the backend would never accept. `editableOnUpdate: false` (already existed, used by `ExchangeRate.rate_date`) is the mirror-image flag and now also covers `Item.sku` (§4.4, present at create, immutable after).

### 3.2 `CrudTable.jsx` — optional `column.render`

One-line change to the cell-rendering loop, so a column can supply a formatter instead of falling back to raw `String(value)`:

```jsx
{config.columns.map((column) => (
  <TableCell key={column.key}>
    {column.render ? column.render(row) : formatCell(row[column.key])}
  </TableCell>
))}
```

Needed for `Item`'s category/model-name columns (raw `category_id`/`model_id` integers are meaningless in a table) and `Party`'s roles column (an array of enum strings should render as badges, not `"china_vendor,cargo_agent"`).

### 3.3 New component — `components/custom/FormMultiSelect.jsx`

No shadcn primitive in this repo does multi-select today; the simplest fit is a checkbox group (adds one new shadcn primitive, `components/ui/checkbox.jsx`, via `npx shadcn@latest add checkbox` — same generated/don't-hand-edit status as every other `ui/` primitive per CLAUDE.md §3.4 point 4):

```jsx
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';

export function FormMultiSelect({ label, error, options = [], value = [], onChange, name }) {
  const toggle = (optionValue) => {
    onChange(value.includes(optionValue) ? value.filter((v) => v !== optionValue) : [...value, optionValue]);
  };

  return (
    <div className="flex flex-col gap-1.5">
      {label && <Label>{label}</Label>}
      <div className="flex flex-wrap gap-4">
        {options.map((option) => (
          <label key={option.value} htmlFor={`${name}-${option.value}`} className="flex items-center gap-2 text-sm font-normal">
            <Checkbox
              id={`${name}-${option.value}`}
              checked={value.includes(option.value)}
              onCheckedChange={() => toggle(option.value)}
            />
            {option.label}
          </label>
        ))}
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
```

Add the export to `components/custom/index.js` alongside `FormField`/`FormSelect`.

---

## 4. Catalog domain (`Category`, `Model`, `Item`)

### 4.1 `validations/catalogSchemas.js`

```javascript
import { object, string, number } from 'yup';

export const categoryCreateSchema = object({
  name: string().required('Name is required').max(120),
});
export const categoryUpdateSchema = categoryCreateSchema.partial();

export const modelCreateSchema = object({
  name: string().required('Name is required').max(120),
});
// ModelUpdate is a genuinely different field set from ModelCreate (adds `priority`,
// which Create doesn't accept at all — §1.1) — written directly rather than derived
// via .partial(), since .partial() only relaxes required-ness, it can't add a field.
export const modelUpdateSchema = object({
  name: string().max(120),
  priority: number().typeError('Priority must be a number').integer('Priority must be a whole number'),
});

export const itemCreateSchema = object({
  category_id: number().typeError('Select a category').required('Select a category'),
  model_id: number().typeError('Select a model').required('Select a model'),
  sku: string().required('SKU is required').max(64),
  variant: string().max(64).nullable().default(null),
});
// ItemUpdate omits sku entirely (immutable — §1.1) — .omit() rather than .partial()
// alone, same reasoning as ExchangeRateUpdate in the phase-0 spec §8.1.
export const itemUpdateSchema = itemCreateSchema.omit(['sku']).partial();
```

### 4.2 `components/catalog/CategoryCrudConfig.js` / `ModelCrudConfig.js` — plain objects, same shape as Phase 0's configs

```javascript
// CategoryCrudConfig.js
export const categoryCrudConfig = {
  queryKey: categoryKeys,
  useList: useCategories, useCreate: useCreateCategory, useUpdate: useUpdateCategory, useDelete: useDeleteCategory,
  columns: [{ key: 'name', label: 'Name' }],
  createSchema: categoryCreateSchema, updateSchema: categoryUpdateSchema,
  fields: [{ name: 'name', label: 'Name', component: 'text' }],
};

// ModelCrudConfig.js
export const modelCrudConfig = {
  queryKey: modelKeys,
  useList: useModels, useCreate: useCreateModel, useUpdate: useUpdateModel, useDelete: useDeleteModel,
  columns: [{ key: 'name', label: 'Name' }, { key: 'priority', label: 'Priority' }],
  createSchema: modelCreateSchema, updateSchema: modelUpdateSchema,
  fields: [
    { name: 'name', label: 'Name', component: 'text' },
    // Absent from ModelCreate on the backend — hidden until the row exists (§3.1/§1.1).
    { name: 'priority', label: 'Priority (used for reorder ranking from Phase 8)', component: 'number', hideOnCreate: true },
  ],
};
```

### 4.3 `components/catalog/ItemCrudConfig.js` — hook, not a plain object (decision §2.5)

```javascript
import { useCategories } from '@/hooks/catalogHooks/categoryQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { useCreateItem, useUpdateItem, useDeleteItem } from '@/hooks/catalogHooks/itemMutations';
import { itemCreateSchema, itemUpdateSchema } from '@/validations/catalogSchemas';
import { itemKeys } from '@/utils/queryKeys';

const LOOKUP_PAGE = { page: 1, page_size: 100 }; // §2.1's single-page limitation, applied here too

export function useItemCrudConfig() {
  const { data: categoriesData } = useCategories(LOOKUP_PAGE);
  const { data: modelsData } = useModels(LOOKUP_PAGE);

  const categories = categoriesData?.items ?? [];
  const models = modelsData?.items ?? [];
  const categoryNameById = Object.fromEntries(categories.map((c) => [c.id, c.name]));
  const modelNameById = Object.fromEntries(models.map((m) => [m.id, m.name]));

  return {
    queryKey: itemKeys,
    useList: useItems, useCreate: useCreateItem, useUpdate: useUpdateItem, useDelete: useDeleteItem,
    columns: [
      { key: 'sku', label: 'SKU' },
      { key: 'category_id', label: 'Category', render: (row) => categoryNameById[row.category_id] ?? '—' },
      { key: 'model_id', label: 'Model', render: (row) => modelNameById[row.model_id] ?? '—' },
      { key: 'variant', label: 'Variant' },
    ],
    createSchema: itemCreateSchema,
    updateSchema: itemUpdateSchema,
    fields: [
      { name: 'category_id', label: 'Category', component: 'select', options: categories.map((c) => ({ value: String(c.id), label: c.name })) },
      { name: 'model_id', label: 'Model', component: 'select', options: models.map((m) => ({ value: String(m.id), label: m.name })) },
      { name: 'sku', label: 'SKU', component: 'text', editableOnUpdate: false },
      { name: 'variant', label: 'Variant', component: 'text' },
    ],
  };
}
```

**Known gap, accepted for Phase 1 (§1.1's table):** if a `Category`/`Model` is deleted in another tab while this drawer's options were fetched, submitting against the now-stale id returns a 409 `"Item already exists"` — a misleading message the frontend can't fix (it's the backend's generic-CRUD `IntegrityError` handling, shared with every other lookup). `fetchClient`'s existing toast-on-error path surfaces it as-is; no special-case handling for this one entity.

### 4.4 `pages/CatalogPage.jsx` → `containers/CatalogContainer.jsx`

Same tabbed pattern as Phase 0's `SettingsContainer` (§1.1's confirmed layout decision):

```jsx
export function CatalogContainer() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get('tab') || 'categories';

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Catalog</h1>
        <p className="mt-1 text-sm text-muted-foreground">Categories, models, and items — what you buy and sell.</p>
      </div>
      <Tabs value={tab} onValueChange={(v) => setSearchParams({ tab: v })}>
        <TabsList>
          <TabsTrigger value="categories">Categories</TabsTrigger>
          <TabsTrigger value="models">Models</TabsTrigger>
          <TabsTrigger value="items">Items</TabsTrigger>
        </TabsList>
        <TabsContent value="categories" className="pt-4">
          <CrudTable config={categoryCrudConfig} title="Categories" icon={Tag} addLabel="Add category" entityLabel="category" />
        </TabsContent>
        <TabsContent value="models" className="pt-4">
          <CrudTable config={modelCrudConfig} title="Models" icon={Smartphone} addLabel="Add model" entityLabel="model" />
        </TabsContent>
        <TabsContent value="items" className="pt-4">
          <ItemsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ItemsTab() {
  const config = useItemCrudConfig();
  return <CrudTable config={config} title="Items" icon={Package} addLabel="Add item" entityLabel="item" />;
}
```

`ItemsTab` exists specifically so `useItemCrudConfig()` (§4.3) is only called — and only fetches `Category`/`Model` — while the Items tab is actually mounted. Radix's `Tabs.Content` unmounts inactive panels by default, so this isn't wasted: switching to Categories/Models doesn't keep Items' two extra queries alive (though TanStack Query's cache means switching back doesn't re-fetch instantly either).

### 4.5 Hooks/services — mechanical, one pair per entity per decision §2.6

`hooks/catalogHooks/{category,model,item}Queries.js` — each exports one `use<Entity>s(params)` wrapping `useQuery`, identical shape to Phase 0's `purchasingQueries.js`. `hooks/catalogHooks/{category,model,item}Mutations.js` — each exports `useCreate<Entity>`/`useUpdate<Entity>`/`useDelete<Entity>`, each invalidating `<entity>Keys.lists()`, identical shape to Phase 0's `purchasingMutations.js`. `services/catalogService.js` is one file with all twelve functions (`list/create/update/delete` × `Category`/`Model`/`Item`), each a thin `fetchClient` call against `/catalog/categories`, `/catalog/models`, `/catalog/items` respectively — same shape as `purchasingService.js`'s existing exchange-rate functions.

---

## 5. Parties domain

### 5.1 `utils/constants.js` additions

```javascript
export const PARTY_ROLE = {
  CHINA_VENDOR: 'china_vendor',
  CARGO_AGENT: 'cargo_agent',
  CUSTOMER: 'customer',
  LOCAL_VENDOR: 'local_vendor',
};

export const PARTY_ROLE_OPTIONS = [
  { value: PARTY_ROLE.CHINA_VENDOR, label: 'China Vendor' },
  { value: PARTY_ROLE.CARGO_AGENT, label: 'Cargo Agent' },
  { value: PARTY_ROLE.CUSTOMER, label: 'Customer' },
  { value: PARTY_ROLE.LOCAL_VENDOR, label: 'Local Vendor' },
];
```

### 5.2 `validations/partySchemas.js`

```javascript
import { object, string, array, number } from 'yup';
import { PARTY_ROLE } from '@/utils/constants';

export const partyCreateSchema = object({
  name: string().required('Name is required').max(120),
  contact: string().max(64).nullable().default(null),
  address: string().max(255).nullable().default(null),
  roles: array().of(string().oneOf(Object.values(PARTY_ROLE))).min(1, 'Select at least one role').required(),
  opening_balance: number().typeError('Opening balance must be a number').default(0),
});

// opening_balance is write-once on the backend (§1.1) — .omit(), same reasoning as
// ItemUpdate/ExchangeRateUpdate: removed entirely, not merely made optional.
export const partyUpdateSchema = partyCreateSchema.omit(['opening_balance']).partial();
```

### 5.3 `components/parties/PartyRoleBadges.jsx`

Small presentational component, used both by the CRUD config's column `render` and (eventually, Phase 4+) a party detail screen:

```jsx
import { Badge } from '@/components/ui/badge';
import { PARTY_ROLE_OPTIONS } from '@/utils/constants';

const LABEL_BY_VALUE = Object.fromEntries(PARTY_ROLE_OPTIONS.map((o) => [o.value, o.label]));

export function PartyRoleBadges({ roles = [] }) {
  if (roles.length === 0) return <span className="text-muted-foreground">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {roles.map((role) => (
        <Badge key={role} variant="secondary">{LABEL_BY_VALUE[role] ?? role}</Badge>
      ))}
    </div>
  );
}
```

### 5.4 `components/parties/PartyCrudConfig.js` — plain object

```javascript
export const partyCrudConfig = {
  queryKey: partyKeys,
  useList: useParties,
  useCreate: useCreateParty,
  useUpdate: useUpdateParty,
  useDelete: useDeactivateParty, // exported name matches CLAUDE.md's naming (§2.6); config key stays useDelete for CrudTable
  columns: [
    { key: 'name', label: 'Name' },
    { key: 'roles', label: 'Roles', render: (row) => <PartyRoleBadges roles={row.roles} /> },
    { key: 'contact', label: 'Contact' },
  ],
  createSchema: partyCreateSchema,
  updateSchema: partyUpdateSchema,
  fields: [
    { name: 'name', label: 'Party name', component: 'text' },
    { name: 'contact', label: 'Contact', component: 'text' },
    { name: 'address', label: 'Address', component: 'text' },
    { name: 'roles', label: 'Roles', component: 'multiselect', options: PARTY_ROLE_OPTIONS, defaultValue: [] },
    { name: 'opening_balance', label: 'Opening balance', component: 'number', step: '0.01', defaultValue: 0, editableOnUpdate: false },
  ],
};
```

### 5.5 `hooks/partyHooks/partyQueries.js` / `partyMutations.js`

```javascript
// partyQueries.js
export function useParties(params) {
  return useQuery({ queryKey: partyKeys.list(params), queryFn: () => listParties(params) });
}

// Derived, not a separate backend call — filters the one fetched page client-side
// per §2.1's decision. Used by the PO form's vendor picker (§7.3).
export function useChinaVendorParties() {
  const query = useParties({ page: 1, page_size: 100 });
  const vendors = (query.data?.items ?? []).filter((party) => party.roles.includes(PARTY_ROLE.CHINA_VENDOR));
  return { ...query, vendors };
}
```

```javascript
// partyMutations.js — useCreateParty / useUpdateParty / useDeactivateParty,
// each the same useMutation + invalidate(partyKeys.lists()) shape as every
// other domain's mutations file.
```

`services/partyService.js` (singular, per CLAUDE.md §3.3's naming — plural `components/parties/` folder, singular `partyService.js`/`partyHooks/`/`partySchemas.js` file names): `listParties`, `createParty`, `updateParty`, `deactivateParty` — four thin `fetchClient` calls against `/parties`.

### 5.6 `pages/PartiesPage.jsx` → `containers/PartiesContainer.jsx`

No tabs needed — one `CrudTable`, same page shell pattern as `SettingsContainer`/`CatalogContainer` minus the `Tabs` wrapper:

```jsx
export function PartiesContainer() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Parties</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Vendors, agents, and customers — one record per contact. Only the China Vendor role is used so far;
          Customer and Local Vendor arrive in later phases without a new screen.
        </p>
      </div>
      <CrudTable config={partyCrudConfig} title="Parties" icon={Users} addLabel="Add party" entityLabel="party" />
    </div>
  );
}
```

---

## 6. `utils/currencyUtils.js` + `components/common/CurrencyAmount.jsx`

Deferred from Phase 0 (that spec's §2 explicitly named this as out of scope until a screen needed real RMB↔PKR math). This is a **client-side preview only** — it mirrors the backend's rounding so the PO form's live totals don't visibly disagree with what the server returns after submit, but the server's numbers are always the authoritative ones actually stored/displayed post-creation.

```javascript
// utils/currencyUtils.js

// Mirrors backend/src/purchasing/utils.py's money() — ROUND_HALF_UP to 2dp,
// not JS's default float rounding, so the live preview doesn't drift from what
// the server computes with the same inputs.
export function toMoney(value) {
  const num = Number(value);
  if (Number.isNaN(num)) return 0;
  return Math.round((num + Number.EPSILON) * 100) / 100;
}

export function computeRmbAmount(qty, rateRmb) {
  return toMoney(Number(qty) * Number(rateRmb));
}

export function computePkrAmount(qty, rateRmb, exchangeRate) {
  return toMoney(Number(qty) * Number(rateRmb) * Number(exchangeRate));
}

export function formatRMB(value) {
  return `¥${Number(value).toFixed(2)}`;
}

export function formatPKR(value) {
  return `₨${Number(value).toLocaleString('en-PK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
```

```jsx
// components/common/CurrencyAmount.jsx
import { cn } from '@/lib/utils';
import { formatRMB, formatPKR } from '@/utils/currencyUtils';

export function CurrencyAmount({ value, currency = 'PKR', className }) {
  return (
    <span className={cn('font-mono tabular-nums', className)}>
      {currency === 'RMB' ? formatRMB(value) : formatPKR(value)}
    </span>
  );
}
```

---

## 7. Purchasing domain — `PurchaseOrder`

### 7.1 `validations/purchasingSchemas.js` additions

```javascript
import { object, string, number, array } from 'yup';

export const purchaseOrderLineSchema = object({
  item_id: number().typeError('Select an item').required('Select an item'),
  qty: number().typeError('Quantity must be a number').positive('Quantity must be positive').required('Quantity is required'),
  rate_rmb: number().typeError('Rate must be a number').positive('Rate must be positive').required('Rate is required'),
});

export const purchaseOrderCreateSchema = object({
  party_id: number().typeError('Select a vendor').required('Select a vendor'),
  order_date: string().required('Order date is required'),
  lines: array().of(purchaseOrderLineSchema).min(1, 'Add at least one line'),
});
```

Existing `exchangeRateCreateSchema`/`exchangeRateUpdateSchema` (Phase 0) are unchanged.

### 7.2 `queryKeys.js` additions

```javascript
export const categoryKeys = { all: ['categories'], lists: () => [...categoryKeys.all, 'list'], list: (p) => [...categoryKeys.lists(), p] };
export const modelKeys = { all: ['models'], lists: () => [...modelKeys.all, 'list'], list: (p) => [...modelKeys.lists(), p] };
export const itemKeys = { all: ['items'], lists: () => [...itemKeys.all, 'list'], list: (p) => [...itemKeys.lists(), p] };
export const partyKeys = { all: ['parties'], lists: () => [...partyKeys.all, 'list'], list: (p) => [...partyKeys.lists(), p] };

export const purchaseOrderKeys = {
  all: ['purchaseOrders'],
  lists: () => [...purchaseOrderKeys.all, 'list'],
  list: (p) => [...purchaseOrderKeys.lists(), p],
  detail: (id) => [...purchaseOrderKeys.all, 'detail', id],
};
```

`purchaseOrderKeys.detail(id)` is the first `detail()` key factory in this codebase — Phase 0 never needed one (no detail view existed yet). `exchangeRateKeys`/`paymentMethodKeys` stay unchanged.

### 7.3 `hooks/purchasingHooks/purchasingQueries.js` additions

```javascript
export function usePurchaseOrders(params) {
  return useQuery({ queryKey: purchaseOrderKeys.list(params), queryFn: () => listPurchaseOrders(params) });
}

export function usePurchaseOrder(id) {
  return useQuery({ queryKey: purchaseOrderKeys.detail(id), queryFn: () => getPurchaseOrder(id), enabled: Boolean(id) });
}

// Derived from the existing useExchangeRates — no new backend call. Client-side
// exact-date match over one page_size=100 page, per §2.1's decision.
export function useExchangeRateForDate(rateDate) {
  const query = useExchangeRates({ page: 1, page_size: 100 });
  const rate = query.data?.items?.find((r) => r.rate_date === rateDate) ?? null;
  return { ...query, rate };
}
```

`hooks/purchasingHooks/purchasingMutations.js` gets one addition, `useCreatePurchaseOrder`, invalidating `purchaseOrderKeys.lists()` on success — same shape as the existing three mutations. `services/purchasingService.js` gets `listPurchaseOrders`, `getPurchaseOrder`, `createPurchaseOrder` — three thin `fetchClient` calls against `/purchasing/purchase-orders`.

### 7.4 `components/purchasing/form/PurchaseOrderForm.jsx`

The centerpiece of Phase 1 — the one screen this whole phase exists to ship. Dynamic line items via `useFieldArray`, a live exchange-rate lookup gating submit, and a live per-line + total RMB/PKR preview:

```jsx
import { useForm, useFieldArray, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FormField, FormSelect } from '@/components/custom';
import { purchaseOrderCreateSchema } from '@/validations/purchasingSchemas';
import { useCreatePurchaseOrder } from '@/hooks/purchasingHooks/purchasingMutations';
import { useExchangeRateForDate } from '@/hooks/purchasingHooks/purchasingQueries';
import { useChinaVendorParties } from '@/hooks/partyHooks/partyQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { useCategories } from '@/hooks/catalogHooks/categoryQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';
import { computeRmbAmount, computePkrAmount, formatRMB, formatPKR } from '@/utils/currencyUtils';

const LOOKUP_PAGE = { page: 1, page_size: 100 };
const EMPTY_LINE = { item_id: '', qty: '', rate_rmb: '' };
const todayIso = () => new Date().toISOString().slice(0, 10);

export function PurchaseOrderForm({ onSuccess }) {
  const { vendors } = useChinaVendorParties();
  const { data: itemsData } = useItems(LOOKUP_PAGE);
  const { data: categoriesData } = useCategories(LOOKUP_PAGE);
  const { data: modelsData } = useModels(LOOKUP_PAGE);

  const categoryNameById = Object.fromEntries((categoriesData?.items ?? []).map((c) => [c.id, c.name]));
  const modelNameById = Object.fromEntries((modelsData?.items ?? []).map((m) => [m.id, m.name]));
  const itemOptions = (itemsData?.items ?? []).map((item) => ({
    value: String(item.id),
    label: `${modelNameById[item.model_id] ?? '?'} · ${categoryNameById[item.category_id] ?? '?'} — ${item.sku}${item.variant ? ` (${item.variant})` : ''}`,
  }));
  const vendorOptions = vendors.map((v) => ({ value: String(v.id), label: v.name }));

  const { control, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm({
    resolver: yupResolver(purchaseOrderCreateSchema, {}, { raw: true }),
    defaultValues: { party_id: '', order_date: todayIso(), lines: [EMPTY_LINE] },
  });
  const { fields, append, remove } = useFieldArray({ control, name: 'lines' });
  const createMutation = useCreatePurchaseOrder();

  const orderDate = watch('order_date');
  const lines = watch('lines');
  const { rate: exchangeRate, isLoading: isRateLoading } = useExchangeRateForDate(orderDate);

  const totals = lines.reduce((acc, line) => ({
    rmb: acc.rmb + computeRmbAmount(line.qty, line.rate_rmb),
    pkr: acc.pkr + (exchangeRate ? computePkrAmount(line.qty, line.rate_rmb, exchangeRate.rate) : 0),
  }), { rmb: 0, pkr: 0 });

  const onSubmit = async (values) => {
    const created = await createMutation.mutateAsync({
      party_id: values.party_id,
      order_date: values.order_date,
      lines: values.lines.map(({ item_id, qty, rate_rmb }) => ({ item_id, qty, rate_rmb })),
    });
    onSuccess?.(created);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
      <div className="grid gap-4 md:grid-cols-2">
        <Controller name="party_id" control={control} render={({ field }) => (
          <FormSelect {...field} label="Vendor (china vendor)" options={vendorOptions} error={errors.party_id?.message} />
        )} />
        <Controller name="order_date" control={control} render={({ field }) => (
          <FormField {...field} type="date" label="Order date" error={errors.order_date?.message} />
        )} />
      </div>

      {!isRateLoading && !exchangeRate && (
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
            <Controller name={`lines.${index}.rate_rmb`} control={control} render={({ field: f }) => (
              <FormField {...f} type="number" step="0.01" label="Rate (RMB)" error={errors.lines?.[index]?.rate_rmb?.message} />
            )} />
            <div className="flex flex-col justify-end text-sm text-muted-foreground">
              <span>{formatRMB(computeRmbAmount(lines[index]?.qty, lines[index]?.rate_rmb))}</span>
              {exchangeRate && <span>{formatPKR(computePkrAmount(lines[index]?.qty, lines[index]?.rate_rmb, exchangeRate.rate))}</span>}
            </div>
            <Button type="button" variant="ghost" size="icon-sm" onClick={() => remove(index)} disabled={fields.length === 1}>
              <Trash2 className="text-destructive" />
            </Button>
          </div>
        ))}
        <Button type="button" variant="outline" size="sm" onClick={() => append(EMPTY_LINE)} className="self-start">
          <Plus /> Add line
        </Button>
      </div>

      <div className="flex justify-end gap-6 border-t pt-4 text-sm">
        <span>Total RMB: <strong>{formatRMB(totals.rmb)}</strong></span>
        <span>Total PKR: <strong>{formatPKR(totals.pkr)}</strong></span>
      </div>

      <Button type="submit" disabled={isSubmitting || !exchangeRate} className="self-end">
        {isSubmitting ? 'Saving…' : 'Create purchase order'}
      </Button>
    </form>
  );
}
```

Each line's per-row grid (`md:grid-cols-[2fr_1fr_1fr_auto_auto]`) collapses to a single stacked column below `md` by not applying that grid class at all below the breakpoint — per CLAUDE.md §3.7, verify this at ~375px specifically, since a 5-cell inline grid is exactly the shape that overflows a phone screen if the breakpoint prefix is missed.

### 7.5 `components/purchasing/PurchaseOrderDetail.jsx` (read-only)

Renders one `PurchaseOrderRead` (already has every `amount_*`/`total_*` computed server-side — no client math needed here, unlike the form). Resolve `line.item_id` to a label the same way the form does (fetch `Items`/`Categories`/`Models` at `page_size=100`, build id→label maps) rather than displaying a raw id. Shows `order.status` (always `"draft"` in Phase 1 — render as a `Badge`, no picker) and a totals row using `CurrencyAmount`.

### 7.6 `components/purchasing/PurchaseOrderList.jsx`

Table of `usePurchaseOrders({page, page_size}).items`: columns `id`, vendor name (resolve `party_id` via `useParties`'s fetched page — same map pattern), `order_date`, `status` (badge), `total_pkr` (via `CurrencyAmount`). Each row links to `/purchase-orders/{id}`. An "New purchase order" button links to `/purchase-orders/new`. Wrapped in `overflow-x-auto` per CLAUDE.md §3.7, same as every other table in this app.

### 7.7 Pages / containers

```
pages/PurchaseOrdersPage.jsx        → containers/PurchaseOrdersContainer.jsx        (renders PurchaseOrderList + "New" button)
pages/PurchaseOrderCreatePage.jsx   → containers/PurchaseOrderCreateContainer.jsx    (renders PurchaseOrderForm; onSuccess navigates to /purchase-orders/{created.id})
pages/PurchaseOrderDetailPage.jsx   → containers/PurchaseOrderDetailContainer.jsx    (reads :orderId param, usePurchaseOrder(orderId), renders PurchaseOrderDetail or a 404 state)
```

`PurchaseOrderDetailContainer` is where CLAUDE.md §1's "containers read/validate URL params" rule actually matters this phase — `orderId` from `useParams()` must be parsed and passed to `usePurchaseOrder`, and a missing/non-numeric id or a 404 response should render a "not found" state rather than an infinite loading spinner.

---

## 8. App shell updates

### 8.1 `App.jsx` — new routes, new default landing (decision §2.7)

```jsx
<Route element={<ProtectedRoute />}>
  <Route path="/settings" element={<SettingsPage />} />
  <Route path="/catalog" element={<CatalogPage />} />
  <Route path="/parties" element={<PartiesPage />} />
  <Route path="/purchase-orders" element={<PurchaseOrdersPage />} />
  <Route path="/purchase-orders/new" element={<PurchaseOrderCreatePage />} />
  <Route path="/purchase-orders/:orderId" element={<PurchaseOrderDetailPage />} />
  <Route path="/" element={<Navigate to="/purchase-orders" replace />} />
</Route>
```

### 8.2 `Navbar.jsx` — `NAV_LINKS`

```javascript
const NAV_LINKS = [
  { to: '/purchase-orders', label: 'Purchase Orders' },
  { to: '/parties', label: 'Parties' },
  { to: '/catalog', label: 'Catalog' },
  { to: '/settings', label: 'Settings' },
];
```

Four links now fit the collapsing hamburger pattern Phase 0 already built (§6.3 of that spec) — no structural change to `Navbar.jsx` needed beyond this array, but this is exactly the growth CLAUDE.md §3.7 anticipated ("a desktop-width nav bar with nine domains will not fit a phone's width un-collapsed") — verify the mobile menu still opens/closes cleanly with four entries plus sign-out, at ~375px.

---

## 9. Testing checklist (manual, matches PLAN.md's "done when")

1. `/catalog`: add a Category, a Model (no priority field on the create drawer — confirm it's genuinely absent, not just empty), an Item (category/model dropdowns populated from what you just created, SKU required). Edit the Model and set a priority — confirm the create drawer still doesn't show it, only the edit drawer does. Edit the Item — confirm SKU is disabled/read-only, category/model/variant are editable.
2. `/parties`: add a party named as a real vendor, roles = China Vendor only, an opening balance of e.g. 5000. Confirm the row's Roles column shows a badge, not a raw string. Edit the party — confirm `opening_balance` isn't editable (disabled field) while name/contact/address/roles are.
3. On `/settings` → Exchange Rates, confirm today's date has a rate (add one if not).
4. `/purchase-orders/new`: vendor dropdown shows only the china_vendor party from step 2 (not a customer/local_vendor-only party, if you added one to test the roles field). Order date defaults to today. Add two lines against real items; confirm each line's RMB/PKR preview appears live as you type, and the running total at the bottom updates. Submit — lands on the new PO's detail page, showing the same totals the form previewed.
5. Change the PO form's order date to a date with no exchange rate row — confirm the warning appears and the submit button disables, without needing to actually attempt the submit and see a 422.
6. `/purchase-orders`: the list shows the PO just created, vendor name resolved (not a raw `party_id`), status badge reads "draft", total_pkr formatted with `CurrencyAmount`.
7. Resize to ~375px, ~768px, ~1280px: `Navbar` still collapses correctly with 4 links + sign-out; the PO form's per-line grid stacks to one column below `md`; every table (`Categories`/`Models`/`Items`/`Parties`/`PurchaseOrders`) scrolls inside its own container rather than widening the page.
8. Attempt to create an Item with a category/model that gets soft-deleted in another tab first (simulating the stale-options gotcha from §1.1) — confirm the resulting 409 toast doesn't crash the form, even though its message ("Item already exists") is misleading.
