import { useParams, Link } from 'react-router-dom';
import { Loader2, ArrowLeft } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { PurchaseOrderDetail } from '@/components/purchasing/PurchaseOrderDetail';
import { usePurchaseOrder } from '@/hooks/purchasingHooks/purchasingQueries';

export function PurchaseOrderDetailContainer() {
  const { orderId } = useParams();
  const id = Number(orderId);
  const isValidId = Number.isInteger(id) && id > 0;

  const { data: order, isLoading, isError } = usePurchaseOrder(isValidId ? id : undefined);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Purchase Order</h1>
          <p className="mt-1 text-sm text-muted-foreground">Immutable once created — Phase 1 has no edit or delete.</p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link to="/purchase-orders">
            <ArrowLeft />
            Back to list
          </Link>
        </Button>
      </div>

      <Card>
        <CardContent className="py-6">
          {!isValidId || isError ? (
            <p className="py-10 text-center text-destructive">Purchase order not found.</p>
          ) : isLoading ? (
            <div className="flex flex-col items-center justify-center gap-2 py-10 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
              Loading…
            </div>
          ) : (
            <PurchaseOrderDetail order={order} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
