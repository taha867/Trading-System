# Stock List Share — Spec

Governed by `STOCK_LIST_SHARE_PLAN.md` (what and why) and `CLAUDE.md` (how). This document is the missing middle layer: the exact schema, query, and component structure needed to implement the feature, consistent with what's already built. Every choice below either follows an existing precedent in the codebase (cited by file:line) or is flagged explicitly as a new decision/deviation this feature introduces. Two research passes read the actual current `reporting/` domain (backend) and page/nav/dependency structure (frontend) before this was written — nothing here is assumed.

**Done when** (from `STOCK_LIST_SHARE_PLAN.md`): the user opens a screen, sees every model currently in stock grouped Category → Brand, unchecks whatever they don't want to share, and downloads a PNG of exactly what's left checked. No persistence anywhere — a fresh curation every time.

---

## 1. Where we stand

- **`backend/src/reporting/`** already holds four read-only, cross-domain report endpoints (`balance-statement`, `sell-through`, `reorder-priority`, `margin`) — this feature is a fifth. `reporting/router.py` is a single `router = APIRouter(tags=["reporting"])` (no sub-routers to merge, no own prefix — `main.py:36` supplies `/reporting`), every route takes `Annotated[AsyncSession, Depends(get_db)]` + `Annotated[User, Depends(get_current_user)]` (the latter unused, purely an auth gate), and every route body is one line: `return await service.<fn>(db, ...)`.
- **Every existing `reporting/schemas.py` class is a plain `BaseModel`**, never `ConfigDict(from_attributes=True)` — they're built explicitly in `service.py` from query result tuples (e.g. `PartyBalanceRead(party_id=pid, name=name, ...)`), not `Model.model_validate(orm_row)`. This is deliberate and consistent within `reporting/` specifically (these are aggregation DTOs, not passthrough CRUD reads) — match it.
- **Every existing "entries" schema wraps in an envelope** (`SellThroughRead { window_days, start_date, end_date, entries: list[SellThroughEntryRead] }`, same shape for `ReorderPriorityRead`/`MarginReportRead`) — there's no bare-`list[X]` response precedent in this domain yet, though all three existing ones happen to need the wrapper for their date-window fields, which this feature doesn't have.
- **`get_margin_report` (`reporting/service.py:138-216`) is the established "combine two things" precedent, and it does so via a SQL `outerjoin` of two subqueries — not two separate ORM queries merged/deduped in Python.** There is no precedent anywhere in this file for a Python-side merge. This directly overturns `STOCK_LIST_SHARE_PLAN.md`'s original suggestion ("two simple queries, combine+dedupe in Python") — §2.1 below follows the actual codebase convention instead.
- **No existing query joins `Item`+`Model`+`StockLot` together.** `get_balance_statement`'s inventory-value query touches `StockLot` alone (`reporting/service.py:46-54`, filtering `StockLot.qty_remaining > 0` — the exact "in stock" filter this feature reuses). The closest shape to mirror is `get_margin_report`'s `Item.id == subquery.c.item_id` → `Model.id == Item.model_id` join chain (`reporting/service.py:178-179`).
- **`Category` and `Brand` are not linked to each other.** `Category` is an `Item`-level attribute (`Item.category_id`); `Brand` is reached only via `Model.brand_id`. So per row: `category` comes from `Item.category_id`, `brand`/`model` come from `Item.model_id → Model.brand_id` (primary) or `ItemCompatibleModel.model_id → Model.brand_id` (compatible) — but **category is still the item's own category in both cases**, since a compatible model doesn't carry its own category.
- **`ItemCompatibleModel`** (`catalog/models.py:34-40`): composite PK `(item_id, model_id)`, nothing else on it. `Item.compatible_models` is a `lazy="raise"` relationship — every existing query in `reporting/service.py` avoids ORM relationships entirely and joins mapped classes directly instead, which sidesteps that guard naturally; this feature does the same, never touching `.compatible_models` as an attribute.
- **Frontend**: `reportingService.js`/`reportingQueries.js` are both short, flat files (~30-50 lines) — one function per report, no shared helper beyond `fetchClient`. `reportingKeys` (`utils/queryKeys.js:130-136`) is a flat factory, one entry per report.
- **No two-level (Category→Brand→Model) grouping exists anywhere in the frontend.** The closest precedent is `StockLotTable.jsx:39-51`'s one-level `Map`-based grouping (dedupe key → index into a groups array, then `.sort()` for display order). This feature extends that technique by one level — there is no existing two-level example to copy verbatim.
- **No "checked items → live preview" pattern exists anywhere.** The only two `Checkbox` usages outside `components/ui/` are single boolean toggles (`StockLotTable.jsx:67`'s "include depleted" filter, `PaymentForm.jsx:161`'s "has reference" reveal) — neither drives a multi-item preview. This will be the first.
- **No reporting component owns its own page/route.** All four existing ones (`BalanceStatement.jsx`, `SellThroughChart.jsx`, `ReorderPriorityTable.jsx`, `MarginReportTable.jsx`) are composed directly into `DashboardContainer.jsx`, reached only via `/dashboard`. This feature is the first `reporting/` screen with its own URL.
- **`Navbar.jsx` holds no nav links at all** — navigation lives in `utils/constants.js`'s `NAV_LINKS` array (`{ to, label, icon, shortLabel? }` objects), consumed by both `Sidebar.jsx` and `BottomNav.jsx` with zero per-component wiring needed beyond adding one entry. Anything not in `BOTTOM_NAV_PRIMARY_PATHS` (`constants.js:151`, currently 4 paths) automatically falls into `BottomNav.jsx`'s mobile "More" sheet — correct default for a low-frequency utility screen like this one.
- **No image-export library exists** (`html-to-image`/`html2canvas`/`dom-to-image` all absent from `package.json`). Frontend is on React 19.2 / Vite 8 — `html-to-image` has no React peer dependency (DOM-node-in, canvas/data-URL-out), no conflict expected.

---

## 2. Design decisions

### 2.1 Combine primary + compatible models via one SQL `UNION`, not a Python-side merge

Per §1, `get_margin_report` establishes that this codebase combines multi-source query results in SQL, not in application code. Two `select()`s — one joining `Item → Model → Brand` (primary), one joining `Item → ItemCompatibleModel → Model → Brand` (compatible), both filtered to active, in-stock items — combined with SQLAlchemy's `union()` (plain `UNION`, not `UNION ALL`, so identical `(category, brand, model, model_id)` rows collapse automatically — no manual dedup needed). This is both more consistent with precedent and less code than a Python `set`/dict merge.

### 2.2 Response schema — keep the envelope, for consistency with every sibling report

`AvailableModelRead`-style naming would break from this domain's own `XEntryRead`/`XRead` convention (`SellThroughEntryRead`/`SellThroughRead`, etc.) — so this feature is named `StockListEntryRead`/`StockListRead` instead, matching the feature's own name. `StockListRead` has no window/date fields (nothing here is time-windowed), so it's just `{ entries: list[StockListEntryRead] }` — a thin wrapper with nothing else in it today. Flagging this as a judgment call, not a hard requirement: the wrapper's only real justification is shape-consistency with the other four reports and leaving room for a future field (e.g. `generated_at`) without a breaking response-shape change later. A bare `list[StockListEntryRead]` would work equally well functionally.

### 2.3 Route matches the other four exactly

`GET /reporting/stock-list` → `response_model=StockListRead`, no query params, same two-dependency auth-gate shape as every other route in this router. One line in the router body: `return await service.get_stock_list(db)`.

### 2.4 Backend returns flat, frontend groups — matches the existing division of labor

The backend does aggregation math (the SQL `UNION`, `is_active`/`qty_remaining>0` filtering); grouping-for-display stays a frontend concern, same as `StockLotTable.jsx` already groups its flat item/lot list client-side rather than the backend pre-nesting it. `StockListEntryRead` stays a flat row; the frontend groups it into Category → Brand → `[Model]`.

### 2.5 This is the first `reporting/` screen with its own page — deliberate, not an oversight

Every existing reporting component lives inside `DashboardContainer.jsx` with no route of its own. This feature doesn't fit that shape — it's a distinct workflow (curate, then export), not a glance-and-done dashboard widget — so it gets the same page→container→component structure every other domain's *own* screens already use (e.g. `PaymentsPage.jsx` → `PaymentsContainer.jsx` → `PaymentAccountList.jsx`/`PaymentTransactionList.jsx`), just placed under `reporting/`'s domain folder since it reads reporting-shaped data and owns nothing.

### 2.6 Nav wiring is one line in `utils/constants.js`, nothing else

Add one object to `NAV_LINKS` (e.g. `{ to: '/stock-list', label: 'Stock List', icon: Share2 }`, no `shortLabel` needed since it isn't a `BOTTOM_NAV_PRIMARY_PATHS` entry). `Sidebar.jsx` and `BottomNav.jsx` both pick it up automatically; it'll surface under `BottomNav`'s mobile "More" sheet by default, which is the right place for a screen used occasionally, not every session.

### 2.7 Local `useState`, not react-hook-form — this isn't a form

Every existing checkbox/select screen in this codebase that touches react-hook-form does so because it's building a payload to submit to a create/update mutation. This screen submits nothing to the backend — "which models are checked" is ephemeral, client-only UI state with no Yup schema and no server round-trip on change. Forcing it into the `Controller`/`FormMultiSelect` pattern used everywhere else would be reaching for form infrastructure this screen doesn't need. Use a plain `useState<Set<number>>` of excluded (or included — pick one, be consistent) model ids instead. Flagging this explicitly since react-hook-form is so pervasive elsewhere that its absence here could otherwise look like an oversight rather than a deliberate fit-the-actual-need choice.

### 2.8 Image export forces a light background, independent of the app's own theme

```js
import { toPng } from 'html-to-image';

async function handleDownload(previewNode) {
  const dataUrl = await toPng(previewNode, { pixelRatio: 2, backgroundColor: '#ffffff' });
  const link = document.createElement('a');
  link.download = 'stock-list.png';
  link.href = dataUrl;
  link.click();
}
```
`pixelRatio: 2` for a crisp image when viewed at full size on a phone (default 1x looks soft). `backgroundColor: '#ffffff'` is forced explicitly and deliberately does **not** follow the viewer's dark/light app theme — this image is meant for an external client to read on WhatsApp, not to match whatever theme the shop owner's own browser happens to be in.

---

## 3. Data model

**No new tables, no migration.** This is a pure read over `catalog` (`Item`, `Model`, `Brand`, `Category`, `ItemCompatibleModel`) and `inventory` (`StockLot`), all of which already exist.

---

## 4. Pydantic schemas

New in `backend/src/reporting/schemas.py`, alongside the existing four:

```python
class StockListEntryRead(BaseModel):
    category: str
    brand: str
    model: str
    model_id: int


class StockListRead(BaseModel):
    entries: list[StockListEntryRead]
```

No `ConfigDict(from_attributes=True)` — built explicitly from query rows in `service.py`, matching every sibling schema in this file (§1).

---

## 5. Service logic

New in `backend/src/reporting/service.py`:

```python
from sqlalchemy import union

from src.catalog.models import Brand, Category, Item, ItemCompatibleModel, Model
from src.inventory.models import StockLot


async def get_stock_list(db: AsyncSession) -> StockListRead:
    in_stock_item_ids = select(StockLot.item_id).where(StockLot.qty_remaining > 0).distinct()

    primary = (
        select(
            Category.name.label("category"),
            Brand.name.label("brand"),
            Model.name.label("model"),
            Model.id.label("model_id"),
        )
        .select_from(Item)
        .join(Category, Category.id == Item.category_id)
        .join(Model, Model.id == Item.model_id)
        .join(Brand, Brand.id == Model.brand_id)
        .where(Item.is_active.is_(True), Item.id.in_(in_stock_item_ids))
    )

    compatible = (
        select(
            Category.name.label("category"),
            Brand.name.label("brand"),
            Model.name.label("model"),
            Model.id.label("model_id"),
        )
        .select_from(Item)
        .join(Category, Category.id == Item.category_id)
        .join(ItemCompatibleModel, ItemCompatibleModel.item_id == Item.id)
        .join(Model, Model.id == ItemCompatibleModel.model_id)
        .join(Brand, Brand.id == Model.brand_id)
        .where(Item.is_active.is_(True), Item.id.in_(in_stock_item_ids))
    )

    combined = union(primary, compatible).subquery()
    rows = (
        await db.execute(
            select(combined.c.category, combined.c.brand, combined.c.model, combined.c.model_id).order_by(
                combined.c.category, combined.c.brand, combined.c.model
            )
        )
    ).all()

    return StockListRead(
        entries=[
            StockListEntryRead(category=r.category, brand=r.brand, model=r.model, model_id=r.model_id)
            for r in rows
        ]
    )
```

Plain `UNION` (not `UNION ALL`) collapses an item that's simultaneously reachable two ways (e.g. its own primary model already equals a model another item also lists as compatible) into one row automatically — no application-level dedup needed.

---

## 6. API surface

`reporting/router.py` gains one route, same shape as its four siblings:

```python
@router.get("/stock-list", response_model=StockListRead)
async def get_stock_list(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.get_stock_list(db)
```

| Method | Path | Notes |
|---|---|---|
| GET | `/reporting/stock-list` | No query params; always "as of now", same posture as `/reporting/balance-statement` |

No changes to `main.py` — rides on the existing `app.include_router(reporting_router, prefix="/reporting")` mount.

---

## 7. Frontend — services & hooks

**`services/reportingService.js`** — add, matching the existing no-param shape (closest to `getBalanceStatement`):
```js
export async function getStockList() {
  const { data } = await fetchClient.get('/reporting/stock-list');
  return data; // StockListRead
}
```

**`hooks/reportingHooks/reportingQueries.js`** — add:
```js
export function useStockList() {
  return useQuery({
    queryKey: reportingKeys.stockList(),
    queryFn: getStockList,
  });
}
```

**`utils/queryKeys.js`** — add one entry to the existing `reportingKeys` factory:
```js
stockList: () => [...reportingKeys.all, 'stock-list'],
```

---

## 8. Frontend — page, container, component

**`pages/StockListPage.jsx`** (new, 5 lines, exact shape of `PaymentsPage.jsx`):
```jsx
import { StockListContainer } from '@/containers/StockListContainer';

export function StockListPage() {
  return <StockListContainer />;
}
```

**`containers/StockListContainer.jsx`** (new) — page chrome, composes `StockListShare`, no param parsing needed (no URL params for this screen).

**`components/reporting/StockListShare.jsx`** (new) — the actual feature:
1. `const { data, isLoading, isError } = useStockList();`
2. Group `data.entries` into a nested structure — extend `StockLotTable.jsx`'s one-level `Map`-keyed-by-index technique (§1) by one more level: a `Map` of category → (`Map` of brand → `Model[]`), built once per render from the flat `entries` array, then converted to a sorted array-of-arrays for rendering (categories and brands sorted alphabetically, matching the SQL's own `ORDER BY category, brand, model`).
3. Local state: `const [excludedModelIds, setExcludedModelIds] = useState(() => new Set());` — a model is included unless its id is in this set. Toggling a checkbox adds/removes from the set (§2.7 — no react-hook-form).
4. A "Select all" / "Deselect all" control per category (clears/adds every model id under that category from the set) plus one global control.
5. A preview `<div ref={previewRef}>` rendering only non-excluded models, styled as the plan's plain-list format:
   ```
   PROTECTOR

     Apple
       iPhone 12 / iPhone 12 Pro
       iPhone 13

     Samsung
       Galaxy A54
   ```
   Category as an uppercase heading, Brand as an indented sub-heading, Models as a further-indented list — this preview node is the literal thing `toPng()` captures, so there's no separate "what gets exported" render path to keep in sync with "what's on screen."
6. A "Download image" button calling the `handleDownload` function from §2.8 with `previewRef.current`.

### Responsive (CLAUDE.md §3.7, non-negotiable)
Checklist and preview stack vertically below `md` (`flex flex-col md:flex-row` or similar) — side-by-side only on wider screens. The checklist itself needs no table (a phone-friendly stacked list of checkboxes, not a wide multi-column grid).

---

## 9. Nav & routing

- **`App.jsx`**: one new `import { StockListPage } from '@/pages/StockListPage';` near the other page imports, one new `<Route path="/stock-list" element={<StockListPage />} />` inside the existing `ProtectedRoute` group.
- **`utils/constants.js`**: one new `NAV_LINKS` entry — `{ to: '/stock-list', label: 'Stock List', icon: Share2 }` (or another suitable `lucide-react` icon already unused elsewhere in that array). No `shortLabel` — this isn't a `BOTTOM_NAV_PRIMARY_PATHS` entry, so it surfaces in `BottomNav.jsx`'s "More" sheet on mobile by default.
- **No changes to `Navbar.jsx`, `Sidebar.jsx`, or `BottomNav.jsx`** — all three pick up the new link with zero direct edits (§1, §2.6).

---

## 10. New dependency

`frontend/package.json`: add `html-to-image` (`npm install html-to-image`). No React peer dependency, no known conflict with React 19.2/Vite 8 (§1). Matches this codebase's existing precedent for adding a small, narrowly-justified dependency (`cmdk`, added specifically for `FormCombobox` in an earlier phase) rather than reaching for one by default.

---

## 11. Verification / manual testing path

1. Seed a few `StockLot` rows with `qty_remaining > 0` against a handful of dev items, including at least one item tagged with a compatible model (Phase 2 feature).
2. `GET /reporting/stock-list` — confirm the response includes the expected `(category, brand, model)` rows, including the compatible-model row, and excludes any model whose only items are currently out of stock (`qty_remaining = 0` everywhere).
3. Open `/stock-list` in the browser: confirm the checklist groups correctly by Category → Brand, all checked by default.
4. Uncheck a few models — confirm the preview pane updates immediately, with no stale entries.
5. Click "Download image" — confirm the downloaded PNG matches the on-screen preview exactly (same models, same grouping, same text), and has a white background regardless of the app's current theme.
6. Check the screen at ~375px width (phone) — checklist and preview should stack, not squeeze into an unreadable layout.
7. Confirm the new nav entry appears in `Sidebar.jsx` on desktop and under `BottomNav.jsx`'s "More" sheet on mobile, with no other nav files touched.

---

## 12. Out of scope / open questions for later

- **No persistence of the excluded-models selection** (`STOCK_LIST_SHARE_PLAN.md`'s explicit decision) — every page load starts from "everything in stock is checked." Revisit only if this proves annoying in daily use.
- **The image is a fixed plain-list style** — no logo, no branding, no color. `STOCK_LIST_SHARE_PLAN.md` explicitly deferred a "branded catalog graphic" version; this spec doesn't build toward one.
- **No server-side rendering of the image** — generation is 100% client-side via `html-to-image`; the backend never sees or stores the exported PNG.
- **`StockListRead`'s envelope wrapper (§2.2) has no fields besides `entries` today** — flagged as a consistency-only choice, not a hard requirement; trivial to flatten to a bare list later if the envelope never ends up earning its keep.

---

## 13. Implementation checklist

New:
- `backend/src/reporting/schemas.py` — add `StockListEntryRead`, `StockListRead`
- `backend/src/reporting/service.py` — add `get_stock_list`
- `backend/src/reporting/router.py` — add `GET /stock-list`
- `frontend/src/services/reportingService.js` — add `getStockList`
- `frontend/src/hooks/reportingHooks/reportingQueries.js` — add `useStockList`
- `frontend/src/utils/queryKeys.js` — add `reportingKeys.stockList`
- `frontend/src/pages/StockListPage.jsx`
- `frontend/src/containers/StockListContainer.jsx`
- `frontend/src/components/reporting/StockListShare.jsx`

Changed:
- `frontend/src/App.jsx` — new route
- `frontend/src/utils/constants.js` — new `NAV_LINKS` entry
- `frontend/package.json` — new dependency (`html-to-image`)

Not changed (confirmed, not assumed):
- `backend/src/main.py` (existing mount already covers the new route)
- `frontend/src/components/Navbar.jsx`, `Sidebar.jsx`, `BottomNav.jsx` (all pick up the new nav entry automatically)
- Any existing `reporting/` component (`BalanceStatement.jsx`, `SellThroughChart.jsx`, `ReorderPriorityTable.jsx`, `MarginReportTable.jsx`, `DashboardContainer.jsx`)
- No database migration
