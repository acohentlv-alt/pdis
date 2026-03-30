"""Event detection: compare snapshots between scans."""
from datetime import date

import structlog

import pdis.database as _db

logger = structlog.get_logger(__name__)


async def detect_events(session_id: int, preset_id: int) -> int:
    """
    Compare current session's snapshots to the previous completed session
    for the SAME preset_id. Emit events for changes found.
    Returns count of events created.
    """
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            # Find the previous completed session for this preset
            await cur.execute(
                """SELECT id FROM scan_sessions
                   WHERE preset_id = %s AND id < %s AND status = 'done'
                   ORDER BY id DESC LIMIT 1""",
                (preset_id, session_id),
            )
            prev_session_row = await cur.fetchone()

            if not prev_session_row:
                # First successful scan for this preset — no events to detect
                logger.info("events.first_scan", session_id=session_id, preset_id=preset_id)
                return 0

            prev_session_id = prev_session_row["id"]

            # Compare current vs previous snapshots in one query
            await cur.execute(
                """
                WITH current_snap AS (
                    SELECT property_id, price, description_hash, image_hash
                    FROM property_snapshots
                    WHERE session_id = %s
                ),
                prev_snap AS (
                    SELECT property_id, price, description_hash, image_hash
                    FROM property_snapshots
                    WHERE session_id = %s
                )
                SELECT
                    c.property_id,
                    c.price AS new_price, p.price AS old_price,
                    c.description_hash AS new_desc_hash, p.description_hash AS old_desc_hash,
                    c.image_hash AS new_img_hash, p.image_hash AS old_img_hash,
                    p.property_id IS NULL AS is_new
                FROM current_snap c
                LEFT JOIN prev_snap p ON p.property_id = c.property_id
                """,
                (session_id, prev_session_id),
            )
            rows = await cur.fetchall()

            events = []
            today_str = date.today().isoformat()

            for row in rows:
                pid = row["property_id"]

                if row["is_new"]:
                    # Check if this is truly new or a relisting
                    await cur.execute(
                        "SELECT first_seen FROM properties WHERE id = %s", (pid,)
                    )
                    prop = await cur.fetchone()
                    if prop and prop["first_seen"].isoformat()[:10] < today_str:
                        events.append((pid, session_id, "relisting", None, None))
                    else:
                        events.append((pid, session_id, "new_listing", None, None))
                    continue

                # Price change (NULL guards)
                old_p = row["old_price"]
                new_p = row["new_price"]
                if old_p is not None and new_p is not None and old_p != new_p:
                    if new_p < old_p:
                        events.append((pid, session_id, "price_drop", str(old_p), str(new_p)))
                    else:
                        events.append((pid, session_id, "price_increase", str(old_p), str(new_p)))

                # Description change (NULL guards)
                old_d = row["old_desc_hash"]
                new_d = row["new_desc_hash"]
                if old_d != new_d and not (old_d is None and new_d is None):
                    events.append((pid, session_id, "description_change", old_d, new_d))

                # Image change (NULL guards)
                old_i = row["old_img_hash"]
                new_i = row["new_img_hash"]
                if old_i != new_i and not (old_i is None and new_i is None):
                    events.append((pid, session_id, "image_change", old_i, new_i))

            # Batch insert events
            if events:
                await cur.executemany(
                    """INSERT INTO property_events
                       (property_id, session_id, event_type, old_value, new_value)
                       VALUES (%s, %s, %s, %s, %s)""",
                    events,
                )

        await conn.commit()

    logger.info("events.detected", session_id=session_id, count=len(events))
    return len(events)


async def detect_removals(seen_yad2_ids: set[str], successful_preset_ids: set[int]) -> int:
    """
    Mark active properties as removed if not seen in any successful scan.
    Only considers properties belonging to presets that actually succeeded.
    session_id is NULL for removal events (they happen outside any single session).
    Returns count of removals.
    """
    if not seen_yad2_ids or not successful_preset_ids:
        return 0

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            # Find active properties from successful presets that were NOT seen
            await cur.execute(
                """SELECT id, yad2_id FROM properties
                   WHERE is_active = TRUE
                   AND preset_id = ANY(%s)
                   AND yad2_id != ALL(%s)""",
                (list(successful_preset_ids), list(seen_yad2_ids)),
            )
            removed = await cur.fetchall()

            if not removed:
                return 0

            removed_ids = [r["id"] for r in removed]

            # Create removal events (session_id = NULL)
            await cur.executemany(
                """INSERT INTO property_events (property_id, session_id, event_type)
                   VALUES (%s, NULL, 'removal')""",
                [(rid,) for rid in removed_ids],
            )

            # Mark as inactive
            await cur.execute(
                """UPDATE properties SET is_active = FALSE, updated_at = NOW()
                   WHERE id = ANY(%s)""",
                (removed_ids,),
            )

        await conn.commit()

    logger.info("events.removals", count=len(removed_ids))
    return len(removed_ids)
