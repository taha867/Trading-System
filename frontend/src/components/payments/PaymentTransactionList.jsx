import { Link } from 'react-router-dom';
import { Loader2, Inbox, History, X } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { PaginationControls } from '@/components/common/PaginationControls';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { DateFilter, FormSelect } from '@/components/custom';
import { usePaymentTransactions, usePaymentAccounts } from '@/hooks/paymentsHooks/paymentsQueries';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { DATE_FILTER_KEYS, useDateFilter } from '@/hooks/useDateFilter';
import { useSearchParamFilters } from '@/hooks/useSearchParamFilters';
import {
  DEFAULT_SORT,
  PAYMENT_DIRECTION,
  PAYMENT_KIND_LABELS,
  PAYMENT_KIND_OPTIONS,
  PAYMENT_KIND_VALUES,
  PAYMENT_REFERENCE_TYPE,
  PAYMENT_REFERENCE_TYPE_LABEL,
  SELECT_ALL_VALUE,
  SORT_OPTIONS,
  SORT_VALUES,
} from '@/utils/constants';
import { LOOKUP_PAGE } from '@/utils/queryParams';
import { cn } from '@/lib/utils';

const DEFAULT_PAGE_SIZE = 20;
// Sort is a display choice, not a filter: Clear filters keeps it.
const FILTER_KEYS = ['type', 'account', 'party', 'search', ...DATE_FILTER_KEYS];

const isIn = (txn) => txn.direction === PAYMENT_DIRECTION.IN;

function ShownOnlyBadge() {
  return (
    <Badge variant="outline" className="font-normal" title="Shown for reference only — not in any balance or total">
      Shown only
    </Badge>
  );
}

function KindBadge({ kind }) {
  return <Badge variant={kind === 'supplier_payment' ? 'outline' : 'secondary'}>{PAYMENT_KIND_LABELS[kind] ?? kind}</Badge>;
}

// Money in is green with a +, money out has a −.
function SignedAmount({ txn, className }) {
  return (
    <span className={cn(isIn(txn) ? 'text-emerald-600 dark:text-emerald-400' : 'text-foreground', className)}>
      {isIn(txn) ? '+' : '−'}
      <CurrencyAmount value={txn.amount} />
    </span>
  );
}

function PartyLink({ txn }) {
  if (!txn.party_id) return <span className="text-muted-foreground">—</span>;
  return (
    <Link to={`/parties/${txn.party_id}`} className="hover:underline">
      {txn.party_name ?? `Party #${txn.party_id}`}
    </Link>
  );
}

// What the payment was for: an expense (its category and description), a linked order (a link), or just its note.
function Detail({ txn }) {
  if (txn.kind === 'expense') {
    const text = [txn.expense_category, txn.expense_description || txn.note].filter(Boolean).join(' · ');
    return <span title={text}>{text || `Expense #${txn.reference_id}`}</span>;
  }
  if (txn.reference_type === PAYMENT_REFERENCE_TYPE.SALES_ORDER || txn.reference_type === PAYMENT_REFERENCE_TYPE.PURCHASE_ORDER) {
    const path = txn.reference_type === PAYMENT_REFERENCE_TYPE.SALES_ORDER ? 'sales-orders' : 'purchase-orders';
    return (
      <span>
        <Link to={`/${path}/${txn.reference_id}`} className="text-primary hover:underline">
          {PAYMENT_REFERENCE_TYPE_LABEL[txn.reference_type]} #{txn.reference_id}
        </Link>
        {txn.note && <span className="text-muted-foreground"> · {txn.note}</span>}
      </span>
    );
  }
  return <span title={txn.note ?? ''}>{txn.note || '—'}</span>;
}

export function PaymentTransactionList() {
  const filters = useSearchParamFilters();
  const dates = useDateFilter(filters); // default: the current month; 'All dates' or a From – To range in the URL

  const kind = filters.getOneOf('type', PAYMENT_KIND_VALUES);
  const account = filters.getId('account');
  const party = filters.getId('party');
  const search = filters.get('search');
  const sort = filters.getOneOf('sort', SORT_VALUES);
  const hasActiveFilter = Boolean(kind || account || party || search || !dates.isDefault);
  const narrowed = hasActiveFilter || dates.mode !== 'all'; // wording only: a month / range also narrows the list

  const { data, isLoading, isError, isFetching } = usePaymentTransactions({
    page: filters.page,
    page_size: DEFAULT_PAGE_SIZE,
    kind: kind || undefined,
    payment_account_id: account || undefined,
    party_id: party || undefined,
    search: search || undefined,
    date_from: dates.dateFrom,
    date_to: dates.dateTo,
    sort: sort || undefined,
  });
  const { data: accountsData } = usePaymentAccounts(LOOKUP_PAGE);
  const { data: partiesData } = useParties(LOOKUP_PAGE);

  const accountOptions = [
    { value: SELECT_ALL_VALUE, label: 'All accounts' },
    ...(accountsData?.items ?? []).map((a) => ({ value: String(a.id), label: a.label })),
  ];
  const partyOptions = [
    { value: SELECT_ALL_VALUE, label: 'All parties' },
    ...(partiesData?.items ?? []).map((p) => ({ value: String(p.id), label: p.name })),
  ];
  const kindOptions = [{ value: SELECT_ALL_VALUE, label: 'All types' }, ...PAYMENT_KIND_OPTIONS];
  const fromAll = (value) => (value === SELECT_ALL_VALUE ? '' : value);
  const dim = cn('transition-opacity', isFetching && !isLoading && 'opacity-60'); // old rows stay visible, dimmed, while the next set loads

  const transactions = data?.items ?? [];
  const total = data?.total ?? 0;

  const emptyText = narrowed ? `No payments match these filters (${dates.label}).` : 'No payments yet — record the first payment above.';
  const showAllDates = dates.mode !== 'all' && (
    <Button variant="outline" size="sm" onClick={dates.setAll}>
      Show all dates
    </Button>
  );

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <History className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Transactions</CardTitle>
            <CardDescription>
              Every payment recorded — money in from customers, money out to suppliers and for expenses. Each one is already posted to the ledger, none editable.
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {!isLoading && !isError && data && (
          <div className={cn('flex flex-col gap-2 rounded-lg border bg-muted/30 px-4 py-3', dim)}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div>
                <p className="text-xs text-muted-foreground">Money in</p>
                <CurrencyAmount value={data.total_in} className="text-2xl font-semibold text-emerald-600 dark:text-emerald-400" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Money out</p>
                <CurrencyAmount value={data.total_out} className="text-2xl font-semibold text-foreground" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Net</p>
                <CurrencyAmount
                  value={data.net}
                  className={cn('text-2xl font-semibold', Number(data.net) < 0 ? 'text-destructive' : 'text-foreground')}
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              {total} {total === 1 ? 'payment' : 'payments'}
              {narrowed ? ' matching the filters below' : ' across every date'}
              {data.by_kind.map((k) => (
                <span key={k.kind}>
                  {' · '}
                  {PAYMENT_KIND_LABELS[k.kind]} {k.count} (<CurrencyAmount value={Number(k.total_in) > 0 ? k.total_in : k.total_out} />)
                </span>
              ))}
              {data.shown_only_count > 0 && ` · ${data.shown_only_count} shown-only not counted`}
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="payment_search">Search</Label>
            <Input
              id="payment_search"
              type="search"
              placeholder="Note or party name"
              value={filters.searchInput}
              onChange={(event) => filters.handleSearchChange(event.target.value)}
            />
          </div>
          <FormSelect
            name="kind_filter"
            label="Type"
            options={kindOptions}
            value={kind || SELECT_ALL_VALUE}
            onChange={(value) => filters.setFilters({ type: fromAll(value) })}
          />
          <FormSelect
            name="account_filter"
            label="Account"
            options={accountOptions}
            value={account || SELECT_ALL_VALUE}
            onChange={(value) => filters.setFilters({ account: fromAll(value) })}
          />
          <FormSelect
            name="party_filter"
            label="Party"
            options={partyOptions}
            value={party || SELECT_ALL_VALUE}
            onChange={(value) => filters.setFilters({ party: fromAll(value) })}
          />
          <FormSelect
            name="sort_filter"
            label="Sort by date"
            options={SORT_OPTIONS}
            value={sort || DEFAULT_SORT}
            onChange={(value) => filters.setFilters({ sort: value === DEFAULT_SORT ? '' : value })}
          />
          <DateFilter filter={dates} id="payment_date" className="sm:col-span-2 lg:col-span-3" />
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
                <TableHead>Type</TableHead>
                <TableHead>Account</TableHead>
                <TableHead>Party</TableHead>
                <TableHead>Detail</TableHead>
                <TableHead className="text-right">Amount</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && transactions.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      {emptyText}
                      {showAllDates}
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {transactions.map((txn) => (
                <TableRow key={txn.id} className="hover:bg-muted/40">
                  <TableCell className="whitespace-nowrap">{txn.transaction_date}</TableCell>
                  <TableCell>
                    <span className="flex flex-wrap items-center gap-1">
                      <KindBadge kind={txn.kind} />
                      {txn.shown_only && <ShownOnlyBadge />}
                    </span>
                  </TableCell>
                  <TableCell>{txn.account_label}</TableCell>
                  <TableCell>
                    <PartyLink txn={txn} />
                  </TableCell>
                  <TableCell className="max-w-64 truncate">
                    <Detail txn={txn} />
                  </TableCell>
                  <TableCell className="text-right">
                    <SignedAmount txn={txn} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* phone: cards */}
        <div className={cn('flex flex-col gap-2 sm:hidden', dim)}>
          {isLoading && (
            <div className="flex h-32 flex-col items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
              Loading…
            </div>
          )}
          {isError && <div className="flex h-32 items-center justify-center text-destructive">Failed to load.</div>}
          {!isLoading && !isError && transactions.length === 0 && (
            <div className="flex h-32 flex-col items-center justify-center gap-2 text-center text-muted-foreground">
              <Inbox className="size-6 text-muted-foreground/60" />
              {emptyText}
              {showAllDates}
            </div>
          )}
          {transactions.map((txn) => (
            <div key={txn.id} className="rounded-lg border p-3">
              <div className="flex items-start justify-between gap-3">
                <span className="flex flex-wrap items-center gap-1">
                  <KindBadge kind={txn.kind} />
                  {txn.shown_only && <ShownOnlyBadge />}
                </span>
                <SignedAmount txn={txn} className="font-medium" />
              </div>
              <p className="mt-1 text-sm">
                <PartyLink txn={txn} />
                {txn.party_id ? ' · ' : ''}
                <span className="text-muted-foreground">{txn.transaction_date}</span>
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {txn.account_label} · <Detail txn={txn} />
              </p>
            </div>
          ))}
        </div>

        <PaginationControls page={filters.page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={filters.setPage} />
      </CardContent>
    </Card>
  );
}
