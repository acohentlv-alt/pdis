"""
Tel Aviv neighborhood canonical taxonomy + alias normalization.

Master source for neighborhood spelling normalization across PDIS. The FB
ingest prompt (vm-scraper/llm_parse.py) has its own copy of CANONICAL_TLV
for the Haiku extraction prompt (that file can't import server-side code) —
keep the two lists in sync if either changes.

Leaf module: stdlib imports only, no DB, no other pdis.* imports.
"""

from __future__ import annotations

# The 32 canonical Hebrew neighborhood names used in the FB extraction prompt
# (vm-scraper/llm_parse.py:43-47). Kept in sync manually — this module is the
# master; that prompt list is a copy for the Haiku system prompt.
CANONICAL_TLV: list[str] = [
    "פלורנטין", "נווה צדק", "כרם התימנים", "לב תל אביב", "הצפון הישן", "הצפון החדש",
    "יפו העתיקה", "יפו", "שפירא", "שבזי", "נווה אביבים", "רמת אביב", "תל ברוך", "חובבי ציון",
    "מונטיפיורי", "דיזנגוף", "רוטשילד", "בצלאל", "ביצרון", "יד אליהו", "הרב קוק", "בבלי",
    "כוכב הצפון", "אזורי חן", "גורדון", "בן יהודה", "רבין", "נחלת בנימין", "שוק הכרמל",
    "נחלאות", "מרכז העיר",
    "הצפון",  # Ambiguous: could mean הצפון הישן or הצפון החדש. Kept for FB-prompt
              # compat only — NEVER use as an ALIASES target (see assert below).
]

# Variant Hebrew spelling/sub-area string -> normalized canonical string.
# TLV strings only. Exact-string matches ONLY — no fuzzy matching. Derived
# from a read-only SELECT DISTINCT neighborhood, COUNT(*) FROM properties
# against the live DB (2026-07-08), scoped to address_city = 'תל אביב יפו'
# to avoid misclassifying same-named neighborhoods in other cities (Haifa's
# הדר הכרמל/אחוזה, Kiryat Chaim, etc. are intentionally left unmapped here).
# Only variants with meaningful row counts are covered; 1-row oddities are
# left unmapped rather than guessed.
ALIASES: dict[str, str] = {
    # הצפון הישן (Old North) — directional / sub-area splits
    "הצפון הישן - צפון": "הצפון הישן",
    "הצפון הישן - דרום": "הצפון הישן",
    "הצפון הישן החלק הצפוני": "הצפון הישן",
    "הצפון הישן החלק הדרום מזרחי": "הצפון הישן",
    "הצפון הישן החלק הדרום מערבי": "הצפון הישן",
    "הצפון הישן החלק המרכזי": "הצפון הישן",

    # הצפון החדש (New North) — directional / sub-area splits
    "הצפון החדש - כיכר המדינה": "הצפון החדש",
    "הצפון החדש סביבת כיכר המדינה": "הצפון החדש",
    "הצפון החדש - דרום": "הצפון החדש",
    "הצפון החדש - צפון": "הצפון החדש",
    "הצפון החדש החלק הדרומי": "הצפון החדש",
    "הצפון החדש החלק הצפוני": "הצפון החדש",

    # נוה/נווה (defective vs full spelling) doublets
    "נוה שאנן": "נווה שאנן",
    "נוה אביבים": "נווה אביבים",
    "נוה שרת": "נווה שרת",
    "נוה חן": "נווה חן",

    # לב תל אביב — compound variant
    "לב תל אביב, לב העיר צפון": "לב תל אביב",
    "לב תל אביב החלק המערבי": "לב תל אביב",

    # מרכז העיר — directional splits
    "מרכז העיר צפון": "מרכז העיר",
    "מרכז העיר דרום": "מרכז העיר",

    # קרית/קריית (defective vs full spelling)
    "קריית שלום": "קרית שלום",

    # Geresh (') punctuation variants of the same sub-area name
    "רמת אביב ג": "רמת אביב ג'",
    "נאות אפקה ב": "נאות אפקה ב'",
}

# Import-time guard: no canonical target may itself be an alias key —
# alias chains are forbidden (A -> B -> C would silently under-normalize).
assert not (set(ALIASES.values()) & set(ALIASES.keys())), "alias chains forbidden"

# Neighborhoods inside Maison Tel Aviv's target turf (used by Exec B's
# lead-routing/turf logic; defined here since neighborhoods.py is the
# canonical taxonomy module).
MAISON_TURF: set[str] = {
    "הצפון הישן", "הצפון החדש", "בבלי", "כוכב הצפון",
    "אזורי חן", "נווה אביבים", "רמת אביב", "תל ברוך",
}


def normalize_neighborhood(name: str | None) -> str | None:
    """Normalize a raw neighborhood string to its canonical spelling.

    None-safe. Strips whitespace, does an exact alias lookup, and falls back
    to the (stripped) input unchanged if there's no known alias — including
    for non-TLV neighborhoods, which this module never touches.
    """
    if name is None:
        return None
    stripped = name.strip()
    if not stripped:
        return stripped
    return ALIASES.get(stripped, stripped)
