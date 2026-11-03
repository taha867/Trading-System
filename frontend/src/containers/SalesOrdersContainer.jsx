import { useSearchParams } from 'react-router-dom';
import { Receipt, FileQuestion } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { SalesOrderList } from '@/components/sales/SalesOrderList';
import { SalesLogExceptionList } from '@/components/sales/SalesLogExceptionList';

const DEFAULT_TAB = 'invoices';

export function SalesOrdersContainer() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get('tab') || DEFAULT_TAB;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Sales Orders</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Invoice a wholesale customer — stock is deducted FIFO and posts straight to their balance.
        </p>
      </div>

      {/* Switching tabs replaces the whole query string on purpose: the two lists have different
          filters, and a stale search/month from one should not leak into the other. */}
      <Tabs value={tab} onValueChange={(value) => setSearchParams({ tab: value })}>
        <div className="overflow-x-auto">
          <TabsList>
            <TabsTrigger value="invoices">
              <Receipt className="size-4" />
              Invoices
            </TabsTrigger>
            <TabsTrigger value="other">
              <FileQuestion className="size-4" />
              Other entries
            </TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="invoices" className="pt-4">
          <SalesOrderList />
        </TabsContent>
        <TabsContent value="other" className="pt-4">
          <SalesLogExceptionList />
        </TabsContent>
      </Tabs>
    </div>
  );
}
