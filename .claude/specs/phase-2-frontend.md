# Phase 2 Frontend — Spec

Source of truth: `PLAN.md` (§ Phase 2 — Cargo & landed cost) for *what*, `CLAUDE.md` (§3) for *how*, and `.claude/specs/phase-2-backend.md` for the backend design — but the API surface table below (§1.1) is re-verified against the **actual running `backend/src/cargo/`, `backend/src/purchasing/`, and `backend/src/parties/` code**, not the design doc, exactly like the phase-1-frontend spec did for Phase 1. Where this doc and the backend spec draft disagree, trust §1.1.

**Done when** (verbatim from PLAN.md): a shipment's freight cost is visibly split across the items in it, and each PO line shows a landed cost, not just its RMB rate.

At the time of writing, `frontend/` already has Phase 0 and Phase 1 shipped in full — auth, the generic `CrudTable`/`CrudDrawer` engine (including the `select`/`multiselect`/`hideOnCreate`/`editableOnUpdate` capabilities Phase 1 added), `ExchangeRate`/`PaymentMethod` lookups on a tabbed `/settings`, full `Category`/`Model`/`Item`/`Party` CRUD, and the hand-written `PurchaseOrder` list/create/detail screens. This spec is additive on top of that tree — nothing in §1–§8 of the phase-1 spec gets removed or renamed.

---

## 1. Scope

Build, in this order (each step independently usable/testable before the next):

1. `utils/constants.js` gets `CARGO_COST_BASIS_CODE`/`CARGO_COST_BASIS_CODE_OPTIONS`; `utils/queryKeys.js` gets `cargoModeKeys`/`cargoCostBasisKeys`/`cargoShipmentKeys`.
2. `hooks/partyHooks/partyQueries.js` gets one addition, `useCargoAgentParties()` — the same client-side role-filter pattern as Phase 1's `useChinaVendorParties()`, now for the `cargo_agent` role.
3. `hooks/purchasingHooks/purchasingQueries.js` gets one addition, `useDraftPurchaseOrders()` — same client-side filter pattern, this time on `status === "draft"`, needed for the "attach open POs" picker.
4. `components/purchasing/PurchaseOrderDetail.jsx` gets two new columns (`landed_cost_pkr`, `amount_landed_pkr`) so a PO's detail page shows its post-allocation numbers once a shipment has run — the one required change to an existing Phase 1 screen.
5. Cargo domain lookups — `CargoMode`, `CargoCostBasis` CRUD, both through the generic engine (no engine changes needed — see §3), added as two new tabs on the existing `/settings` page, same home as `ExchangeRate`/`PaymentMethod`.
6. `utils/currencyUtils.js` gets one addition, `computeCargoAllocation()` — a client-side mirror of the backend's proportional-split-plus-remainder algorithm, for the shipment form's live preview.
7. Cargo domain, `CargoShipment` — hand-written (not generic-engine) screens: list, create form (multi-PO attach, per-line basis-figure inputs, live allocation preview), read-only detail.
8. App shell — new routes in `App.jsx`, new nav link in `Navbar.jsx`, two new tabs in `SettingsContainer.jsx`. Default landing route (`/purchase-orders`) is unchanged — see §2, decision 4.

Out of scope, deferred to later phases per PLAN.md's roadmap: `inventory/` ("Receive" turning a landed-cost line into a `StockLot` is Phase 3), `sales/`, anything beyond lookups in `payments/`, `expenses/`, `reporting/`, `PartyStatement`/cargo-agent balance screen (needs the ledger-by-party query — and per §1.1's flagged gap, cargo shipments don't post a ledger entry at all yet, so this wouldn't be derivable even if built early). No shipment edit/cancel/re-allocate UI — no such backend route exists (§1.1).

### 1.1 Confirmed API surface (from running backend code, not the design draft)

Every route below requires `Authorization: Bearer <access_token>`, same as every route in Phase 0/1 — no exceptions in this phase either. Every error body is `{"detail": "..."}` for a domain `AppException`, or `{"detail": [{"loc":..., "msg":...}]}` for a raw Pydantic validation failure on a malformed body — same dual shape the phase-1 spec flagged, `fetchClient.js` already handles both, no new handling needed.

**Every `Decimal` field is still a JSON string** (phase-1 spec's global gotcha, unchanged): `total_cost_pkr`, `basis_value`, `allocated_cost_pkr`, `landed_cost_pkr`, `amount_landed_pkr` all serialize as strings (e.g. `"12.50"`, `"3.2500"`). Send back exactly what the form collected — never `Number()`-cast a value before it goes into a request body.

**`landed_cost_pkr` is a per-unit rate, not a line total — don't confuse it with `amount_landed_pkr`.** `landed_cost_pkr = rate_pkr + (this line's share of freight ÷ qty)`. `amount_landed_pkr = qty × landed_cost_pkr`, computed server-side, present alongside the existing `amount_rmb`/`amount_pkr`. Both are `null` on a line whose PO hasn't been through a shipment yet — render `—`, don't coerce to `0`.

**No `GET /cargo/shipments/{id}` `role`/`status` filters exist, same limitation as Phase 1's `GET /parties` and `GET /purchasing/purchase-orders`, now extended to two more lookups this phase touches:**
- `GET /parties` still has no `?role=` filter — the cargo-agent picker filters client-side, same as the china-vendor picker (§2.1 of this spec).
- `GET /purchasing/purchase-orders` still has no `?status=` filter — "attach open POs" filters client-side for `status === "draft"`, same `page_size=100` cap and staleness caveat as every other client-side filter in this app.

| Method | Path | Body | Response | Status | Notes |
|---|---|---|---|---|---|
| GET | `/cargo/modes?page=&page_size=` | — | `{items:[{id,name,is_active}], total, page, page_size}` | 200 | plain generic-CRUD lookup, identical shape to `PaymentMethod` |
| POST | `/cargo/modes` | `{name}` (max 64) | `CargoModeRead` | 201 / 409 | 409 on duplicate `name` |
| PUT | `/cargo/modes/{id}` | `{name?}` | `CargoModeRead` | 200 / 404 / 409 | |
| DELETE | `/cargo/modes/{id}` | — | — | 204 / 404 | soft delete |
| GET | `/cargo/cost-bases?page=&page_size=` | — | `{items:[{id,name,code,is_active}], total, page, page_size}` | 200 | |
| POST | `/cargo/cost-bases` | `{name (max64), code}` | `CargoCostBasisRead` | 201 / 409 | `code` must be exactly `"weight"`, `"cbm"`, or `"piece"` |
| PUT | `/cargo/cost-bases/{id}` | `{name?}` | `CargoCostBasisRead` | 200 / 404 / 409 | **`code` is not accepted on update at all** — absent from `CargoCostBasisUpdate`, immutable after creation |
| DELETE | `/cargo/cost-bases/{id}` | — | — | 204 / 404 | soft delete |
| POST | `/cargo/shipments` | see below | `CargoShipmentRead` | 201 / 404 / 422 / 409 | runs the whole allocation in one transaction — see error table |
| GET | `/cargo/shipments?page=&page_size=` | — | `{items:[CargoShipmentRead], total, page, page_size}` | 200 | |
| GET | `/cargo/shipments/{id}` | — | `CargoShipmentRead` | 200 / 404 | |

`CargoShipmentCreate` body: `{cargo_agent_id:int, cargo_mode_id:int, cost_basis_id:int, shipment_date:date, total_cost_pkr:Decimal(gt=0,2dp), purchase_order_ids:[int] (min 1), line_basis_values:[{purchase_order_line_id:int, basis_value:Decimal(gt=0,4dp)}]=[]}`.

`CargoShipmentRead`: `{id, cargo_agent_id, cargo_mode_id, cost_basis_id, shipment_date, total_cost_pkr, allocations:[CargoAllocationRead]}`. `CargoAllocationRead`: `{id, purchase_order_line_id, basis_value, allocated_cost_pkr}` — **note there is no `item_id` or `purchase_order_id` on an allocation row.** Resolving "which item/PO did this allocation cover" requires joining `purchase_order_line_id` back against the already-fetched `PurchaseOrder` list's embedded `lines[]` — see §8.2.

**`purchase_order_ids` attaches whole POs, not individual lines (§2.2 of the backend spec) — the unit the frontend picker offers is a PO, never a line inside one.** Every line belonging to every attached PO gets allocated in that same call; there is no way to ship "half a PO."

**The basis-value rule branches on the selected `CargoCostBasis.code`, and it is a runtime rule, not a Pydantic-expressible one:**
- `code === "piece"`: `line_basis_values` **must be omitted entirely** (empty array `[]` is fine — the check is "any entries at all," not "an empty array"). Sending even one entry raises 422 `MissingBasisValue`, even if that entry is otherwise well-formed. The basis figure for every line is derived server-side from `line.qty` — the frontend never sends it.
- `code === "weight"` or `"cbm"`: every attached line **must** have a matching entry with a positive `basis_value`, or 422 `MissingBasisValue` naming the offending line.

**Shipment creation error cases, in the order the backend checks them:**

| Cause | Status | Detail |
|---|---|---|
| `cargo_agent_id` doesn't resolve to an active `Party` | 404 | "Party not found" |
| that party's `roles` doesn't include `cargo_agent` | 422 | (`PartyRoleMismatch`) |
| `cargo_mode_id` doesn't resolve to an active `CargoMode` | 404 | generic not-found |
| `cost_basis_id` doesn't resolve to an active `CargoCostBasis` | 404 | generic not-found |
| any id in `purchase_order_ids` doesn't resolve to a PO with at least one line | 404 | (`PurchaseOrderNotFound`) |
| any attached line's parent PO has `status != "draft"` (already covered by an earlier shipment) | 422 | (`PurchaseOrderNotOpen`) — this is the real-world case of "someone else allocated this PO since the picker's data was fetched" |
| basis-value rule above is violated | 422 | (`MissingBasisValue`) |
| anything else (residual `IntegrityError`) | 409 | generic conflict |

**There is no `PUT`/`DELETE` on `/cargo/shipments` — a shipment is permanent from the moment it's created, exactly like `PurchaseOrder`.** Every PO it touched flips to `status = "allocated"` and every one of its lines' `landed_cost_pkr` is set, in that same transaction; there is no undo, re-allocate, or edit endpoint. The create form has exactly one shot to get it right.

**`PurchaseOrder.status` now has two values, `"draft" | "allocated"`, not just `"draft"`.** Every screen that renders `order.status` as a bare string/badge (Phase 1's `PurchaseOrderList`/`PurchaseOrderDetail`) already handles this correctly with zero changes — the value just changes at runtime; only the "attach open POs" picker (§1.1 above, §7.3) needs to actually branch on it.

**Confirmed backend gap, carried into this spec rather than silently assumed away:** `cargo/service.py`'s `create_shipment` never posts a `LedgerEntry`, despite the shipment recording a real payable to the `cargo_agent` party (the same shape `purchasing.service.create_purchase_order` *does* post for a china vendor). This deviates from `CLAUDE.md` §4's non-negotiable ("every ledger-affecting action posts a `LedgerEntry`"). Practically: **do not build a "cargo agent balance/statement" screen this phase** — the data to back it doesn't exist in the ledger. If PLAN.md later phases expect one, that's a backend follow-up, not something the frontend can work around by re-deriving from `CargoShipment.total_cost_pkr` (that total isn't attributed to a payment/settlement event the way a party ledger entry would be).

---

## 2. Decisions (confirmed with user)

1. **Cargo agent and open-PO pickers are client-side filters, same pattern as Phase 1.** `useCargoAgentParties()` filters one `page_size=100` fetch of `GET /parties` on `roles.includes('cargo_agent')`; `useDraftPurchaseOrders()` filters one `page_size=100` fetch of `GET /purchasing/purchase-orders` on `status === 'draft'`. Both inherit Phase 1's accepted limitation (silently stops finding rows past 100) and its accepted mitigation (revisit if a backend filter param or a searchable combobox becomes necessary). Not re-litigated here — same call, same scope, one more table.
2. **`CargoMode`/`CargoCostBasis` live on `/settings`, not a new `/cargo` lookup page.** `PLAN.md` calls both "dynamic lookups," same category as `ExchangeRate`/`PaymentMethod`, which already live on `/settings`'s tabs regardless of which domain they belong to (`ExchangeRate` is a `purchasing` concern, `PaymentMethod` a `payments` concern, both under `/settings`). Two more tabs, `Cargo Modes` and `Cargo Cost Bases`, follow the same precedent rather than starting a domain-scoped settings page.
3. **No generic-engine changes needed this phase.** Phase 1 added `select`, `multiselect`, `hideOnCreate`, and `editableOnUpdate` to `CrudDrawer`/`CrudTable` specifically so later lookups wouldn't need bespoke forms. `CargoMode` needs only a `text` field (identical to `PaymentMethod`); `CargoCostBasis` needs `text` + a `select` for `code` with `editableOnUpdate: false` (identical mechanism to `ExchangeRate.rate_date`'s immutability). Both fit the engine exactly as it stands — confirmed by writing out both configs (§7.1) before concluding this, not assumed.
4. **Default landing route stays `/purchase-orders`, not `/cargo-shipments`.** PLAN.md Principle 1 wants "a screen you open the next morning to run part of the real business" — for this business that's still placing purchase orders, which happens far more often than reconciling a cargo shipment (one shipment can consolidate many POs, and shipments happen on a freight schedule, not daily). `/cargo-shipments` gets a nav link and its own routes, not the `/` redirect target.
5. **`purchase_order_ids` is picked with the existing `FormMultiSelect` component, not a new bespoke picker.** `FormMultiSelect` (Phase 1, `components/custom/FormMultiSelect.jsx`) is already a generic checkbox-group over `{value, label}` options bound to an array field — exactly the shape "check every open PO you want to attach" needs. Building a second multi-select component for this one field would duplicate Phase 1's own work; the richer per-PO label (vendor name, date, line count) is just a longer `label` string, not a reason for a new component.
6. **The basis-value-per-line requirement is validated in the component, not in Yup.** `cargoShipmentCreateSchema` covers everything structurally simple (required ids, positive total, at least one attached PO). Whether a positive `basis_value` is required for a given line depends on the *looked-up* `CargoCostBasis.code` for whatever `cost_basis_id` is currently selected — data that lives in a TanStack Query cache, not in the form's own values, so a static Yup schema can't reach it without an awkward context-injection hack. This mirrors the exact precedent Phase 1's `PurchaseOrderForm` already set for its exchange-rate-existence check: not a Yup rule, a computed boolean that disables submit and shows an inline message (§8.1).

---

## 3. Generic CRUD engine

No changes. `CargoMode`/`CargoCostBasis` are the first two lookups since Phase 1 to prove the engine needs nothing new — `select` + `editableOnUpdate` (both added in Phase 1) are sufficient for `CargoCostBasis.code`, and `CargoMode` is a bare `PaymentMethod`-shaped single-field lookup.

---

## 4. `utils/constants.js` and `utils/queryKeys.js` additions

```javascript
// utils/constants.js
export const CARGO_COST_BASIS_CODE = {
  WEIGHT: 'weight',
  CBM: 'cbm',
  PIECE: 'piece',
};

export const CARGO_COST_BASIS_CODE_OPTIONS = [
  { value: CARGO_COST_BASIS_CODE.WEIGHT, label: 'Weight' },
  { value: CARGO_COST_BASIS_CODE.CBM, label: 'CBM' },
  { value: CARGO_COST_BASIS_CODE.PIECE, label: 'Piece' },
];
```

```javascript
// utils/queryKeys.js additions
export const cargoModeKeys = {
  all: ['cargoModes'],
  lists: () => [...cargoModeKeys.all, 'list'],
  list: (params) => [...cargoModeKeys.lists(), params],
};

export const cargoCostBasisKeys = {
  all: ['cargoCostBases'],
  lists: () => [...cargoCostBasisKeys.all, 'list'],
  list: (params) => [...cargoCostBasisKeys.lists(), params],
};

export const cargoShipmentKeys = {
  all: ['cargoShipments'],
  lists: () => [...cargoShipmentKeys.all, 'list'],
  list: (params) => [...cargoShipmentKeys.lists(), params],
  detail: (id) => [...cargoShipmentKeys.all, 'detail', id],
};
```

`purchaseOrderKeys`/`partyKeys` are unchanged in shape — §5/§6 below only add new *hooks*, not new keys, since they derive from data already fetched under the existing `partyKeys.list(...)`/`purchaseOrderKeys.list(...)` cache entries.

---

## 5. Party domain addition

```javascript
// hooks/partyHooks/partyQueries.js — addition
// Derived, not a separate backend call — GET /parties has no role filter (§1.1), so
// this filters the one fetched page client-side, same pattern as useChinaVendorParties.
export function useCargoAgentParties() {
  const query = useParties(LOOKUP_PAGE);
  const agents = (query.data?.items ?? []).filter((party) => party.roles.includes(PARTY_ROLE.CARGO_AGENT));
  return { ...query, agents };
}
```

No changes to `partyMutations.js`, `partyService.js`, or `PartyCrudConfig.js` — a `Party` gets the `cargo_agent` role through the existing generic `Party` CRUD screen (`roles` multiselect already offers all four `PartyRole` values since Phase 1), no new UI.

---

## 6. Purchasing domain changes

### 6.1 `hooks/purchasingHooks/purchasingQueries.js` — addition

```javascript
// Derived, not a separate backend call — no ?status= filter exists (§1.1), so this
// fetches one page_size=100 page and filters client-side, same pattern as
// useExchangeRateForDate/useChinaVendorParties.
export function useDraftPurchaseOrders() {
  const query = usePurchaseOrders(LOOKUP_PAGE);
  const draftOrders = (query.data?.items ?? []).filter((order) => order.status === 'draft');
  return { ...query, draftOrders };
}
```

### 6.2 `components/purchasing/PurchaseOrderDetail.jsx` — two new columns

The lines table gains `Landed cost/unit (PKR)` and `Amount landed (PKR)` columns after the existing `Amount (PKR)` column, both rendering `—` when `null` (a line whose PO hasn't been through a cargo shipment yet):

```jsx
<TableHead>Landed cost/unit</TableHead>
<TableHead className="text-right">Amount landed</TableHead>
```
```jsx
<TableCell>
  {line.landed_cost_pkr != null ? <CurrencyAmount value={line.landed_cost_pkr} /> : '—'}
</TableCell>
<TableCell className="text-right">
  {line.amount_landed_pkr != null ? <CurrencyAmount value={line.amount_landed_pkr} /> : '—'}
</TableCell>
```

No changes needed to `PurchaseOrderList.jsx` — its `status` badge already renders whatever string the backend returns; `"allocated"` displays with zero code changes, same `<Badge variant="secondary">{order.status}</Badge>`.

---

## 7. Cargo domain — `CargoMode` / `CargoCostBasis` (generic CRUD)

### 7.1 `validations/cargoSchemas.js`

```javascript
import { object, string } from 'yup';
import { CARGO_COST_BASIS_CODE } from '@/utils/constants';

export const cargoModeCreateSchema = object({
  name: string().required('Name is required').max(64),
});
export const cargoModeUpdateSchema = cargoModeCreateSchema.partial();

export const cargoCostBasisCreateSchema = object({
  name: string().required('Name is required').max(64),
  code: string()
    .oneOf(Object.values(CARGO_COST_BASIS_CODE), 'Select a cost basis code')
    .required('Select a cost basis code'),
});
// code is immutable after creation (backend CargoCostBasisUpdate omits it entirely,
// §1.1) — .omit(), same reasoning as ItemUpdate/PartyUpdate in the phase-1 spec.
export const cargoCostBasisUpdateSchema = cargoCostBasisCreateSchema.omit(['code']).partial();
```

### 7.2 `services/cargoService.js` — one file, mirrors `purchasingService.js`'s shape

```javascript
import { fetchClient } from '@/middleware/fetchClient';
import { buildQueryString } from '@/utils/queryParams';

export async function listCargoModes(params) {
  const { data } = await fetchClient.get(`/cargo/modes${buildQueryString(params)}`);
  return data;
}
export async function createCargoMode(payload) {
  const { data } = await fetchClient.post('/cargo/modes', payload);
  return data;
}
export async function updateCargoMode({ id, ...payload }) {
  const { data } = await fetchClient.put(`/cargo/modes/${id}`, payload);
  return data;
}
export async function deleteCargoMode(id) {
  await fetchClient.delete(`/cargo/modes/${id}`);
}

export async function listCargoCostBases(params) {
  const { data } = await fetchClient.get(`/cargo/cost-bases${buildQueryString(params)}`);
  return data;
}
export async function createCargoCostBasis(payload) {
  const { data } = await fetchClient.post('/cargo/cost-bases', payload);
  return data;
}
export async function updateCargoCostBasis({ id, ...payload }) {
  const { data } = await fetchClient.put(`/cargo/cost-bases/${id}`, payload);
  return data;
}
export async function deleteCargoCostBasis(id) {
  await fetchClient.delete(`/cargo/cost-bases/${id}`);
}

export async function listCargoShipments(params) {
  const { data } = await fetchClient.get(`/cargo/shipments${buildQueryString(params)}`);
  return data;
}
export async function getCargoShipment(id) {
  const { data } = await fetchClient.get(`/cargo/shipments/${id}`);
  return data;
}
export async function createCargoShipment(payload) {
  const { data } = await fetchClient.post('/cargo/shipments', payload);
  return data;
}
```

### 7.3 `hooks/cargoHooks/cargoQueries.js` / `cargoMutations.js` — one domain-level pair

CLAUDE.md §3.3's own illustrative tree spells out `cargoHooks/` as exactly `(cargoQueries.js, cargoMutations.js)` — a domain-level pair, not per-entity like `catalogHooks/`. No granularity decision to make here; follow the tree as written.

```javascript
// hooks/cargoHooks/cargoQueries.js
import { useQuery } from '@tanstack/react-query';
import { cargoModeKeys, cargoCostBasisKeys, cargoShipmentKeys } from '@/utils/queryKeys';
import { listCargoModes, listCargoCostBases, listCargoShipments, getCargoShipment } from '@/services/cargoService';

export function useCargoModes(params) {
  return useQuery({ queryKey: cargoModeKeys.list(params), queryFn: () => listCargoModes(params) });
}
export function useCargoCostBases(params) {
  return useQuery({ queryKey: cargoCostBasisKeys.list(params), queryFn: () => listCargoCostBases(params) });
}
export function useCargoShipments(params) {
  return useQuery({ queryKey: cargoShipmentKeys.list(params), queryFn: () => listCargoShipments(params) });
}
export function useCargoShipment(id) {
  return useQuery({
    queryKey: cargoShipmentKeys.detail(id),
    queryFn: () => getCargoShipment(id),
    enabled: Boolean(id),
  });
}
```

```javascript
// hooks/cargoHooks/cargoMutations.js
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { cargoModeKeys, cargoCostBasisKeys, cargoShipmentKeys, purchaseOrderKeys } from '@/utils/queryKeys';
import * as cargoService from '@/services/cargoService';

export function useCreateCargoMode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cargoService.createCargoMode,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cargoModeKeys.lists() }),
  });
}
export function useUpdateCargoMode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cargoService.updateCargoMode,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cargoModeKeys.lists() }),
  });
}
export function useDeleteCargoMode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cargoService.deleteCargoMode,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cargoModeKeys.lists() }),
  });
}

export function useCreateCargoCostBasis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cargoService.createCargoCostBasis,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cargoCostBasisKeys.lists() }),
  });
}
export function useUpdateCargoCostBasis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cargoService.updateCargoCostBasis,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cargoCostBasisKeys.lists() }),
  });
}
export function useDeleteCargoCostBasis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cargoService.deleteCargoCostBasis,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cargoCostBasisKeys.lists() }),
  });
}

export function useCreateCargoShipment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cargoService.createCargoShipment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cargoShipmentKeys.lists() });
      // A shipment mutates every attached PO's status AND every one of its lines'
      // landed_cost_pkr in the same backend transaction (§1.1). Invalidating just
      // purchaseOrderKeys.lists() would leave a PurchaseOrderDetail page open in
      // another tab showing stale (null) landed costs — invalidate the whole
      // purchaseOrders key space (lists + every cached detail) instead, the same
      // cross-screen invalidation CLAUDE.md §3.4 describes for PurchaseOrderForm.
      queryClient.invalidateQueries({ queryKey: purchaseOrderKeys.all });
    },
  });
}
```

### 7.4 `components/cargo/CargoModeCrudConfig.js` / `CargoCostBasisCrudConfig.js` — plain objects

```javascript
// CargoModeCrudConfig.js
export const cargoModeCrudConfig = {
  queryKey: cargoModeKeys,
  useList: useCargoModes,
  useCreate: useCreateCargoMode,
  useUpdate: useUpdateCargoMode,
  useDelete: useDeleteCargoMode,
  columns: [{ key: 'name', label: 'Name' }],
  createSchema: cargoModeCreateSchema,
  updateSchema: cargoModeUpdateSchema,
  fields: [{ name: 'name', label: 'Name', component: 'text' }],
};

// CargoCostBasisCrudConfig.js
export const cargoCostBasisCrudConfig = {
  queryKey: cargoCostBasisKeys,
  useList: useCargoCostBases,
  useCreate: useCreateCargoCostBasis,
  useUpdate: useUpdateCargoCostBasis,
  useDelete: useDeleteCargoCostBasis,
  columns: [
    { key: 'name', label: 'Name' },
    { key: 'code', label: 'Code' },
  ],
  createSchema: cargoCostBasisCreateSchema,
  updateSchema: cargoCostBasisUpdateSchema,
  fields: [
    { name: 'name', label: 'Name', component: 'text' },
    // Immutable after creation (§1.1/§7.1) — same mechanism as ExchangeRate.rate_date.
    { name: 'code', label: 'Code', component: 'select', options: CARGO_COST_BASIS_CODE_OPTIONS, editableOnUpdate: false },
  ],
};
```

---

## 8. Cargo domain — `CargoShipment` (hand-written, transactional)

### 8.1 `utils/currencyUtils.js` — addition

Client-side mirror of `cargo/service.py`'s allocation algorithm (backend spec §5.1 step 6): proportional split by basis value, with the last line (by ascending `id`) absorbing the rounding remainder so the preview's total always matches `total_cost_pkr` exactly, same as the server's guarantee.

```javascript
// Mirrors backend/src/cargo/service.py's create_shipment allocation math (§5.1 of
// the backend spec): proportional split by basis value, remainder-corrected on the
// last line (ordered by ascending id) so allocated amounts always sum to the total.
export function computeCargoAllocation({ lines, basisValues, totalCostPkr }) {
  const total = Number(totalCostPkr);
  const ordered = [...lines].sort((a, b) => a.id - b.id);
  const totalBasis = ordered.reduce((sum, line) => sum + Number(basisValues[line.id] ?? 0), 0);
  if (!total || !totalBasis) return {};

  let allocatedSoFar = 0;
  const result = {};
  ordered.forEach((line, index) => {
    const isLast = index === ordered.length - 1;
    const allocatedCostPkr = isLast
      ? toMoney(total - allocatedSoFar)
      : toMoney((total * Number(basisValues[line.id] ?? 0)) / totalBasis);
    if (!isLast) allocatedSoFar += allocatedCostPkr;
    result[line.id] = {
      allocatedCostPkr,
      landedCostPkr: toMoney(Number(line.rate_pkr) + allocatedCostPkr / Number(line.qty)),
    };
  });
  return result;
}
```

### 8.2 `components/cargo/form/CargoShipmentForm.jsx` — the centerpiece of Phase 2

Fetches draft POs and cargo agents client-side-filtered (§5, §6.1), lets the user pick a basis, attach POs via `FormMultiSelect`, enter a per-line basis figure (or nothing, for `piece`), and previews the allocation live before submit:

```jsx
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Button } from '@/components/ui/button';
import { FormField, FormSelect, FormMultiSelect } from '@/components/custom';
import { cargoShipmentCreateSchema } from '@/validations/cargoSchemas';
import { useCreateCargoShipment } from '@/hooks/cargoHooks/cargoMutations';
import { useCargoModes, useCargoCostBases } from '@/hooks/cargoHooks/cargoQueries';
import { useCargoAgentParties } from '@/hooks/partyHooks/partyQueries';
import { useDraftPurchaseOrders } from '@/hooks/purchasingHooks/purchasingQueries';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { useCategories } from '@/hooks/catalogHooks/categoryQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';
import { CARGO_COST_BASIS_CODE } from '@/utils/constants';
import { toMoney, computeCargoAllocation, formatPKR } from '@/utils/currencyUtils';

const LOOKUP_PAGE = { page: 1, page_size: 100 };
const todayIso = () => new Date().toISOString().slice(0, 10);

export function CargoShipmentForm({ onSuccess }) {
  const { agents } = useCargoAgentParties();
  const { data: modesData } = useCargoModes(LOOKUP_PAGE);
  const { data: costBasesData } = useCargoCostBases(LOOKUP_PAGE);
  const { draftOrders } = useDraftPurchaseOrders();
  const { data: partiesData } = useParties(LOOKUP_PAGE);
  const { data: itemsData } = useItems(LOOKUP_PAGE);
  const { data: categoriesData } = useCategories(LOOKUP_PAGE);
  const { data: modelsData } = useModels(LOOKUP_PAGE);

  const vendorNameById = Object.fromEntries((partiesData?.items ?? []).map((p) => [p.id, p.name]));
  const itemById = Object.fromEntries((itemsData?.items ?? []).map((i) => [i.id, i]));
  const categoryNameById = Object.fromEntries((categoriesData?.items ?? []).map((c) => [c.id, c.name]));
  const modelNameById = Object.fromEntries((modelsData?.items ?? []).map((m) => [m.id, m.name]));

  function lineLabel(line) {
    const item = itemById[line.item_id];
    if (!item) return `Item #${line.item_id}`;
    const parts = [modelNameById[item.model_id], categoryNameById[item.category_id], item.sku].filter(Boolean);
    return parts.join(' · ') + (item.variant ? ` (${item.variant})` : '');
  }

  const agentOptions = agents.map((a) => ({ value: String(a.id), label: a.name }));
  const modeOptions = (modesData?.items ?? []).map((m) => ({ value: String(m.id), label: m.name }));
  const costBasisOptions = (costBasesData?.items ?? []).map((b) => ({ value: String(b.id), label: b.name }));
  const poOptions = draftOrders.map((po) => ({
    value: String(po.id),
    label: `#${po.id} · ${vendorNameById[po.party_id] ?? `Party #${po.party_id}`} · ${po.order_date} · ${po.lines.length} line(s)`,
  }));

  const {
    control,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(cargoShipmentCreateSchema, {}, { raw: true }),
    defaultValues: {
      cargo_agent_id: '',
      cargo_mode_id: '',
      cost_basis_id: '',
      shipment_date: todayIso(),
      total_cost_pkr: '',
      purchase_order_ids: [],
      basisValues: {},
    },
  });
  const createMutation = useCreateCargoShipment();

  const selectedPoIds = (watch('purchase_order_ids') ?? []).map(Number);
  const costBasisId = watch('cost_basis_id');
  const totalCostPkr = watch('total_cost_pkr');
  const basisValues = watch('basisValues') ?? {};

  const selectedCostBasis = (costBasesData?.items ?? []).find((b) => String(b.id) === String(costBasisId));
  const isPieceBasis = selectedCostBasis?.code === CARGO_COST_BASIS_CODE.PIECE;

  const selectedLines = draftOrders
    .filter((po) => selectedPoIds.includes(po.id))
    .flatMap((po) => po.lines.map((line) => ({ ...line, poId: po.id })));

  // Piece basis derives its figure from each line's own qty — never user-entered;
  // the backend rejects any line_basis_values entries at all when code === "piece" (§1.1).
  const effectiveBasisValues = isPieceBasis
    ? Object.fromEntries(selectedLines.map((l) => [l.id, l.qty]))
    : basisValues;

  const missingBasisValues =
    !isPieceBasis &&
    Boolean(selectedCostBasis) &&
    selectedLines.some((l) => !effectiveBasisValues[l.id] || Number(effectiveBasisValues[l.id]) <= 0);

  const allocationPreview =
    selectedCostBasis && totalCostPkr && !missingBasisValues
      ? computeCargoAllocation({ lines: selectedLines, basisValues: effectiveBasisValues, totalCostPkr })
      : {};

  const onSubmit = async (values) => {
    try {
      const created = await createMutation.mutateAsync({
        cargo_agent_id: values.cargo_agent_id,
        cargo_mode_id: values.cargo_mode_id,
        cost_basis_id: values.cost_basis_id,
        shipment_date: values.shipment_date,
        total_cost_pkr: values.total_cost_pkr,
        purchase_order_ids: values.purchase_order_ids,
        line_basis_values: isPieceBasis
          ? []
          : selectedLines.map((l) => ({
              purchase_order_line_id: l.id,
              basis_value: values.basisValues?.[l.id] ?? '',
            })),
      });
      onSuccess?.(created);
    } catch {
      // fetchClient already toasted the backend's error detail (role mismatch, a PO
      // that got allocated by someone else since this form's data was fetched, a
      // missing basis figure) — keep the form open to fix and retry, same pattern
      // as PurchaseOrderForm.
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
      <div className="grid gap-4 md:grid-cols-2">
        <Controller
          name="cargo_agent_id"
          control={control}
          render={({ field }) => (
            <FormSelect {...field} label="Cargo agent" placeholder="Select an agent" options={agentOptions} error={errors.cargo_agent_id?.message} />
          )}
        />
        <Controller
          name="shipment_date"
          control={control}
          render={({ field }) => <FormField {...field} type="date" label="Shipment date" error={errors.shipment_date?.message} />}
        />
        <Controller
          name="cargo_mode_id"
          control={control}
          render={({ field }) => (
            <FormSelect {...field} label="Cargo mode" placeholder="Sea or Air" options={modeOptions} error={errors.cargo_mode_id?.message} />
          )}
        />
        <Controller
          name="cost_basis_id"
          control={control}
          render={({ field }) => (
            <FormSelect {...field} label="Cost basis" placeholder="Weight, CBM, or Piece" options={costBasisOptions} error={errors.cost_basis_id?.message} />
          )}
        />
        <Controller
          name="total_cost_pkr"
          control={control}
          render={({ field }) => (
            <FormField {...field} type="number" step="0.01" label="Total freight cost (PKR)" error={errors.total_cost_pkr?.message} />
          )}
        />
      </div>

      <Controller
        name="purchase_order_ids"
        control={control}
        render={({ field }) => (
          <FormMultiSelect {...field} label="Attach open purchase orders" options={poOptions} error={errors.purchase_order_ids?.message} />
        )}
      />
      {poOptions.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No draft purchase orders are open to attach — every PO has already been allocated to a shipment.
        </p>
      )}

      {selectedLines.length > 0 && selectedCostBasis && (
        <div className="flex flex-col gap-3 rounded-lg border p-3">
          <p className="text-sm font-medium text-foreground">
            Split {formatPKR(toMoney(totalCostPkr || 0))} across {selectedLines.length} line(s) by {selectedCostBasis.name}
          </p>
          {selectedLines.map((line) => (
            <div key={line.id} className="grid gap-3 md:grid-cols-[2fr_1fr_1fr_1fr] md:items-center">
              <span className="text-sm">
                PO #{line.poId} — {lineLabel(line)} · qty {line.qty}
              </span>
              {isPieceBasis ? (
                <span className="text-sm text-muted-foreground">Basis: {line.qty} (piece count)</span>
              ) : (
                <Controller
                  name={`basisValues.${line.id}`}
                  control={control}
                  render={({ field }) => <FormField {...field} type="number" step="0.0001" label="Basis figure" />}
                />
              )}
              <span className="text-sm text-muted-foreground">
                Allocated: {allocationPreview[line.id] ? formatPKR(allocationPreview[line.id].allocatedCostPkr) : '—'}
              </span>
              <span className="text-sm text-muted-foreground">
                Landed/unit: {allocationPreview[line.id] ? formatPKR(allocationPreview[line.id].landedCostPkr) : '—'}
              </span>
            </div>
          ))}
          {missingBasisValues && (
            <p className="text-sm text-destructive">Enter a positive basis figure for every attached line before submitting.</p>
          )}
        </div>
      )}

      <Button type="submit" size="lg" disabled={isSubmitting || selectedLines.length === 0 || missingBasisValues} className="self-end">
        {isSubmitting ? 'Saving…' : 'Create shipment'}
      </Button>
    </form>
  );
}
```

Each line's per-row grid (`md:grid-cols-[2fr_1fr_1fr_1fr]`) stacks to one column below `md`, same CLAUDE.md §3.7 rule `PurchaseOrderForm`'s line grid already follows — verify at ~375px.

**Note on `basisValues` form state**: toggling a PO off in the `FormMultiSelect` doesn't unregister its lines' `basisValues.{id}` entries from React Hook Form's internal state — they just become irrelevant, since `selectedLines` (and therefore `onSubmit`'s payload and the preview) is always recomputed from the *currently* checked PO ids. This is intentional, not a bug to fix: re-checking the same PO restores its previously-typed basis figures for free.

### 8.3 `components/cargo/CargoShipmentDetail.jsx` — read-only

An allocation row (`CargoAllocationRead`) carries only `purchase_order_line_id`, `basis_value`, `allocated_cost_pkr` — no `item_id` or PO reference (§1.1). Resolving a human-readable label requires flattening every fetched `PurchaseOrder`'s embedded `lines[]` into one lookup map keyed by line id:

```jsx
const lineContextById = Object.fromEntries(
  (ordersData?.items ?? []).flatMap((po) => po.lines.map((line) => [line.id, { po, line }])),
);

function lineLabel(lineId) {
  const ctx = lineContextById[lineId];
  if (!ctx) return `Line #${lineId}`;
  const item = itemById[ctx.line.item_id];
  const itemPart = item
    ? [modelNameById[item.model_id], categoryNameById[item.category_id], item.sku].filter(Boolean).join(' · ')
    : `Item #${ctx.line.item_id}`;
  return `PO #${ctx.po.id} — ${itemPart}`;
}
```

`ordersData` here is `usePurchaseOrders(LOOKUP_PAGE)` — the **unfiltered** list (not `useDraftPurchaseOrders()`), since a shipment's allocations reference lines whose parent PO is now `"allocated"`, not `"draft"`. The rest of the component renders the shipment header (agent name via `useParties`, mode name via `useCargoModes`, cost basis name via `useCargoCostBases`, `shipment_date`) and a table of `shipment.allocations` with columns `Line` (via `lineLabel`), `Basis figure` (`allocation.basis_value`), `Allocated cost` (`<CurrencyAmount value={allocation.allocated_cost_pkr} />`), plus a total row for `shipment.total_cost_pkr` — same visual shape as `PurchaseOrderDetail.jsx`.

### 8.4 `components/cargo/CargoShipmentList.jsx`

Same shape as `PurchaseOrderList.jsx`: a `Card` wrapping a table of `useCargoShipments({page, page_size}).items`, columns `ID` (links to `/cargo-shipments/{id}`), `Agent` (resolve `cargo_agent_id` via `useParties`'s fetched page), `Mode` (resolve `cargo_mode_id` via `useCargoModes`), `Cost basis` (resolve `cost_basis_id` via `useCargoCostBases`), `Shipment date`, `Total cost` (`CurrencyAmount`). A "New shipment" button links to `/cargo-shipments/new`. Wrapped in `overflow-x-auto`, per CLAUDE.md §3.7, same as every other table in this app.

### 8.5 Pages / containers

```
pages/CargoShipmentsPage.jsx        → containers/CargoShipmentsContainer.jsx        (renders CargoShipmentList + "New" button)
pages/CargoShipmentCreatePage.jsx   → containers/CargoShipmentCreateContainer.jsx    (renders CargoShipmentForm; onSuccess navigates to /cargo-shipments/{created.id})
pages/CargoShipmentDetailPage.jsx   → containers/CargoShipmentDetailContainer.jsx    (reads :shipmentId param, useCargoShipment(shipmentId), renders CargoShipmentDetail or a "not found" state)
```

Same three-file shape as Phase 1's `PurchaseOrder*` pages/containers (§7.7 of that spec) — `CargoShipmentDetailContainer` is where the `:shipmentId` param gets parsed and validated (`Number.isInteger(id) && id > 0`) exactly like `PurchaseOrderDetailContainer` already does for `:orderId`.

---

## 9. App shell updates

### 9.1 `App.jsx` — new routes

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
  <Route path="/" element={<Navigate to="/purchase-orders" replace />} />
</Route>
```

Default landing route unchanged (§2, decision 4).

### 9.2 `Navbar.jsx` — `NAV_LINKS`

```javascript
const NAV_LINKS = [
  { to: '/purchase-orders', label: 'Purchase Orders' },
  { to: '/cargo-shipments', label: 'Cargo Shipments' },
  { to: '/parties', label: 'Parties' },
  { to: '/catalog', label: 'Catalog' },
  { to: '/settings', label: 'Settings' },
];
```

Five links now fit the same collapsing hamburger pattern Phase 0 built and Phase 1 already stretched to four — verify the mobile menu still opens/closes cleanly with five entries plus sign-out, at ~375px, per CLAUDE.md §3.7.

### 9.3 `containers/SettingsContainer.jsx` — two new tabs

```jsx
<TabsList>
  <TabsTrigger value="exchange-rates"><ArrowLeftRight className="size-4" />Exchange Rates</TabsTrigger>
  <TabsTrigger value="payment-methods"><Wallet className="size-4" />Payment Methods</TabsTrigger>
  <TabsTrigger value="cargo-modes"><Truck className="size-4" />Cargo Modes</TabsTrigger>
  <TabsTrigger value="cargo-cost-bases"><Scale className="size-4" />Cost Bases</TabsTrigger>
</TabsList>
<TabsContent value="cargo-modes" className="pt-4">
  <CrudTable
    config={cargoModeCrudConfig}
    title="Cargo Modes"
    description="Sea, Air — how a shipment travels."
    icon={Truck}
    addLabel="Add mode"
    entityLabel="cargo mode"
  />
</TabsContent>
<TabsContent value="cargo-cost-bases" className="pt-4">
  <CrudTable
    config={cargoCostBasisCrudConfig}
    title="Cargo Cost Bases"
    description="How a shipment's freight cost splits across its lines — Weight, CBM, or Piece."
    icon={Scale}
    addLabel="Add cost basis"
    entityLabel="cost basis"
  />
</TabsContent>
```

`DEFAULT_TAB` stays `'exchange-rates'` — no change to which tab opens first.

---

## 10. Testing checklist (manual, matches PLAN.md's "done when")

1. On `/settings`, add a Cargo Mode ("Sea") and two Cargo Cost Bases ("Weight" → code `weight`, "Piece" → code `piece`). Edit the "Weight" row — confirm `code` renders disabled/read-only in the edit drawer while `name` stays editable.
2. On `/parties`, add a party with role Cargo Agent only (or add that role to an existing party).
3. Create at least two draft POs on `/purchase-orders` (Phase 1 flow) against a china vendor, each with at least one line, so there's something to attach.
4. `/cargo-shipments/new`: confirm the agent dropdown shows only the cargo-agent party from step 2. Pick "Weight" as the cost basis, attach both draft POs — confirm every line from both POs appears in the allocation section with a basis-figure input, and the submit button is disabled until every line has a positive figure. Enter a total cost and basis figures — confirm the live "Allocated" and "Landed/unit" columns update per line, and their sum (mentally or by inspection) matches the entered total.
5. Submit — lands on the new shipment's detail page, showing the same allocations you just previewed.
6. Return to `/purchase-orders` — confirm the two POs you attached now show status "allocated," and their detail pages show non-null landed cost columns matching what the shipment preview showed.
7. `/cargo-shipments/new` again — confirm the two POs from step 3 no longer appear in the "Attach open purchase orders" picker (they're `allocated`, not `draft`).
8. Repeat steps 3–5 with the "Piece" cost basis on a fresh draft PO — confirm no basis-figure inputs render for any line (each shows "Basis: {qty} (piece count)" instead), and the created shipment's allocations split proportionally to each line's `qty`.
9. Resize to ~375px, ~768px, ~1280px: `Navbar` still collapses correctly with 5 links + sign-out; the shipment form's per-line grid stacks to one column below `md`; the `CargoShipmentList`/`CargoShipmentDetail` tables scroll inside their own container rather than widening the page; the `Settings` tab bar with 4 tabs doesn't overflow awkwardly on a phone.
10. Attempt to attach a PO that's simultaneously allocated by a second browser tab's shipment submission first (simulating the `PurchaseOrderNotOpen` race, §1.1) — confirm the 422 toast surfaces cleanly and the form stays open rather than crashing.
