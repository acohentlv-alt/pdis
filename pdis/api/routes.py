"""
PDIS API routes.
"""

import json
import re
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from psycopg.rows import dict_row
from pydantic import BaseModel
from typing import Optional

import structlog

import pdis.database as _db
from pdis.database import check_connection
from pdis.models import ScrapedListing
from pdis.scanner import run_scan, run_all_scans, run_scan_from_listings
from pdis.signals import compute_signals_batch

logger = structlog.get_logger(__name__)
router = APIRouter()

_URL_RE = re.compile(r"https?://\S+")


def _scrub_error_message(msg: str | None) -> str | None:
    """Truncate to 200 chars and replace URLs with [url]."""
    if not msg:
        return msg
    scrubbed = _URL_RE.sub("[url]", msg)
    if len(scrubbed) > 200:
        scrubbed = scrubbed[:197] + "..."
    return scrubbed

FB_OPT_IN_SOURCES = {"yad2_facebook", "madlan_facebook", "all", "facebook"}
MADLAN_SOURCES = {"madlan", "yad2_madlan", "madlan_facebook", "all", "both"}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/api/health")
async def health():
    db_ok = await check_connection()
    return {"status": "ok", "db_connected": db_ok, "version": "0.1.0"}


# ---------------------------------------------------------------------------
# Neighborhoods
# ---------------------------------------------------------------------------

@router.get("/api/neighborhoods")
async def list_neighborhoods(city_code: str = Query(default=None)):
    """Return distinct hood_id/neighborhood pairs, grouped by city if city_code given."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            if city_code:
                await cur.execute(
                    "SELECT id FROM search_presets WHERE city_code = %s",
                    (city_code,),
                )
                preset_ids = [r["id"] for r in await cur.fetchall()]
                if not preset_ids:
                    return {"neighborhoods": []}
                await cur.execute(
                    """SELECT DISTINCT hood_id, neighborhood, COUNT(*) as listing_count
                       FROM properties
                       WHERE hood_id IS NOT NULL AND neighborhood IS NOT NULL
                         AND (preset_id = ANY(%s) OR preset_id IS NULL)
                       GROUP BY hood_id, neighborhood
                       ORDER BY neighborhood""",
                    (preset_ids,),
                )
            else:
                await cur.execute(
                    """SELECT DISTINCT hood_id, neighborhood, COUNT(*) as listing_count
                       FROM properties
                       WHERE hood_id IS NOT NULL AND neighborhood IS NOT NULL
                       GROUP BY hood_id, neighborhood
                       ORDER BY neighborhood"""
                )
            rows = await cur.fetchall()
    return {"neighborhoods": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

@router.get("/api/presets")
async def list_presets(is_active: bool | None = Query(default=None)):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            if is_active is not None:
                await cur.execute(
                    "SELECT * FROM search_presets WHERE is_active = %s ORDER BY created_at DESC",
                    (is_active,),
                )
            else:
                await cur.execute("SELECT * FROM search_presets ORDER BY id")
            rows = await cur.fetchall()
    return {"presets": [dict(r) for r in rows]}


# IMPORTANT: /api/presets/stats/latest must be registered BEFORE /api/presets/{preset_id}/stats
@router.get("/api/presets/stats/latest")
async def get_latest_preset_stats(category: str | None = Query(default=None)):
    """Return the latest stats for ALL presets (one row per preset from the most recent session)."""
    category_clause = ""
    params_list: list = []
    if category:
        category_clause = "AND sp.category = %s"
        params_list.append(category)

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT DISTINCT ON (sps.preset_id)
                    sps.preset_id, sp.name AS preset_name,
                    sps.session_id, sps.total_active, sps.new_listings,
                    sps.removals, sps.price_drops, sps.price_increases,
                    sps.created_at
                FROM scan_preset_stats sps
                JOIN search_presets sp ON sp.id = sps.preset_id
                WHERE TRUE
                {category_clause}
                ORDER BY sps.preset_id, sps.created_at DESC
                """,
                tuple(params_list),
            )
            rows = await cur.fetchall()
    return {"presets": [dict(r) for r in rows]}


@router.get("/api/presets/{preset_id}/properties")
async def get_preset_properties(
    preset_id: int,
    page: int = Query(default=1),
    per_page: int = Query(default=500),
):
    """Return properties matching a preset's criteria (city-scoped, not preset_id filtered)."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            # 1. Load the preset
            await cur.execute("SELECT * FROM search_presets WHERE id = %s", (preset_id,))
            preset = await cur.fetchone()
            if not preset:
                raise HTTPException(404, "Preset not found")
            preset = dict(preset)

            # 2. Find all preset IDs with the same city_code
            await cur.execute(
                "SELECT id FROM search_presets WHERE city_code = %s",
                (preset["city_code"],),
            )
            city_preset_ids = [r["id"] for r in await cur.fetchall()]

            # If the viewed preset is NOT a FB-opt-in source, exclude any pure-FB preset
            _preset_extra = preset.get("extra_params") or {}
            if isinstance(_preset_extra, str):
                import json as _j
                _preset_extra = _j.loads(_preset_extra)
            _viewed_source = _preset_extra.get("source", "yad2")
            if _viewed_source not in FB_OPT_IN_SOURCES:
                await cur.execute(
                    "SELECT id FROM search_presets WHERE extra_params->>'source' = 'facebook' LIMIT 1"
                )
                fb_row = await cur.fetchone()
                if fb_row:
                    city_preset_ids = [pid for pid in city_preset_ids if pid != fb_row["id"]]

            # 3. Build dynamic WHERE clauses
            conditions = [
                "(p.preset_id = ANY(%s) OR p.preset_id IS NULL)",
                "p.category = %s",
                "p.is_active = TRUE",
                "bl.id IS NULL",
            ]
            params: list = [city_preset_ids, preset["category"]]

            if preset.get("min_price") is not None:
                conditions.append("p.price >= %s")
                params.append(preset["min_price"])
            if preset.get("max_price") is not None:
                conditions.append("p.price <= %s")
                params.append(preset["max_price"])
            if preset.get("min_rooms") is not None:
                conditions.append("p.rooms >= %s")
                params.append(preset["min_rooms"])
            if preset.get("max_rooms") is not None:
                conditions.append("p.rooms <= %s")
                params.append(preset["max_rooms"])

            property_types = preset.get("property_types")
            if property_types:
                conditions.append("p.property_type = ANY(%s)")
                params.append(property_types)

            neighborhood = preset.get("neighborhood")
            if neighborhood and neighborhood.strip():
                try:
                    hood_ids = [int(x.strip()) for x in neighborhood.split(",") if x.strip().isdigit()]
                    if hood_ids:
                        conditions.append("p.hood_id = ANY(%s)")
                        params.append(hood_ids)
                except (ValueError, AttributeError):
                    pass

            where_clause = " AND ".join(conditions)

            # 4. Count total
            await cur.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM properties p
                LEFT JOIN property_classifications pc ON pc.property_id = p.id
                LEFT JOIN blacklist bl ON bl.property_id = p.id
                WHERE {where_clause}
                """,
                tuple(params),
            )
            total_row = await cur.fetchone()
            total = total_row["total"] if total_row else 0

            # 5. Fetch paginated results
            offset = (page - 1) * per_page
            params_with_pagination = params + [per_page, offset]

            await cur.execute(
                f"""
                SELECT
                    p.*,
                    pc.signal_details,
                    (
                        SELECT ARRAY_AGG(DISTINCT p2.source)
                        FROM property_matches pm
                        JOIN properties p2 ON p2.id = CASE
                            WHEN pm.property_id_a = p.id THEN pm.property_id_b
                            ELSE pm.property_id_a END
                        WHERE pm.property_id_a = p.id OR pm.property_id_b = p.id
                    ) AS matched_sources
                FROM properties p
                LEFT JOIN property_classifications pc ON pc.property_id = p.id
                LEFT JOIN blacklist bl ON bl.property_id = p.id
                WHERE {where_clause}
                ORDER BY
                    COALESCE(p.days_on_market, 0) DESC,
                    p.updated_at DESC
                LIMIT %s OFFSET %s
                """,
                tuple(params_with_pagination),
            )
            rows = await cur.fetchall()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "properties": [dict(r) for r in rows],
    }


@router.get("/api/presets/{preset_id}/stats")
async def get_preset_stats(preset_id: int):
    """Return recent scan_preset_stats for a preset (last 20 sessions)."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT session_id, total_active, new_listings, removals,
                       price_drops, price_increases, created_at
                FROM scan_preset_stats
                WHERE preset_id = %s
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (preset_id,),
            )
            rows = await cur.fetchall()
    return {"preset_id": preset_id, "stats": [dict(r) for r in rows]}


# IMPORTANT: /api/presets/{preset_id}/last-session must be after /api/presets/stats/latest
@router.get("/api/presets/{preset_id}/last-session")
async def get_preset_last_session(preset_id: int):
    """Return the latest scan_sessions row for a preset (for live progress bar)."""
    async with _db.pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id AS session_id, started_at, finished_at, status,
                       listings_found, new_listings, error_message, progress
                FROM scan_sessions
                WHERE preset_id = %s
                ORDER BY started_at DESC LIMIT 1
                """,
                (preset_id,),
            )
            row = await cur.fetchone()
    if not row:
        return {"session": None}
    row = dict(row)
    row["error_message"] = _scrub_error_message(row.get("error_message"))
    if row.get("started_at"):
        row["started_at"] = row["started_at"].isoformat()
    if row.get("finished_at"):
        row["finished_at"] = row["finished_at"].isoformat()
    return {"session": row}


@router.get("/api/fb-groups")
async def list_fb_groups():
    """Return all FB groups ordered by name. Unauthed."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT group_id, name, url, is_active FROM fb_groups ORDER BY name ASC"
            )
            rows = await cur.fetchall()
    return {"groups": [dict(r) for r in rows]}


@router.get("/api/fb-groups/active")
async def list_active_fb_groups():
    """Return FB groups that are active AND referenced by an active facebook-source preset. Unauthed."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            # MVP: only presets with source='facebook' exactly drive FB scraping.
            # Multi-source presets (yad2_facebook, all) are not yet wired through scanner.py routing.
            await cur.execute(
                """
                SELECT DISTINCT fg.group_id, fg.name, fg.url
                FROM fb_groups fg
                JOIN search_presets sp
                  ON sp.is_active = TRUE
                 AND sp.extra_params->>'source' = 'facebook'
                 AND fg.group_id = ANY(
                       SELECT jsonb_array_elements_text(COALESCE(sp.extra_params->'fb_groups', '[]'::jsonb))
                     )
                WHERE fg.is_active = TRUE
                ORDER BY fg.name ASC
                """
            )
            rows = await cur.fetchall()
    return {"groups": [dict(r) for r in rows]}


@router.post("/api/presets")
async def create_preset(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Name is required")

    city_code = body.get("city_code", "").strip()
    source = body.get("source", "yad2")

    VALID_SOURCES = {"yad2", "madlan", "facebook", "yad2_madlan", "yad2_facebook", "madlan_facebook", "all"}
    if source not in VALID_SOURCES:
        raise HTTPException(400, f"Invalid source '{source}'. Valid values: {sorted(VALID_SOURCES)}")

    extra_params: dict = {}
    if source != "yad2":
        extra_params["source"] = source
    if source in MADLAN_SOURCES:
        extra_params["madlan_city"] = body.get("madlan_city") or city_code

    # Advanced filter params stored in extra_params JSONB
    for key in ["min_sqm", "max_sqm", "min_floor", "max_floor", "enter_date",
                "img_only", "parking", "elevator", "air_conditioning", "balcony",
                "pets", "furniture", "mamad", "accessible", "property_condition",
                "fb_groups"]:
        val = body.get(key)
        if val is not None:
            extra_params[key] = val

    extra_params_json = json.dumps(extra_params) if extra_params else None

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO search_presets
                    (name, category, city_code, area_code, neighborhood, property_types,
                     min_price, max_price, min_rooms, max_rooms, extra_params, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    name,
                    body.get("category", "rent"),
                    city_code,
                    body.get("area_code") or None,
                    body.get("neighborhood") or None,
                    body.get("property_types") or None,
                    body.get("min_price"),
                    body.get("max_price"),
                    body.get("min_rooms"),
                    body.get("max_rooms"),
                    extra_params_json,
                    body.get("is_active", True),
                ),
            )
            row = await cur.fetchone()
        await conn.commit()
    return dict(row)


@router.put("/api/presets/{preset_id}")
async def update_preset(preset_id: int, request: Request):
    body = await request.json()

    source = body.get("source", "yad2")
    VALID_SOURCES = {"yad2", "madlan", "facebook", "yad2_madlan", "yad2_facebook", "madlan_facebook", "all"}
    if source not in VALID_SOURCES:
        raise HTTPException(400, f"Invalid source '{source}'. Valid values: {sorted(VALID_SOURCES)}")

    # Read existing extra_params from DB to preserve custom seeder keys
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT extra_params FROM search_presets WHERE id = %s", (preset_id,))
            existing_row = await cur.fetchone()
    if not existing_row:
        raise HTTPException(404, "Preset not found")
    existing_extra = existing_row["extra_params"] or {}
    if isinstance(existing_extra, str):
        existing_extra = json.loads(existing_extra)

    # Start from existing extra_params to preserve custom seeder keys
    extra_params: dict = dict(existing_extra)

    # Pop all known managed keys (will be re-set from new values)
    for key in ["source", "madlan_city",
                "min_sqm", "max_sqm", "min_floor", "max_floor", "enter_date",
                "img_only", "parking", "elevator", "air_conditioning", "balcony",
                "pets", "furniture", "mamad", "accessible", "property_condition",
                "fb_groups"]:
        extra_params.pop(key, None)

    # Re-apply new source/madlan_city
    if source != "yad2":
        extra_params["source"] = source
    city_code_for_madlan = body.get("city_code") or ""
    if source in MADLAN_SOURCES:
        extra_params["madlan_city"] = body.get("madlan_city") or city_code_for_madlan

    # Advanced filter params stored in extra_params JSONB
    for key in ["min_sqm", "max_sqm", "min_floor", "max_floor", "enter_date",
                "img_only", "parking", "elevator", "air_conditioning", "balcony",
                "pets", "furniture", "mamad", "accessible", "property_condition",
                "fb_groups"]:
        val = body.get(key)
        if val is not None:
            extra_params[key] = val

    extra_params_json = json.dumps(extra_params) if extra_params else None

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE search_presets SET
                    name = COALESCE(%s, name),
                    category = COALESCE(%s, category),
                    city_code = COALESCE(%s, city_code),
                    area_code = COALESCE(%s, area_code),
                    neighborhood = COALESCE(%s, neighborhood),
                    property_types = COALESCE(%s, property_types),
                    min_price = %s,
                    max_price = %s,
                    min_rooms = %s,
                    max_rooms = %s,
                    extra_params = %s,
                    is_active = COALESCE(%s, is_active),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (
                    body.get("name"),
                    body.get("category"),
                    body.get("city_code"),
                    body.get("area_code") or None,
                    body.get("neighborhood") or None,
                    body.get("property_types") or None,
                    body.get("min_price"),
                    body.get("max_price"),
                    body.get("min_rooms"),
                    body.get("max_rooms"),
                    extra_params_json,
                    body.get("is_active"),
                    preset_id,
                ),
            )
            row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Preset not found")
        await conn.commit()
    return dict(row)


@router.delete("/api/presets/{preset_id}")
async def delete_preset(preset_id: int):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            # Check preset exists
            await cur.execute("SELECT id FROM search_presets WHERE id = %s", (preset_id,))
            preset = await cur.fetchone()
            if not preset:
                raise HTTPException(404, "Preset not found")

            # Get session IDs for this preset
            await cur.execute("SELECT id FROM scan_sessions WHERE preset_id = %s", (preset_id,))
            session_rows = await cur.fetchall()
            session_ids = [r["id"] for r in session_rows]

            if session_ids:
                await cur.execute(
                    "DELETE FROM scan_preset_stats WHERE preset_id = %s", (preset_id,))
                await cur.execute(
                    "DELETE FROM property_events WHERE session_id = ANY(%s)", (session_ids,))
                await cur.execute(
                    "DELETE FROM property_snapshots WHERE session_id = ANY(%s)", (session_ids,))
                await cur.execute(
                    "DELETE FROM scan_sessions WHERE preset_id = %s", (preset_id,))

            # Disconnect properties (keep them — they may be favorited)
            await cur.execute(
                "UPDATE properties SET preset_id = NULL WHERE preset_id = %s", (preset_id,))

            # Delete the preset itself
            await cur.execute("DELETE FROM search_presets WHERE id = %s", (preset_id,))
        await conn.commit()
    return {"deleted": True}


@router.patch("/api/presets/{preset_id}/toggle")
async def toggle_preset(preset_id: int):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE search_presets SET is_active = NOT is_active, updated_at = NOW()
                WHERE id = %s RETURNING id, is_active
                """,
                (preset_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(404, "Preset not found")
        await conn.commit()
    return dict(row)


@router.post("/api/presets/{preset_id}/clone")
async def clone_preset(preset_id: int):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM search_presets WHERE id = %s", (preset_id,))
            original = await cur.fetchone()
            if not original:
                raise HTTPException(status_code=404, detail="Preset not found")
            extra_params_json = json.dumps(original['extra_params']) if original['extra_params'] else None
            await cur.execute(
                """INSERT INTO search_presets
                   (name, category, city_code, area_code, neighborhood, property_types,
                    min_price, max_price, min_rooms, max_rooms, extra_params, is_active)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING *""",
                (f"{original['name']} (copy)", original['category'], original['city_code'],
                 original['area_code'], original['neighborhood'], original['property_types'],
                 original['min_price'], original['max_price'], original['min_rooms'],
                 original['max_rooms'],
                 extra_params_json,
                 True)
            )
            row = await cur.fetchone()
        await conn.commit()
    return dict(row)


# ---------------------------------------------------------------------------
# Amit Fit
# ---------------------------------------------------------------------------

@router.get("/api/amit-fit/properties")
async def get_amit_fit_properties(
    page: int = Query(default=1),
    per_page: int = Query(default=500),
):
    """Return all active properties that have buyer_fit_tags, sorted by amit_pct_vs_preferred ASC."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            # Get all active preset IDs (all sources, including FB)
            await cur.execute("SELECT id FROM search_presets WHERE is_active = TRUE")
            preset_ids = [r["id"] for r in await cur.fetchall()]

            if not preset_ids:
                return {"total": 0, "page": page, "per_page": per_page, "properties": []}

            # Count total
            await cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM properties p
                LEFT JOIN property_classifications pc ON pc.property_id = p.id
                LEFT JOIN blacklist bl ON bl.property_id = p.id
                WHERE (p.preset_id = ANY(%s) OR p.preset_id IS NULL)
                  AND p.is_active = TRUE
                  AND bl.id IS NULL
                  AND jsonb_array_length(COALESCE(pc.signal_details->'buyer_fit_tags', '[]'::jsonb)) > 0
                """,
                (preset_ids,),
            )
            total_row = await cur.fetchone()
            total = total_row["total"] if total_row else 0

            offset = (page - 1) * per_page
            await cur.execute(
                """
                SELECT p.*, pc.signal_details,
                    (
                        SELECT ARRAY_AGG(DISTINCT p2.source)
                        FROM property_matches pm
                        JOIN properties p2 ON p2.id = CASE
                            WHEN pm.property_id_a = p.id THEN pm.property_id_b
                            ELSE pm.property_id_a END
                        WHERE pm.property_id_a = p.id OR pm.property_id_b = p.id
                    ) AS matched_sources
                FROM properties p
                LEFT JOIN property_classifications pc ON pc.property_id = p.id
                LEFT JOIN blacklist bl ON bl.property_id = p.id
                WHERE (p.preset_id = ANY(%s) OR p.preset_id IS NULL)
                  AND p.is_active = TRUE
                  AND bl.id IS NULL
                  AND jsonb_array_length(COALESCE(pc.signal_details->'buyer_fit_tags', '[]'::jsonb)) > 0
                ORDER BY (pc.signal_details->>'amit_pct_vs_preferred')::float ASC NULLS LAST,
                         p.updated_at DESC
                LIMIT %s OFFSET %s
                """,
                (preset_ids, per_page, offset),
            )
            rows = await cur.fetchall()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "properties": [dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

@router.post("/api/scan/all")
async def trigger_all_scans():
    try:
        results = await run_all_scans()
    except Exception as exc:
        logger.error("api.scan_all_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    return {"scans": results}


@router.post("/api/scan/scheduled")
async def trigger_scheduled_scan(request: Request, background_tasks: BackgroundTasks):
    """Endpoint for external cron service. Requires CRON_SECRET auth."""
    from pdis.config import settings

    # Check auth
    auth_header = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.cron_secret}"
    if not settings.cron_secret or auth_header != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing cron secret")

    # Check if scan already running
    from pdis.scanner import get_scan_status, scheduled_scan
    status = get_scan_status()
    if status["running"]:
        raise HTTPException(status_code=409, detail="Scan already in progress")

    # Fire and forget
    background_tasks.add_task(scheduled_scan)
    return {"status": "started", "message": "Scan triggered in background"}


@router.get("/api/scan/status")
async def scan_status():
    """Check if a scan is currently running."""
    from pdis.scanner import get_scan_status
    return get_scan_status()


class OpenSearchBody(BaseModel):
    city_code: str = "5000"
    min_price: int | None = None
    max_price: int | None = None
    min_rooms: float | None = None
    max_rooms: float | None = None
    category: str = "rent"


@router.post("/api/scan/open")
async def trigger_open_scan(body: OpenSearchBody):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO search_presets
                   (name, category, city_code, min_price, max_price, min_rooms, max_rooms, is_active)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE)
                   RETURNING id""",
                (
                    f"Open search {datetime.now().strftime('%d.%m %H:%M')}",
                    body.category,
                    body.city_code,
                    body.min_price,
                    body.max_price,
                    body.min_rooms,
                    body.max_rooms,
                ),
            )
            row = await cur.fetchone()
        await conn.commit()

    preset_id = row["id"]

    try:
        result = await run_scan(preset_id)
    except Exception as exc:
        logger.error("api.open_scan_error", preset_id=preset_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

    return result


async def _run_scan_background(preset_id: int) -> None:
    """Background wrapper for per-preset scan — uses the same lock as scheduled scans."""
    import time as _time
    import pdis.scanner as _scanner
    global_running = _scanner.get_scan_status()
    if global_running["running"]:
        logger.warning("api.scan_skipped_already_running", preset_id=preset_id)
        return
    _scanner._scan_running = True
    _scanner._scan_started_at = _time.time()
    try:
        await run_scan(preset_id)
    except Exception as exc:
        logger.error("api.scan_background_error", preset_id=preset_id, error=str(exc))
    finally:
        _scanner._scan_running = False
        _scanner._scan_started_at = None
        _scanner._scan_progress = None  # safety net — normally reset by _finish_session


@router.post("/api/scan/{preset_id}")
async def trigger_scan(preset_id: int, background_tasks: BackgroundTasks):
    from pdis.scanner import get_scan_status
    status = get_scan_status()
    if status["running"]:
        raise HTTPException(status_code=409, detail="Scan already in progress")
    background_tasks.add_task(_run_scan_background, preset_id)
    return {"status": "started", "preset_id": preset_id}


@router.get("/api/scan/sessions")
async def list_sessions():
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT ss.*, sp.name AS preset_name
                FROM scan_sessions ss
                JOIN search_presets sp ON sp.id = ss.preset_id
                ORDER BY ss.started_at DESC
                LIMIT 20
                """
            )
            rows = await cur.fetchall()
    return {"sessions": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

@router.get("/api/properties")
async def list_properties(
    preset_id: int | None = Query(default=None),
    min_price: int | None = Query(default=None),
    max_price: int | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    min_days_on_market: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=1000),
):
    conditions = []
    params: list = []

    if preset_id is not None:
        conditions.append("preset_id = %s")
        params.append(preset_id)
    if min_price is not None:
        conditions.append("price >= %s")
        params.append(min_price)
    if max_price is not None:
        conditions.append("price <= %s")
        params.append(max_price)
    if is_active is not None:
        conditions.append("is_active = %s")
        params.append(is_active)
    if min_days_on_market is not None:
        conditions.append("days_on_market >= %s")
        params.append(min_days_on_market)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    offset = (page - 1) * per_page

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT COUNT(*) AS total FROM properties {where}",
                params,
            )
            count_row = await cur.fetchone()
            total = count_row["total"] if count_row else 0

            await cur.execute(
                f"""
                SELECT * FROM properties {where}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                params + [per_page, offset],
            )
            rows = await cur.fetchall()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "properties": [dict(r) for r in rows],
    }


@router.get("/api/properties/search")
async def search_properties(q: str = "", category: str | None = Query(default=None)):
    if not q or len(q) < 2:
        return {"properties": []}

    search_term = f"%{q}%"
    category_clause = ""
    params_list: list = [search_term, search_term, search_term, search_term, search_term, search_term]
    if category:
        category_clause = "AND p.category = %s"
        params_list.append(category)

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT p.*,
                       pc.signal_details
                FROM properties p
                LEFT JOIN property_classifications pc ON pc.property_id = p.id
                WHERE (
                    p.address_street ILIKE %s
                   OR p.address_home_number ILIKE %s
                   OR p.neighborhood ILIKE %s
                   OR p.address_city ILIKE %s
                   OR p.description ILIKE %s
                   OR CONCAT(p.address_street, ' ', p.address_home_number) ILIKE %s
                )
                {category_clause}
                ORDER BY p.updated_at DESC
                LIMIT 100
                """,
                tuple(params_list),
            )
            rows = await cur.fetchall()

    return {"properties": [dict(r) for r in rows]}


@router.get("/api/properties/{yad2_id}")
async def get_property(yad2_id: str):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM properties WHERE yad2_id = %s",
                (yad2_id,),
            )
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")

            await cur.execute(
                """
                SELECT ps.*, ss.started_at AS session_started_at
                FROM property_snapshots ps
                JOIN scan_sessions ss ON ss.id = ps.session_id
                WHERE ps.property_id = %s
                ORDER BY ps.captured_at DESC
                """,
                (prop["id"],),
            )
            snapshots = await cur.fetchall()

            await cur.execute(
                """
                SELECT signal_details, updated_at
                FROM property_classifications
                WHERE property_id = %s
                """,
                (prop["id"],),
            )
            classification_row = await cur.fetchone()

            # Operator notes
            await cur.execute(
                """
                SELECT id, property_id, note, created_by, created_at
                FROM operator_notes
                WHERE property_id = %s
                ORDER BY created_at DESC
                """,
                (prop["id"],),
            )
            notes_rows = await cur.fetchall()

            # Property matches
            property_id = prop["id"]
            await cur.execute(
                """
                SELECT
                    pm.id, pm.match_tier, pm.match_reason, pm.confidence, pm.is_confirmed,
                    CASE WHEN pm.property_id_a = %s THEN pm.property_id_b
                         ELSE pm.property_id_a END AS matched_id
                FROM property_matches pm
                WHERE pm.property_id_a = %s OR pm.property_id_b = %s
                ORDER BY pm.created_at DESC
                """,
                (property_id, property_id, property_id),
            )
            match_rows = await cur.fetchall()

            matches = []
            for mrow in match_rows:
                matched_id = mrow["matched_id"]
                await cur.execute(
                    "SELECT yad2_id, address_street, price, rooms FROM properties WHERE id = %s",
                    (matched_id,),
                )
                matched_prop = await cur.fetchone()
                matches.append({
                    "id": mrow["id"],
                    "match_tier": mrow["match_tier"],
                    "match_reason": mrow["match_reason"],
                    "confidence": mrow["confidence"],
                    "is_confirmed": mrow["is_confirmed"],
                    "matched_property": dict(matched_prop) if matched_prop else None,
                })

            await cur.execute("SELECT 1 FROM whitelist WHERE property_id = %s", (prop["id"],))
            is_whitelisted = await cur.fetchone() is not None
            await cur.execute("SELECT 1 FROM blacklist WHERE property_id = %s", (prop["id"],))
            is_blacklisted = await cur.fetchone() is not None
            await cur.execute("SELECT 1 FROM favorites WHERE property_id = %s", (prop["id"],))
            is_favorited = await cur.fetchone() is not None

    result = dict(prop)
    result["snapshots"] = [dict(s) for s in snapshots]
    result["classification"] = dict(classification_row) if classification_row else None
    result["notes"] = [dict(n) for n in notes_rows]
    result["matches"] = matches
    result["is_whitelisted"] = is_whitelisted
    result["is_blacklisted"] = is_blacklisted
    result["is_favorited"] = is_favorited
    return result


@router.get("/api/properties/{yad2_id}/snapshots")
async def get_property_snapshots(yad2_id: str):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM properties WHERE yad2_id = %s",
                (yad2_id,),
            )
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")

            await cur.execute(
                """
                SELECT ps.*, ss.started_at AS session_started_at
                FROM property_snapshots ps
                JOIN scan_sessions ss ON ss.id = ps.session_id
                WHERE ps.property_id = %s
                ORDER BY ps.captured_at DESC
                """,
                (prop["id"],),
            )
            rows = await cur.fetchall()

    return {"snapshots": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@router.get("/api/events/recent")
async def list_recent_events(category: str | None = Query(default=None)):
    category_clause = ""
    params_list: list = []
    if category:
        category_clause = "AND p.category = %s"
        params_list.append(category)

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT pe.*, p.yad2_id, p.address_street, p.address_city
                FROM property_events pe
                JOIN properties p ON p.id = pe.property_id
                WHERE TRUE
                {category_clause}
                ORDER BY pe.created_at DESC
                LIMIT 50
                """,
                tuple(params_list),
            )
            rows = await cur.fetchall()
    return {"events": [dict(r) for r in rows]}


# IMPORTANT: /api/events/properties must be registered BEFORE /api/events to avoid path conflicts
@router.get("/api/events/properties")
async def get_event_properties(
    event_type: str = Query(...),
    category: str | None = Query(default=None),
):
    """Return full property data for properties that have events of a given type."""
    category_clause = ""
    params_list: list = [event_type]
    if category:
        category_clause = "AND p.category = %s"
        params_list.append(category)

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT DISTINCT ON (p.id)
                    pc.signal_details, p.*,
                    (SELECT ARRAY_AGG(DISTINCT p2.source)
                     FROM property_matches pm
                     JOIN properties p2 ON p2.id = CASE
                         WHEN pm.property_id_a = p.id THEN pm.property_id_b
                         ELSE pm.property_id_a END
                     WHERE pm.property_id_a = p.id OR pm.property_id_b = p.id
                    ) AS matched_sources
                FROM properties p
                JOIN property_events pe ON pe.property_id = p.id
                LEFT JOIN property_classifications pc ON pc.property_id = p.id
                WHERE pe.event_type = %s
                  AND p.is_active = TRUE
                {category_clause}
                ORDER BY p.id
                """,
                tuple(params_list),
            )
            rows = await cur.fetchall()

    return {"properties": [dict(r) for r in rows]}


@router.get("/api/events")
async def list_events(
    property_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=1000),
):
    conditions = []
    params: list = []

    if property_id is not None:
        conditions.append("pe.property_id = %s")
        params.append(property_id)
    if event_type is not None:
        conditions.append("pe.event_type = %s")
        params.append(event_type)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    offset = (page - 1) * per_page

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT COUNT(*) AS total FROM property_events pe {where}",
                params,
            )
            count_row = await cur.fetchone()
            total = count_row["total"] if count_row else 0

            await cur.execute(
                f"""
                SELECT pe.*, p.yad2_id, p.address_street, p.address_city
                FROM property_events pe
                JOIN properties p ON p.id = pe.property_id
                {where}
                ORDER BY pe.created_at DESC
                LIMIT %s OFFSET %s
                """,
                params + [per_page, offset],
            )
            rows = await cur.fetchall()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "events": [dict(r) for r in rows],
    }


@router.get("/api/properties/{yad2_id}/events")
async def get_property_events(yad2_id: str):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM properties WHERE yad2_id = %s",
                (yad2_id,),
            )
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")

            await cur.execute(
                """
                SELECT * FROM property_events
                WHERE property_id = %s
                ORDER BY created_at DESC
                """,
                (prop["id"],),
            )
            rows = await cur.fetchall()

    return {"events": [dict(r) for r in rows]}


@router.get("/api/properties/{yad2_id}/notes")
async def get_property_notes(yad2_id: str):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM properties WHERE yad2_id = %s",
                (yad2_id,),
            )
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")

            await cur.execute(
                """
                SELECT id, property_id, note, created_by, created_at
                FROM operator_notes
                WHERE property_id = %s
                ORDER BY created_at DESC
                """,
                (prop["id"],),
            )
            rows = await cur.fetchall()
    return {"notes": [dict(r) for r in rows]}


class NoteBody(BaseModel):
    note: str
    created_by: Optional[str] = "operator"


@router.post("/api/properties/{yad2_id}/notes")
async def add_property_note(yad2_id: str, body: NoteBody):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM properties WHERE yad2_id = %s",
                (yad2_id,),
            )
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")

            await cur.execute(
                """
                INSERT INTO operator_notes (property_id, note, created_by)
                VALUES (%s, %s, %s)
                RETURNING id, property_id, note, created_by, created_at
                """,
                (prop["id"], body.note, body.created_by or "operator"),
            )
            row = await cur.fetchone()
        await conn.commit()
    return dict(row)


@router.delete("/api/notes/{note_id}")
async def delete_note(note_id: int):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM operator_notes WHERE id = %s",
                (note_id,),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Note not found")
        await conn.commit()
    return {"status": "deleted"}


@router.get("/api/properties/{yad2_id}/matches")
async def get_property_matches(yad2_id: str):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM properties WHERE yad2_id = %s",
                (yad2_id,),
            )
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")

            property_id = prop["id"]

            await cur.execute(
                """
                SELECT
                    pm.id, pm.match_tier, pm.match_reason, pm.confidence, pm.is_confirmed,
                    CASE WHEN pm.property_id_a = %s THEN pm.property_id_b
                         ELSE pm.property_id_a END AS matched_id
                FROM property_matches pm
                WHERE pm.property_id_a = %s OR pm.property_id_b = %s
                ORDER BY pm.created_at DESC
                """,
                (property_id, property_id, property_id),
            )
            match_rows = await cur.fetchall()

            matches = []
            for row in match_rows:
                matched_id = row["matched_id"]
                await cur.execute(
                    "SELECT yad2_id, address_street, price, rooms FROM properties WHERE id = %s",
                    (matched_id,),
                )
                matched_prop = await cur.fetchone()
                matches.append({
                    "id": row["id"],
                    "match_tier": row["match_tier"],
                    "match_reason": row["match_reason"],
                    "confidence": row["confidence"],
                    "is_confirmed": row["is_confirmed"],
                    "matched_property": dict(matched_prop) if matched_prop else None,
                })

    return {"matches": matches}


@router.post("/api/matches/{match_id}/confirm")
async def confirm_match(match_id: int):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE property_matches SET is_confirmed = TRUE WHERE id = %s",
                (match_id,),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Match not found")
        await conn.commit()
    return {"status": "confirmed"}


@router.post("/api/matches/{match_id}/reject")
async def reject_match(match_id: int):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE property_matches SET is_confirmed = FALSE WHERE id = %s",
                (match_id,),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Match not found")
        await conn.commit()
    return {"status": "rejected"}


@router.get("/api/matches/pending")
async def get_pending_matches():
    """List all Tier 3 matches awaiting operator review (is_confirmed IS NULL)."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    pm.id, pm.match_tier, pm.match_reason, pm.confidence, pm.created_at,
                    pa.yad2_id AS yad2_id_a, pa.address_street AS address_a,
                    pa.price AS price_a, pa.rooms AS rooms_a,
                    pb.yad2_id AS yad2_id_b, pb.address_street AS address_b,
                    pb.price AS price_b, pb.rooms AS rooms_b
                FROM property_matches pm
                JOIN properties pa ON pa.id = pm.property_id_a
                JOIN properties pb ON pb.id = pm.property_id_b
                WHERE pm.is_confirmed IS NULL
                ORDER BY pm.created_at DESC
                """
            )
            rows = await cur.fetchall()

    matches = []
    for row in rows:
        row = dict(row)
        matches.append({
            "id": row["id"],
            "match_tier": row["match_tier"],
            "match_reason": row["match_reason"],
            "confidence": row["confidence"],
            "created_at": row["created_at"],
            "property_a": {
                "yad2_id": row["yad2_id_a"],
                "address_street": row["address_a"],
                "price": row["price_a"],
                "rooms": row["rooms_a"],
            },
            "property_b": {
                "yad2_id": row["yad2_id_b"],
                "address_street": row["address_b"],
                "price": row["price_b"],
                "rooms": row["rooms_b"],
            },
        })

    return {"total": len(matches), "matches": matches}


@router.get("/api/properties/{yad2_id}/signals")
async def get_property_signals(yad2_id: str):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM properties WHERE yad2_id = %s",
                (yad2_id,),
            )
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")

    property_id = prop["id"]
    signals = await compute_signals_batch([property_id])
    sig = signals.get(property_id, {"details": {}})
    return {
        "property_id": property_id,
        "details": sig["details"],
    }


@router.get("/api/properties/{yad2_id}/comps")
async def get_comps(yad2_id: str):
    from pdis.comps import compute_building_comps
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM properties WHERE yad2_id = %s", (yad2_id,))
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Property not found")
            pid = row["id"]
    return await compute_building_comps(pid, lookback_months=24)


# ---------------------------------------------------------------------------
# Whitelist / Blacklist
# IMPORTANT: /api/whitelist/ids and /api/blacklist/ids must be registered
# BEFORE /api/whitelist/{yad2_id} and /api/blacklist/{yad2_id}
# ---------------------------------------------------------------------------

@router.get("/api/whitelist/ids")
async def get_whitelist_ids():
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT p.yad2_id FROM whitelist w JOIN properties p ON w.property_id = p.id"
            )
            rows = await cur.fetchall()
    return {"ids": [r["yad2_id"] for r in rows]}


@router.get("/api/blacklist/ids")
async def get_blacklist_ids():
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT p.yad2_id FROM blacklist b JOIN properties p ON b.property_id = p.id"
            )
            rows = await cur.fetchall()
    return {"ids": [r["yad2_id"] for r in rows]}


@router.get("/api/whitelist")
async def list_whitelist():
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT p.*, pc.signal_details,
                       (SELECT ARRAY_AGG(DISTINCT p2.source)
                        FROM property_matches pm
                        JOIN properties p2 ON p2.id = CASE
                            WHEN pm.property_id_a = p.id THEN pm.property_id_b
                            ELSE pm.property_id_a END
                        WHERE pm.property_id_a = p.id OR pm.property_id_b = p.id
                       ) AS matched_sources
                FROM whitelist w
                JOIN properties p ON p.id = w.property_id
                LEFT JOIN property_classifications pc ON pc.property_id = p.id
                ORDER BY w.created_at DESC
            """)
            rows = await cur.fetchall()
    return {"total": len(rows), "properties": [dict(r) for r in rows]}


@router.get("/api/blacklist")
async def list_blacklist():
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT p.*, pc.signal_details,
                       (SELECT ARRAY_AGG(DISTINCT p2.source)
                        FROM property_matches pm
                        JOIN properties p2 ON p2.id = CASE
                            WHEN pm.property_id_a = p.id THEN pm.property_id_b
                            ELSE pm.property_id_a END
                        WHERE pm.property_id_a = p.id OR pm.property_id_b = p.id
                       ) AS matched_sources
                FROM blacklist b
                JOIN properties p ON p.id = b.property_id
                LEFT JOIN property_classifications pc ON pc.property_id = p.id
                ORDER BY b.created_at DESC
            """)
            rows = await cur.fetchall()
    return {"total": len(rows), "properties": [dict(r) for r in rows]}


class ListReason(BaseModel):
    reason: str | None = None


@router.post("/api/whitelist/{yad2_id}")
async def add_to_whitelist(yad2_id: str, body: ListReason = ListReason()):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM properties WHERE yad2_id = %s",
                (yad2_id,),
            )
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")

            property_id = prop["id"]

            await cur.execute(
                """INSERT INTO whitelist (property_id, reason)
                   VALUES (%s, %s)
                   ON CONFLICT (property_id) DO UPDATE SET reason = EXCLUDED.reason""",
                (property_id, body.reason),
            )
        await conn.commit()

    return {"status": "added", "property_id": property_id}


@router.delete("/api/whitelist/{yad2_id}")
async def remove_from_whitelist(yad2_id: str):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM properties WHERE yad2_id = %s",
                (yad2_id,),
            )
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")

            property_id = prop["id"]

            await cur.execute(
                "DELETE FROM whitelist WHERE property_id = %s",
                (property_id,),
            )
        await conn.commit()

    return {"status": "removed"}


@router.post("/api/blacklist/{yad2_id}")
async def add_to_blacklist(yad2_id: str, body: ListReason = ListReason()):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM properties WHERE yad2_id = %s",
                (yad2_id,),
            )
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")

            property_id = prop["id"]

            await cur.execute(
                """INSERT INTO blacklist (property_id, reason)
                   VALUES (%s, %s)
                   ON CONFLICT (property_id) DO UPDATE SET reason = EXCLUDED.reason""",
                (property_id, body.reason),
            )
        await conn.commit()

    return {"status": "added", "property_id": property_id}


@router.delete("/api/blacklist/{yad2_id}")
async def remove_from_blacklist(yad2_id: str):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM properties WHERE yad2_id = %s",
                (yad2_id,),
            )
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")

            property_id = prop["id"]

            await cur.execute(
                "DELETE FROM blacklist WHERE property_id = %s",
                (property_id,),
            )
        await conn.commit()

    return {"status": "removed"}


# ---------------------------------------------------------------------------
# Favorites
# IMPORTANT: /api/favorites/ids must be registered BEFORE /api/favorites/{yad2_id}
# ---------------------------------------------------------------------------

@router.get("/api/favorites/ids")
async def list_favorite_ids():
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT p.yad2_id FROM favorites f
                JOIN properties p ON p.id = f.property_id
            """)
            rows = await cur.fetchall()
    return {"ids": [r["yad2_id"] for r in rows]}


@router.get("/api/favorites")
async def list_favorites():
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT p.*, pc.signal_details,
                       p.source,
                       (SELECT ARRAY_AGG(DISTINCT p2.source)
                        FROM property_matches pm
                        JOIN properties p2 ON p2.id = CASE
                            WHEN pm.property_id_a = p.id THEN pm.property_id_b
                            ELSE pm.property_id_a END
                        WHERE pm.property_id_a = p.id OR pm.property_id_b = p.id
                       ) AS matched_sources
                FROM favorites f
                JOIN properties p ON p.id = f.property_id
                LEFT JOIN property_classifications pc ON pc.property_id = p.id
                ORDER BY f.created_at DESC
            """)
            rows = await cur.fetchall()
    return {"total": len(rows), "favorites": [dict(r) for r in rows]}


@router.post("/api/favorites/{yad2_id}")
async def add_favorite(yad2_id: str):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM properties WHERE yad2_id = %s", (yad2_id,))
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")
            await cur.execute(
                "INSERT INTO favorites (property_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (prop["id"],),
            )
        await conn.commit()
    return {"status": "added", "property_id": prop["id"]}


@router.delete("/api/favorites/{yad2_id}")
async def remove_favorite(yad2_id: str):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM properties WHERE yad2_id = %s", (yad2_id,))
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")
            await cur.execute("DELETE FROM favorites WHERE property_id = %s", (prop["id"],))
        await conn.commit()
    return {"status": "removed"}


# ---------------------------------------------------------------------------
# Session changes
# ---------------------------------------------------------------------------

@router.get("/api/scan/sessions/{session_id}/changes")
async def get_session_changes(session_id: int):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT pe.*, p.yad2_id
                FROM property_events pe
                JOIN properties p ON p.id = pe.property_id
                WHERE pe.session_id = %s
                ORDER BY pe.created_at
                """,
                (session_id,),
            )
            rows = await cur.fetchall()

    events = [dict(r) for r in rows]
    summary = {
        "new_listings": 0,
        "price_drops": 0,
        "price_increases": 0,
        "removals": 0,
        "relistings": 0,
        "description_changes": 0,
        "image_changes": 0,
    }
    key_map = {
        "new_listing": "new_listings",
        "price_drop": "price_drops",
        "price_increase": "price_increases",
        "removal": "removals",
        "relisting": "relistings",
        "description_change": "description_changes",
        "image_change": "image_changes",
    }
    for ev in events:
        k = key_map.get(ev["event_type"])
        if k:
            summary[k] += 1

    return {
        "session_id": session_id,
        "events": events,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Operator Input
# ---------------------------------------------------------------------------

class OperatorInputBody(BaseModel):
    agent_name: str | None = None
    manual_days_on_market: int | None = None
    flexibility: str | None = None
    condition: str | None = None


@router.get("/api/properties/{yad2_id}/operator-input")
async def get_operator_input(yad2_id: str):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM properties WHERE yad2_id = %s",
                (yad2_id,),
            )
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")

            await cur.execute(
                """
                SELECT agent_name, manual_days_on_market, flexibility, condition, updated_at
                FROM property_operator_input
                WHERE property_id = %s
                """,
                (prop["id"],),
            )
            row = await cur.fetchone()

    if row:
        return dict(row)
    return {
        "agent_name": None,
        "manual_days_on_market": None,
        "flexibility": None,
        "condition": None,
        "updated_at": None,
    }


@router.put("/api/properties/{yad2_id}/operator-input")
async def upsert_operator_input(yad2_id: str, body: OperatorInputBody):
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM properties WHERE yad2_id = %s",
                (yad2_id,),
            )
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")

            await cur.execute(
                """
                INSERT INTO property_operator_input
                    (property_id, agent_name, manual_days_on_market, flexibility, condition, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (property_id) DO UPDATE SET
                    agent_name = EXCLUDED.agent_name,
                    manual_days_on_market = EXCLUDED.manual_days_on_market,
                    flexibility = EXCLUDED.flexibility,
                    condition = EXCLUDED.condition,
                    updated_at = NOW()
                RETURNING agent_name, manual_days_on_market, flexibility, condition, updated_at
                """,
                (
                    prop["id"],
                    body.agent_name,
                    body.manual_days_on_market,
                    body.flexibility,
                    body.condition,
                ),
            )
            row = await cur.fetchone()
        await conn.commit()
    return dict(row)


# ---------------------------------------------------------------------------
# Neighborhood Thresholds (Amit Fit)
# ---------------------------------------------------------------------------

async def _recompute_amit_fit_for_scope(
    scopes: list[tuple[int | None, str | None, str]],
) -> tuple[int | None, str | None]:
    """Best-effort Amit Fit recompute for properties matching (hood_id, neighborhood, category) scopes.
    Returns (count, warning). On success: (N, None). On failure: (None, error_string)."""
    unique_scopes = list({
        (hood_id, (name or "").strip() or None, cat)
        for hood_id, name, cat in scopes
    })
    if not unique_scopes:
        return 0, None

    or_clauses = []
    params: list = []
    for hood_id, name, cat in unique_scopes:
        if hood_id is not None:
            or_clauses.append("(hood_id = %s AND category = %s)")
            params.extend([hood_id, cat])
        if name:
            or_clauses.append("(TRIM(neighborhood) = %s AND category = %s)")
            params.extend([name, cat])

    if not or_clauses:
        return 0, None

    sql = (
        "SELECT id FROM properties WHERE is_active = TRUE AND ("
        + " OR ".join(or_clauses)
        + ")"
    )

    try:
        async with _db.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, params)
                rows = await cur.fetchall()

        property_ids = [r["id"] for r in rows]
        if not property_ids:
            logger.info("amit_fit.recompute.empty_scope", scopes=unique_scopes)
            return 0, None

        from pdis.scanner import get_scan_status
        if get_scan_status().get("running"):
            logger.info(
                "amit_fit.recompute.scan_in_progress",
                count=len(property_ids),
                note="idempotent — proceeding anyway",
            )

        from pdis.classification import persist_signals_batch
        await persist_signals_batch(property_ids)
        logger.info("amit_fit.recompute.done", count=len(property_ids), scopes=unique_scopes)
        return len(property_ids), None

    except Exception as exc:
        logger.warning("amit_fit.recompute_failed", error=str(exc), scopes=unique_scopes)
        return None, str(exc)


@router.get("/api/thresholds")
async def list_thresholds(neighborhood: str | None = None, category: str = "forsale"):
    async with _db.pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            if neighborhood:
                await cur.execute(
                    """SELECT * FROM neighborhood_thresholds
                       WHERE neighborhood = %s AND category = %s
                       ORDER BY size_min""",
                    (neighborhood, category),
                )
            else:
                await cur.execute(
                    "SELECT * FROM neighborhood_thresholds WHERE category = %s ORDER BY neighborhood, size_min",
                    (category,),
                )
            rows = await cur.fetchall()
    return {"thresholds": rows}


@router.put("/api/thresholds")
async def upsert_thresholds(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be a JSON object with a thresholds array")
    rows_in = body.get("thresholds", [])
    if not isinstance(rows_in, list) or not rows_in:
        raise HTTPException(400, "thresholds must be a non-empty array")

    for t in rows_in:
        neighborhood = (t.get("neighborhood") or "").strip()
        category = t.get("category", "forsale")
        size_min = t.get("size_min")
        size_max = t.get("size_max")
        pref = t.get("target_price_per_sqm_preferred")
        mx = t.get("target_price_per_sqm_max")
        if not neighborhood:
            raise HTTPException(400, "neighborhood is required")
        if category not in ("forsale", "rent"):
            raise HTTPException(400, f"invalid category: {category}")
        if not isinstance(size_min, int) or not isinstance(size_max, int) or size_min < 0 or size_max <= size_min:
            raise HTTPException(400, f"invalid size bucket: {size_min}-{size_max}")
        if not isinstance(pref, int) or not isinstance(mx, int) or pref <= 0 or mx < pref:
            raise HTTPException(400, f"invalid targets for bucket {size_min}-{size_max}: pref={pref} max={mx}")

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            for t in rows_in:
                await cur.execute(
                    """INSERT INTO neighborhood_thresholds
                         (neighborhood, hood_id, category, size_min, size_max,
                          target_price_per_sqm_preferred, target_price_per_sqm_max, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                       ON CONFLICT (neighborhood, size_min, size_max, category)
                       DO UPDATE SET
                         hood_id = EXCLUDED.hood_id,
                         target_price_per_sqm_preferred = EXCLUDED.target_price_per_sqm_preferred,
                         target_price_per_sqm_max = EXCLUDED.target_price_per_sqm_max,
                         updated_at = NOW()""",
                    (
                        t["neighborhood"].strip(), t.get("hood_id"), t.get("category", "forsale"),
                        int(t["size_min"]), int(t["size_max"]),
                        int(t["target_price_per_sqm_preferred"]), int(t["target_price_per_sqm_max"]),
                    ),
                )
        await conn.commit()
    scopes = [
        (t.get("hood_id"), t["neighborhood"].strip(), t.get("category", "forsale"))
        for t in rows_in
    ]
    recomputed, warning = await _recompute_amit_fit_for_scope(scopes)
    response = {"ok": True, "count": len(rows_in), "recomputed": recomputed}
    if warning:
        response["recompute_warning"] = warning
    return response


@router.delete("/api/thresholds/{threshold_id}")
async def delete_threshold(threshold_id: int):
    async with _db.pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT hood_id, neighborhood, category FROM neighborhood_thresholds WHERE id = %s",
                (threshold_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(404, "threshold not found")
            await cur.execute("DELETE FROM neighborhood_thresholds WHERE id = %s", (threshold_id,))
        await conn.commit()

    scopes = [(row["hood_id"], row["neighborhood"], row["category"])]
    recomputed, warning = await _recompute_amit_fit_for_scope(scopes)
    response = {"ok": True, "recomputed": recomputed}
    if warning:
        response["recompute_warning"] = warning
    return response


# ---------------------------------------------------------------------------
# Neighborhood feature adjustments (Phase 2B-1)
# ---------------------------------------------------------------------------

_FA_PAIRED = [
    ("year_old_pref_pct", "year_old_max_pct"),
    ("year_mid_old_pref_pct", "year_mid_old_max_pct"),
    ("year_mid_pref_pct", "year_mid_max_pct"),
    ("year_new_pref_pct", "year_new_max_pct"),
    ("parking_bonus_pref", "parking_bonus_max"),
    ("mamad_pct_pref", "mamad_pct_max"),
]
_FA_ALL_COLS = [
    "year_old_pref_pct", "year_old_max_pct",
    "year_mid_old_pref_pct", "year_mid_old_max_pct",
    "year_mid_pref_pct", "year_mid_max_pct",
    "year_new_pref_pct", "year_new_max_pct",
    "walkup_pct_per_floor",
    "parking_bonus_pref", "parking_bonus_max",
    "mamad_pct_pref", "mamad_pct_max",
]


@router.get("/api/feature-adjustments")
async def list_feature_adjustments(neighborhood: str | None = None, category: str = "forsale"):
    async with _db.pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            if neighborhood:
                await cur.execute(
                    """SELECT * FROM neighborhood_feature_adjustments
                       WHERE neighborhood = %s AND category = %s""",
                    (neighborhood, category),
                )
            else:
                await cur.execute(
                    """SELECT * FROM neighborhood_feature_adjustments
                       WHERE category = %s ORDER BY neighborhood""",
                    (category,),
                )
            rows = await cur.fetchall()
    return {"adjustments": rows}


@router.put("/api/feature-adjustments")
async def upsert_feature_adjustments(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be a JSON object")
    rows_in = body.get("adjustments", [])
    if not isinstance(rows_in, list) or not rows_in:
        raise HTTPException(400, "adjustments must be a non-empty array")

    for t in rows_in:
        neighborhood = (t.get("neighborhood") or "").strip()
        if not neighborhood:
            raise HTTPException(400, "neighborhood is required")
        category = t.get("category", "forsale")
        if category not in ("forsale", "rent"):
            raise HTTPException(400, f"invalid category: {category}")
        walkup = t.get("walkup_pct_per_floor")
        if walkup is None or not isinstance(walkup, (int, float)) or walkup < 0 or walkup > 10:
            raise HTTPException(400, f"walkup_pct_per_floor must be 0-10, got {walkup}")
        for k in _FA_ALL_COLS:
            v = t.get(k)
            if v is None or not isinstance(v, (int, float)):
                raise HTTPException(400, f"{k} required and must be numeric")
        for pref_k, max_k in _FA_PAIRED:
            if t[max_k] < t[pref_k]:
                raise HTTPException(400, f"{max_k} ({t[max_k]}) must be >= {pref_k} ({t[pref_k]})")

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            for t in rows_in:
                await cur.execute(
                    f"""INSERT INTO neighborhood_feature_adjustments
                         (neighborhood, hood_id, category, {', '.join(_FA_ALL_COLS)}, updated_at)
                       VALUES (%s, %s, %s, {', '.join(['%s'] * len(_FA_ALL_COLS))}, NOW())
                       ON CONFLICT (neighborhood, category)
                       DO UPDATE SET
                         hood_id = EXCLUDED.hood_id,
                         {', '.join(f'{c} = EXCLUDED.{c}' for c in _FA_ALL_COLS)},
                         updated_at = NOW()""",
                    (
                        t["neighborhood"].strip(),
                        t.get("hood_id"),
                        t.get("category", "forsale"),
                        *[t[c] for c in _FA_ALL_COLS],
                    ),
                )
        await conn.commit()
    scopes = [
        (t.get("hood_id"), t["neighborhood"].strip(), t.get("category", "forsale"))
        for t in rows_in
    ]
    recomputed, warning = await _recompute_amit_fit_for_scope(scopes)
    response = {"ok": True, "count": len(rows_in), "recomputed": recomputed}
    if warning:
        response["recompute_warning"] = warning
    return response


@router.delete("/api/feature-adjustments/{fa_id}")
async def delete_feature_adjustment(fa_id: int):
    async with _db.pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT hood_id, neighborhood, category FROM neighborhood_feature_adjustments WHERE id = %s",
                (fa_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(404, "feature adjustment not found")
            await cur.execute("DELETE FROM neighborhood_feature_adjustments WHERE id = %s", (fa_id,))
        await conn.commit()

    scopes = [(row["hood_id"], row["neighborhood"], row["category"])]
    recomputed, warning = await _recompute_amit_fit_for_scope(scopes)
    response = {"ok": True, "recomputed": recomputed}
    if warning:
        response["recompute_warning"] = warning
    return response


# ---------------------------------------------------------------------------
# Facebook ingestion
# IMPORTANT: /api/ingest/facebook/health must be registered BEFORE any
# path-param routes to avoid capture issues.
# ---------------------------------------------------------------------------

# Canonical TLV address_city — matches existing properties.address_city values in prod.
# Verified 2026-04-15: all 2,175 TLV rows use this spacing (space, no hyphen).
TLV_CITY_STRING = "תל אביב יפו"

GROUP_CITY_MAP = {
    "458499457501175": TLV_CITY_STRING,
    "RentinTLV": TLV_CITY_STRING,
    "333022240594651": TLV_CITY_STRING,
    "305724686290054": TLV_CITY_STRING,
    "457465901082882": TLV_CITY_STRING,
}


class FacebookPost(BaseModel):
    post_id: str
    group_url: str
    group_id: str
    author_name: str | None = None
    posted_at: str | None = None
    description: str
    contact_phone: str | None = None
    price: int | None = None
    rooms: float | None = None
    square_meters: int | None = None
    neighborhood: str | None = None
    address_city: str | None = None
    image_urls: list[str] = []
    like_count: int | None = None
    listing_url: str


class FacebookIngestBody(BaseModel):
    posts: list[FacebookPost]


class LogRevealBody(BaseModel):
    yad2_id: str


async def _get_facebook_preset_id() -> int | None:
    """Return the search_preset id for the FB source preset, or None if not found."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM search_presets WHERE extra_params->>'source' = 'facebook' LIMIT 1"
            )
            row = await cur.fetchone()
    return row["id"] if row else None


async def _bump_fb_warning_counter() -> None:
    """Increment the FB ingest warning counter and record check time."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE ingest_state SET warning_count = warning_count + 1, last_check_at = NOW() WHERE source = 'facebook'"
            )
        await conn.commit()


async def _reset_fb_warning_counter() -> None:
    """Reset the FB ingest warning counter and record last successful check."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE ingest_state SET warning_count = 0, last_ok_at = NOW(), last_check_at = NOW() WHERE source = 'facebook'"
            )
        await conn.commit()


async def _fb_post_to_listing(post: FacebookPost) -> ScrapedListing | None:
    """
    Convert a FacebookPost to a ScrapedListing.
    Returns None if the post should be skipped (empty description AND no phone).
    """
    # Skip only if both description is empty AND no phone
    if not post.description.strip() and post.contact_phone is None:
        return None

    address_city = GROUP_CITY_MAP.get(post.group_id, TLV_CITY_STRING)

    return ScrapedListing(
        yad2_id=f"fb_{post.post_id}",
        source="facebook",
        category="rent",
        address_street=None,
        address_city=address_city,
        neighborhood=post.neighborhood,
        rooms=post.rooms,
        floor=None,
        total_floors=None,
        square_meters=post.square_meters,
        square_meter_build=None,
        price=post.price,
        currency="ILS",
        property_type=None,
        description=post.description,
        contact_name=post.author_name,
        contact_phone=post.contact_phone,
        image_urls=post.image_urls,
        listing_url=post.listing_url,
        yad2_date_added=post.posted_at,
        author_name=post.author_name,
        group_url=post.group_url,
        like_count=post.like_count,
    )


@router.get("/api/ingest/facebook/health")
async def fb_ingest_health():
    """Return FB ingest health state. Unauthed — safe to expose."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT warning_count, last_ok_at, last_check_at FROM ingest_state WHERE source = 'facebook'"
            )
            row = await cur.fetchone()

    if not row:
        return {"warning_count": 0, "last_ok_at": None, "last_check_at": None, "alert": False}

    warning_count = row["warning_count"]
    last_ok_at = row["last_ok_at"].isoformat() if row["last_ok_at"] else None
    last_check_at = row["last_check_at"].isoformat() if row["last_check_at"] else None
    return {
        "warning_count": warning_count,
        "last_ok_at": last_ok_at,
        "last_check_at": last_check_at,
        "alert": warning_count >= 2,
    }


@router.post("/api/log-reveal")
async def log_reveal(body: LogRevealBody):
    """Log a phone reveal event for any property. Unauthed."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM properties WHERE yad2_id = %s",
                (body.yad2_id,),
            )
            prop = await cur.fetchone()
            if not prop:
                raise HTTPException(status_code=404, detail="Property not found")

            await cur.execute(
                "INSERT INTO operator_notes (property_id, note, created_by) VALUES (%s, 'phone_revealed', 'system')",
                (prop["id"],),
            )
        await conn.commit()
    return {"status": "logged"}


@router.post("/api/ingest/facebook")
async def fb_ingest(request: Request, body: FacebookIngestBody):
    """Receive scraped FB posts from the Oracle VM scraper and run the full scan pipeline."""
    from pdis.config import settings

    # Bearer auth against INGEST_SECRET
    auth_header = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.ingest_secret}"
    if not settings.ingest_secret or auth_header != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing ingest secret")

    # Feature flag gate
    if not settings.fb_ingestion_enabled:
        raise HTTPException(status_code=503, detail="Facebook ingestion is disabled")

    # Resolve FB preset
    preset_id = await _get_facebook_preset_id()
    if preset_id is None:
        raise HTTPException(status_code=500, detail="Facebook preset not found — migration may not have run")

    # Build ScrapedListings, skipping posts with empty description AND no phone
    listings: list[ScrapedListing] = []
    for post in body.posts:
        listing = await _fb_post_to_listing(post)
        if listing is not None:
            listings.append(listing)

    logger.info("api.fb_ingest_received", total_posts=len(body.posts), valid_listings=len(listings))

    result = await run_scan_from_listings(preset_id, listings)

    # Bump or reset warning counter based on outcome
    if result.get("status") == "suspicious_low_volume":
        await _bump_fb_warning_counter()
    elif result.get("status") == "done":
        await _reset_fb_warning_counter()

    return result


# ---------------------------------------------------------------------------
# Yad2 forsale ingestion (scraped on Oracle VM — Render is blocked by ShieldSquare)
# ---------------------------------------------------------------------------

class Yad2IngestListing(BaseModel):
    yad2_id: str
    category: str
    address_street: str | None = None
    address_home_number: str | None = None
    address_city: str | None = None
    neighborhood: str | None = None
    rooms: float | None = None
    floor: int | None = None
    total_floors: int | None = None
    square_meters: int | None = None
    square_meter_build: int | None = None
    price: int | None = None
    currency: str = "ILS"
    property_type: str | None = None
    description: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    year_built: int | None = None
    yad2_date_added: str | None = None
    source: str = "yad2"
    latitude: float | None = None
    longitude: float | None = None
    parking: bool = False
    elevator: bool = False
    safe_room: bool = False
    renovated: bool = False
    balcony: bool = False
    pets_allowed: bool = False
    furnished: bool = False
    air_conditioning: bool = False
    is_agent: bool = False
    agent_office: str | None = None
    move_in_date: str | None = None
    hood_id: int | None = None
    customer_id: str | None = None
    accessibility: bool = False
    image_urls: list[str] = []
    listing_url: str = ""


class Yad2IngestBody(BaseModel):
    preset_id: int
    listings: list[Yad2IngestListing]


@router.post("/api/ingest/yad2")
async def yad2_ingest(request: Request, body: Yad2IngestBody):
    """Receive scraped Yad2 forsale listings from the Oracle VM scraper."""
    from pdis.config import settings

    auth_header = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.ingest_secret}" if settings.ingest_secret else None
    if not expected or auth_header != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing ingest secret")

    if not getattr(settings, "yad2_vm_ingestion_enabled", False):
        raise HTTPException(status_code=503, detail="Yad2 VM ingestion is disabled")

    async with _db.pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, category, is_active FROM search_presets WHERE id = %s",
                (body.preset_id,),
            )
            preset = await cur.fetchone()
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset {body.preset_id} not found")
    if not preset["is_active"]:
        raise HTTPException(status_code=400, detail=f"Preset {body.preset_id} is not active")
    if preset["category"] != "forsale":
        raise HTTPException(status_code=400, detail=f"Preset {body.preset_id} is not forsale")

    listings: list[ScrapedListing] = []
    for item in body.listings:
        listings.append(ScrapedListing(**item.model_dump()))

    logger.info("api.yad2_ingest_received", preset_id=body.preset_id, count=len(listings))

    result = await run_scan_from_listings(body.preset_id, listings, source="yad2")
    return result


# ---------------------------------------------------------------------------
# Govmap closed-sale ingestion
# ---------------------------------------------------------------------------

class GovmapDeal(BaseModel):
    deal_id: str
    polygon_id: str
    gush_num: int | None = None
    parcel_num: int | None = None
    sub_parcel_num: int | None = None
    settlement: str | None = None
    neighborhood: str | None = None
    street: str | None = None
    house_number: str | None = None
    floor: int | None = None
    rooms: float | None = None
    sqm: int | None = None
    sale_price: int
    deal_date: str
    year_built: int | None = None
    shape_wkt: str | None = None
    centroid_lat: float | None = None
    centroid_lng: float | None = None
    raw_data: dict | None = None


class GovmapIngestBody(BaseModel):
    deals: list[GovmapDeal]


@router.post("/api/ingest/govmap-deals")
async def govmap_ingest(request: Request, body: GovmapIngestBody):
    from pdis.config import settings as _settings
    auth = request.headers.get("Authorization", "")
    expected = f"Bearer {_settings.ingest_secret}" if _settings.ingest_secret else None
    if not expected or auth != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing ingest secret")
    if not getattr(_settings, "govmap_ingestion_enabled", False):
        raise HTTPException(status_code=503, detail="Govmap ingestion is disabled")

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            for d in body.deals:
                params = {**d.model_dump()}
                params["raw_data"] = json.dumps(d.raw_data) if d.raw_data else None
                await cur.execute("""
                    INSERT INTO closed_transactions (
                        deal_id, polygon_id, gush_num, parcel_num, sub_parcel_num,
                        settlement, neighborhood, street, house_number,
                        floor, rooms, sqm, sale_price, deal_date, year_built,
                        shape_wkt, centroid_lat, centroid_lng, raw_data
                    ) VALUES (
                        %(deal_id)s, %(polygon_id)s, %(gush_num)s, %(parcel_num)s, %(sub_parcel_num)s,
                        %(settlement)s, %(neighborhood)s, %(street)s, %(house_number)s,
                        %(floor)s, %(rooms)s, %(sqm)s, %(sale_price)s, %(deal_date)s, %(year_built)s,
                        %(shape_wkt)s, %(centroid_lat)s, %(centroid_lng)s, %(raw_data)s
                    )
                    ON CONFLICT (deal_id) DO UPDATE SET
                        polygon_id=EXCLUDED.polygon_id,
                        gush_num=EXCLUDED.gush_num,
                        parcel_num=EXCLUDED.parcel_num,
                        settlement=EXCLUDED.settlement,
                        neighborhood=EXCLUDED.neighborhood,
                        street=EXCLUDED.street,
                        house_number=EXCLUDED.house_number,
                        floor=EXCLUDED.floor,
                        rooms=EXCLUDED.rooms,
                        sqm=EXCLUDED.sqm,
                        sale_price=EXCLUDED.sale_price,
                        deal_date=EXCLUDED.deal_date,
                        year_built=EXCLUDED.year_built,
                        shape_wkt=EXCLUDED.shape_wkt,
                        centroid_lat=EXCLUDED.centroid_lat,
                        centroid_lng=EXCLUDED.centroid_lng,
                        raw_data=EXCLUDED.raw_data,
                        imported_at=NOW()
                """, params)
        await conn.commit()
    return {"inserted_or_updated": len(body.deals)}


@router.get("/api/govmap/imported-polygons")
async def govmap_imported_polygons():
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT DISTINCT polygon_id FROM closed_transactions")
            rows = await cur.fetchall()
    return {"polygon_ids": [r["polygon_id"] for r in rows]}
