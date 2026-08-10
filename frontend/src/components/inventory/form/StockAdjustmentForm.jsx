import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { DialogFooter, DialogClose } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { FormField } from '@/components/custom';
import { buildStockAdjustmentSchema } from '@/validations/inventorySchemas';
import { useCreateStockMovement } from '@/hooks/inventoryHooks/inventoryMutations';

const todayIso = () => new Date().toISOString().slice(0, 10);

export function StockAdjustmentForm({ lot, onSuccess }) {
  const schema = buildStockAdjustmentSchema(lot);
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(schema, {}, { raw: true }),
    defaultValues: { qty_delta: '', reason: '', movement_date: todayIso() },
  });
  const createMutation = useCreateStockMovement();

  const onSubmit = async (values) => {
    try {
      await createMutation.mutateAsync({ stock_lot_id: lot.id, ...values });
      onSuccess?.();
    } catch {
      // fetchClient already toasted the backend's error detail (out-of-range
      // adjustment) — keep the form open to fix and retry.
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <Controller
        name="qty_delta"
        control={control}
        render={({ field }) => (
          <FormField
            {...field}
            type="number"
            step="0.01"
            label="Quantity change"
            placeholder="e.g. -2 for damage, +3 for a recount"
            error={errors.qty_delta?.message}
          />
        )}
      />
      <Controller
        name="reason"
        control={control}
        render={({ field }) => (
          <FormField {...field} label="Reason" placeholder="Damaged in storage, recount, …" error={errors.reason?.message} />
        )}
      />
      <Controller
        name="movement_date"
        control={control}
        render={({ field }) => (
          <FormField {...field} type="date" label="Movement date" error={errors.movement_date?.message} />
        )}
      />
      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline">
            Cancel
          </Button>
        </DialogClose>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Saving…' : 'Save adjustment'}
        </Button>
      </DialogFooter>
    </form>
  );
}
