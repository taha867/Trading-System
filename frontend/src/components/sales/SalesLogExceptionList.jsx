import { Link } from 'react-router-dom';
import { Loader2, Inbox, FileQuestion, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { PaginationControls } from '@/components/common/PaginationControls';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { FormSelect } from '@/components/custom';
import { InvoiceCombobox } from '@/components/common/InvoiceCombobox';
import {
  useSalesLogExceptions,
  useSalesLogExceptionInvoiceOptions,
  useSalesLogExceptionCategories,
} from '@/hooks/salesHooks/salesQueries';
import { useCustomerParties } from '@/hooks/partyHooks/partyQueries';
import { useSearchParamFilters } from '@/hooks/useSearchParamFilters';
import { monthBounds, formatDateTime } from '@/utils/dateUtils';
import { cn } from '@/lib/utils';
import { logExceptionInvoiceOptionLabel } from '@/utils/invoiceOptionLabels';
import {
  SELECT_ALL_VALUE,
  SORT_OPTIONS,
  SORT_VALUES,
  DEFAULT_SORT,
  SALES_LOG_EXCEPTION_KIND_LABELS,
  SALES_LOG_EXCEPTION_KIND_OPTIONS,
} from '@/utils/constants';

const DEFAULT_PAGE_SIZE = 20;
const FILTER_KEYS = ['search', 'invoice', 'kind', 'party', 'category', 'month'];
const COLUMN_COUNT = 11;

const kindLabel = (kind) => SALES_LOG_EXCEPTION_KIND_LABELS[kind] ?? kind;

export function SalesLogExceptionList() {
  const filters = useSearchParamFilters();
  const { customers } = useCustomerParties();
  const { data: categories } = useSalesLogExceptionCategories();

  const kind = filters.getOneOf('kind', SALES_LOG_EXCEPTION_KIND_OPTIONS.map((o) => o.value));
  const sort = filters.getOneOf('sort', SORT_VALUES);  // a display choice, not a filter: not in FILTER_KEYS
  const party = filters.getId('party');
  const month = filters.getMonth();
  const search = filters.get('search');
  const invoice = filters.get('invoice');
  const category = filters.get('category');
  const bounds = monthBounds(month);
  const hasActiveFilter = Boolean(search || invoice || kind || party || category || month);

  const { data, isLoading, isError, isFetching } = useSalesLogExceptions({
    page: filters.page,
    page_size: DEFAULT_PAGE_SIZE,
    search: search || undefined,
    invoice_number: invoice || undefined,
    category: category || undefined,
    kind: kind || undefined,
    party_id: party || undefined,
    date_from: bounds?.from,
    date_to: bounds?.to,
    sort: sort || undefined,
  });

  const kindOptions = [{ value: SELECT_ALL_VALUE, label: 'All kinds' }, ...SALES_LOG_EXCEPTION_KIND_OPTIONS];
  const customerOptions = [
    { value: SELECT_ALL_VALUE, label: 'All customers' },
    ...customers.map((c) => ({ value: String(c.id), label: c.name })),
  ];

  const categoryOptions = [
    { value: SELECT_ALL_VALUE, label: 'All categories' },
    ...(categories ?? []).map((name) => ({ value: name, label: name })),
  ];

  const dim = cn('transition-opacity', isFetching && !isLoading && 'opacity-60');  // old rows stay visible, dimmed, while the next set loads

  const entries = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <FileQuestion className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Other sales entries</CardTitle>
            <CardDescription>
              Sales that couldn't become a normal invoice line — items that had no stock recorded at the time, bulk
              batches, price corrections, discounts and cancelled invoices. They change what a customer owes, but
              not your stock, and they are not part of monthly profit.
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {!isLoading && !isError && data && (
          <div className={cn('flex flex-col gap-2 rounded-lg border bg-muted/30 px-4 py-3', dim)}>
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <CurrencyAmount value={data.total_amount_pkr} className="text-2xl font-semibold text-foreground" />
              <span className="text-sm text-muted-foreground">
                {hasActiveFilter ? 'matching the filters below' : 'across every entry'} · {total}{' '}
                {total === 1 ? 'entry' : 'entries'}
              </span>
            </div>
            {data.totals_by_kind.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {data.totals_by_kind.map((row) => (
                  <Badge key={row.kind} variant="secondary">
                    {kindLabel(row.kind)}: {row.count} · <CurrencyAmount value={row.total_pkr} className="ml-1" />
                  </Badge>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <InvoiceCombobox
            value={invoice}
            onChange={(value) => filters.setFilters({ invoice: value })}
            useOptions={useSalesLogExceptionInvoiceOptions}
            optionLabel={logExceptionInvoiceOptionLabel}
          />
          <FormSelect
            name="exceptions_customer_filter"
            label="Customer"
            options={customerOptions}
            value={party || SELECT_ALL_VALUE}
            onChange={(value) => filters.setFilters({ party: value === SELECT_ALL_VALUE ? '' : value })}
          />
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="exceptions_month">Month</Label>
            <Input
              id="exceptions_month"
              type="month"
              value={month}
              onChange={(event) => filters.setFilters({ month: event.target.value })}
            />
          </div>
          <FormSelect
            name="exceptions_category_filter"
            label="Category"
            options={categoryOptions}
            value={category || SELECT_ALL_VALUE}
            onChange={(value) => filters.setFilters({ category: value === SELECT_ALL_VALUE ? '' : value })}
          />
          <FormSelect
            name="kind_filter"
            label="Kind"
            options={kindOptions}
            value={kind || SELECT_ALL_VALUE}
            onChange={(value) => filters.setFilters({ kind: value === SELECT_ALL_VALUE ? '' : value })}
          />
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="exceptions_search">Search note</Label>
            <Input
              id="exceptions_search"
              type="search"
              placeholder="e.g. cancelled"
              value={filters.searchInput}
              onChange={(event) => filters.handleSearchChange(event.target.value)}
            />
          </div>
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
                <TableHead>Date</TableHead>
                <TableHead>Kind</TableHead>
                <TableHead>Invoice no.</TableHead>
                <TableHead>Customer</TableHead>
                <TableHead>Category</TableHead>
                <TableHead className="text-right">Qty</TableHead>
                <TableHead className="text-right">Rate</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead>Note</TableHead>
                <TableHead>Ledger</TableHead>
                <TableHead>Entered on</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={COLUMN_COUNT} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={COLUMN_COUNT} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && entries.length === 0 && (
                <TableRow>
                  <TableCell colSpan={COLUMN_COUNT} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      {hasActiveFilter ? 'No entries match these filters.' : 'No other sales entries.'}
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {entries.map((entry) => (
                <TableRow key={entry.id} className="hover:bg-muted/40">
                  <TableCell>{entry.entry_date}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{kindLabel(entry.kind)}</Badge>
                  </TableCell>
                  <TableCell>{entry.invoice_number || '—'}</TableCell>
                  <TableCell>
                    {entry.party_id ? (
                      <Link to={`/parties/${entry.party_id}`} className="hover:underline">
                        {entry.party_name}
                      </Link>
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell>{entry.category_name || '—'}</TableCell>
                  <TableCell className="text-right">{entry.qty ?? '—'}</TableCell>
                  <TableCell className="text-right">
                    {entry.rate_pkr != null ? <CurrencyAmount value={entry.rate_pkr} /> : '—'}
                  </TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={entry.amount_pkr} />
                  </TableCell>
                  <TableCell className="max-w-48 truncate" title={entry.note ?? ''}>
                    {entry.note || '—'}
                  </TableCell>
                  <TableCell>
                    <Badge variant={entry.ledger_posted ? 'secondary' : 'outline'}>
                      {entry.ledger_posted ? 'Posted' : 'Not posted'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(entry.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* below sm: one card per entry, amount / customer / date first (CLAUDE.md §3.7) */}
        <div className={cn('flex flex-col gap-2 sm:hidden', dim)}>
          {isLoading && (
            <div className="flex h-32 flex-col items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
              Loading…
            </div>
          )}
          {isError && <div className="flex h-32 items-center justify-center text-destructive">Failed to load.</div>}
          {!isLoading && !isError && entries.length === 0 && (
            <div className="flex h-32 flex-col items-center justify-center gap-2 text-center text-muted-foreground">
              <Inbox className="size-6 text-muted-foreground/60" />
              {hasActiveFilter ? 'No entries match these filters.' : 'No other sales entries.'}
            </div>
          )}
          {entries.map((entry) => (
            <div key={entry.id} className="rounded-lg border p-3">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-medium text-foreground">
                  {entry.invoice_number ? `Invoice ${entry.invoice_number}` : kindLabel(entry.kind)}
                </span>
                <CurrencyAmount value={entry.amount_pkr} className="font-semibold" />
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {entry.party_name ?? 'No customer recorded'} · {entry.entry_date}
              </p>
              <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                <Badge variant="outline">{kindLabel(entry.kind)}</Badge>
                {entry.category_name && (
                  <span>
                    {entry.category_name}
                    {entry.qty != null ? ` · ${entry.qty} pcs` : ''}
                  </span>
                )}
                <Badge variant={entry.ledger_posted ? 'secondary' : 'outline'}>
                  {entry.ledger_posted ? 'Posted' : 'Not posted'}
                </Badge>
              </p>
              {entry.note && <p className="mt-1 text-xs text-muted-foreground">{entry.note}</p>}
            </div>
          ))}
        </div>

        <PaginationControls page={filters.page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={filters.setPage} />
      </CardContent>
    </Card>
  );
}
