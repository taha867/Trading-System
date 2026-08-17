import { useState } from 'react';
import html2canvas from 'html2canvas';
import { Loader2, Inbox, Share2, Download } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useStockList } from '@/hooks/reportingHooks/reportingQueries';
import { useSetting } from '@/hooks/settingsHooks/settingsQueries';

// Export page geometry — see paginateBrandBlocks/buildPageDocument below. Wide
// enough for several brand-block "cards" side by side, tall enough that a
// large multi-brand catalog packs into few pages instead of one page per
// screenful of rows.
const PAGE_WIDTH = 1000;
const PAGE_HEIGHT = 1500;
const MAX_COLUMNS = 4; // "as many columns as fit" — capped, not fixed; a sparse page uses fewer
const HEADER_HEIGHT_LINES = 3; // shop name banner + category band, in "line" units
const LINE_HEIGHT_PX = 20;

// entries arrive flat, already ordered (category, brand, model) by the backend query —
// grouping into two Maps preserves that order, so no re-sort is needed here.
function groupByCategoryAndBrand(entries) {
  const categories = new Map();
  for (const entry of entries) {
    if (!categories.has(entry.category)) categories.set(entry.category, new Map());
    const brands = categories.get(entry.category);
    if (!brands.has(entry.brand)) brands.set(entry.brand, []);
    brands.get(entry.brand).push({ model: entry.model, modelId: entry.model_id });
  }
  return Array.from(categories.entries()).map(([category, brands]) => ({
    category,
    brands: Array.from(brands.entries()).map(([brand, models]) => ({ brand, models })),
  }));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// Plain hex-color CSS, deliberately isolated from the app's own Tailwind
// stylesheet — both html-to-image and html2canvas fail on this app's real
// stylesheet (confirmed by hand: one hangs indefinitely inside its SVG→canvas
// step with no error, the other throws "Attempting to parse an unsupported
// color function 'oklch'" outright, since Tailwind v4's entire default
// palette resolves through oklch() custom properties neither library's color
// parser understands). Colors below are literal hex — swap them for the
// shop's real brand colors freely; the isolation only requires they never be
// a CSS custom property pointing back at the app's own stylesheet.
const EXPORT_STYLES = `
  body { margin: 0; padding: 0; width: ${PAGE_WIDTH}px; font-family: Arial, Helvetica, sans-serif; color: #111111; background: #ffffff; }
  .header { background: #1d4ed8; color: #ffffff; padding: 20px 28px; }
  .shop-name { font-size: 22px; font-weight: 700; margin: 0; }
  .subtitle { font-size: 12px; margin: 4px 0 0; opacity: 0.9; }
  .subtitle strong { font-weight: 700; }
  .category-band { background: #eff6ff; color: #1d4ed8; padding: 10px 28px; font-size: 15px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }
  .page-columns { column-gap: 16px; padding: 18px 28px; }
  .brand-block { break-inside: avoid; margin: 0 0 14px; padding: 8px 12px; background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 6px; }
  .brand-name { margin: 0 0 4px; font-size: 13px; font-weight: 700; text-decoration: underline; text-decoration-color: #1d4ed8; text-decoration-thickness: 2px; text-underline-offset: 3px; }
  .model-list { margin: 0; }
  .model-item { position: relative; margin: 0; padding-left: 12px; font-size: 12px; line-height: ${LINE_HEIGHT_PX}px; }
  .model-item::before { content: ''; position: absolute; left: 0; top: ${(LINE_HEIGHT_PX - 4) / 2}px; width: 4px; height: 4px; border-radius: 50%; background: #111111; }
  .footer { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 14px 28px; font-size: 14px; font-weight: 600; color: #ffffff; background: #1d4ed8; }
  .footer strong { font-weight: 700; }
`;

// Flattens visibleGrouped into one brand-block-per-row list, each carrying a
// rough "line cost" (model count + 1 for its own heading) used to bin-pack
// blocks into pages below. No existing precedent for export pagination in
// this codebase — this is a deliberately simple heuristic (not exact DOM
// measurement), matched to WhatsApp-image sharing rather than print fidelity.
function flattenToBrandBlocks(visibleGrouped) {
  return visibleGrouped.flatMap((cat) =>
    cat.brands.map((b) => ({ category: cat.category, brand: b.brand, models: b.models, lineCost: b.models.length + 1 })),
  );
}

// One column's line capacity, ignoring the page header (the header only
// costs space once per page, not once per column).
const LINES_PER_COLUMN = Math.floor(PAGE_HEIGHT / LINE_HEIGHT_PX) - HEADER_HEIGHT_LINES;

// Picks how many columns a page's own content should flow into — as many as
// fit (up to MAX_COLUMNS), capped by how many brand blocks are actually on the
// page. Sized off the block count, not the estimated line volume: the page is
// a fixed width regardless of how tall its content is, so a short page still
// wants every column filled (the column-balancer below packs short and tall
// blocks together to even out the heights) — fewer columns than blocks fit
// would just leave the right side of a wide page blank. The only time fewer
// columns is correct is when there simply aren't enough distinct brands to
// fill them (e.g. a single brand on its own page shouldn't render as 4 mostly
// empty columns).
function columnsForBlocks(blocks) {
  return Math.max(1, Math.min(MAX_COLUMNS, blocks.length));
}

// Greedily bin-packs brand blocks into pages so each page's total line cost
// stays within one page's multi-column line budget (capacity per column times
// up to MAX_COLUMNS) — this is what lets a large, many-brand catalog collapse
// into a handful of pages instead of one page per screenful of rows. A single
// brand block whose own cost exceeds a full page's budget is never split — it
// gets its own (over-budget) page rather than fragmenting one brand's list
// across pages, an accepted edge case for a shop with an unusually long
// single-brand catalog. The browser's own column-flow (see buildPageDocument)
// handles the actual per-column placement within a page; this only decides
// how much content belongs together on one page.
function paginateBrandBlocks(visibleGrouped) {
  const blocks = flattenToBrandBlocks(visibleGrouped);
  const linesPerPage = LINES_PER_COLUMN * MAX_COLUMNS;

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

// Builds one page's standalone HTML document. Each brand renders as one
// self-contained "card" (name + its full model list beneath it), and cards
// flow into a CSS multi-column layout — `break-inside: avoid` keeps a card
// from splitting across columns, and the browser's own column-balancing packs
// short and long brand cards together far more densely than a single
// Brand|Model table ever could, which is what collapses a large catalog into
// far fewer pages. The category band shows whichever category the page's
// first block belongs to — if a category's blocks span more than one page,
// the band simply repeats on each page that carries part of it, reading
// naturally as "this page continues that category."
function buildPageDocument(shopName, shopAddress, blocks, pageNumber, totalPages, asOfDate) {
  const category = blocks[0]?.category ?? '';
  const columns = columnsForBlocks(blocks);
  const cards = blocks
    .map(
      (b) => `
    <div class="brand-block">
      <p class="brand-name">${escapeHtml(b.brand)}</p>
      <div class="model-list">${b.models.map((m) => `<p class="model-item">${escapeHtml(m.model)}</p>`).join('')}</div>
    </div>`,
    )
    .join('');
  const body = `
    <div class="header">
      <p class="shop-name">${escapeHtml(shopName || 'Stock List')}</p>
      <p class="subtitle"><strong>Available Stock:</strong> ${escapeHtml(asOfDate)}</p>
    </div>
    <div class="category-band">${escapeHtml(category)}</div>
    <div class="page-columns" style="column-count: ${columns}">${cards}</div>
    ${
      shopAddress || totalPages > 1
        ? `<div class="footer">
      <span>${shopAddress ? `<strong>Address:</strong> ${escapeHtml(shopAddress)}` : ''}</span>
      <span>${totalPages > 1 ? `Page ${pageNumber} of ${totalPages}` : ''}</span>
    </div>`
        : ''
    }
  `;
  return `<!doctype html><html><head><meta charset="utf-8"><style>${EXPORT_STYLES}</style></head><body>${body}</body></html>`;
}

export function StockListShare() {
  // Off by default — only models with real recorded stock show up, matching
  // what the shop can actually fulfill right now. Switching this on bypasses
  // the stock filter entirely (every active model, regardless of StockLot
  // quantity) — for before real stock tracking is set up, without needing to
  // fake StockLot/PurchaseOrder rows against real accounting data to get there.
  const [showAllActive, setShowAllActive] = useState(false);
  const { data, isLoading, isError } = useStockList(!showAllActive);
  const { data: settingData } = useSetting();
  const shopName = settingData?.shop_name;
  const shopAddress = settingData?.shop_address;
  // Ephemeral UI state only — nothing here is submitted anywhere, so this is a
  // plain Set, not a react-hook-form field. A model is included unless its id
  // is in this set.
  const [excludedModelIds, setExcludedModelIds] = useState(() => new Set());
  const [isDownloading, setIsDownloading] = useState(false);

  // React Compiler handles memoization automatically (CLAUDE.md §3.6) — no
  // manual useMemo needed for these, and the dataset is small (a few hundred
  // rows at most).
  const entries = data?.entries ?? [];
  const grouped = groupByCategoryAndBrand(entries);
  const allModelIds = entries.map((e) => e.model_id);

  const toggleModel = (modelId) => {
    setExcludedModelIds((prev) => {
      const next = new Set(prev);
      if (next.has(modelId)) next.delete(modelId);
      else next.add(modelId);
      return next;
    });
  };

  const setGroupExcluded = (modelIds, excluded) => {
    setExcludedModelIds((prev) => {
      const next = new Set(prev);
      modelIds.forEach((id) => (excluded ? next.add(id) : next.delete(id)));
      return next;
    });
  };

  const visibleGrouped = grouped
    .map((cat) => ({
      category: cat.category,
      brands: cat.brands
        .map((b) => ({ brand: b.brand, models: b.models.filter((m) => !excludedModelIds.has(m.modelId)) }))
        .filter((b) => b.models.length > 0),
    }))
    .filter((cat) => cat.brands.length > 0);

  // Renders each page into its own isolated, off-screen <iframe> with the
  // plain hex-color stylesheet above, rather than capturing the on-screen
  // preview node directly — see EXPORT_STYLES's comment for why. Downloads
  // are sequential (awaited one at a time, not Promise.all/fired in a tight
  // burst) — clicking several <a download> links synchronously is what makes
  // browsers treat later ones as blocked pop-ups.
  const handleDownload = async () => {
    if (visibleGrouped.length === 0) return;
    setIsDownloading(true);
    try {
      const asOfDate = new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
      const pages = paginateBrandBlocks(visibleGrouped);
      for (let i = 0; i < pages.length; i++) {
        const iframe = document.createElement('iframe');
        iframe.style.cssText = `position:fixed;left:-9999px;top:0;width:${PAGE_WIDTH}px;height:100px;border:0;`;
        document.body.appendChild(iframe);
        try {
          await new Promise((resolve) => {
            iframe.onload = resolve;
            iframe.srcdoc = buildPageDocument(shopName, shopAddress, pages[i], i + 1, pages.length, asOfDate);
          });
          // Grow the iframe to fit its real content — html2canvas only captures
          // what's within the target element's own box, and an untouched 100px
          // starting height would clip anything longer than that.
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

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-4">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Share2 className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Stock List Share</CardTitle>
            <CardDescription>
              {showAllActive
                ? 'Every active model, regardless of recorded stock — uncheck what you don\'t want to share, then download an image.'
                : "Everything currently in stock — uncheck what you don't want to share, then download an image."}
            </CardDescription>
          </div>
        </div>
        <CardAction className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setExcludedModelIds(new Set())}>
            Select all
          </Button>
          <Button size="sm" variant="outline" onClick={() => setExcludedModelIds(new Set(allModelIds))}>
            Deselect all
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent>
        <label className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
          <Checkbox checked={showAllActive} onCheckedChange={(checked) => setShowAllActive(Boolean(checked))} />
          Show all active models (not just what's currently in stock)
        </label>

        {isLoading && (
          <div className="flex h-32 flex-col items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            Loading…
          </div>
        )}
        {isError && <div className="flex h-32 items-center justify-center text-destructive">Failed to load.</div>}
        {!isLoading && !isError && entries.length === 0 && (
          <div className="flex h-32 flex-col items-center justify-center gap-2 text-muted-foreground">
            <Inbox className="size-6 text-muted-foreground/60" />
            {showAllActive ? 'No active models in the catalog yet.' : "Nothing currently in stock — try \"Show all active models.\""}
          </div>
        )}

        {!isLoading && !isError && entries.length > 0 && (
          <div className="flex flex-col gap-6 md:flex-row">
            <div className="flex min-w-0 flex-1 flex-col gap-4">
              {grouped.map((cat) => {
                const categoryModelIds = cat.brands.flatMap((b) => b.models.map((m) => m.modelId));
                return (
                  <div key={cat.category} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="font-semibold text-foreground">{cat.category}</h3>
                      <div className="flex gap-1">
                        <Button
                          type="button"
                          variant="link"
                          size="xs"
                          onClick={() => setGroupExcluded(categoryModelIds, false)}
                        >
                          All
                        </Button>
                        <Button
                          type="button"
                          variant="link"
                          size="xs"
                          onClick={() => setGroupExcluded(categoryModelIds, true)}
                        >
                          None
                        </Button>
                      </div>
                    </div>
                    <div className="mt-2 flex flex-col gap-3">
                      {cat.brands.map((b) => (
                        <div key={b.brand}>
                          <p className="text-sm font-medium text-muted-foreground">{b.brand}</p>
                          <div className="mt-1 flex flex-col gap-1.5">
                            {b.models.map((m) => (
                              <label key={m.modelId} className="flex items-center gap-2 text-sm">
                                <Checkbox
                                  checked={!excludedModelIds.has(m.modelId)}
                                  onCheckedChange={() => toggleModel(m.modelId)}
                                />
                                {m.model}
                              </label>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="flex min-w-0 flex-1 flex-col gap-3">
              <div className="overflow-hidden rounded-lg border bg-white text-black">
                {visibleGrouped.length === 0 && (
                  <p className="p-4 text-sm text-muted-foreground">Nothing selected.</p>
                )}
                {visibleGrouped.map((cat) => (
                  <div key={cat.category} className="border-b last:border-b-0">
                    <p className="bg-blue-50 px-4 py-2 text-xs font-bold uppercase tracking-wide text-blue-700">
                      {cat.category}
                    </p>
                    <div className="columns-1 gap-3 p-3 sm:columns-2 lg:columns-3">
                      {cat.brands.map((b) => (
                        <div
                          key={b.brand}
                          className="mb-3 break-inside-avoid rounded-md border bg-slate-50 px-3 py-2 text-sm"
                        >
                          <p className="mb-1 font-semibold underline decoration-blue-600 decoration-2 underline-offset-2">
                            {b.brand}
                          </p>
                          <ul className="list-disc pl-4">
                            {b.models.map((m) => (
                              <li key={m.modelId}>{m.model}</li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <Button onClick={handleDownload} disabled={isDownloading || visibleGrouped.length === 0}>
                <Download />
                {isDownloading ? 'Generating…' : 'Download image'}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
