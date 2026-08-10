import { useMutation, useQueryClient } from '@tanstack/react-query';
import { expenseCategoryKeys, recurringExpenseTemplateKeys, expenseKeys, paymentAccountKeys } from '@/utils/queryKeys';
import * as expensesService from '@/services/expensesService';

export function useCreateExpenseCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.createExpenseCategory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: expenseCategoryKeys.lists() }),
  });
}

export function useUpdateExpenseCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.updateExpenseCategory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: expenseCategoryKeys.lists() }),
  });
}

export function useDeleteExpenseCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.deleteExpenseCategory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: expenseCategoryKeys.lists() }),
  });
}

export function useCreateRecurringExpenseTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.createRecurringExpenseTemplate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: recurringExpenseTemplateKeys.lists() }),
  });
}

export function useUpdateRecurringExpenseTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.updateRecurringExpenseTemplate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: recurringExpenseTemplateKeys.lists() }),
  });
}

export function useDeleteRecurringExpenseTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.deleteRecurringExpenseTemplate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: recurringExpenseTemplateKeys.lists() }),
  });
}

// Generating a draft touches no money — only expenseKeys needs invalidating
// (ExpenseList and the "Generated this month" badge both re-read from it).
// No paymentAccountKeys.balances() invalidation here, unlike confirm/create
// below — nothing has posted yet.
export function useGenerateExpenseFromTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.generateExpenseFromTemplate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: expenseKeys.lists() }),
  });
}

// Posts immediately (status="confirmed") — invalidates account balances too,
// the same paired invalidation useCreatePaymentTransaction/
// useCreatePaymentAccount already use (hooks/paymentsHooks/paymentsMutations.js).
export function useCreateExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.createExpense,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: expenseKeys.lists() });
      queryClient.invalidateQueries({ queryKey: paymentAccountKeys.balances() });
    },
  });
}

// Confirming a draft is the other moment money actually moves — same paired
// invalidation as create, above.
export function useConfirmExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.confirmExpense,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: expenseKeys.lists() });
      queryClient.invalidateQueries({ queryKey: paymentAccountKeys.balances() });
    },
  });
}

// Discarding a still-draft expense never touched an account balance — only
// expenseKeys needs invalidating.
export function useDiscardExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: expensesService.discardExpense,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: expenseKeys.lists() }),
  });
}
