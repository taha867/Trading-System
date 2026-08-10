import { usePaymentMethods } from '@/hooks/paymentsHooks/paymentsQueries';
import {
  useCreatePaymentMethod,
  useUpdatePaymentMethod,
  useDeletePaymentMethod,
} from '@/hooks/paymentsHooks/paymentsMutations';
import { paymentMethodCreateSchema, paymentMethodUpdateSchema } from '@/validations/paymentsSchemas';
import { paymentMethodKeys } from '@/utils/queryKeys';

export const paymentMethodCrudConfig = {
  queryKey: paymentMethodKeys,
  useList: usePaymentMethods,
  useCreate: useCreatePaymentMethod,
  useUpdate: useUpdatePaymentMethod,
  useDelete: useDeletePaymentMethod,
  columns: [{ key: 'name', label: 'Name' }],
  createSchema: paymentMethodCreateSchema,
  updateSchema: paymentMethodUpdateSchema,
  fields: [{ name: 'name', label: 'Name', component: 'text' }],
};
