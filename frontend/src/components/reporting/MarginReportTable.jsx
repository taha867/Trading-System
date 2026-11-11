import { Link } from 'react-router-dom';
import { PieChart, Loader2, Inbox } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableFooter } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { useMarginReport } from '@/hooks/reportingHooks/reportingQueries';

// `dates` is the dashboard's shared period (useDateFilter): a month or a From – To range.
export function MarginReportTable({ dates }) {
  const { data, isLoading, isError } = useMarginReport({ dateFrom: dates.dateFrom, dateTo: dates.dateTo });
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
            <CardDescription>
              Sale rate vs. landed cost, per item, for {dates.label}.{' '}
              <Link to="/reports" className="text-primary hover:underline">
                See monthly profit
              </Link>
            </CardDescription>
          </div>
        </div>
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
                      No items sold in {dates.label}.
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
