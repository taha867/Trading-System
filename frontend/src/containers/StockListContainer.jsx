import { StockListShare } from '@/components/reporting/StockListShare';

export function StockListContainer() {
  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Stock List</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Curate what's currently in stock and download an image to send to your clients.
        </p>
      </div>

      <StockListShare />
    </div>
  );
}
