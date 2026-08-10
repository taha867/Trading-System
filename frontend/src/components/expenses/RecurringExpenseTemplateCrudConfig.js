import { useRecurringExpenseTemplates } from '@/hooks/expensesHooks/expensesQueries';
import {
  useCreateRecurringExpenseTemplate,
  useUpdateRecurringExpenseTemplate,
  useDeleteRecurringExpenseTemplate,
} from '@/hooks/expensesHooks/expensesMutations';
import {
  recurringExpenseTemplateCreateSchema,
  recurringExpenseTemplateUpdateSchema,
} from '@/validations/expensesSchemas';
import { recurringExpenseTemplateKeys } from '@/utils/queryKeys';

// category_id/payment_account_id need live ExpenseCategory/PaymentAccount rows
// for both their column display and their drawer <select> options — a plain
// exported object can't call a hook. RecurringExpenseList.jsx injects both at
// render time, the same split PaymentAccountCrudConfig.jsx/
// PaymentAccountList.jsx already established for payment_method_id.
export const recurringExpenseTemplateCrudConfig = {
  queryKey: recurringExpenseTemplateKeys,
  useList: useRecurringExpenseTemplates,
  useCreate: useCreateRecurringExpenseTemplate,
  useUpdate: useUpdateRecurringExpenseTemplate,
  useDelete: useDeleteRecurringExpenseTemplate,
  columns: [
    { key: 'name', label: 'Name' },
    { key: 'category_id', label: 'Category' },
    { key: 'payment_account_id', label: 'Account' },
    { key: 'amount', label: 'Amount' },
    { key: 'day_of_month', label: 'Day of month' },
    { key: 'description', label: 'Description' },
  ],
  createSchema: recurringExpenseTemplateCreateSchema,
  updateSchema: recurringExpenseTemplateUpdateSchema,
  fields: [
    { name: 'name', label: 'Name', component: 'text' },
    { name: 'category_id', label: 'Category', component: 'select', options: [] },
    { name: 'payment_account_id', label: 'Payment account', component: 'select', options: [] },
    { name: 'amount', label: 'Amount', component: 'number', step: '0.01' },
    // Informational only — nothing server-side or client-side uses this to
    // auto-trigger generation.
    { name: 'day_of_month', label: 'Day of month (informational only)', component: 'number' },
    { name: 'description', label: 'Description', component: 'text' },
  ],
};
