import { object, string, number, array } from 'yup';

export const salesOrderLineSchema = object({
  item_id: number().typeError('Select an item').required('Select an item'),
  qty: number().typeError('Quantity must be a number').positive('Quantity must be positive').required('Quantity is required'),
  rate_pkr: number().typeError('Rate must be a number').positive('Rate must be positive').required('Rate is required'),
});

export const salesOrderCreateSchema = object({
  party_id: number().typeError('Select a customer').required('Select a customer'),
  order_date: string().required('Order date is required'),
  lines: array()
    .of(salesOrderLineSchema)
    .min(1, 'Add at least one line')
    // Mirrors the backend's own rule verbatim (backend spec §2.3) — a pure function
    // of this form's own values, safe to enforce client-side unlike a live-stock bound.
    .test(
      'unique-items',
      'Each item may appear at most once per sales order — increase its qty instead',
      (lines) => {
        if (!lines) return true;
        const ids = lines.map((line) => line.item_id).filter((id) => id !== undefined && id !== '');
        return new Set(ids).size === ids.length;
      },
    ),
});
