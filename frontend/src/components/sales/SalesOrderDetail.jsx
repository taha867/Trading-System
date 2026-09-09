import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { LOOKUP_PAGE } from '@/utils/queryParams';

function lineItemLabel(line) {
  const parts = [line.model_name, line.category_name, line.item_sku];
  return parts.filter(Boolean).join(' · ') + (line.item_variant ? ` (${line.item_variant})` : '');
}

export function SalesOrderDetail({ order }) {
  const { data: partiesData } = useParties(LOOKUP_PAGE);

  const customerNameById = Object.fromEntries((partiesData?.items ?? []).map((p) => [p.id, p.name]));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Sales Order #{order.id}</h2>
          <p className="text-sm text-muted-foreground">
            {customerNameById[order.party_id] ?? `Party #${order.party_id}`} · {order.order_date}
          </p>
        </div>
        <Badge variant={Number(order.total_margin_pkr) >= 0 ? 'secondary' : 'destructive'}>
          Margin <CurrencyAmount value={order.total_margin_pkr} className="ml-1" />
        </Badge>
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead>Item</TableHead>
              <TableHead className="text-right">Qty</TableHead>
              <TableHead className="text-right">Rate (PKR)</TableHead>
              <TableHead className="text-right">Amount (PKR)</TableHead>
              <TableHead className="text-right">Cost (PKR)</TableHead>
              <TableHead className="text-right">Margin (PKR)</TableHead>
              <TableHead>Drawn from</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {order.lines.map((line) => (
              <TableRow key={line.id} className="hover:bg-muted/40">
                <TableCell>{lineItemLabel(line)}</TableCell>
                <TableCell className="text-right">{line.qty}</TableCell>
                <TableCell className="text-right">
                  <CurrencyAmount value={line.rate_pkr} />
                </TableCell>
                <TableCell className="text-right">
                  <CurrencyAmount value={line.amount_pkr} />
                </TableCell>
                <TableCell className="text-right">
                  <CurrencyAmount value={line.cost_pkr} />
                </TableCell>
                <TableCell className="text-right">
                  <CurrencyAmount value={line.margin_pkr} />
                </TableCell>
                <TableCell>
                  <div className="flex flex-col gap-0.5 text-xs text-muted-foreground">
                    {line.consumptions.map((c) => (
                      <span key={c.stock_lot_id}>
                        Lot #{c.stock_lot_id}: {c.qty_consumed} @ <CurrencyAmount value={c.unit_cost_pkr} />
                      </span>
                    ))}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex justify-end gap-6 border-t pt-4 text-sm">
        <span>
          Total: <strong><CurrencyAmount value={order.total_pkr} /></strong>
        </span>
        <span>
          Total margin: <strong><CurrencyAmount value={order.total_margin_pkr} /></strong>
        </span>
      </div>
    </div>
  );
}
