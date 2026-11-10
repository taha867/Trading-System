# September 2026 — Missing Local Purchases: DRY RUN

> **Status (2026-11-10): applied.** This dry run has since been applied to production. Invoice numbers shown here were the carry-down values; the wrong ones were cleared afterwards. See `PRODUCTION_CHANGES_LOG.md`.

Generated 2026-11-04. **Nothing was written to production.** This shows exactly what the apply step would do with the defaults you chose (OG Glass Protector for rows up to ₨52 and for ₨55–80 rows, Dust Plug for the ₨90 rows, missing models/items created, bulk rows payable only). Companion to `SEPTEMBER_2026_MISSING_PURCHASES_REVIEW.md`.

## Summary

| | Rows | Amount (PKR) |
|---|---|---|
| Class A, ready to enter as stock | 40 | 417,840 |
| Class A, **needs your decision** (cannot be entered yet) | 0 | 0 |
| Class B, payable only (no stock) | 16 | 118,375 |
| **Total** | 56 | 536,215 |

- New purchase orders: 40 (one line each, as the earlier import did) — each posts an Accounts Payable credit, a stock lot and a receipt movement.
- New payable-only ledger entries: 16 (reference type `local_purchase_exception`).
- Resales that go with a purchase (the sheet's 'Sold To' column, same quantity and rate): 9 rows, ₨8,380 — these become sales that consume the new stock.
- New models/items to create: 4.

### Supplier balance effect (payable goes up by)

| Supplier | Existing party | Added payable |
|---|---|---|
| Galaxy Mobile, Kamran | yes | 201,500 |
| NS Traders | yes | 154,000 |
| S&A | yes | 125,045 |
| AlNafeh Traders | yes | 44,050 |
| Javed Traders | yes | 8,740 |
| AMT | yes | 2,880 |

### Duplicate catalog models found (default applied: the one with more stock)

- Google Pixel Pixel 9: 2 duplicate models with Dust Plug items; chose model #157 (most stock)
- Redmi 13C: 2 duplicate models with OG Glass Protector items; chose model #193 (most stock)

### Rows that need your decision (please answer these)

| Sheet row | Supplier | Model on sheet | Qty × Rate | Amount | Question |
|---|---|---|---|---|---|

## Class A — rows that would be entered as stock

| Row | Date | Supplier | Inv | Qty × Rate | Amount | Category | Item | Compatible models | Resale to |
|---|---|---|---|---|---|---|---|---|---|
| 20 | 2026-09-07 | S&A | 5 | 40 × 52 | 2,080 | OG Glass Protector | EXISTING item #2419 OG G-SAMSUNG-GALAXYA16 (stock now 0) |  | Dream Mobile |
| 31 | 2026-09-13 | Javed Traders |  | 20 × 51 | 1,020 | OG Glass Protector | EXISTING item #225 PROT-INFINIX-HOT9 (stock now 0) |  |  |
| 32 | 2026-09-13 | Javed Traders |  | 20 × 51 | 1,020 | OG Glass Protector | EXISTING item #227 PROT-INFINIX-HOT10 (stock now 0) |  |  |
| 33 | 2026-09-13 | Javed Traders |  | 20 × 80 | 1,600 | OG Glass Protector | EXISTING item #2435 OG G-INFINIX-SMART20 (stock now 580) |  |  |
| 34 | 2026-09-13 | Javed Traders |  | 100 × 51 | 5,100 | OG Glass Protector | EXISTING item #2406 OG G-SAMSUNG-A80 (stock now 0) |  |  |
| 36 | 2026-09-13 | S&A | 506 | 3 × 90 | 270 | Dust Plug | EXISTING item #2456 DUST-SAMSUNG-GALAXYA32 (stock now 0) |  |  |
| 37 | 2026-09-13 | S&A | 506 | 2 × 90 | 180 | Dust Plug | EXISTING item #454 DPLUG-PIXEL9 (stock now 58) | Google Pixel Pixel 9PRO |  |
| 38 | 2026-09-13 | S&A | 506 | 3 × 90 | 270 | Dust Plug | EXISTING item #2457 DUST-INFINIX-HOT60PRO+ (stock now 0) |  |  |
| 43 | 2026-09-13 | AlNafeh Traders | 506 | 20 × 51 | 1,020 | OG Glass Protector | EXISTING item #213 PROT-SAMSUNG-A70 (stock now 20) |  |  |
| 44 | 2026-09-13 | AlNafeh Traders | 506 | 10 × 51 | 510 | OG Glass Protector | EXISTING item #2406 OG G-SAMSUNG-A80 (stock now 0) | Redmi Note 9S |  |
| 45 | 2026-09-13 | AlNafeh Traders | 506 | 20 × 51 | 1,020 | OG Glass Protector | EXISTING item #2459 OG G-REALME-C51 (stock now 0) |  |  |
| 46 | 2026-09-13 | AlNafeh Traders | 506 | 20 × 51 | 1,020 | OG Glass Protector | EXISTING item #2458 OG G-OPPO-A3S (stock now 0) |  |  |
| 47 | 2026-09-13 | AlNafeh Traders | 506 | 10 × 51 | 510 | OG Glass Protector | EXISTING item #2436 OG G-OPPO-RENO6 (stock now 0) |  |  |
| 53 | 2026-09-18 | S&A | 518 | 30 × 60 | 1,800 | OG Glass Protector | CREATE item for existing model 'Oppo A6' in OG Glass Protector |  |  |
| 54 | 2026-09-18 | S&A | 518 | 20 × 51 | 1,020 | OG Glass Protector | EXISTING item #2459 OG G-REALME-C51 (stock now 0) |  |  |
| 55 | 2026-09-18 | S&A | 518 | 20 × 51 | 1,020 | OG Glass Protector | EXISTING item #2541 OG G-TECNO-CAMON20 (stock now 0) |  |  |
| 56 | 2026-09-18 | S&A | 518 | 10 × 51 | 510 | OG Glass Protector | EXISTING item #241 PROT-NOTE50 (stock now 50) |  |  |
| 57 | 2026-09-18 | S&A | 518 | 20 × 51 | 1,020 | OG Glass Protector | EXISTING item #227 PROT-INFINIX-HOT10 (stock now 0) |  |  |
| 58 | 2026-09-18 | S&A | 518 | 10 × 51 | 510 | OG Glass Protector | EXISTING item #137 PROT-APPLE-IPX (stock now 140) |  |  |
| 59 | 2026-09-18 | S&A | 518 | 20 × 51 | 1,020 | OG Glass Protector | CREATE item for existing model 'iPhone iPhone 12 Pro' in OG Glass Protector |  |  |
| 63 | 2026-09-22 | NS Traders |  | 1000 × 51.5 | 51,500 | OG Glass Protector | EXISTING item #225 PROT-INFINIX-HOT9 (stock now 0) |  |  |
| 64 | 2026-09-22 | NS Traders |  | 500 × 51 | 25,500 | OG Glass Protector | EXISTING item #248 PROT-VIVOY15 (stock now 500) | Vivo Y12 |  |
| 65 | 2026-09-22 | NS Traders |  | 500 × 51 | 25,500 | OG Glass Protector | EXISTING item #227 PROT-INFINIX-HOT10 (stock now 0) |  |  |
| 66 | 2026-09-22 | NS Traders |  | 1000 × 51.5 | 51,500 | OG Glass Protector | EXISTING item #2406 OG G-SAMSUNG-A80 (stock now 0) |  |  |
| 68 | 2026-09-23 | AlNafeh Traders | 532 | 300 × 65 | 19,500 | OG Glass Protector | EXISTING item #2435 OG G-INFINIX-SMART20 (stock now 580) |  |  |
| 69 | 2026-09-23 | AlNafeh Traders | 532 | 200 × 65 | 13,000 | OG Glass Protector | CREATE model 'Oppo A6c' + item |  |  |
| 70 | 2026-09-23 | AlNafeh Traders | 532 | 20 × 51 | 1,020 | OG Glass Protector | EXISTING item #2422 OG G-TECNO-CAMON30 (stock now 0) |  |  |
| 72 | 2026-09-24 | Galaxy Mobile, Kamran |  | 500 × 50 | 25,000 | OG Glass Protector | EXISTING item #174 PROT-GOOGLE-PIXEL7 (stock now 0) |  |  |
| 73 | 2026-09-24 | Galaxy Mobile, Kamran |  | 500 × 50 | 25,000 | OG Glass Protector | EXISTING item #208 PROT-REDMI-13C (stock now 610) |  |  |
| 74 | 2026-09-24 | Galaxy Mobile, Kamran |  | 500 × 55 | 27,500 | OG Glass Protector | EXISTING item #2427 OG G-INFINIX-SMART9 (stock now 0) |  |  |
| 75 | 2026-09-24 | Galaxy Mobile, Kamran |  | 2000 × 60 | 120,000 | OG Glass Protector | EXISTING item #2435 OG G-INFINIX-SMART20 (stock now 580) |  |  |
| 76 | 2026-09-24 | Galaxy Mobile, Kamran |  | 80 × 50 | 4,000 | OG Glass Protector | EXISTING item #2408 OG G-TECNO-POVA2 (stock now 0) | Infinix Note 7 |  |
| 78 | 2026-09-25 | S&A | 541 | 10 × 90 | 900 | Dust Plug | EXISTING item #849 DPLUG-IPHONE15 (stock now 0) |  | Shoaib Mobile, Jhang |
| 79 | 2026-09-25 | S&A | 541 | 5 × 90 | 450 | Dust Plug | CREATE model 'Redmi Note 15' + item |  | Shoaib Mobile, Jhang |
| 80 | 2026-09-25 | S&A | 541 | 10 × 90 | 900 | Dust Plug | EXISTING item #2549 DUST-IPHONE-IPHONE13PRO (stock now 0) |  | Shoaib Mobile, Jhang |
| 81 | 2026-09-25 | S&A | 541 | 10 × 90 | 900 | Dust Plug | EXISTING item #2534 DUST-INFINIX-SMART20 (stock now 0) |  | Shoaib Mobile, Jhang |
| 82 | 2026-09-25 | S&A | 541 | 10 × 90 | 900 | Dust Plug | EXISTING item #851 DPLUG-IPHONE16PROMAX (stock now 72) |  | Shoaib Mobile, Jhang |
| 83 | 2026-09-25 | S&A | 541 | 5 × 90 | 450 | Dust Plug | EXISTING item #2533 DUST-VIVO-V70 (stock now 0) |  | Shoaib Mobile, Jhang |
| 84 | 2026-09-25 | S&A | 541 | 10 × 90 | 900 | Dust Plug | EXISTING item #2554 DUST-VIVO-V70FE (stock now 0) |  | Shoaib Mobile, Jhang |
| 85 | 2026-09-25 | S&A | 541 | 10 × 90 | 900 | Dust Plug | EXISTING item #2139 DUST-VIVO-Y500 (stock now 0) |  | Shoaib Mobile, Jhang |

## Class B — payable only (no stock)

| Row | Date | Supplier | Inv | Category | Qty × Rate | Amount | Sold to (sheet) |
|---|---|---|---|---|---|---|---|
| 4 | 2026-09-03 | S&A | 433 | TPU | 40 × 72 | 2,880 | Sonu Traders Khawali Lakhan |
| 5 | 2026-09-03 | S&A | 433 | Dust Plug | 10 × 100 | 1,000 | Sonu Traders Khawali Lakhan |
| 6 | 2026-09-03 | S&A | 433 | Privacy | 20 × 75 | 1,500 | Sonu Traders Khawali Lakhan |
| 7 | 2026-09-03 | S&A | 444 | TPU | 540 × 75 | 40,500 | Abdullah Mobile Mandi Bhaudeen |
| 8 | 2026-09-03 | S&A | 444 | Dust Plug | 27 × 98 | 2,646 | Abdullah Mobile Mandi Bhaudeen |
| 9 | 2026-09-03 | S&A | 444 | Membrane Sheet | 175 × 67 | 11,725 | Abdullah Mobile Mandi Bhaudeen |
| 10 | 2026-09-03 | S&A | 444 | OG | 290 × 52 | 15,080 | Abdullah Mobile Mandi Bhaudeen |
| 11 | 2026-09-03 | S&A | 444 | OG | 200 × 52 | 10,400 | Abdullah Mobile Mandi Bhaudeen |
| 12 | 2026-09-03 | S&A | 445 | OG | 80 × 52 | 4,160 | Dream Mobile, Sargodha |
| 13 | 2026-09-03 | S&A | 453 | Privacy | 88 × 98 | 8,624 | Sonu Traders Khawali Lakhan |
| 14 | 2026-09-04 | AMT |  | Membrane | 48 × 60 | 2,880 |  |
| 15 | 2026-09-04 | AlNafeh Traders |  | Borderless | 30 × 95 | 2,850 |  |
| 16 | 2026-09-04 | AlNafeh Traders |  | Borderless Fingerprint | 30 × 120 | 3,600 |  |
| 17 | 2026-09-04 | S&A |  | Borderless | 30 × 95 | 2,850 |  |
| 18 | 2026-09-04 | S&A |  | Borderless | 10 × 120 | 1,200 |  |
| 50 | 2026-09-16 | S&A | 513 | Dust plug | 72 × 90 | 6,480 | Sonu Traders Khawali Lakhan |

## Catalog additions the apply step would make (complete list)

| What | Why |
|---|---|
| Model **Oppo A6c** + OG Glass Protector item | Sheet row 69 (not in the catalog) |
| Model **Redmi Note 15** + Dust Plug item | Sheet row 79 ("Mi note 15") |
| Model **Redmi Note 9S** (compatible model only, no item of its own) | Sheet row 44 ("A80/ Note 9s") |
| OG Glass Protector item for existing model **Oppo A6** | Sheet row 53 |
| OG Glass Protector item for existing model **iPhone 12 Pro** | Sheet row 59 |

Decisions you gave: A80 = Samsung A80, C51 = Realme C51, A6 = Oppo A6, A6c = Oppo A6c. Duplicate catalog models (Redmi 13C, Google Pixel 9 in Dust Plug) use the model with the most stock; the catalog also has `iPhone 12 Pro` / `IP 12 PRO` and `Pixel 9 Pro` / `9PRO` pairs worth merging later.
