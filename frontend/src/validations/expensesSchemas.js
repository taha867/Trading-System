import { object, string, number } from 'yup';
import { EXPENSE_CATEGORY_FREQUENCY } from '@/utils/constants';

export const expenseCategoryCreateSchema = object({
  name: string().required('Name is required').max(120),
  frequency: string().oneOf(Object.values(EXPENSE_CATEGORY_FREQUENCY)).required('Select a frequency'),
});

// ExpenseCategoryUpdate mirrors ExpenseCategoryCreate with every field optional —
// plain .partial() is correct here (same reasoning as paymentMethodUpdateSchema).
export const expenseCategoryUpdateSchema = expenseCategoryCreateSchema.partial();

export const recurringExpenseTemplateCreateSchema = object({
  name: string().required('Name is required').max(120),
  category_id: number().typeError('Select a category').required('Select a category'),
  payment_account_id: number().typeError('Select an account').required('Select an account'),
  amount: number().typeError('Amount must be a number').positive('Amount must be positive').required('Amount is required'),
  // Optional numeric field: the transform casts an untouched '' to null rather
  // than NaN before typeError runs — the same pattern paymentsSchemas.js's
  // party_id/reference_id already use.
  day_of_month: number()
    .transform((value, originalValue) => (originalValue === '' ? null : value))
    .typeError('Day of month must be a number')
    .min(1, 'Day of month must be between 1 and 28')
    .max(28, 'Day of month must be between 1 and 28')
    .nullable()
    .default(null),
  description: string().max(255).nullable().default(null),
});

// RecurringExpenseTemplateUpdate genuinely accepts every field optional, unlike
// PaymentAccountUpdate's narrower backend schema — .partial() applies cleanly.
export const recurringExpenseTemplateUpdateSchema = recurringExpenseTemplateCreateSchema.partial();

export const expenseCreateSchema = object({
  category_id: number().typeError('Select a category').required('Select a category'),
  payment_account_id: number().typeError('Select an account').required('Select an account'),
  amount: number().typeError('Amount must be a number').positive('Amount must be positive').required('Amount is required'),
  expense_date: string().required('Date is required'),
  description: string().max(255).nullable().default(null),
});
// No expenseUpdateSchema — Expense has no update endpoint.
