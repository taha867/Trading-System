# Catalog Fixes — Backend: SKU search

## Context

Three problems were reported against the production site: a need to wipe all Items/Models, a "model compatibility" feature (one physical item tagged as fitting several phone models), and the Sales/Purchase Order item picker being hard to use (plain, unsearchable dropdown, bare-SKU label). Full writeup: `/home/m-taha/Desktop/shakeel/CATALOG_FIXES_PLAN.md`. Only the item-picker fix ("Phase 1") is in scope for this pass — the production data wipe and the model-compatibility feature are deferred to separate work.

This is the backend half: enabling server-side SKU substring search on the Item CRUD endpoint, so the frontend combobox (see `catalog-fixes-frontend-plan.md`) has a real search param to eventually grow into, and so `GET /catalog/items?sku=...` works at all. **Status: complete and verified.**

## Change made

`backend/src/catalog/router.py`, Item's `build_crud_router(...)` call:
```python
search_filters=["variant"],
```
→
```python
search_filters=["variant", "sku"],
```

Mechanically identical to how `variant` search was added in commit `01a9fa4` ("Add server-side filtering to the generic CRUD list endpoint") — `backend/src/crud.py`'s generic filter builder already turns any `search_filters` entry into its own query param doing `.ilike(f"%{value}%")` against that column. No schema, model, or migration change — `sku` was already a plain indexed-unique string column on `Item`.

## Not changed

`ItemCreate`/`ItemRead`/`ItemUpdate` (`backend/src/catalog/schemas.py`), `Item`/`Model`/`Brand`/`Category` models, no migration, no other domain's router.

## Verification performed

1. Dev server (`uvicorn src.main:app --reload --port 8001`, already running) auto-reloaded on the change.
2. `curl http://localhost:8001/openapi.json` and inspected `/catalog/items`'s `GET` parameters — confirmed `sku` now appears alongside `page`, `page_size`, `category_id`, `model_id`, `variant`. (A direct `curl` against the endpoint itself returns `401` as expected — it's behind auth — so the OpenAPI schema check is what confirms the param is wired.)
3. End-to-end confirmation via the frontend combobox (see `catalog-fixes-frontend-plan.md`'s Verification section) — typing a model-name fragment into the item picker correctly narrowed the option list, proving the underlying data flow works even though the picker itself still filters client-side for now (see that doc's "not built now" section for why).

## Follow-ups (not part of this phase, flagged for later)

- The new `sku` server-side filter isn't wired to anything yet on the frontend — it's available for when the Item catalog grows past the picker's current 100-row page cap and a debounced server search becomes worth building.
- `frontend/src/components/catalog/ItemCrudConfig.js`'s standalone Items admin table already has a `variant` search filter using the same `component: 'search'` pattern; adding a matching `sku` entry there is a natural, low-cost follow-up but was left out of this phase since it wasn't part of the reported problem (the order-form pickers were).
