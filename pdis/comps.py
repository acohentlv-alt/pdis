"""Closed-sale comps computation (Israel Tax Authority via govmap.gov.il)."""
from __future__ import annotations
import math
from pdis import database as _db

LOOKBACK_MONTHS = 24
MIN_BUILDING = 3
MIN_STREET = 5
MIN_NEIGHBORHOOD = 10
STREET_RADIUS_M = 150
BUILDING_RADIUS_M = 30


def _haversine_m(lat1, lng1, lat2, lng2) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.asin(math.sqrt(a))


async def compute_building_comps(property_id: int, lookback_months: int = LOOKBACK_MONTHS) -> dict:
    """Returns {median_pps, count, source_level, deals:[top-10]}"""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT id, latitude, longitude, address_street, neighborhood,
                       gush_num, parcel_num, price, square_meter_build, square_meters
                FROM properties WHERE id = %s
            """, (property_id,))
            prop = await cur.fetchone()
            if not prop:
                return {"median_pps": None, "count": 0, "source_level": "none", "deals": []}

            # Tier 1: gush+parcel exact building match
            if prop["gush_num"] and prop["parcel_num"]:
                await cur.execute(f"""
                    SELECT deal_id, deal_date, floor, sqm, sale_price, price_per_sqm
                    FROM closed_transactions
                    WHERE gush_num=%s AND parcel_num=%s
                      AND sqm > 0 AND price_per_sqm IS NOT NULL
                      AND deal_date >= CURRENT_DATE - INTERVAL '{int(lookback_months)} months'
                    ORDER BY deal_date DESC
                """, (prop["gush_num"], prop["parcel_num"]))
                deals = await cur.fetchall()
                if len(deals) >= MIN_BUILDING:
                    return _summarize(deals, "building")

            # Tier 2+3: radius-based fallback
            if prop["latitude"] and prop["longitude"]:
                await cur.execute(f"""
                    SELECT deal_id, deal_date, floor, sqm, sale_price, price_per_sqm,
                           centroid_lat, centroid_lng
                    FROM closed_transactions
                    WHERE sqm > 0 AND price_per_sqm IS NOT NULL
                      AND deal_date >= CURRENT_DATE - INTERVAL '{int(lookback_months)} months'
                      AND centroid_lat BETWEEN %s - 0.002 AND %s + 0.002
                      AND centroid_lng BETWEEN %s - 0.002 AND %s + 0.002
                    ORDER BY deal_date DESC
                    LIMIT 500
                """, (prop["latitude"], prop["latitude"],
                      prop["longitude"], prop["longitude"]))
                rows = await cur.fetchall()

                building_deals = [
                    d for d in rows
                    if d["centroid_lat"] and d["centroid_lng"] and
                    _haversine_m(prop["latitude"], prop["longitude"],
                                 d["centroid_lat"], d["centroid_lng"]) <= BUILDING_RADIUS_M
                ]
                if len(building_deals) >= MIN_BUILDING:
                    return _summarize(building_deals, "building")

                street_deals = [
                    d for d in rows
                    if d["centroid_lat"] and d["centroid_lng"] and
                    _haversine_m(prop["latitude"], prop["longitude"],
                                 d["centroid_lat"], d["centroid_lng"]) <= STREET_RADIUS_M
                ]
                if len(street_deals) >= MIN_STREET:
                    return _summarize(street_deals, "street")

            # Tier 4: neighborhood
            if prop["neighborhood"]:
                await cur.execute(f"""
                    SELECT deal_id, deal_date, floor, sqm, sale_price, price_per_sqm
                    FROM closed_transactions
                    WHERE neighborhood=%s AND sqm > 0 AND price_per_sqm IS NOT NULL
                      AND deal_date >= CURRENT_DATE - INTERVAL '{int(lookback_months)} months'
                    ORDER BY deal_date DESC
                    LIMIT 500
                """, (prop["neighborhood"],))
                deals = await cur.fetchall()
                if len(deals) >= MIN_NEIGHBORHOOD:
                    return _summarize(deals, "neighborhood")

    return {"median_pps": None, "count": 0, "source_level": "none", "deals": []}


def _summarize(deals: list[dict], source_level: str) -> dict:
    pps_list = sorted([d["price_per_sqm"] for d in deals if d["price_per_sqm"]])
    if not pps_list:
        return {"median_pps": None, "count": 0, "source_level": "none", "deals": []}
    n = len(pps_list)
    median = pps_list[n//2] if n % 2 else (pps_list[n//2-1] + pps_list[n//2]) // 2
    return {
        "median_pps": int(median),
        "count": n,
        "source_level": source_level,
        "deals": [dict(d) for d in deals[:10]],
    }


async def compute_building_comps_batch(property_ids: list[int]) -> dict[int, dict]:
    """Batch variant — avoids N+1 by caller, per-id loop inside (optimize later)."""
    results = {}
    for pid in property_ids:
        results[pid] = await compute_building_comps(pid)
    return results


async def compute_closed_comp_signals(property_id: int, price: int | None, sqm: int | None) -> tuple[list[str], dict]:
    """Per Amit: no average-based signals — return raw comp metadata only."""
    if not price or not sqm or sqm <= 0:
        return [], {}
    comps = await compute_building_comps(property_id)
    if comps["count"] == 0:
        return [], {}
    details = {
        "closed_comp_count": comps["count"],
        "closed_comp_source": comps["source_level"],
    }
    return [], details
