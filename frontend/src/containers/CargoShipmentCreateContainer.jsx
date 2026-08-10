import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { CargoShipmentForm } from '@/components/cargo/form/CargoShipmentForm';

export function CargoShipmentCreateContainer() {
  const navigate = useNavigate();

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">New Cargo Shipment</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Attach open purchase orders and split the freight cost across their lines.
        </p>
      </div>
      <Card>
        <CardHeader className="border-b [.border-b]:pb-4">
          <CardTitle className="text-base">Shipment details</CardTitle>
          <CardDescription>At least one attached purchase order is required.</CardDescription>
        </CardHeader>
        <CardContent>
          <CargoShipmentForm onSuccess={(shipment) => navigate(`/cargo-shipments/${shipment.id}`)} />
        </CardContent>
      </Card>
    </div>
  );
}
