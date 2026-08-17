import { useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { FormField, FormSelect, FormCombobox } from '@/components/custom';
import { paymentTransactionCreateSchema } from '@/validations/paymentsSchemas';
import { useCreatePaymentTransaction } from '@/hooks/paymentsHooks/paymentsMutations';
import { usePaymentAccounts } from '@/hooks/paymentsHooks/paymentsQueries';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { useSalesOrders } from '@/hooks/salesHooks/salesQueries';
import { usePurchaseOrders } from '@/hooks/purchasingHooks/purchasingQueries';
import {
  PAYMENT_DIRECTION,
  PAYMENT_DIRECTION_OPTIONS,
  PAYMENT_REFERENCE_TYPE,
  PAYMENT_REFERENCE_TYPE_OPTIONS,
} from '@/utils/constants';
import { LOOKUP_PAGE } from '@/utils/queryParams';

const todayIso = () => new Date().toISOString().slice(0, 10);

export function PaymentForm({ onSuccess }) {
  const [hasReference, setHasReference] = useState(false);

  const { data: accountsData } = usePaymentAccounts(LOOKUP_PAGE);
  const { data: partiesData } = useParties(LOOKUP_PAGE);
  const { data: salesOrdersData } = useSalesOrders(LOOKUP_PAGE);
  const { data: purchaseOrdersData } = usePurchaseOrders(LOOKUP_PAGE);

  const partyNameById = Object.fromEntries((partiesData?.items ?? []).map((p) => [p.id, p.name]));
  const accountOptions = (accountsData?.items ?? []).map((a) => ({ value: String(a.id), label: a.label }));
  const partyOptions = (partiesData?.items ?? []).map((p) => ({ value: String(p.id), label: p.name }));

  const {
    control,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(paymentTransactionCreateSchema, {}, { raw: true }),
    defaultValues: {
      payment_account_id: '',
      direction: PAYMENT_DIRECTION.IN,
      amount: '',
      transaction_date: todayIso(),
      party_id: '',
      reference_type: '',
      reference_id: '',
      note: '',
    },
  });
  const createMutation = useCreatePaymentTransaction();
  const referenceType = watch('reference_type');

  // Same "fetch page_size=100, no backend search" posture as
  // useDraftPurchaseOrders/useExchangeRateForDate — neither list endpoint supports
  // search, and a solo-trading-system's order volume makes one page a fair trade.
  const referenceOptions = (
    referenceType === PAYMENT_REFERENCE_TYPE.SALES_ORDER
      ? (salesOrdersData?.items ?? [])
      : referenceType === PAYMENT_REFERENCE_TYPE.PURCHASE_ORDER
        ? (purchaseOrdersData?.items ?? [])
        : []
  ).map((order) => ({
    value: String(order.id),
    label: `#${order.id} — ${order.order_date} — ${partyNameById[order.party_id] ?? `Party #${order.party_id}`}`,
  }));

  const toggleReference = (checked) => {
    setHasReference(checked);
    if (!checked) {
      setValue('reference_type', '');
      setValue('reference_id', '');
    }
  };

  const onSubmit = async (values) => {
    try {
      // Omit unset optional fields entirely rather than sending null/'' — the
      // same shape PurchaseOrderForm.onSubmit uses for its conditional rate field.
      const payload = {
        payment_account_id: values.payment_account_id,
        direction: values.direction,
        amount: values.amount,
        transaction_date: values.transaction_date,
        ...(values.party_id ? { party_id: values.party_id } : {}),
        ...(values.reference_type && values.reference_id
          ? { reference_type: values.reference_type, reference_id: values.reference_id }
          : {}),
        ...(values.note ? { note: values.note } : {}),
      };
      await createMutation.mutateAsync(payload);
      onSuccess?.();
    } catch {
      // fetchClient already toasted the backend's error detail — keep the form
      // open so the user can fix (e.g. an inactive account/party) and retry.
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <div className="flex flex-col gap-4">
        <Controller
          name="direction"
          control={control}
          render={({ field }) => (
            <FormSelect {...field} label="Direction" options={PAYMENT_DIRECTION_OPTIONS} error={errors.direction?.message} />
          )}
        />
        <Controller
          name="payment_account_id"
          control={control}
          render={({ field }) => (
            <FormSelect
              {...field}
              label="Account"
              placeholder="Select an account"
              options={accountOptions}
              error={errors.payment_account_id?.message}
            />
          )}
        />
        <Controller
          name="amount"
          control={control}
          render={({ field }) => (
            <FormField {...field} type="number" step="0.01" label="Amount" error={errors.amount?.message} />
          )}
        />
        <Controller
          name="transaction_date"
          control={control}
          render={({ field }) => (
            <FormField {...field} type="date" label="Date" error={errors.transaction_date?.message} />
          )}
        />
        <Controller
          name="party_id"
          control={control}
          render={({ field }) => (
            <FormSelect
              {...field}
              label="Party (optional)"
              placeholder="No party linked"
              options={partyOptions}
              error={errors.party_id?.message}
            />
          )}
        />
        <Controller
          name="note"
          control={control}
          render={({ field }) => <FormField {...field} label="Note (optional)" error={errors.note?.message} />}
        />
      </div>

      <div className="flex flex-col gap-3 rounded-lg border p-3">
        <label className="flex items-center gap-2 text-sm font-medium">
          <Checkbox checked={hasReference} onCheckedChange={toggleReference} />
          Link to a sales order or purchase order
        </label>
        {hasReference && (
          <div className="flex flex-col gap-3">
            <Controller
              name="reference_type"
              control={control}
              render={({ field }) => (
                <FormSelect
                  {...field}
                  label="Document type"
                  placeholder="Select a type"
                  options={PAYMENT_REFERENCE_TYPE_OPTIONS}
                  error={errors.reference_type?.message}
                />
              )}
            />
            <Controller
              name="reference_id"
              control={control}
              render={({ field }) => (
                <FormCombobox
                  {...field}
                  label="Document"
                  placeholder={referenceType ? 'Select a document' : 'Pick a type first'}
                  searchPlaceholder="Search by id or party…"
                  options={referenceOptions}
                  disabled={!referenceType}
                  error={errors.reference_id?.message}
                />
              )}
            />
          </div>
        )}
      </div>

      <Button type="submit" size="lg" disabled={isSubmitting} className="self-end">
        {isSubmitting ? 'Recording…' : 'Record payment'}
      </Button>
    </form>
  );
}
