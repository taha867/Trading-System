import { CargoShipmentList } from '@/components/cargo/CargoShipmentList';

export function CargoShipmentsContainer() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Cargo Shipments</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Split freight cost across purchase-order lines to get a true landed cost per item.
        </p>
      </div>
      <CargoShipmentList />
    </div>
  );
}
