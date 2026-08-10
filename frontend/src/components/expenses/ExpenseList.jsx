import { useState } from 'react';
import { Loader2, Inbox, Receipt, Trash2 } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { PaginationControls } from '@/components/common/PaginationControls';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { FormSelect } from '@/components/custom';
import { useExpenses, useExpenseCategories } from '@/hooks/expensesHooks/expensesQueries';
import { usePaymentAccounts } from '@/hooks/paymentsHooks/paymentsQueries';
import { useConfirmExpense, useDiscardExpense } from '@/hooks/expensesHooks/expensesMutations';
import { EXPENSE_STATUS, EXPENSE_STATUS_OPTIONS } from '@/utils/constants';

const DEFAULT_PAGE_SIZE = 20;
const LOOKUP_PAGE = { page: 1, page_size: 100 };
const ALL = 'all';

export function ExpenseList() {
  const [page, setPage] = useState(1);
  const [categoryFilter, setCategoryFilter] = useState(ALL);
  const [accountFilter, setAccountFilter] = useState(ALL);
  const [statusFilter, setStatusFilter] = useState(ALL);
  const [confirmingRow, setConfirmingRow] = useState(null);
  const [discardingRow, setDiscardingRow] = useState(null);

  const { data: categoriesData } = useExpenseCategories(LOOKUP_PAGE);
  const { data: accountsData } = usePaymentAccounts(LOOKUP_PAGE);

  // Real server-side filters — unlike PaymentTransactionList's client-side-only
  // account filter, these narrow the full history.
  const { data, isLoading, isError } = useExpenses({
    page,
    page_size: DEFAULT_PAGE_SIZE,
    ...(categoryFilter !== ALL ? { category_id: categoryFilter } : {}),
    ...(accountFilter !== ALL ? { payment_account_id: accountFilter } : {}),
    ...(statusFilter !== ALL ? { status: statusFilter } : {}),
  });

  const confirmMutation = useConfirmExpense();
  const discardMutation = useDiscardExpense();

  const categoryNameById = Object.fromEntries((categoriesData?.items ?? []).map((c) => [c.id, c.name]));
  const accountLabelById = Object.fromEntries((accountsData?.items ?? []).map((a) => [a.id, a.label]));
  const categoryOptions = [
    { value: ALL, label: 'All categories' },
    ...(categoriesData?.items ?? []).map((c) => ({ value: String(c.id), label: c.name })),
  ];
  const accountOptions = [
    { value: ALL, label: 'All accounts' },
    ...(accountsData?.items ?? []).map((a) => ({ value: String(a.id), label: a.label })),
  ];
  const statusOptions = [{ value: ALL, label: 'All statuses' }, ...EXPENSE_STATUS_OPTIONS];

  const expenses = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Receipt className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Expenses</CardTitle>
            <CardDescription>
              Every expense recorded — drafts wait for confirmation before they touch an account's balance.
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <FormSelect name="category_filter" label="Category" options={categoryOptions} value={categoryFilter} onChange={setCategoryFilter} />
          <FormSelect name="account_filter" label="Account" options={accountOptions} value={accountFilter} onChange={setAccountFilter} />
          <FormSelect name="status_filter" label="Status" options={statusOptions} value={statusFilter} onChange={setStatusFilter} />
        </div>

        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>Date</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Account</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
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
              {!isLoading && !isError && expenses.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No expenses yet — add the first one above.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {expenses.map((expense) => (
                <TableRow key={expense.id} className="hover:bg-muted/40">
                  <TableCell>{expense.expense_date}</TableCell>
                  <TableCell>{categoryNameById[expense.category_id] ?? `Category #${expense.category_id}`}</TableCell>
                  <TableCell>{accountLabelById[expense.payment_account_id] ?? `Account #${expense.payment_account_id}`}</TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={expense.amount} />
                  </TableCell>
                  <TableCell className="max-w-40 truncate" title={expense.description ?? ''}>
                    {expense.description || '—'}
                  </TableCell>
                  <TableCell>
                    <Badge variant={expense.status === EXPENSE_STATUS.DRAFT ? 'outline' : 'secondary'}>
                      {expense.status === EXPENSE_STATUS.DRAFT ? 'Draft' : 'Confirmed'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    {expense.status === EXPENSE_STATUS.DRAFT ? (
                      <div className="flex justify-end gap-1">
                        <Button size="sm" onClick={() => setConfirmingRow(expense)}>
                          Confirm
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label="Discard draft expense"
                          onClick={() => setDiscardingRow(expense)}
                        >
                          <Trash2 className="text-destructive" />
                        </Button>
                      </div>
                    ) : (
                      '—'
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <PaginationControls page={page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={setPage} />
      </CardContent>

      <ConfirmDialog
        open={Boolean(confirmingRow)}
        onOpenChange={(nextOpen) => !nextOpen && setConfirmingRow(null)}
        isPending={confirmMutation.isPending}
        title="Confirm this expense?"
        description="This posts a payment transaction against the account immediately — its balance will drop by the expense amount."
        confirmLabel="Confirm & pay"
        pendingLabel="Confirming…"
        onConfirm={async () => {
          await confirmMutation.mutateAsync(confirmingRow?.id);
          setConfirmingRow(null);
        }}
      />

      {/* Not ConfirmDeleteDialog — its hardcoded copy claims a soft delete,
          but a draft expense is genuinely hard-deleted. */}
      <ConfirmDialog
        open={Boolean(discardingRow)}
        onOpenChange={(nextOpen) => !nextOpen && setDiscardingRow(null)}
        isPending={discardMutation.isPending}
        title="Discard this draft expense?"
        description="Nothing has posted yet, so this is a permanent delete — there's no ledger entry to undo."
        confirmLabel="Discard"
        pendingLabel="Discarding…"
        confirmVariant="destructive"
        onConfirm={async () => {
          await discardMutation.mutateAsync(discardingRow?.id);
          setDiscardingRow(null);
        }}
      />
    </Card>
  );
}
