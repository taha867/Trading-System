import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { DialogFooter, DialogClose } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { FormField } from '@/components/custom';
import { buildStockDamageSchema } from '@/validations/inventorySchemas';
import { useMarkStockLotDamaged } from '@/hooks/inventoryHooks/inventoryMutations';

const todayIso = () => new Date().toISOString().slice(0, 10);

export function MarkDamagedForm({ lot, onSuccess }) {
  const schema = buildStockDamageSchema(lot);
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(schema, {}, { raw: true }),
    defaultValues: { qty: '', reason: '', movement_date: todayIso() },
  });
  const markDamagedMutation = useMarkStockLotDamaged();

  const onSubmit = async (values) => {
    try {
      await markDamagedMutation.mutateAsync({ stock_lot_id: lot.id, ...values });
      onSuccess?.();
    } catch {
      // fetchClient already toasted the backend's error detail (e.g. qty exceeding
      // what's remaining) — keep the form open to fix and retry.
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <Controller
        name="qty"
        control={control}
        render={({ field }) => (
          <FormField {...field} type="number" step="0.01" label="Quantity damaged" error={errors.qty?.message} />
        )}
      />
      <Controller
        name="reason"
        control={control}
        render={({ field }) => (
          <FormField {...field} label="Reason" placeholder="Turned yellow, cracked in storage, …" error={errors.reason?.message} />
        )}
      />
      <Controller
        name="movement_date"
        control={control}
        render={({ field }) => (
          <FormField {...field} type="date" label="Date" error={errors.movement_date?.message} />
        )}
      />
      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline">
            Cancel
          </Button>
        </DialogClose>
        <Button type="submit" variant="destructive" disabled={isSubmitting}>
          {isSubmitting ? 'Saving…' : 'Mark as damaged'}
        </Button>
      </DialogFooter>
    </form>
  );
}
