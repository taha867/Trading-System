import { object, string, number, array } from 'yup';
import { PURCHASE_ORDER_SOURCE } from '@/utils/constants';

export const purchaseOrderLineSchema = object({
  item_id: number().typeError('Select an item').required('Select an item'),
  qty: number().typeError('Quantity must be a number').positive('Quantity must be positive').required('Quantity is required'),
  // Both optional at the per-line level — which one is actually required depends on
  // the parent order's `source`, enforced once below via the array-level test,
  // mirroring the backend's own model_validator (phase-5-backend.md §2.3).
  // The transform is required: the field not rendered for the current source stays
  // '' (the form's empty-string convention), and Yup's number() type treats '' as
  // NaN rather than null, which would otherwise fail typeError on every submit.
  rate_rmb: number()
    .transform((value, originalValue) => (originalValue === '' ? null : value))
    .typeError('Rate must be a number')
    .positive('Rate must be positive')
    .nullable()
    .default(null),
  rate_pkr: number()
    .transform((value, originalValue) => (originalValue === '' ? null : value))
    .typeError('Rate must be a number')
    .positive('Rate must be positive')
    .nullable()
    .default(null),
});

export const purchaseOrderCreateSchema = object({
  party_id: number().typeError('Select a vendor').required('Select a vendor'),
  order_date: string().required('Order date is required'),
  source: string().oneOf(Object.values(PURCHASE_ORDER_SOURCE)).required(),
  lines: array()
    .of(purchaseOrderLineSchema)
    .min(1, 'Add at least one line')
    // Sibling access via this.parent — `lines` and `source` are both direct children
    // of this same object schema (phase-5-frontend spec §2 decision 4).
    .test(
      'rate-matches-source',
      'Enter a rate for every line — RMB for a China order, PKR for a local vendor order',
      function (lines) {
        const { source } = this.parent;
        if (!lines) return true;
        return lines.every((line) =>
          source === PURCHASE_ORDER_SOURCE.CHINA ? Number(line.rate_rmb) > 0 : Number(line.rate_pkr) > 0,
        );
      },
    ),
});

export const exchangeRateCreateSchema = object({
  rate_date: string().required('Date is required'),
  rate: number().typeError('Rate must be a number').positive('Rate must be positive').required('Rate is required'),
});

// Backend's ExchangeRateUpdate only accepts `rate` — .pick() keeps rate_date out
// entirely rather than merely optional, matching the backend schema exactly.
export const exchangeRateUpdateSchema = exchangeRateCreateSchema.pick(['rate']).partial();
