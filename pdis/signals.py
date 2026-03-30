"""Distress signal calculator — batch mode."""
import structlog

import pdis.database as _db

logger = structlog.get_logger(__name__)


async def compute_signals_batch(property_ids: list[int]) -> dict[int, dict]:
    """
    Compute distress scores for a batch of properties.
    Uses BATCH queries (2 queries total, not per-property).
    Returns {property_id: {"distress_score": float, "details": dict}}
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
                """SELECT id, days_on_market, price, description
                   FROM properties
                   WHERE id = ANY(%s)""",
                (property_ids,),
            )
            prop_rows = await cur.fetchall()

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
        results[pid] = _compute_single(pid, events, prop)

    return results


# Hebrew weak-language keywords
WEAK_LANGUAGE_KEYWORDS = [
    "דחוף", "גמיש", "חייב", "מוכרח", "הזדמנות",
    "ירידת מחיר", "מחיר מציאה", "מתחת למחיר",
    "חייבים", "בהזדמנות", "מחיר שפוי",
]


def _compute_single(pid: int, events: list[dict], prop: dict) -> dict:
    """Compute distress score for a single property. Pure function, no DB calls."""
    score = 0.0
    details = {
        "price_drops": 0,
        "largest_drop_pct": 0.0,
        "days_on_market": 0,
        "has_relisting": False,
        "desc_changes": 0,
        "img_changes": 0,
        "weak_language_found": [],
    }

    # Count events by type
    for ev in events:
        etype = ev["event_type"]
        if etype == "price_drop":
            details["price_drops"] += 1
            score += 15
            # Check drop percentage
            try:
                old_p = int(ev["old_value"])
                new_p = int(ev["new_value"])
                if old_p > 0:
                    drop_pct = ((old_p - new_p) / old_p) * 100
                    details["largest_drop_pct"] = max(details["largest_drop_pct"], drop_pct)
                    if drop_pct > 10:
                        score += 10  # bonus for large drop
            except (TypeError, ValueError):
                pass
        elif etype == "relisting":
            details["has_relisting"] = True
            score += 15
        elif etype == "description_change":
            details["desc_changes"] += 1
            score += 5
        elif etype == "image_change":
            details["img_changes"] += 1
            score += 5

    # Multiple price drops bonus
    if details["price_drops"] >= 2:
        score += 10

    # Days on market
    dom = prop.get("days_on_market") or 0
    details["days_on_market"] = dom
    if dom > 30:
        score += 10
    if dom > 60:
        score += 10
    if dom > 90:
        score += 10

    # Weak language detection (Hebrew keywords in description)
    desc = prop.get("description") or ""
    for keyword in WEAK_LANGUAGE_KEYWORDS:
        if keyword in desc:
            details["weak_language_found"].append(keyword)
            score += 5

    # Cap at 100
    score = min(score, 100.0)

    return {"distress_score": score, "details": details}
