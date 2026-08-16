# Item Model Compatibility — Frontend

## Context

Companion to `item-model-compatibility-backend-plan.md` — see that doc's Context for the full background. This is the frontend half: letting a user tag additional compatible Models on an Item from the Catalog admin screen, and see at a glance which items cover which extra models ("users can know what relevant models can be applied here too" — the user's own framing of the need). **Status: complete and verified.**

## Files changed

- `frontend/src/validations/catalogSchemas.js`
- `frontend/src/components/catalog/ItemCrudConfig.js`

### `catalogSchemas.js`
Added `compatible_model_ids: array().of(number()).default([])` to `itemCreateSchema`. `itemUpdateSchema` already derives via `itemCreateSchema.omit(['sku']).partial()`, so the new field became optional there automatically — no separate handling needed.

### `ItemCrudConfig.js`
- Added one field to the `fields` array reusing the `models` list already fetched there for the `model_id` select:
  ```js
  {
    name: 'compatible_model_ids',
    label: 'Also compatible with',
    component: 'multiselect',
    options: models.map((m) => ({ value: m.id, label: m.name })),
    defaultValue: [],
  }
  ```
- Added one column to `columns`: `{ key: 'compatible_models', label: 'Also fits', render: (row) => row.compatible_models?.length ? row.compatible_models.map((m) => m.name).join(', ') : '—' }` — reads `ItemRead.compatible_models` (full nested `ModelRead`s) directly, no extra lookup needed.

## A real gotcha, resolved by a call-site choice (no shared-component change needed)

`FormMultiSelect` (`components/custom/FormMultiSelect.jsx`) and `CrudDrawer.jsx`'s `buildDefaultValues` do a plain `value.includes(option.value)` / array push-remove for `component: 'multiselect'`, with **no type coercion** — unlike the `select` case, which explicitly does `String(row[field.name])`. The only prior multiselect usage (`PartyForm`'s `roles`) never hit this because roles are strings on both ends (backend `ARRAY(String)`). `compatible_model_ids` is numeric on both ends instead (backend `list[int]`, `ItemRead.compatible_model_ids` returns raw ints).

**Fix**: this field's `options` use raw `m.id` (not `String(m.id)`), matching the numeric type flowing from the backend end-to-end — checkbox `checked` state, toggle add/remove, and the submitted value all stay consistently numeric, with Yup's `array().of(number())` cast acting as a no-op safety net rather than a load-bearing conversion. Confirmed correct in the browser: editing an item with `compatible_model_ids: [4]` showed exactly the "iPhone 11 Pro" checkbox checked and the item's own primary model's checkbox unchecked — no false negatives from a type mismatch. **No changes needed to `FormMultiSelect.jsx` or `CrudDrawer.jsx`.**

## Not changed

`itemQueries.js`/`itemMutations.js`/`catalogService.js` (thin passthroughs, unaffected), the Phase-1 Sales/Purchase Order item pickers (they already list every item in one flat searchable combobox regardless of model — compatibility only changes what a model-filtered *admin* list matches, not what shows in the order-line picker).

## Verification performed

1. **Lint**: `npx eslint` on both changed files — 0 errors, 0 warnings.
2. **Build**: `npm run build` — clean.
3. **Functional, end-to-end, in a real browser**, against the already-running dev backend/frontend, using the two items seeded during Phase 1 (`PROT-XS-CLEAR-01` / iPhone XS, `PROT-11PRO-CLEAR-01` / iPhone 11 Pro):
   - Confirmed the Items table's new "Also fits" column showed "iPhone 11 Pro" for `PROT-XS-CLEAR-01` (set via the backend API test in the companion doc).
   - Opened the item's Edit drawer — the "Also compatible with" checkbox group correctly showed only "iPhone 11 Pro" checked, not the item's own primary model ("iPhone XS") — confirming the numeric-id gotcha above was resolved correctly, not just theoretically.
   - Checked the second box ("iPhone XS") and saved — the "Also fits" column updated live to "iPhone 11 Pro, iPhone XS", confirming multi-select submission and persistence.
   - Reopened the drawer, unchecked "iPhone XS", saved — column reverted to just "iPhone 11 Pro", confirming the update correctly replaces (not just appends to) the compatibility set from the UI, matching the backend's reassignment semantics.

## Follow-ups (not part of this phase, flagged for later)

- No chip/badge-style display for "Also fits" — it's a plain comma-joined string, consistent with how every other list-only lookup column in this table renders (no existing precedent for badges outside `PartyRoleBadges`, which was written specifically for a small closed enum of roles, not an open-ended model list).
