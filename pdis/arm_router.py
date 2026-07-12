"""
Maison Tel Aviv lead-arm routing — suggests which "arm" (Amit, Roi, Eliyahu,
Alan) a flagged property_leads row should go to. Pure function, no DB calls.
"""

from __future__ import annotations

# Deliberately NOT importing CONDITION_KEYWORDS from pdis/signals.py (8 items).
# That list also includes דורש ריענון / טעון ריענון (cosmetic refresh), which
# must NOT route a lead to Roi (major-renovation contractor) — only the 6
# phrases below unambiguously indicate the property needs real construction
# work. Justified duplication, not an oversight.
HEAVY_RENOVATION_KEYWORDS = {
    "דרוש שיפוץ",   # needs renovation
    "צריך שיפוץ",   # requires renovation
    "לשיפוץ",       # for renovation
    "דורש שיפוץ",   # demands renovation
    "טעון שיפוץ",   # in need of renovation
    "דירת סבתא",    # grandma apartment (always = old/untouched)
}


def suggest_arm(
    prop: dict,
    signal_details: dict,
    operator_input: dict | None,
) -> tuple[str, list[str]]:
    """Suggest which arm a property_leads row should route to.

    Rules, first match wins:
      R1: forsale + heavy renovation signal -> roi
      R2: forsale + Amit-fit buyer tag -> amit
      R3: forsale, otherwise -> eliyahu
      R4: rent -> alan

    Returns (suggested_arm, reasons) where reasons are plain-English strings.
    """
    category = prop.get("category")
    operator_input = operator_input or {}
    signal_details = signal_details or {}

    reasons: list[str] = []

    condition_keywords_found = set(signal_details.get("condition_keywords_found") or [])
    has_heavy_keyword = bool(condition_keywords_found & HEAVY_RENOVATION_KEYWORDS)
    operator_condition = operator_input.get("condition")
    needs_renovation = has_heavy_keyword or operator_condition == "Needs Renovation"

    buyer_fit_tags = signal_details.get("buyer_fit_tags") or []
    is_amit_fit = "below_amit_target" in buyer_fit_tags or "close_to_amit_target" in buyer_fit_tags

    if category == "forsale" and needs_renovation:
        arm = "roi"
        reasons.append("Major renovation needed")
    elif category == "forsale" and is_amit_fit:
        arm = "amit"
        reasons.append("Fits Amit's buy target")
    elif category == "forsale":
        arm = "eliyahu"
        reasons.append("For-sale, no other arm match")
    else:
        arm = "alan"
        reasons.append("Rental listing")

    if prop.get("is_agent"):
        reasons.append("Listed via agent")

    raw_data = prop.get("raw_data") or {}
    if isinstance(raw_data, dict) and raw_data.get("fb_intent") == "building_forsale":
        reasons.append("Whole building for sale")

    return arm, reasons
