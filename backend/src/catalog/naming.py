"""Catalog naming standard — pure functions, no database, no framework.

One rule set for how a phone model is written, how two spellings are recognised as the same phone, how an item
code (SKU) is built, and how a sheet's "BRAND/M1/M2" fitment text is read. Used by the catalog service (so new
records follow the standard), by the cleanup script and review report, and by any future import script.

The standard (see CLAUDE.md, "Catalog naming"):
  * Model name: short, brand kept in the brand column — "Y15", "A35", "13C", "12 Pro Max", "S24 Ultra", "14+".
  * One Model row per phone: two spellings with the same `match_key` are the same phone.
  * One Item per (category, brand, primary model, variant); phones taking the same part are the item's
    compatible models, never separate items.
  * SKU: CATEGORY-BRAND-MODEL[-VARIANT], upper-case letters and digits only (e.g. OG-VIVO-Y15, DP-IPHONE-12PRO).

4G / 5G tags are dropped from the standard name ("A36 5G" -> "A36").

Nothing here guesses silently: `canonical_model_name` returns a `NameResult` whose `needs_review` is set when
the text can't be turned into a trustworthy model name (a colour, a fragment, an unknown typo).
"""
import re
from dataclasses import dataclass, field

# Brand column value -> words that may precede the model in free text (and are removed from the model name).
BRAND_PREFIXES: dict[str, tuple[str, ...]] = {
    "iPhone": ("IPHONE", "APPLE", "IP"),
    "Samsung": ("SAMSUNG", "GALAXY", "SAM"),
    "Google Pixel": ("GOOGLEPIXEL", "GOOGLE", "PIXEL"),
    "Vivo": ("VIVO",),
    "Xiaomi": ("XIAOMI", "XM"),  # the line words REDMI / POCO / MI stay in the model name (see _xiaomi_line)
    "Honor": ("HONOR",),
    "Motorola": ("MOTOROLA", "MOTOROLLA", "MOTO"),
    "LG": ("LG",),
    "Infinix": ("INFINIX",),
    "Oppo": ("OPPO",),
    "Tecno": ("TECNO",),
    "OnePlus": ("ONEPLUS", "1PLUS"),
    "Realme": ("REALME",),
    "Huawei": ("HUAWEI",),
    "Itel": ("ITEL",),
}

# Short code used in item codes, per brand column value.
BRAND_CODES: dict[str, str] = {
    "iPhone": "IPHONE", "Samsung": "SAMSUNG", "Vivo": "VIVO", "Xiaomi": "XIAOMI", "Infinix": "INFINIX",
    "Oppo": "OPPO", "Tecno": "TECNO", "Google Pixel": "PIXEL", "OnePlus": "ONEPLUS", "Realme": "REALME",
    "Huawei": "HUAWEI", "Itel": "ITEL", "Honor": "HONOR", "Motorola": "MOTOROLA", "LG": "LG",
}
# The catalog's old brand name "Redmi" is the Xiaomi family; its models are Redmi-line models.
BRAND_ALIASES = {"Redmi": ("Xiaomi", "Redmi")}  # old name -> (current brand, default line)
XIAOMI_LINES = ("Redmi", "Poco", "Mi")

# One short code per category (the old per-importer prefixes — PROT/OG G, DPLUG/DUST, MEMSH/MEMB ... — are retired).
CATEGORY_CODES: dict[str, str] = {
    "OG Glass Protector": "OG", "OG Finger Protector": "OGF", "Dust Plug": "DP", "TPU Case": "TPU",
    "Membrane Sheet Protector": "MEMB", "Its Me Privacy Protector": "ITSME", "Its Me UV Glass Protector": "ITSUV",
    "Polish Glass Protector": "POLGL", "Bolt Lens Protector": "BOLT", "Simple Lens Protector": "SMPLL",
    "Camera Glass Protector": "CAMGL", "Jun Best Lens Protector": "JUNBL", "Matt Privacy Glass Protector": "MATTP",
    "Simple Privacy Protector": "SMPPV", "UV Glass Protector": "UVGLS", "Dust Proof Privacy Protector": "DPPRV",
}

# Words that name a model series; a number glued to one gets a space ("NOTE12" -> "Note 12").
SERIES_WORDS = ("NOTE", "HOT", "SMART", "SPARK", "RENO", "CAMON", "CAMMON", "POVA", "PHANTOM", "FIND", "ZERO", "MI", "POCO", "NORD", "ACE", "HONOR", "NARZO", "IQOO")
# Suffix words, written the same way everywhere.
SUFFIX_WORDS = {
    "PRO": "Pro", "MAX": "Max", "ULTRA": "Ultra", "LITE": "Lite", "MINI": "Mini", "AIR": "Air", "EDGE": "Edge",
    "PLAY": "Play", "PRIME": "Prime", "CORE": "Core", "NEO": "Neo", "FOLD": "Fold", "FLIP": "Flip",
    "XL": "XL", "FE": "FE", "SE": "SE", "GT": "GT", "HD": "HD", "II": "II", "III": "III", "NOTE": "Note",
    "HOT": "Hot", "SMART": "Smart", "SPARK": "Spark", "RENO": "Reno", "CAMON": "Camon", "POVA": "Pova", "MI": "Mi",
    "PHANTOM": "Phantom", "POCO": "Poco", "GO": "Go", "NORD": "Nord", "ACE": "Ace", "HONOR": "Honor", "NARZO": "Narzo", "IQOO": "iQOO", "FIND": "Find", "POWER": "Power",
}
# Spellings we know are typos / abbreviations of a suffix word.
TYPO_WORDS = {"MINNI": "MINI", "ULT": "ULTRA", "ULTR": "ULTRA", "CAMMON": "CAMON", "CAMMOM": "CAMON", "PLUS": "+"}
COLOUR_WORDS = {
    "BLACK", "BLUE", "WHITE", "GOLD", "GOLDEN", "GREY", "GRAY", "RED", "GREEN", "PURPLE", "SILVER", "PINK", "TITANIUM",
    "BLACKTITANIUM", "BLUETITANIUM", "NATURALTITANIUM", "WHITETITANIUM", "DESERTTITANIUM", "ORANGE", "YELLOW",
}
NETWORK_TAGS = {"4G", "5G"}
# Real phone models whose name has no number (confirmed by the owner), so they are not flagged for review.
NUMBERLESS_OK = {"SE", "X", "XR", "XS", "XS MAX", "GT", "GT NEO", "REDMI GT", "REDMI GT NEO", "NOTE EDGE", "RENO Z", "POP LITE", "SPARK GO"}


@dataclass(frozen=True)
class NameResult:
    name: str  # the canonical model name ("" when nothing usable is left)
    needs_review: bool
    reasons: tuple[str, ...] = field(default=())


def _strip_brand_prefix(brand: str, upper: str) -> str:
    """Remove leading brand/series words, also when glued to the model (REDMI13C, IPHONE13)."""
    prefixes = sorted(BRAND_PREFIXES.get(brand, ()) + ("PHONE",), key=len, reverse=True)
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if not upper.startswith(prefix) or len(upper) == len(prefix):
                continue
            rest = upper[len(prefix):]
            attached_ok = (
                rest[0] in " -_.,"
                or rest[0].isdigit()
                or re.match(r"^[A-Z]\d", rest) is not None
                or any(rest.startswith(w) for w in SERIES_WORDS)
            )
            if prefix in ("IP", "RM", "RN", "SAM") and rest[0] not in " -_.,":
                attached_ok = rest[0].isdigit() or any(rest.startswith(w) for w in SERIES_WORDS)
            if attached_ok:
                upper = rest.lstrip(" -_.,")
                changed = True
                break
    return upper


def _split_tokens(upper: str) -> list[str]:
    s = upper.replace("(", " (").replace(")", ") ").replace("+", "+ ")
    # glue splitting: series word + number ("NOTE12"), model digits + suffix word ("12PRO", "S24ULTRA", "9PROXL")
    for word in SERIES_WORDS:
        s = re.sub(rf"\b{word}(?=\d)", f"{word} ", s)
    s = re.sub(r"\b(POCO|NORD|FIND|IQOO|NARZO|HONOR)(?=[A-Z]?\d)", r"\1 ", s)  # POCOM6 -> POCO M6, FINDX8 -> FIND X8, IQOOZ7 -> IQOO Z7
    s = re.sub(r"\b(NORD) (CE|N)(?=\d|LITE|\b)", r"\1 \2", s)
    s = re.sub(r"\bSPARK ?GO(?=\d|\b)", "SPARK GO ", s)  # SPARKGO / SPARKGO1 -> SPARK GO / SPARK GO 1
    s = re.sub(r"(?<=[A-Z])(4G|5G)\b", r" \1", s)  # Y18E4G -> Y18E 4G (a network tag glued after a letter)
    s = re.sub(r"(?<=\d)(CHINA|INDIA|MALAYSIA|GLOBAL)\b|\b(CHINA|INDIA|MALAYSIA|GLOBAL)\b", "", s)  # region is not part of the model
    s = re.sub(r"(?<=\d)(4G|5G)\b", r" \1", s)  # 125G / A324G -> 12 5G / A32 4G (a glued network tag)
    s = re.sub(r"(?<=PRO)(PLUS)\b", r" \1", s)  # NOTE14PROPLUS -> NOTE 14 PRO PLUS
    suffixes = "|".join(sorted((w for w in list(SUFFIX_WORDS) + list(TYPO_WORDS) if w not in ("MI", "GO", "II", "III", "HD", "SE", "GT", "FE", "XL")), key=len, reverse=True))
    s = re.sub(rf"(?<=\d)({suffixes})", r" \1", s)  # 12PRO -> 12 PRO
    s = re.sub(r"(?<=[A-Z])(?=PRO(?:MAX|XL)\b)", " ", s)
    s = re.sub(r"(?<=\bPRO)(MAX|XL)\b", r" \1", s)  # PROMAX -> PRO MAX
    s = re.sub(r"(?<=\d)(FE|XL)\b", r" \1", s)  # S23FE -> S23 FE
    s = re.sub(r"(?<=[A-Z0-9])FINGER\b", " FINGER", s)  # 9PROXLFINGER -> 9PROXL FINGER
    s = re.sub(r"\b(S\d+) ?U\b", r"\1 ULTRA", s)  # S24U / S24 U -> S24 ULTRA (Samsung S-series)
    return [t for t in re.split(r"[\s,/_-]+", s) if t]


def _brand_and_line(brand: str, line: str | None) -> tuple[str, str | None]:
    if brand in BRAND_ALIASES:
        new_brand, default_line = BRAND_ALIASES[brand]
        return new_brand, line or default_line
    return brand, line


def canonical_model_name(brand: str, raw: str, line: str | None = None) -> NameResult:
    """Turn any spelling of a model into the standard short form, or say why it can't be trusted.

    `line` is only used for Xiaomi (Redmi / Poco / Mi / Xiaomi): the product line the text belongs to when the
    text itself doesn't say (a bare "13C" in the old Redmi brand is "Redmi 13C"; a sheet code "XM-14T" is "14T").
    """
    brand, line = _brand_and_line(brand, line)
    reasons: list[str] = []
    upper = re.sub(r"\s+", " ", str(raw or "").strip().upper())
    if not upper:
        return NameResult("", True, ("empty",))
    if brand == "Xiaomi":
        # RMI / RM / RN / HM are all "Redmi" (HM = Hongmi); glued or spaced.
        upper = re.sub(r"^(REDMI|RMI|RM|RN|HM)(?=[A-Z0-9 ])", "REDMI ", upper)
        upper = re.sub(r"^REDMI\s*(?=$)", "REDMI", upper)
    if upper.count("(") != upper.count(")"):
        reasons.append("unbalanced bracket (text cut off)")
    upper = _strip_brand_prefix(brand, upper)
    tokens = _split_tokens(upper)
    if not tokens:
        return NameResult("", True, tuple(reasons + ["nothing left after removing the brand"]))
    if all(t in COLOUR_WORDS for t in tokens):
        return NameResult(" ".join(t.title() for t in tokens), True, tuple(reasons + ["a colour, not a model"]))

    if brand == "Xiaomi":
        tokens = [("Black Shark" if t == "BLACKSHARK" else t) for t in tokens]
        first = tokens[0]
        has_line = first in ("REDMI", "POCO", "MI") or first == "Black Shark"
        if not has_line and line and line != "Xiaomi":
            tokens = [line.upper()] + tokens

    out: list[str] = []
    only_tags = all(t.strip("()") in NETWORK_TAGS for t in tokens)
    for token in tokens:
        if not only_tags and token.strip("()") in NETWORK_TAGS:
            continue  # 4G / 5G is not part of the standard model name ("A36 5G" is the model "A36")
        token = TYPO_WORDS.get(token, token)
        if token == "+":
            if out:
                out[-1] += "+"
            continue
        if token == "REDMI":
            out.append("Redmi")
        elif token in SUFFIX_WORDS:
            out.append(SUFFIX_WORDS[token])
        elif token in NETWORK_TAGS or re.fullmatch(r"\(?\d{4}\)?", token) or any(ch.isdigit() for ch in token):
            out.append(token.strip("()") if token in {f"({t})" for t in NETWORK_TAGS} else token)
        elif token.startswith("(") or token.endswith(")"):
            out.append(token)
        elif len(token) <= 2:
            out.append(token.upper())  # XS, XR, SE ...
            if len(token) == 1 and token != "X":
                reasons.append(f"single letter '{token}' (abbreviation?)")
        else:
            out.append(token.title())
    name = " ".join(out)
    name = re.sub(r"\s+\(", " (", name)
    if only_tags:
        reasons.append("only a network tag (4G/5G), no model")
    if re.search(r"[^A-Za-z0-9+() ]", name):
        reasons.append("unexpected characters")
    if any(t in COLOUR_WORDS for t in tokens):
        reasons.append("contains a colour word (belongs in the item's variant)")
    if "FINGER" in tokens:
        reasons.append("'Finger' is a category (OG Finger Protector), not part of the model")
    if re.search(r"\d+RO(XL)?\b", upper):
        reasons.append("looks like 'Pro' with the P missing")
    if brand == "Xiaomi" and not any(name.startswith(w) for w in (*XIAOMI_LINES, "Black Shark")) and line != "Xiaomi":
        reasons.append("Xiaomi line (Redmi / Poco / Mi) not given")
    if not any(ch.isdigit() for ch in name) and name.upper() not in NUMBERLESS_OK:
        reasons.append("no model number")
    if name.upper() in NUMBERLESS_OK:  # a confirmed real model: "Reno Z" has a single letter and no number on purpose
        reasons = [r for r in reasons if not r.startswith("single letter") and r != "no model number"]
    return NameResult(name, bool(reasons), tuple(reasons))


def match_key(brand: str, name: str, line: str | None = None) -> str:
    """Two spellings of the same phone share a key (case, spaces, brand words, 4G/5G tags ignored)."""
    result = canonical_model_name(brand, name, line)
    tokens = [t for t in re.split(r"\s+", result.name.upper()) if t and t not in NETWORK_TAGS]
    return re.sub(r"[^A-Z0-9+]", "", "".join(tokens))


def _slug(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(text or "").upper().replace("+", "PLUS"))


def build_sku(category: str, brand: str, model_name: str, variant: str | None = None) -> str:
    """CATEGORY-BRAND-MODEL[-VARIANT]; raises KeyError for a category/brand with no code yet (add it above)."""
    brand, line = _brand_and_line(brand, None)
    parts = [CATEGORY_CODES[category], BRAND_CODES[brand], _slug(canonical_model_name(brand, model_name, line).name)]
    if variant and _slug(variant):
        parts.append(_slug(variant))
    return "-".join(parts)


SKU_PATTERN = re.compile(r"^[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+(-[A-Z0-9]+)*$")


def is_standard_sku(sku: str) -> bool:
    return bool(SKU_PATTERN.match(sku or ""))


@dataclass(frozen=True)
class Fitment:
    brands: tuple[str, ...]  # brand column values named in the text (may be 2+ when the text is ambiguous)
    models: tuple[str, ...]  # canonical model names, first = primary
    variants: tuple[str, ...]  # colours / finishes found in the text
    needs_review: bool
    reasons: tuple[str, ...] = ()


_BRAND_WORD_TO_BRAND = {w: b for b, ws in BRAND_PREFIXES.items() for w in ws if w not in ("IP", "SAM", "XM", "PIXEL")}
_BRAND_WORD_TO_BRAND.update({"REDMI": "Xiaomi", "POCO": "Xiaomi"})


def parse_fitment(text: str, default_brand: str | None = None) -> Fitment:
    """Read a sheet fitment text such as "SAMSUNG/A36/A56" or "VIVO/Y15/Y17" into brand(s) + models + colours.

    Slash-separated parts that are brand words set the brand; colour words become variants; every other part
    is a model. When several brands precede the models the text is ambiguous (e.g. "INFINIX/TECNO/HOT11S/CAMMON18":
    Hot 11S is Infinix, Camon 18 is Tecno) and `needs_review` is set so the caller looks each model up per brand.
    """
    parts = [p.strip() for p in re.split(r"[/]", str(text or "")) if p.strip()]
    brands: list[str] = []
    models: list[str] = []
    variants: list[str] = []
    reasons: list[str] = []
    for part in parts:
        key = re.sub(r"[^A-Z0-9+]", "", part.upper())
        if key in _BRAND_WORD_TO_BRAND:
            brand = _BRAND_WORD_TO_BRAND[key]
            if brand not in brands:
                brands.append(brand)
        elif key in COLOUR_WORDS:
            variants.append(part.title())
        else:
            models.append(part)
    if not brands and default_brand:
        brands = [default_brand]
    if len(brands) > 1:
        reasons.append("several brands named - resolve each model against each brand")
    brand_for_names = brands[0] if brands else (default_brand or "")
    canon: list[str] = []
    for raw in models:
        result = canonical_model_name(brand_for_names, raw)
        if result.needs_review:
            reasons.extend(f"{raw}: {r}" for r in result.reasons)
        if result.name and result.name not in canon:
            canon.append(result.name)
    if not brands:
        reasons.append("no brand named")
    return Fitment(tuple(brands), tuple(canon), tuple(variants), bool(reasons), tuple(reasons))


# ---- reading the owner's compatibility workbook ("BRAND-MODEL" codes such as SAM-A324G, RMI-13C, MI-POCOC65) ----

# sheet prefix -> (catalog brand, Xiaomi line implied by the prefix)
SHEET_PREFIXES: dict[str, tuple[str, str | None]] = {
    "VIVO": ("Vivo", None), "SAM": ("Samsung", None), "OPPO": ("Oppo", None), "INF": ("Infinix", None),
    "IP": ("iPhone", None), "TECNO": ("Tecno", None), "RME": ("Realme", None), "REALME": ("Realme", None),
    "RMI": ("Xiaomi", "Redmi"), "HM": ("Xiaomi", "Redmi"), "REDMI": ("Xiaomi", "Redmi"), "RM": ("Xiaomi", "Redmi"),
    "MI": ("Xiaomi", "Mi"), "XIAOMI": ("Xiaomi", "Xiaomi"), "XM": ("Xiaomi", "Xiaomi"), "PIXEL": ("Google Pixel", None),
    "1PLUS": ("OnePlus", None), "ITEL": ("Itel", None), "HUAWEI": ("Huawei", None), "HW": ("Huawei", None),
    "HONOR": ("Honor", None), "MOTOROLLA": ("Motorola", None), "MOTOROLA": ("Motorola", None), "LG": ("LG", None),
}
_KNOWN_WORDS = {v.upper() for v in SUFFIX_WORDS.values()} | {"REDMI", "POCO", "MI", "BLACK SHARK", "PLUS", "5G", "4G"}
_CODE_TOKEN = re.compile(r"^[A-Z]{0,2}\d{1,4}[A-Z]{0,3}\+?$")


def is_plausible_model_name(name: str) -> bool:
    """True when the name is only known words and short model codes (A32, Y91C, 13C, S24) - safe to create automatically."""
    tokens = [t[:-1] if len(t) > 1 and t.endswith("+") else t for t in name.upper().split()]
    return bool(tokens) and all(t in _KNOWN_WORDS or _CODE_TOKEN.match(t) or re.fullmatch(r"\(?\d{4}\)?", t) for t in tokens)


@dataclass(frozen=True)
class SheetPhone:
    brand: str | None
    name: str
    needs_review: bool
    reasons: tuple[str, ...] = ()


def parse_sheet_phone(token: str) -> SheetPhone:
    """'SAM-A324G' -> Samsung 'A32'; 'MI-POCOC65' -> Xiaomi 'Poco C65'; 'HW-HONOR9X' -> Honor '9X'."""
    token = str(token or "").strip()
    if "-" not in token:
        return SheetPhone(None, token, True, ("no brand prefix in the sheet",))
    prefix, rest = token.split("-", 1)
    entry = SHEET_PREFIXES.get(prefix.upper())
    if entry is None:
        return SheetPhone(None, rest, True, (f"unknown brand prefix '{prefix}'",))
    brand, line = entry
    if brand == "Huawei" and re.match(r"^HONOR", rest.upper()):
        brand, line = "Honor", None  # Honor is its own brand (sold by Huawei in 2020)
    result = canonical_model_name(brand, rest, line)
    if result.needs_review or not result.name:
        return SheetPhone(brand, result.name or rest, True, result.reasons or ("unclear",))
    if not is_plausible_model_name(result.name):
        return SheetPhone(brand, result.name, True, ("spelling unclear (check)",))
    return SheetPhone(brand, result.name, False)
