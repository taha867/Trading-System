import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { useCargoModes, useCargoCostBases } from '@/hooks/cargoHooks/cargoQueries';
import { usePurchaseOrders } from '@/hooks/purchasingHooks/purchasingQueries';
import { LOOKUP_PAGE } from '@/utils/queryParams';

export function CargoShipmentDetail({ shipment }) {
  const { data: partiesData } = useParties(LOOKUP_PAGE);
  const { data: modesData } = useCargoModes(LOOKUP_PAGE);
  const { data: costBasesData } = useCargoCostBases(LOOKUP_PAGE);
  // Unfiltered, not useDraftPurchaseOrders — a shipment's allocations reference lines
  // whose parent PO is now "allocated", not "draft". Only needed here to resolve
  // "which PO does this line belong to" (a CargoAllocation only carries
  // purchase_order_line_id) — the item/model/category label itself comes straight
  // off the line (PurchaseOrderLineRead embeds those, same as CargoAllocationRead).
  const { data: ordersData } = usePurchaseOrders(LOOKUP_PAGE);

  const agentNameById = Object.fromEntries((partiesData?.items ?? []).map((p) => [p.id, p.name]));
  const modeNameById = Object.fromEntries((modesData?.items ?? []).map((m) => [m.id, m.name]));
  const costBasisById = Object.fromEntries((costBasesData?.items ?? []).map((b) => [b.id, b]));

  const poIdByLineId = Object.fromEntries(
    (ordersData?.items ?? []).flatMap((po) => po.lines.map((line) => [line.id, po.id])),
  );

  function lineLabel(allocation) {
    const poId = poIdByLineId[allocation.purchase_order_line_id];
    const itemPart = [allocation.model_name, allocation.category_name, allocation.item_sku]
      .filter(Boolean)
      .join(' · ');
    return poId ? `PO #${poId} — ${itemPart}` : itemPart;
  }

  const costBasis = costBasisById[shipment.cost_basis_id];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Cargo Shipment #{shipment.id}</h2>
          <p className="text-sm text-muted-foreground">
            {agentNameById[shipment.cargo_agent_id] ?? `Party #${shipment.cargo_agent_id}`} ·{' '}
            {modeNameById[shipment.cargo_mode_id] ?? `Mode #${shipment.cargo_mode_id}`} · {shipment.shipment_date}
          </p>
        </div>
        <Badge variant="secondary">{costBasis?.name ?? `Basis #${shipment.cost_basis_id}`}</Badge>
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead>Line</TableHead>
              <TableHead>Basis figure</TableHead>
              <TableHead className="text-right">Allocated cost</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shipment.allocations.map((allocation) => (
              <TableRow key={allocation.id} className="hover:bg-muted/40">
                <TableCell>{lineLabel(allocation)}</TableCell>
                <TableCell>{allocation.basis_value}</TableCell>
                <TableCell className="text-right">
                  <CurrencyAmount value={allocation.allocated_cost_pkr} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex justify-end border-t pt-4 text-sm">
        <span>
          Total freight cost: <strong><CurrencyAmount value={shipment.total_cost_pkr} /></strong>
        </span>
      </div>
    </div>
  );
}
