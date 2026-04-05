"""Distress signal calculator — batch mode, tier-based."""
from datetime import date, timedelta

import structlog

import pdis.database as _db

logger = structlog.get_logger(__name__)


async def compute_signals_batch(property_ids: list[int]) -> dict[int, dict]:
    """
    Compute distress signals for a batch of properties.
    Uses BATCH queries (3 queries total, not per-property).
    Returns {property_id: {"distress_score": float, "strong_signals": list, "weak_signals": list, "details": dict}}
    """
    if not property_ids:
        return {}

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            # BATCH QUERY 1: All events for all properties
            await cur.execute(
                """SELECT property_id, event_type, old_value, new_value, created_at
                   FROM property_events
                   WHERE property_id = ANY(%s)
                   ORDER BY property_id, created_at""",
                (property_ids,),
            )
            event_rows = await cur.fetchall()

            # BATCH QUERY 2: Property metadata
            await cur.execute(
                """SELECT id, days_on_market, price, description,
                          move_in_date, square_meters, neighborhood, is_agent, renovated, category
                   FROM properties
                   WHERE id = ANY(%s)""",
                (property_ids,),
            )
            prop_rows = await cur.fetchall()

            # Determine category from the batch (all props in a scan share a category)
            batch_categories = set(r["category"] for r in prop_rows if r.get("category"))
            batch_category = batch_categories.pop() if len(batch_categories) == 1 else None

            # BATCH QUERY 3: Neighborhood avg price per sqm (filtered by category)
            if batch_category:
                await cur.execute("""
                    SELECT neighborhood,
                           AVG(price / NULLIF(COALESCE(square_meter_build, square_meters), 0)) as avg_price_sqm,
                           COUNT(*) as cnt
                    FROM properties
                    WHERE price > 0 AND COALESCE(square_meter_build, square_meters) > 0
                          AND neighborhood IS NOT NULL
                          AND is_active = TRUE AND category = %s
                    GROUP BY neighborhood
                    HAVING COUNT(*) >= 5
                """, (batch_category,))
            else:
                await cur.execute("""
                    SELECT neighborhood,
                           AVG(price / NULLIF(COALESCE(square_meter_build, square_meters), 0)) as avg_price_sqm,
                           COUNT(*) as cnt
                    FROM properties
                    WHERE price > 0 AND COALESCE(square_meter_build, square_meters) > 0
                          AND neighborhood IS NOT NULL AND is_active = TRUE
                    GROUP BY neighborhood
                    HAVING COUNT(*) >= 5
                """)
            hood_avg_rows = await cur.fetchall()
            hood_avgs = {r["neighborhood"]: float(r["avg_price_sqm"]) for r in hood_avg_rows}

    # Group events by property
    events_by_prop: dict[int, list[dict]] = {}
    for row in event_rows:
        pid = row["property_id"]
        events_by_prop.setdefault(pid, []).append(dict(row))

    # Property metadata lookup
    props = {r["id"]: dict(r) for r in prop_rows}

    # Compute per-property
    results = {}
    for pid in property_ids:
        events = events_by_prop.get(pid, [])
        prop = props.get(pid, {})
        results[pid] = _compute_single(pid, events, prop, hood_avgs)

    return results


# Hebrew weak-language keywords
WEAK_LANGUAGE_KEYWORDS = [
    "דחוף", "גמיש", "חייב", "מוכרח", "הזדמנות",
    "ירידת מחיר", "מחיר מציאה", "מתחת למחיר",
    "חייבים", "בהזדמנות", "מחיר שפוי",
]

# Condition keywords — specific distress PHRASES only
# Root words like "שיפוץ" cause false positives ("לאחר שיפוץ" = after renovation = positive)
# Only match phrases that unambiguously indicate the property needs work
CONDITION_KEYWORDS = [
    "דרוש שיפוץ",    # needs renovation
    "צריך שיפוץ",    # requires renovation
    "לשיפוץ",        # for renovation
    "דורש שיפוץ",    # demands renovation
    "טעון שיפוץ",    # in need of renovation
    "דירת סבתא",     # grandma apartment (always = old/untouched)
    "דורש ריענון",    # needs refreshing
    "טעון ריענון",    # in need of refreshing
]


def _compute_single(pid: int, events: list[dict], prop: dict, hood_avgs: dict) -> dict:
    """Compute tier-based signals for a single property. Pure function, no DB calls."""
    strong_signals = []
    weak_signals = []
    details = {
        "price_drops": 0,
        "largest_drop_pct": 0.0,
        "relisting_count": 0,
        "days_on_market": 0,
        "desc_changes": 0,
        "img_changes": 0,
        "weak_language_found": [],
        "condition_keywords_found": [],
        "below_avg_price_sqm": False,
        "neighborhood_avg_price_sqm": None,
        "property_price_sqm": None,
    }

    # Count events
    last_drop_date = None
    for ev in events:
        etype = ev["event_type"]
        if etype == "price_drop":
            details["price_drops"] += 1
            ev_date = str(ev.get("created_at") or "")[:10]
            if ev_date:
                last_drop_date = ev_date
            try:
                old_p = int(ev["old_value"])
                new_p = int(ev["new_value"])
                if old_p > 0:
                    drop_pct = ((old_p - new_p) / old_p) * 100
                    details["largest_drop_pct"] = max(details["largest_drop_pct"], drop_pct)
            except (TypeError, ValueError):
                pass
        elif etype == "relisting":
            details["relisting_count"] += 1
        elif etype == "description_change":
            details["desc_changes"] += 1
        elif etype == "image_change":
            details["img_changes"] += 1

    if last_drop_date:
        details["last_price_drop_date"] = last_drop_date

    # Days on market
    dom = prop.get("days_on_market") or 0
    details["days_on_market"] = dom

    # Description analysis
    desc = prop.get("description") or ""
    for keyword in WEAK_LANGUAGE_KEYWORDS:
        if keyword in desc:
            details["weak_language_found"].append(keyword)
    for keyword in CONDITION_KEYWORDS:
        if keyword in desc:
            details["condition_keywords_found"].append(keyword)

    # Don't flag condition keywords if property is already marked as renovated
    if prop.get("renovated"):
        details["condition_keywords_found"] = []

    # Price/sqm vs neighborhood average — use built sqm (actual indoor area) when available
    price = prop.get("price") or 0
    sqm = prop.get("square_meter_build") or prop.get("square_meters") or 0
    neighborhood = prop.get("neighborhood")
    if price > 0 and sqm > 0 and neighborhood and neighborhood in hood_avgs:
        prop_price_sqm = price / sqm
        avg_price_sqm = hood_avgs[neighborhood]
        details["property_price_sqm"] = round(prop_price_sqm, 1)
        details["neighborhood_avg_price_sqm"] = round(avg_price_sqm, 1)
        if prop_price_sqm < avg_price_sqm * 0.8:  # 20%+ below average
            details["below_avg_price_sqm"] = True

    # === CLASSIFY SIGNALS INTO TIERS ===

    # STRONG signals (any 1 = hot)
    if details["largest_drop_pct"] > 10:
        strong_signals.append("price_drop_gt_10pct")
    if details["relisting_count"] >= 2:
        strong_signals.append("relisted_2plus")
    if dom >= 90:
        strong_signals.append("listed_90plus_days")
    if details["weak_language_found"]:
        strong_signals.append("weak_language")
    if details["condition_keywords_found"]:
        strong_signals.append("condition_keywords")
    if details["below_avg_price_sqm"]:
        strong_signals.append("below_avg_price")

    # WEAK signals
    if details["price_drops"] > 0 and "price_drop_gt_10pct" not in strong_signals:
        weak_signals.append("price_drop_small")
    if details["relisting_count"] == 1:
        weak_signals.append("relisted_once")
    if 30 <= dom < 90 and "listed_90plus_days" not in strong_signals:
        weak_signals.append("listed_30_60_days")
    if details["desc_changes"] > 0:
        weak_signals.append("desc_changes")
    if details["img_changes"] > 0:
        weak_signals.append("img_changes")

    return {
        "distress_score": 0.0,  # kept for DB compat, no longer used
        "strong_signals": strong_signals,
        "weak_signals": weak_signals,
        "details": details,
    }
