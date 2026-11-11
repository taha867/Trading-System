import { InvoiceList } from '@/components/sales/InvoiceList';

// One list: every invoice once, with its day-book entries (no stock found, bulk, correction, cancelled...) under it.
// Old links with ?tab=other (or ?kind=) just open this list; the filters it understands are read from the address.
export function SalesOrdersContainer() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Sales Orders</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Invoice a wholesale customer — stock is deducted FIFO and posts straight to their balance.
        </p>
      </div>
      <InvoiceList />
    </div>
  );
}
