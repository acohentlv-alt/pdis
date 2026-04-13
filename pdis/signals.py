"""Distress signal calculator — batch mode, tier-based."""
import re
import unicodedata
from datetime import date, timedelta

import structlog

import pdis.database as _db

logger = structlog.get_logger(__name__)


def _year_band(year: int | None) -> str:
    """Year-built band for Amit Fit adjustment. NULL falls back to 'mid' (0% adj)."""
    if year is None:
        return "mid"
    if year < 1960:
        return "old"
    if year < 1990:
        return "mid_old"
    if year < 2010:
        return "mid"
    return "new"


_YEAR_ADJUSTMENT = {
    "old":     -0.18,   # < 1960
    "mid_old": -0.08,   # 1960-1989
    "mid":      0.00,   # 1990-2009 (and fallback for unknown)
    "new":      0.05,   # >= 2010
}

_DEFAULT_FA = {
    "year_old_pref_pct":     -18.0,
    "year_old_max_pct":      -18.0,
    "year_mid_old_pref_pct":  -8.0,
    "year_mid_old_max_pct":   -8.0,
    "year_mid_pref_pct":       0.0,
    "year_mid_max_pct":        0.0,
    "year_new_pref_pct":       5.0,
    "year_new_max_pct":        5.0,
    "walkup_pct_per_floor":    3.0,
    "parking_bonus_pref":      0,
    "parking_bonus_max":       0,
    "mamad_pct_pref":          0.0,
    "mamad_pct_max":           0.0,
}

_MAX_NEGATIVE_ADJUSTMENT = -0.50


def _floor_adjustment(floor: int | None, has_elevator: bool | None) -> float:
    """Floor 1 = 0% (barely a walk-up). Floor 2 = -3%. Cap at -15%.
    If elevator is True, no penalty regardless of floor."""
    if floor is None or floor <= 1:
        return 0.0
    if has_elevator:
        return 0.0
    penalty = max(0, floor - 1) * -0.03
    return max(penalty, -0.15)


def _normalize_address(city, street, house_number) -> tuple[str, str, str]:
    """Normalize address triple. city: NFKC + hyphen->space + collapse whitespace.
    street: NFKC + whitespace. house_number: leading digits only."""
    def _nfkc_strip(s) -> str:
        if not s:
            return ""
        s = unicodedata.normalize("NFKC", str(s)).strip()
        s = re.sub(r"\s+", " ", s)
        return s
    c = _nfkc_strip(city).replace("-", " ")
    c = re.sub(r"\s+", " ", c)
    s = _nfkc_strip(street)
    h_raw = _nfkc_strip(house_number)
    h_match = re.match(r"^\d+", h_raw)
    h = h_match.group(0) if h_match else ""
    return c, s, h


async def compute_signals_batch(property_ids: list[int]) -> dict[int, dict]:
    """
    Compute distress signals for a batch of properties.
    Uses BATCH queries (4 queries total, not per-property).
    Returns {property_id: {"distress_score": float, "strong_signals": list, "weak_signals": list, "buyer_fit_tags": list, "details": dict}}
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
                          move_in_date, square_meters, square_meter_build, neighborhood, is_agent, renovated, category,
                          hood_id, year_built, floor, elevator
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

            # BATCH QUERY 4: All neighborhood thresholds for buyer fit tagging
            await cur.execute("SELECT * FROM neighborhood_thresholds")
            threshold_rows = await cur.fetchall()

            # BATCH QUERY 5: Per-neighborhood feature adjustments (Phase 2B-1)
            await cur.execute(
                """SELECT neighborhood, hood_id, category,
                          year_old_pref_pct, year_old_max_pct,
                          year_mid_old_pref_pct, year_mid_old_max_pct,
                          year_mid_pref_pct, year_mid_max_pct,
                          year_new_pref_pct, year_new_max_pct,
                          walkup_pct_per_floor,
                          parking_bonus_pref, parking_bonus_max,
                          mamad_pct_pref, mamad_pct_max
                   FROM neighborhood_feature_adjustments"""
            )
            fa_rows = await cur.fetchall()
            fa_by_hood_id: dict[tuple, dict] = {}
            fa_by_name: dict[tuple, dict] = {}
            for r in fa_rows:
                if r.get("hood_id"):
                    fa_by_hood_id[(r["hood_id"], r["category"])] = dict(r)
                if r.get("neighborhood"):
                    fa_by_name[(r["neighborhood"], r["category"])] = dict(r)

    # Build threshold lookup dicts
    by_hood_id: dict[tuple, list[dict]] = {}
    by_name: dict[tuple, list[dict]] = {}
    for row in threshold_rows:
        r = dict(row)
        if r.get("hood_id") is not None:
            key = (r["hood_id"], r["category"])
            by_hood_id.setdefault(key, []).append(r)
        key_name = (r["neighborhood"], r["category"])
        by_name.setdefault(key_name, []).append(r)

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
        results[pid] = _compute_single(pid, events, prop, hood_avgs, by_hood_id, by_name, fa_by_hood_id, fa_by_name)

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


def _compute_single(
    pid: int,
    events: list[dict],
    prop: dict,
    hood_avgs: dict,
    by_hood_id: dict | None = None,
    by_name: dict | None = None,
    fa_by_hood_id: dict | None = None,
    fa_by_name: dict | None = None,
) -> dict:
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

    # === BUYER FIT TAGS (orthogonal — does not affect hot/warm/cold) ===
    buyer_fit_tags = []
    prop_category = prop.get("category")
    prop_hood_id = prop.get("hood_id")
    prop_neighborhood = prop.get("neighborhood")

    if price > 0 and sqm > 0 and prop_category and (by_hood_id is not None or by_name is not None):
        candidates = []
        if prop_hood_id and by_hood_id is not None:
            candidates.extend(by_hood_id.get((prop_hood_id, prop_category), []))
        if prop_neighborhood and by_name is not None:
            candidates.extend(by_name.get((prop_neighborhood, prop_category), []))
        # Dedupe by row id
        seen: set[int] = set()
        unique_candidates = []
        for r in candidates:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique_candidates.append(r)
        # Find bucket matching sqm (size_min <= sqm < size_max)
        bucket = next(
            (r for r in unique_candidates if r["size_min"] <= sqm < r["size_max"]),
            None,
        )

        if bucket and sqm > 0 and price > 0:
            pref_per_sqm_base = float(bucket["target_price_per_sqm_preferred"])
            max_per_sqm_base = float(bucket["target_price_per_sqm_max"])

            pref_total_base = pref_per_sqm_base * sqm
            max_total_base = max_per_sqm_base * sqm

            # Find feature adjustments for this property; fall back to defaults
            fa = None
            hood_id = prop.get("hood_id")
            category = prop_category
            if hood_id and category:
                fa = (fa_by_hood_id or {}).get((hood_id, category))
            if not fa and prop_neighborhood and category:
                fa = (fa_by_name or {}).get((prop_neighborhood, category))
            fa_source = "neighborhood" if fa else "default"
            fa_values = fa if fa else _DEFAULT_FA

            # Year band + adjustment
            year = prop.get("year_built")
            band = _year_band(year)
            year_pref_pct = float(fa_values[f"year_{band}_pref_pct"])
            year_max_pct = float(fa_values[f"year_{band}_max_pct"])

            # Floor / elevator adjustment — walkup_pct_per_floor stored positive, code negates
            walkup_pct_positive = float(fa_values["walkup_pct_per_floor"])
            floor = prop.get("floor")
            elevator = prop.get("elevator")
            floor_adj = 0.0
            if floor is not None and floor > 1 and not elevator:
                raw = -walkup_pct_positive / 100.0 * (floor - 1)
                floor_adj = max(raw, -0.15)  # cap at -15%

            # Mamad adjustment
            has_mamad = bool(prop.get("safe_room"))
            mamad_pref_pct = float(fa_values["mamad_pct_pref"]) / 100.0 if has_mamad else 0.0
            mamad_max_pct = float(fa_values["mamad_pct_max"]) / 100.0 if has_mamad else 0.0

            # Combined % adjustment per tier
            total_pref_pct = year_pref_pct / 100.0 + floor_adj + mamad_pref_pct
            total_max_pct = year_max_pct / 100.0 + floor_adj + mamad_max_pct
            total_pref_pct = max(total_pref_pct, _MAX_NEGATIVE_ADJUSTMENT)
            total_max_pct = max(total_max_pct, _MAX_NEGATIVE_ADJUSTMENT)

            # Parking: flat ₪ OUTSIDE the % multiplier
            has_parking = bool(prop.get("parking"))
            parking_pref = int(fa_values["parking_bonus_pref"]) if has_parking else 0
            parking_max = int(fa_values["parking_bonus_max"]) if has_parking else 0

            pref_total_adj = pref_total_base * (1 + total_pref_pct) + parking_pref
            max_total_adj = max_total_base * (1 + total_max_pct) + parking_max

            details["amit_breakdown"] = {
                "v": 2,
                "fa_source": fa_source,
                "year_built": year,
                "year_band": band,
                "year_pref_pct": year_pref_pct,
                "year_max_pct": year_max_pct,
                "floor": floor,
                "elevator": bool(elevator) if elevator is not None else None,
                "floor_adjustment_applied": floor_adj,
                "parking_applied": has_parking,
                "parking_bonus_pref_applied": parking_pref,
                "parking_bonus_max_applied": parking_max,
                "mamad_applied": has_mamad,
                "mamad_pct_pref_applied": mamad_pref_pct,
                "mamad_pct_max_applied": mamad_max_pct,
                "total_pref_pct_applied": total_pref_pct,
                "total_max_pct_applied": total_max_pct,
                "pref_per_sqm_baseline": pref_per_sqm_base,
                "max_per_sqm_baseline": max_per_sqm_base,
                "pref_total_baseline": pref_total_base,
                "max_total_baseline": max_total_base,
                "pref_total_adjusted": pref_total_adj,
                "max_total_adjusted": max_total_adj,
                "sqm": sqm,
                "price": price,
            }
            details["amit_target_total_pref"] = pref_total_adj
            details["amit_target_total_max"] = max_total_adj

            if price <= pref_total_adj:
                buyer_fit_tags.append("below_amit_target")
                details["amit_pct_vs_preferred"] = round((price - pref_total_adj) / pref_total_adj * 100, 1)
            elif price <= max_total_adj:
                buyer_fit_tags.append("close_to_amit_target")
                details["amit_pct_vs_preferred"] = round((price - pref_total_adj) / pref_total_adj * 100, 1)

    return {
        "distress_score": 0.0,  # kept for DB compat, no longer used
        "strong_signals": strong_signals,
        "weak_signals": weak_signals,
        "buyer_fit_tags": buyer_fit_tags,
        "details": details,
    }
