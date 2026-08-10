import { useExpenseCategories } from '@/hooks/expensesHooks/expensesQueries';
import {
  useCreateExpenseCategory,
  useUpdateExpenseCategory,
  useDeleteExpenseCategory,
} from '@/hooks/expensesHooks/expensesMutations';
import { expenseCategoryCreateSchema, expenseCategoryUpdateSchema } from '@/validations/expensesSchemas';
import { expenseCategoryKeys } from '@/utils/queryKeys';
import { EXPENSE_CATEGORY_FREQUENCY_OPTIONS } from '@/utils/constants';

function frequencyLabel(value) {
  return EXPENSE_CATEGORY_FREQUENCY_OPTIONS.find((option) => option.value === value)?.label ?? value;
}

export const expenseCategoryCrudConfig = {
  queryKey: expenseCategoryKeys,
  useList: useExpenseCategories,
  useCreate: useCreateExpenseCategory,
  useUpdate: useUpdateExpenseCategory,
  useDelete: useDeleteExpenseCategory,
  columns: [
    { key: 'name', label: 'Name' },
    { key: 'frequency', label: 'Frequency', render: (row) => frequencyLabel(row.frequency) },
  ],
  createSchema: expenseCategoryCreateSchema,
  updateSchema: expenseCategoryUpdateSchema,
  fields: [
    { name: 'name', label: 'Name', component: 'text' },
    { name: 'frequency', label: 'Frequency', component: 'select', options: EXPENSE_CATEGORY_FREQUENCY_OPTIONS },
  ],
};
