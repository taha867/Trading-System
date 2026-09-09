import { Fragment, useState } from 'react';
import { Loader2, Inbox, Boxes, SlidersHorizontal } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { PaginationControls } from '@/components/common/PaginationControls';
import { StockAdjustmentDialog } from '@/components/inventory/StockAdjustmentDialog';
import { useStockLots } from '@/hooks/inventoryHooks/inventoryQueries';

const PAGE_SIZE = 20;

function itemSubLabel(lot) {
  const parts = [lot.category_name, lot.item_sku].filter(Boolean);
  return parts.join(' · ') + (lot.item_variant ? ` (${lot.item_variant})` : '');
}

export function StockLotTable() {
  const [page, setPage] = useState(1);
  const [includeDepleted, setIncludeDepleted] = useState(false);
  const [adjustingLot, setAdjustingLot] = useState(null);

  // Real pagination — StockLotRead now carries its own item_sku/model_name/
  // category_name (see backend/src/inventory/schemas.py), so no more
  // whole-Items/Models/Categories-catalog LOOKUP_PAGE fetch is needed just to
  // label a page of rows. Grouping by model is a per-page display concern
  // now, not a whole-table one — a model's lots can span two pages.
  const { data, isLoading, isError } = useStockLots({ page, page_size: PAGE_SIZE, include_depleted: includeDepleted });
  const lots = data?.items ?? [];
  const total = data?.total ?? 0;

  const groupIndex = new Map();
  const groups = [];
  for (const lot of lots) {
    const key = `${lot.item_id}`;
    if (!groupIndex.has(key)) {
      groupIndex.set(key, groups.length);
      groups.push({ itemId: lot.item_id, modelName: lot.model_name, lots: [] });
    }
    groups[groupIndex.get(key)].lots.push(lot);
  }

  const handleIncludeDepletedChange = (checked) => {
    setIncludeDepleted(Boolean(checked));
    setPage(1);
  };

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-4">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Boxes className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Inventory</CardTitle>
            <CardDescription>Stock on hand, model by model — every lot at the rate it landed.</CardDescription>
          </div>
        </div>
        <CardAction>
          <label className="flex items-center gap-2 text-sm font-normal text-muted-foreground">
            <Checkbox checked={includeDepleted} onCheckedChange={handleIncludeDepletedChange} />
            Show depleted lots
          </label>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>Received</TableHead>
                <TableHead className="text-right">Qty received</TableHead>
                <TableHead className="text-right">Qty remaining</TableHead>
                <TableHead className="text-right">Landed cost/unit</TableHead>
                <TableHead className="text-right">Value remaining</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && groups.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No stock received yet — receive a purchase order line from its detail page.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {!isLoading &&
                !isError &&
                groups.map((group) => (
                  <Fragment key={group.itemId}>
                    <TableRow className="bg-muted/30">
                      <TableCell colSpan={4} className="font-medium text-foreground">
                        {group.modelName}
                        <span className="ml-2 font-normal text-muted-foreground">{itemSubLabel(group.lots[0])}</span>
                      </TableCell>
                      <TableCell colSpan={2} className="text-right font-medium text-foreground">
                        {group.lots.reduce((sum, lot) => sum + Number(lot.qty_remaining), 0)} on hand
                      </TableCell>
                    </TableRow>
                    {group.lots.map((lot) => (
                      <TableRow key={lot.id} className="hover:bg-muted/40">
                        <TableCell>{lot.received_date}</TableCell>
                        <TableCell className="text-right">{lot.qty_received}</TableCell>
                        <TableCell className="text-right">{lot.qty_remaining}</TableCell>
                        <TableCell className="text-right">
                          <CurrencyAmount value={lot.landed_cost_pkr} />
                        </TableCell>
                        <TableCell className="text-right">
                          <CurrencyAmount value={lot.value_remaining_pkr} />
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label={`Adjust stock lot #${lot.id}`}
                            onClick={() => setAdjustingLot(lot)}
                          >
                            <SlidersHorizontal />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </Fragment>
                ))}
            </TableBody>
          </Table>
        </div>
        {!isLoading && !isError && total > 0 && (
          <PaginationControls page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
        )}
      </CardContent>

      {adjustingLot && (
        <StockAdjustmentDialog
          open={Boolean(adjustingLot)}
          onOpenChange={(open) => !open && setAdjustingLot(null)}
          lot={adjustingLot}
        />
      )}
    </Card>
  );
}
