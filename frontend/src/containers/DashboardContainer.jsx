import { Card, CardContent } from '@/components/ui/card';
import { BalanceStatement } from '@/components/reporting/BalanceStatement';
import { SellThroughChart } from '@/components/reporting/SellThroughChart';
import { ReorderPriorityTable } from '@/components/reporting/ReorderPriorityTable';
import { MarginReportTable } from '@/components/reporting/MarginReportTable';
import { DateFilter } from '@/components/custom';
import { useAuth } from '@/hooks/authHooks/authHooks';
import { useDateFilter } from '@/hooks/useDateFilter';
import { useSearchParamFilters } from '@/hooks/useSearchParamFilters';

export function DashboardContainer() {
  const { user } = useAuth();
  // One period for Fast Movers and Margin (the Balance statement is always "now"; Reorder priority keeps its own
  // last-N-days window because it saves a recalculation). Default: the current month.
  const dates = useDateFilter(useSearchParamFilters());
  const periodComplete = Boolean(dates.dateFrom && dates.dateTo);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <Card className="border-none bg-primary/5">
        <CardContent className="py-2">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Welcome back{user?.username ? `, ${user.username}` : ''}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Here's where the business stands, and what to reorder from China next.
          </p>
        </CardContent>
      </Card>

      <BalanceStatement />
      <Card>
        <CardContent className="flex flex-col gap-2 py-4">
          <DateFilter filter={dates} id="dashboard_date" label="Period for Fast Movers and Margin" modes={['month', 'range']} className="max-w-xl" />
          {!periodComplete && <p className="text-sm text-muted-foreground">Pick both a From and a To date.</p>}
        </CardContent>
      </Card>
      <SellThroughChart dates={dates} />
      <ReorderPriorityTable />
      <MarginReportTable dates={dates} />
    </div>
  );
}
