import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  TrendingUp,
  Receipt,
  Coins,
  Banknote,
  Scale,
  Printer,
  ChevronLeft,
  ChevronRight,
  TriangleAlert,
  Loader2,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { StatCard } from '@/components/common/StatCard';
import { useProfitLoss } from '@/hooks/reportingHooks/reportingQueries';
import { currentMonth, monthBounds, monthLabel, shiftMonth } from '@/utils/dateUtils';
import { cn } from '@/lib/utils';

// Display-only ratio between two amounts the server already computed — the one place
// the client does arithmetic on money-derived numbers, and never to produce a figure
// that gets stored or re-sent. "—" when there is nothing to compare against.
function changeLabel(current, previous) {
  const prev = Number(previous);
  if (previous == null || !prev) return '—';
  const change = ((Number(current) - prev) / Math.abs(prev)) * 100;
  return `${change > 0 ? '+' : ''}${change.toFixed(1)}%`;
}

// One flat list of statement lines, rendered both as a table (sm+) and as stacked
// cards (below sm) — CLAUDE.md §3.7: a 4-column table hides the figure a phone user
// actually wants.
function buildLines(current, previous) {
  const categoryTotal = (period, categoryId) =>
    period?.expenses_by_category.find((c) => c.category_id === categoryId)?.total_pkr ?? '0.00';

  const categories = [...current.expenses_by_category];
  for (const entry of previous?.expenses_by_category ?? []) {
    if (!categories.some((c) => c.category_id === entry.category_id)) categories.push(entry);
  }

  const line = (id, label, key, extra = {}) => ({
    id,
    label,
    current: current[key],
    previous: previous ? previous[key] : null,
    ...extra,
  });

  return [
    line('revenue', 'Sales revenue', 'revenue_pkr'),
    line('cogs', 'Cost of goods sold', 'cogs_pkr', { deduct: true, hint: 'Landed cost of the stock sold, oldest stock first' }),
    line('gross', 'Gross profit', 'gross_profit_pkr', { strong: true }),
    line('gross_pct', 'Gross margin', 'gross_margin_pct', { pct: true }),
    line('stock_loss', 'Stock losses', 'stock_loss_pkr', { deduct: true, hint: 'Damaged and adjusted-away stock, at cost' }),
    { id: 'expenses_head', label: 'Expenses', heading: true },
    ...categories.map((category) => ({
      id: `expense-${category.category_id}`,
      label: category.category_name,
      current: categoryTotal(current, category.category_id),
      previous: previous ? categoryTotal(previous, category.category_id) : null,
      deduct: true,
      indent: true,
    })),
    line('expenses_total', 'Total expenses', 'expenses_total_pkr', { deduct: true }),
    line('net', 'Net profit', 'net_profit_pkr', { strong: true, signed: true }),
    line('net_pct', 'Net margin', 'net_margin_pct', { pct: true }),
    line('excluded', 'Not counted in profit', 'excluded_expenses_pkr', {
      hint: 'Personal and other spending outside the shop — recorded, but not a shop cost',
    }),
  ];
}

function LineValue({ line, value }) {
  if (value == null) return <span className="text-muted-foreground">—</span>;
  if (line.pct) return <span>{Number(value).toFixed(1)}%</span>;

  const isLoss = line.signed && Number(value) < 0;
  return (
    <span className={cn(isLoss && 'text-destructive')}>
      {line.deduct && Number(value) !== 0 && <span className="mr-0.5">−</span>}
      <CurrencyAmount value={value} />
    </span>
  );
}

export function ProfitLossStatement({ month, onMonthChange }) {
  const [comparePrevious, setComparePrevious] = useState(true);
  const bounds = monthBounds(month);
  const { data, isLoading, isError } = useProfitLoss({
    dateFrom: bounds?.from,
    dateTo: bounds?.to,
    comparePrevious,
  });

  const thisMonth = currentMonth();
  const current = data?.current;
  const previous = data?.previous ?? null;
  const lines = current ? buildLines(current, previous) : [];
  const showCompare = Boolean(previous);

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-4">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <TrendingUp className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Profit &amp; Loss — {monthLabel(month)}</CardTitle>
            <CardDescription>
              Sales minus what that stock cost you (freight included), minus stock losses and expenses.
            </CardDescription>
          </div>
        </div>
        <CardAction className="print:hidden">
          <Button variant="outline" onClick={() => window.print()}>
            <Printer />
            Print
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-6">
        <div className="flex flex-wrap items-end gap-3 print:hidden">
          <div className="flex items-end gap-2">
            <Button
              variant="outline"
              size="icon"
              aria-label="Previous month"
              onClick={() => onMonthChange(shiftMonth(month, -1))}
            >
              <ChevronLeft />
            </Button>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="report_month">Month</Label>
              <Input
                id="report_month"
                type="month"
                value={month}
                max={thisMonth}
                onChange={(event) => event.target.value && onMonthChange(event.target.value)}
              />
            </div>
            <Button
              variant="outline"
              size="icon"
              aria-label="Next month"
              disabled={month >= thisMonth}
              onClick={() => onMonthChange(shiftMonth(month, 1))}
            >
              <ChevronRight />
            </Button>
          </div>
          <div className="flex items-center gap-2 pb-2">
            <Checkbox
              id="compare_previous"
              checked={comparePrevious}
              onCheckedChange={(checked) => setComparePrevious(checked === true)}
            />
            <Label htmlFor="compare_previous">Compare with previous month</Label>
          </div>
        </div>

        {isLoading && (
          <div className="flex h-32 flex-col items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            Loading…
          </div>
        )}
        {isError && <div className="flex h-32 items-center justify-center text-destructive">Failed to load.</div>}

        {!isError && current && (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard icon={Receipt} label="Sales revenue" value={current.revenue_pkr} />
              <StatCard icon={Coins} label="Gross profit" value={current.gross_profit_pkr} />
              <StatCard icon={Banknote} label="Expenses" value={current.expenses_total_pkr} />
              <StatCard
                icon={Scale}
                label="Net profit"
                value={current.net_profit_pkr}
                valueClassName={Number(current.net_profit_pkr) < 0 ? 'text-destructive' : undefined}
              />
            </div>

            <p className="text-xs text-muted-foreground">
              {current.order_count} {current.order_count === 1 ? 'sale' : 'sales'} · {current.units_sold} units sold
            </p>

            {data.warnings.length > 0 && (
              <ul className="flex flex-col gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm">
                {data.warnings.map((warning) => (
                  <li key={warning} className="flex items-start gap-2 text-foreground">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0 text-destructive" />
                    {warning}
                  </li>
                ))}
              </ul>
            )}

            {Number(current.unitemised_sales_pkr) !== 0 && (
              <p className="text-sm print:hidden">
                <Link to={`/sales-orders?month=${month}&show=has_other_entries`} className="text-primary hover:underline">
                  View the sales without item data for {monthLabel(month)}
                </Link>
              </p>
            )}

            {/* sm and up: statement table */}
            <div className="hidden overflow-x-auto rounded-lg border sm:block">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/50">
                    <TableHead>Statement</TableHead>
                    <TableHead className="text-right">{monthLabel(month)}</TableHead>
                    {showCompare && (
                      <>
                        <TableHead className="text-right">{monthLabel(shiftMonth(month, -1))}</TableHead>
                        <TableHead className="text-right">Change</TableHead>
                      </>
                    )}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {lines.map((line) =>
                    line.heading ? (
                      <TableRow key={line.id} className="bg-muted/30">
                        <TableCell colSpan={showCompare ? 4 : 2} className="text-xs font-medium uppercase text-muted-foreground">
                          {line.label}
                        </TableCell>
                      </TableRow>
                    ) : (
                      <TableRow key={line.id} className={cn('hover:bg-muted/40', line.strong && 'bg-muted/20 font-semibold')}>
                        <TableCell className={cn(line.indent && 'pl-8')}>
                          {line.label}
                          {line.hint && <span className="block text-xs font-normal text-muted-foreground">{line.hint}</span>}
                        </TableCell>
                        <TableCell className="text-right">
                          <LineValue line={line} value={line.current} />
                        </TableCell>
                        {showCompare && (
                          <>
                            <TableCell className="text-right text-muted-foreground">
                              <LineValue line={line} value={line.previous} />
                            </TableCell>
                            <TableCell className="text-right text-muted-foreground">
                              {line.pct ? '—' : changeLabel(line.current, line.previous)}
                            </TableCell>
                          </>
                        )}
                      </TableRow>
                    ),
                  )}
                </TableBody>
              </Table>
            </div>

            {/* below sm: one stacked row per line */}
            <div className="flex flex-col gap-2 sm:hidden">
              {lines.map((line) =>
                line.heading ? (
                  <p key={line.id} className="mt-2 text-xs font-medium uppercase text-muted-foreground">
                    {line.label}
                  </p>
                ) : (
                  <div key={line.id} className={cn('rounded-lg border p-3', line.strong && 'bg-muted/30')}>
                    <div className="flex items-baseline justify-between gap-3">
                      <span className={cn('text-sm', line.strong ? 'font-semibold' : 'text-foreground')}>{line.label}</span>
                      <span className={cn('text-sm', line.strong && 'font-semibold')}>
                        <LineValue line={line} value={line.current} />
                      </span>
                    </div>
                    {showCompare && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        {monthLabel(shiftMonth(month, -1))}: <LineValue line={line} value={line.previous} />
                        {!line.pct && ` · ${changeLabel(line.current, line.previous)}`}
                      </p>
                    )}
                  </div>
                ),
              )}
            </div>

            <p className="text-xs text-muted-foreground">
              Buying stock and paying vendors are not costs here — stock only becomes a cost when it is sold or lost.
              Cash received from customers is not revenue either; sales count on the day they were made.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
