import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { formatDateTime } from '@/utils/dateUtils';

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

export function SalesOrderDetail({ order }) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-foreground">
          {order.invoice_number ? `Invoice ${order.invoice_number}` : `Sales Order #${order.id}`}
        </h2>
        <Badge variant={Number(order.total_margin_pkr) >= 0 ? 'secondary' : 'destructive'}>
          Margin <CurrencyAmount value={order.total_margin_pkr} className="ml-1" />
        </Badge>
      </div>

      <dl className="grid grid-cols-1 gap-4 rounded-lg border bg-muted/30 p-4 sm:grid-cols-2 lg:grid-cols-5">
        <Detail label="Invoice number">{order.invoice_number || '—'}</Detail>
        <Detail label="Sale ID">#{order.id}</Detail>
        <Detail label="Customer">
          <Link to={`/parties/${order.party_id}`} className="text-primary hover:underline">
            {order.party_name}
          </Link>
        </Detail>
        <Detail label="Sale date">{order.order_date}</Detail>
        <Detail label="Entered on">{formatDateTime(order.created_at)}</Detail>
      </dl>

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
                        Lot #{c.stock_lot_id} (received {c.lot_received_date}): {c.qty_consumed} @{' '}
                        <CurrencyAmount value={c.unit_cost_pkr} />
                      </span>
                    ))}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="-mt-3 text-xs text-muted-foreground">
        Cost is the landed cost of each lot at the time of the sale — it doesn't change if a rate or lot is edited later.
      </p>

      <div className="flex justify-end gap-6 border-t pt-4 text-sm">
        <span>
          Total: <strong><CurrencyAmount value={order.total_pkr} /></strong>
        </span>
        <span>
          Total margin: <strong><CurrencyAmount value={order.total_margin_pkr} /></strong>
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
                    No ledger entry is linked to this sale.
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
            A debit to Accounts Receivable adds to what {order.party_name} owes you.
          </p>
        )}
      </section>
    </div>
  );
}
