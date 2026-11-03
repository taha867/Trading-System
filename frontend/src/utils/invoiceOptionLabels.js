// How the invoice dropdown describes one invoice number, per screen. One number can cover several
// documents (numbers aren't unique), so say so rather than hide it.

// A cancelled sales invoice has no sale at all — only a day-book entry — so it is called out too.
export function salesInvoiceOptionLabel({ invoice_number: number, sale_count: sales, cancelled_count: cancelled }) {
  const notes = [];
  if (sales > 1) notes.push(`${sales} sales`);
  if (cancelled > 0) notes.push(sales > 0 ? `${cancelled} cancelled` : 'cancelled');
  return notes.length ? `${number} (${notes.join(', ')})` : number;
}

export function purchaseInvoiceOptionLabel({ invoice_number: number, order_count: orders }) {
  return orders > 1 ? `${number} (${orders} orders)` : number;
}
