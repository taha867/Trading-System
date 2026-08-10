import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { StockAdjustmentForm } from '@/components/inventory/form/StockAdjustmentForm';

export function StockAdjustmentDialog({ open, onOpenChange, lot }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Adjust stock lot #{lot.id}</DialogTitle>
          <DialogDescription>
            Recount, damage, or loss — currently {lot.qty_remaining} of {lot.qty_received} remaining.
          </DialogDescription>
        </DialogHeader>
        <StockAdjustmentForm lot={lot} onSuccess={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}
