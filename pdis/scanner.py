"""
Scanner orchestrator: load preset → scrape → upsert → snapshots → update session.
"""

import hashlib
import json

import structlog

import pdis.database as _db
from pdis.models import ScrapedListing, ScrapeResult
from pdis.scraper import scrape_preset
from pdis.scraper_madlan import scrape_madlan_preset
from pdis.config import settings

logger = structlog.get_logger(__name__)
log = logger

_SCAN_STALE_MINUTES = 30
_scan_progress: int | None = None   # None when idle, 0-100 while running


async def _update_progress(session_id: int, pct: int) -> None:
    """Update scan progress. Clamps 0-100. Sets module state AND writes to DB.
    Never fails the scan — log-only on error."""
    global _scan_progress
    clamped = max(0, min(100, int(pct)))
    _scan_progress = clamped
    try:
        async with _db.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE scan_sessions SET progress = %s WHERE id = %s",
                    (clamped, session_id),
                )
            await conn.commit()
    except Exception as exc:
        logger.warning("scanner.progress_update_failed", session_id=session_id, progress=clamped, error=str(exc))


async def _load_preset(preset_id: int) -> dict | None:
    """Fetch a single active preset by ID."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM search_presets WHERE id = %s",
                (preset_id,),
            )
            return await cur.fetchone()


async def _create_session(preset_id: int) -> int:
    """Insert a new scan_session row and return its ID."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO scan_sessions (preset_id, status)
                VALUES (%s, 'running')
                RETURNING id
                """,
                (preset_id,),
            )
            row = await cur.fetchone()
        await conn.commit()
    return row["id"]


async def _upsert_properties(
    listings: list[ScrapedListing], preset_id: int, session_id: int
) -> tuple[int, int]:
    """
    Upsert all listings into the properties table.
    Returns (total_upserted, new_count).
    """
    if not listings:
        return 0, 0

    new_count = 0
    total = 0

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            for listing in listings:
                image_urls_val = listing.image_urls if listing.image_urls else []
                raw_data_val = json.dumps(listing.raw_data) if listing.raw_data else "{}"

                await cur.execute(
                    """
                    INSERT INTO properties (
                        yad2_id, preset_id, category,
                        address_street, address_city, neighborhood,
                        address_home_number,
                        rooms, floor, total_floors, square_meters, square_meter_build,
                        price, currency, property_type,
                        description, contact_name, contact_phone,
                        image_urls, listing_url, raw_data,
                        yad2_date_added,
                        source, latitude, longitude,
                        parking, elevator, safe_room, renovated, balcony,
                        pets_allowed, furnished, air_conditioning,
                        is_agent, agent_office, move_in_date,
                        hood_id, customer_id, accessibility,
                        author_name, group_url, like_count,
                        year_built
                    ) VALUES (
                        %(yad2_id)s, %(preset_id)s, %(category)s,
                        %(address_street)s, %(address_city)s, %(neighborhood)s,
                        %(address_home_number)s,
                        %(rooms)s, %(floor)s, %(total_floors)s, %(square_meters)s, %(square_meter_build)s,
                        %(price)s, %(currency)s, %(property_type)s,
                        %(description)s, %(contact_name)s, %(contact_phone)s,
                        %(image_urls)s, %(listing_url)s, %(raw_data)s::jsonb,
                        %(yad2_date_added)s,
                        %(source)s, %(latitude)s, %(longitude)s,
                        %(parking)s, %(elevator)s, %(safe_room)s, %(renovated)s, %(balcony)s,
                        %(pets_allowed)s, %(furnished)s, %(air_conditioning)s,
                        %(is_agent)s, %(agent_office)s, %(move_in_date)s,
                        %(hood_id)s, %(customer_id)s, %(accessibility)s,
                        %(author_name)s, %(group_url)s, %(like_count)s,
                        %(year_built)s
                    )
                    ON CONFLICT (yad2_id) DO UPDATE SET
                        price           = EXCLUDED.price,
                        description     = EXCLUDED.description,
                        image_urls      = EXCLUDED.image_urls,
                        contact_name    = EXCLUDED.contact_name,
                        neighborhood    = EXCLUDED.neighborhood,
                        address_street  = EXCLUDED.address_street,
                        address_city    = EXCLUDED.address_city,
                        address_home_number = EXCLUDED.address_home_number,
                        rooms           = EXCLUDED.rooms,
                        floor           = EXCLUDED.floor,
                        square_meters   = EXCLUDED.square_meters,
                        square_meter_build = COALESCE(EXCLUDED.square_meter_build, properties.square_meter_build),
                        property_type   = EXCLUDED.property_type,
                        last_seen       = CURRENT_DATE,
                        yad2_date_added = COALESCE(EXCLUDED.yad2_date_added, properties.yad2_date_added),
                        days_on_market  = CASE
                            WHEN EXCLUDED.yad2_date_added IS NOT NULL THEN CURRENT_DATE - EXCLUDED.yad2_date_added::date
                            WHEN properties.yad2_date_added IS NOT NULL THEN CURRENT_DATE - properties.yad2_date_added::date
                            ELSE CURRENT_DATE - properties.first_seen
                        END,
                        raw_data        = EXCLUDED.raw_data,
                        is_active       = TRUE,
                        updated_at      = NOW(),
                        source          = EXCLUDED.source,
                        latitude        = COALESCE(EXCLUDED.latitude, properties.latitude),
                        longitude       = COALESCE(EXCLUDED.longitude, properties.longitude),
                        parking         = EXCLUDED.parking,
                        elevator        = EXCLUDED.elevator,
                        safe_room       = EXCLUDED.safe_room,
                        renovated       = EXCLUDED.renovated,
                        balcony         = EXCLUDED.balcony,
                        pets_allowed    = EXCLUDED.pets_allowed,
                        furnished       = EXCLUDED.furnished,
                        air_conditioning = EXCLUDED.air_conditioning,
                        is_agent        = EXCLUDED.is_agent,
                        agent_office    = EXCLUDED.agent_office,
                        move_in_date    = EXCLUDED.move_in_date,
                        hood_id         = EXCLUDED.hood_id,
                        customer_id     = EXCLUDED.customer_id,
                        accessibility   = EXCLUDED.accessibility,
                        author_name     = COALESCE(EXCLUDED.author_name, properties.author_name),
                        group_url       = COALESCE(EXCLUDED.group_url, properties.group_url),
                        like_count      = COALESCE(EXCLUDED.like_count, properties.like_count),
                        year_built      = COALESCE(EXCLUDED.year_built, properties.year_built)
                    RETURNING (xmax = 0) AS is_insert
                    """,
                    {
                        "yad2_id": listing.yad2_id,
                        "preset_id": preset_id,
                        "category": listing.category,
                        "address_street": listing.address_street,
                        "address_city": listing.address_city,
                        "neighborhood": listing.neighborhood,
                        "address_home_number": listing.address_home_number,
                        "rooms": listing.rooms,
                        "floor": listing.floor,
                        "total_floors": listing.total_floors,
                        "square_meters": listing.square_meters,
                        "square_meter_build": listing.square_meter_build,
                        "price": listing.price,
                        "currency": listing.currency,
                        "property_type": listing.property_type,
                        "description": listing.description,
                        "contact_name": listing.contact_name,
                        "contact_phone": listing.contact_phone,
                        "image_urls": image_urls_val,
                        "listing_url": listing.listing_url,
                        "raw_data": raw_data_val,
                        "yad2_date_added": listing.yad2_date_added,
                        "source": listing.source,
                        "latitude": listing.latitude,
                        "longitude": listing.longitude,
                        "parking": listing.parking,
                        "elevator": listing.elevator,
                        "safe_room": listing.safe_room,
                        "renovated": listing.renovated,
                        "balcony": listing.balcony,
                        "pets_allowed": listing.pets_allowed,
                        "furnished": listing.furnished,
                        "air_conditioning": listing.air_conditioning,
                        "is_agent": listing.is_agent,
                        "agent_office": listing.agent_office,
                        "move_in_date": listing.move_in_date,
                        "hood_id": listing.hood_id,
                        "customer_id": listing.customer_id,
                        "accessibility": listing.accessibility,
                        "author_name": listing.author_name,
                        "group_url": listing.group_url,
                        "like_count": listing.like_count,
                        "year_built": listing.year_built,
                    },
                )
                row = await cur.fetchone()
                total += 1
                if row and row["is_insert"]:
                    new_count += 1

        await conn.commit()

    return total, new_count


async def _create_snapshots(
    listings: list[ScrapedListing], session_id: int
) -> None:
    """Insert one snapshot per listing per session, ignoring duplicates."""
    if not listings:
        return

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            for listing in listings:
                # Look up the property id by yad2_id
                await cur.execute(
                    "SELECT id FROM properties WHERE yad2_id = %s",
                    (listing.yad2_id,),
                )
                prop_row = await cur.fetchone()
                if not prop_row:
                    continue

                raw_data_val = json.dumps(listing.raw_data) if listing.raw_data else "{}"

                desc_hash = (
                    hashlib.md5((listing.description or "").encode()).hexdigest()
                    if listing.description is not None
                    else None
                )
                img_hash = (
                    hashlib.md5(
                        ",".join(sorted(listing.image_urls or [])).encode()
                    ).hexdigest()
                    if listing.image_urls
                    else None
                )

                await cur.execute(
                    """
                    INSERT INTO property_snapshots
                        (property_id, session_id, price, is_listed, raw_data, description_hash, image_hash)
                    VALUES
                        (%s, %s, %s, TRUE, %s::jsonb, %s, %s)
                    ON CONFLICT (property_id, session_id) DO NOTHING
                    """,
                    (prop_row["id"], session_id, listing.price, raw_data_val, desc_hash, img_hash),
                )
        await conn.commit()


async def _get_property_ids_for_session(session_id: int) -> list[int]:
    """Return all property_ids that have a snapshot in the given session."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT DISTINCT property_id FROM property_snapshots WHERE session_id = %s",
                (session_id,),
            )
            rows = await cur.fetchall()
    return [r["property_id"] for r in rows]


async def _finish_session(
    session_id: int,
    result: ScrapeResult,
    new_count: int,
    status: str = "done",
    error_message: str | None = None,
) -> None:
    """Update the session row with final counts and status."""
    global _scan_progress
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE scan_sessions SET
                    finished_at     = NOW(),
                    status          = %s,
                    listings_found  = %s,
                    new_listings    = %s,
                    pages_scraped   = %s,
                    error_message   = %s,
                    progress        = CASE WHEN %s::text = 'done' THEN 100 ELSE progress END
                WHERE id = %s
                """,
                (
                    status,
                    len(result.listings),
                    new_count,
                    result.pages_scraped,
                    error_message,
                    status,
                    session_id,
                ),
            )
        await conn.commit()
    _scan_progress = None


async def _record_preset_stats(preset_id: int, session_id: int) -> None:
    """Record aggregated stats for this preset+session."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            # Count events by type for this session
            await cur.execute(
                """SELECT event_type, COUNT(*) as cnt
                   FROM property_events
                   WHERE session_id = %s
                   GROUP BY event_type""",
                (session_id,),
            )
            event_counts = {r["event_type"]: r["cnt"] for r in await cur.fetchall()}

            # Count active properties for this preset
            await cur.execute(
                "SELECT COUNT(*) as cnt FROM properties WHERE preset_id = %s AND is_active = TRUE",
                (preset_id,),
            )
            active_count = (await cur.fetchone())["cnt"]

            await cur.execute(
                """INSERT INTO scan_preset_stats
                   (preset_id, session_id, total_active, new_listings, removals,
                    price_drops, price_increases)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    preset_id, session_id, active_count,
                    event_counts.get("new_listing", 0),
                    event_counts.get("removal", 0),
                    event_counts.get("price_drop", 0),
                    event_counts.get("price_increase", 0),
                ),
            )
        await conn.commit()



async def _cache_madlan_years(listings: list[ScrapedListing]) -> None:
    """Cache year_built values from Madlan listings into building_metadata.
    TLV municipality data always wins (CASE clause in ON CONFLICT preserves it).
    """
    from pdis.signals import _normalize_address
    rows = []
    for listing in listings:
        if listing.year_built is None:
            continue
        c, s, h = _normalize_address(listing.address_city, listing.address_street, listing.address_home_number)
        if not (c and s and h):
            continue
        rows.append((c, s, h, listing.year_built, listing.latitude, listing.longitude))

    if not rows:
        return

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            for c, s, h, year, lat, lon in rows:
                await cur.execute(
                    """INSERT INTO building_metadata
                       (city_norm, street_norm, house_number_norm, year_built, source, raw_lat, raw_lon, updated_at)
                       VALUES (%s, %s, %s, %s, 'madlan_cache', %s, %s, NOW())
                       ON CONFLICT (city_norm, street_norm, house_number_norm) DO UPDATE SET
                           year_built = CASE
                               WHEN building_metadata.source = 'tlv_municipality' THEN building_metadata.year_built
                               ELSE EXCLUDED.year_built
                           END,
                           source = CASE
                               WHEN building_metadata.source = 'tlv_municipality' THEN 'tlv_municipality'
                               ELSE 'madlan_cache'
                           END,
                           raw_lat = COALESCE(EXCLUDED.raw_lat, building_metadata.raw_lat),
                           raw_lon = COALESCE(EXCLUDED.raw_lon, building_metadata.raw_lon),
                           updated_at = NOW()""",
                    (c, s, h, year, lat, lon),
                )
        await conn.commit()

    logger.info("scanner.madlan_years_cached", count=len(rows))


async def _yad2_phone_scan_hook(session_id: int) -> None:
    """Fetch Yad2 phones for listings in this session that are either new-this-session
    or already carry any distress signal AND have no phone yet. Capped per scan.
    Runs AFTER persist_signals_batch so property_classifications is populated.
    Never raises — log-only on failure.
    """
    if not settings.yad2_phone_fetch_enabled:
        return
    from pdis.yad2_phone import fetch_phones
    cap = settings.yad2_phone_scan_cap
    cooldown = settings.yad2_phone_retry_cooldown_days
    try:
        async with _db.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """SELECT p.yad2_id
                       FROM properties p
                       JOIN property_snapshots ps ON ps.property_id = p.id
                       LEFT JOIN property_classifications pc ON pc.property_id = p.id
                       WHERE ps.session_id = %s
                         AND p.source = 'yad2'
                         AND p.contact_phone IS NULL
                         AND (p.phone_fetch_attempted_at IS NULL
                              OR p.phone_fetch_attempted_at < NOW() - make_interval(days => %s))
                         AND (
                              p.first_seen >= (SELECT started_at::date FROM scan_sessions WHERE id = %s)
                              OR (pc.signal_details IS NOT NULL
                                  AND (jsonb_array_length(COALESCE(pc.signal_details->'strong_signals','[]'::jsonb)) > 0
                                    OR jsonb_array_length(COALESCE(pc.signal_details->'weak_signals','[]'::jsonb)) > 0))
                         )
                       ORDER BY
                         CASE WHEN p.first_seen >= (SELECT started_at::date FROM scan_sessions WHERE id = %s)
                              THEN 0 ELSE 1 END,
                         p.last_seen DESC
                       LIMIT %s""",
                    (session_id, cooldown, session_id, session_id, cap),
                )
                tokens = [r["yad2_id"] for r in await cur.fetchall()]
    except Exception as exc:
        logger.warning("yad2_phone.select_failed", error=str(exc))
        return

    if not tokens:
        return

    logger.info("yad2_phone.scan_fetching", count=len(tokens))
    phones = await fetch_phones(tokens)
    filled = await _persist_yad2_phones(phones, tokens)
    logger.info("yad2_phone.scan_done", attempted=len(tokens), filled=filled)


async def _yad2_phone_backfill() -> None:
    """Drain the historical backlog of null-phone Yad2 properties (any status,
    including blacklisted). Runs at the tail of run_all_scans. 7-day cooldown
    applies uniformly to both 'no phone returned' and 'blocked'.
    """
    if not settings.yad2_phone_fetch_enabled:
        return
    from pdis.yad2_phone import fetch_phones
    limit = settings.yad2_phone_backfill_batch_size
    cooldown = settings.yad2_phone_retry_cooldown_days
    try:
        async with _db.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """SELECT yad2_id FROM properties
                       WHERE source = 'yad2'
                         AND contact_phone IS NULL
                         AND (phone_fetch_attempted_at IS NULL
                              OR phone_fetch_attempted_at < NOW() - make_interval(days => %s))
                       ORDER BY last_seen DESC, id ASC
                       LIMIT %s""",
                    (cooldown, limit),
                )
                tokens = [r["yad2_id"] for r in await cur.fetchall()]
    except Exception as exc:
        logger.warning("yad2_phone.backfill_select_failed", error=str(exc))
        return

    if not tokens:
        return

    logger.info("yad2_phone.backfill_fetching", count=len(tokens))
    phones = await fetch_phones(tokens)
    filled = await _persist_yad2_phones(phones, tokens)
    logger.info("yad2_phone.backfill_done", attempted=len(tokens), filled=filled)


async def _persist_yad2_phones(phones: dict[str, str | None], attempted: list[str]) -> int:
    """Write phone values back. Mark ALL attempted ids with phone_fetch_attempted_at = NOW()
    regardless of outcome, so the cooldown covers both genuine-no-phone and blocked cases.
    Returns count of rows that got a non-null phone.
    """
    filled = 0
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE properties SET phone_fetch_attempted_at = NOW() WHERE yad2_id = ANY(%s)",
                (attempted,),
            )
            for token, phone in phones.items():
                if phone:
                    await cur.execute(
                        "UPDATE properties SET contact_phone = %s, updated_at = NOW() WHERE yad2_id = %s AND contact_phone IS NULL",
                        (phone, token),
                    )
                    if cur.rowcount:
                        filled += 1
        await conn.commit()
    return filled


async def run_scan(preset_id: int) -> dict:
    """
    Run a full scan for a single preset.
    Returns a summary dict with session details.
    """
    log = logger.bind(preset_id=preset_id)

    preset = await _load_preset(preset_id)
    if not preset:
        raise ValueError(f"Preset {preset_id} not found")

    if not preset.get("scan_enabled"):
        raise ValueError(f"Preset {preset_id} is not scan-enabled")

    session_id = await _create_session(preset_id)
    log = log.bind(session_id=session_id)
    log.info("scanner.session_created")

    error_message = None
    status = "done"
    result = ScrapeResult()
    new_count = 0
    event_count = 0
    match_count = 0
    relist_count = 0

    # Hoist source detection BEFORE try so VM-skip can return without entering finally
    _extra = preset.get("extra_params") or {}
    if isinstance(_extra, str):
        import json as _json
        _extra = _json.loads(_extra)
    _source = _extra.get("source", "yad2")

    # VM-skip: ALL Yad2 scraping routed through Oracle VM when flag is set
    # (Render-IP blocked on /forsale by ShieldSquare; /rent started blocking 2026-04-18.
    # Consolidated to single 10:00 IDT VM run.)
    if _source == "yad2" and getattr(settings, "yad2_vm_ingestion_enabled", False):
        log.info("scanner.yad2_skipped_vm", preset_id=preset_id,
                 preset_name=preset["name"], category=preset["category"])
        await _finish_session(session_id, result, new_count,
                              status="skipped_vm",
                              error_message="Yad2 scraping routed through Oracle VM")
        return {
            "session_id": session_id, "preset_id": preset_id,
            "preset_name": preset["name"], "status": "skipped_vm",
            "listings_found": 0, "new_listings": 0, "pages_scraped": 0,
            "duration_seconds": 0.0, "was_blocked": False, "errors": [],
            "events_detected": 0, "matches_found": 0, "customer_relistings": 0,
        }

    # FB-skip: facebook scraping is routed through Oracle VM scraper
    if _source == "facebook":
        log.info("scanner.fb_preset_skipped_handled_by_vm", preset_id=preset_id, preset_name=preset["name"])
        await _finish_session(session_id, result, new_count,
                              status="skipped_vm",
                              error_message="Facebook scraping routed through Oracle VM")
        return {
            "session_id": session_id, "preset_id": preset_id,
            "preset_name": preset["name"], "status": "skipped_vm",
            "listings_found": 0, "new_listings": 0, "pages_scraped": 0,
            "duration_seconds": 0.0, "was_blocked": False, "errors": [],
            "events_detected": 0, "matches_found": 0, "customer_relistings": 0,
        }

    # Set initial progress to 0 — signals scan has started
    await _update_progress(session_id, 0)

    try:
        async def progress_cb(p: int) -> None:
            await _update_progress(session_id, p)

        if _source == "madlan":
            result = await scrape_madlan_preset(dict(preset), progress_cb=progress_cb)
        else:
            result = await scrape_preset(dict(preset), progress_cb=progress_cb)

        if result.was_blocked and len(result.listings) == 0:
            status = "blocked"
            error_message = f"{_source.capitalize()} blocked the request — zero listings retrieved"
        elif result.was_blocked and len(result.listings) > 0:
            status = "done"
            error_message = f"Partial block detected on final page but {len(result.listings)} listings collected successfully"
            log.warning("scanner.partial_block", listings=len(result.listings))
        elif result.errors:
            status = "error"
            error_message = "; ".join(result.errors[:3])

        total, new_count = await _upsert_properties(result.listings, preset_id, session_id)
        await _create_snapshots(result.listings, session_id)
        await _update_progress(session_id, 92)

        log.info(
            "scanner.upserted",
            total=total,
            new=new_count,
            blocked=result.was_blocked,
        )

        # Cache Madlan year_built values into building_metadata
        if _source == "madlan":
            await _cache_madlan_years(result.listings)

        from pdis.events import detect_events
        from pdis.classification import persist_signals_batch
        from pdis.matching import find_matches, find_fb_cross_source_matches, detect_customer_relistings, backfill_year_built_from_matches, backfill_year_built_from_buildings

        # Detect events by comparing to previous snapshots
        event_count = await detect_events(session_id, preset_id)
        log.info("scanner.events_detected", count=event_count)
        await _update_progress(session_id, 95)

        # Find property matches (before signal persistence so year backfills can use confirmed matches)
        match_count = await find_matches(session_id)
        if match_count > 0:
            log.info("scanner.matches_found", count=match_count)
        fb_match_count = await find_fb_cross_source_matches(session_id)
        if fb_match_count > 0:
            log.info("scanner.fb_matches_found", count=fb_match_count)
        match_count += fb_match_count
        await _update_progress(session_id, 97)

        # Backfill year_built from matches and building_metadata before signal persistence
        property_ids = await _get_property_ids_for_session(session_id)
        if property_ids:
            await backfill_year_built_from_matches(property_ids)
            await backfill_year_built_from_buildings(property_ids)

        # Persist signals for all properties seen in this scan (after year backfills)
        if property_ids:
            await persist_signals_batch(property_ids)
            log.info("scanner.signals_persisted", count=len(property_ids))

        # Yad2 phone capture — new + signaled listings only, capped
        if _source == "yad2":
            await _yad2_phone_scan_hook(session_id)

        await _update_progress(session_id, 99)

        relist_count = await detect_customer_relistings(session_id)
        if relist_count > 0:
            log.info("scanner.customer_relistings", count=relist_count)

        # Record per-preset stats
        await _record_preset_stats(preset_id, session_id)

    except Exception as exc:
        log.error("scanner.failed", error=str(exc))
        status = "error"
        error_message = str(exc)

    finally:
        await _finish_session(
            session_id, result, new_count, status=status, error_message=error_message
        )

    return {
        "session_id": session_id,
        "preset_id": preset_id,
        "preset_name": preset["name"],
        "status": status,
        "listings_found": len(result.listings),
        "new_listings": new_count,
        "pages_scraped": result.pages_scraped,
        "duration_seconds": result.duration_seconds,
        "was_blocked": result.was_blocked,
        "errors": result.errors,
        "events_detected": event_count,
        "matches_found": match_count,
        "customer_relistings": relist_count,
    }


async def _mark_fb_removals_for_session(session_id: int) -> int:
    """
    Mirror events.detect_removals but FB-scoped only.
    Marks FB properties not seen in this session as removed.
    Returns count of removed properties.
    """
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            # Find FB properties that are active but not in this session's snapshots
            await cur.execute(
                """
                SELECT id FROM properties
                WHERE is_active = TRUE
                  AND source = 'facebook'
                  AND id NOT IN (
                      SELECT property_id FROM property_snapshots WHERE session_id = %s
                  )
                """,
                (session_id,),
            )
            removed_rows = await cur.fetchall()

            if not removed_rows:
                return 0

            removed_ids = [r["id"] for r in removed_rows]

            # Insert removal events (session_id = NULL for removals — mirrors events.py:155-159)
            await cur.executemany(
                """INSERT INTO property_events (property_id, session_id, event_type)
                   VALUES (%s, NULL, 'removal')""",
                [(rid,) for rid in removed_ids],
            )

            # Mark as inactive — mirrors events.py:163
            await cur.execute(
                """UPDATE properties SET is_active = FALSE, updated_at = NOW()
                   WHERE id = ANY(%s)""",
                (removed_ids,),
            )

        await conn.commit()

    logger.info("scanner.fb_removals", session_id=session_id, count=len(removed_ids))
    return len(removed_ids)


async def run_scan_from_listings(preset_id: int, listings: list[ScrapedListing], source: str = "facebook") -> dict:
    """
    Run full PDIS pipeline against pre-scraped listings (e.g., from Facebook or Yad2 VM ingest).
    Skips the scrape step — listings are provided directly.
    """
    log = logger.bind(preset_id=preset_id, source=source)

    # Low-volume guard:
    # - Facebook: sampling ingest by design (5 posts/group × 14 groups = 70 raw,
    #   minus text drops + intent filter = ~10-20 POSTed per run). No lower bound
    #   to enforce — removal detection is disabled for FB anyway (see ca608dc),
    #   so a small batch can't nuke rows.
    # - Yad2/Madlan: per-preset ingest. Completely empty batch = scraper hit a
    #   block; anything non-empty is a valid partial result.
    if source == "facebook":
        pass  # no threshold for sampling ingest
    else:
        if not listings:
            log.warning("scanner.ingest_empty_batch", source=source)
            return {
                "status": "suspicious_low_volume",
                "received": 0,
                "prior_count": 0,
            }

    session_id = await _create_session(preset_id)
    log = log.bind(session_id=session_id)
    log.info("scanner.ingest_session_created")

    new_count = 0
    event_count = 0
    match_count = 0
    relist_count = 0
    removal_count = 0
    status = "done"
    error_message = None

    try:
        total, new_count = await _upsert_properties(listings, preset_id, session_id)
        await _create_snapshots(listings, session_id)

        log.info("scanner.ingest_upserted", total=total, new=new_count)

        from pdis.events import detect_events
        from pdis.classification import persist_signals_batch
        from pdis.matching import find_matches, find_fb_cross_source_matches, detect_customer_relistings, backfill_year_built_from_matches, backfill_year_built_from_buildings

        event_count = await detect_events(session_id, preset_id)
        log.info("scanner.ingest_events_detected", count=event_count)

        # Find property matches (before signal persistence so year backfills can use confirmed matches)
        match_count = await find_matches(session_id)
        if match_count > 0:
            log.info("scanner.ingest_matches_found", count=match_count)
        fb_match_count = await find_fb_cross_source_matches(session_id)
        if fb_match_count > 0:
            log.info("scanner.fb_matches_found", count=fb_match_count)
        match_count += fb_match_count

        # Backfill year_built from matches and building_metadata before signal persistence
        property_ids = await _get_property_ids_for_session(session_id)
        if property_ids:
            await backfill_year_built_from_matches(property_ids)
            await backfill_year_built_from_buildings(property_ids)

        # Persist signals for all properties seen in this scan (after year backfills)
        if property_ids:
            await persist_signals_batch(property_ids)
            log.info("scanner.signals_persisted", count=len(property_ids))

        # Yad2 phone capture for VM-ingested listings
        if source == "yad2":
            await _yad2_phone_scan_hook(session_id)

        relist_count = await detect_customer_relistings(session_id)
        if relist_count > 0:
            log.info("scanner.ingest_customer_relistings", count=relist_count)

        # FB removal detection is DISABLED — Apify runs with resultsLimit=5 per
        # group (sampling), so "not in this ingest" != "removed from FB". FB posts
        # also stay in groups indefinitely. Re-enable only if we switch to an
        # exhaustive sweep.
        removal_count = 0

        await _record_preset_stats(preset_id, session_id)

    except Exception as exc:
        log.error("scanner.ingest_failed", error=str(exc))
        status = "error"
        error_message = str(exc)

    finally:
        result = ScrapeResult(listings=listings)
        await _finish_session(session_id, result, new_count, status=status, error_message=error_message)

    return {
        "session_id": session_id,
        "preset_id": preset_id,
        "status": status,
        "listings_found": len(listings),
        "new_listings": new_count,
        "events_detected": event_count,
        "matches_found": match_count,
        "customer_relistings": relist_count,
        "removals": removal_count,
        "error_message": error_message,
    }


async def run_all_scans() -> list[dict]:
    """Run scans for all active presets sequentially."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM search_presets WHERE scan_enabled = TRUE ORDER BY id"
            )
            rows = await cur.fetchall()

    preset_ids = [r["id"] for r in rows]
    results = []
    for pid in preset_ids:
        summary = await run_scan(pid)
        results.append(summary)

    # Collect yad2_ids from SUCCESSFUL scans only (not blocked/error)
    all_seen_yad2_ids: set[str] = set()
    successful_preset_ids: set[int] = set()
    for scan_result in results:
        if scan_result.get("status") == "done":
            successful_preset_ids.add(scan_result["preset_id"])
            session_id = scan_result["session_id"]
            async with _db.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """SELECT p.yad2_id FROM property_snapshots ps
                           JOIN properties p ON p.id = ps.property_id
                           WHERE ps.session_id = %s""",
                        (session_id,),
                    )
                    rows = await cur.fetchall()
                    all_seen_yad2_ids.update(r["yad2_id"] for r in rows)

    # Only detect removals if at least one preset succeeded
    if all_seen_yad2_ids and successful_preset_ids:
        from pdis.events import detect_removals
        removal_count = await detect_removals(all_seen_yad2_ids, successful_preset_ids)
        if removal_count > 0:
            logger.info("scanner.removals_detected", count=removal_count)

    # Drain historical Yad2 null-phone backlog
    await _yad2_phone_backfill()

    return results


async def _expire_stale_running_sessions() -> int:
    """Mark scan_sessions stuck in 'running' for > _SCAN_STALE_MINUTES as errored.
    Returns count expired."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                UPDATE scan_sessions
                   SET status = 'error',
                       finished_at = NOW(),
                       error_message = COALESCE(error_message, 'stale — auto-expired after {_SCAN_STALE_MINUTES}min')
                 WHERE status = 'running'
                   AND started_at < NOW() - INTERVAL '{_SCAN_STALE_MINUTES} minutes'
                """
            )
            expired = cur.rowcount or 0
        await conn.commit()
    if expired > 0:
        log.warning("scanner.stale_sessions_expired", count=expired)
    return expired


async def _is_scan_running() -> bool:
    """True if any scan_session is 'running' within the stale window."""
    await _expire_stale_running_sessions()
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT 1 FROM scan_sessions
                 WHERE status = 'running'
                   AND started_at >= NOW() - INTERVAL '{_SCAN_STALE_MINUTES} minutes'
                 LIMIT 1
                """
            )
            row = await cur.fetchone()
    return row is not None


async def scheduled_scan() -> dict:
    """Called by the cron endpoint. Runs all scans — DB-backed lock checked by caller."""
    try:
        results = await run_all_scans()
        return {"status": "done", "presets": len(results), "results": results}
    except Exception as e:
        log.error("scan.scheduled.error", error=str(e))
        return {"status": "error", "error": str(e)}
    finally:
        global _scan_progress
        _scan_progress = None


async def get_scan_status() -> dict:
    """Current scan running state. DB-backed lock + module progress."""
    return {
        "running": await _is_scan_running(),
        "progress": _scan_progress,
    }
