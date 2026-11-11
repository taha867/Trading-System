"""Checks for src/catalog/naming.py using spellings that really exist in the production catalog.

Run with pytest if installed, or directly:  python tests/test_catalog_naming.py   (from backend/)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.catalog.naming import build_sku, canonical_model_name, check_model_name, is_standard_sku, match_key, parse_fitment, parse_sheet_phone  # noqa: E402

# (brand, raw spelling, expected canonical name)
NAME_CASES = [
    ("iPhone", "iPhone 12 Pro", "12 Pro"), ("iPhone", "IP 13 PRO MAX", "13 Pro Max"), ("iPhone", "12PRO", "12 Pro"),
    ("iPhone", "iPhone 14+", "14+"), ("iPhone", "iPhone 14 Plus", "14+"), ("iPhone", "iPhone 12 mini", "12 Mini"),
    ("iPhone", "iPhone 13MINNI", "13 Mini"), ("iPhone", "iPhone XS Max", "XS Max"), ("iPhone", "iPhone X", "X"),
    ("iPhone", "iPhone SE", "SE"), ("iPhone", "iPhone 17 Pro Max", "17 Pro Max"), ("iPhone", "17", "17"),
    ("Samsung", "Galaxy A35", "A35"), ("Samsung", "A35", "A35"), ("Samsung", "Sam S24 Ultra", "S24 Ultra"),
    ("Samsung", "S24U", "S24 Ultra"), ("Samsung", "S24 U", "S24 Ultra"), ("Samsung", "S21 Ultr", "S21 Ultra"),
    ("Samsung", "S23FE", "S23 FE"), ("Samsung", "S23 Fe", "S23 FE"), ("Samsung", "Galaxy S22+", "S22+"),
    ("Samsung", "Galaxy A36", "A36"), ("Samsung", "A36 5G", "A36"), ("Redmi", "14T (5G)", "Redmi 14T"),
    ("Google Pixel", "Pixel 8", "8"), ("Google Pixel", "8", "8"), ("Google Pixel", "9PROXL", "9 Pro XL"),
    ("Google Pixel", "PIXEL 7 PRO", "7 Pro"), ("Google Pixel", "Pixel 9 Pro XL", "9 Pro XL"), ("Google Pixel", "7A", "7A"),
    ("Vivo", "Vivo Y15", "Y15"), ("Vivo", "Y15", "Y15"), ("Vivo", "V70FE", "V70 FE"), ("Vivo", "V50 Lite", "V50 Lite"),
    ("Vivo", "V40LITE", "V40 Lite"), ("Vivo", "Y20i", "Y20I"), ("Samsung", "Galaxy A03s", "A03S"),
    ("Redmi", "REDMI13C", "Redmi 13C"), ("Redmi", "13C", "Redmi 13C"), ("Redmi", "Redmi 14", "Redmi 14"), ("Redmi", "REDMINOTE12", "Redmi Note 12"),
    ("Redmi", "RM NOTE14 PRO PLUS", "Redmi Note 14 Pro+"), ("Redmi", "Redmi NOTE11 Pro", "Redmi Note 11 Pro"), ("Redmi", "REDMIC3", "Redmi C3"), ("Redmi", "Mi Note 10", "Mi Note 10"),
    ("Infinix", "Note50", "Note 50"), ("Infinix", "Note 50", "Note 50"), ("Infinix", "HOT 9", "Hot 9"),
    ("Infinix", "NOTE EDGE", "Note Edge"), ("Samsung", "Galaxy Note Edge", "Note Edge"), ("Oppo", "Reno Z", "Reno Z"), ("Tecno", "Pop Lite", "Pop Lite"),
    ("Tecno", "SPARKGO", "Spark Go"), ("OnePlus", "Ace 5", "Ace 5"),
    ("Oppo", "RENO14", "Reno 14"), ("Oppo", "Reno 14", "Reno 14"), ("Tecno", "CAMMON 30", "Camon 30"),
]

# Spellings that must share one match_key (same phone).
SAME_PHONE = [
    ("Redmi", ["13C", "REDMI13C", "Redmi 13C", "RM13C"]), ("Vivo", ["Y15", "Vivo Y15"]),
    ("Google Pixel", ["8", "Pixel 8", "PIXEL 8"]), ("iPhone", ["12 Pro", "iPhone 12 Pro", "IP 12 PRO", "12PRO"]),
    ("Samsung", ["S24U", "S24 U", "Sam S24 Ultra", "S24 Ultra"]), ("Samsung", ["A35", "Galaxy A35"]),
    ("Infinix", ["Note50", "Note 50"]), ("Oppo", ["RENO13", "Reno 13"]), ("Samsung", ["A36", "A36 5G"]),
]
# Spellings that are NOT the same phone.
DIFFERENT_PHONE = [("iPhone", "12 Pro", "12 Pro Max"), ("Vivo", "V70", "V70 FE"), ("Vivo", "Y15", "Y17"), ("Samsung", "S24", "S24 Ultra")]
# Text that must be flagged for review (colours, fragments) rather than guessed.
REVIEW = [("iPhone", "BLACK"), ("iPhone", "BLACKTITANIUM"), ("Vivo", "V40 Lite (YOUNG"), ("Vivo", "HD5)"), ("Redmi", "REDMI"), ("Samsung", "4G"), ("Redmi", "REDMI")]


def test_canonical_names():
    for brand, raw, expected in NAME_CASES:
        got = canonical_model_name(brand, raw)
        assert got.name == expected, f"{brand} {raw!r}: expected {expected!r}, got {got.name!r}"
        assert not got.needs_review, f"{brand} {raw!r} unexpectedly flagged: {got.reasons}"


def test_same_phone_shares_key():
    for brand, spellings in SAME_PHONE:
        keys = {match_key(brand, s) for s in spellings}
        assert len(keys) == 1, f"{brand}: {spellings} -> {keys}"


def test_different_phones_differ():
    for brand, a, b in DIFFERENT_PHONE:
        assert match_key(brand, a) != match_key(brand, b), f"{brand}: {a!r} and {b!r} must differ"


def test_unclear_text_is_flagged_not_guessed():
    for brand, raw in REVIEW:
        assert canonical_model_name(brand, raw).needs_review, f"{brand} {raw!r} should need review"


def test_sku():
    assert build_sku("OG Glass Protector", "Vivo", "Vivo Y15") == "OG-VIVO-Y15"
    assert build_sku("Dust Plug", "iPhone", "iPhone 12 Pro") == "DP-IPHONE-12PRO"
    assert build_sku("TPU Case", "Samsung", "Galaxy S22+") == "TPU-SAMSUNG-S22PLUS"
    assert build_sku("OG Glass Protector", "iPhone", "15 Pro Max", "Black Titanium") == "OG-IPHONE-15PROMAX-BLACKTITANIUM"
    assert all(is_standard_sku(s) for s in ("OG-VIVO-Y15", "DP-IPHONE-12PRO"))
    assert not is_standard_sku("PROT-VIVO-Y15-Y17 ") and not is_standard_sku("OG G-VIVO-F15")


def test_fitment_text():
    f = parse_fitment("SAMSUNG/A36/A56")
    assert (f.brands, f.models, f.needs_review) == (("Samsung",), ("A36", "A56"), False), f
    f = parse_fitment("VIVO/Y15/Y17")
    assert (f.brands, f.models) == (("Vivo",), ("Y15", "Y17")), f
    f = parse_fitment("APPLE/IP15PROMAX/BLACKTITANIUM")
    assert (f.brands, f.models, f.variants) == (("iPhone",), ("15 Pro Max",), ("Blacktitanium",)), f
    f = parse_fitment("INFINIX/TECNO/HOT11S/CAMMON18")
    assert f.needs_review and f.brands == ("Infinix", "Tecno") and f.models == ("Hot 11S", "Camon 18"), f
    f = parse_fitment("XIAOMI/REDMI10C/REDMI12C")
    assert (f.brands, f.models) == (("Xiaomi",), ("Redmi 10C", "Redmi 12C")), f


# (sheet code, brand, standard name) - the owner's compatibility workbook
SHEET_CASES = [
    ("RMI-12", "Xiaomi", "Redmi 12"), ("RMI-125G", "Xiaomi", "Redmi 12"), ("HM-NOTE14PROPLUS-5G", "Xiaomi", "Redmi Note 14 Pro+"),
    ("MI-POCOM6PRO5G", "Xiaomi", "Poco M6 Pro"), ("MI-11LITE", "Xiaomi", "Mi 11 Lite"), ("XIAOMI-POCOF3", "Xiaomi", "Poco F3"),
    ("XIAOMI-11T", "Xiaomi", "11T"), ("XM-14T-5G", "Xiaomi", "14T"), ("REDMI-NOTE9S", "Xiaomi", "Redmi Note 9S"),
    ("RM-A5-4G", "Xiaomi", "Redmi A5"), ("HW-HONOR9X", "Honor", "9X"), ("HUAWEI-HONORX8", "Honor", "X8"), ("HONOR-8C", "Honor", "8C"),
    ("MOTOROLLA-G24POWER", "Motorola", "G24 Power"), ("LG-K62PLUS", "LG", "K62+"), ("SAM-A324G", "Samsung", "A32"),
    ("RME-C75X", "Realme", "C75X"), ("IP-14PROMAX", "iPhone", "14 Pro Max"), ("INF-HOT6PRO", "Infinix", "Hot 6 Pro"),
    ("VIVO-Y18E4G", "Vivo", "Y18E"), ("1PLUS-ACE5PRO", "OnePlus", "Ace 5 Pro"),
]


def test_sheet_codes():
    for code, brand, name in SHEET_CASES:
        got = parse_sheet_phone(code)
        assert (got.brand, got.name, got.needs_review) == (brand, name, False), f"{code}: {got}"
    for code in ("124G", "V60LITE5G", "VIVO-Y91C2020", "1PLUS-NORDCE3LITE"):
        assert parse_sheet_phone(code).needs_review, f"{code} should be flagged"
    # the same phone written two ways must share a key
    assert match_key("Xiaomi", parse_sheet_phone("RMI-13C").name) == match_key("Redmi", "13C")
    assert build_sku("OG Glass Protector", "Redmi", "13C") == "OG-XIAOMI-REDMI13C"
    assert build_sku("TPU Case", "Honor", "9X") == "TPU-HONOR-9X"


def test_check_model_name_accepts_clear_names_and_refuses_unclear_ones():
    assert check_model_name("Vivo", "Vivo Y15") == ("Y15", None)
    assert check_model_name("iPhone", "iPhone 12 Pro Max") == ("12 Pro Max", None)
    assert check_model_name("Xiaomi", "REDMI13C") == ("Redmi 13C", None)
    assert check_model_name("Xiaomi", "Poco M6 Pro") == ("Poco M6 Pro", None)
    name, problem = check_model_name("Xiaomi", "13C")
    assert problem and "Redmi" in problem, (name, problem)  # the Xiaomi line must be written
    for brand, raw in (("iPhone", "BLACK"), ("Vivo", "V40 Lite (YOUNG"), ("Samsung", "4G"), ("Vivo", "")):
        assert check_model_name(brand, raw)[1], f"{brand} {raw!r} should be refused"
    assert check_model_name("Oppo", "Reno Z")[1] is None  # a confirmed real name without a number


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except AssertionError as exc:
                failed += 1
                print("FAIL", name, "-", exc)
    sys.exit(1 if failed else 0)
