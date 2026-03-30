"""Property matching — detect duplicate listings for the same apartment."""
import structlog
import pdis.database as _db

logger = structlog.get_logger(__name__)


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

    # Load full data for new properties
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, address_city, neighborhood, rooms, floor,
                       square_meters, price, contact_phone, description
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
                       square_meters, price, contact_phone, description
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

            # --- Tier 1: same phone + same neighborhood + price within 20% ---
            phone_a = new_p.get("contact_phone")
            phone_b = cand.get("contact_phone")
            neigh_a = new_p.get("neighborhood")
            neigh_b = cand.get("neighborhood")
            price_a = new_p.get("price")
            price_b = cand.get("price")

            if (
                phone_a is not None
                and phone_b is not None
                and neigh_a is not None
                and neigh_b is not None
                and phone_a == phone_b
                and neigh_a == neigh_b
                and price_a is not None
                and price_b is not None
                and _price_within_pct(price_a, price_b, 0.20)
            ):
                matches_to_insert.append(
                    (id_a, id_b, 1, "same_phone_neighborhood_price", 0.95, True)
                )
                continue  # already matched; skip further tier checks

            # --- Tier 2: neighborhood + rooms + floor + sq_meters (±5) + price within 20% ---
            rooms_a = new_p.get("rooms")
            rooms_b = cand.get("rooms")
            floor_a = new_p.get("floor")
            floor_b = cand.get("floor")
            sqm_a = new_p.get("square_meters")
            sqm_b = cand.get("square_meters")

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
