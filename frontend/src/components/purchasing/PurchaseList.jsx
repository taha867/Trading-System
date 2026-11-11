import { Fragment, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Loader2, Inbox, ShoppingCart, X, ChevronRight, ChevronDown } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { PaginationControls } from '@/components/common/PaginationControls';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { InvoiceCombobox } from '@/components/common/InvoiceCombobox';
import { FormSelect, ItemCombobox } from '@/components/custom';
import { usePurchaseGroups, usePurchaseInvoiceOptions } from '@/hooks/purchasingHooks/purchasingQueries';
import { useVendorParties } from '@/hooks/partyHooks/partyQueries';
import { useSearchParamFilters } from '@/hooks/useSearchParamFilters';
import { monthBounds } from '@/utils/dateUtils';
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
  PURCHASE_LOG_EXCEPTION_KIND_LABELS,
  PURCHASE_SHOW_OPTIONS,
  PURCHASE_SHOW_VALUES,
} from '@/utils/constants';
import { cn } from '@/lib/utils';

const DEFAULT_PAGE_SIZE = 20;
const FILTER_KEYS = ['invoice', 'vendor', 'source', 'status', 'month', 'item', 'show'];
const rowKey = (row) => `${row.group_key}|${row.party_id}`;
const categoryLabel = (row) => {
  if (row.categories.length === 0) return '—';
  return row.categories.length === 1 ? row.categories[0] : `${row.categories[0]} +${row.categories.length - 1} more`;
};

// What a row is made of: its purchase order(s) (full page on a link), then every payable-only entry with the same number.
function PurchaseDetails({ row }) {
  return (
    <div className="flex flex-col gap-3 text-sm">
      {row.orders.length > 0 && (
        <ul className="flex flex-col gap-1">
          {row.orders.map((order) => (
            <li key={order.id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="font-medium text-foreground">Order</span>
              <Link to={`/purchase-orders/${order.id}`} className="font-medium text-primary hover:underline">
                #{order.id}
              </Link>
              <span className="text-muted-foreground">{order.order_date}</span>
              <Badge variant="secondary" className="font-normal">
                {PURCHASE_ORDER_SOURCE_BADGE_LABEL[order.source] ?? order.source}
              </Badge>
              <Badge variant="outline" className="font-normal">
                {PURCHASE_ORDER_STATUS_LABEL[order.status] ?? order.status}
              </Badge>
              <CurrencyAmount value={order.total_pkr} />
              {Number(order.total_rmb) > 0 && <CurrencyAmount value={order.total_rmb} currency="RMB" />}
              <span className="text-xs text-muted-foreground">{order.categories.join(', ')}</span>
            </li>
          ))}
        </ul>
      )}
      {row.entries.length > 0 && (
        <div className="overflow-x-auto rounded-md border bg-background">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/40">
                <TableHead>Entry</TableHead>
                <TableHead>Category</TableHead>
                <TableHead className="text-right">Qty</TableHead>
                <TableHead className="text-right">Rate</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead>Note</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {row.entries.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell>
                    <Badge variant="outline" className="font-normal">
                      {PURCHASE_LOG_EXCEPTION_KIND_LABELS[entry.kind] ?? entry.kind}
                    </Badge>
                  </TableCell>
                  <TableCell>{entry.category_name ?? '—'}</TableCell>
                  <TableCell className="text-right">{entry.qty ?? '—'}</TableCell>
                  <TableCell className="text-right">{entry.rate_pkr ? <CurrencyAmount value={entry.rate_pkr} /> : '—'}</TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={entry.amount_pkr} />
                  </TableCell>
                  <TableCell className="max-w-72 truncate text-xs text-muted-foreground" title={entry.note ?? ''}>
                    {entry.note ?? ''}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p className="border-t px-3 py-2 text-xs text-muted-foreground">
            Payable-only: money owed to the supplier for goods with no phone model, so nothing was added to stock.
          </p>
        </div>
      )}
    </div>
  );
}

function RowBadges({ row }) {
  return (
    <span className="ml-2 inline-flex flex-wrap gap-1 align-middle">
      {row.orders.length > 1 && (
        <Badge variant="outline" className="font-normal">
          {row.orders.length} orders
        </Badge>
      )}
      {row.entries.length > 0 && (
        <Badge variant="secondary" className="font-normal">
          Payable-only{row.entries.length > 1 ? ` ×${row.entries.length}` : ''}
        </Badge>
      )}
    </span>
  );
}

export function PurchaseList() {
  const filters = useSearchParamFilters();
  const { vendors } = useVendorParties();
  const [openKeys, setOpenKeys] = useState(() => new Set());

  const invoice = filters.get('invoice');
  const sort = filters.getOneOf('sort', SORT_VALUES); // a display choice, not a filter: Clear filters keeps it
  const vendor = filters.getId('vendor');
  const source = filters.getOneOf('source', PURCHASE_ORDER_SOURCE_OPTIONS.map((o) => o.value));
  const status = filters.getOneOf('status', PURCHASE_ORDER_STATUS_OPTIONS.map((o) => o.value));
  const month = filters.getMonth();
  const item = filters.getId('item');
  const show = filters.getOneOf('show', PURCHASE_SHOW_VALUES);
  const bounds = monthBounds(month);
  const hasActiveFilter = Boolean(invoice || vendor || source || status || month || item || show);

  const { data, isLoading, isError, isFetching } = usePurchaseGroups({
    page: filters.page,
    page_size: DEFAULT_PAGE_SIZE,
    invoice_number: invoice || undefined,
    party_id: vendor || undefined,
    source: source || undefined,
    status: status || undefined,
    date_from: bounds?.from,
    date_to: bounds?.to,
    item_id: item || undefined,
    show: show || undefined,
    sort: sort || undefined,
  });

  const vendorOptions = [{ value: SELECT_ALL_VALUE, label: 'All vendors' }, ...vendors.map((v) => ({ value: String(v.id), label: v.name }))];
  const sourceOptions = [{ value: SELECT_ALL_VALUE, label: 'All sources' }, ...PURCHASE_ORDER_SOURCE_OPTIONS];
  const statusOptions = [{ value: SELECT_ALL_VALUE, label: 'All statuses' }, ...PURCHASE_ORDER_STATUS_OPTIONS];
  const fromAll = (value) => (value === SELECT_ALL_VALUE ? '' : value);
  const dim = cn('transition-opacity', isFetching && !isLoading && 'opacity-60'); // old rows stay visible, dimmed, while the next set loads

  const rows = data?.items ?? [];
  const total = data?.total ?? 0;
  const toggle = (key) =>
    setOpenKeys((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  const sourceOf = (row) => (row.orders[0] ? (PURCHASE_ORDER_SOURCE_BADGE_LABEL[row.orders[0].source] ?? row.orders[0].source) : 'Local');

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <ShoppingCart className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Purchases</CardTitle>
            <CardDescription>
              Every supplier invoice once — purchase orders with items, and payable-only entries (money owed, no phone model) under the same invoice.
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
          <div className={cn('flex flex-col gap-1 rounded-lg border bg-muted/30 px-4 py-3', dim)}>
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <CurrencyAmount value={data.total_pkr} className="text-2xl font-semibold text-foreground" />
              <span className="text-sm text-muted-foreground">
                payable to suppliers{hasActiveFilter ? ' for the rows below' : ' across every purchase'} · {total} {total === 1 ? 'row' : 'rows'}
                {Number(data.total_rmb) > 0 && (
                  <>
                    {' '}
                    · <CurrencyAmount value={data.total_rmb} currency="RMB" /> on China orders
                  </>
                )}
                {item && ' · whole orders that contain the chosen item'}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Orders with items <CurrencyAmount value={data.orders_pkr} /> · Payable-only entries <CurrencyAmount value={data.entries_pkr} />
            </p>
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
            <Input id="purchase_month" type="month" value={month} onChange={(event) => filters.setFilters({ month: event.target.value })} />
          </div>
          <ItemCombobox label="Item" placeholder="Any item" value={item} onChange={(value) => filters.setFilters({ item: value })} />
          <FormSelect
            name="show_filter"
            label="Show"
            options={PURCHASE_SHOW_OPTIONS}
            value={show || SELECT_ALL_VALUE}
            onChange={(value) => filters.setFilters({ show: fromAll(value) })}
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

        {/* sm and up: table, a row expands to show the order(s) and the payable-only entries */}
        <div className={cn('hidden overflow-x-auto rounded-lg border sm:block', dim)}>
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead className="w-8" />
                <TableHead>Invoice no.</TableHead>
                <TableHead>Vendor</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Source</TableHead>
                <TableHead className="text-right">Orders PKR</TableHead>
                <TableHead className="text-right">Payable-only PKR</TableHead>
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
              {!isLoading && !isError && rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      {hasActiveFilter ? 'No purchases match these filters.' : 'No purchases yet — create the first order above.'}
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {rows.map((row) => {
                const key = rowKey(row);
                const open = openKeys.has(key);
                return (
                  <Fragment key={key}>
                    <TableRow className="cursor-pointer hover:bg-muted/40" onClick={() => toggle(key)}>
                      <TableCell>
                        <button
                          type="button"
                          aria-expanded={open}
                          aria-label={open ? 'Hide details' : 'Show details'}
                          className="text-muted-foreground"
                          onClick={(event) => {
                            event.stopPropagation();
                            toggle(key);
                          }}
                        >
                          {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                        </button>
                      </TableCell>
                      <TableCell className="font-medium text-foreground">
                        {row.invoice_number || '—'}
                        <RowBadges row={row} />
                      </TableCell>
                      <TableCell>
                        <Link to={`/parties/${row.party_id}`} className="hover:underline" onClick={(event) => event.stopPropagation()}>
                          {row.party_name}
                        </Link>
                      </TableCell>
                      <TableCell>{categoryLabel(row)}</TableCell>
                      <TableCell>{row.invoice_date}</TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="font-normal">
                          {sourceOf(row)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <CurrencyAmount value={row.orders_pkr} />
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground">
                        <CurrencyAmount value={row.entries_pkr} />
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        <CurrencyAmount value={row.total_pkr} />
                      </TableCell>
                    </TableRow>
                    {open && (
                      <TableRow className="bg-muted/20 hover:bg-muted/20">
                        <TableCell />
                        <TableCell colSpan={8}>
                          <PurchaseDetails row={row} />
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                );
              })}
            </TableBody>
          </Table>
        </div>

        {/* below sm: one card per row, invoice / vendor / date / total first (CLAUDE.md 3.7) */}
        <div className={cn('flex flex-col gap-2 sm:hidden', dim)}>
          {isLoading && (
            <div className="flex h-32 flex-col items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
              Loading…
            </div>
          )}
          {isError && <div className="flex h-32 items-center justify-center text-destructive">Failed to load.</div>}
          {!isLoading && !isError && rows.length === 0 && (
            <div className="flex h-32 flex-col items-center justify-center gap-2 text-center text-muted-foreground">
              <Inbox className="size-6 text-muted-foreground/60" />
              {hasActiveFilter ? 'No purchases match these filters.' : 'No purchases yet.'}
            </div>
          )}
          {rows.map((row) => {
            const key = rowKey(row);
            const open = openKeys.has(key);
            return (
              <div key={key} className="rounded-lg border p-3">
                <button type="button" className="flex w-full flex-col gap-1 text-left" aria-expanded={open} onClick={() => toggle(key)}>
                  <span className="flex items-baseline justify-between gap-3">
                    <span className="font-medium text-foreground">{row.invoice_number ? `Invoice ${row.invoice_number}` : 'No invoice number'}</span>
                    <CurrencyAmount value={row.total_pkr} className="font-semibold" />
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {row.party_name} · {row.invoice_date}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {categoryLabel(row)} · orders <CurrencyAmount value={row.orders_pkr} /> · payable-only <CurrencyAmount value={row.entries_pkr} />
                  </span>
                  <RowBadges row={row} />
                  <span className="text-xs text-primary">{open ? 'Hide details' : 'Show details'}</span>
                </button>
                {open && (
                  <div className="mt-3 border-t pt-3">
                    <PurchaseDetails row={row} />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <PaginationControls page={filters.page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={filters.setPage} />
      </CardContent>
    </Card>
  );
}
