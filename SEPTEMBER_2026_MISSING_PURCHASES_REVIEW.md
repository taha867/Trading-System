# September 2026 — Missing Local Purchases (review before anything is entered)

Prepared 2026-11-04 from `Daily Cash Book (Sept 2026).xlsx` (Local Purchase sheet) compared with the production database, read-only. **Nothing has been written to production.**

## 1. What is missing

The sheet's September Local Purchase total is **₨853,935** (82 rows). The app holds **₨317,720** (23 purchase orders ₨316,220 + one ₨1,500 ledger entry for A.Power Traders). The earlier import only kept rows that had **both a category and a model**, so every row missing one of the two was skipped without a trace.

**56 rows, ₨536,215, are not in the app** (the A.Power Traders row, ₨1,500, is already booked and is excluded from this list).

| Class | Rows | Amount (PKR) | What it is |
|---|---|---|---|
| A. Model given, category blank | 40 | 417,840 | e.g. NS Traders 'HOT 9' 1000 pcs. Can become real stock once we agree the category |
| B. Category given, model blank | 16 | 118,375 | e.g. 'TPU' 540 pcs resold in bulk. No model, so no stock can be tracked |

### By supplier (what the supplier balance is understated by)

| Supplier | Missing (PKR) |
|---|---|
| Galaxy mobile  Kamran | 201,500 |
| NS Traders | 154,000 |
| S&A | 125,045 |
| AlNafeh Traders | 44,050 |
| Javed Traders | 8,740 |
| AMT | 2,880 |

## 2. Proposed treatment

**Class A (model known):** receive as real purchases into stock, one purchase order per (date, supplier), with the category chosen below.

- 29 rows (₨205,430): the model **and** an item in the proposed category already exist in the catalog — ready.
- 5 rows (₨29,010): the category is clear by price but the model or its item is not in the catalog yet — needs a new model or item (listed in the appendix).
- 6 rows (₨183,400): the price (55–80) doesn't match a clear category — **please confirm the category** (I assumed OG Glass Protector).

**Class B (no model):** record only the money owed to the supplier (Accounts Payable) with no stock, the same way the A.Power Traders row was handled. These are mostly bulk resales that the app already holds as no-stock sales (invoices 433, 444, 445, 453, 513), so adding stock here would double count.

## 3. Risks you should know about before approving

1. **Stock would be overstated unless the earlier no-stock sales are replayed.** 231 September sales lines (₨540,510) were logged as 'insufficient stock' most likely because these purchases were missing (not yet proven); they never reduced stock. If we add the purchases as stock, those lines still don't consume it. The clean fix is a second step: turn those 231 lines into real FIFO sales after the purchases are in. I would do that as a separate, dry-run-first step.
2. **Rough evidence these purchases were resold:** Infinix Hot 9 — 1,020 bought here, about 790 appear on September sales; Vivo Y12/Y15 — 500 bought, about 640 sold; Redmi 13C — 500 bought, about 930 sold; Infinix Smart 9 — 500 bought, about 610 sold. (Name match only, all categories, so treat as indicative.)
3. **Supplier balances change** by the amounts in the table above (up). Check them against the supplier's own statement.
4. **Category guesses:** rows 63–75 etc. are priced about ₨51, which fits OG Glass, but the sheet does not say so.

## 4. Decisions needed

1. Confirm **OG Glass Protector** for model-only rows priced up to ₨52, **Dust Plug** for the ₨90 rows, and the category for the rows priced ₨55–80.
2. OK to create the missing models/items (Class A, 'not in catalog' rows)?
3. OK to record Class B as payable-only (no stock)?
4. Do the follow-up that replays the 231 no-stock sales against the new stock (recommended), or leave them as logged?

## Appendix: every row

Sheet row numbers refer to the Local Purchase sheet. 'Sold to' is the sheet's resale column.

| Row | Date | Supplier | Inv | Category (sheet) | Model (sheet) | Qty × Rate | Amount | Class | Proposed | Catalog check | Sold to |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | 2026-09-03 | S&A | 433 | TPU |  | 40 × 72 | 2,880 | B | no stock (payable only) | - | Sonu Traders Khawali Lakhan |
| 5 | 2026-09-03 | S&A | 433 | Dust Plug |  | 10 × 100 | 1,000 | B | no stock (payable only) | - | Sonu Traders Khawali Lakhan |
| 6 | 2026-09-03 | S&A | 433 | Privacy |  | 20 × 75 | 1,500 | B | no stock (payable only) | - | Sonu Traders Khawali Lakhan |
| 7 | 2026-09-03 | S&A | 444 | TPU |  | 540 × 75 | 40,500 | B | no stock (payable only) | - | Abdullah Mobile Mandi Bhaudeen |
| 8 | 2026-09-03 | S&A | 444 | Dust Plug |  | 27 × 98 | 2,646 | B | no stock (payable only) | - | Abdullah Mobile Mandi Bhaudeen |
| 9 | 2026-09-03 | S&A | 444 | Membrane Sheet |  | 175 × 67 | 11,725 | B | no stock (payable only) | - | Abdullah Mobile Mandi Bhaudeen |
| 10 | 2026-09-03 | S&A | 444 | OG |  | 290 × 52 | 15,080 | B | no stock (payable only) | - | Abdullah Mobile Mandi Bhaudeen |
| 11 | 2026-09-03 | S&A | 444 | OG |  | 200 × 52 | 10,400 | B | no stock (payable only) | - | Abdullah Mobile Mandi Bhaudeen |
| 12 | 2026-09-03 | S&A | 445 | OG |  | 80 × 52 | 4,160 | B | no stock (payable only) | - | Dream Mobile, Sargodha |
| 13 | 2026-09-03 | S&A | 453 | Privacy |  | 88 × 98 | 8,624 | B | no stock (payable only) | - | Sonu Traders Khawali Lakhan |
| 14 | 2026-09-04 | AMT |  | Membrane |  | 48 × 60 | 2,880 | B | no stock (payable only) | - |  |
| 15 | 2026-09-04 | AlNafeh Traders |  | Borderless |  | 30 × 95 | 2,850 | B | no stock (payable only) | - |  |
| 16 | 2026-09-04 | AlNafeh Traders |  | Borderless Fingerprint |  | 30 × 120 | 3,600 | B | no stock (payable only) | - |  |
| 17 | 2026-09-04 | S&A |  | Borderless |  | 30 × 95 | 2,850 | B | no stock (payable only) | - |  |
| 18 | 2026-09-04 | S&A |  | Borderless |  | 10 × 120 | 1,200 | B | no stock (payable only) | - |  |
| 20 | 2026-09-07 | S&A | 5 |  | A16 | 40 × 52 | 2,080 | A | OG Glass Protector | 'A16' item exists | Dream Mobile |
| 31 | 2026-09-13 | Javed Traders |  |  | HOT 9 | 20 × 51 | 1,020 | A | OG Glass Protector | 'HOT 9' item exists |  |
| 32 | 2026-09-13 | Javed Traders |  |  | HOT 10 | 20 × 51 | 1,020 | A | OG Glass Protector | 'HOT 10' item exists |  |
| 33 | 2026-09-13 | Javed Traders |  |  | Smart 20 | 20 × 80 | 1,600 | A | OG Glass Protector? | 'Smart 20' item exists |  |
| 34 | 2026-09-13 | Javed Traders |  |  | A80 | 100 × 51 | 5,100 | A | OG Glass Protector | 'A80' item exists |  |
| 36 | 2026-09-13 | S&A | 506 |  | A32 | 3 × 90 | 270 | A | Dust Plug | 'A32' item exists |  |
| 37 | 2026-09-13 | S&A | 506 |  | pixel 9/ 9 pro | 2 × 90 | 180 | A | Dust Plug | 'pixel 9' item exists; '9 pro' item exists |  |
| 38 | 2026-09-13 | S&A | 506 |  | hot 60 pro | 3 × 90 | 270 | A | Dust Plug | 'hot 60 pro' item exists |  |
| 43 | 2026-09-13 | AlNafeh Traders | 506 |  | A70 | 20 × 51 | 1,020 | A | OG Glass Protector | 'A70' item exists |  |
| 44 | 2026-09-13 | AlNafeh Traders | 506 |  | A80/ Note 9s | 10 × 51 | 510 | A | OG Glass Protector | 'A80' item exists; 'Note 9s' item exists |  |
| 45 | 2026-09-13 | AlNafeh Traders | 506 |  | C51 | 20 × 51 | 1,020 | A | OG Glass Protector | 'C51' item exists |  |
| 46 | 2026-09-13 | AlNafeh Traders | 506 |  | A3s | 20 × 51 | 1,020 | A | OG Glass Protector | 'A3s' item exists |  |
| 47 | 2026-09-13 | AlNafeh Traders | 506 |  | Oppo Reno 6 | 10 × 51 | 510 | A | OG Glass Protector | 'Oppo Reno 6' item exists |  |
| 50 | 2026-09-16 | S&A | 513 | Dust plug |  | 72 × 90 | 6,480 | B | no stock (payable only) | - | Sonu Traders Khawali Lakhan |
| 53 | 2026-09-18 | S&A | 518 |  | A6 | 30 × 60 | 1,800 | A | OG Glass Protector? | 'A6' model exists, no OG Glass Protector item yet |  |
| 54 | 2026-09-18 | S&A | 518 |  | C51 | 20 × 51 | 1,020 | A | OG Glass Protector | 'C51' item exists |  |
| 55 | 2026-09-18 | S&A | 518 |  | Cammon 20 | 20 × 51 | 1,020 | A | OG Glass Protector | 'Cammon 20' not in catalog |  |
| 56 | 2026-09-18 | S&A | 518 |  | Note 50 | 10 × 51 | 510 | A | OG Glass Protector | 'Note 50' item exists |  |
| 57 | 2026-09-18 | S&A | 518 |  | Hot 10 | 20 × 51 | 1,020 | A | OG Glass Protector | 'Hot 10' item exists |  |
| 58 | 2026-09-18 | S&A | 518 |  | Iphone X | 10 × 51 | 510 | A | OG Glass Protector | 'Iphone X' item exists |  |
| 59 | 2026-09-18 | S&A | 518 |  | Iphone 12 pro | 20 × 51 | 1,020 | A | OG Glass Protector | 'Iphone 12 pro' model exists, no OG Glass Protector item yet |  |
| 63 | 2026-09-22 | NS Traders |  |  | HOT 9 | 1000 × 51.5 | 51,500 | A | OG Glass Protector | 'HOT 9' item exists |  |
| 64 | 2026-09-22 | NS Traders |  |  | Y12/ Y15 | 500 × 51 | 25,500 | A | OG Glass Protector | 'Y12' model exists, no OG Glass Protector item yet; 'Y15' item exists |  |
| 65 | 2026-09-22 | NS Traders |  |  | HOT 10 | 500 × 51 | 25,500 | A | OG Glass Protector | 'HOT 10' item exists |  |
| 66 | 2026-09-22 | NS Traders |  |  | A80 | 1000 × 51.5 | 51,500 | A | OG Glass Protector | 'A80' item exists |  |
| 68 | 2026-09-23 | AlNafeh Traders | 532 |  | Smart 20 | 300 × 65 | 19,500 | A | OG Glass Protector? | 'Smart 20' item exists |  |
| 69 | 2026-09-23 | AlNafeh Traders | 532 |  | A6c | 200 × 65 | 13,000 | A | OG Glass Protector? | 'A6c' not in catalog |  |
| 70 | 2026-09-23 | AlNafeh Traders | 532 |  | cammon 30 | 20 × 51 | 1,020 | A | OG Glass Protector | 'cammon 30' not in catalog |  |
| 72 | 2026-09-24 | Galaxy mobile  Kamran |  |  | pixel 7 | 500 × 50 | 25,000 | A | OG Glass Protector | 'pixel 7' item exists |  |
| 73 | 2026-09-24 | Galaxy mobile  Kamran |  |  | 13C | 500 × 50 | 25,000 | A | OG Glass Protector | '13C' item exists |  |
| 74 | 2026-09-24 | Galaxy mobile  Kamran |  |  | Smart 9 | 500 × 55 | 27,500 | A | OG Glass Protector? | 'Smart 9' item exists |  |
| 75 | 2026-09-24 | Galaxy mobile  Kamran |  |  | Smart 20 | 2000 × 60 | 120,000 | A | OG Glass Protector? | 'Smart 20' item exists |  |
| 76 | 2026-09-24 | Galaxy mobile  Kamran |  |  | Pova2/Note7 | 80 × 50 | 4,000 | A | OG Glass Protector | 'Pova2' item exists; 'Note7' item exists |  |
| 78 | 2026-09-25 | S&A | 541 |  | iphone 15 | 10 × 90 | 900 | A | Dust Plug | 'iphone 15' item exists | Habib Mobile Jhang |
| 79 | 2026-09-25 | S&A | 541 |  | Mi note 15 | 5 × 90 | 450 | A | Dust Plug | 'Mi note 15' not in catalog | Habib Mobile Jhang |
| 80 | 2026-09-25 | S&A | 541 |  | 13 pro | 10 × 90 | 900 | A | Dust Plug | '13 pro' item exists | Habib Mobile Jhang |
| 81 | 2026-09-25 | S&A | 541 |  | smart 20 | 10 × 90 | 900 | A | Dust Plug | 'smart 20' item exists | Habib Mobile Jhang |
| 82 | 2026-09-25 | S&A | 541 |  | 16 pro max | 10 × 90 | 900 | A | Dust Plug | '16 pro max' item exists | Habib Mobile Jhang |
| 83 | 2026-09-25 | S&A | 541 |  | v70 | 5 × 90 | 450 | A | Dust Plug | 'v70' item exists | Habib Mobile Jhang |
| 84 | 2026-09-25 | S&A | 541 |  | v70 FE | 10 × 90 | 900 | A | Dust Plug | 'v70 FE' item exists | Habib Mobile Jhang |
| 85 | 2026-09-25 | S&A | 541 |  | y500 | 10 × 90 | 900 | A | Dust Plug | 'y500' item exists | Habib Mobile Jhang |
