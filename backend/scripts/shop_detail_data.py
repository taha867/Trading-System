"""Raw sheet layout + rate lookups for the Shop Detail import.

Kept separate from the parsing/resolution logic (resolve.py) so the two can
be reviewed independently: this file only describes *what the workbook
contains*, resolve.py decides *what it means*.
"""

XLSX_PATH = "/home/m-taha/Desktop/upwork/shakeel accesories/Shop Detail.xlsx"

# Sheet name -> new Category name. "OG GLASS" already exists as "OG Glass
# Protector" in the catalog (234 items, seeded from a different source
# ledger) -- reuse that exact name so rows resolve to the same Category.
SHEET_TO_CATEGORY = {
    "OG GLASS": "OG Glass Protector",
    "OG FINGER": "OG Finger Protector",
    "TPU": "TPU Case",
    "DUST PLUG": "Dust Plug",
    "POLISH GLASS": "Polish Glass Protector",
    "BOLT LENZ": "Bolt Lens Protector",
    "SIMPLE LENS": "Simple Lens Protector",
    "MEMBRANE SHEET": "Membrane Sheet Protector",
    "CAMERA GLASS": "Camera Glass Protector",
    "CLEAR BODER LESS GLASS": "Clear Borderless Glass Protector",
    "FUL COVER BBODER GLASS": "Full Cover Bordered Glass Protector",
    "JUN BEST LENZ": "Jun Best Lens Protector",
    "UV GLASS SIMPLE": "UV Glass Protector",
    "MATT PRIVACY GLASS": "Matt Privacy Glass Protector",
    "DUST PROOF PRIVACY": "Dust Proof Privacy Protector",
    "SIMPLE PRIVACY": "Simple Privacy Protector",
    "ITS ME PRIVACY": "Its Me Privacy Protector",
}

# Sheets whose layout is (PRODUCT/BRAND, MODEL, RECEIVED PCS) -- brand given
# directly in column 1, no Mohin/Shakeel split columns at all yet.
BRAND_COLUMN_SHEETS = {"DUST PLUG", "TPU"}

# Category name -> average PKR rate, transcribed from the `Shop Detail`
# summary sheet's RATE column (keyed by that sheet's own PRODUCT label).
CATEGORY_AVG_RATE = {
    "Its Me Privacy Protector": 57.88,
    "Simple Privacy Protector": 71.66,
    "Dust Proof Privacy Protector": 140.79,
    "Matt Privacy Glass Protector": 170.32,
    "Camera Glass Protector": 65.36,
    "Simple Lens Protector": 50.23,  # summary sheet calls this product "SIMPLE CAMERA LENZ"
    "Clear Borderless Glass Protector": 51.0,
    "Full Cover Bordered Glass Protector": 68.0,
    "Bolt Lens Protector": 127.96,
    "Membrane Sheet Protector": 57.31,
    "OG Glass Protector": 48.22,
    "OG Finger Protector": 84.21,
    "UV Glass Protector": 88.44,
    "Jun Best Lens Protector": 153.46,  # avg of IPH(153.46)/SAM(272.88) sub-lines; see NOTE below
    "Polish Glass Protector": 22.01,
    "TPU Case": 66.04,
    "Dust Plug": 82.51,
}

# NOTE: the summary sheet actually splits "JUN BEST LENZ" into two separate
# rate rows -- IPH lenz at 153.46, SAM lenz at 272.88 -- because the Samsung
# lens is a materially different (pricier) product. Use per-product-label
# rates for this one category instead of a single average.
JUN_BEST_LENZ_RATES = {
    "JUN BEST LENZ IPH": 153.46,
    "JUN BEST LENZ SAM": 272.88,
}

# Rows whose first cell (PRODUCT / PRODUCT-BRAND column) marks a non-data
# line to skip entirely -- totals, subtotals, free-text notes.
SKIP_PRODUCT_PREFIXES = (
    "TOTAL",
    "GRAND TOTAL",
    "NOTE:",
)
SKIP_PRODUCT_SUFFIXES = ("SUBTOTAL",)
SKIP_PRODUCT_EXACT = {
    "EXTRA STOCK - GODAM MIXUP (not part of original shop stock)",
}

# Hand-resolved exceptions the general resolver correctly declines to guess --
# typos, sheet-context-only cases, or genuinely ambiguous bare numbers where
# the surrounding sheet content makes the real answer clear. Keyed by the
# raw token exactly as it appears (post "/"-split, pre variant-stripping).
# Mirrors seed_protectors.py's own precedent of hand-confirming exceptions
# rather than encoding one-off cases as general regex rules.
TOKEN_OVERRIDES = {
    "RDMI 12": ("Redmi", "12"),  # typo for "REDMI 12"
    "RDNMI NOTE 12": ("Redmi", "Note 12"),  # typo for "REDMI NOTE 12"
    "A16": ("Samsung", "Galaxy A16"),  # 2025 Galaxy A-series, not yet in catalog; no Oppo A16 exists
    "A17": ("Samsung", "Galaxy A17"),
    "A26": ("Samsung", "Galaxy A26"),
    "A35": ("Samsung", "Galaxy A35"),  # matches the catalog's existing "Galaxy A35" exactly
    "GO 1": ("Tecno", "Spark Go 1"),  # confirmed with the user: Tecno's "Spark Go 1"
    "GO1": ("Tecno", "Spark Go 1"),
    "PAVIOUR 4": ("Tecno", "Paviour 4"),  # confirmed with the user: a Tecno model
    # 2026-09-10 batch -- bare iPhone shorthand the resolver's patterns don't
    # cover (no digit run to anchor on, unlike "IP13"/"IP15").
    "IPX": ("iPhone", "iPhone X"),
    "IPXR": ("iPhone", "iPhone XR"),
    "IPXS MAX": ("iPhone", "iPhone XS Max"),
    "S24 U": ("Samsung", "Galaxy S24 Ultra"),  # "U" = Ultra, confirmed with the user
    "S25 U": ("Samsung", "Galaxy S25 Ultra"),
    "A7 2017": ("Samsung", "Galaxy A7 (2017)"),
    "HONOR 9 LITE": ("Huawei", "Honor 9 Lite"),  # confirmed with the user: Huawei brand, not a separate Honor brand
    # No override needed for the sheet's "MATE10 LITE" -- the existing
    # r"^MATE\s*\d" -> "Huawei" pattern below already resolves it (confirmed
    # with the user: Huawei brand).
    "NOTE EDGE": ("Samsung", "Galaxy Note Edge"),
}

# Sheets where a bare ambiguous number (matches both an existing Redmi model
# and an existing iPhone model, e.g. "12", "15") should default to iPhone --
# these are camera-lens/membrane-screen-protector categories where every
# other row in the sheet is unambiguously iPhone.
IPHONE_DEFAULT_SHEETS = {"CAMERA GLASS", "MEMBRANE SHEET", "BOLT LENZ", "SIMPLE LENS", "MATT PRIVACY GLASS"}

# Exact DB brand spelling for each DUST PLUG/TPU section header -- NOT
# `.title()`, which mangles "IPHONE" -> "Iphone" instead of the catalog's
# actual "iPhone". `None` means "don't trust this header as a single brand" --
# "DAMAG YELLOW PCS" mixes a Redmi and an Infinix model under one heading, so
# rows under it must be resolved per-token instead of inheriting a brand.
BRAND_HEADER_ALIASES = {
    "IPHONE": "iPhone",
    "REDMI": "Redmi",
    "REDMI/XIAOMI": "Redmi",
    "TECHNO": "Tecno",
    "INFINIX": "Infinix",
    "VIVO": "Vivo",
    "OPPO": "Oppo",
    "SAMSUNG": "Samsung",
    "ONEPLUS": "OnePlus",
    "REALME": "Realme",
    "PIXEL": "Google",
    "ITEL": "Itel",
    "DAMAG YELLOW PCS": None,
}

# Nothing currently excluded -- the two prior unknowns (GO 1/GO1, PAVIOUR 4)
# were confirmed with the user and moved to TOKEN_OVERRIDES above.
EXCLUDED_TOKENS: set[str] = set()
