"""
Scanner orchestrator: load preset → scrape → upsert → snapshots → update session.
"""

import hashlib
import json
import time as _time

import structlog

import asyncio

import pdis.database as _db
from pdis.models import ScrapedListing, ScrapeResult
from pdis.scraper import scrape_preset, fetch_item_detail
from pdis.scraper_madlan import scrape_madlan_preset

logger = structlog.get_logger(__name__)
log = logger

_scan_running = False
_scan_started_at: float | None = None


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
                        hood_id, customer_id, accessibility
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
                        %(hood_id)s, %(customer_id)s, %(accessibility)s
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
                        accessibility   = EXCLUDED.accessibility
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
                    error_message   = %s
                WHERE id = %s
                """,
                (
                    status,
                    len(result.listings),
                    new_count,
                    result.pages_scraped,
                    error_message,
                    session_id,
                ),
            )
        await conn.commit()


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

            # Count opportunities (hot+warm) for this preset
            await cur.execute(
                """SELECT COUNT(*) as cnt FROM property_classifications pc
                   JOIN properties p ON p.id = pc.property_id
                   WHERE p.preset_id = %s AND pc.classification IN ('hot', 'warm')""",
                (preset_id,),
            )
            opp_count = (await cur.fetchone())["cnt"]

            await cur.execute(
                """INSERT INTO scan_preset_stats
                   (preset_id, session_id, total_active, new_listings, removals,
                    price_drops, price_increases, opportunities)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    preset_id, session_id, active_count,
                    event_counts.get("new_listing", 0),
                    event_counts.get("removal", 0),
                    event_counts.get("price_drop", 0),
                    event_counts.get("price_increase", 0),
                    opp_count,
                ),
            )
        await conn.commit()


async def _backfill_built_sqm(listings: list[ScrapedListing], log) -> None:
    """Fetch square_meter_build and description from Yad2 detail API for properties missing them."""
    # Find yad2_ids that are missing square_meter_build OR have a short/missing description
    yad2_ids = [l.yad2_id for l in listings if l.source == "yad2"]
    if not yad2_ids:
        return

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """SELECT yad2_id FROM properties
                   WHERE yad2_id = ANY(%s)
                   AND (
                       square_meter_build IS NULL
                       OR description IS NULL
                       OR LENGTH(description) < 30
                   )""",
                (yad2_ids,),
            )
            missing = [r["yad2_id"] for r in await cur.fetchall()]

    if not missing:
        return

    log.info("scanner.fetching_detail", count=len(missing))
    updated = 0
    for yad2_id in missing:
        detail = await asyncio.to_thread(fetch_item_detail, yad2_id)
        if detail:
            updates = {}
            if detail.get("square_meter_build") is not None:
                try:
                    updates["square_meter_build"] = int(detail["square_meter_build"])
                except (ValueError, TypeError):
                    pass
            if detail.get("info_text"):
                updates["description"] = detail["info_text"]

            if updates:
                set_clause = ", ".join(f"{k} = %s" for k in updates)
                values = list(updates.values()) + [yad2_id]
                async with _db.pool.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            f"UPDATE properties SET {set_clause} WHERE yad2_id = %s",
                            values,
                        )
                    await conn.commit()
                updated += 1
        await asyncio.sleep(0.3)  # rate limit

    log.info("scanner.detail_filled", updated=updated, total=len(missing))


async def run_scan(preset_id: int) -> dict:
    """
    Run a full scan for a single preset.
    Returns a summary dict with session details.
    """
    log = logger.bind(preset_id=preset_id)

    preset = await _load_preset(preset_id)
    if not preset:
        raise ValueError(f"Preset {preset_id} not found")

    if not preset.get("is_active"):
        raise ValueError(f"Preset {preset_id} is not active")

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

    try:
        # Detect source from preset extra_params
        _extra = preset.get("extra_params") or {}
        if isinstance(_extra, str):
            import json as _json
            _extra = _json.loads(_extra)
        _source = _extra.get("source", "yad2")

        if _source == "madlan":
            result = await scrape_madlan_preset(dict(preset))
        else:
            result = await scrape_preset(dict(preset))

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

        log.info(
            "scanner.upserted",
            total=total,
            new=new_count,
            blocked=result.was_blocked,
        )

        # Fetch square_meter_build from detail API for properties that don't have it
        if _source == "yad2":
            await _backfill_built_sqm(result.listings, log)

        from pdis.events import detect_events
        from pdis.classification import classify_batch

        # Detect events by comparing to previous snapshots
        event_count = await detect_events(session_id, preset_id)
        log.info("scanner.events_detected", count=event_count)

        # Classify all properties seen in this scan
        property_ids = await _get_property_ids_for_session(session_id)
        if property_ids:
            await classify_batch(property_ids)
            log.info("scanner.classified", count=len(property_ids))

        # Find property matches
        from pdis.matching import find_matches, detect_customer_relistings
        match_count = await find_matches(session_id)
        if match_count > 0:
            log.info("scanner.matches_found", count=match_count)

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


async def run_all_scans() -> list[dict]:
    """Run scans for all active presets sequentially."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM search_presets WHERE is_active = TRUE ORDER BY id"
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

    return results


async def scheduled_scan() -> dict:
    """Called by the cron endpoint. Runs all scans with lock protection."""
    global _scan_running, _scan_started_at
    if _scan_running:
        return {"status": "skipped", "reason": "scan already running"}

    _scan_running = True
    _scan_started_at = _time.time()
    try:
        results = await run_all_scans()
        return {"status": "done", "presets": len(results), "results": results}
    except Exception as e:
        log.error("scan.scheduled.error", error=str(e))
        return {"status": "error", "error": str(e)}
    finally:
        _scan_running = False
        _scan_started_at = None


def get_scan_status() -> dict:
    """Return current scan running state."""
    result = {"running": _scan_running}
    if _scan_running and _scan_started_at:
        result["running_for_seconds"] = int(_time.time() - _scan_started_at)
    return result
