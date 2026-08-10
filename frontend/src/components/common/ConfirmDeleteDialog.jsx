import { ConfirmDialog } from '@/components/common/ConfirmDialog';

export function ConfirmDeleteDialog({ open, onOpenChange, onConfirm, isPending, itemLabel }) {
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      onConfirm={onConfirm}
      isPending={isPending}
      title={`Delete ${itemLabel ?? 'this record'}?`}
      description="This soft-deletes the record — it disappears from the list but isn't permanently removed."
      confirmLabel="Delete"
      pendingLabel="Deleting…"
      confirmVariant="destructive"
    />
  );
}
