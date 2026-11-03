import { useSearchParams } from 'react-router-dom';
import { ShoppingCart, FileQuestion } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { PurchaseOrderList } from '@/components/purchasing/PurchaseOrderList';
import { PurchaseLogExceptionList } from '@/components/purchasing/PurchaseLogExceptionList';

const DEFAULT_TAB = 'orders';

export function PurchaseOrdersContainer() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get('tab') || DEFAULT_TAB;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Purchase Orders</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Buy stock from China vendors in RMB (snapshotted to PKR at that day's rate), or record local and Mohsin
          purchases in PKR.
        </p>
      </div>

      {/* Switching tabs replaces the whole query string on purpose: the two lists have different
          filters, and a stale search/month from one should not leak into the other. */}
      <Tabs value={tab} onValueChange={(value) => setSearchParams({ tab: value })}>
        <div className="overflow-x-auto">
          <TabsList>
            <TabsTrigger value="orders">
              <ShoppingCart className="size-4" />
              Orders
            </TabsTrigger>
            <TabsTrigger value="other">
              <FileQuestion className="size-4" />
              Other entries
            </TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="orders" className="pt-4">
          <PurchaseOrderList />
        </TabsContent>
        <TabsContent value="other" className="pt-4">
          <PurchaseLogExceptionList />
        </TabsContent>
      </Tabs>
    </div>
  );
}
