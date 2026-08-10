import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { useCargoModes, useCargoCostBases } from '@/hooks/cargoHooks/cargoQueries';
import { usePurchaseOrders } from '@/hooks/purchasingHooks/purchasingQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { useCategories } from '@/hooks/catalogHooks/categoryQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';

const LOOKUP_PAGE = { page: 1, page_size: 100 };

export function CargoShipmentDetail({ shipment }) {
  const { data: partiesData } = useParties(LOOKUP_PAGE);
  const { data: modesData } = useCargoModes(LOOKUP_PAGE);
  const { data: costBasesData } = useCargoCostBases(LOOKUP_PAGE);
  // Unfiltered, not useDraftPurchaseOrders — a shipment's allocations reference lines
  // whose parent PO is now "allocated", not "draft".
  const { data: ordersData } = usePurchaseOrders(LOOKUP_PAGE);
  const { data: itemsData } = useItems(LOOKUP_PAGE);
  const { data: categoriesData } = useCategories(LOOKUP_PAGE);
  const { data: modelsData } = useModels(LOOKUP_PAGE);

  const agentNameById = Object.fromEntries((partiesData?.items ?? []).map((p) => [p.id, p.name]));
  const modeNameById = Object.fromEntries((modesData?.items ?? []).map((m) => [m.id, m.name]));
  const costBasisById = Object.fromEntries((costBasesData?.items ?? []).map((b) => [b.id, b]));
  const itemById = Object.fromEntries((itemsData?.items ?? []).map((i) => [i.id, i]));
  const categoryNameById = Object.fromEntries((categoriesData?.items ?? []).map((c) => [c.id, c.name]));
  const modelNameById = Object.fromEntries((modelsData?.items ?? []).map((m) => [m.id, m.name]));

  // Flatten every fetched PO's lines into one map keyed by line id — an allocation
  // only carries `purchase_order_line_id`, so this is the only way to resolve which
  // PO/item a given allocation row belongs to.
  const lineContextById = Object.fromEntries(
    (ordersData?.items ?? []).flatMap((po) => po.lines.map((line) => [line.id, { po, line }])),
  );

  function lineLabel(lineId) {
    const ctx = lineContextById[lineId];
    if (!ctx) return `Line #${lineId}`;
    const item = itemById[ctx.line.item_id];
    const itemPart = item
      ? [modelNameById[item.model_id], categoryNameById[item.category_id], item.sku].filter(Boolean).join(' · ')
      : `Item #${ctx.line.item_id}`;
    return `PO #${ctx.po.id} — ${itemPart}`;
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
                <TableCell>{lineLabel(allocation.purchase_order_line_id)}</TableCell>
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
