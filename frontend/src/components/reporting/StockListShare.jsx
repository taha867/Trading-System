import { useState } from 'react';
import html2canvas from 'html2canvas';
import { Loader2, Inbox, Share2, Download } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { useStockList } from '@/hooks/reportingHooks/reportingQueries';
import { useSetting } from '@/hooks/settingsHooks/settingsQueries';
import {
  SELECT_ALL_VALUE,
  STOCK_LIST_PAGE_WIDTH,
  STOCK_LIST_MAX_COLUMNS,
  STOCK_LIST_LINES_PER_COLUMN,
  STOCK_LIST_EXPORT_STYLES,
} from '@/utils/constants';

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

function slugify(text) {
  const slug = String(text)
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
  return slug || 'category';
}

// A single category's model list is numbered sequentially, continuing across
// every brand within that category (matching the reference design: iPhone's
// last model might be #20, and Redmi's first model right after it is #21) —
// this is why numbering is assigned once per category, before any pagination
// splits the brands across pages/columns.
function assignSequentialNumbers(brands) {
  let counter = 1;
  return brands.map((b) => ({
    brand: b.brand,
    models: b.models.map((m) => ({ ...m, number: counter++ })),
  }));
}

// Flattens one category's numbered brands into one brand-block-per-row list,
// each carrying a rough "line cost" (model count + 1 for its own heading)
// used to bin-pack blocks into pages below. No existing precedent for export
// pagination in this codebase — this is a deliberately simple heuristic (not
// exact DOM measurement), matched to WhatsApp-image sharing rather than print
// fidelity.
function toBrandBlocks(numberedBrands) {
  return numberedBrands.map((b) => ({ brand: b.brand, models: b.models, lineCost: b.models.length + 1 }));
}

// Picks how many columns a page's own content should flow into — as many as
// fit (up to STOCK_LIST_MAX_COLUMNS), capped by how many brand blocks are actually on the
// page. Sized off the block count, not the estimated line volume: the page is
// a fixed width regardless of how tall its content is, so a short page still
// wants every column filled (the column-balancer below packs short and tall
// blocks together to even out the heights) — fewer columns than blocks fit
// would just leave the right side of a wide page blank. The only time fewer
// columns is correct is when there simply aren't enough distinct brands to
// fill them (e.g. a single brand on its own page shouldn't render as 4 mostly
// empty columns).
function columnsForBlocks(blocks) {
  return Math.max(1, Math.min(STOCK_LIST_MAX_COLUMNS, blocks.length));
}

// Greedily bin-packs one category's brand blocks into pages so each page's
// total line cost stays within one page's multi-column line budget (capacity
// per column times up to STOCK_LIST_MAX_COLUMNS) — this is what lets a large, many-brand
// category collapse into a handful of pages instead of one page per
// screenful of rows. A single brand block whose own cost exceeds a full
// page's budget is never split — it gets its own (over-budget) page rather
// than fragmenting one brand's list across pages, an accepted edge case for a
// shop with an unusually long single-brand catalog. The browser's own
// column-flow (see buildPageDocument) handles the actual per-column placement
// within a page; this only decides how much content belongs together on one
// page.
function paginateBlocks(blocks) {
  const linesPerPage = STOCK_LIST_LINES_PER_COLUMN * STOCK_LIST_MAX_COLUMNS;

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

// Builds one page's standalone HTML document. Every page belongs to exactly
// one category — the whole page is a title page for that category (large
// bold category name + "Available Models" subtitle), not a shop-wide banner —
// and each brand renders as one self-contained "card" (name + its
// sequentially-numbered model list beneath it) that flows into a CSS
// multi-column layout. `break-inside: avoid` keeps a card from splitting
// across columns, and the browser's own column-balancing packs short and
// long brand cards together far more densely than a single Brand|Model table
// ever could, which is what collapses a large category into far fewer pages.
function buildPageDocument(shopName, shopAddress, category, blocks, pageNumber, totalPages) {
  const columns = columnsForBlocks(blocks);
  const cards = blocks
    .map(
      (b) => `
    <div class="brand-block">
      <p class="brand-name">${escapeHtml(b.brand)}</p>
      <div class="model-list">${b.models
        .map((m) => `<p class="model-item"><span class="model-number">${m.number}.</span> ${escapeHtml(m.model)}</p>`)
        .join('')}</div>
    </div>`,
    )
    .join('');
  const body = `
    <div class="title-block">
      <p class="category-title">${escapeHtml(category)}</p>
      <p class="category-subtitle">Available Models</p>
    </div>
    <hr class="divider" />
    <div class="page-columns" style="column-count: ${columns}">${cards}</div>
    <div class="footer">
      <p class="footer-shop">${escapeHtml(shopName || 'Stock List')}</p>
      ${shopAddress ? `<p class="footer-address">${escapeHtml(shopAddress)}</p>` : ''}
      ${totalPages > 1 ? `<p class="footer-page">Page ${pageNumber} of ${totalPages}</p>` : ''}
    </div>
  `;
  return `<!doctype html><html><head><meta charset="utf-8"><style>${STOCK_LIST_EXPORT_STYLES}</style></head><body>${body}</body></html>`;
}

// Every category becomes its own independent set of pages — numbering resets
// to 1 at the start of each category (see assignSequentialNumbers) since a
// category's export reads as its own standalone document (e.g. a "Dust Plug"
// list handed to a customer on its own), not a chapter of one combined file.
function buildCategoryDocuments(visibleGrouped, shopName, shopAddress) {
  const documents = [];
  for (const cat of visibleGrouped) {
    const numberedBrands = assignSequentialNumbers(cat.brands);
    const blocks = toBrandBlocks(numberedBrands);
    const pages = paginateBlocks(blocks);
    pages.forEach((pageBlocks, index) => {
      documents.push({
        category: cat.category,
        pageNumber: index + 1,
        totalPages: pages.length,
        html: buildPageDocument(shopName, shopAddress, cat.category, pageBlocks, index + 1, pages.length),
      });
    });
  }
  return documents;
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
  // Ephemeral UI state only — nothing here is submitted anywhere, so these are
  // plain useState, not react-hook-form fields.
  const [excludedModelIds, setExcludedModelIds] = useState(() => new Set());
  const [selectedCategory, setSelectedCategory] = useState(SELECT_ALL_VALUE);
  const [isDownloading, setIsDownloading] = useState(false);

  // React Compiler handles memoization automatically (CLAUDE.md §3.6) — no
  // manual useMemo needed for these, and the dataset is small (a few hundred
  // rows at most).
  const entries = data?.entries ?? [];
  const groupedAll = groupByCategoryAndBrand(entries);
  // The category selector's own options always reflect every category the
  // current stock filter (showAllActive) has, regardless of which one is
  // currently selected — so switching categories never requires resetting
  // back to "All categories" first.
  const categoryOptions = groupedAll.map((c) => c.category);
  const grouped =
    selectedCategory === SELECT_ALL_VALUE ? groupedAll : groupedAll.filter((c) => c.category === selectedCategory);
  // "Select all" / "Deselect all" scope to whatever's currently visible (all
  // categories, or just the one picked above) — picking one category and
  // hitting "print that only" shouldn't require also manually excluding every
  // other category's models first.
  const visibleModelIds = grouped.flatMap((cat) => cat.brands.flatMap((b) => b.models.map((m) => m.modelId)));

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
  // preview node directly — see STOCK_LIST_EXPORT_STYLES's comment for why. Downloads
  // are sequential (awaited one at a time, not Promise.all/fired in a tight
  // burst) — clicking several <a download> links synchronously is what makes
  // browsers treat later ones as blocked pop-ups. Each category downloads as
  // its own file (or its own numbered set of files, if it spans multiple
  // pages) — picking "Dust Plug" alone downloads just dust-plug.png.
  const handleDownload = async () => {
    if (visibleGrouped.length === 0) return;
    setIsDownloading(true);
    try {
      const documents = buildCategoryDocuments(visibleGrouped, shopName, shopAddress);
      for (const doc of documents) {
        const iframe = document.createElement('iframe');
        iframe.style.cssText = `position:fixed;left:-9999px;top:0;width:${STOCK_LIST_PAGE_WIDTH}px;height:100px;border:0;`;
        document.body.appendChild(iframe);
        try {
          await new Promise((resolve) => {
            iframe.onload = resolve;
            iframe.srcdoc = doc.html;
          });
          // Grow the iframe to fit its real content — html2canvas only captures
          // what's within the target element's own box, and an untouched 100px
          // starting height would clip anything longer than that.
          iframe.style.height = `${iframe.contentDocument.body.scrollHeight}px`;
          const canvas = await html2canvas(iframe.contentDocument.body, { scale: 2, backgroundColor: '#ffffff' });
          const link = document.createElement('a');
          const slug = slugify(doc.category);
          link.download = doc.totalPages > 1 ? `${slug}-page-${doc.pageNumber}-of-${doc.totalPages}.png` : `${slug}.png`;
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
          <Button
            size="sm"
            variant="outline"
            onClick={() => setExcludedModelIds((prev) => new Set([...prev, ...visibleModelIds]))}
          >
            Deselect all
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <Checkbox checked={showAllActive} onCheckedChange={(checked) => setShowAllActive(Boolean(checked))} />
            Show all active models (not just what's currently in stock)
          </label>
          <Select value={selectedCategory} onValueChange={setSelectedCategory}>
            <SelectTrigger className="w-full sm:w-56" aria-label="Category">
              <SelectValue placeholder="All categories" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={SELECT_ALL_VALUE}>All categories</SelectItem>
              {categoryOptions.map((category) => (
                <SelectItem key={category} value={category}>
                  {category}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

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
        {!isLoading && !isError && entries.length > 0 && grouped.length === 0 && (
          <div className="flex h-32 flex-col items-center justify-center gap-2 text-muted-foreground">
            <Inbox className="size-6 text-muted-foreground/60" />
            No models in this category.
          </div>
        )}

        {!isLoading && !isError && grouped.length > 0 && (
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
              <div className="flex flex-col gap-4 overflow-hidden rounded-lg border bg-white text-black">
                {visibleGrouped.length === 0 && (
                  <p className="p-4 text-sm text-muted-foreground">Nothing selected.</p>
                )}
                {visibleGrouped.map((cat) => (
                  <div key={cat.category} className="border-b pb-4 last:border-b-0 last:pb-0">
                    <div className="px-4 pt-4 text-center">
                      <p className="text-lg font-extrabold uppercase tracking-wide text-blue-900">{cat.category}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">Available Models</p>
                    </div>
                    <hr className="mx-4 mt-3 border-blue-900" />
                    <div className="columns-1 gap-3 p-4 sm:columns-2 lg:columns-3">
                      {assignSequentialNumbers(cat.brands).map((b) => (
                        <div
                          key={b.brand}
                          className="mb-3 break-inside-avoid rounded-md border bg-slate-50 px-3 py-2 text-sm"
                        >
                          <p className="mb-1 font-semibold text-blue-700 underline decoration-blue-600 decoration-2 underline-offset-2">
                            {b.brand}
                          </p>
                          <div className="flex flex-col">
                            {b.models.map((m) => (
                              <p key={m.modelId}>
                                <span className="inline-block min-w-5 font-medium text-muted-foreground">
                                  {m.number}.
                                </span>{' '}
                                {m.model}
                              </p>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                    <p className="px-4 text-center text-xs font-semibold text-muted-foreground">
                      {shopName || 'Stock List'}
                    </p>
                    {shopAddress && (
                      <p className="px-4 text-center text-[11px] text-muted-foreground/70">{shopAddress}</p>
                    )}
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
