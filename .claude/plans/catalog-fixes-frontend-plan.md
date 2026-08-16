# Catalog Fixes — Frontend: searchable, SKU+model item picker

## Context

Companion to `catalog-fixes-backend-plan.md` — see that doc's Context for the full three-problem background (`CATALOG_FIXES_PLAN.md`). This is the frontend half of the one in-scope piece: the item picker in the Sales Order and Purchase Order forms was a plain, unsearchable `FormSelect` dropdown labeled with bare SKU only (commit `044dcec` had simplified it to SKU-alone), which made it hard to find the right item once several items share similar SKUs. **Status: complete and verified.**

A Plan agent reconciled the approach against the real current file contents before any code was written and confirmed: `FormCombobox` (`components/custom/FormCombobox.jsx`) already exists and is already used identically in `PaymentForm.jsx`, its prop contract is a strict superset of `FormSelect`'s so the `Controller` wiring needed zero changes, and `ItemCrudConfig.js` already has the exact `modelNameById` lookup pattern needed to enrich the label — so this was a same-shape reuse of existing pieces, not new component work.

## Files changed

- `frontend/src/components/sales/form/SalesOrderForm.jsx`
- `frontend/src/components/purchasing/form/PurchaseOrderForm.jsx`

Identical shape in both (this codebase's convention is to duplicate a two-call-site change rather than extract an abstraction — `ItemCrudConfig.js`'s own inline `modelNameById` is the existing precedent):

1. Added `FormCombobox` to the `@/components/custom` import (kept `FormSelect` — still used for the Customer/Vendor field).
2. Added `import { useModels } from '@/hooks/catalogHooks/modelQueries'` and `const { data: modelsData } = useModels(LOOKUP_PAGE)`, reusing each file's already-declared `LOOKUP_PAGE` constant, alongside the existing `useItems(LOOKUP_PAGE)` call.
3. Added `const modelNameById = Object.fromEntries((modelsData?.items ?? []).map((m) => [m.id, m.name]))`.
4. Changed the `itemOptions` label from `item.sku` to `` `${item.sku} · ${modelNameById[item.model_id] ?? 'Unknown model'}${item.variant ? ` (${item.variant})` : ''}` `` — a trimmed version of the richer label that existed before `044dcec`. Category was deliberately left out (it was dropped for being non-discriminating noise across items; model was never the complaint).
5. Replaced the item-line `<FormSelect .../>` with `<FormCombobox ... searchPlaceholder="Search by SKU or model…" />`, keeping every other prop (`{...field}`, `label`, `placeholder`, `options`, `error`) identical.

## Not changed

`FormCombobox.jsx` itself (so `PaymentForm.jsx`'s existing usage doesn't regress), `salesSchemas.js`/`purchasingSchemas.js` (both already coerce a string `item_id` to number, unaffected by which picker component produced it), `useForm` defaults, `useFieldArray`, `onSubmit`, `useExchangeRateForDate`, `handleSourceChange` — nothing about form submission behavior changed, only how the item field is rendered and labeled.

## Verification performed

1. **Lint**: `npx eslint` on both changed files — 0 errors. Each has one pre-existing warning (`react-hooks/incompatible-library` on react-hook-form's `watch()`), confirmed already present before this change — not a regression.
2. **Build**: `npm run build` — clean.
3. **Functional, end-to-end, in a real browser**, against the already-running dev backend (`uvicorn`, port 8001) and dev frontend (`vite`, port 5173):
   - Seeded test catalog data via the `/catalog` admin screens: category "Protector", brand "Apple", models "iPhone XS" and "iPhone 11 Pro", and two items — `PROT-XS-CLEAR-01` (iPhone XS) and `PROT-11PRO-CLEAR-01` (iPhone 11 Pro).
   - On `/sales-orders/new`: opened the Item field — both items rendered as a searchable combobox showing `SKU · Model` labels (`PROT-XS-CLEAR-01 · iPhone XS`, `PROT-11PRO-CLEAR-01 · iPhone 11 Pro`). Typed "11 Pro" — the list correctly narrowed to just the matching item by model name, not just SKU. Selected it — the trigger updated to show the full label and the row's "In stock: 0" line rendered, confirming `item_id` was populated in `react-hook-form` state exactly as `FormSelect` used to do.
   - On `/purchase-orders/new`: same picker, same combobox behavior, confirmed working identically (both items listed with rich labels, popover opens/searches/selects correctly).
   - Confirmed `PaymentForm.jsx`'s existing `FormCombobox` usage (the order/reference picker) was not touched and is unaffected.

## Follow-ups (not part of this phase, flagged for later)

- `FormCombobox`'s filtering is client-side only, over a flat `page_size=100` fetch (`LOOKUP_PAGE`). Once the Item catalog grows past that cap, extend it with a controlled, debounced search wired to the backend's new `sku` filter (`catalog-fixes-backend-plan.md`) — matching the debounce pattern `CrudTable.jsx`'s `SearchFilter` already uses for the Items admin table's `variant` filter. Not built now since the current picker already solves the reported problem within the existing page cap.
- Noticed, not fixed (out of scope, cosmetic): the Catalog admin drawers (`CrudDrawer`) don't always reset their form fields between successive "Add" opens in the same session — encountered while seeding test data (a second "Add model" open retained the first model's typed name until overwritten). Worth a look if it recurs in normal use, but it didn't affect this phase's actual deliverable.
