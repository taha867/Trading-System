import { useState } from 'react';
import html2canvas from 'html2canvas';
import { Loader2, Inbox, Share2, Download } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useStockList } from '@/hooks/reportingHooks/reportingQueries';
import { useSetting } from '@/hooks/settingsHooks/settingsQueries';

// Export page geometry — see paginateBrandBlocks/buildPageDocument below.
const PAGE_WIDTH = 700;
const PAGE_HEIGHT = 1200;
const HEADER_HEIGHT_LINES = 3; // shop name banner + category band, in "table row" units
const ROW_HEIGHT_PX = 30;

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
  .stock-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
  .stock-table th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #1d4ed8; border-bottom: 2px solid #1d4ed8; padding: 10px 28px; }
  .stock-table td { font-size: 13px; padding: 7px 28px; border-bottom: 1px solid #e5e7eb; vertical-align: middle; }
  .stock-table .brand-cell { font-weight: 700; }
  .stock-table tr.zebra td { background: #f8fafc; }
  .footer { padding: 10px 28px; font-size: 11px; color: #6b7280; text-align: right; }
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

// Greedily bin-packs brand blocks into pages so each page's total line cost
// stays within one page's line budget. A single brand block whose own cost
// exceeds a full page's budget is never split — it gets its own (over-budget)
// page rather than fragmenting one brand's list across pages, an accepted
// edge case for a shop with an unusually long single-brand catalog.
function paginateBrandBlocks(visibleGrouped) {
  const blocks = flattenToBrandBlocks(visibleGrouped);
  const linesPerPage = Math.floor(PAGE_HEIGHT / ROW_HEIGHT_PX) - HEADER_HEIGHT_LINES;

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

// Builds one page's standalone HTML document. The category band shows
// whichever category the page's first block belongs to — if a category's
// blocks span more than one page, the band simply repeats on each page that
// carries part of it, reading naturally as "this page continues that category."
function buildPageDocument(shopName, blocks, pageNumber, totalPages, asOfDate) {
  const category = blocks[0]?.category ?? '';
  // One <tr> per model; the brand name only appears once per group via
  // rowspan, and every row in that group shares one zebra class so the
  // striping reads as "one band per brand," not "one band per model."
  const rows = blocks
    .map((b, blockIndex) => {
      const zebraClass = blockIndex % 2 === 1 ? ' class="zebra"' : '';
      return b.models
        .map(
          (m, modelIndex) => `
      <tr${zebraClass}>
        ${modelIndex === 0 ? `<td class="brand-cell" rowspan="${b.models.length}">${escapeHtml(b.brand)}</td>` : ''}
        <td>${escapeHtml(m.model)}</td>
      </tr>`,
        )
        .join('');
    })
    .join('');
  const body = `
    <div class="header">
      <p class="shop-name">${escapeHtml(shopName || 'Stock List')}</p>
      <p class="subtitle"><strong>Available Stock:</strong> ${escapeHtml(asOfDate)}</p>
    </div>
    <div class="category-band">${escapeHtml(category)}</div>
    <table class="stock-table">
      <colgroup><col style="width: 30%" /><col style="width: 70%" /></colgroup>
      <thead><tr><th>Brand</th><th>Model</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${totalPages > 1 ? `<div class="footer">Page ${pageNumber} of ${totalPages}</div>` : ''}
  `;
  return `<!doctype html><html><head><meta charset="utf-8"><style>${EXPORT_STYLES}</style></head><body>${body}</body></html>`;
}

export function StockListShare() {
  const { data, isLoading, isError } = useStockList();
  const { data: settingData } = useSetting();
  const shopName = settingData?.shop_name;
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
            iframe.srcdoc = buildPageDocument(shopName, pages[i], i + 1, pages.length, asOfDate);
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
              Everything currently in stock — uncheck what you don't want to share, then download an image.
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
            Nothing currently in stock.
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
                    <table className="w-full text-sm">
                      <tbody>
                        {cat.brands.map((b, brandIndex) =>
                          b.models.map((m, modelIndex) => (
                            <tr key={m.modelId} className={brandIndex % 2 === 1 ? 'bg-slate-50' : undefined}>
                              {modelIndex === 0 && (
                                <td
                                  rowSpan={b.models.length}
                                  className="whitespace-nowrap border-r px-4 py-1.5 align-middle font-semibold"
                                >
                                  {b.brand}
                                </td>
                              )}
                              <td className="w-full px-4 py-1.5">{m.model}</td>
                            </tr>
                          )),
                        )}
                      </tbody>
                    </table>
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
