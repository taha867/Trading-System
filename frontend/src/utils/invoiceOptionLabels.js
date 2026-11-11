// How the invoice dropdown describes one invoice number, per screen. One number can cover several
// documents (numbers aren't unique), so say so rather than hide it.

// An invoice is a sale plus any day-book entries (no stock found, bulk, correction, cancelled...) with its number;
// an invoice that is only entries has no sale at all, so say how many entries it holds.
export function salesInvoiceOptionLabel({ invoice_number: number, sale_count: sales, entry_count: entries }) {
  const notes = [];
  if (sales > 1) notes.push(`${sales} sales`);
  if (entries > 0) notes.push(`${entries} ${entries === 1 ? 'entry' : 'entries'}`);
  return notes.length ? `${number} (${notes.join(', ')})` : number;
}

export function purchaseInvoiceOptionLabel({ invoice_number: number, order_count: orders }) {
  return orders > 1 ? `${number} (${orders} orders)` : number;
}

// "Other entries" lists (day-book lines that aren't real orders): a sale and its correction or discount can
// share one invoice number, so say how many entries carry it.
export function logExceptionInvoiceOptionLabel({ invoice_number: number, entry_count: entries }) {
  return entries > 1 ? `${number} (${entries} entries)` : number;
}
