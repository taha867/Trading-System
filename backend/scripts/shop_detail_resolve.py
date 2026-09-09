"""Token -> (brand, model) resolution for the Shop Detail import.

Deliberately conservative: a token is only auto-resolved when a rule matches
with high confidence. Anything else (nested slashes mixing models and
colors, unrecognized abbreviations, "MIX"/"UNIV"/free-text notes) is left
unresolved and reported for manual review rather than guessed -- wrong
brand/model here corrupts real inventory and accounting data.
"""

import re
from dataclasses import dataclass

# Trailing variant/color phrases, longest-first so multi-word ones match
# before their last word alone would. Matched case-insensitively against the
# end of a token; stripped into a shared `variant` for the row.
VARIANT_PHRASES = [
    "NATURAL TITANIUM COSMIC", "DESERT TITANIUM", "BLACK TITANIUM", "WHITE TITANIUM",
    "BLUE TITANIUM", "NATURAL TITANIUM", "SPACE BLACK", "ALPINE GREEN", "PACIFIC BLUE",
    "DEEP PURPLE", "DEEP BLUE", "DESERT BROWN", "T.GREY", "C.BLUE",
    "BLACK", "WHITE", "SILVER", "BLUE", "GOLD", "GOLDEN", "PURPLE", "ORANGE",
    "GREEN", "GREY", "GRAY", "RED", "PINK", "YELLOW", "DESERT", "BURGUNDY", "BROWN",
]

# Ordered (regex, brand) prefix/pattern rules. First match wins. `\b` boundaries
# so e.g. "S1" doesn't match a stray "S" rule meant for "S24".
BRAND_PATTERNS: list[tuple[str, str]] = [
    (r"^\d{1,2}\s*C\b", "Redmi"),  # 10C/12C/13C/14C/15C/"13 C" -- Redmi's C-series, before the bare-iPhone fallback
    (r"^C\d{1,3}\b", "Redmi"),  # bare "C51" -- same C-series, R-prefix dropped
    (r"^(IPH|IP)(?=\d|\s|-)", "iPhone"),  # lookahead, not \b -- "IP13"/"IPH-XR" have no word-boundary before the rest
    (r"^1P(?=\d|\s)", "iPhone"),  # OCR/typo for "IP" seen in JUN BEST LENZ
    (r"^SAM(SUNG)?\s+", "Samsung"),
    (r"^SM\s*A\d", "Samsung"),
    (r"^S\d{1,2}(\s|$|\+|U|FE)", "Samsung"),  # S21, S24U, S23FE, S21+
    (r"^J\d", "Samsung"),  # old Galaxy J-series: J2, J6, J7 Prime, J510
    (r"^OPP?O?\s", "Oppo"),  # OP/OPP/OPPO, all seen as spelling variants in this sheet
    (r"^RENO", "Oppo"),
    (r"^F\d{2}", "Oppo"),  # F11, F19 (Oppo's F-series)
    (r"^A\d{1,2}[A-Z]?(/|$|\s)", None),  # Ambiguous Samsung/Oppo A-series -- resolved by caller via DB lookup
    (r"^INF(INIX)?\s+", "Infinix"),
    (r"^HOT", "Infinix"),  # no \b -- "HOT9" has no boundary between T and 9
    (r"^ZERO\d", "Infinix"),
    (r"^SMART\s*\d", "Infinix"),
    (r"^NOTE\s*\d", "Infinix"),  # this sheet always prefixes Redmi's Note (RM/RN NOTE##) -- bare "Note" is Infinix's own convention
    (r"^SPARK", "Tecno"),
    (r"^CAM(ON)?\s*\d", "Tecno"),
    (r"^1\+", "OnePlus"),
    (r"^PIX(EL)?\b", "Google"),
    (r"^REDMI\s+", "Redmi"),
    (r"^R[MNC]?\s*\d", "Redmi"),
    (r"^MI\s+", "Redmi"),  # "MI Note 10" / "MI 15C" -- Xiaomi folded into Redmi (see brand cleanup)
    (r"^XM\s+", "Redmi"),
    (r"^MATE\s*\d", "Huawei"),
    (r"^P\d{1,3}\b", "Huawei"),  # Huawei's own P-series (P10 Lite, ...)
    (r"^VIVO\s+", "Vivo"),
    (r"^Y\d{1,3}[A-Z]?(\s|$|/)(?!.*PRIME)", "Vivo"),
    (r"^Y\d.*PRIME", "Huawei"),  # "Y9 Prime" is Huawei's naming; Vivo's Y-series never uses "Prime"
    (r"^V\d{2,3}", "Vivo"),
    (r"^X\d{3}", "Vivo"),  # X300, X200FE
]

# This whole workbook's own convention: an iPhone model is written as a BARE
# number (generation), with only these words/symbols as suffixes -- every
# other brand always carries an explicit letter prefix (S/A/SM/OP/HOT/...).
# So "17 PRO MX", "16+", "12 MINI", "14 PRO" with nothing else in the token
# are iPhone by this sheet's own convention, not a guess.
IPHONE_SUFFIX_WORDS = {"PRO", "MAX", "MX", "MINI", "PLUS", "AIR", "P"}


def expand_glued_suffixes(s: str) -> str:
    """'13PROMX' and '12PRO MX' both mean 'Pro Max' -- collapse the glued
    'PROMX' spelling to two words before anything tries to tokenize it, or
    'PROMX' reads as one unrecognized word instead of PRO + MX."""
    return s.upper().replace("PROMX", "PRO MX")


def looks_like_bare_iphone(token: str) -> bool:
    # split digit-runs and letter-runs separately -- "12PRO" must become
    # ["12", "PRO"], not one opaque alnum blob, or "PRO" never gets checked
    # against IPHONE_SUFFIX_WORDS.
    words = re.findall(r"\d+\+?|[A-Z]+", expand_glued_suffixes(token))
    if not words:
        return False
    has_number = False
    for w in words:
        core = w.rstrip("+")
        if core.isdigit():
            has_number = True
            continue
        if w not in IPHONE_SUFFIX_WORDS:
            return False
    return has_number


def normalize_iphone_model(raw: str) -> str:
    t = re.sub(r"\s+", " ", raw.upper().strip())
    t = re.sub(r"^(IPH|IP|1P)[\s-]*", "", t)  # try the longer "IPH" alternative first
    t = re.sub(r"(\d)G\b", r"\1", t)  # "6G"/"7G" -- colloquial for the base model, not a separate "G" part
    # Only split a digit away from a recognized SUFFIX word when glued
    # ("13PROMX" -> "13 PROMX") -- a generic digit/letter split would also
    # wrongly break real compound model numbers like "6S" into "6 S".
    t = re.sub(r"(\d)(PROMX|PRO|MAX|MINI|PLUS|AIR|MX)\b", r"\1 \2", t)
    t = t.replace("PROMX", "PRO MAX")
    t = re.sub(r"\bMX\b", "MAX", t)
    t = re.sub(r"\bP MAX\b", "PRO MAX", t)
    t = re.sub(r"\bP\b(?!\s*MAX)", "PRO", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Title-case each suffix word consistently, regardless of how the source
    # spelled it ("PRO"/"Pro"/"pro" all become "Pro") -- "mini" is the one
    # exception, matching this catalog's existing lowercase convention.
    keep_upper = {"X", "XR", "XS"}
    words = [
        w if (w in keep_upper or not w.isalpha()) else ("mini" if w == "MINI" else w.capitalize())
        for w in t.split(" ")
    ]
    t = " ".join(words)
    return f"iPhone {t}".strip()

# Bare tokens with no numeric/brand prefix at all -- iPhone's own naming
# (X, XR, XS, XS Max, XSMAX) has no letter prefix in this sheet.
BARE_IPHONE_MODELS = {"X", "XR", "XS", "XSMAX", "XS MAX", "XSMAX MAX"}

# Tokens that are never real models -- free-text notes, placeholders, or
# admissions of missing/unclear data from the source sheet itself.
JUNK_MARKERS = ("MIX", "UNIV", "TOP MODEL", "NOT WRITTEN", "NOT CONFIRMED", "PAVIOUR")


@dataclass
class Resolution:
    brand: str | None
    model: str
    variant: str | None
    note: str


def strip_variant(token: str) -> tuple[str, str | None]:
    t = token.strip()
    for phrase in VARIANT_PHRASES:
        if t.upper().endswith(phrase):
            base = t[: -len(phrase)].strip()
            if base:
                return base, phrase.title()
    return t, None


def is_junk(token: str) -> bool:
    upper = token.upper()
    return any(marker in upper for marker in JUNK_MARKERS)


def strip_parenthetical(token: str) -> tuple[str, str | None]:
    m = re.search(r"\s*\(([^)]*)\)\s*$", token)
    if not m:
        return token, None
    return token[: m.start()].strip(), m.group(1).strip()


def canonical_key(s: str) -> str:
    return re.sub(r"[\s.\-]", "", s.upper())


CLEAN_PREFIXES = ("Galaxy ", "iPhone ")
# Pre-existing data-quality issue in this catalog (predates this import):
# several iPhone models exist twice -- once cleanly ("iPhone 15 Pro") and
# once as leftover raw sheet abbreviations ("IP 15 PRO", or even "IP
# 13/13 PRO/13 PRO MAX" with the slash baked into the name itself). Matching
# on these must prefer the clean form so this import doesn't propagate the
# dirty one further; the underlying duplicate rows are a separate cleanup,
# flagged in this script's summary, not fixed here.
DIRTY_PREFIXES = ("IP ", "SM ")


def is_clean_model_text(model: str) -> bool:
    return "/" not in model and not model.startswith(DIRTY_PREFIXES)


def candidate_keys(text: str) -> set[str]:
    """All canonical forms worth trying for a piece of text -- the text as-is,
    plus with a leading brand-name/abbreviation prefix stripped. Used
    identically for indexing catalog model names AND for querying an
    incoming sheet token, so a query like 'IP15 PRO' also tries the
    prefix-stripped key '15PRO' -- the same key a clean 'iPhone 15 Pro'
    catalog entry registers under -- instead of only ever finding whichever
    dirty entry happens to share its own literal abbreviated spelling."""
    keys = {canonical_key(text)}
    for prefix in CLEAN_PREFIXES + DIRTY_PREFIXES:
        if text.startswith(prefix):
            keys.add(canonical_key(text[len(prefix):]))
    return keys


def build_catalog_index(catalog: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """canonical model text -> [(brand, exact_model_name), ...], keyed by every
    candidate_keys() form so a bare sheet token like 'A20' matches 'Galaxy A20'."""
    index: dict[str, list[tuple[str, str]]] = {}
    for row in catalog:
        brand, model = row["brand"], row["model"]
        for key in candidate_keys(model):
            index.setdefault(key, []).append((brand, model))
    return index


def pick_best_match(matches: list[tuple[str, str]]) -> tuple[str, str] | None:
    """Given same-brand candidates for one canonical key, prefer a clean
    model string over a dirty leftover-abbreviation one. Returns None if
    genuinely ambiguous (no single best pick)."""
    clean = [m for m in matches if is_clean_model_text(m[1])]
    if len(clean) == 1:
        return clean[0]
    if len(clean) > 1:
        # A second pre-existing duplication pattern: an ALL-CAPS orphan-ish
        # spelling alongside the properly Title-Cased one ("PIXEL 8" vs
        # "Pixel 8") -- both pass is_clean_model_text, so narrow further to
        # whichever has real lowercase letters (this catalog's dominant style).
        properly_cased = [m for m in clean if any(c.islower() for c in m[1])]
        if len(properly_cased) == 1:
            return properly_cased[0]
        return None  # still ambiguous -- don't guess
    return matches[0] if len(matches) == 1 else None


def resolve_token(raw_token: str, catalog_index: dict | None = None) -> Resolution:
    token = raw_token.strip()
    if not token:
        return Resolution(None, raw_token, None, "empty token")
    if "/" in token:
        return Resolution(None, raw_token, None, "nested slash -- split upstream should have handled this; flag for manual review")
    if is_junk(token):
        return Resolution(None, raw_token, None, "junk/placeholder marker (MIX/UNIV/etc.) -- source data admits this is unclear")

    token, paren_note = strip_parenthetical(token)
    base, variant = strip_variant(token)
    if paren_note:
        variant = f"{variant} ({paren_note})" if variant else paren_note
    upper = base.upper().strip()

    catalog_matches: list[tuple[str, str]] = []
    if catalog_index is not None:
        seen = set()
        for key in candidate_keys(upper):
            for m in catalog_index.get(key, []):
                if m not in seen:
                    seen.add(m)
                    catalog_matches.append(m)
        if catalog_matches:
            distinct_brands = {b for b, _ in catalog_matches}
            if len(distinct_brands) == 1:
                best = pick_best_match(catalog_matches)
                if best:
                    return Resolution(best[0], best[1], variant, "matched existing catalog")
                # same brand, multiple spellings, no clear winner -- pattern
                # rules below have no more context to add here either, so
                # this is the final answer, not a fall-through case.
                return Resolution(
                    None, base, variant,
                    f"ambiguous -- multiple differently-spelled catalog entries for the same brand: {catalog_matches}",
                )
            # Cross-brand ambiguity (e.g. bare "A54" is both a Samsung and an
            # Oppo model) -- fall through to the explicit-prefix pattern
            # rules below, which may have context the bare catalog text
            # doesn't (e.g. an "SM"/"IP" prefix the token still carries).

    if upper in BARE_IPHONE_MODELS:
        return Resolution("iPhone", normalize_iphone_model(upper), variant, "bare iPhone model name")

    for pattern, brand in BRAND_PATTERNS:
        if re.match(pattern, upper):
            if brand is None:
                break  # pattern itself is ambiguous too -- nothing more to try
            # Pattern resolved a brand with more context than the catalog
            # lookup had -- prefer the catalog's exact spelling for that
            # specific brand if one of the earlier matches was for it.
            same_brand = [m for m in catalog_matches if m[0] == brand]
            if same_brand:
                best = pick_best_match(same_brand)
                if best:
                    return Resolution(best[0], best[1], variant, "matched pattern, exact spelling from catalog")
            model = normalize_iphone_model(upper) if brand == "iPhone" else normalize_model(brand, upper)
            return Resolution(brand, model, variant, "matched pattern")

    if catalog_matches:
        distinct_brands = sorted({b for b, _ in catalog_matches})
        return Resolution(None, base, variant, f"ambiguous -- exists in catalog under multiple brands: {distinct_brands}")

    if looks_like_bare_iphone(upper):
        return Resolution("iPhone", normalize_iphone_model(upper), variant, "bare-number iPhone convention")

    return Resolution(None, base, variant, "no pattern matched")


# Per-brand text this catalog's existing models never spell out -- the
# brand's own identity, since Brand is already a separate column/FK. Bare
# leading abbreviations get dropped entirely; these three get expanded
# instead, because this catalog's established models spell the sub-line out
# in full ("Camon 50", "Pixel 8A") rather than using the sheet's shorthand.
REDUNDANT_PREFIXES = {
    "Oppo": [r"^OPP?O?\s+"],
    "Redmi": [r"^(MI|XM|RM|RN)\s+"],
    "OnePlus": [r"^1\+\s*"],
    "Infinix": [r"^INF(INIX)?\s+"],
}
EXPAND_PREFIXES = {
    "Google": [(r"^PIX(EL)?\s+", "Pixel ")],
    "Tecno": [(r"^CAM\s+", "Camon "), (r"^CAM(?=\d)", "Camon ")],
}


def normalize_model(brand: str, upper: str) -> str:
    """Best-effort cleanup toward each brand's established spelling
    convention in this catalog. Not exhaustive -- a mildly redundant name
    (e.g. a leftover abbreviation this function doesn't yet know about) is a
    cosmetic issue the shop owner can fix later via the UI; it never affects
    which brand/quantity/cost gets recorded.
    """
    s = re.sub(r"\s+", " ", upper).strip()
    s = s.replace("PRO MX", "PRO MAX").replace("P MX", "PRO MAX").replace("PROMX", "PRO MAX")
    s = re.sub(r"\bMX\b", "MAX", s)

    for pattern, replacement in EXPAND_PREFIXES.get(brand, []):
        s = re.sub(pattern, replacement, s)
    for pattern in REDUNDANT_PREFIXES.get(brand, []):
        s = re.sub(pattern, "", s)
    s = re.sub(r"(\d)([A-Z])", r"\1 \2", s) if brand == "Infinix" and re.match(r"^NOT\d", s) else s
    s = re.sub(r"^NOT(?=\s|\d)", "Note", s)  # "NOT 50"/"NOT50" -> "Note 50" (Infinix)

    words = [w.capitalize() if w.isalpha() and w not in ("MX",) else w for w in s.split(" ")]
    return " ".join(words)
