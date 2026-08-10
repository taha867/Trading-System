import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { PurchaseOrderForm } from '@/components/purchasing/form/PurchaseOrderForm';

export function PurchaseOrderCreateContainer() {
  const navigate = useNavigate();

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">New Purchase Order</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Pick a vendor, add lines with qty and RMB rate — the PKR cost uses today's exchange rate.
        </p>
      </div>
      <Card>
        <CardHeader className="border-b [.border-b]:pb-4">
          <CardTitle className="text-base">Order details</CardTitle>
          <CardDescription>At least one line is required.</CardDescription>
        </CardHeader>
        <CardContent>
          <PurchaseOrderForm onSuccess={(order) => navigate(`/purchase-orders/${order.id}`)} />
        </CardContent>
      </Card>
    </div>
  );
}
