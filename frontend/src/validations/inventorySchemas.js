import { object, string, number } from 'yup';

export const stockLotReceiveSchema = object({
  received_date: string().required('Received date is required'),
});

// A factory, not a static schema — the valid qty_delta range depends on the specific
// lot's qty_remaining/qty_received, which StockAdjustmentForm already has as a prop
// (unlike CargoShipmentForm's basis-value rule, which needed a value from a query
// cache the form couldn't see — phase-2-frontend spec §2 decision 6 — this rule has
// everything it needs right on the component, so it's expressed as Yup, not a
// computed disabled boolean).
export function buildStockAdjustmentSchema(lot) {
  return object({
    qty_delta: number()
      .typeError('Enter a number')
      .required('Enter a quantity change')
      .notOneOf([0], 'Adjustment quantity must be non-zero')
      .test('within-bounds', `Resulting quantity must stay between 0 and ${lot.qty_received}`, (value) => {
        if (value == null) return true; // required() already reports the empty case
        const resultingQty = Number(lot.qty_remaining) + value;
        return resultingQty >= 0 && resultingQty <= Number(lot.qty_received);
      }),
    reason: string().required('Reason is required').max(255, 'Max 255 characters'),
    movement_date: string().required('Movement date is required'),
  });
}
