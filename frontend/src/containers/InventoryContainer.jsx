import { StockLotTable } from '@/components/inventory/StockLotTable';

export function InventoryContainer() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Inventory</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Stock on hand, lot by lot — receive a line from its purchase order to add to this view.
        </p>
      </div>
      <StockLotTable />
    </div>
  );
}
