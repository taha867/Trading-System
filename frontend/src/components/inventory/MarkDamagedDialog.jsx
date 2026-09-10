import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { MarkDamagedForm } from '@/components/inventory/form/MarkDamagedForm';

export function MarkDamagedDialog({ open, onOpenChange, lot }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Mark stock lot #{lot.id} as damaged</DialogTitle>
          <DialogDescription>
            Removes this quantity from sellable stock and lists it on the Damaged Stock page — currently{' '}
            {lot.qty_remaining} of {lot.qty_received} remaining.
          </DialogDescription>
        </DialogHeader>
        <MarkDamagedForm lot={lot} onSuccess={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}
