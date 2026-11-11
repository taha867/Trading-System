import { ProfitLossStatement } from '@/components/reporting/ProfitLossStatement';
import { useDateFilter } from '@/hooks/useDateFilter';
import { useSearchParamFilters } from '@/hooks/useSearchParamFilters';

export function ReportsContainer() {
  // The period lives in the URL (?month=2026-09 or ?from=..&to=..) so a report can be bookmarked or shared; a
  // missing or hand-edited (invalid) value falls back to the current month instead of erroring. A profit report
  // needs a bounded period, so there is no "all dates" here.
  const dates = useDateFilter(useSearchParamFilters());

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div className="print:hidden">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Reports</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          How much the business made or lost in a month or between two dates, based on what the stock cost and what it sold for.
        </p>
      </div>

      <ProfitLossStatement dates={dates} />
    </div>
  );
}
