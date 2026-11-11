import { Fragment, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Loader2, Inbox, Receipt, X, ChevronRight, ChevronDown } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { PaginationControls } from '@/components/common/PaginationControls';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { DateFilter, FormSelect, ItemCombobox } from '@/components/custom';
import { InvoiceCombobox } from '@/components/common/InvoiceCombobox';
import { useInvoices, useInvoiceOptions } from '@/hooks/salesHooks/salesQueries';
import { useCustomerParties } from '@/hooks/partyHooks/partyQueries';
import { useSearchParamFilters } from '@/hooks/useSearchParamFilters';
import { DATE_FILTER_KEYS, useDateFilter } from '@/hooks/useDateFilter';
import { salesInvoiceOptionLabel } from '@/utils/invoiceOptionLabels';
import {
  SELECT_ALL_VALUE,
  SORT_OPTIONS,
  SORT_VALUES,
  DEFAULT_SORT,
  INVOICE_SHOW_OPTIONS,
  INVOICE_SHOW_VALUES,
  SALES_LOG_EXCEPTION_KIND_LABELS,
} from '@/utils/constants';
import { cn } from '@/lib/utils';

const DEFAULT_PAGE_SIZE = 20;
const FILTER_KEYS = ['invoice', 'party', ...DATE_FILTER_KEYS, 'item', 'show'];
const kindLabel = (kind) => SALES_LOG_EXCEPTION_KIND_LABELS[kind] ?? kind;
const rowKey = (invoice) => `${invoice.group_key}|${invoice.party_id ?? ''}`;

// Display-only ratio of two figures the server already computed.
function marginPct(invoice) {
  const booked = Number(invoice.booked_pkr);
  return booked ? `${((Number(invoice.margin_pkr) / booked) * 100).toFixed(1)}%` : '—';
}

// Reference-only (3 Sept 2026): listed, but in no balance, stock or profit figure.
function ShownOnlyBadge() {
  return (
    <Badge variant="outline" className="ml-2 font-normal" title="Shown for reference only — it is not in any balance, stock or profit figure">
      Shown only
    </Badge>
  );
}

// The small badges next to an invoice number: how many lines had no stock found, other entries, cancelled.
function InvoiceBadges({ invoice }) {
  if (invoice.shown_only) return <ShownOnlyBadge />;
  const counts = {};
  for (const entry of invoice.entries) counts[entry.kind] = (counts[entry.kind] ?? 0) + 1;
  const kinds = Object.keys(counts);
  if (!kinds.length) return null;
  return (
    <span className="ml-2 inline-flex flex-wrap gap-1 align-middle">
      {kinds.map((kind) => (
        <Badge key={kind} variant={kind === 'insufficient_stock' ? 'secondary' : 'outline'} className="font-normal">
          {kindLabel(kind)}
          {counts[kind] > 1 ? ` ×${counts[kind]}` : ''}
        </Badge>
      ))}
    </span>
  );
}

// What an invoice is made of: its real sale(s) (full page on a link), then every day-book entry with the same number.
function InvoiceDetails({ invoice }) {
  return (
    <div className="flex flex-col gap-3 text-sm">
      {invoice.orders.length > 0 ? (
        <ul className="flex flex-col gap-1">
          {invoice.orders.map((order) => (
            <li key={order.id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="font-medium text-foreground">Sale</span>
              <Link to={`/sales-orders/${order.id}`} className="font-medium text-primary hover:underline">
                #{order.id}
              </Link>
              <span className="text-muted-foreground">{order.order_date}</span>
              <CurrencyAmount value={order.total_pkr} />
              <span className="text-xs text-muted-foreground">
                margin <CurrencyAmount value={order.margin_pkr} /> · open for lines, stock lots and ledger
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground">
          {invoice.is_cancelled ? 'Cancelled — no items and no money.' : 'No real sale is booked for this invoice yet.'}
        </p>
      )}
      {invoice.entries.length > 0 && (
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
              {invoice.entries.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell>
                    <Badge variant={entry.kind === 'insufficient_stock' ? 'secondary' : 'outline'} className="font-normal">
                      {kindLabel(entry.kind)}
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
        </div>
      )}
    </div>
  );
}

export function InvoiceList() {
  const filters = useSearchParamFilters();
  const { customers } = useCustomerParties();
  const [openKeys, setOpenKeys] = useState(() => new Set());

  const party = filters.getId('party');
  const dates = useDateFilter(filters); // default: the current month; 'All dates' or a From – To range in the URL
  const item = filters.getId('item');
  const invoice = filters.get('invoice');
  const show = filters.getOneOf('show', INVOICE_SHOW_VALUES);
  const sort = filters.getOneOf('sort', SORT_VALUES); // a display choice, not a filter: Clear filters keeps it
  const hasActiveFilter = Boolean(invoice || party || !dates.isDefault || item || show);
  const narrowed = hasActiveFilter || dates.mode !== 'all'; // wording only: a month / range also narrows the list

  const { data, isLoading, isError, isFetching } = useInvoices({
    page: filters.page,
    page_size: DEFAULT_PAGE_SIZE,
    invoice_number: invoice || undefined,
    party_id: party || undefined,
    date_from: dates.dateFrom,
    date_to: dates.dateTo,
    item_id: item || undefined,
    show: show || undefined,
    sort: sort || undefined,
  });

  const customerOptions = [
    { value: SELECT_ALL_VALUE, label: 'All customers' },
    ...customers.map((c) => ({ value: String(c.id), label: c.name })),
  ];
  const dim = cn('transition-opacity', isFetching && !isLoading && 'opacity-60'); // old rows stay visible, dimmed, while the next set loads

  const invoices = data?.items ?? [];
  const total = data?.total ?? 0;
  const toggle = (key) =>
    setOpenKeys((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Receipt className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Invoices</CardTitle>
            <CardDescription>
              Every invoice once. Lines that had no stock found, bulk lines, corrections and cancellations sit under their invoice.
            </CardDescription>
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
          <div className={cn('flex flex-col gap-1 rounded-lg border bg-muted/30 px-4 py-3', dim)}>
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <CurrencyAmount value={data.total_pkr} className="text-2xl font-semibold text-foreground" />
              <span className="text-sm text-muted-foreground">
                owed by customers{narrowed ? ' for the invoices below' : ' across every invoice'} · {total}{' '}
                {total === 1 ? 'invoice' : 'invoices'}
                {item && ' · whole sales that contain the chosen item'}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Booked as sales <CurrencyAmount value={data.booked_pkr} /> (margin <CurrencyAmount value={data.margin_pkr} />) · No stock found{' '}
              <CurrencyAmount value={data.no_stock_pkr} /> · Other entries <CurrencyAmount value={data.other_entries_pkr} />
              {data.cancelled_count > 0 && ` · ${data.cancelled_count} cancelled`}. Only the booked part counts in monthly profit.
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <InvoiceCombobox
            value={invoice}
            // an invoice picked from the list can be from any month: leave the default month behind
            onChange={(value) => filters.setFilters(value && dates.isDefault ? { invoice: value, dates: 'all' } : { invoice: value })}
            useOptions={useInvoiceOptions}
            optionLabel={salesInvoiceOptionLabel}
          />
          <FormSelect
            name="customer_filter"
            label="Customer"
            options={customerOptions}
            value={party || SELECT_ALL_VALUE}
            onChange={(value) => filters.setFilters({ party: value === SELECT_ALL_VALUE ? '' : value })}
          />
          <DateFilter filter={dates} id="invoice_date" className="sm:col-span-2" />
          <ItemCombobox label="Item" placeholder="Any item" value={item} onChange={(value) => filters.setFilters({ item: value })} />
          <FormSelect
            name="show_filter"
            label="Show"
            options={INVOICE_SHOW_OPTIONS}
            value={show || SELECT_ALL_VALUE}
            onChange={(value) => filters.setFilters({ show: value === SELECT_ALL_VALUE ? '' : value })}
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

        {/* sm and up: table, a row expands to show the sale and its entries */}
        <div className={cn('hidden overflow-x-auto rounded-lg border sm:block', dim)}>
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead className="w-8" />
                <TableHead>Invoice no.</TableHead>
                <TableHead>Customer</TableHead>
                <TableHead>Date</TableHead>
                <TableHead className="text-right">Booked PKR</TableHead>
                <TableHead className="text-right">No stock PKR</TableHead>
                <TableHead className="text-right">Total PKR</TableHead>
                <TableHead className="text-right">Margin PKR</TableHead>
                <TableHead className="text-right">Margin %</TableHead>
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
              {!isLoading && !isError && invoices.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      {narrowed ? `No invoices match these filters (${dates.label}).` : 'No invoices yet — create the first sales order above.'}
                      {dates.mode !== 'all' && (
                        <Button variant="outline" size="sm" onClick={dates.setAll}>
                          Show all dates
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {invoices.map((entry) => {
                const key = rowKey(entry);
                const open = openKeys.has(key);
                return (
                  <Fragment key={key}>
                    <TableRow className="cursor-pointer hover:bg-muted/40" onClick={() => toggle(key)}>
                      <TableCell>
                        <button
                          type="button"
                          aria-expanded={open}
                          aria-label={open ? 'Hide invoice details' : 'Show invoice details'}
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
                        {entry.invoice_number || '—'}
                        <InvoiceBadges invoice={entry} />
                      </TableCell>
                      <TableCell>
                        {entry.party_id ? (
                          <Link to={`/parties/${entry.party_id}`} className="hover:underline" onClick={(event) => event.stopPropagation()}>
                            {entry.party_name}
                          </Link>
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell>{entry.invoice_date}</TableCell>
                      <TableCell className="text-right">
                        <CurrencyAmount value={entry.booked_pkr} />
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground">
                        <CurrencyAmount value={entry.no_stock_pkr} />
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        <CurrencyAmount value={entry.total_pkr} />
                      </TableCell>
                      <TableCell className="text-right">
                        <CurrencyAmount value={entry.margin_pkr} className={Number(entry.margin_pkr) < 0 ? 'text-destructive' : undefined} />
                      </TableCell>
                      <TableCell className="text-right">{marginPct(entry)}</TableCell>
                    </TableRow>
                    {open && (
                      <TableRow className="bg-muted/20 hover:bg-muted/20">
                        <TableCell />
                        <TableCell colSpan={8}>
                          <InvoiceDetails invoice={entry} />
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                );
              })}
            </TableBody>
          </Table>
        </div>

        {/* below sm: one card per invoice, invoice number / customer / date / total first (CLAUDE.md 3.7) */}
        <div className={cn('flex flex-col gap-2 sm:hidden', dim)}>
          {isLoading && (
            <div className="flex h-32 flex-col items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
              Loading…
            </div>
          )}
          {isError && <div className="flex h-32 items-center justify-center text-destructive">Failed to load.</div>}
          {!isLoading && !isError && invoices.length === 0 && (
            <div className="flex h-32 flex-col items-center justify-center gap-2 text-center text-muted-foreground">
              <Inbox className="size-6 text-muted-foreground/60" />
              {narrowed ? `No invoices match these filters (${dates.label}).` : 'No invoices yet.'}
              {dates.mode !== 'all' && (
                <Button variant="outline" size="sm" onClick={dates.setAll}>
                  Show all dates
                </Button>
              )}
            </div>
          )}
          {invoices.map((entry) => {
            const key = rowKey(entry);
            const open = openKeys.has(key);
            return (
              <div key={key} className="rounded-lg border p-3">
                <button type="button" className="flex w-full flex-col gap-1 text-left" aria-expanded={open} onClick={() => toggle(key)}>
                  <span className="flex items-baseline justify-between gap-3">
                    <span className="font-medium text-foreground">
                      {entry.invoice_number ? `Invoice ${entry.invoice_number}` : 'No invoice number'}
                    </span>
                    <CurrencyAmount value={entry.total_pkr} className="font-semibold" />
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {entry.party_name ?? '—'} · {entry.invoice_date}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    booked <CurrencyAmount value={entry.booked_pkr} /> · no stock <CurrencyAmount value={entry.no_stock_pkr} /> · margin{' '}
                    <CurrencyAmount value={entry.margin_pkr} /> ({marginPct(entry)})
                  </span>
                  <InvoiceBadges invoice={entry} />
                  <span className="text-xs text-primary">{open ? 'Hide details' : 'Show details'}</span>
                </button>
                {open && (
                  <div className="mt-3 border-t pt-3">
                    <InvoiceDetails invoice={entry} />
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
