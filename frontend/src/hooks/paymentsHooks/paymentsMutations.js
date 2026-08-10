import { useMutation, useQueryClient } from '@tanstack/react-query';
import { paymentMethodKeys, paymentAccountKeys, paymentTransactionKeys, partyKeys } from '@/utils/queryKeys';
import * as paymentsService from '@/services/paymentsService';

export function useCreatePaymentMethod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: paymentsService.createPaymentMethod,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: paymentMethodKeys.lists() }),
  });
}

export function useUpdatePaymentMethod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: paymentsService.updatePaymentMethod,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: paymentMethodKeys.lists() }),
  });
}

export function useDeletePaymentMethod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: paymentsService.deletePaymentMethod,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: paymentMethodKeys.lists() }),
  });
}

export function useCreatePaymentAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: paymentsService.createPaymentAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: paymentAccountKeys.lists() });
      queryClient.invalidateQueries({ queryKey: paymentAccountKeys.balances() });
    },
  });
}

export function useUpdatePaymentAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: paymentsService.updatePaymentAccount,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: paymentAccountKeys.lists() }),
  });
}

export function useDeletePaymentAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: paymentsService.deletePaymentAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: paymentAccountKeys.lists() });
      queryClient.invalidateQueries({ queryKey: paymentAccountKeys.balances() });
    },
  });
}

export function useCreatePaymentTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: paymentsService.createPaymentTransaction,
    onSuccess: (transaction, variables) => {
      queryClient.invalidateQueries({ queryKey: paymentTransactionKeys.lists() });
      queryClient.invalidateQueries({ queryKey: paymentAccountKeys.balances() });
      // Only when a party was actually linked — mirrors useCreateSalesOrder's
      // conditional partyKeys.statement invalidation: a payment with no party_id
      // never touches that party's ledger rows.
      if (variables.party_id) {
        queryClient.invalidateQueries({ queryKey: partyKeys.statement(variables.party_id) });
      }
    },
  });
}
