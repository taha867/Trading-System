import { Link, useNavigate } from 'react-router-dom';
import { Plus, Loader2, Inbox, ShoppingCart, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { PaginationControls } from '@/components/common/PaginationControls';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { InvoiceCombobox } from '@/components/common/InvoiceCombobox';
import { FormSelect, ItemCombobox } from '@/components/custom';
import { usePurchaseOrders, usePurchaseInvoiceOptions } from '@/hooks/purchasingHooks/purchasingQueries';
import { useVendorParties } from '@/hooks/partyHooks/partyQueries';
import { useSearchParamFilters } from '@/hooks/useSearchParamFilters';
import { monthBounds, formatDateTime } from '@/utils/dateUtils';
import { cn } from '@/lib/utils';
import { purchaseInvoiceOptionLabel } from '@/utils/invoiceOptionLabels';
import {
  SELECT_ALL_VALUE,
  SORT_OPTIONS,
  SORT_VALUES,
  DEFAULT_SORT,
  PURCHASE_ORDER_SOURCE_OPTIONS,
  PURCHASE_ORDER_SOURCE_BADGE_LABEL,
  PURCHASE_ORDER_STATUS_OPTIONS,
  PURCHASE_ORDER_STATUS_LABEL,
} from '@/utils/constants';

const DEFAULT_PAGE_SIZE = 20;
const FILTER_KEYS = ['invoice', 'vendor', 'source', 'status', 'month', 'item'];

// A PO's own lines already carry their category_name (embedded — see
// purchasing/schemas.py's PurchaseOrderLineRead), so no per-row lookup fetch
// is needed just to answer "what did this order buy" (usually one category,
// per this app's own "one PurchaseOrder per category" convention, but shown
// honestly if a PO ever mixes a few).
function categoryLabel(order) {
  const names = [...new Set((order.lines ?? []).map((line) => line.category_name))];
  if (names.length === 0) return '—';
  if (names.length === 1) return names[0];
  return `${names[0]} +${names.length - 1} more`;
}

const sourceLabel = (order) => PURCHASE_ORDER_SOURCE_BADGE_LABEL[order.source] ?? order.source;
const statusLabel = (order) => PURCHASE_ORDER_STATUS_LABEL[order.status] ?? order.status;

export function PurchaseOrderList() {
  const filters = useSearchParamFilters();
  const navigate = useNavigate();
  const { vendors } = useVendorParties();

  const invoice = filters.get('invoice');
  const sort = filters.getOneOf('sort', SORT_VALUES);  // a display choice, not a filter: not in FILTER_KEYS, so Clear filters keeps it
  const vendor = filters.getId('vendor');
  const source = filters.getOneOf('source', PURCHASE_ORDER_SOURCE_OPTIONS.map((o) => o.value));
  const status = filters.getOneOf('status', PURCHASE_ORDER_STATUS_OPTIONS.map((o) => o.value));
  const month = filters.getMonth();
  const item = filters.getId('item');
  const bounds = monthBounds(month);
  const hasActiveFilter = Boolean(invoice || vendor || source || status || month || item);

  // buildQueryString (the service) drops undefined/empty values, so unset filters never reach the URL.
  const { data, isLoading, isError, isFetching } = usePurchaseOrders(
    {
      page: filters.page,
      page_size: DEFAULT_PAGE_SIZE,
      invoice_number: invoice || undefined,
      party_id: vendor || undefined,
      source: source || undefined,
      status: status || undefined,
      date_from: bounds?.from,
      date_to: bounds?.to,
      item_id: item || undefined,
      sort: sort || undefined,
    },
    { keepPrevious: true },
  );

  const vendorOptions = [
    { value: SELECT_ALL_VALUE, label: 'All vendors' },
    ...vendors.map((v) => ({ value: String(v.id), label: v.name })),
  ];
  const sourceOptions = [{ value: SELECT_ALL_VALUE, label: 'All sources' }, ...PURCHASE_ORDER_SOURCE_OPTIONS];
  const statusOptions = [{ value: SELECT_ALL_VALUE, label: 'All statuses' }, ...PURCHASE_ORDER_STATUS_OPTIONS];
  const fromAll = (value) => (value === SELECT_ALL_VALUE ? '' : value);

  const dim = cn('transition-opacity', isFetching && !isLoading && 'opacity-60');  // old rows stay visible, dimmed, while the next set loads

  const orders = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <ShoppingCart className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Purchase Orders</CardTitle>
            <CardDescription>
              Every order placed with a vendor — China orders in RMB with their snapshotted PKR cost, local and Mohsin
              orders in PKR.
            </CardDescription>
          </div>
        </div>
        <CardAction>
          <Button size="sm" asChild>
            <Link to="/purchase-orders/new">
              <Plus />
              New purchase order
            </Link>
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {!isLoading && !isError && data && (
          <div className={cn('flex flex-wrap items-baseline gap-x-2 gap-y-1 rounded-lg border bg-muted/30 px-4 py-3', dim)}>
            <CurrencyAmount value={data.total_amount_pkr} className="text-2xl font-semibold text-foreground" />
            <span className="text-sm text-muted-foreground">
              purchased{hasActiveFilter ? ' matching the filters below' : ' across every order'} · {total}{' '}
              {total === 1 ? 'order' : 'orders'}
              {Number(data.total_rmb) > 0 && (
                <>
                  {' '}
                  · <CurrencyAmount value={data.total_rmb} currency="RMB" /> on China orders
                </>
              )}
              {item && ' · whole orders that contain the chosen item'}
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <InvoiceCombobox
            value={invoice}
            onChange={(value) => filters.setFilters({ invoice: value })}
            useOptions={usePurchaseInvoiceOptions}
            optionLabel={purchaseInvoiceOptionLabel}
          />
          <FormSelect
            name="vendor_filter"
            label="Vendor"
            options={vendorOptions}
            value={vendor || SELECT_ALL_VALUE}
            onChange={(value) => filters.setFilters({ vendor: fromAll(value) })}
          />
          <FormSelect
            name="source_filter"
            label="Source"
            options={sourceOptions}
            value={source || SELECT_ALL_VALUE}
            onChange={(value) => filters.setFilters({ source: fromAll(value) })}
          />
          <FormSelect
            name="status_filter"
            label="Status"
            options={statusOptions}
            value={status || SELECT_ALL_VALUE}
            onChange={(value) => filters.setFilters({ status: fromAll(value) })}
          />
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="purchase_month">Month</Label>
            <Input
              id="purchase_month"
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
          <FormSelect
            name="sort_filter"
            label="Sort by date"
            options={SORT_OPTIONS}
            value={sort || DEFAULT_SORT}
            onChange={(value) => filters.setFilters({ sort: value === DEFAULT_SORT ? '' : value })}
          />
        </div>

        {hasActiveFilter && (
          <Button variant="outline" size="sm" className="self-start" onClick={() => filters.clearFilters(FILTER_KEYS)}>
            <X />
            Clear filters
          </Button>
        )}

        {/* sm and up: table */}
        <div className={cn('hidden overflow-x-auto rounded-lg border sm:block', dim)}>
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>Invoice no.</TableHead>
                <TableHead>ID</TableHead>
                <TableHead>Vendor</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Order date</TableHead>
                <TableHead>Entered on</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Source</TableHead>
                <TableHead className="text-right">Total PKR</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={9} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={9} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && orders.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      {hasActiveFilter
                        ? 'No purchase orders match these filters.'
                        : 'No purchase orders yet — create the first one above.'}
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {orders.map((order) => (
                <TableRow
                  key={order.id}
                  className="cursor-pointer hover:bg-muted/40"
                  onClick={() => navigate(`/purchase-orders/${order.id}`)}
                >
                  <TableCell className="font-medium text-foreground">{order.invoice_number || '—'}</TableCell>
                  <TableCell>
                    {/* A real link, so the order opens by keyboard, middle-click and "open in new tab";
                        stopPropagation keeps the row's own click from navigating a second time. */}
                    <Link
                      to={`/purchase-orders/${order.id}`}
                      className="font-medium text-primary hover:underline"
                      onClick={(event) => event.stopPropagation()}
                    >
                      #{order.id}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {/* stopPropagation: the row itself opens the order; the vendor name opens the vendor. */}
                    <Link
                      to={`/parties/${order.party_id}`}
                      className="hover:underline"
                      onClick={(event) => event.stopPropagation()}
                    >
                      {order.party_name}
                    </Link>
                  </TableCell>
                  <TableCell>{categoryLabel(order)}</TableCell>
                  <TableCell>{order.order_date}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(order.created_at)}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{statusLabel(order)}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{sourceLabel(order)}</Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={order.total_pkr} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* below sm: one card per order, invoice number / vendor / date / total first (CLAUDE.md §3.7) */}
        <div className={cn('flex flex-col gap-2 sm:hidden', dim)}>
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
              {hasActiveFilter ? 'No purchase orders match these filters.' : 'No purchase orders yet.'}
            </div>
          )}
          {orders.map((order) => (
            <Link key={order.id} to={`/purchase-orders/${order.id}`} className="rounded-lg border p-3">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-medium text-foreground">
                  {order.invoice_number ? `Invoice ${order.invoice_number}` : `Order #${order.id}`}
                </span>
                <CurrencyAmount value={order.total_pkr} className="font-semibold" />
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {order.party_name} · {order.order_date}
              </p>
              <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                #{order.id} · {categoryLabel(order)}
                <Badge variant="secondary">{statusLabel(order)}</Badge>
                <Badge variant="secondary">{sourceLabel(order)}</Badge>
                entered {formatDateTime(order.created_at)}
              </p>
            </Link>
          ))}
        </div>

        <PaginationControls page={filters.page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={filters.setPage} />
      </CardContent>
    </Card>
  );
}
