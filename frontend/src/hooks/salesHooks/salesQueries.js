import { useQuery } from '@tanstack/react-query';
import { salesOrderKeys } from '@/utils/queryKeys';
import { listSalesOrders, getSalesOrder } from '@/services/salesService';

export function useSalesOrders(params) {
  return useQuery({ queryKey: salesOrderKeys.list(params), queryFn: () => listSalesOrders(params) });
}

export function useSalesOrder(id) {
  return useQuery({
    queryKey: salesOrderKeys.detail(id),
    queryFn: () => getSalesOrder(id),
    enabled: Boolean(id),
  });
}
