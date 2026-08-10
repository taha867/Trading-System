import { usePaymentAccounts } from '@/hooks/paymentsHooks/paymentsQueries';
import {
  useCreatePaymentAccount,
  useUpdatePaymentAccount,
  useDeletePaymentAccount,
} from '@/hooks/paymentsHooks/paymentsMutations';
import { paymentAccountCreateSchema, paymentAccountUpdateSchema } from '@/validations/paymentsSchemas';
import { paymentAccountKeys } from '@/utils/queryKeys';

// `payment_method_id`'s options and the same column's display value both need a
// live PaymentMethod lookup, which a plain exported config object can't fetch
// itself — PaymentAccountList injects both at render time before handing this
// config to CrudTable. Left empty/undecorated here.
export const paymentAccountCrudConfig = {
  queryKey: paymentAccountKeys,
  useList: usePaymentAccounts,
  useCreate: useCreatePaymentAccount,
  useUpdate: useUpdatePaymentAccount,
  useDelete: useDeletePaymentAccount,
  columns: [
    { key: 'label', label: 'Label' },
    { key: 'payment_method_id', label: 'Method' },
    { key: 'account_number', label: 'Account number' },
  ],
  createSchema: paymentAccountCreateSchema,
  updateSchema: paymentAccountUpdateSchema,
  fields: [
    // Update schema doesn't accept this field at all — disabled in edit mode so
    // RHF drops it from the submitted payload (same reasoning as opening_balance).
    { name: 'payment_method_id', label: 'Payment method', component: 'select', options: [], editableOnUpdate: false },
    { name: 'label', label: 'Label', component: 'text' },
    { name: 'account_number', label: 'Account number', component: 'text' },
    // Write-once on the backend — posts its own ledger row at creation — disabled
    // in edit mode, same as PartyCrudConfig.jsx's opening_balance field.
    {
      name: 'opening_balance',
      label: 'Opening balance',
      component: 'number',
      step: '0.01',
      defaultValue: 0,
      editableOnUpdate: false,
    },
  ],
};
