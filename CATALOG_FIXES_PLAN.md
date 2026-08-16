# Catalog & Item-Picker Fixes — Plan

Three problems reported against the production site, all in the `catalog` domain (Category / Brand / Model / Item) and its consumers (Sales Order / Purchase Order item pickers). This file is the plan; PLAN.md/CLAUDE.md govern the rest of the system as usual.

## Decisions already made

- **Deleting Items/Models**: one-time cleanup, not a reusable UI feature. Soft delete (`is_active = false`), not a hard row delete — consistent with how every other table in this app handles delete, and it keeps historical Purchase/Sales Orders that reference these rows intact.
- **SKU**: keep a single `sku` field. The real problem is that the item picker is a plain, unsearchable dropdown, not that SKU needs a second "short" variant.

---

## Problem 1 — Delete all Items and Models

No new code needed. Both tables already have `is_active`, and every list/picker endpoint already filters on `is_active = true` (`backend/src/crud.py`).

```sql
UPDATE item SET is_active = false;
UPDATE model SET is_active = false;
```

- Items/Models disappear from every catalog screen and picker immediately.
- Any existing `PurchaseOrderLine` / `SalesOrderLine` / `StockLot` rows that reference them keep working — they reference by id, not through the active-filtered list.
- **Requires production DB access and explicit go-ahead before running** — not run yet.

---

## Problem 2 — Model compatibility ("this protector also fits these other models")

Today `Item.model_id` is a single FK — one model per item — and the whole `catalog` domain is 100% generic CRUD (`build_crud_router()` in `crud.py`) with zero hand-written service logic. There is no many-to-many relationship anywhere in the codebase to pattern-match against. This feature is the first thing that requires Item to grow real business logic, matching how every other domain in this app already works.

### Backend
1. New join table `item_compatible_model(item_id FK → item.id, model_id FK → model.id)`, composite primary key. One Alembic migration, date-prefixed filename per CLAUDE.md §2.5.
2. `ItemCreate` / `ItemRead` / `ItemUpdate` (`catalog/schemas.py`) gain `compatible_model_ids: list[int]`.
3. Add `catalog/service.py` (and `dependencies.py` if needed) with hand-written create/update logic that syncs the join-table rows in the same transaction as the Item write, and read logic that `selectinload`s them back onto the response. Item stops being routed through `build_crud_router()`; Category/Brand/Model stay on the generic engine.
4. The `model_id` filter (used when picking items for a given model) needs to match **primary model OR a compatibility row for that model**, so filtering by "iPhone 11 Pro" also surfaces a protector created under "iPhone XS" but tagged compatible.

### Frontend
No new component needed — `FormMultiSelect` (`components/custom/FormMultiSelect.jsx`) already exists and is already proven for this exact shape via `PartyForm`'s `roles` field.

- Add one field to `ItemCrudConfig.js`: a multiselect over the same `models` list already fetched for the `model_id` dropdown.
- Add `compatible_model_ids: array().of(number()).default([])` to the Yup schema in `validations/catalogSchemas.js`, mirroring the backend field.

---

## Problem 3 — Item picker is hard to use

### Backend
Add `sku` to Item's `search_filters` in `catalog/router.py` — mechanically identical to how `variant` search was already added (commit `01a9fa4`). Small, low-risk change, no migration.

### Frontend (Sales Order and Purchase Order forms)
1. Swap the plain `FormSelect` dropdown for `FormCombobox` (`components/custom/FormCombobox.jsx`) — it already exists and is already used in `PaymentForm` for the same "type to find the right row" problem. No new component required.
2. Widen the picker's label beyond bare SKU (commit `044dcec` made it SKU-only, which is part of what's making items hard to tell apart now) — e.g. `SKU · Model (Variant)` — so typing a model name also filters correctly, since `FormCombobox` matches against the label text.
3. Current fetch is capped at 100 items with no search param sent — fine for now with client-side filtering. If the catalog grows past that, wire the combobox's typing to the new server-side `sku` filter with a debounce instead of relying on the flat fetch.

---

## Suggested order

1. **Phase 0** (needs DB access + explicit go-ahead): soft-delete all Items/Models.
2. **Phase 1** (fast, independent, no schema change): picker UX fix — combobox + better labels + `sku` search filter.
3. **Phase 2** (bigger lift): model-compatibility migration + service + frontend multiselect.
