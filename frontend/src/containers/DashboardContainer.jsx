import { BalanceStatement } from '@/components/reporting/BalanceStatement';
import { SellThroughChart } from '@/components/reporting/SellThroughChart';
import { ReorderPriorityTable } from '@/components/reporting/ReorderPriorityTable';
import { MarginReportTable } from '@/components/reporting/MarginReportTable';

export function DashboardContainer() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8 sm:py-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          One screen for where the business stands, and what to reorder from China next.
        </p>
      </div>

      <BalanceStatement />
      <SellThroughChart />
      <ReorderPriorityTable />
      <MarginReportTable />
    </div>
  );
}
