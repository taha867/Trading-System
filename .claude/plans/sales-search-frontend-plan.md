# Sales Search & Full Detail — Frontend Plan

Implements `.claude/specs/sales-search-and-full-detail.md` (frontend, `frontend/src`). Use the `frontend-design-system` skill.

## Steps
1. `utils/dateUtils.js`: `formatDateTime`. `utils/constants.js`: `SALES_LOG_EXCEPTION_KIND_LABELS`.
2. `utils/queryKeys.js`: `salesLogExceptionKeys`, `salesOrderKeys.invoiceNumbers`.
3. `services/salesService.js` and `hooks/salesHooks/salesQueries.js`: `listSalesLogExceptions`, `getInvoiceNumbers`, matching hooks; list hooks use `keepPreviousData`.
4. `validations/salesSchemas.js`: optional `invoice_number` (max 64).
5. `SalesOrderForm.jsx`: optional invoice number field plus a non-blocking duplicate hint (reuse `useDebouncedValue`).
6. `SalesOrderList.jsx`: URL-backed filters (search, customer, month, item), clear button, whole-set summary bar, new columns (Invoice no., customer name, entered on, margin %), stacked cards below `sm`.
7. `SalesOrderDetail.jsx`: header details, lot received dates, "Posted to ledger" card.
8. `SalesLogExceptionList.jsx` (new) and `SalesOrdersContainer.jsx` tabs ("Invoices" / "Other entries", tab in the URL).
9. `PartyStatement.jsx`: `Sale #id · Invoice N` link via `useInvoiceNumbers`.
10. `ProfitLossStatement.jsx`: "View these entries" link for unitemised sales.

## Verification
`npm run lint`, `npm run build`; check 375 / 768 / 1280 px; filters persist in the URL; summary equals the Reports page for the same month; create a sale with and without an invoice number.
