"""Property matching — detect duplicate listings for the same apartment."""
import math
import structlog
import pdis.database as _db

logger = structlog.get_logger(__name__)


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _word_overlap(text_a: str, text_b: str) -> float:
    """Compute Jaccard similarity between two texts using word sets."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _price_within_pct(price_a: int, price_b: int, pct: float) -> bool:
    """Return True if the two prices are within pct% of each other."""
    if price_a <= 0 or price_b <= 0:
        return False
    ratio = abs(price_a - price_b) / max(price_a, price_b)
    return ratio <= pct


async def find_matches(session_id: int) -> int:
    """
    Find matching properties among those seen in this scan session.
    Only compares NEW properties (from this session) against existing ones.
    Returns count of new matches found.
    """
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            # Get the property IDs for new inserts in this session.
            # We detect new inserts by checking which properties have first_seen = today
            # and appear in this session's snapshots.
            await cur.execute(
                """
                SELECT DISTINCT p.id
                FROM property_snapshots ps
                JOIN properties p ON p.id = ps.property_id
                WHERE ps.session_id = %s
                  AND p.created_at >= NOW() - INTERVAL '1 hour'
                """,
                (session_id,),
            )
            new_prop_rows = await cur.fetchall()

    if not new_prop_rows:
        return 0

    new_prop_ids = [r["id"] for r in new_prop_rows]

    # Load full data for new properties (including customer_id and coordinates)
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, address_city, neighborhood, rooms, floor,
                       square_meters, price, contact_phone, description,
                       customer_id, latitude, longitude
                FROM properties
                WHERE id = ANY(%s)
                """,
                (new_prop_ids,),
            )
            new_props = await cur.fetchall()

    if not new_props:
        return 0

    # Get distinct cities from new properties for batched existing-property lookup
    cities = list({p["address_city"] for p in new_props if p["address_city"]})

    if not cities:
        return 0

    # Load all active properties in those cities (excluding the new ones themselves)
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, address_city, neighborhood, rooms, floor,
                       square_meters, price, contact_phone, description,
                       customer_id, latitude, longitude
                FROM properties
                WHERE address_city = ANY(%s)
                  AND is_active = TRUE
                  AND id != ALL(%s)
                """,
                (cities, new_prop_ids),
            )
            existing_props = await cur.fetchall()

    if not existing_props:
        return 0

    # Build a lookup: city -> list of properties
    city_props: dict[str, list[dict]] = {}
    for p in existing_props:
        city = p["address_city"]
        if city:
            city_props.setdefault(city, []).append(dict(p))

    matches_to_insert: list[tuple] = []

    for new_p in new_props:
        new_p = dict(new_p)
        city = new_p.get("address_city")
        if not city:
            continue

        candidates = city_props.get(city, [])

        for cand in candidates:
            # Determine canonical order: id_a < id_b
            id_a = min(new_p["id"], cand["id"])
            id_b = max(new_p["id"], cand["id"])

            # --- Tier 0: same customer_id + same city (auto-confirmed) ---
            cust_a = new_p.get("customer_id")
            cust_b = cand.get("customer_id")

            if (
                cust_a is not None
                and cust_a != ""
                and cust_b is not None
                and cust_b != ""
                and cust_a == cust_b
            ):
                matches_to_insert.append(
                    (id_a, id_b, 0, "same_customer_id", 0.99, True)
                )
                continue  # already matched; skip further tier checks

            # --- Tier 1: coordinates within 50m + same rooms + same floor (auto-confirmed) ---
            lat_a = new_p.get("latitude")
            lon_a = new_p.get("longitude")
            lat_b = cand.get("latitude")
            lon_b = cand.get("longitude")
            rooms_a = new_p.get("rooms")
            rooms_b = cand.get("rooms")
            floor_a = new_p.get("floor")
            floor_b = cand.get("floor")

            if (
                lat_a is not None
                and lon_a is not None
                and lat_b is not None
                and lon_b is not None
                and rooms_a is not None
                and rooms_b is not None
                and floor_a is not None
                and floor_b is not None
                and rooms_a == rooms_b
                and floor_a == floor_b
                and _haversine_meters(lat_a, lon_a, lat_b, lon_b) < 50
            ):
                matches_to_insert.append(
                    (id_a, id_b, 1, "coordinates_rooms_floor", 0.95, True)
                )
                continue

            # --- Tier 2: neighborhood + rooms + floor + sq_meters (±5) + price within 20% ---
            neigh_a = new_p.get("neighborhood")
            neigh_b = cand.get("neighborhood")
            sqm_a = new_p.get("square_meters")
            sqm_b = cand.get("square_meters")
            price_a = new_p.get("price")
            price_b = cand.get("price")

            if (
                neigh_a is not None
                and neigh_b is not None
                and rooms_a is not None
                and rooms_b is not None
                and floor_a is not None
                and floor_b is not None
                and sqm_a is not None
                and sqm_b is not None
                and price_a is not None
                and price_b is not None
                and neigh_a == neigh_b
                and rooms_a == rooms_b
                and floor_a == floor_b
                and abs(sqm_a - sqm_b) <= 5
                and _price_within_pct(price_a, price_b, 0.20)
            ):
                matches_to_insert.append(
                    (id_a, id_b, 2, "neighborhood_rooms_floor_size_price", 0.75, True)
                )
                continue

            # --- Tier 3: neighborhood + price within 20% + text similarity > 60% ---
            desc_a = new_p.get("description")
            desc_b = cand.get("description")

            if (
                neigh_a is not None
                and neigh_b is not None
                and price_a is not None
                and price_b is not None
                and desc_a is not None
                and desc_b is not None
                and len(desc_a) >= 10
                and len(desc_b) >= 10
                and neigh_a == neigh_b
                and _price_within_pct(price_a, price_b, 0.20)
            ):
                overlap = _word_overlap(desc_a, desc_b)
                if overlap > 0.60:
                    matches_to_insert.append(
                        (id_a, id_b, 3, "neighborhood_price_text_similarity", overlap, None)
                    )

    if not matches_to_insert:
        return 0

    # Deduplicate by (id_a, id_b) — keep highest tier (lowest tier number) per pair
    seen: dict[tuple[int, int], tuple] = {}
    for m in matches_to_insert:
        key = (m[0], m[1])
        if key not in seen or m[2] < seen[key][2]:
            seen[key] = m

    deduped = list(seen.values())

    inserted = 0
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            for m in deduped:
                id_a, id_b, tier, reason, confidence, is_confirmed = m
                await cur.execute(
                    """
                    INSERT INTO property_matches
                        (property_id_a, property_id_b, match_tier, match_reason, confidence, is_confirmed)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (property_id_a, property_id_b) DO NOTHING
                    """,
                    (id_a, id_b, tier, reason, confidence, is_confirmed),
                )
                if cur.rowcount > 0:
                    inserted += 1
        await conn.commit()

    logger.info("matching.done", session_id=session_id, new_matches=inserted)
    return inserted


async def detect_customer_relistings(session_id: int) -> int:
    """
    Find properties in this session that share a customer_id with
    a previously REMOVED property. This means the landlord relisted.
    Creates a 'relisting' match record linking the old and new property.
    Returns count of relistings detected.
    """
    # Get all properties (and their customer_ids) that have snapshots in this session
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT DISTINCT p.id, p.customer_id
                FROM property_snapshots ps
                JOIN properties p ON p.id = ps.property_id
                WHERE ps.session_id = %s
                  AND p.customer_id IS NOT NULL
                  AND p.customer_id != ''
                """,
                (session_id,),
            )
            session_props = await cur.fetchall()

    if not session_props:
        return 0

    # Build map of customer_id -> active property id from this session
    customer_to_active: dict[str, int] = {}
    for row in session_props:
        customer_to_active[row["customer_id"]] = row["id"]

    customer_ids = list(customer_to_active.keys())

    # Find INACTIVE properties with the same customer_ids (not in this session)
    active_ids = list(customer_to_active.values())

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, customer_id
                FROM properties
                WHERE customer_id = ANY(%s)
                  AND is_active = FALSE
                  AND id != ALL(%s)
                """,
                (customer_ids, active_ids),
            )
            inactive_props = await cur.fetchall()

    if not inactive_props:
        return 0

    matches_to_insert: list[tuple] = []

    for inactive in inactive_props:
        cust_id = inactive["customer_id"]
        active_id = customer_to_active.get(cust_id)
        if active_id is None:
            continue

        old_id = inactive["id"]
        id_a = min(active_id, old_id)
        id_b = max(active_id, old_id)

        matches_to_insert.append(
            (id_a, id_b, 0, "same_customer_relist", 0.99, True)
        )

    if not matches_to_insert:
        return 0

    # Deduplicate by (id_a, id_b)
    seen: dict[tuple[int, int], tuple] = {}
    for m in matches_to_insert:
        key = (m[0], m[1])
        if key not in seen:
            seen[key] = m

    inserted = 0
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            for m in seen.values():
                id_a, id_b, tier, reason, confidence, is_confirmed = m
                await cur.execute(
                    """
                    INSERT INTO property_matches
                        (property_id_a, property_id_b, match_tier, match_reason, confidence, is_confirmed)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (property_id_a, property_id_b) DO NOTHING
                    """,
                    (id_a, id_b, tier, reason, confidence, is_confirmed),
                )
                if cur.rowcount > 0:
                    inserted += 1
        await conn.commit()

    logger.info("matching.customer_relistings", session_id=session_id, count=inserted)
    return inserted
