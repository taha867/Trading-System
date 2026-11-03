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
import { usePurchaseLogExceptions } from '@/hooks/purchasingHooks/purchasingQueries';
import { useVendorParties } from '@/hooks/partyHooks/partyQueries';
import { useSearchParamFilters } from '@/hooks/useSearchParamFilters';
import { monthBounds, formatDateTime } from '@/utils/dateUtils';
import { SELECT_ALL_VALUE } from '@/utils/constants';

const DEFAULT_PAGE_SIZE = 20;
const FILTER_KEYS = ['search', 'party', 'month'];
const COLUMN_COUNT = 10;

export function PurchaseLogExceptionList() {
  const filters = useSearchParamFilters();
  const { vendors } = useVendorParties();

  const party = filters.get('party');
  const month = filters.get('month');
  const search = filters.get('search');
  const bounds = monthBounds(month);
  const hasActiveFilter = Boolean(search || party || month);

  const { data, isLoading, isError } = usePurchaseLogExceptions({
    page: filters.page,
    page_size: DEFAULT_PAGE_SIZE,
    search: search || undefined,
    party_id: party || undefined,
    date_from: bounds?.from,
    date_to: bounds?.to,
  });

  const vendorOptions = [
    { value: SELECT_ALL_VALUE, label: 'All vendors' },
    ...vendors.map((v) => ({ value: String(v.id), label: v.name })),
  ];

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
            <CardTitle className="text-base">Other purchase entries</CardTitle>
            <CardDescription>
              Goods bought where the day book gave a category but no phone model, so no stock could be recorded. Only
              the money owed to the supplier is posted.
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {!isLoading && !isError && data && (
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 rounded-lg border bg-muted/30 px-4 py-3">
            <CurrencyAmount value={data.total_amount_pkr} className="text-2xl font-semibold text-foreground" />
            <span className="text-sm text-muted-foreground">
              owed to suppliers{hasActiveFilter ? ' matching the filters below' : ' across every entry'} · {total}{' '}
              {total === 1 ? 'entry' : 'entries'}
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="purchase_exceptions_search">Invoice no. or note</Label>
            <Input
              id="purchase_exceptions_search"
              type="search"
              placeholder="e.g. 444"
              value={filters.searchInput}
              onChange={(event) => filters.handleSearchChange(event.target.value)}
            />
          </div>
          <FormSelect
            name="purchase_exceptions_vendor_filter"
            label="Vendor"
            options={vendorOptions}
            value={party || SELECT_ALL_VALUE}
            onChange={(value) => filters.setFilters({ party: value === SELECT_ALL_VALUE ? '' : value })}
          />
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="purchase_exceptions_month">Month</Label>
            <Input
              id="purchase_exceptions_month"
              type="month"
              value={month}
              onChange={(event) => filters.setFilters({ month: event.target.value })}
            />
          </div>
        </div>

        {hasActiveFilter && (
          <Button variant="outline" size="sm" className="self-start" onClick={() => filters.clearFilters(FILTER_KEYS)}>
            <X />
            Clear filters
          </Button>
        )}

        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>Date</TableHead>
                <TableHead>Invoice no.</TableHead>
                <TableHead>Vendor</TableHead>
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
                      {hasActiveFilter ? 'No entries match these filters.' : 'No other purchase entries.'}
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {entries.map((entry) => (
                <TableRow key={entry.id} className="hover:bg-muted/40">
                  <TableCell>{entry.entry_date}</TableCell>
                  <TableCell>{entry.invoice_number || '—'}</TableCell>
                  <TableCell>
                    <Link to={`/parties/${entry.party_id}`} className="hover:underline">
                      {entry.party_name}
                    </Link>
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

        <PaginationControls page={filters.page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={filters.setPage} />
      </CardContent>
    </Card>
  );
}
