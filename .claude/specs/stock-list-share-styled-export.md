# Stock List Share v2 — Shop Setting, Styled Multi-Page Export, and a CrudDrawer Bug Fix

Governed by `.claude/specs/stock-list-share.md` (the shipped MVP this extends) and `CLAUDE.md` (how). Three independent pieces of work, bundled into one spec because they were requested together: (A) a real bug in the shared `CrudDrawer` component, caught by its own symptom appearing in this feature's test data; (B) a new app-wide "Setting" entity (`shop_name`) — planned since `PLAN.md`'s Phase 0 entity list but never actually built; (C) replacing the MVP's plain single-list export with a styled, multi-column, paginated one.

---

## Part A — Fix: `CrudDrawer` doesn't always reset between two consecutive "Add" clicks

### A.1 What happened, and why (root cause confirmed by reading the code, not guessed)

The "ProtectorProtector" category name visible in the Stock List screenshots is leftover local test data from earlier manual testing in this session — not a data problem in the app. But it's a symptom of a real, general bug worth fixing now that it's been noticed.

`CrudTable.jsx:142` — the "Add" button always does `onClick={() => setDrawerState({ mode: 'create' })}`, a **new object every click**. `CrudDrawer.jsx:227-229` derives `open={Boolean(drawerState)}`, `mode={drawerState?.mode}`, `row={drawerState?.row}` — three **primitives**. `CrudDrawer.jsx:49-54`'s reset effect depends on exactly those three primitives:
```js
useEffect(() => {
  if (open) reset(buildDefaultValues(config.fields, mode === 'edit' ? row : null, mode));
}, [open, mode, row]);
```
If "Add" is clicked a second time while the drawer is already open, the *object* `drawerState` is new, but the *derived primitives* React actually diffs (`true`, `'create'`, `undefined`) are identical to what they already were — so the effect does not re-fire, and `reset()` is never called. Whatever was already typed survives, and new typing lands on top of it — exactly how two separate "Protector" attempts became one "ProtectorProtector" row. This affects every screen built on `CrudTable`/`CrudDrawer` (every tab in Settings, every tab in Catalog) — not just Categories.

### A.2 Fix

Give every open-intent a value that's guaranteed to differ from the last one, and include it in the effect's dependency array. `CrudTable.jsx`:
```js
onClick={() => setDrawerState({ mode: 'create', openedAt: Date.now() })}
...
onClick={() => setDrawerState({ mode: 'edit', row, openedAt: Date.now() })}
```
`CrudDrawer.jsx`:
```js
export function CrudDrawer({ config, open, mode, row, openedAt, onOpenChange, entityLabel = 'record' }) {
  ...
  useEffect(() => {
    if (open) reset(buildDefaultValues(config.fields, mode === 'edit' ? row : null, mode));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, mode, row, openedAt]);
```
And `CrudTable.jsx`'s `<CrudDrawer ... openedAt={drawerState?.openedAt} />`. `Date.now()` is fine here — this is ordinary component code, not a Workflow script (the `Date.now()`-is-unavailable constraint is specific to Workflow scripts elsewhere in this environment, unrelated to this app). Any monotonically-changing value works equally well (an incrementing ref counter would too); `Date.now()` needs no extra state to thread through.

### Files
- `frontend/src/components/common/CrudTable.jsx` — both `setDrawerState` calls
- `frontend/src/components/common/CrudDrawer.jsx` — accept `openedAt`, add to the effect's dependency array

No backend change. No other component needs touching — every `CrudTable`/`CrudDrawer` consumer picks this up automatically since they don't manage `drawerState` themselves.

---

## Part B — Shop name setting

### B.1 Where this lives

`PLAN.md:126` lists `Setting` as a Phase 0 entity, but it was never actually built (confirmed: no `Setting` model, no settings table, anywhere in `backend/src`). `CLAUDE.md`'s architecture notes say app-wide `Setting` "lives as a table owned by `src/config.py`'s domain (no dedicated package)" — i.e., don't build a full `src/settings/` domain package (router.py/service.py/schemas.py/models.py/dependencies.py/constants.py/exceptions.py) for what's a single settings row with one field today. Concretely:

- **Model**: add `Setting` to `src/models.py` (the shared file that already holds `Base` and the naming-convention `MetaData`) — this table has no domain owner, which is exactly what that file is already for.
- **Schemas, service, router**: one new flat module, `src/settings.py`, alongside other flat cross-cutting modules already living directly under `src/` (`crud.py`, `pagination.py`, `exceptions.py`). Small enough that splitting it into `settings/schemas.py` + `settings/service.py` + `settings/router.py` would be more ceremony than the content justifies.

### B.2 Data model

`src/models.py` addition:
```python
class Setting(Base):
    __tablename__ = "setting"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_name: Mapped[str | None] = mapped_column(nullable=True)
```
Singleton by convention, not by constraint: exactly one row, always `id=1`, get-or-create on first read (§B.3) — matching this codebase's general preference for a Python-level invariant over an exotic DB-level one (e.g. a `CHECK (id = 1)` constraint), consistent with how `catalog/service.py`'s validation logic already prefers explicit Python checks over relying on the database to enforce business rules.

### B.3 `src/settings.py` (new)

```python
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.models import Setting

SETTING_ID = 1


class SettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    shop_name: str | None = None


class SettingUpdate(BaseModel):
    shop_name: Annotated[str, Field(max_length=120)] | None = None


async def get_or_create_setting(db: AsyncSession) -> Setting:
    setting = await db.get(Setting, SETTING_ID)
    if setting is None:
        setting = Setting(id=SETTING_ID)
        db.add(setting)
        await db.commit()
        await db.refresh(setting)
    return setting


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingRead)
async def read_setting(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await get_or_create_setting(db)


@router.put("", response_model=SettingRead)
async def update_setting(
    payload: SettingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    setting = await get_or_create_setting(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(setting, field, value)
    await db.commit()
    await db.refresh(setting)
    return setting
```

`main.py`: `from src.settings import router as settings_router` + `app.include_router(settings_router)` (the router already carries its own `/settings` prefix and tag, matching `reporting/router.py`'s self-contained-prefix style — no `prefix=` kwarg needed at the call site).

`migrations/env.py`: add `from src.models import Setting  # noqa: F401` to whatever import already covers `src/models.py`'s contents (today only `Base` is imported from there; `Setting` needs adding explicitly since it's a new class in that file).

### B.4 Migration

One new table, no FKs: `CREATE TABLE setting (id INTEGER PRIMARY KEY, shop_name VARCHAR NULL)`. Standard `alembic revision --autogenerate`, reviewed, date-prefixed filename, continuing from whatever the head is at implementation time.

### B.5 Frontend

- `services/settingsService.js` (new): `getSetting()` (`GET /settings`), `updateSetting(payload)` (`PUT /settings`) — same shape as every other service file, routed through `fetchClient`.
- `hooks/settingsHooks/settingsQueries.js` (new): `useSetting()`.
- `hooks/settingsHooks/settingsMutations.js` (new): `useUpdateSetting()`, invalidating `settingsKeys.detail()` on success.
- `utils/queryKeys.js`: add `settingsKeys = { all: ['settings'], detail: () => [...settingsKeys.all, 'detail'] }`.
- `validations/settingsSchemas.js` (new): `settingUpdateSchema = object({ shop_name: string().max(120).nullable() })` — mirrors `SettingUpdate` field-for-field per `CLAUDE.md` §1's Yup/Pydantic mirroring rule.
- **`containers/SettingsContainer.jsx`**: add one more `TabsTrigger`/`TabsContent` pair, e.g. `"shop"` / "Shop" (icon: `Store` from `lucide-react`), rendering a new `components/settings/ShopSettingsForm.jsx` — **not** a `CrudTable`/`CrudDrawer` pair, since there's no list here, just one row to edit in place. A small `react-hook-form` + Yup form (matching the shape of any other single-field settings form in this codebase, e.g. the size of `ExpenseForm.jsx`'s simplest fields) that loads via `useSetting()`, submits via `useUpdateSetting()`, and toasts success the same way every mutation already does via `fetchClient`.

### Files
New: `src/settings.py`, one migration, `services/settingsService.js`, `hooks/settingsHooks/{settingsQueries,settingsMutations}.js`, `validations/settingsSchemas.js`, `components/settings/ShopSettingsForm.jsx`.
Changed: `src/models.py` (add `Setting`), `src/main.py` (mount), `migrations/env.py`, `utils/queryKeys.js`, `containers/SettingsContainer.jsx`.

---

## Part C — Styled, multi-column, paginated export image

### C.1 What's changing from the MVP

The shipped MVP (`stock-list-share.md`) exports one plain list into one PNG via an isolated `<iframe>` + `html2canvas` (necessary because this app's Tailwind v4 stylesheet uses `oklch()`/`color-mix()` colors that both candidate screenshot libraries choke on — confirmed by hand: `html-to-image`'s canvas step hangs indefinitely with no error even on a trivial div; `html2canvas` throws `"Attempting to parse an unsupported color function 'oklch'"` outright. The isolated-iframe-with-plain-hex-CSS technique from the MVP is the reason either library works at all here, and everything below keeps using it). This phase asks for three additions on top of that foundation:

1. **Shop name** (Part B) printed at the top of the export, above the category.
2. **A more designed look** — not a plain list: a header banner, a category band, brand sections with dividers, models laid out in **3–4 columns** instead of one.
3. **Pagination** — if everything doesn't fit on one page at a readable size, continue on a second (or third, …) page, each downloaded as its own image.

### C.2 Column layout: CSS multi-column, scoped per page

Standard CSS `columns` (`column-count: 3; column-gap: ...`) is the right tool for "flow a list of brand blocks into N side-by-side columns" — but it only balances content across columns for whatever height the container naturally grows to; it has no concept of a second "sheet." Pagination (§C.3) is handled separately, one page's worth of content at a time, and *each page* gets its own multi-column container. Within one page:
```css
.page-columns { column-count: 3; column-gap: 24px; }
.brand-block { break-inside: avoid; margin-bottom: 16px; }
```
`break-inside: avoid` (a real, still-relevant CSS property for column/print layout, distinct from the print-only `@media print` rules that don't apply here) keeps one brand's model list from being visually split across a column boundary — matches the plan's original intent of keeping each brand's list a coherent, readable block.

### C.3 Pagination: a height-budget bin-pack over brand blocks, not real DOM measurement

There's no precedent anywhere in this codebase for splitting content across multiple export "pages" — this is new, and deliberately approximate rather than pixel-perfect, for the same reason the rest of this feature avoids unnecessary complexity: a heuristic that's right in the overwhelming majority of real cases is a better trade than a much more complex exact-measurement pass for a feature whose output is a WhatsApp image, not a print-ready document.

**Design:**
1. Define one **page budget** up front: a fixed page pixel size (e.g. `PAGE_WIDTH = 900`, `PAGE_HEIGHT = 1200` before the `scale: 2` html2canvas multiplier — a portrait shape comfortable to view full-size on a phone) and a **line-height budget**: given the chosen font sizes in `EXPORT_STYLES`, estimate how many "model lines" worth of vertical space one page holds, in one column, then multiply by `columnCount` for the page's total per-page capacity in "model lines" — e.g. `LINES_PER_PAGE = Math.floor((PAGE_HEIGHT - HEADER_HEIGHT) / LINE_HEIGHT_PX) * COLUMN_COUNT`.
2. Flatten `visibleGrouped` into a list of **brand blocks**, each carrying its own line cost: `{ category, brand, models, lineCost: models.length + 1 }` (the `+1` accounts for the brand's own heading line). Category headings are cheap enough (one line, shown once per category per page) to fold into whichever brand block starts that category on a given page rather than costing their own budget line — simpler than tracking them separately, and the visual difference is negligible.
3. **Greedily bin-pack** brand blocks into pages: walk the flattened list in order, accumulating `lineCost` into the current page's running total; when adding the next block would exceed `LINES_PER_PAGE`, close the current page and start a new one. A single brand block whose own `lineCost` exceeds a full page's budget (a brand with an extremely long model list) is **not** split — it gets its own page even if that page runs over budget, rather than fragmenting one brand's list across three pages for a edge case unlikely to occur in practice (a business with hundreds of models under one single brand). Flag this explicitly as an accepted edge case, not a silent bug.
4. Each resulting page is rendered as its own isolated-iframe document (§C.4), captured, and downloaded as `stock-list-page-{n}-of-{total}.png`. A single-page result (the common case, matching the MVP's typical dataset size) still goes through this same code path with `total = 1` — no special-casing "does this need pagination at all," which keeps this one code path instead of two.

```js
const PAGE_WIDTH = 900;
const PAGE_HEIGHT = 1200;
const COLUMN_COUNT = 3; // 4 if a page's brand blocks are short on average — see C.6
const HEADER_HEIGHT_LINES = 3; // shop name + category band, in "model line" units
const LINE_HEIGHT_PX = 22;

function paginateBrandBlocks(visibleGrouped) {
  const blocks = visibleGrouped.flatMap((cat) =>
    cat.brands.map((b) => ({ category: cat.category, brand: b.brand, models: b.models, lineCost: b.models.length + 1 })),
  );
  const linesPerPage = Math.floor((PAGE_HEIGHT / LINE_HEIGHT_PX - HEADER_HEIGHT_LINES)) * COLUMN_COUNT;

  const pages = [];
  let current = [];
  let currentLines = 0;
  for (const block of blocks) {
    if (currentLines > 0 && currentLines + block.lineCost > linesPerPage) {
      pages.push(current);
      current = [];
      currentLines = 0;
    }
    current.push(block);
    currentLines += block.lineCost;
  }
  if (current.length > 0) pages.push(current);
  return pages;
}
```

### C.4 Export document per page — shop name + category band + multi-column brands

Extends `buildExportDocument` from the MVP (same isolated-iframe technique, richer `EXPORT_STYLES`, one call per page instead of one call total):
```js
const EXPORT_STYLES = `
  body { margin: 0; padding: 0; width: ${PAGE_WIDTH}px; font-family: Arial, Helvetica, sans-serif; color: #111111; background: #ffffff; }
  .header { background: #1d4ed8; color: #ffffff; padding: 20px 28px; }
  .shop-name { font-size: 22px; font-weight: 700; margin: 0; }
  .category-band { background: #eff6ff; color: #1d4ed8; padding: 10px 28px; font-size: 15px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }
  .page-columns { column-count: ${COLUMN_COUNT}; column-gap: 24px; padding: 20px 28px; }
  .brand-block { break-inside: avoid; margin-bottom: 16px; }
  .brand-name { font-size: 14px; font-weight: 700; margin: 0 0 4px; border-bottom: 2px solid #1d4ed8; display: inline-block; padding-bottom: 2px; }
  .model-list { margin: 6px 0 0; padding-left: 18px; font-size: 13px; line-height: ${LINE_HEIGHT_PX}px; }
  .footer { padding: 10px 28px; font-size: 11px; color: #6b7280; text-align: right; }
`;

function buildPageDocument(shopName, blocks, pageNumber, totalPages) {
  const category = blocks[0]?.category ?? '';
  const body = `
    <div class="header"><p class="shop-name">${escapeHtml(shopName || 'Stock List')}</p></div>
    <div class="category-band">${escapeHtml(category)}</div>
    <div class="page-columns">
      ${blocks
        .map(
          (b) => `
        <div class="brand-block">
          <p class="brand-name">${escapeHtml(b.brand)}</p>
          <ul class="model-list">${b.models.map((m) => `<li>${escapeHtml(m.model)}</li>`).join('')}</ul>
        </div>`,
        )
        .join('')}
    </div>
    ${totalPages > 1 ? `<div class="footer">Page ${pageNumber} of ${totalPages}</div>` : ''}
  `;
  return `<!doctype html><html><head><meta charset="utf-8"><style>${EXPORT_STYLES}</style></head><body>${body}</body></html>`;
}
```
Colors (`#1d4ed8` blue, `#eff6ff` light blue band) are placeholders for "a bit stylish" — literal hex values, deliberately **not** this app's own `--primary`/Tailwind tokens, since those resolve through the same `oklch()` custom properties this whole isolation technique exists to avoid. Swap the hex values for whatever the shop's actual brand colors should be; the mechanism doesn't care what colors go in as long as they're literal hex/rgb, never a CSS custom property pointing back at the app's own stylesheet.

If a category spans more than one page (its brand blocks got split across the bin-packing boundary), the category band simply repeats at the top of each page that contains any of its blocks — reads naturally as "this page continues that category," matching how the MVP's category headings already only ever appear once per group, extended here to "once per group per page."

### C.5 `handleDownload` — one call per page

```js
const handleDownload = async () => {
  if (visibleGrouped.length === 0) return;
  setIsDownloading(true);
  try {
    const pages = paginateBrandBlocks(visibleGrouped);
    for (let i = 0; i < pages.length; i++) {
      const iframe = document.createElement('iframe');
      iframe.style.cssText = `position:fixed;left:-9999px;top:0;width:${PAGE_WIDTH}px;height:100px;border:0;`;
      document.body.appendChild(iframe);
      try {
        await new Promise((resolve) => {
          iframe.onload = resolve;
          iframe.srcdoc = buildPageDocument(shopName, pages[i], i + 1, pages.length);
        });
        iframe.style.height = `${iframe.contentDocument.body.scrollHeight}px`;
        const canvas = await html2canvas(iframe.contentDocument.body, { scale: 2, backgroundColor: '#ffffff' });
        const link = document.createElement('a');
        link.download = pages.length > 1 ? `stock-list-page-${i + 1}-of-${pages.length}.png` : 'stock-list.png';
        link.href = canvas.toDataURL('image/png');
        link.click();
      } finally {
        iframe.remove();
      }
    }
  } finally {
    setIsDownloading(false);
  }
};
```
Sequential downloads (`await`ed one at a time, not `Promise.all`) — triggering several `<a download>` clicks in a tight synchronous burst is what makes browsers flag them as pop-up-like and block everything after the first; awaiting `html2canvas` between each click keeps the pacing natural and avoids that.

`shopName` comes from `useSetting()` (Part B), read once at the top of `StockListShare`, alongside the existing `useStockList()` call.

### C.6 Column count: fixed at 3, not adaptive

The request said "three to four columns." Rather than a formula that guesses which of the two looks better per page (a source of surprising, hard-to-predict layout choices), fix `COLUMN_COUNT = 3` as a constant and treat 4 as a one-line manual tweak if it turns out to look better in practice once real data is in front of it — this is a cosmetic constant, not a structural decision, and the cheapest kind of thing to adjust after seeing the real output rather than guessing correctly up front.

### Files
Changed: `components/reporting/StockListShare.jsx` (new pagination + multi-page export logic, replacing the MVP's single-page `buildExportDocument`/`handleDownload`), reads `useSetting()` for `shopName`.
Not changed: `services/reportingService.js`, `hooks/reportingHooks/reportingQueries.js`, backend `reporting/*` — the underlying stock-list data/query is unchanged; only how it's turned into an image changes.

---

## Verification

**Part A**: open any Settings/Catalog tab's "Add" drawer, click the same "Add" button again without closing it (or close-then-reopen rapidly), confirm the form is always empty on a fresh create-open — not carrying over previous unsaved typing.

**Part B**: `GET /settings` before any row exists — confirm it creates and returns `{shop_name: null}` rather than 404/error. `PUT /settings {"shop_name": "Shakeel Mobile Accessories"}` — confirm it persists and a subsequent `GET` reflects it. Confirm the new "Shop" Settings tab loads the current value and saving it round-trips correctly.

**Part C**: with a small dataset (fits one page) — confirm exactly one PNG downloads, styled with the header/category band/3-column brand layout, shop name from Part B showing at the top. Seed enough stock (many brands/models) to deliberately exceed one page's line budget — confirm exactly the expected number of pages download in order, each with a correct "Page X of Y" footer, no brand's model list visibly split across two pages (barring the single-brand-too-long edge case in §C.3, which should visibly show as an intentionally over-budget page, not corrupted output).

## Implementation checklist

New: `src/settings.py`, one migration, `frontend/src/services/settingsService.js`, `frontend/src/hooks/settingsHooks/{settingsQueries,settingsMutations}.js`, `frontend/src/validations/settingsSchemas.js`, `frontend/src/components/settings/ShopSettingsForm.jsx`.

Changed: `frontend/src/components/common/{CrudTable,CrudDrawer}.jsx` (Part A), `backend/src/models.py`, `backend/src/main.py`, `backend/migrations/env.py`, `frontend/src/utils/queryKeys.js`, `frontend/src/containers/SettingsContainer.jsx`, `frontend/src/components/reporting/StockListShare.jsx` (Part C rewrite of the export logic).

Not changed: `backend/src/reporting/*` (Part C only changes how the already-fetched data is turned into an image), every other `CrudTable`/`CrudDrawer` consumer (Part A's fix is transparent to them).
