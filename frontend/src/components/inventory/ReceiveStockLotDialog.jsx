import { useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { FormField } from '@/components/custom';
import { stockLotReceiveSchema } from '@/validations/inventorySchemas';
import { useReceiveStockLot } from '@/hooks/inventoryHooks/inventoryMutations';

const todayIso = () => new Date().toISOString().slice(0, 10);

export function ReceiveStockLotDialog({ open, onOpenChange, line, itemLabel }) {
  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(stockLotReceiveSchema, {}, { raw: true }),
    defaultValues: { received_date: todayIso() },
  });
  const receiveMutation = useReceiveStockLot();

  useEffect(() => {
    if (open) reset({ received_date: todayIso() });
  }, [open, reset]);

  const onSubmit = async (values) => {
    try {
      await receiveMutation.mutateAsync({ purchase_order_line_id: line.id, received_date: values.received_date });
      onOpenChange(false);
    } catch {
      // fetchClient already toasted the backend's error detail (not yet allocated,
      // or already received by a second tab) — keep the dialog open so the user can
      // see it and cancel or retry.
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Receive into stock</DialogTitle>
          <DialogDescription>
            {itemLabel} · qty {line.qty} — creates one stock lot for the full line quantity at its landed cost.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <Controller
            name="received_date"
            control={control}
            render={({ field }) => (
              <FormField {...field} type="date" label="Received date" error={errors.received_date?.message} />
            )}
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Receiving…' : 'Receive'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
