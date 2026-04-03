"""
PDIS API routes.
"""

import json
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional

import structlog

import pdis.database as _db
from pdis.database import check_connection
from pdis.scanner import run_scan, run_all_scans
from pdis.signals import compute_signals_batch
from pdis.classification import classify_batch

logger = structlog.get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/api/health")
async def health():
    db_ok = await check_connection()
    return {"status": "ok", "db_connected": db_ok, "version": "0.1.0"}


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
                    sps.opportunities, sps.created_at
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


@router.get("/api/presets/{preset_id}/stats")
async def get_preset_stats(preset_id: int):
    """Return recent scan_preset_stats for a preset (last 20 sessions)."""
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT session_id, total_active, new_listings, removals,
                       price_drops, price_increases, opportunities, created_at
                FROM scan_preset_stats
                WHERE preset_id = %s
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (preset_id,),
            )
            rows = await cur.fetchall()
    return {"preset_id": preset_id, "stats": [dict(r) for r in rows]}


@router.post("/api/presets")
async def create_preset(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Name is required")

    city_code = body.get("city_code", "").strip()
    source = body.get("source", "yad2")

    extra_params: dict = {}
    if source == "madlan":
        extra_params["source"] = "madlan"
        extra_params["madlan_city"] = body.get("madlan_city", city_code)
    elif source == "both":
        extra_params["source"] = "both"

    # Advanced filter params stored in extra_params JSONB
    for key in ["min_sqm", "max_sqm", "min_floor", "max_floor", "enter_date",
                "img_only", "parking", "elevator", "air_conditioning", "balcony",
                "pets", "furniture", "mamad", "accessible"]:
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
    extra_params: dict = {}
    if source == "madlan":
        extra_params["source"] = "madlan"
        extra_params["madlan_city"] = body.get("madlan_city", body.get("city_code", ""))
    elif source == "both":
        extra_params["source"] = "both"

    # Advanced filter params stored in extra_params JSONB
    for key in ["min_sqm", "max_sqm", "min_floor", "max_floor", "enter_date",
                "img_only", "parking", "elevator", "air_conditioning", "balcony",
                "pets", "furniture", "mamad", "accessible"]:
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


@router.post("/api/scan/{preset_id}")
async def trigger_scan(preset_id: int):
    try:
        result = await run_scan(preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("api.scan_error", preset_id=preset_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    return result


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
                       pc.classification, pc.signal_details
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
                ORDER BY CASE pc.classification WHEN 'hot' THEN 1 WHEN 'warm' THEN 2 ELSE 3 END,
                         p.updated_at DESC
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
                SELECT classification, distress_score, signal_details, updated_at
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
                    pc.*, p.*,
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
    sig = signals.get(property_id, {"distress_score": 0.0, "details": {}})
    return {
        "property_id": property_id,
        "distress_score": sig["distress_score"],
        "details": sig["details"],
    }


# ---------------------------------------------------------------------------
# Classifications
# ---------------------------------------------------------------------------

@router.get("/api/classifications")
async def list_classifications(
    classification: str | None = Query(default=None),
    min_score: float | None = Query(default=None),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=1000),
):
    conditions = []
    params: list = []

    if classification is not None:
        conditions.append("pc.classification = %s")
        params.append(classification)
    if min_score is not None:
        conditions.append("pc.distress_score >= %s")
        params.append(min_score)
    if category is not None:
        conditions.append("p.category = %s")
        params.append(category)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    offset = (page - 1) * per_page

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM property_classifications pc
                JOIN properties p ON p.id = pc.property_id
                {where}
                """,
                params,
            )
            count_row = await cur.fetchone()
            total = count_row["total"] if count_row else 0

            await cur.execute(
                f"""
                SELECT pc.*, p.yad2_id, p.address_street, p.address_city,
                       p.address_home_number, p.price, p.rooms, p.neighborhood, p.days_on_market,
                       p.square_meters, p.image_urls, p.listing_url,
                       p.is_agent, p.parking, p.elevator, p.air_conditioning,
                       p.source, p.description, p.contact_name,
                       (SELECT ARRAY_AGG(DISTINCT p2.source)
                        FROM property_matches pm
                        JOIN properties p2 ON p2.id = CASE
                            WHEN pm.property_id_a = p.id THEN pm.property_id_b
                            ELSE pm.property_id_a END
                        WHERE pm.property_id_a = p.id OR pm.property_id_b = p.id
                       ) AS matched_sources
                FROM property_classifications pc
                JOIN properties p ON p.id = pc.property_id
                {where}
                ORDER BY CASE pc.classification
                    WHEN 'hot' THEN 1
                    WHEN 'warm' THEN 2
                    ELSE 3
                END, pc.updated_at DESC
                LIMIT %s OFFSET %s
                """,
                params + [per_page, offset],
            )
            rows = await cur.fetchall()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "classifications": [dict(r) for r in rows],
    }


@router.get("/api/opportunities")
async def list_opportunities(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=1000),
    category: str | None = Query(default=None),
):
    offset = (page - 1) * per_page
    category_clause = ""
    count_params: list = []
    if category:
        category_clause = "AND p.category = %s"
        count_params.append(category)

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM property_classifications pc
                JOIN properties p ON p.id = pc.property_id
                LEFT JOIN blacklist bl ON bl.property_id = pc.property_id
                WHERE pc.classification IN ('hot', 'warm')
                  AND bl.id IS NULL
                {category_clause}
                """,
                tuple(count_params),
            )
            count_row = await cur.fetchone()
            total = count_row["total"] if count_row else 0

            main_params: list = list(count_params)
            await cur.execute(
                f"""
                SELECT pc.*, p.*,
                       (SELECT ARRAY_AGG(DISTINCT p2.source)
                        FROM property_matches pm
                        JOIN properties p2 ON p2.id = CASE
                            WHEN pm.property_id_a = p.id THEN pm.property_id_b
                            ELSE pm.property_id_a END
                        WHERE pm.property_id_a = p.id OR pm.property_id_b = p.id
                       ) AS matched_sources
                FROM property_classifications pc
                JOIN properties p ON p.id = pc.property_id
                LEFT JOIN blacklist bl ON bl.property_id = pc.property_id
                WHERE pc.classification IN ('hot', 'warm')
                  AND bl.id IS NULL
                {category_clause}
                ORDER BY CASE pc.classification
                    WHEN 'hot' THEN 1
                    WHEN 'warm' THEN 2
                    ELSE 3
                END, pc.updated_at DESC
                LIMIT %s OFFSET %s
                """,
                tuple(main_params) + (per_page, offset),
            )
            rows = await cur.fetchall()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "opportunities": [dict(r) for r in rows],
    }


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

    await classify_batch([property_id])
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

    await classify_batch([property_id])
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

    await classify_batch([property_id])
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

    await classify_batch([property_id])
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
                SELECT p.*, pc.classification, pc.distress_score, pc.signal_details,
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
# Stats
# ---------------------------------------------------------------------------

@router.get("/api/stats")
async def get_stats(category: str | None = Query(default=None)):
    cat_filter = "AND category = %s" if category else ""
    cat_param = (category,) if category else ()

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT COUNT(*) AS total_properties FROM properties WHERE TRUE {cat_filter}",
                cat_param,
            )
            total_row = await cur.fetchone()

            await cur.execute(
                f"SELECT COUNT(*) AS active_properties FROM properties WHERE is_active = TRUE {cat_filter}",
                cat_param,
            )
            active_row = await cur.fetchone()

            await cur.execute(
                "SELECT COUNT(*) AS total_sessions FROM scan_sessions"
            )
            sessions_row = await cur.fetchone()

            await cur.execute(
                "SELECT COUNT(*) AS total_snapshots FROM property_snapshots"
            )
            snaps_row = await cur.fetchone()

            await cur.execute(
                f"""
                SELECT AVG(price) AS avg_price, MIN(price) AS min_price, MAX(price) AS max_price
                FROM properties
                WHERE is_active = TRUE AND price IS NOT NULL
                {cat_filter}
                """,
                cat_param,
            )
            price_row = await cur.fetchone()

            await cur.execute(
                f"""
                SELECT AVG(days_on_market) AS avg_days_on_market
                FROM properties
                WHERE is_active = TRUE
                {cat_filter}
                """,
                cat_param,
            )
            dom_row = await cur.fetchone()

            await cur.execute(
                """
                SELECT status, COUNT(*) AS cnt
                FROM scan_sessions
                GROUP BY status
                """
            )
            session_status_rows = await cur.fetchall()

            if category:
                await cur.execute(
                    """
                    SELECT COUNT(*) AS total_events FROM property_events pe
                    JOIN properties p ON p.id = pe.property_id
                    WHERE p.category = %s
                    """,
                    (category,),
                )
            else:
                await cur.execute("SELECT COUNT(*) AS total_events FROM property_events")
            events_total_row = await cur.fetchone()

            if category:
                await cur.execute(
                    """
                    SELECT pe.event_type, COUNT(*) AS cnt
                    FROM property_events pe
                    JOIN properties p ON p.id = pe.property_id
                    WHERE p.category = %s
                    GROUP BY pe.event_type
                    """,
                    (category,),
                )
            else:
                await cur.execute(
                    """
                    SELECT event_type, COUNT(*) AS cnt
                    FROM property_events
                    GROUP BY event_type
                    """
                )
            events_by_type_rows = await cur.fetchall()

            if category:
                await cur.execute(
                    """
                    SELECT pc.classification, COUNT(*) AS cnt
                    FROM property_classifications pc
                    JOIN properties p ON p.id = pc.property_id
                    WHERE p.category = %s
                    GROUP BY pc.classification
                    """,
                    (category,),
                )
            else:
                await cur.execute(
                    """
                    SELECT classification, COUNT(*) AS cnt
                    FROM property_classifications
                    GROUP BY classification
                    """
                )
            classifications_rows = await cur.fetchall()

            await cur.execute("SELECT COUNT(*) AS cnt FROM whitelist")
            whitelist_row = await cur.fetchone()

            await cur.execute("SELECT COUNT(*) AS cnt FROM blacklist")
            blacklist_row = await cur.fetchone()

            await cur.execute("""
                SELECT MAX(finished_at) as last_scan_at
                FROM scan_sessions
                WHERE status = 'done'
            """)
            last_scan_row = await cur.fetchone()

    classifications_counts = {"hot": 0, "warm": 0, "cold": 0}
    for r in classifications_rows:
        classifications_counts[r["classification"]] = r["cnt"]

    return {
        "total_properties": total_row["total_properties"] if total_row else 0,
        "active_properties": active_row["active_properties"] if active_row else 0,
        "total_sessions": sessions_row["total_sessions"] if sessions_row else 0,
        "total_snapshots": snaps_row["total_snapshots"] if snaps_row else 0,
        "price_stats": {
            "avg": float(price_row["avg_price"]) if price_row and price_row["avg_price"] else None,
            "min": price_row["min_price"] if price_row else None,
            "max": price_row["max_price"] if price_row else None,
        },
        "avg_days_on_market": (
            float(dom_row["avg_days_on_market"])
            if dom_row and dom_row["avg_days_on_market"]
            else None
        ),
        "sessions_by_status": {r["status"]: r["cnt"] for r in session_status_rows},
        "total_events": events_total_row["total_events"] if events_total_row else 0,
        "events_by_type": {r["event_type"]: r["cnt"] for r in events_by_type_rows},
        "classifications": classifications_counts,
        "whitelisted": whitelist_row["cnt"] if whitelist_row else 0,
        "blacklisted": blacklist_row["cnt"] if blacklist_row else 0,
        "last_scan_at": last_scan_row["last_scan_at"].isoformat() if last_scan_row and last_scan_row["last_scan_at"] else None,
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
