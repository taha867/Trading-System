import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { SalesOrderForm } from '@/components/sales/form/SalesOrderForm';

export function SalesOrderCreateContainer() {
  const navigate = useNavigate();

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">New Sales Order</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Pick a customer, add lines with qty and PKR rate — stock is drawn oldest lot first.
        </p>
      </div>
      <Card>
        <CardHeader className="border-b [.border-b]:pb-4">
          <CardTitle className="text-base">Order details</CardTitle>
          <CardDescription>At least one line is required; each item may appear only once.</CardDescription>
        </CardHeader>
        <CardContent>
          <SalesOrderForm onSuccess={(order) => navigate(`/sales-orders/${order.id}`)} />
        </CardContent>
      </Card>
    </div>
  );
}
