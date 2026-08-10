import { object, string, number } from 'yup';
import { PAYMENT_DIRECTION } from '@/utils/constants';

export const paymentMethodCreateSchema = object({
  name: string().required('Name is required').max(64),
});

// PaymentMethodUpdate genuinely mirrors PaymentMethodCreate with every field
// optional — plain .partial() is correct here (contrast with ExchangeRateUpdate).
export const paymentMethodUpdateSchema = paymentMethodCreateSchema.partial();

export const paymentAccountCreateSchema = object({
  payment_method_id: number().typeError('Select a payment method').required('Select a payment method'),
  label: string().required('Label is required').max(120),
  account_number: string().max(64).nullable().default(null),
  opening_balance: number().typeError('Opening balance must be a number').default(0),
});

// PaymentAccountUpdate on the backend only accepts label/account_number — its own
// object rather than a .partial() of the create schema, since payment_method_id and
// opening_balance aren't merely optional on update, the backend rejects them
// outright.
export const paymentAccountUpdateSchema = object({
  label: string().required('Label is required').max(120),
  account_number: string().max(64).nullable().default(null),
});

export const paymentTransactionCreateSchema = object({
  payment_account_id: number().typeError('Select an account').required('Select an account'),
  direction: string().oneOf(Object.values(PAYMENT_DIRECTION)).required('Select a direction'),
  amount: number().typeError('Amount must be a number').positive('Amount must be positive').required('Amount is required'),
  transaction_date: string().required('Date is required'),
  // Optional numeric fields: the transform is required so an untouched '' from the
  // form casts to null rather than NaN before typeError runs — the same pattern
  // purchasingSchemas.js's rate_rmb/rate_pkr already use.
  party_id: number()
    .transform((value, originalValue) => (originalValue === '' ? null : value))
    .typeError('Select a party')
    .nullable()
    .default(null),
  reference_type: string()
    .transform((value) => (value === '' ? null : value))
    .nullable()
    .default(null),
  reference_id: number()
    .transform((value, originalValue) => (originalValue === '' ? null : value))
    .typeError('Pick a document')
    .nullable()
    .default(null),
  note: string().max(255).nullable().default(null),
})
  // Mirrors the backend's model_validator verbatim — both set or both null,
  // checked here as a sibling-field .test() the same shape purchasingSchemas.js's
  // rate-matches-source test already uses on its own object schema.
  .test(
    'reference-type-and-id-together',
    'Pick a document to link, or clear both the type and the selection',
    (values) => (values.reference_type == null) === (values.reference_id == null),
  );
