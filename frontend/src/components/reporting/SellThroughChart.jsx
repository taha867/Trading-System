import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts';
import { TrendingUp, Loader2, Inbox } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
import { FormSelect } from '@/components/custom';
import { useSellThrough } from '@/hooks/reportingHooks/reportingQueries';
import { WINDOW_DAYS_OPTIONS, DEFAULT_WINDOW_DAYS } from '@/utils/constants';

const TOP_N = 10;

const chartConfig = {
  qty_sold: { label: 'Units sold', color: 'var(--chart-1)' },
};

export function SellThroughChart() {
  const [windowDays, setWindowDays] = useState(String(DEFAULT_WINDOW_DAYS));
  const { data, isLoading, isError } = useSellThrough(Number(windowDays));

  // Every active Model comes back, ranked 1..N — only the top N fastest
  // movers get charted here; the full ranked list, fast AND slow, is already
  // fully visible in ReorderPriorityTable right below this card.
  // qty_sold arrives as a JSON string (backend Decimal serialization) —
  // coerce to a real number before handing it to Recharts' numeric axis.
  const topEntries = (data?.entries ?? [])
    .slice(0, TOP_N)
    .map((entry) => ({ ...entry, qty_sold: Number(entry.qty_sold) }));

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-4">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <TrendingUp className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Fast Movers</CardTitle>
            <CardDescription>Top {TOP_N} models by units sold in the selected window.</CardDescription>
          </div>
        </div>
        <CardAction>
          <FormSelect
            name="sell_through_window"
            options={WINDOW_DAYS_OPTIONS}
            value={windowDays}
            onChange={setWindowDays}
            className="w-full sm:w-40"
          />
        </CardAction>
      </CardHeader>

      <CardContent>
        {isLoading && (
          <div className="flex h-72 flex-col items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            Loading…
          </div>
        )}
        {isError && <div className="flex h-72 items-center justify-center text-destructive">Failed to load.</div>}
        {!isLoading && !isError && topEntries.length === 0 && (
          <div className="flex h-72 flex-col items-center justify-center gap-2 text-muted-foreground">
            <Inbox className="size-6 text-muted-foreground/60" />
            No sales in this window yet.
          </div>
        )}
        {!isLoading && !isError && topEntries.length > 0 && (
          <ChartContainer config={chartConfig} className="h-72 w-full">
            <BarChart data={topEntries} layout="vertical" margin={{ left: 12 }}>
              <CartesianGrid horizontal={false} />
              <XAxis type="number" dataKey="qty_sold" hide />
              <YAxis type="category" dataKey="model_name" tickLine={false} axisLine={false} width={120} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="qty_sold" fill="var(--color-qty_sold)" radius={4} />
            </BarChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
