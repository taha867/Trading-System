# Purchase Orders — Backend Plan (port of the Sales Orders work)

All changes in `backend/src/purchasing/` unless noted. Mirrors `backend/src/sales/*`.

## Decisions
- Default order newest first (`order_date desc, id desc`); filters add **source** and **status**.
- Other entries: new `purchase_log_exception` table; the 17 existing payable-only ledger entries are backfilled by a **separate guarded production step** shown to the owner first.
- Detail reads `StockLot` and `CargoAllocation` with batched service-level queries (no model relationships, avoids import cycles).

## Steps
1. `constants.py`: `MAX_INVOICE_NUMBER_LOOKUP_IDS`, `MAX_INVOICE_OPTIONS`, `PurchaseLogExceptionKind`.
2. `exceptions.py`: `InvalidPurchaseFilter` (422). `utils.py`: `escape_like`.
3. `models.py`: `PurchaseOrder.party` + `party_name`, indexes on `order_date` and `invoice_number`; new `PurchaseLogException`.
4. `dependencies.py`: `joinedload(PurchaseOrder.party)` in the load options.
5. `schemas.py`: blank invoice -> `None`; `PurchaseOrderRead` += `party_name`, `created_at`; `PurchaseOrderListRead` (totals); line and order detail schemas; invoice number/option schemas; `PurchaseLogException*`.
6. `service.py`: filter clauses, filtered list with whole-set totals, detail (ledger + lot + cargo), invoice numbers/options, log-exception list.
7. `router.py`: `Depends()` pagination + scalar filters, `/invoice-options` and `/invoice-numbers` before `/{id}`, detail response, `/purchase-log-exceptions`.
8. Migration `2026-11-04_add_purchase_search_indexes_and_log_exception.py` (`down_revision = a3c7f1d95b28`).
9. Stage 3 script also writes the log row; new guarded `backfill_purchase_log_exceptions.py` (plan / `--rehearse` / `--apply`).

## Verification
Compile + import + mappers + OpenAPI; compiled SQL checked; read-only service checks against production; migration and backfill only with the owner's OK.
