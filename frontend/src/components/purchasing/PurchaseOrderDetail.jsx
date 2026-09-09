import { useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { ReceiveStockLotDialog } from '@/components/inventory/ReceiveStockLotDialog';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { useReceivedLineIds } from '@/hooks/inventoryHooks/inventoryQueries';
import { LOOKUP_PAGE } from '@/utils/queryParams';

function lineItemLabel(line) {
  const parts = [line.model_name, line.category_name, line.item_sku];
  return parts.filter(Boolean).join(' · ') + (line.item_variant ? ` (${line.item_variant})` : '');
}

export function PurchaseOrderDetail({ order }) {
  const { data: partiesData } = useParties(LOOKUP_PAGE);
  const { ids: receivedLineIds } = useReceivedLineIds();
  const [receivingLine, setReceivingLine] = useState(null);

  const vendorNameById = Object.fromEntries((partiesData?.items ?? []).map((p) => [p.id, p.name]));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Purchase Order #{order.id}</h2>
          <p className="text-sm text-muted-foreground">
            {vendorNameById[order.party_id] ?? `Party #${order.party_id}`} · {order.order_date}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{order.status}</Badge>
          <Badge variant="secondary">{order.source === 'local' ? 'Local' : 'China'}</Badge>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead>Item</TableHead>
              <TableHead>Qty</TableHead>
              <TableHead>Rate (RMB)</TableHead>
              <TableHead>Rate (PKR)</TableHead>
              <TableHead className="text-right">Amount (RMB)</TableHead>
              <TableHead className="text-right">Amount (PKR)</TableHead>
              <TableHead>Landed cost/unit</TableHead>
              <TableHead className="text-right">Amount landed</TableHead>
              <TableHead>Receive</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {order.lines.map((line) => (
              <TableRow key={line.id} className="hover:bg-muted/40">
                <TableCell>{lineItemLabel(line)}</TableCell>
                <TableCell>{line.qty}</TableCell>
                <TableCell>
                  {line.rate_rmb != null ? <CurrencyAmount value={line.rate_rmb} currency="RMB" /> : '—'}
                </TableCell>
                <TableCell>
                  <CurrencyAmount value={line.rate_pkr} />
                </TableCell>
                <TableCell className="text-right">
                  {line.amount_rmb != null ? <CurrencyAmount value={line.amount_rmb} currency="RMB" /> : '—'}
                </TableCell>
                <TableCell className="text-right">
                  <CurrencyAmount value={line.amount_pkr} />
                </TableCell>
                <TableCell>
                  {line.landed_cost_pkr != null ? <CurrencyAmount value={line.landed_cost_pkr} /> : '—'}
                </TableCell>
                <TableCell className="text-right">
                  {line.amount_landed_pkr != null ? <CurrencyAmount value={line.amount_landed_pkr} /> : '—'}
                </TableCell>
                <TableCell>
                  {line.landed_cost_pkr == null ? (
                    '—'
                  ) : receivedLineIds.has(line.id) ? (
                    <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                      <CheckCircle2 className="size-4 text-primary" />
                      Received
                    </span>
                  ) : (
                    <Button size="sm" variant="outline" onClick={() => setReceivingLine(line)}>
                      Receive
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex justify-end gap-6 border-t pt-4 text-sm">
        <span>
          Total RMB: <strong>{order.total_rmb != null ? <CurrencyAmount value={order.total_rmb} currency="RMB" /> : '—'}</strong>
        </span>
        <span>
          Total PKR: <strong><CurrencyAmount value={order.total_pkr} /></strong>
        </span>
      </div>

      {receivingLine && (
        <ReceiveStockLotDialog
          open={Boolean(receivingLine)}
          onOpenChange={(open) => !open && setReceivingLine(null)}
          line={receivingLine}
          itemLabel={lineItemLabel(receivingLine)}
        />
      )}
    </div>
  );
}
