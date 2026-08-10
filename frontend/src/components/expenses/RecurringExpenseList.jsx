import { useState } from 'react';
import { Plus, Pencil, Trash2, Loader2, Inbox, Repeat, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { PaginationControls } from '@/components/common/PaginationControls';
import { ConfirmDeleteDialog } from '@/components/common/ConfirmDeleteDialog';
import { CrudDrawer } from '@/components/common/CrudDrawer';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { recurringExpenseTemplateCrudConfig } from '@/components/expenses/RecurringExpenseTemplateCrudConfig';
import { useExpenseCategories, useTemplateIdsGeneratedThisMonth } from '@/hooks/expensesHooks/expensesQueries';
import { usePaymentAccounts } from '@/hooks/paymentsHooks/paymentsQueries';
import { useGenerateExpenseFromTemplate } from '@/hooks/expensesHooks/expensesMutations';
import { EXPENSE_CATEGORY_FREQUENCY } from '@/utils/constants';

const DEFAULT_PAGE_SIZE = 20;
const LOOKUP_PAGE = { page: 1, page_size: 100 };

export function RecurringExpenseList() {
  const [page, setPage] = useState(1);
  const [drawerState, setDrawerState] = useState(null); // { mode: 'create' | 'edit', row? }
  const [deleteRow, setDeleteRow] = useState(null);

  const { data, isLoading, isError } = recurringExpenseTemplateCrudConfig.useList({ page, page_size: DEFAULT_PAGE_SIZE });
  const deleteMutation = recurringExpenseTemplateCrudConfig.useDelete();
  const generateMutation = useGenerateExpenseFromTemplate();
  const { data: categoriesData } = useExpenseCategories(LOOKUP_PAGE);
  const { data: accountsData } = usePaymentAccounts(LOOKUP_PAGE);
  const { ids: generatedThisMonth } = useTemplateIdsGeneratedThisMonth();

  const categoryNameById = Object.fromEntries((categoriesData?.items ?? []).map((c) => [c.id, c.name]));
  const accountLabelById = Object.fromEntries((accountsData?.items ?? []).map((a) => [a.id, a.label]));
  // Only monthly categories are offered here — a UX nicety, not a backend rule.
  const monthlyCategoryOptions = (categoriesData?.items ?? [])
    .filter((c) => c.frequency === EXPENSE_CATEGORY_FREQUENCY.MONTHLY)
    .map((c) => ({ value: String(c.id), label: c.name }));
  const accountOptions = (accountsData?.items ?? []).map((a) => ({ value: String(a.id), label: a.label }));

  const config = {
    ...recurringExpenseTemplateCrudConfig,
    columns: recurringExpenseTemplateCrudConfig.columns.map((column) => {
      if (column.key === 'category_id') {
        return { ...column, render: (row) => categoryNameById[row.category_id] ?? `Category #${row.category_id}` };
      }
      if (column.key === 'payment_account_id') {
        return { ...column, render: (row) => accountLabelById[row.payment_account_id] ?? `Account #${row.payment_account_id}` };
      }
      if (column.key === 'amount') {
        return { ...column, render: (row) => <CurrencyAmount value={row.amount} /> };
      }
      return column;
    }),
    fields: recurringExpenseTemplateCrudConfig.fields.map((field) => {
      if (field.name === 'category_id') return { ...field, options: monthlyCategoryOptions };
      if (field.name === 'payment_account_id') return { ...field, options: accountOptions };
      return field;
    }),
  };

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const columnCount = config.columns.length + 1; // + Actions

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Repeat className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Recurring Templates</CardTitle>
            <CardDescription>
              Monthly fixed costs — generate this month's draft, then confirm it once it's actually paid.
            </CardDescription>
          </div>
        </div>
        <CardAction>
          <Button size="sm" onClick={() => setDrawerState({ mode: 'create' })}>
            <Plus />
            Add template
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                {config.columns.map((column) => (
                  <TableHead key={column.key}>{column.label}</TableHead>
                ))}
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={columnCount} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={columnCount} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={columnCount} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No recurring templates yet — add the first one above.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {items.map((row) => (
                <TableRow key={row.id} className="hover:bg-muted/40">
                  {config.columns.map((column) => (
                    <TableCell key={column.key}>{column.render ? column.render(row) : (row[column.key] ?? '—')}</TableCell>
                  ))}
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      {generatedThisMonth.has(row.id) ? (
                        <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                          <CheckCircle2 className="size-4 text-primary" />
                          Generated
                        </span>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={generateMutation.isPending}
                          onClick={() => generateMutation.mutate(row.id)}
                        >
                          Generate
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Edit recurring expense template"
                        onClick={() => setDrawerState({ mode: 'edit', row })}
                      >
                        <Pencil />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Delete recurring expense template"
                        onClick={() => setDeleteRow(row)}
                      >
                        <Trash2 className="text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <PaginationControls page={page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={setPage} />
      </CardContent>

      <CrudDrawer
        config={config}
        open={Boolean(drawerState)}
        mode={drawerState?.mode}
        row={drawerState?.row}
        entityLabel="recurring expense template"
        onOpenChange={(nextOpen) => !nextOpen && setDrawerState(null)}
      />

      <ConfirmDeleteDialog
        open={Boolean(deleteRow)}
        onOpenChange={(nextOpen) => !nextOpen && setDeleteRow(null)}
        isPending={deleteMutation.isPending}
        itemLabel="recurring expense template"
        onConfirm={async () => {
          await deleteMutation.mutateAsync(deleteRow?.id);
          setDeleteRow(null);
        }}
      />
    </Card>
  );
}
