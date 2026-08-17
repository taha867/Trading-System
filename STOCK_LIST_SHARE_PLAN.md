# Stock List Share — Plan

## Context

The user currently sends clients an informal photo of physical stock so clients know what models are available to order. The ask: a proper in-app feature that generates a clean, shareable image listing everything currently in stock — grouped Category → Brand → Model — which the user can curate (remove anything they don't want shown) before generating.

## Decisions already made

- **Only models with current stock** (any item under that model has a `StockLot` with `qty_remaining > 0`) — matches the same "in stock" definition the existing Balance Statement report already uses (`reporting/service.py::get_balance_statement`).
- **Includes models reachable via compatibility too** (Phase 2's `item_compatible_model`), not just each item's own primary model — if a client can actually order it, it should show as available, the same reasoning behind that feature in the first place.
- **No persistence.** Every time the user opens this screen it's a fresh curation starting from "everything in stock is checked" — nothing about which models were excluded last time is remembered server-side. Simplest, and stock changes daily anyway so a saved selection would go stale fast.
- **Output is a clean plain list** — Category as a heading, Brand as a sub-heading, Models listed underneath. No logo/branding/graphic design work.

## Backend approach

New read-only endpoint in the `reporting/` domain — it already exists specifically for cross-domain, read-only views (`BalanceStatement`, `SellThrough`, `ReorderPriority`), and this is exactly that shape: reads `catalog` + `inventory`, owns nothing.

**`reporting/schemas.py`**: add
```python
class AvailableModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    category: str
    brand: str
    model: str
    model_id: int
```

**`reporting/service.py`**: add `get_available_models(db) -> list[AvailableModelRead]`:
1. Find item ids with stock: `select(StockLot.item_id).where(StockLot.qty_remaining > 0).distinct()`.
2. Query A — primary models: join `Item` (filtered to those ids, `is_active`) → `Model` → `Brand`, select `(Item.category → Category.name, Brand.name, Model.name, Model.id)`.
3. Query B — compatible models: join `Item` (same stocked ids) → `ItemCompatibleModel` → `Model` → `Brand`, same shape.
4. Combine both result sets in Python and dedupe on `(category, brand, model)` — two simple queries plus a Python-side merge is simpler and more maintainable than a SQL `UNION` for a dataset this size (currently ~100 rows), consistent with this codebase's general preference for straightforward code over cleverness.
5. Sort by `(category, brand, model)` and return.

**`reporting/router.py`**: one new hand-written route, `GET /available-models`, `response_model=list[AvailableModelRead]`, no pagination (dataset stays small — this is "all models currently sellable," not a transactional list).

## Frontend approach

- **`services/reportingService.js`**: add `listAvailableModels()`.
- **`hooks/reportingHooks/reportingQueries.js`**: add `useAvailableModels()`.
- **New component** `components/reporting/StockListShare.jsx`:
  1. Fetch available models, group client-side into Category → Brand → `[Model]` (same `Object.fromEntries`/`reduce` grouping style already used throughout the app, e.g. `ItemCrudConfig.js`'s `modelNameById`).
  2. Render a checklist — every model has a checkbox, checked by default; a "Select all" / "Deselect all" control per category (and globally) for convenience when a category has many models.
  3. A live preview pane that renders *only the checked models*, styled exactly as the exported image will look (Category heading, Brand sub-heading, Model list) — this preview `<div>` is the actual DOM node that gets captured, so what's on screen is exactly what gets downloaded, no separate render path to keep in sync.
  4. A "Download image" button: `html-to-image`'s `toPng(previewNode)` renders that preview into a PNG data URL, then a hidden `<a download="stock-list.png">` triggers the browser's normal save-file dialog — a standard client-side download the user initiates themselves, not something requiring special handling.
- **New page** `pages/StockListPage.jsx` (thin pass-through, matching every other page file), new route in `App.jsx` inside the existing `ProtectedRoute` group, new `Navbar.jsx` link (e.g. "Stock List").
- **New dependency**: `html-to-image` — small, no runtime dependencies of its own, actively maintained. Matches the precedent already set in this codebase for `cmdk` (added specifically for `FormCombobox` in an earlier phase) — a new dependency justified by a genuine, narrow need rather than reached for by default.

### Responsive design (CLAUDE.md §3.7, non-negotiable)
Mobile-first — staff may curate and send from a phone. Checklist and preview pane stack vertically below `md`; side-by-side only on wider screens.

### Critical files
- `backend/src/reporting/schemas.py`, `service.py`, `router.py`
- `frontend/src/services/reportingService.js`, `frontend/src/hooks/reportingHooks/reportingQueries.js`
- `frontend/src/components/reporting/StockListShare.jsx` (new)
- `frontend/src/pages/StockListPage.jsx` (new), `frontend/src/App.jsx`, `frontend/src/components/Navbar.jsx`
- `frontend/package.json` (new dependency)

### Not changed
No new database tables/migrations (purely a read query over existing `catalog`/`inventory` data), no changes to Item/Model creation flows, no persistence layer.

## Verification

1. Seed a few `StockLot` rows with `qty_remaining > 0` against a handful of items (including at least one with a compatible model tagged) against the dev backend.
2. Confirm `GET /reporting/available-models` returns exactly the expected `(category, brand, model)` rows — including the compatible-model row, and excluding any model whose only items are out of stock.
3. Open the new Stock List page: confirm the checklist groups correctly by Category → Brand, confirm unchecking a model removes it from the live preview immediately.
4. Click "Download image": confirm the downloaded PNG matches the on-screen preview exactly (same models, same grouping, same text).
5. Check at ~375px width (phone) — confirm the checklist and preview remain usable, not squeezed into an unreadable two-column layout.
