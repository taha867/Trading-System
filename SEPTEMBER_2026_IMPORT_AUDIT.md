# September 2026 Day Book Import — Audit Notes

> **Status (2026-11-10): partly out of date.** Written before the Stage 3 import and the invoice clean-ups. Since then: local purchases are 63 POs / ₨853,935 (§1); the 231 `insufficient_stock` lines in §6 are probably explained by the purchases that were missing, and are still not replayed; 9 more resales exist (§7); only ₨2,080 of Dream Mobile's ₨3,580 A.Power resale is booked (§8). The supplier invoice numbers carried down onto the wrong rows were cleared. See `PRODUCTION_CHANGES_LOG.md`.

Source file: `Daily Cash Book (Sept 2026).xlsx` (Expenses, Credit Sale, Local Purchase,
Received Amount sheets), filtered strictly to Ledger Date within September 2026 — the
file also contains October rows, out of scope for this import.

Scripts (in order applied), all under `backend/scripts/`:
1. `import_daybook_sept2026_stage1.py` — Expenses + Received Amount
2. `import_daybook_sept2026_stage2a_exceptions.py` — Credit Sale rows with no real item
   (cancelled invoices, bulk/mixed-model batches, corrections/discounts)
3. `import_daybook_sept2026_stage2_combined.py` — Local Purchase + the remaining Credit
   Sale rows with a real item, processed together in chronological order

This document exists so a later audit of the data knows exactly what was assumed,
guessed, or deliberately simplified — not to re-justify the decisions, just to make
every loophole findable.

---

## 1. Final totals (verified against the source sheet)

| | Rows | Amount (PKR) |
|---|---|---|
| Expenses | 131 | 6,352,404 |
| Received Amount | 43 | 4,622,615 |
| Credit Sale — real `SalesOrderLine` | 228 lines | 444,991 |
| Credit Sale — logged exceptions (no real item/stock) | 33 entries | 697,586 |
| Local Purchase — real `PurchaseOrderLine` | 23 lines | 316,220 |
| Local Purchase — logged exception (A.Power Traders) | 1 entry | 1,500 |

Credit Sale reconciliation: 444,991 + 697,586 = **1,142,577** = sheet's own total for every
money-bearing Credit Sale row (1,142,127, every category including Correction/Discount,
excluding only the 8 genuinely-cancelled-invoice rows) **+** the one new "Sold To" resale
from Local Purchase row 77 (450). Verified exactly, twice, after finding and fixing two
false "duplicates" (see §6).

Local Purchase reconciliation: 316,220 + 1,500 = **317,720** = sheet's own total for all
23 real rows + the 1 exception row.

---

## 2. New parties created (none existed before this import)

| Name | Roles | Why |
|---|---|---|
| Cash (Walk-in / Anonymous) | customer | Catch-all for anonymous cash sales/receipts ("CASH invoice 14", "Mix", invoices #14 and #24's item-level detail) — confirmed by the user these are real walk-in sales, not a single tracked party. |
| Abdullah Mobile, Mandi Bhaudeen | customer | New, no existing match |
| Hasan Man, Sheikhupura | customer | New, no existing match |
| Server Goraya | customer | A recurring cheque-paying contact ("Cashed/recived check from server goraya (Factory)") — confirmed as its own party, not cash/anonymous |
| Mobile Store, Khanewal | customer | New |
| Naveed Mobile, Chowk Azam | customer | New |
| Noman Mobile, Multan | customer | Merges "Noman"/"Nouman" spelling variants |
| Shoaib Mobile, Jhang | customer | Already correctly identified in the sheet's own Customer Ledger tab as the real name for "Habib Mobile Jhang" (a misspelling) — but was never actually added when the other 22 opening balances were imported. Added now. |
| Punjab Kamal Industries | customer | New — note the sheet's own text next to it ("shakeel Dues from shop") hints this might actually be a payable relationship rather than a receivable one. **Not independently verified — worth checking.** |
| S&A | customer + local_vendor | Both buys from and sells to the business — genuinely dual-role, matches the `Party` model's design intent |
| AlNafeh Traders | local_vendor | New |
| Javed Traders | local_vendor | New |
| NS Traders | local_vendor | New |
| Galaxy Mobile, Kamran | local_vendor | New |
| AMT | local_vendor | New |
| A.Power Traders | local_vendor | New |

All opening balances set to 0 (no prior history for any of these before September).

## New ExpenseCategory

Only two, matching the sheet exactly (not the richer Rent/Fuel/Bills breakdown `PLAN.md`
originally envisioned) — explicitly requested by the user, to be replaced later once a
real categorization file is provided:
- **Personal** (80 expense rows)
- **Shop** (51 expense rows)

## New PaymentAccount

- **Unspecified (to be decided)** — used for every Expense row, since the Expenses sheet
  never records which account money came from at all. **Every one of the 131 imported
  expenses sits under this account** — none of them have a real bank/cash account
  assigned. This is probably the single biggest "needs real investigation" item in this
  whole import if account-level cash reconciliation matters.
- **Faysal Bank - main**, **Bank of Punjab - main** — added because the Received Amount
  sheet used both banks but only "Meezan Bank" had an account, and it was wired to the
  wrong *method* (see next section).

## Pre-existing data bug fixed (not part of this import, found while doing it)

`payment_account` #1 was labeled "Meezan Bank - main" but linked to `payment_method` #1,
which was itself named "Bank of punjab" — i.e. Meezan Bank and Bank of Punjab were
silently merged into one account before this session. Fixed: added a real "Meezan Bank"
method, repointed account #1 to it, gave Bank of Punjab its own new account.

---

## 3. Catalog resolution — how model names were matched

The sheet's Model column has two different formats:
- **Credit Sale**: `BRAND/MODEL[/MODEL...]` (e.g. `VIVO/Y15`, or
  `INFINIX/TECNO/HOT11S/CAMMON18` for a cross-brand compatible group — Hot 11S is really
  Infinix, Camon 18 is really Tecno, matched against the existing catalog per brand, not
  guessed positionally).
- **Local Purchase**: bare model names, no brand token at all (e.g. `iphone 12`, `Hot 10`,
  `y20`) — brand was inferred from the model name itself or by checking which brand
  already has that model in the real catalog.

**Known limitation**: the brand-matching logic (`BRAND_ALIASES` in the combined script)
only recognizes a fixed list of abbreviations (APPLE/IP → iPhone, SAM → Samsung, RMI/MI →
Redmi, RME → Realme, INF → Infinix, 1PLUS → OnePlus, HW → Huawei, PIXEL/GOOGLE → Google
Pixel). Any brand outside this list in future months' sheets will need the alias list
extended first, or every row using it will fail to resolve.

**Manual overrides** (couldn't be resolved automatically, resolved this session against
the "Ayan Compatible Models System" reference file and known product-line naming):

| Sheet text | Resolved to | Basis |
|---|---|---|
| `A16` | Samsung Galaxy A16 | Ayan reference |
| `s24 ultra` | Samsung Galaxy S24 Ultra | Ayan reference |
| `13 C` | Redmi 13C | Ayan reference |
| `R` (wherever it appears as a bare model) | iPhone XR | User's explicit confirmation |
| `PIXEL 9` | Google Pixel 9 | Ayan reference |
| `NEW` (OG category, qty 120) | Treated as an unknown-model bulk sale (same as "(Bulk, mixed models)") | User's explicit confirmation — "most probably sits inside bulk model list" |
| `NILL` | Same — unknown-model, no stock deduction | Same pattern as "NEW" |
| `A36/A56`, `SMART 9`/`HOT50I` vs `SPARKGO1`, `F15/V20/V21/V21E`, etc. | See script's `MANUAL_OVERRIDES` dict | Cross-brand compatible groups, resolved per-brand against the real catalog, not positionally |

**Variant/color picking**: a handful of models (mostly Jun Best Lens Protector and Simple
Lens Protector, where color genuinely is a separate stock item) have multiple `Item` rows
under one `Model` (e.g. iPhone 14 Pro Max in Gold/Black/Purple). Where the sheet gave a
trailing color token (`APPLE/IP14PROMAX/GOLDEN`), it was matched against the real
`Item.variant` values. **One case had no color given at all** — `iPhone 6+` sold with no
color specified — the user explicitly chose **White** (item #200) as the default; there
was no principled way to know which one was actually sold.

---

## 4. Three duplicate catalog entries found and merged

All had real stock on at least one side (not simple empty-vs-real cases like earlier
merges this session):

| Model | Kept | Merged away | Stock moved |
|---|---|---|---|
| Infinix "Note 50" | item #241 (50 pcs) | item #228 (0 pcs, no lot at all) | n/a |
| "IP 14 Pro" (Dust Plug) | item #898 "DPLUG-IPHONE14PRO" (35 pcs) | item #320 "DPLUG-IP14PRO" (28 pcs) | 28 pcs moved → #898 now has 63 |
| "IP 13 Pro Max" (Dust Plug) | item #323 "DPLUG-IP13PROMAX" (74 pcs, more stock) | item #899 "DPLUG-IPHONE13PROMAX" (50 pcs) | 50 pcs moved → #323 now has 124 |

The IP14Pro/IP13ProMax pair is the exact same "IP" vs "IPHONE" spelling inconsistency this
import's own matching script had to work around (see §3) — it was already present in the
catalog from an earlier session's import, not introduced here. **Worth checking the rest
of the catalog for the same pattern** — this was only caught because these two specific
models happened to be needed by September's data; others may exist unnoticed.

Rule used to decide which side to keep when both had real stock: the one with **more**
stock remaining. This is a reasonable default, not a verified-correct one — there was no
way to know which spelling was "more right" from the data alone.

---

## 5. Credit Sale rows with no real item (Stage 2a + combined script)

These post real money to the party ledger (so receivables/payables stay correct) but
**never touch stock** — logged in a new `sales_log_exception` table (`kind` column
distinguishes the reason), linked to its `ledger_entry` via `ledger_entry_id` when money
moved.

| Kind | Count | Total (PKR) | What it means |
|---|---|---|---|
| `cancelled_invoice` | 8 | 0 | Sheet said "invoice was cancelled" — kept only so the invoice-number sequence doesn't look like an unexplained gap |
| `bulk_mixed_models` | 13 | 113,430 | Sheet literally says "(Bulk, mixed models)", or "NEW"/"NILL" (per the user's confirmation that these mean the same thing) — a batch sale where which specific phone models were involved is genuinely unknown |
| `blank_model` | 7 | 39,946 | Category/qty/rate given, but no model at all — same as above, just a different way the sheet recorded "don't know which model" |
| `correction` | 3 | 3,950 | Sheet's own text says these are price corrections ("added by Ayan"), not real products |
| `discount` | 1 | -250 | A negative-amount discount line, matches a comment elsewhere about invoice #25's "Less 250" |
| `insufficient_stock` | **231** | **540,510** | See §6 — the big one |

**None of these have a specific `Item`/`StockLot` behind them.** If you ever want to know
"how many pieces of category X were sold without reducing recorded stock," `category_name`
and `qty` on these rows is where that lives.

---

## 6. The big one: 231 lines with no purchasing history (`insufficient_stock`)

**This is explicitly flagged by the user as needing root-cause investigation later — it
was applied as-is on their explicit instruction ("do this... i will find root cause later
then we can fix it"), not because the cause is understood.**

What was found: when Credit Sale rows are processed in true chronological order (so stock
from same-day Local Purchases is available before being sold — see §7), roughly half of
all September's real sale lines (231 of 458) need a model that has **zero recorded stock
at that point** — some needing as few as 2 units, one needing as many as 900 (iPhone XR).
Neither the 23 real Local Purchase rows nor the ~30 pre-existing "Mohsin" partnership
stock-handover purchase orders (dated Aug–Oct, already in the system before this import)
account for these units.

**Open questions for the root-cause investigation:**
- Is there a real local-purchase/stock-receipt history for August that was never entered
  into this system at all, which would explain the missing stock?
- Are some of these actually the *same* physical units as stock already recorded under a
  slightly different model name/spelling (another instance of the §4 problem), just not
  caught because this specific combination wasn't in September's data?
- Is the "Mohsin" handover genuinely incomplete for some models (he handed over less than
  what was actually needed to fulfil September's sales)?

**What's safe about the current state regardless of the cause**: no stock quantities were
corrupted or double-counted to make these "work" — they simply don't touch stock at all,
and the real money owed is still correctly posted to each customer's ledger.

**A related, smaller gap**: 4 of the 7 zero-rate ("free/sample") Credit Sale rows also had
no real stock to mark as damaged against — logged as a plain print warning during the
import run, not in any table. If you want these findable later, search the import run's
output or re-derive from rows 57, 259, 262, 264 in the source sheet.

---

## 7. Local Purchase → Credit Sale ordering, and the "Sold To" column

Local Purchase and Credit Sale are **not independent** — some Credit Sale rows draw stock
from a same-day Local Purchase (confirmed for invoice #417: S&A sells 20 Vivo Y500 units
to Shakeel, which go straight to Sonu Traders the same day). This import processes **every
September transaction from both sheets together, in one chronological pass**, Local
Purchase before Credit Sale on the same date, specifically to make this work.

**Local Purchase's "Sold To (Party)" column** means the same physical units were
immediately resold. Checked empirically against Credit Sale's own invoice numbers: **only
2 of 9 "Sold To" rows also appear as their own independent Credit Sale entry** (invoices
#417 and #445 — Shakeel apparently cross-referenced some resales in both sheets). For
those 2, the synthetic "Sold To" sale is **skipped** to avoid double-counting; the real
Credit Sale entry for that invoice covers it. For the other 7, most had no resolvable
model/category at all (handled as the A.Power Traders exception, §8, or simply excluded
from `lp_real` entirely upfront) — **only 1 ("Sold To" row 77, Shoaib Mobile Jhang,
Samsung S26 Ultra, 5 units) became a real new sale.**

**If a future month's data has more "Sold To" overlaps with its own Credit Sale sheet,
this same invoice-number cross-check needs to be redone** — it isn't generic, it's keyed
to the specific invoice numbers found in September.

---

## 8. The A.Power Traders exception (Local Purchase row 21)

One Local Purchase row (A.Power Traders, invoice 478, Rs 1,500) has **no resolvable
category/model at all** — the sheet just says "Membrane" with no specific phone model —
and was resold to "Dream Mobile" with **no sale amount given at all** in the source.
Handled as: a plain `Accounts Payable` ledger entry for A.Power Traders (Rs 1,500,
`reference_type='local_purchase_exception'`), no stock effect, and **no matching sale
recorded for Dream Mobile at all** — the source simply doesn't give enough information to
record one.

---

## 9. Mistakes made and caught during this import (for transparency)

- **Normalization bug**: an early version of the brand/model matching stripped the literal
  word "IPHONE" but not the common sheet abbreviation "IP" — this would have silently
  created duplicate iPhone models for most of the catalog before being caught and fixed.
- **Category-scoping bug**: `Item` lookups were briefly keyed only by `model_id`, not
  `(model_id, category_id)` — since one `Model` is shared across every category (e.g.
  "Galaxy A10" has a separate `Item` under OG Glass, Dust Plug, TPU Case...), this made
  models that exist in multiple categories look like they had multiple "variants" within
  one category, when they didn't.
- **Duplicate invoice processing**: invoice #417 was initially created twice — once via
  Local Purchase's "Sold To" field, once via Credit Sale's own rows for the same invoice
  — before the cross-check in §7 was added.
- **Resumability gaps, found and fixed across several partial `--apply` runs** that failed
  partway through (each failure's partial work was either cleanly rolled back by Postgres,
  since each transaction commits independently, or cleaned up by hand where needed):
  - Zero-rate ("free/sample") rows were being silently dropped on resume, because they
    were only ever collected from inside the same per-group loop that gets skipped once a
    group's main sale already exists.
  - The Local Purchase exception row (§8) and two `insufficient_stock` log entries got
    posted **twice** across separate run attempts before a proper idempotency check was
    added — found via a full duplicate sweep after the run completed, and removed.
  - **One false positive during that same sweep**: two pairs of `insufficient_stock`
    entries looked like duplicates (identical item/qty/rate under the same invoice,
    #16) and were deleted — then found to be genuinely separate rows in the source
    sheet (Shakeel's own book really does record the same model/qty/rate twice in a row
    sometimes) and restored. **Worth remembering for any future audit**: identical
    consecutive values are not automatically duplicates — always check the source sheet
    before assuming so.

---

## 10. Things not independently re-verified, worth a second look

- Punjab Kamal Industries' party role (customer vs. local_vendor) — see §2.
- Whether any other catalog models have the same "IP" vs "IPHONE" (or similar) spelling
  duplication as the two found in §4, outside what September's data happened to touch.
  Also not checked: whether this spelling inconsistency is now what the ~150 brand-new
  items created by this import themselves use consistently (the matching script always
  normalized to "IP"-prefixed forms, so the duplication risk going forward should be
  low, but wasn't separately re-audited against the Membrane/Bolt/Jun Best categories
  this import didn't need).
- All 131 Expenses sit under "Unspecified (to be decided)" payment account — see §2.
