import { useSearchParams } from 'react-router-dom';
import { ProfitLossStatement } from '@/components/reporting/ProfitLossStatement';
import { currentMonth, isValidMonth } from '@/utils/dateUtils';

export function ReportsContainer() {
  const [searchParams, setSearchParams] = useSearchParams();

  // The month lives in the URL so a report can be bookmarked or shared; a missing or
  // hand-edited (invalid) value falls back to the current month instead of erroring.
  const requestedMonth = searchParams.get('month');
  const month = isValidMonth(requestedMonth) ? requestedMonth : currentMonth();

  const handleMonthChange = (nextMonth) => setSearchParams({ month: nextMonth }, { replace: true });

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div className="print:hidden">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Reports</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          How much the business made or lost in a month, based on what the stock cost and what it sold for.
        </p>
      </div>

      <ProfitLossStatement month={month} onMonthChange={handleMonthChange} />
    </div>
  );
}
