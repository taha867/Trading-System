import { Link } from 'react-router-dom';
import { Plus, Loader2, Inbox, Receipt, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { PaginationControls } from '@/components/common/PaginationControls';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { FormSelect, ItemCombobox } from '@/components/custom';
import { InvoiceCombobox } from '@/components/sales/InvoiceCombobox';
import { useSalesOrders } from '@/hooks/salesHooks/salesQueries';
import { useCustomerParties } from '@/hooks/partyHooks/partyQueries';
import { useSearchParamFilters } from '@/hooks/useSearchParamFilters';
import { monthBounds, formatDateTime } from '@/utils/dateUtils';
import { SELECT_ALL_VALUE } from '@/utils/constants';

const DEFAULT_PAGE_SIZE = 20;
const FILTER_KEYS = ['invoice', 'party', 'month', 'item'];

// Display-only ratio of two figures the server already computed.
function marginPct(order) {
  const total = Number(order.total_pkr);
  return total ? `${((Number(order.total_margin_pkr) / total) * 100).toFixed(1)}%` : '—';
}

export function SalesOrderList() {
  const filters = useSearchParamFilters();
  const { customers } = useCustomerParties();

  const party = filters.get('party');
  const month = filters.get('month');
  const item = filters.get('item');
  const invoice = filters.get('invoice');
  const bounds = monthBounds(month);
  const hasActiveFilter = Boolean(invoice || party || month || item);

  // buildQueryString (the service) drops undefined/empty values, so unset filters never reach the URL.
  const { data, isLoading, isError } = useSalesOrders({
    page: filters.page,
    page_size: DEFAULT_PAGE_SIZE,
    invoice_number: invoice || undefined,
    party_id: party || undefined,
    date_from: bounds?.from,
    date_to: bounds?.to,
    item_id: item || undefined,
  });

  const customerOptions = [
    { value: SELECT_ALL_VALUE, label: 'All customers' },
    ...customers.map((c) => ({ value: String(c.id), label: c.name })),
  ];

  const orders = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Receipt className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Sales Orders</CardTitle>
            <CardDescription>Every invoice to a wholesale customer, FIFO-costed against the lots it drew from.</CardDescription>
          </div>
        </div>
        <CardAction>
          <Button size="sm" asChild>
            <Link to="/sales-orders/new">
              <Plus />
              New sales order
            </Link>
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {!isLoading && !isError && data && (
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 rounded-lg border bg-muted/30 px-4 py-3">
            <CurrencyAmount value={data.total_sales_pkr} className="text-2xl font-semibold text-foreground" />
            <span className="text-sm text-muted-foreground">
              in sales{hasActiveFilter ? ' matching the filters below' : ' across every sale'} · {total}{' '}
              {total === 1 ? 'sale' : 'sales'} · margin <CurrencyAmount value={data.total_margin_pkr} />
              {item && ' · whole sales that contain the chosen item'}
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <InvoiceCombobox value={invoice} onChange={(value) => filters.setFilters({ invoice: value })} />
          <FormSelect
            name="customer_filter"
            label="Customer"
            options={customerOptions}
            value={party || SELECT_ALL_VALUE}
            onChange={(value) => filters.setFilters({ party: value === SELECT_ALL_VALUE ? '' : value })}
          />
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sales_month">Month</Label>
            <Input
              id="sales_month"
              type="month"
              value={month}
              onChange={(event) => filters.setFilters({ month: event.target.value })}
            />
          </div>
          <ItemCombobox
            label="Item"
            placeholder="Any item"
            value={item}
            onChange={(value) => filters.setFilters({ item: value })}
          />
        </div>

        {hasActiveFilter && (
          <Button
            variant="outline"
            size="sm"
            className="self-start"
            onClick={() => filters.clearFilters(FILTER_KEYS)}
          >
            <X />
            Clear filters
          </Button>
        )}

        {/* sm and up: table */}
        <div className="hidden overflow-x-auto rounded-lg border sm:block">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>Invoice no.</TableHead>
                <TableHead>ID</TableHead>
                <TableHead>Customer</TableHead>
                <TableHead>Sale date</TableHead>
                <TableHead>Entered on</TableHead>
                <TableHead className="text-right">Total PKR</TableHead>
                <TableHead className="text-right">Margin PKR</TableHead>
                <TableHead className="text-right">Margin %</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={8} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={8} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && orders.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      {hasActiveFilter
                        ? 'No sales match these filters.'
                        : 'No sales orders yet — create the first one above.'}
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {orders.map((order) => (
                <TableRow key={order.id} className="hover:bg-muted/40">
                  <TableCell className="font-medium text-foreground">{order.invoice_number || '—'}</TableCell>
                  <TableCell>
                    <Link to={`/sales-orders/${order.id}`} className="font-medium text-primary hover:underline">
                      #{order.id}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <Link to={`/parties/${order.party_id}`} className="hover:underline">
                      {order.party_name}
                    </Link>
                  </TableCell>
                  <TableCell>{order.order_date}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(order.created_at)}</TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={order.total_pkr} />
                  </TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount
                      value={order.total_margin_pkr}
                      className={Number(order.total_margin_pkr) < 0 ? 'text-destructive' : undefined}
                    />
                  </TableCell>
                  <TableCell className="text-right">{marginPct(order)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* below sm: one card per sale, invoice number / customer / date / total first (CLAUDE.md §3.7) */}
        <div className="flex flex-col gap-2 sm:hidden">
          {isLoading && (
            <div className="flex h-32 flex-col items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
              Loading…
            </div>
          )}
          {isError && <div className="flex h-32 items-center justify-center text-destructive">Failed to load.</div>}
          {!isLoading && !isError && orders.length === 0 && (
            <div className="flex h-32 flex-col items-center justify-center gap-2 text-center text-muted-foreground">
              <Inbox className="size-6 text-muted-foreground/60" />
              {hasActiveFilter ? 'No sales match these filters.' : 'No sales orders yet.'}
            </div>
          )}
          {orders.map((order) => (
            <Link key={order.id} to={`/sales-orders/${order.id}`} className="rounded-lg border p-3">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-medium text-foreground">
                  {order.invoice_number ? `Invoice ${order.invoice_number}` : `Sale #${order.id}`}
                </span>
                <CurrencyAmount value={order.total_pkr} className="font-semibold" />
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {order.party_name} · {order.order_date}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                #{order.id} · margin <CurrencyAmount value={order.total_margin_pkr} /> ({marginPct(order)}) · entered{' '}
                {formatDateTime(order.created_at)}
              </p>
            </Link>
          ))}
        </div>

        <PaginationControls page={filters.page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={filters.setPage} />
      </CardContent>
    </Card>
  );
}
