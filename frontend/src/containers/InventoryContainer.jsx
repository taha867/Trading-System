import { useSearchParams } from 'react-router-dom';
import { Boxes, TriangleAlert } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { StockLotTable } from '@/components/inventory/StockLotTable';
import { DamagedStockList } from '@/components/inventory/DamagedStockList';

const DEFAULT_TAB = 'stock';

export function InventoryContainer() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get('tab') || DEFAULT_TAB;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Inventory</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Stock on hand, lot by lot — receive a line from its purchase order to add to this view.
        </p>
      </div>

      <Tabs value={tab} onValueChange={(value) => setSearchParams({ tab: value })}>
        <div className="mb-4 overflow-x-auto">
          <TabsList>
            <TabsTrigger value="stock">
              <Boxes className="size-4" />
              Stock on hand
            </TabsTrigger>
            <TabsTrigger value="damaged">
              <TriangleAlert className="size-4" />
              Damaged stock
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="stock">
          <StockLotTable />
        </TabsContent>
        <TabsContent value="damaged">
          <DamagedStockList />
        </TabsContent>
      </Tabs>
    </div>
  );
}
