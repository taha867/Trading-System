# Catalog cleanup review

> **Status (2026-11-11): applied.** The catalog cleanup described below was applied to production; this file shows the state BEFORE it. See `PRODUCTION_CHANGES_LOG.md` (#14) and the lists in `catalog_cleanup_review/cleanup_*.csv`.

Generated read-only from production. **Nothing has been changed.** Check the lists, tell me what to correct, and only then is the cleanup run.

## Summary

- Models: 601 total. 278 already in the standard form, 205 to rename, 87 to merge into another model, 31 need your decision.
- Items: 1016 active. 53 duplicates to merge into another item (stock lots, purchase lines and sales lines are moved, nothing is lost). 963 remain.
- Item codes: 359 of 1016 are in the standard pattern today. After the cleanup 944 get a standard code (944 change, 0 already match); 19 wait for their model to be decided.
- Compatible models: 32 cases where two items (same category, same colour) share a phone - decide one item or two; 26 old item codes name an extra phone that is missing from the compatible list (it would be lost when codes are rewritten); 55 fitment texts in your sheet.

Full lists: `catalog_cleanup_review/models.csv`, `items.csv`, `skus.csv`, `fitment.csv`.

## 1. Models that need your decision

These can't be turned into a trustworthy model name automatically (a colour entered as a model, a cut-off fragment, a typo).

| Brand | Current name | Items using it | Why |
|---|---|---|---|
| Google Pixel | `9PROXLFINGER` | 1 | 'Finger' is a category (OG Finger Protector), not part of the model |
| Google Pixel | `Pixel 9RO` | 1 | looks like 'Pro' with the P missing |
| Google Pixel | `Pixel 9ROXL` | 1 | looks like 'Pro' with the P missing |
| Infinix | `NOTE EDGE` | 2 | no model number |
| OnePlus | `Ace` | 1 | no model number |
| Oppo | `Reno Z` | 2 | single letter 'Z' (abbreviation?); no model number |
| Redmi | `R-C15` | 1 | single letter 'R' (abbreviation?) |
| Redmi | `REDMI` | 1 | no model number |
| Redmi | `RN13 & Poco C55` | 1 | single letter '&' (abbreviation?); unexpected characters |
| Samsung | `4G` | 0 | only a network tag (4G/5G), no model |
| Samsung | `BLACK` | 0 | a colour, not a model |
| Samsung | `BLACKTITANIUM` | 0 | a colour, not a model |
| Samsung | `Galaxy Note Edge` | 2 | no model number |
| Samsung | `JACE` | 0 | no model number |
| Samsung | `S25 Ultra Grey Titanium` | 1 | contains a colour word (belongs in the item's variant) |
| Tecno | `Pop Lite` | 1 | no model number |
| Tecno | `SPARKGO` | 1 | no model number |
| Vivo | `5G` | 0 | only a network tag (4G/5G), no model |
| Vivo | `5G30)` | 0 | unbalanced bracket (text cut off) |
| Vivo | `HD5)` | 0 | unbalanced bracket (text cut off) |
| Vivo | `V40 Lite (YOUNG` | 2 | unbalanced bracket (text cut off) |
| Vivo | `Y51(2020` | 1 | unbalanced bracket (text cut off) |
| iPhone | `BLACK` | 0 | a colour, not a model |
| iPhone | `BLACKTITANIUM` | 0 | a colour, not a model |
| iPhone | `BLUE` | 0 | a colour, not a model |
| iPhone | `BLUETITANIUM` | 0 | a colour, not a model |
| iPhone | `GOLDEN` | 0 | a colour, not a model |
| iPhone | `GREY` | 0 | a colour, not a model |
| iPhone | `PURPLE` | 0 | a colour, not a model |
| iPhone | `SILVER` | 0 | a colour, not a model |
| iPhone | `TITANIUM` | 0 | a colour, not a model |

## 2. Same phone written several ways (will be merged into one model)

73 phones. A further 159 models only get a tidier name (see `models.csv`).

| Brand | Standard name | Spellings merged | Items moved |
|---|---|---|---|
| Google Pixel | **10** | `10`, `Pixel 10` | 3 |
| Google Pixel | **10 Pro XL** | `10PROXL`, `Pixel 10 Pro XL` | 2 |
| Google Pixel | **6** | `6`, `Pixel 6` | 6 |
| Google Pixel | **6 Pro** | `6PRO`, `PIXEL 6 PRO`, `Pixel 6 Pro` | 3 |
| Google Pixel | **6A** | `6A`, `Pixel 6A` | 6 |
| Google Pixel | **7** | `7`, `Pixel 7` | 4 |
| Google Pixel | **7 Pro** | `7PRO`, `PIXEL 7 PRO`, `Pixel 7 Pro` | 3 |
| Google Pixel | **7A** | `7A`, `Pixel 7A` | 5 |
| Google Pixel | **8** | `Pixel 8` | 3 |
| Google Pixel | **8 Pro** | `8PRO`, `Pixel 8 Pro` | 5 |
| Google Pixel | **8A** | `Pixel 8A` | 2 |
| Google Pixel | **9** | `9`, `Pixel 9` | 4 |
| Google Pixel | **9 Pro** | `9PRO`, `Pixel 9 Pro` | 1 |
| Google Pixel | **9 Pro XL** | `9PROXL`, `Pixel 9 Pro XL` | 4 |
| Huawei | **Y9 Prime** | `Y9PRIME` | 1 |
| Infinix | **Hot 60** | `HOT 60` | 1 |
| Infinix | **Note 50** | `Note 50`, `Note50` | 1 |
| Infinix | **Smart 10+** | `SMART10+`, `Smart 10 Plus` | 3 |
| Infinix | **Smart 9** | `SMART 9`, `Smart 9` | 6 |
| OnePlus | **12 Pro** | `12PRO` | 1 |
| OnePlus | **8 Pro** | `8PRO` | 1 |
| Oppo | **A5 Pro** | `A5 PRO`, `A5 PRO 5G` | 2 |
| Oppo | **A54** | `A54(4G)` | 1 |
| Oppo | **A58** | `A58(4G)` | 1 |
| Oppo | **Reno 13** | `RENO13` | 1 |
| Oppo | **Reno 14** | `RENO14`, `Reno 14 5G` | 1 |
| Realme | **Note 70** | `NOTE70`, `REALME NOTE 70` | 3 |
| Redmi | **10C** | `REDMI10C` | 1 |
| Redmi | **12** | `REDMI12` | 1 |
| Redmi | **12C** | `REDMI12C` | 0 |
| Redmi | **13C** | `REDMI13C` | 3 |
| Redmi | **14C** | `REDMI14C`, `RM14C` | 3 |
| Redmi | **15C** | `15C 4G`, `REDMI15C` | 2 |
| Redmi | **A5** | `A5 4G` | 1 |
| Redmi | **C51** | `REDMIC51` | 0 |
| Redmi | **Note 12** | `REDMINOTE12`, `RN NOTE12` | 2 |
| Redmi | **Note 13** | `RM NOTE13` | 1 |
| Redmi | **Note 13 Pro** | `Note 13 Pro 5G`, `RN NOTE13 PRO` | 1 |
| Redmi | **Note 14** | `RM NOTE14` | 1 |
| Redmi | **Note 14 Pro** | `RN NOTE14 PRO` | 1 |
| Redmi | **Note 14 Pro+** | `RM NOTE14 PRO PLUS` | 1 |
| Samsung | **A14** | `Galaxy A14`, `Galaxy A14 5G`, `Sam A14` | 3 |
| Samsung | **A35** | `Galaxy A35` | 2 |
| Samsung | **A36** | `A36 5G`, `Galaxy A36` | 3 |
| Samsung | **A54** | `Galaxy A54` | 1 |
| Samsung | **A55** | `Galaxy A55` | 0 |
| Samsung | **S21** | `Galaxy S21`, `Sam S21` | 2 |
| Samsung | **S21 Ultra** | `S21 ULTRA`, `S21 Ultr`, `S21U` | 3 |
| Samsung | **S22** | `Galaxy S22`, `Sam S22` | 2 |
| Samsung | **S22 Ultra** | `S22 ULTRA`, `S22U` | 7 |
| Samsung | **S23 FE** | `S23 Fe`, `S23FE` | 3 |
| Samsung | **S23 Ultra** | `S23 ULTRA`, `S23 Ult` | 8 |
| Samsung | **S24** | `Galaxy S24`, `Sam S24` | 4 |
| Samsung | **S24 Ultra** | `Galaxy S24 Ultra`, `S24 U`, `S24U`, `Sam S24 Ultra` | 12 |
| Samsung | **S25** | `Galaxy S25`, `Sam S25` | 6 |
| Samsung | **S25 Ultra** | `Galaxy S25 Ultra`, `S25 U`, `S25 Ult`, `S25U` | 13 |
| Samsung | **S26** | `Galaxy S26`, `SAM S26` | 3 |
| Samsung | **S26 Ultra** | `Galaxy S26 Ultra`, `S26 Ult` | 9 |
| Samsung | **S26+** | `Galaxy S26+`, `SAM S26+` | 3 |
| Tecno | **Camon 50 Pro** | `CAMON 50 PRO`, `Camon 50 Pro`, `Camon 50PRO` | 4 |
| Vivo | **V50** | `V50`, `V50 5G` | 3 |
| Vivo | **V60** | `V60`, `Vivo V60` | 3 |
| Vivo | **V70** | `Vivo V70` | 1 |
| Vivo | **V70 FE** | `V70 FE (5G)`, `V70FE` | 2 |
| Vivo | **Y15** | `Vivo Y15`, `Y15` | 2 |
| iPhone | **12 Pro** | `12PRO`, `IP 12 PRO`, `iPhone 12 Pro` | 15 |
| iPhone | **13 Mini** | `iPhone 13 mini`, `iPhone 13MINNI` | 2 |
| iPhone | **13 Pro Max** | `IP 13 PRO MAX`, `iPhone 13 Pro Max` | 18 |
| iPhone | **14 Pro** | `IP 14 PRO`, `iPhone 14 Pro` | 13 |
| iPhone | **14+** | `iPhone 14 Plus`, `iPhone 14+` | 0 |
| iPhone | **15 Pro** | `IP 15 PRO`, `iPhone 15 Pro` | 12 |
| iPhone | **17** | `17`, `iPhone 17` | 10 |
| iPhone | **17 Pro Max** | `IP 17 PRO MAX`, `iPhone 17 Pro Max` | 21 |

## 3. Items that will be merged (same product, two records)

| Category | Keep | Merge into it | Stock moved |
|---|---|---|---|
| Dust Plug | `DPLUG-A5PRO` (stock 30.00) | `DPLUG-A5PRO5G` (stock 25.00) | 25.00 |
| Dust Plug | `DPLUG-IPHONE15PRO` (stock 30.00) | `DPLUG-IP15PRO` (stock 29.00) | 29.00 |
| Dust Plug | `DPLUG-PIXEL6PRO` (stock 52.00) | `DUST-GOOGLEPIXEL-6PRO` (stock 0) | 0 |
| Dust Plug | `DPLUG-RENO145G` (stock 60.00) | `DPLUG-RENO14` (stock 40.00) | 40.00 |
| Dust Plug | `DPLUG-RNNOTE12` (stock 23.00) | `DPLUG-NOTE12` (stock 14.00) | 14.00 |
| Dust Plug | `DPLUG-S23FE` (stock 31.00) | `DPLUG-S23FE-2` (stock 10.00) | 10.00 |
| Dust Plug | `DPLUG-SMART10PLUS` (stock 25.00) | `DUST-INFINIX-SMART10+` (stock 0) | 0 |
| Dust Plug | `DPLUG-V505G` (stock 10.00) | `DUST-VIVO-V50` (stock 0) | 0 |
| Dust Plug | `DPLUG-PIXEL10` (stock 103.00) | `DUST-GOOGLEPIXEL-10` (stock 0) | 0 |
| Dust Plug | `DPLUG-PIXEL10PROXL` (stock 71.00) | `DUST-GOOGLEPIXEL-10PROXL` (stock 0) | 0 |
| Dust Plug | `DPLUG-PIXEL6` (stock 126.00) | `DUST-GOOGLEPIXEL-6` (stock 0) | 0 |
| Dust Plug | `DPLUG-PIXEL6A` (stock 85.00) | `DUST-GOOGLEPIXEL-6A` (stock 0) | 0 |
| Dust Plug | `DPLUG-PIXEL7` (stock 108.00) | `DUST-GOOGLEPIXEL-7` (stock 0) | 0 |
| Dust Plug | `DPLUG-PIXEL7A` (stock 92.00) | `DUST-GOOGLEPIXEL-7A` (stock 0) | 0 |
| Dust Plug | `DPLUG-PIXEL7PRO` (stock 40.00) | `DUST-GOOGLEPIXEL-7PRO` (stock 0) | 0 |
| Dust Plug | `DPLUG-PIXEL8A` (stock 90.00) | `DUST-GOOGLEPIXEL-8A` (stock 0) | 0 |
| Dust Plug | `DPLUG-PIXEL8PRO` (stock 32.00) | `DUST-GOOGLEPIXEL-8PRO` (stock 0) | 0 |
| Dust Plug | `DPLUG-PIXEL9` (stock 60.00) | `DUST-GOOGLEPIXEL-9` (stock 0) | 0 |
| Dust Plug | `DPLUG-PIXEL9PROXL` (stock 21.00) | `DUST-GOOGLEPIXEL-9PROXL` (stock 0) | 0 |
| Dust Plug | `DPLUG-RM14C` (stock 60.00) | `DUST-REDMI-REDMI14C` (stock 0) | 0 |
| Dust Plug | `DPLUG-15C4G` (stock 36.00) | `DUST-REDMI-REDMI15C` (stock 0) | 0 |
| Its Me Privacy Protector | `ITSME-IPHONE13PROMAX` (stock 360.00) | `ITS -IPHONE-IP13PROMAX` (stock 0) | 0 |
| Its Me Privacy Protector | `ITSME-IPHONE14PRO` (stock 174.00) | `ITS -IPHONE-IP14PRO` (stock 0) | 0 |
| Its Me Privacy Protector | `ITSME-IPHONE17PROMAX` (stock 360.00) | `ITS -IPHONE-IP17PROMAX` (stock 0) | 0 |
| Its Me UV Glass Protector | `ITSUV-CAMON50PRO` (stock 637.00) | `ITS -TECNO-CAMON50PRO` (stock 0) | 0 |
| Membrane Sheet Protector | `MEMSH-IPHONE17PROMAX` (stock 414.00) | `MEMB-IPHONE-IP17PROMAX` (stock 0) | 0 |
| Membrane Sheet Protector | `MEMSH-S24U` (stock 66.00) | `MEMB-SAMSUNG-GALAXYS24ULTRA` (stock 0) | 0 |
| Membrane Sheet Protector | `MEMSH-IPHONE14PRO` (stock 55.00) | `MEMB-IPHONE-IP14PRO` (stock 0) | 0 |
| OG Finger Protector | `OGFNG-S24U` (stock 30.00) | `OG F-SAMSUNG-GALAXYS24ULTRA` (stock 0) | 0 |
| OG Finger Protector | `OGFNG-S25U` (stock 450.00) | `OG F-SAMSUNG-GALAXYS25ULTRA` (stock 0) | 0 |
| OG Glass Protector | `PROT-REDMI-12` (stock 100.00) | `OG G-REDMI-REDMI12` (stock 0) | 0 |
| OG Glass Protector | `PROT-REDMI-13C` (stock 1110.00) | `OG G-REDMI-REDMI13C` (stock 0) | 0 |
| OG Glass Protector | `PROT-REDMI-NOTE12` (stock 800.00) | `OG G-REDMI-REDMINOTE12` (stock 0) | 0 |
| OG Glass Protector | `PROT-14C` (stock 290.00) | `OG G-REDMI-REDMI14C` (stock 0) | 0 |
| OG Glass Protector | `OG G-IPHONE-IP13PROMAX` (stock 430.00) | `PROT-APPLE-IP13PROMAX` (stock 0) | 0 |
| OG Glass Protector | `PROT-APPLE-IP15PRO` (stock 264.00) | `OG G-IPHONE-IP15PRO` (stock 0) | 0 |
| OG Glass Protector | `PROT-APPLE-IP17PROMAX` (stock 305.00) | `OG G-IPHONE-IP17PROMAX` (stock 0) | 0 |
| OG Glass Protector | `PROT-OPPO-A54` (stock 550.00) | `OG G-OPPO-A54(4G)` (stock 0) | 0 |
| OG Glass Protector | `PROT-OPPO-A58` (stock 390.00) | `OG G-OPPO-A58(4G)` (stock 0) | 0 |
| OG Glass Protector | `PROT-REDMI-10C` (stock 410.00) | `OG G-REDMI-REDMI10C` (stock 0) | 0 |
| OG Glass Protector | `PROT-SAMA14` (stock 10.00) | `PROT-SAMSUNG-A14` (stock 0) | 0 |
| OG Glass Protector | `PROT-SAMS21` (stock 150.00) | `PROT-SAMSUNG-S21` (stock 0) | 0 |
| OG Glass Protector | `PROT-SAMS22` (stock 270.00) | `PROT-SAMSUNG-S22-S23` (stock 0) | 0 |
| OG Glass Protector | `PROT-SAMS26` (stock 240.00) | `PROT-SAMSUNG-S26` (stock 0) | 0 |
| OG Glass Protector | `PROT-SAMS26-2` (stock 250.00) | `PROT-SAMSUNG-S26PLUS` (stock 0) | 0 |
| OG Glass Protector | `PROT-SAMSUNG-A35-A55` (stock 570.00) | `OG G-SAMSUNG-A35` (stock 0) | 0 |
| Polish Glass Protector | `POLGL-13C` (stock 21.00) | `POLI-REDMI-REDMI13C` (stock 0) | 0 |
| Polish Glass Protector | `POLGL-SMART9` (stock 650.00) | `POLI-INFINIX-SMART9` (stock 0) | 0 |
| Polish Glass Protector | `POLGL-Y9PRIME` (stock 300.00) | `POLGL-Y9PRIME-2` (stock 325.00) | 325.00 |
| TPU Case | `TPU-REALMENOTE70` (stock 34.00) | `TPU -REALME-NOTE70` (stock 0) | 0 |
| TPU Case | `TPU-IPHONE15PRO` (stock 164.00) | `TPU -IPHONE-IP15PRO` (stock 0) | 0 |
| TPU Case | `TPU-IPHONE17PROMAX` (stock 101.00) | `TPU -IPHONE-IP17PROMAX` (stock 0) | 0 |
| TPU Case | `TPU-PIXEL8` (stock 61.00) | `TPU -GOOGLEPIXEL-8` (stock 0) | 0 |

## 4. Compatible models: your call

Phones that take the same part should be ONE item with the other phones as compatible models. Where today they are two items, I will not merge them without your yes. Examples (full list in `fitment.csv`):

- items share a model: Bolt Lens Protector iPhone 14 Pro Max - BOLTL-IPHONE14PROMAX-SILVER (stock 9.00) | BOLTL-IPHONE14PRO-SILVER (stock 9.00)
- items share a model: Bolt Lens Protector iPhone 17 Pro Max - BOLTL-IPHONE17PROMAX-SILVER (stock 18.00) | BOLTL-IPHONE17PRO-SILVER (stock 18.00)
- items share a model: Bolt Lens Protector iPhone 17 Pro Max - BOLTL-IPHONE17PROMAX-ORANGE (stock 100.00) | BOLTL-IPHONE17PRO-ORANGE (stock 100.00)
- items share a model: Dust Plug Infinix Hot 60I - DPLUG-HOT60 (stock 98.00) | DUST-INFINIX-HOT60I (stock 0)
- items share a model: Dust Plug Infinix Smart 9 - DPLUG-HOT50I (stock 88.00) | DUST-INFINIX-SMART9 (stock 0)
- items share a model: Dust Plug Oppo A6 Pro - DPLUG-A6PRO (stock 115.00) | DUST-OPPO-F31 (stock 0)
- items share a model: Dust Plug Redmi A5 - DPLUG-A54G (stock 45.00) | DUST-REDMI-REDMI (stock 0)
- items share a model: Dust Plug Redmi C51 - DPLUG-RC3 (stock 65.00) | DUST-REDMI-REDMIC3 (stock 0)
- items share a model: Its Me Privacy Protector iPhone 14 Pro - ITSME-IPHONE14PRO (stock 174.00) | ITSME-IPHONE14 (stock 150.00)
- items share a model: Jun Best Lens Protector iPhone Blacktitanium - JUNBL-IPHONE16PROMAX-BLACK (stock 82.00) | JUNBL-IPHONE15PROMAX-BLACK (stock 28.00)
- items share a model: Jun Best Lens Protector iPhone Golden - JUNBL-IPHONE14PROMAX-GOLD (stock 25.00) | JUNBL-IPHONE12PROMAX-GOLD (stock 8.00)
- items share a model: Matt Privacy Glass Protector iPhone 16 - MATTP-IPHONE15 (stock 22.00) | MATTP-IPHONE16-2 (stock 28.00)
- items share a model: OG Finger Protector Samsung S25 - OGFNG-GALAXYS24-2 (stock 310.00) | OGFNG-GALAXYS25-2 (stock 190.00)
- items share a model: OG Glass Protector Infinix Note 7 - PROT-INFINIX-NOTE7-POVA2 (stock 40.00) | OG G-TECNO-POVA2 (stock 80.00)
- items share a model: OG Glass Protector Oppo A6 - PROT-Y31 (stock 0.00) | OG G-OPPO-A6 (stock 30.00)
- items share a model: OG Glass Protector Oppo A80 - PROT-OPPO-A80-HOT9S (stock 0) | PROT-NOTE9S (stock 180.00)
- items share a model: OG Glass Protector Tecno Pova 2 - PROT-INFINIX-NOTE7-POVA2 (stock 40.00) | OG G-TECNO-POVA2 (stock 80.00)
- items share a model: OG Glass Protector Tecno Spark Go 1 - PROT-SPARKGO1 (stock 500.00) | OG G-INFINIX-SMART9 (stock 500.00)
- items share a model: OG Glass Protector Vivo V20 - OG G-VIVO-F15 (stock 0) | OG G-VIVO-V20 (stock 120.00)
- items share a model: OG Glass Protector iPhone 12 Pro - PROT-APPLE-IP12-IP12PRO (stock 40.00) | OG G-IPHONE-IPHONE12PRO (stock 20.00)
- items share a model: OG Glass Protector iPhone 14 Pro - PROT-APPLE-IP14-IP14PRO (stock 510.00) | OG G-IPHONE-IP14PRO (stock 0)
- items share a model: OG Glass Protector iPhone 15 - PROT-APPLE-IP16-IP15 (stock 160.00) | OG G-IPHONE-IPHONE15 (stock 0)
- items share a model: OG Glass Protector iPhone 16 - PROT-APPLE-IP16-IP15 (stock 160.00) | OG G-IPHONE-IPHONE15 (stock 0)
- items share a model: OG Glass Protector iPhone XS - PROT-APPLE-IPX (stock 150.00) | PROT-APPLE-IPXS-IP11PRO (stock 10.00)
- items share a model: Polish Glass Protector Redmi 13C - POLGL-13C (stock 21.00) | POLGL-A05 (stock 625.00)
- items share a model: Simple Lens Protector iPhone Black - SMPLL-IPHONE13-BLACK (stock 115.00) | SMPLL-IPHONE12PROMAX-BLACK (stock 79.00) | SMPLL-IPHONE11-BLACK (stock 77.00)
- items share a model: Simple Lens Protector iPhone Blue - SMPLL-IPHONE13-BLUE (stock 21.00) | SMPLL-IPHONE12PROMAX-BLUE (stock 21.00) | SMPLL-IPHONE14-BLUE (stock 85.00)
- items share a model: TPU Case Samsung A6+ - TPU-GALAXYA6 (stock 29.00) | TPU -SAMSUNG-J8 (stock 0)
- items share a model: TPU Case Samsung J8 - TPU-GALAXYA6 (stock 29.00) | TPU -SAMSUNG-J8 (stock 0)
- items share a model: TPU Case Vivo V60 - TPU-VIVOV60 (stock 76.00) | TPU-12 (stock 50.00)

## 5. New item codes

Pattern `CATEGORY-BRAND-MODEL[-VARIANT]`. Category codes: OG Glass Protector = `OG`, OG Finger Protector = `OGF`, Dust Plug = `DP`, TPU Case = `TPU`, Membrane Sheet Protector = `MEMB`, Its Me Privacy Protector = `ITSME`, Its Me UV Glass Protector = `ITSUV`, Polish Glass Protector = `POLGL`, Bolt Lens Protector = `BOLT`, Simple Lens Protector = `SMPLL`, Camera Glass Protector = `CAMGL`, Jun Best Lens Protector = `JUNBL`, Matt Privacy Glass Protector = `MATTP`, Simple Privacy Protector = `SMPPV`, UV Glass Protector = `UVGLS`, Dust Proof Privacy Protector = `DPPRV`.

Sample (full old -> new list in `catalog_cleanup_review/skus.csv`):

| Old | New |
|---|---|
| `PROT-OPPO-F11PRO` | `OG-OPPO-F11PRO` |
| `PROT-OPPO-A58` | `OG-OPPO-A58` |
| `PROT-INFINIX-HOT9PLAY` | `OG-INFINIX-HOT9PLAY` |
| `PROT-HUAWEI-Y9PRIME2019` | `OG-HUAWEI-Y9PRIME2019` |
| `PROT-HUAWEI-MATE10LITE` | `OG-HUAWEI-MATE10LITE` |
| `PROT-APPLE-IPX` | `OG-IPHONE-X` |
| `PROT-APPLE-IPXR-IP11` | `OG-IPHONE-XR` |
| `PROT-APPLE-IPXS-IP11PRO` | `OG-IPHONE-XS` |
| `PROT-APPLE-IPXSMAX-IP11PROMAX` | `OG-IPHONE-XSMAX` |
| `PROT-APPLE-IP12-IP12PRO` | `OG-IPHONE-12` |
| `PROT-APPLE-IP12PROMAX` | `OG-IPHONE-12PROMAX` |
| `PROT-APPLE-IP13-IP13PRO` | `OG-IPHONE-13` |
| `PROT-APPLE-IP14-IP14PRO` | `OG-IPHONE-14` |
| `PROT-APPLE-IP14PROMAX` | `OG-IPHONE-14PROMAX` |
| `PROT-APPLE-IP15PRO` | `OG-IPHONE-15PRO` |
| `PROT-APPLE-IP15PROMAX` | `OG-IPHONE-15PROMAX` |
| `PROT-APPLE-IP16-IP15` | `OG-IPHONE-16` |
| `PROT-APPLE-IP16PRO-IP17` | `OG-IPHONE-16PRO` |
| `PROT-APPLE-IP16PROMAX` | `OG-IPHONE-16PROMAX` |
| `PROT-APPLE-IP15PLUS` | `OG-IPHONE-15PLUS` |
| `PROT-APPLE-IP17PRO` | `OG-IPHONE-17PRO` |
| `PROT-APPLE-IP17PROMAX` | `OG-IPHONE-17PROMAX` |
| `PROT-APPLE-IP17AIR` | `OG-IPHONE-17AIR` |
| `PROT-APPLE-IP12MINI` | `OG-IPHONE-12MINI` |
| `PROT-APPLE-IP13MINI` | `OG-IPHONE-13MINI` |
