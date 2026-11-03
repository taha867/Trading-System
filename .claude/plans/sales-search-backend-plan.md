# Sales Search & Full Detail — Backend Plan

Implements `.claude/specs/sales-search-and-full-detail.md` (backend, `backend/src`). Read the spec's "Implementation notes" for deviations.

## Decisions
- Filters use `Annotated[PaginationParams, Depends()]` + scalar query params (like `inventory/router.py::list_stock_lots`); FastAPI 0.141 can't flatten a Query model next to other params. Date-range errors raise `InvalidSalesFilter` (422) from the service.
- Reuse `ledger/schemas.py::LedgerEntryRead`.
- `parties/` never imports `sales/`: invoice numbers for the customer statement come from a sales-owned batched endpoint `GET /sales/sales-orders/invoice-numbers?ids=`.
- Totals cover whole matching sales (an item filter means "sales containing this item").

## Steps
1. `sales/constants.py` (new): `SalesLogExceptionKind`.
2. `sales/exceptions.py`: `InvalidSalesFilter` (422).
3. `sales/utils.py`: `escape_like`.
4. `sales/models.py`: relationships (`SalesOrder.party`, `SalesOrderLineLot.stock_lot`, `SalesLogException.party`, all `lazy="raise"`), read-only properties, `index=True` on `order_date`, `invoice_number`, `sales_log_exception.entry_date`, `party_id`.
5. `sales/dependencies.py`: extend `SALES_ORDER_LOAD_OPTIONS` (party, stock lot).
6. `sales/schemas.py`: `party_name`, `lot_received_date`, `SalesOrderListRead`, `SalesOrderDetailRead`, `InvoiceNumberRead`, `SalesLogException*`; blank invoice number → `None`.
7. `sales/service.py`: `_order_filter_clauses`, filtered `list_sales_orders` with whole-set totals, `get_sales_order_detail`, `get_invoice_numbers`, `list_sales_log_exceptions`.
8. `sales/router.py`: two sub-routers combined like `inventory/router.py`; `/invoice-numbers` declared before `/{id}`.
9. Migration `…_add_sales_search_indexes.py` (`down_revision = 'd1e54e52c664'`): four indexes, no data change.

## Verification
Compile and import; OpenAPI shows the new params and routes; compiled SQL eyeballed; with the dev database (read-only service-level script, only with the owner's OK): search, month, party, item, combined filters, totals across pages, detail ledger row.
