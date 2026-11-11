import { useState } from 'react';
import { Loader2, Inbox, History } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { PaginationControls } from '@/components/common/PaginationControls';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { Button } from '@/components/ui/button';
import { DateFilter, FormSelect } from '@/components/custom';
import { usePaymentTransactions, usePaymentAccounts } from '@/hooks/paymentsHooks/paymentsQueries';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { PAYMENT_DIRECTION, PAYMENT_REFERENCE_TYPE_LABEL } from '@/utils/constants';
import { useDateFilter } from '@/hooks/useDateFilter';
import { useSearchParamFilters } from '@/hooks/useSearchParamFilters';
import { LOOKUP_PAGE } from '@/utils/queryParams';

const DEFAULT_PAGE_SIZE = 20;
const ALL_ACCOUNTS = 'all';

export function PaymentTransactionList() {
  const [page, setPage] = useState(1);
  const [accountFilter, setAccountFilter] = useState(ALL_ACCOUNTS);
  // The date filter lives in the URL (?month= / ?from=&to= / ?dates=all); default: the current month.
  const dates = useDateFilter(useSearchParamFilters());
  const dateKey = `${dates.dateFrom ?? ''}|${dates.dateTo ?? ''}`;
  const [seenDateKey, setSeenDateKey] = useState(dateKey);
  if (seenDateKey !== dateKey) {
    setSeenDateKey(dateKey); // a new period starts on page 1
    setPage(1);
  }

  const { data, isLoading, isError } = usePaymentTransactions({
    page,
    page_size: DEFAULT_PAGE_SIZE,
    date_from: dates.dateFrom,
    date_to: dates.dateTo,
  });
  const { data: accountsData } = usePaymentAccounts(LOOKUP_PAGE);
  const { data: partiesData } = useParties(LOOKUP_PAGE);

  const accountLabelById = Object.fromEntries((accountsData?.items ?? []).map((a) => [a.id, a.label]));
  const partyNameById = Object.fromEntries((partiesData?.items ?? []).map((p) => [p.id, p.name]));
  // 'all' is a real sentinel option, not an empty-string SelectItem — Radix's
  // Select reserves value="" internally to mean "nothing selected", so a "clear
  // the filter" option needs a real, non-empty value instead.
  const accountOptions = [
    { value: ALL_ACCOUNTS, label: 'All accounts' },
    ...(accountsData?.items ?? []).map((a) => ({ value: String(a.id), label: a.label })),
  ];

  // GET /payment-transactions has no ?payment_account_id= filter — this only
  // narrows the current page, not the full history.
  const allTransactions = data?.items ?? [];
  const transactions =
    accountFilter === ALL_ACCOUNTS
      ? allTransactions
      : allTransactions.filter((t) => String(t.payment_account_id) === accountFilter);
  const total = data?.total ?? 0;

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <History className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Transactions</CardTitle>
            <CardDescription>Every payment recorded — each one already posted to the ledger, none editable.</CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <FormSelect
            name="account_filter"
            label="Filter by account"
            options={accountOptions}
            value={accountFilter}
            onChange={setAccountFilter}
          />
          <DateFilter filter={dates} id="payment_date" className="sm:col-span-1 lg:col-span-2" />
        </div>

        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>Date</TableHead>
                <TableHead>Direction</TableHead>
                <TableHead>Account</TableHead>
                <TableHead>Party</TableHead>
                <TableHead>Reference</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead>Note</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && transactions.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      {dates.mode === 'all' ? 'No transactions yet — record the first payment above.' : `No transactions in ${dates.label}.`}
                      {dates.mode !== 'all' && (
                        <Button variant="outline" size="sm" onClick={dates.setAll}>
                          Show all dates
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {transactions.map((txn) => (
                <TableRow key={txn.id} className="hover:bg-muted/40">
                  <TableCell>{txn.transaction_date}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{txn.direction === PAYMENT_DIRECTION.IN ? 'In' : 'Out'}</Badge>
                  </TableCell>
                  <TableCell>{accountLabelById[txn.payment_account_id] ?? `Account #${txn.payment_account_id}`}</TableCell>
                  <TableCell>{txn.party_id ? partyNameById[txn.party_id] ?? `Party #${txn.party_id}` : '—'}</TableCell>
                  <TableCell>
                    {txn.reference_type
                      ? `${PAYMENT_REFERENCE_TYPE_LABEL[txn.reference_type] ?? txn.reference_type} #${txn.reference_id}`
                      : '—'}
                  </TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={txn.amount} />
                  </TableCell>
                  <TableCell className="max-w-40 truncate" title={txn.note ?? ''}>
                    {txn.note || '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <PaginationControls page={page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={setPage} />
      </CardContent>
    </Card>
  );
}
