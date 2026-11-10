# Production changes log

Every change made directly to the production database (Neon), outside the normal app flow. Newest last.
Scripts live in `backend/scripts/` (imports) and `backend/scripts/oneoff/` (small fixes). All of them take the
connection string from the `PROD_DSN` environment variable; none contains a credential.

| # | When (2026) | What | Rows | Script |
|---|-------------|------|------|--------|
| 1 | Oct | Migration `a3c7f1d95b28` - search indexes for sales | indexes only | `migrations/versions/2026-10-22_add_sales_search_indexes.py` |
| 2 | Oct | September day-book import, stages 1, 2a, 2b, 2-combined (cash sales, credit sale, exceptions, local purchases) | see `SEPTEMBER_2026_IMPORT_AUDIT.md` | `import_daybook_sept2026_stage*.py` (now guarded: `--apply` needs `--i-understand-this-already-ran-in-production`) |
| 3 | Nov | Cancelled-invoice notes added | `sales_log_exception` ids 1, 2, 19, 20, 21, 23, 25, 26 (sheet rows 5, 6, 66, 92, 104, 233, 288, 351) | `oneoff/2026_11_04_add_cancelled_invoice_notes.py` |
| 4 | Nov | Two cash receipts moved from "Unspecified (to be decided)" to "Cash drawer" | `payment_transaction` 165 (Rs 4,200), 173 (Rs 150); `ledger_entry` 1234, 1250 | `oneoff/2026_11_04_move_cash_receipts_to_cash_drawer.py` |
| 5 | Nov | Stage 3 import - 56 missing local purchases | see `SEPTEMBER_2026_MISSING_PURCHASES_DRYRUN.md` | `import_daybook_sept2026_stage3_missing_purchases.py` |
| 6 | Nov | Cleared supplier invoice numbers copied onto 10 resale sales (`541` x9, `5` x1) | `sales_order` 26, 45-52, and one Dream Mobile sale | `oneoff/2026_11_04_clear_resale_sale_invoice_numbers.py` |
| 7 | Nov | Cleared carried-down invoice numbers on 21 purchase orders (488, 506, 518, 532, 541) | `purchase_order` 36-40, 45, 47, 49, 51-55, 104-108, 120-122 | `oneoff/2026_11_04_clear_carried_down_po_invoices.py` |
| 8 | Nov | Migration `c4e81b7a2d95` - purchase search indexes and `purchase_log_exception` table | table + indexes | `migrations/versions/2026-11-04_add_purchase_search_indexes_and_log_exception.py` |

## Not yet applied

- `backend/scripts/backfill_purchase_log_exceptions.py` - plan matches exactly 17 entries / Rs 119,875. Run `--rehearse`, then `--apply`.

## Known open item

- Purchase order #14 (Mohsin, 2026-09-08): ledger payable Rs 174,492.10 vs lines Rs 140,811.90, difference Rs 33,680.20. It comes from the earlier Mohsin import, not from the changes above. Needs an owner decision before correcting.

## Verification habit

Each script runs in one transaction, asserts the exact rows and current values first, defaults to a dry run
(rolled back), and checks the result before committing. Re-running an applied script is harmless: its assertions
fail and nothing is written.
