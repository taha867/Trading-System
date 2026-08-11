import { Card, CardContent } from '@/components/ui/card';
import { BalanceStatement } from '@/components/reporting/BalanceStatement';
import { SellThroughChart } from '@/components/reporting/SellThroughChart';
import { ReorderPriorityTable } from '@/components/reporting/ReorderPriorityTable';
import { MarginReportTable } from '@/components/reporting/MarginReportTable';
import { useAuth } from '@/hooks/authHooks/authHooks';

export function DashboardContainer() {
  const { user } = useAuth();

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
      <SellThroughChart />
      <ReorderPriorityTable />
      <MarginReportTable />
    </div>
  );
}
