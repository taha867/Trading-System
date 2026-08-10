import { PurchaseOrderList } from '@/components/purchasing/PurchaseOrderList';

export function PurchaseOrdersContainer() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Purchase Orders</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Buy stock from China vendors in RMB, snapshotted to PKR at that day's rate.
        </p>
      </div>
      <PurchaseOrderList />
    </div>
  );
}
