"""Claude Haiku 4.5 structured extraction for Hebrew FB rental posts.

Cost at ~350 tokens in + 150 tokens out per post:
  input: 350 × $1/MTok = $0.00035  (or $0.000035 if cached)
  output: 150 × $5/MTok = $0.00075
  total: ~$0.001/post uncached, ~$0.0008/post cached

With prompt caching on the system prompt, a daily batch of 70 posts costs
about $0.05/run or ~$1.50/mo. Well under the $2/mo budget.
"""
from __future__ import annotations

import json
import os
import re
from anthropic import Anthropic


_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPT = """You extract structured real-estate info from Hebrew Facebook posts in TLV rental/sale groups.

Return ONLY a JSON object with these fields (null if not in text — NEVER invent):
- intent: "rent" | "apartment_forsale" | "building_forsale" | "wanted" | "other"
  * "rent" — landlord or tenant offering/seeking a rental
  * "apartment_forsale" — single apartment for sale
  * "building_forsale" — entire building or multi-unit asset for sale
  * "wanted" — someone searching for a property to rent or buy (NOT the landlord)
  * "other" — anything unrelated (commercial, parking only, shout-outs, etc.)
- price_ils: integer NIS or null
  * For rent: monthly rent amount
  * For sale: total purchase price
  * CRITICAL: Do NOT return sqm as price. Do NOT return price-per-sqm as price.
  * Do NOT return ארנונה / ועד בית / פיקדון / דמי תיווך / חניה / מחסן / חשמל / מים
    as the price. If the only number looks like one of those fees, return null.
- sqm_net: integer — net interior area in square meters, or null
- sqm_balcony: integer — balcony/porch area in square meters, or null
  (extract separately from text like "50 מ״ר + מרפסת 10")
- rooms: float (half-rooms allowed: 2.5, 3.5) or null
- phone: string (Israeli mobile, digits only, e.g. "0521234567") or null
- street_address: Hebrew street name without house number (e.g. "אבן גבירול", "דיזנגוף") or null
- house_number: integer or null
- neighborhood: one of these Hebrew canonical names, or null:
  (master list lives in pdis/neighborhoods.py — CANONICAL_TLV; this copy is
  for the Haiku system prompt since this script can't import server code.
  Keep in sync manually if either changes. Note: bare "הצפון" is ambiguous —
  could mean הצפון הישן or הצפון החדש — kept only so Haiku has a fallback
  when the post doesn't specify old/new north; never used as an alias target
  in pdis/neighborhoods.py.)
  פלורנטין, נווה צדק, כרם התימנים, לב תל אביב, הצפון הישן, הצפון החדש,
  יפו העתיקה, יפו, שפירא, שבזי, נווה אביבים, רמת אביב, תל ברוך, חובבי ציון,
  מונטיפיורי, דיזנגוף, רוטשילד, בצלאל, ביצרון, יד אליהו, הרב קוק, בבלי,
  כוכב הצפון, אזורי חן, גורדון, בן יהודה, רבין, נחלת בנימין, שוק הכרמל,
  נחלאות, מרכז העיר, הצפון
- is_agent: true if the author is clearly a broker/agent/realtor (e.g. "תיווך X",
  "סוכן נדל״ן", lists multiple unrelated listings), false if private landlord,
  null if ambiguous
- floor: integer or null
- property_type: "apartment" | "house" | "studio" | "duplex" | "penthouse" |
  "garden_apt" | "rooftop" | "other" | null
- balcony: true/false/null
- elevator: true/false/null
- parking: true/false/null
- ac: true/false/null (air conditioning)
- furnished: true/false/null
- available_date: ISO date "YYYY-MM-DD" or null
- confidence: 0.0 to 1.0 — how confident are you in the overall extraction

Output valid JSON only. No commentary.

Examples:
1. Rent: "להשכרה דירת 3 חדרים, 50 מ\"ר + מרפסת 10, קומה 2, פלורנטין, 6500 לחודש, 052-1234567"
   → {"intent":"rent","price_ils":6500,"sqm_net":50,"sqm_balcony":10,"rooms":3.0,"phone":"0521234567","neighborhood":"פלורנטין","floor":2,"confidence":0.95,...}

2. Apartment for sale: "מוכרים דירת 4 חדרים ברוטשילד, 90 מ\"ר, קומה 5, מחיר 3,200,000 ₪"
   → {"intent":"apartment_forsale","price_ils":3200000,"sqm_net":90,"sqm_balcony":null,"rooms":4.0,"neighborhood":"רוטשילד","floor":5,"confidence":0.93,...}

3. Building for sale: "בניין למכירה, 8 יחידות, דיזנגוף, 12 מיליון ₪"
   → {"intent":"building_forsale","price_ils":12000000,"sqm_net":null,"sqm_balcony":null,"rooms":null,"neighborhood":"דיזנגוף","confidence":0.88,...}

4. Wanted: "מחפש דירת 2-3 חדרים בצפון תל אביב, עד 7000 לחודש, נא לפנות ל-050-9876543"
   → {"intent":"wanted","price_ils":null,"sqm_net":null,"sqm_balcony":null,"rooms":null,"phone":"0509876543","confidence":0.92,...}

5. Other (ארנונה trap): "דירה להשכרה, ארנונה 580 לחודש, ועד 200, פיקדון 2 חודשים"
   → {"intent":"rent","price_ils":null,"sqm_net":null,"sqm_balcony":null,"rooms":null,"confidence":0.4,...}
   (price_ils is null because 580 is ארנונה, not rent — the actual rent is not stated)"""


def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from a response that may contain markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def parse_post(client: Anthropic, text: str, author: str | None = None) -> dict:
    """Call Haiku to extract structured fields from a post.

    Uses prompt caching on the system prompt so cost stays low across a batch.
    Returns a dict with extracted fields (all nullable) plus _raw_response
    for debugging. On error, returns an empty dict — caller decides fallback.
    """
    user_block = f"Post by {author or 'unknown'}:\n\n{text.strip()[:3000]}"
    try:
        resp = client.messages.create(
            model=_MODEL,
            max_tokens=600,
            system=[{
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_block}],
        )
    except Exception as exc:
        return {"_error": str(exc)}

    content = ""
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            content += block.text

    parsed = _extract_json(content)
    if not parsed:
        return {"_error": "invalid_json", "_raw": content[:300]}

    usage = getattr(resp, "usage", None)
    if usage:
        parsed["_usage"] = {
            "input_tokens": getattr(usage, "input_tokens", 0),
            "output_tokens": getattr(usage, "output_tokens", 0),
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0),
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0),
        }
    return parsed


def estimate_cost(usage_stats: list[dict]) -> dict:
    """Sum Anthropic billing from a list of _usage dicts. Haiku 4.5 prices."""
    in_price = 1.0 / 1_000_000
    out_price = 5.0 / 1_000_000
    cache_write_price = 1.25 / 1_000_000
    cache_read_price = 0.10 / 1_000_000

    total = {"in": 0, "out": 0, "cache_write": 0, "cache_read": 0, "usd": 0.0}
    for u in usage_stats:
        total["in"] += u.get("input_tokens", 0)
        total["out"] += u.get("output_tokens", 0)
        total["cache_write"] += u.get("cache_creation_input_tokens", 0)
        total["cache_read"] += u.get("cache_read_input_tokens", 0)

    total["usd"] = (
        total["in"] * in_price
        + total["out"] * out_price
        + total["cache_write"] * cache_write_price
        + total["cache_read"] * cache_read_price
    )
    return total
