import { useQuery } from '@tanstack/react-query';
import { paymentMethodKeys, paymentAccountKeys, paymentTransactionKeys } from '@/utils/queryKeys';
import {
  listPaymentMethods,
  listPaymentAccounts,
  getPaymentAccountBalances,
  listPaymentTransactions,
} from '@/services/paymentsService';

export function usePaymentMethods(params) {
  return useQuery({
    queryKey: paymentMethodKeys.list(params),
    queryFn: () => listPaymentMethods(params),
  });
}

export function usePaymentAccounts(params) {
  return useQuery({
    queryKey: paymentAccountKeys.list(params),
    queryFn: () => listPaymentAccounts(params),
  });
}

export function usePaymentAccountBalances() {
  return useQuery({
    queryKey: paymentAccountKeys.balances(),
    queryFn: getPaymentAccountBalances,
  });
}

export function usePaymentTransactions(params) {
  return useQuery({
    queryKey: paymentTransactionKeys.list(params),
    queryFn: () => listPaymentTransactions(params),
  });
}
