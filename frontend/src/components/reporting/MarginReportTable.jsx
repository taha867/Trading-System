import { useState } from 'react';
import { PieChart, Loader2, Inbox } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableFooter } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { FormSelect } from '@/components/custom';
import { useMarginReport } from '@/hooks/reportingHooks/reportingQueries';
import { WINDOW_DAYS_OPTIONS, DEFAULT_WINDOW_DAYS } from '@/utils/constants';

export function MarginReportTable() {
  const [windowDays, setWindowDays] = useState(String(DEFAULT_WINDOW_DAYS));
  const { data, isLoading, isError } = useMarginReport(Number(windowDays));
  const entries = data?.entries ?? [];

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-4">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <PieChart className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Margin by Item</CardTitle>
            <CardDescription>Sale rate vs. landed cost, per item, for items sold in the selected window.</CardDescription>
          </div>
        </div>
        <CardAction>
          <FormSelect
            name="margin_window"
            options={WINDOW_DAYS_OPTIONS}
            value={windowDays}
            onChange={setWindowDays}
            className="w-full sm:w-40"
          />
        </CardAction>
      </CardHeader>

      <CardContent>
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>SKU</TableHead>
                <TableHead>Model</TableHead>
                <TableHead className="text-right">Qty sold</TableHead>
                <TableHead className="text-right">Revenue</TableHead>
                <TableHead className="text-right">Cost</TableHead>
                <TableHead className="text-right">Margin</TableHead>
                <TableHead className="text-right">Margin %</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && entries.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No items sold in this window.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {entries.map((entry) => (
                <TableRow key={entry.item_id} className="hover:bg-muted/40">
                  <TableCell>{entry.sku}</TableCell>
                  <TableCell>{entry.model_name}</TableCell>
                  <TableCell className="text-right">{entry.qty_sold}</TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={entry.revenue_pkr} />
                  </TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={entry.cost_pkr} />
                  </TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={entry.margin_pkr} />
                  </TableCell>
                  <TableCell className="text-right">{entry.margin_pct.toFixed(1)}%</TableCell>
                </TableRow>
              ))}
            </TableBody>
            {!isLoading && !isError && entries.length > 0 && (
              <TableFooter>
                <TableRow>
                  <TableCell colSpan={3} className="font-medium text-foreground">
                    Total
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    <CurrencyAmount value={data.total_revenue_pkr} />
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    <CurrencyAmount value={data.total_cost_pkr} />
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    <CurrencyAmount value={data.total_margin_pkr} />
                  </TableCell>
                  <TableCell />
                </TableRow>
              </TableFooter>
            )}
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
