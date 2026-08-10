import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Button } from '@/components/ui/button';
import { FormField, FormSelect } from '@/components/custom';
import { expenseCreateSchema } from '@/validations/expensesSchemas';
import { useCreateExpense } from '@/hooks/expensesHooks/expensesMutations';
import { useExpenseCategories } from '@/hooks/expensesHooks/expensesQueries';
import { usePaymentAccounts } from '@/hooks/paymentsHooks/paymentsQueries';

const LOOKUP_PAGE = { page: 1, page_size: 100 };
const todayIso = () => new Date().toISOString().slice(0, 10);

export function ExpenseForm({ onSuccess }) {
  const { data: categoriesData } = useExpenseCategories(LOOKUP_PAGE);
  const { data: accountsData } = usePaymentAccounts(LOOKUP_PAGE);
  const categoryOptions = (categoriesData?.items ?? []).map((c) => ({ value: String(c.id), label: c.name }));
  const accountOptions = (accountsData?.items ?? []).map((a) => ({ value: String(a.id), label: a.label }));

  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(expenseCreateSchema, {}, { raw: true }),
    defaultValues: { category_id: '', payment_account_id: '', amount: '', expense_date: todayIso(), description: '' },
  });
  const createMutation = useCreateExpense();

  const onSubmit = async (values) => {
    try {
      // Omit an unset optional description entirely rather than sending '' —
      // same shape PaymentForm.onSubmit/PurchaseOrderForm.onSubmit already use.
      const payload = {
        category_id: values.category_id,
        payment_account_id: values.payment_account_id,
        amount: values.amount,
        expense_date: values.expense_date,
        ...(values.description ? { description: values.description } : {}),
      };
      await createMutation.mutateAsync(payload);
      onSuccess?.();
    } catch {
      // fetchClient already toasted the backend's error detail — keep the
      // form open so the user can fix (e.g. an inactive account) and retry.
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <Controller
        name="category_id"
        control={control}
        render={({ field }) => (
          <FormSelect {...field} label="Category" placeholder="Select a category" options={categoryOptions} error={errors.category_id?.message} />
        )}
      />
      <Controller
        name="payment_account_id"
        control={control}
        render={({ field }) => (
          <FormSelect {...field} label="Paid from" placeholder="Select an account" options={accountOptions} error={errors.payment_account_id?.message} />
        )}
      />
      <Controller
        name="amount"
        control={control}
        render={({ field }) => <FormField {...field} type="number" step="0.01" label="Amount" error={errors.amount?.message} />}
      />
      <Controller
        name="expense_date"
        control={control}
        render={({ field }) => <FormField {...field} type="date" label="Date" error={errors.expense_date?.message} />}
      />
      <Controller
        name="description"
        control={control}
        render={({ field }) => <FormField {...field} label="Description (optional)" error={errors.description?.message} />}
      />
      <Button type="submit" size="lg" disabled={isSubmitting} className="self-end">
        {isSubmitting ? 'Saving…' : 'Record expense'}
      </Button>
    </form>
  );
}
