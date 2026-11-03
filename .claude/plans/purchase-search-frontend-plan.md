# Purchase Orders — Frontend Plan (port of the Sales Orders work)

All changes under `frontend/src/`. Use the `frontend-design-system` skill for visuals.

## Steps
1. Generalize `InvoiceCombobox` into `components/common/` (props `useOptions`, `optionLabel`); sales uses it unchanged.
2. `utils/constants.js`: `PURCHASE_ORDER_STATUS` + labels/options/badges. `utils/queryKeys.js`: invoice keys, `purchaseLogExceptionKeys`.
3. `services/purchasingService.js` and `hooks/purchasingHooks/purchasingQueries.js`: invoice options/numbers, log exceptions; `usePurchaseOrders(params, { enabled, keepPrevious })` (opt-in). `partyHooks`: `useVendorParties`.
4. `PurchaseOrderList.jsx`: URL-backed filters (Invoice, Vendor, Source, Status, Month, Item), summary bar, new columns (Invoice no., Entered on), vendor name from the API, mobile cards.
5. `PurchaseLogExceptionList.jsx` + `PurchaseOrdersContainer.jsx` tabs ("Orders" / "Other entries").
6. `PurchaseOrderDetail.jsx`: details grid, per-line stock and cargo cell, "Received" from line lot data (replaces `useReceivedLineIds`), ledger card, vendor statement link.
7. `PurchaseOrderForm.jsx` + `purchasingSchemas.js`: optional invoice number with duplicate hint.
8. `PartyStatement.jsx`: purchase-order rows link with invoice number; payable-only entries labelled.
9. Remove `useReceivedLineIds` once unused.

## Verification
`npm run lint`, `npm run build`; check 375 / 768 / 1280 px; cargo draft-PO picker and payment reference picker still work.
