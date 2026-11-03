import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { ReceiveStockLotDialog } from '@/components/inventory/ReceiveStockLotDialog';
import { formatDateTime } from '@/utils/dateUtils';
import { PURCHASE_ORDER_SOURCE_BADGE_LABEL, PURCHASE_ORDER_STATUS_LABEL } from '@/utils/constants';

function lineItemLabel(line) {
  const parts = [line.model_name, line.category_name, line.item_sku];
  return parts.filter(Boolean).join(' · ') + (line.item_variant ? ` (${line.item_variant})` : '');
}

function Detail({ label, children }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium text-foreground">{children}</dd>
    </div>
  );
}

// What happened to a line after it was ordered, straight from the order's own detail response — the
// stock lot it was received into (if any) and the cargo freight allocated to it (China orders only).
// "Received" is whether a lot exists, never whether it is non-empty: a lot sold down to zero still
// means this line was received.
function StockAndCargo({ line, onReceive }) {
  const received = line.stock_lot_id != null;
  return (
    <div className="flex min-w-44 flex-col gap-1.5 text-xs text-muted-foreground">
      {line.landed_cost_pkr == null ? (
        <span>Waiting for freight to be allocated</span>
      ) : received ? (
        <span className="inline-flex items-start gap-1.5 text-sm text-foreground">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
          <span>
            Received {line.received_date}
            <span className="block text-xs text-muted-foreground">
              {line.qty_received} in · {line.qty_remaining} left
            </span>
          </span>
        </span>
      ) : (
        <Button size="sm" variant="outline" className="self-start" onClick={() => onReceive(line)}>
          Receive
        </Button>
      )}
      {line.cargo_shipment_id != null && (
        <span>
          <Link to={`/cargo-shipments/${line.cargo_shipment_id}`} className="text-primary hover:underline">
            Shipment #{line.cargo_shipment_id}
          </Link>{' '}
          ({line.cargo_shipment_date}) · freight <CurrencyAmount value={line.allocated_cost_pkr} />
        </span>
      )}
    </div>
  );
}

export function PurchaseOrderDetail({ order }) {
  const [receivingLine, setReceivingLine] = useState(null);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-foreground">
          {order.invoice_number ? `Invoice ${order.invoice_number}` : `Purchase Order #${order.id}`}
        </h2>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{PURCHASE_ORDER_STATUS_LABEL[order.status] ?? order.status}</Badge>
          <Badge variant="secondary">{PURCHASE_ORDER_SOURCE_BADGE_LABEL[order.source] ?? order.source}</Badge>
        </div>
      </div>

      <dl className="grid grid-cols-1 gap-4 rounded-lg border bg-muted/30 p-4 sm:grid-cols-2 lg:grid-cols-5">
        <Detail label="Invoice number">{order.invoice_number || '—'}</Detail>
        <Detail label="Purchase order ID">#{order.id}</Detail>
        <Detail label="Vendor">
          <Link to={`/parties/${order.party_id}`} className="text-primary hover:underline">
            {order.party_name}
          </Link>
        </Detail>
        <Detail label="Order date">{order.order_date}</Detail>
        <Detail label="Entered on">{formatDateTime(order.created_at)}</Detail>
      </dl>

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
              <TableHead>Stock &amp; cargo</TableHead>
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
                  <StockAndCargo line={line} onReceive={setReceivingLine} />
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

      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-sm font-medium text-foreground">Posted to ledger</h3>
          <Link to={`/parties/${order.party_id}`} className="text-sm text-primary hover:underline">
            View {order.party_name}'s statement
          </Link>
        </div>
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>Ledger date</TableHead>
                <TableHead>Account</TableHead>
                <TableHead className="text-right">Debit</TableHead>
                <TableHead className="text-right">Credit</TableHead>
                <TableHead>Entered on</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {order.ledger_entries.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="h-20 text-center text-muted-foreground">
                    No ledger entry is linked to this order.
                  </TableCell>
                </TableRow>
              )}
              {order.ledger_entries.map((entry) => (
                <TableRow key={entry.id} className="hover:bg-muted/40">
                  <TableCell>{entry.entry_date}</TableCell>
                  <TableCell>{entry.account}</TableCell>
                  <TableCell className="text-right">
                    {Number(entry.debit) > 0 ? <CurrencyAmount value={entry.debit} /> : '—'}
                  </TableCell>
                  <TableCell className="text-right">
                    {Number(entry.credit) > 0 ? <CurrencyAmount value={entry.credit} /> : '—'}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(entry.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        {order.ledger_entries.length > 0 && (
          <p className="text-xs text-muted-foreground">
            A credit to Accounts Payable adds to what you owe {order.party_name}.
          </p>
        )}
      </section>

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
