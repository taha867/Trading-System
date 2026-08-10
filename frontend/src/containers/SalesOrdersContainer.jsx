import { SalesOrderList } from '@/components/sales/SalesOrderList';

export function SalesOrdersContainer() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Sales Orders</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Invoice a wholesale customer — stock is deducted FIFO and posts straight to their balance.
        </p>
      </div>
      <SalesOrderList />
    </div>
  );
}
