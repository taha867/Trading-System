import { PurchaseList } from '@/components/purchasing/PurchaseList';

// One list: every supplier invoice once, with its payable-only entries (money owed, no phone model) under it.
// Old links with ?tab=other just open this list; the filters it understands are read from the address.
export function PurchaseOrdersContainer() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Purchase Orders</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Buy stock from China vendors in RMB (snapshotted to PKR at that day's rate), or record local and Mohsin
          purchases in PKR.
        </p>
      </div>
      <PurchaseList />
    </div>
  );
}
