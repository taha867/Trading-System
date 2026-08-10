import { useQuery } from '@tanstack/react-query';
import { expenseCategoryKeys, recurringExpenseTemplateKeys, expenseKeys } from '@/utils/queryKeys';
import {
  listExpenseCategories,
  listRecurringExpenseTemplates,
  listExpenses,
} from '@/services/expensesService';

export function useExpenseCategories(params) {
  return useQuery({
    queryKey: expenseCategoryKeys.list(params),
    queryFn: () => listExpenseCategories(params),
  });
}

export function useRecurringExpenseTemplates(params) {
  return useQuery({
    queryKey: recurringExpenseTemplateKeys.list(params),
    queryFn: () => listRecurringExpenseTemplates(params),
  });
}

export function useExpenses(params) {
  return useQuery({
    queryKey: expenseKeys.list(params),
    queryFn: () => listExpenses(params),
  });
}

// Same derived-Set-over-a-fetched-page shape as useReceivedLineIds
// (hooks/inventoryHooks/inventoryQueries.js) — there's no backend "has this
// template already been generated this month" flag, so it's computed
// client-side from a LOOKUP_PAGE-sized fetch of entries. Inherits that
// hook's own known limitation: a template whose matching expense falls
// outside the first 100 entries (page_size=100) won't be detected as
// already-generated.
export function useTemplateIdsGeneratedThisMonth() {
  const monthStart = `${new Date().toISOString().slice(0, 7)}-01`;
  const query = useExpenses({ page: 1, page_size: 100 });
  const ids = new Set(
    (query.data?.items ?? [])
      .filter((expense) => expense.recurring_template_id != null && expense.expense_date === monthStart)
      .map((expense) => expense.recurring_template_id),
  );
  return { ...query, ids };
}
