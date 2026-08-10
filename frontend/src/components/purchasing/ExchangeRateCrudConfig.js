import { useExchangeRates } from '@/hooks/purchasingHooks/purchasingQueries';
import {
  useCreateExchangeRate,
  useUpdateExchangeRate,
  useDeleteExchangeRate,
} from '@/hooks/purchasingHooks/purchasingMutations';
import { exchangeRateCreateSchema, exchangeRateUpdateSchema } from '@/validations/purchasingSchemas';
import { exchangeRateKeys } from '@/utils/queryKeys';

export const exchangeRateCrudConfig = {
  queryKey: exchangeRateKeys,
  useList: useExchangeRates,
  useCreate: useCreateExchangeRate,
  useUpdate: useUpdateExchangeRate,
  useDelete: useDeleteExchangeRate,
  columns: [
    { key: 'rate_date', label: 'Date' },
    { key: 'rate', label: 'RMB → PKR' },
  ],
  createSchema: exchangeRateCreateSchema,
  updateSchema: exchangeRateUpdateSchema,
  fields: [
    // Backend's ExchangeRateUpdate doesn't accept rate_date — CrudDrawer disables
    // this field in edit mode so it's never submitted (phase-0-frontend spec §7.1).
    { name: 'rate_date', label: 'Date', component: 'date', editableOnUpdate: false },
    { name: 'rate', label: 'RMB → PKR rate', component: 'number', step: '0.0001' },
  ],
};
