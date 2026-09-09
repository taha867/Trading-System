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

// GET /expenses/entries?expense_date_from=&expense_date_to= now filters
// server-side (a recurring template's auto-generated expense always lands on
// the 1st, so a one-day range is an exact-date match) — no more scanning a
// flat page_size=100 fetch that silently missed matches once total expense
// volume grew past 100 rows.
export function useTemplateIdsGeneratedThisMonth() {
  const monthStart = `${new Date().toISOString().slice(0, 7)}-01`;
  const query = useExpenses({ page: 1, page_size: 100, expense_date_from: monthStart, expense_date_to: monthStart });
  const ids = new Set(
    (query.data?.items ?? [])
      .filter((expense) => expense.recurring_template_id != null)
      .map((expense) => expense.recurring_template_id),
  );
  return { ...query, ids };
}
