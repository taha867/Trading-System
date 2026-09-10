import { useState } from 'react';
import { Loader2, Inbox, TriangleAlert } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { PaginationControls } from '@/components/common/PaginationControls';
import { ModelCombobox } from '@/components/custom';
import { useStockMovements } from '@/hooks/inventoryHooks/inventoryQueries';
import { useCategories } from '@/hooks/catalogHooks/categoryQueries';
import { useBrands } from '@/hooks/catalogHooks/brandQueries';
import { LOOKUP_PAGE } from '@/utils/queryParams';

const PAGE_SIZE = 20;
// Radix Select can't represent "no selection" as an empty-string item value —
// matches StockLotTable.jsx's own sentinel convention for the same reason.
const ALL_VALUE = '__all__';

function itemSubLabel(movement) {
  const parts = [movement.category_name, movement.item_sku].filter(Boolean);
  return parts.join(' · ') + (movement.item_variant ? ` (${movement.item_variant})` : '');
}

// Every stock lot's own quantities (qty_remaining) already exclude whatever's
// been marked damaged here — this list is purely a record of what happened
// and why, not a second source of truth for how much stock exists.
export function DamagedStockList() {
  const [page, setPage] = useState(1);
  const [categoryId, setCategoryId] = useState('');
  const [brandId, setBrandId] = useState('');
  const [modelId, setModelId] = useState('');

  const { data: categoriesData } = useCategories(LOOKUP_PAGE);
  const { data: brandsData } = useBrands(LOOKUP_PAGE);

  const { data, isLoading, isError } = useStockMovements({
    page,
    page_size: PAGE_SIZE,
    movement_type: 'damaged',
    category_id: categoryId || undefined,
    brand_id: brandId || undefined,
    model_id: modelId || undefined,
  });
  const movements = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalQty = data?.total_qty ?? 0;
  const hasActiveFilter = Boolean(categoryId || brandId || modelId);

  const handleCategoryChange = (value) => {
    setCategoryId(value === ALL_VALUE ? '' : value);
    setPage(1);
  };
  const handleBrandChange = (value) => {
    setBrandId(value === ALL_VALUE ? '' : value);
    setPage(1);
  };
  const handleModelChange = (value) => {
    setModelId(value);
    setPage(1);
  };

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-4">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-destructive/10 text-destructive">
            <TriangleAlert className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Damaged Stock</CardTitle>
            <CardDescription>Dead pieces, pulled out of sellable stock — not counted in Inventory anymore.</CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {!isLoading && !isError && (
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 rounded-lg border bg-muted/30 px-4 py-3">
            <span className="text-2xl font-semibold text-foreground">{totalQty}</span>
            <span className="text-sm text-muted-foreground">
              units damaged{hasActiveFilter ? ' matching the filters below' : ' across the whole catalog'} · {total}{' '}
              {total === 1 ? 'record' : 'records'}
            </span>
          </div>
        )}
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <Select value={categoryId || ALL_VALUE} onValueChange={handleCategoryChange}>
            <SelectTrigger className="w-full sm:w-48" aria-label="Category">
              <SelectValue placeholder="All categories" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VALUE}>All categories</SelectItem>
              {(categoriesData?.items ?? []).map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={brandId || ALL_VALUE} onValueChange={handleBrandChange}>
            <SelectTrigger className="w-full sm:w-48" aria-label="Brand">
              <SelectValue placeholder="All brands" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VALUE}>All brands</SelectItem>
              {(brandsData?.items ?? []).map((b) => (
                <SelectItem key={b.id} value={String(b.id)}>
                  {b.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="w-full sm:w-56">
            <ModelCombobox value={modelId} onChange={handleModelChange} label={null} />
          </div>
        </div>

        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>Date</TableHead>
                <TableHead>Model</TableHead>
                <TableHead className="text-right">Qty damaged</TableHead>
                <TableHead>Reason</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={4} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={4} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && movements.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      {hasActiveFilter ? 'No damaged stock matches these filters.' : 'No damaged stock recorded yet.'}
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {!isLoading &&
                !isError &&
                movements.map((movement) => (
                  <TableRow key={movement.id} className="hover:bg-muted/40">
                    <TableCell>{movement.movement_date}</TableCell>
                    <TableCell>
                      {movement.model_name}
                      <span className="ml-2 text-muted-foreground">{itemSubLabel(movement)}</span>
                    </TableCell>
                    <TableCell className="text-right font-medium text-destructive">
                      {-Number(movement.qty_delta)}
                    </TableCell>
                    <TableCell className="max-w-60 truncate" title={movement.reason ?? ''}>
                      {movement.reason || '—'}
                    </TableCell>
                  </TableRow>
                ))}
            </TableBody>
          </Table>
        </div>
        {!isLoading && !isError && total > 0 && (
          <PaginationControls page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
        )}
      </CardContent>
    </Card>
  );
}
