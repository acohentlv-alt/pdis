"""Property matching — detect duplicate listings for the same apartment."""
import math
import re
import unicodedata
import structlog
import pdis.database as _db
from psycopg.rows import dict_row

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


async def run_full_cross_source_match() -> int:
    """One-time full comparison of all properties across sources."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, source, latitude, longitude, rooms, floor,
                       square_meters, price, neighborhood, description
                FROM properties
                WHERE is_active = TRUE AND source = 'yad2'
                """
            )
            yad2_props = [dict(r) for r in await cur.fetchall()]

            await cur.execute(
                """
                SELECT id, source, latitude, longitude, rooms, floor,
                       square_meters, price, neighborhood, description
                FROM properties
                WHERE is_active = TRUE AND source = 'madlan'
                """
            )
            madlan_props = [dict(r) for r in await cur.fetchall()]

    if not yad2_props or not madlan_props:
        logger.info("cross_source_match.skip", yad2=len(yad2_props), madlan=len(madlan_props))
        return 0

    matches_to_insert: list[tuple] = []

    for yp in yad2_props:
        for mp in madlan_props:
            id_a = min(yp["id"], mp["id"])
            id_b = max(yp["id"], mp["id"])

            lat_a = yp.get("latitude")
            lon_a = yp.get("longitude")
            lat_b = mp.get("latitude")
            lon_b = mp.get("longitude")
            rooms_a = yp.get("rooms")
            rooms_b = mp.get("rooms")
            floor_a = yp.get("floor")
            floor_b = mp.get("floor")

            # --- Tier 1: coordinates within 100m + same rooms + same floor ---
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
                and _haversine_meters(lat_a, lon_a, lat_b, lon_b) < 100
            ):
                matches_to_insert.append(
                    (id_a, id_b, 1, "cross_source_coordinates_rooms_floor", 0.95, True)
                )
                continue

            neigh_a = yp.get("neighborhood")
            neigh_b = mp.get("neighborhood")
            sqm_a = yp.get("square_meters")
            sqm_b = mp.get("square_meters")
            price_a = yp.get("price")
            price_b = mp.get("price")

            # --- Tier 2: neighborhood + rooms + floor + sq_meters (±5) + price within 20% ---
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
                    (id_a, id_b, 2, "cross_source_neighborhood_rooms_floor_size_price", 0.75, True)
                )
                continue

            # --- Tier 3: neighborhood + price within 20% + text similarity > 60% ---
            desc_a = yp.get("description")
            desc_b = mp.get("description")

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
                        (id_a, id_b, 3, "cross_source_neighborhood_price_text_similarity", overlap, None)
                    )

    if not matches_to_insert:
        logger.info("cross_source_match.done", new_matches=0)
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
            await cur.executemany(
                """
                INSERT INTO property_matches
                    (property_id_a, property_id_b, match_tier, match_reason, confidence, is_confirmed)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (property_id_a, property_id_b) DO NOTHING
                """,
                deduped,
            )
            inserted = cur.rowcount if cur.rowcount > 0 else 0
        await conn.commit()

    logger.info("cross_source_match.done", new_matches=inserted)
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


# ---------------------------------------------------------------------------
# FB cross-source matcher (Brief B)
# ---------------------------------------------------------------------------

_HEB_STREET_PREFIX_RX = re.compile(r"^\s*(רחוב|רח['׳\"״]?)\s+")
_WHITESPACE_RX = re.compile(r"\s+")
_HEB_LETTER_SUFFIX_RX = re.compile(r"[\u05d0-\u05ea]+$")


def _normalize_hebrew_street(s: str | None) -> str | None:
    """Normalize a Hebrew street name for equality comparison.
    NFKC, strip geresh/gershayim/quotes, dash-to-space, strip
    רחוב/רח׳/רח' prefix, collapse whitespace, lowercase."""
    if not s:
        return None
    t = unicodedata.normalize("NFKC", s)
    t = t.replace("\u05F3", "").replace("\u05F4", "")  # geresh, gershayim
    t = t.replace("'", "").replace("\"", "")
    t = re.sub(r"[\u2010-\u2015\-]", " ", t)
    t = _HEB_STREET_PREFIX_RX.sub("", t)
    t = _WHITESPACE_RX.sub(" ", t).strip().lower()
    return t or None


def _normalize_home_number(n) -> str | None:
    """Normalize house number for equality.
    Strip whitespace, lowercase, then strip trailing Hebrew letter suffix
    (e.g. '12א' -> '12') so building-level matches land."""
    if n is None:
        return None
    s = str(n).strip().lower()
    s = _WHITESPACE_RX.sub("", s)
    s = _HEB_LETTER_SUFFIX_RX.sub("", s).strip()
    return s or None


async def find_fb_cross_source_matches(session_id: int) -> int:
    """
    Match FB posts to Yad2/Madlan listings (or vice versa) using phone,
    address, rooms, price, and floor — no GPS required.

    Runs both directions:
      (A) new FB rows in this session × existing non-FB rows
      (B) new non-FB rows in this session × existing FB rows

    Tier 10: phone + address match + rooms-veto (auto-confirm, 0.95)
    Tier 11: address + rooms + price-within-25% (auto-confirm, 0.80)
    Tier 12: address + price-within-25% (pending review, 0.65)
    Floor veto: if both sides have floor and they differ, skip.
    Rooms veto (Tier 10): if both sides have rooms and they differ, skip
                          regardless of phone+address match.

    Multiple matches per property are allowed — each pair writes its own row.
    Returns count of new matches inserted.
    """
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT DISTINCT p.id, p.source, p.address_city, p.address_street,
                                p.address_home_number, p.rooms, p.floor,
                                p.price, p.contact_phone
                FROM property_snapshots ps
                JOIN properties p ON p.id = ps.property_id
                WHERE ps.session_id = %s
                  AND p.is_active = TRUE
                """,
                (session_id,),
            )
            session_props = [dict(r) for r in await cur.fetchall()]

    if not session_props:
        return 0

    session_fb = [p for p in session_props if p["source"] == "facebook"]
    session_non_fb = [p for p in session_props if p["source"] != "facebook"]

    cities = list({p["address_city"] for p in session_props if p["address_city"]})
    if not cities:
        return 0

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, source, address_city, address_street, address_home_number,
                       rooms, floor, price, contact_phone
                FROM properties
                WHERE address_city = ANY(%s)
                  AND is_active = TRUE
                  AND source = 'facebook'
                """,
                (cities,),
            )
            all_fb = [dict(r) for r in await cur.fetchall()]

            await cur.execute(
                """
                SELECT id, source, address_city, address_street, address_home_number,
                       rooms, floor, price, contact_phone
                FROM properties
                WHERE address_city = ANY(%s)
                  AND is_active = TRUE
                  AND source != 'facebook'
                """,
                (cities,),
            )
            all_non_fb = [dict(r) for r in await cur.fetchall()]

    session_fb_ids = {p["id"] for p in session_fb}
    session_non_fb_ids = {p["id"] for p in session_non_fb}

    pairs: list[tuple[dict, dict]] = []
    for fb in session_fb:
        for nfb in all_non_fb:
            if nfb["address_city"] != fb["address_city"]:
                continue
            pairs.append((fb, nfb))
    for nfb in session_non_fb:
        for fb in all_fb:
            if fb["address_city"] != nfb["address_city"]:
                continue
            if fb["id"] in session_fb_ids and nfb["id"] in session_non_fb_ids:
                continue  # covered by Direction A
            pairs.append((fb, nfb))

    if not pairs:
        return 0

    matches_to_insert: list[tuple] = []

    for fb, nfb in pairs:
        # Floor veto
        f_fb = fb.get("floor")
        f_nfb = nfb.get("floor")
        if f_fb is not None and f_nfb is not None and f_fb != f_nfb:
            continue

        id_a = min(fb["id"], nfb["id"])
        id_b = max(fb["id"], nfb["id"])

        street_fb = _normalize_hebrew_street(fb.get("address_street"))
        street_nfb = _normalize_hebrew_street(nfb.get("address_street"))
        home_fb = _normalize_home_number(fb.get("address_home_number"))
        home_nfb = _normalize_home_number(nfb.get("address_home_number"))

        address_match = (
            street_fb is not None
            and street_nfb is not None
            and street_fb == street_nfb
            and home_fb is not None
            and home_nfb is not None
            and home_fb == home_nfb
        )

        phone_fb = fb.get("contact_phone")
        phone_nfb = nfb.get("contact_phone")
        phone_match = (
            phone_fb is not None
            and phone_nfb is not None
            and phone_fb == phone_nfb
        )

        rooms_fb = fb.get("rooms")
        rooms_nfb = nfb.get("rooms")
        rooms_match = (
            rooms_fb is not None
            and rooms_nfb is not None
            and float(rooms_fb) == float(rooms_nfb)
        )

        price_fb = fb.get("price")
        price_nfb = nfb.get("price")
        price_match_25 = (
            price_fb is not None
            and price_nfb is not None
            and _price_within_pct(price_fb, price_nfb, 0.25)
        )

        # Tier 10: phone + address, with rooms veto
        if phone_match and address_match:
            # Rooms veto: both known and differ -> skip
            if rooms_fb is not None and rooms_nfb is not None and float(rooms_fb) != float(rooms_nfb):
                continue
            matches_to_insert.append(
                (id_a, id_b, 10, "fb_phone_and_address", 0.95, True)
            )
            continue

        # Tier 11: address + rooms + price-within-25%
        if address_match and rooms_match and price_match_25:
            matches_to_insert.append(
                (id_a, id_b, 11, "fb_address_rooms_price", 0.80, True)
            )
            continue

        # Tier 12: address + price-within-25%
        if address_match and price_match_25:
            matches_to_insert.append(
                (id_a, id_b, 12, "fb_address_price", 0.65, None)
            )

    if not matches_to_insert:
        logger.info("fb_cross_source_match.done", session_id=session_id, new_matches=0)
        return 0

    # Dedup by (id_a, id_b) — keep best (lowest tier number)
    seen: dict[tuple[int, int], tuple] = {}
    for m in matches_to_insert:
        key = (m[0], m[1])
        if key not in seen or m[2] < seen[key][2]:
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

    logger.info("fb_cross_source_match.done", session_id=session_id, new_matches=inserted)
    return inserted


async def backfill_year_built_from_buildings(property_ids: list[int]) -> int:
    """For properties with NULL year_built, look up normalized address in building_metadata
    and copy year if found. Returns count updated."""
    from pdis.signals import _normalize_address
    if not property_ids:
        return 0
    async with _db.pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """SELECT id, address_city, address_street, address_home_number, year_built
                   FROM properties WHERE id = ANY(%s)""",
                (property_ids,),
            )
            props = await cur.fetchall()
            updates = []
            for p in props:
                if p["year_built"] is not None:
                    continue
                c, s, h = _normalize_address(p["address_city"], p["address_street"], p["address_home_number"])
                if not (c and s and h):
                    continue
                await cur.execute(
                    """SELECT year_built FROM building_metadata
                       WHERE city_norm = %s AND street_norm = %s AND house_number_norm = %s
                         AND year_built IS NOT NULL""",
                    (c, s, h),
                )
                row = await cur.fetchone()
                if row:
                    updates.append((row["year_built"], p["id"]))
            for year, pid in updates:
                await cur.execute(
                    "UPDATE properties SET year_built = %s, updated_at = NOW() WHERE id = %s",
                    (year, pid),
                )
        await conn.commit()
    logger.info("matching.year_built_backfilled_from_buildings", count=len(updates))
    return len(updates)


async def backfill_year_built_from_matches(property_ids: list[int]) -> int:
    """For properties with NULL year_built, check confirmed property_matches to other properties
    that have year_built. Copy over. Returns count updated."""
    if not property_ids:
        return 0
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """WITH targets AS (
                    SELECT id FROM properties
                    WHERE id = ANY(%s) AND year_built IS NULL
                ),
                matched AS (
                    SELECT t.id AS target_id, p_other.year_built
                    FROM targets t
                    JOIN property_matches m
                      ON (m.property_id_a = t.id OR m.property_id_b = t.id)
                     AND m.is_confirmed = TRUE
                    JOIN properties p_other
                      ON p_other.id = CASE WHEN m.property_id_a = t.id
                                           THEN m.property_id_b ELSE m.property_id_a END
                    WHERE p_other.year_built IS NOT NULL
                )
                UPDATE properties p
                   SET year_built = m.year_built, updated_at = NOW()
                  FROM (SELECT DISTINCT ON (target_id) target_id, year_built
                        FROM matched ORDER BY target_id, year_built DESC) m
                 WHERE p.id = m.target_id""",
                (property_ids,),
            )
            count = cur.rowcount
        await conn.commit()
    logger.info("matching.year_built_backfilled_from_matches", count=count)
    return count
