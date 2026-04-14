"""
Govmap closed-sale scraper for the Oracle VM.

Walks a grid over Tel Aviv, collects closed real-estate transactions from the
Israel Tax Authority via govmap.gov.il, and POSTs them to the PDIS backend at
/api/ingest/govmap-deals.

No pdis.* imports — this script is standalone on the VM.

Usage:
  python3 run_govmap.py             # full backfill
  python3 run_govmap.py --resume    # skip already-imported polygons
  python3 run_govmap.py --monthly   # only deals from the last 35 days
"""

import argparse
import logging
import math
import os
import sys
import time

try:
    from curl_cffi import requests as cf_requests
except ImportError:
    print("ERROR: curl_cffi not installed. Run: pip install 'curl_cffi>=0.7'")
    sys.exit(1)

try:
    from pyproj import Transformer
except ImportError:
    print("ERROR: pyproj not installed. Run: pip install 'pyproj>=3.6'")
    sys.exit(1)

from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FILE = os.environ.get("LOG_FILE", "")
handlers = [logging.StreamHandler(sys.stdout)]
if LOG_FILE:
    handlers.append(logging.FileHandler(LOG_FILE))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=handlers,
)
log = logging.getLogger("run_govmap")

# ---------------------------------------------------------------------------
# Config from env
# ---------------------------------------------------------------------------

INGEST_SECRET = os.environ.get("INGEST_SECRET", "")
PDIS_API_URL = os.environ.get("PDIS_API_URL", "https://pdis-lsah.onrender.com").rstrip("/")

# ---------------------------------------------------------------------------
# Govmap constants
# ---------------------------------------------------------------------------

GOVMAP_BASE = "https://api.govmap.gov.il/govmap/api"

# TLV grid in EPSG:2039 (Israel Transverse Mercator)
# x: easting range for Tel Aviv
# y: northing range for Tel Aviv
GRID_X_MIN = 3865000
GRID_X_MAX = 3880000
GRID_Y_MIN = 3765000
GRID_Y_MAX = 3785000
GRID_STEP = 200  # metres

BATCH_SIZE = 100       # deals per POST to backend
REQ_DELAY = 1.0        # seconds between govmap requests
MAX_CONSECUTIVE_FAILURES = 3
RETRY_DELAYS = [5, 15, 30]  # seconds for 5xx retries

# EPSG:2039 → EPSG:4326 transformer (always_xy=True: x=lng, y=lat)
_itm_to_wgs = Transformer.from_crs("EPSG:2039", "EPSG:4326", always_xy=True)


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def itm_to_wgs(x_itm: float, y_itm: float) -> tuple[float, float]:
    """Convert Israel Transverse Mercator to WGS-84 (lng, lat)."""
    lng, lat = _itm_to_wgs.transform(x_itm, y_itm)
    return lat, lng  # return as (lat, lng)


def _haversine_m(lat1, lng1, lat2, lng2) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Govmap API helpers
# ---------------------------------------------------------------------------

def _govmap_get(path: str, session) -> dict | None:
    """GET from govmap API with retry on 5xx."""
    url = f"{GOVMAP_BASE}/{path}"
    consecutive_failures = 0
    for attempt, delay in enumerate([0] + RETRY_DELAYS):
        if delay:
            log.warning(f"Retrying {url} in {delay}s (attempt {attempt+1})")
            time.sleep(delay)
        try:
            r = session.get(url, timeout=20, impersonate="chrome")
            if r.status_code == 200:
                return r.json()
            if r.status_code >= 500:
                consecutive_failures += 1
                log.warning(f"govmap 5xx on {url}: HTTP {r.status_code}")
                continue
            log.warning(f"govmap non-200 on {url}: HTTP {r.status_code}")
            return None
        except Exception as exc:
            consecutive_failures += 1
            log.warning(f"govmap request error on {url}: {exc}")
            continue
    return None


def get_polygon_ids_near(x_itm: int, y_itm: int, radius_m: int, session) -> list[str]:
    """
    GET /deals/{x},{y}/{radius} — returns list of deal polygons near the point.
    Returns list of unique polygon_ids.
    """
    data = _govmap_get(f"deals/{x_itm},{y_itm}/{radius_m}", session)
    if not data:
        return []
    ids = set()
    # Response shape: {"data": [{"polygonId": "7434-5", ...}, ...]} (approximate)
    items = data if isinstance(data, list) else data.get("data", data.get("results", []))
    if not isinstance(items, list):
        return []
    for item in items:
        pid = item.get("polygonId") or item.get("polygon_id") or item.get("id")
        if pid:
            ids.add(str(pid))
    return list(ids)


def get_deals_for_polygon(polygon_id: str, session) -> list[dict]:
    """
    GET /street-deals/{polygon_id} — returns all deals for that polygon.
    """
    data = _govmap_get(f"street-deals/{polygon_id}", session)
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("data", data.get("deals", data.get("results", [])))
    if not isinstance(items, list):
        return []
    return items


def parse_deal(raw: dict, polygon_id: str) -> dict | None:
    """
    Parse a raw govmap deal dict into the GovmapDeal schema.
    Govmap centroid coordinates are in EPSG:2039 — must be projected to WGS-84.
    """
    deal_id = raw.get("dealId") or raw.get("deal_id") or raw.get("id")
    if not deal_id:
        return None
    deal_id = str(deal_id)

    # Sale price
    sale_price = raw.get("dealAmount") or raw.get("sale_price") or raw.get("price")
    try:
        sale_price = int(sale_price)
    except (TypeError, ValueError):
        return None
    if sale_price <= 0:
        return None

    # Deal date
    deal_date_raw = raw.get("dealDate") or raw.get("deal_date") or raw.get("date")
    if not deal_date_raw:
        return None
    # Govmap returns dates as "2023-06-01" or "01/06/2023" or epoch ms
    deal_date_str = None
    if isinstance(deal_date_raw, (int, float)):
        # epoch milliseconds
        d = date.fromtimestamp(deal_date_raw / 1000)
        deal_date_str = d.isoformat()
    elif isinstance(deal_date_raw, str):
        # Try ISO first
        if len(deal_date_raw) >= 10 and deal_date_raw[4] == "-":
            deal_date_str = deal_date_raw[:10]
        elif "/" in deal_date_raw:
            parts = deal_date_raw.split("/")
            if len(parts) == 3:
                # DD/MM/YYYY
                deal_date_str = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    if not deal_date_str:
        return None

    # sqm
    sqm = raw.get("dealArea") or raw.get("sqm") or raw.get("area")
    try:
        sqm = int(sqm) if sqm is not None else None
    except (TypeError, ValueError):
        sqm = None

    # Centroid — govmap may return ITM or lat/lng depending on API version
    cent_x = raw.get("centroidX") or raw.get("x") or raw.get("centroid_x")
    cent_y = raw.get("centroidY") or raw.get("y") or raw.get("centroid_y")
    centroid_lat = None
    centroid_lng = None
    if cent_x is not None and cent_y is not None:
        try:
            cx = float(cent_x)
            cy = float(cent_y)
            # If values look like ITM (> 1,000,000), project them
            if cx > 1_000_000 or cy > 1_000_000:
                centroid_lat, centroid_lng = itm_to_wgs(cx, cy)
            else:
                # Already WGS-84
                centroid_lat = cy
                centroid_lng = cx
        except (TypeError, ValueError):
            pass

    # Gush/parcel from polygon_id (format: "7434-5" → gush=7434, parcel=5)
    gush_num = None
    parcel_num = None
    sub_parcel_num = None
    parts = str(polygon_id).split("-")
    if len(parts) >= 2:
        try:
            gush_num = int(parts[0])
            parcel_num = int(parts[1])
        except (ValueError, TypeError):
            pass
        if len(parts) >= 3:
            try:
                sub_parcel_num = int(parts[2])
            except (ValueError, TypeError):
                pass
    # Override with explicit fields if present
    if raw.get("gushNum") or raw.get("gush_num"):
        try:
            gush_num = int(raw.get("gushNum") or raw.get("gush_num"))
        except (TypeError, ValueError):
            pass
    if raw.get("parcelNum") or raw.get("parcel_num"):
        try:
            parcel_num = int(raw.get("parcelNum") or raw.get("parcel_num"))
        except (TypeError, ValueError):
            pass

    floor = raw.get("floor") or raw.get("floorNum")
    try:
        floor = int(floor) if floor is not None else None
    except (TypeError, ValueError):
        floor = None

    rooms = raw.get("rooms") or raw.get("roomsNum")
    try:
        rooms = float(rooms) if rooms is not None else None
    except (TypeError, ValueError):
        rooms = None

    year_built = raw.get("yearBuilt") or raw.get("year_built") or raw.get("buildYear")
    try:
        year_built = int(year_built) if year_built is not None else None
    except (TypeError, ValueError):
        year_built = None

    return {
        "deal_id": deal_id,
        "polygon_id": polygon_id,
        "gush_num": gush_num,
        "parcel_num": parcel_num,
        "sub_parcel_num": sub_parcel_num,
        "settlement": raw.get("settlement") or raw.get("city"),
        "neighborhood": raw.get("neighborhood") or raw.get("neighborhoodName"),
        "street": raw.get("street") or raw.get("streetName"),
        "house_number": str(raw.get("houseNum") or raw.get("house_number") or "").strip() or None,
        "floor": floor,
        "rooms": rooms,
        "sqm": sqm,
        "sale_price": sale_price,
        "deal_date": deal_date_str,
        "year_built": year_built,
        "shape_wkt": raw.get("shapeWkt") or raw.get("shape_wkt"),
        "centroid_lat": centroid_lat,
        "centroid_lng": centroid_lng,
        "raw_data": raw,
    }


# ---------------------------------------------------------------------------
# Backend helpers
# ---------------------------------------------------------------------------

def fetch_imported_polygons() -> set[str]:
    """GET /api/govmap/imported-polygons — returns set of already-imported polygon_ids."""
    url = f"{PDIS_API_URL}/api/govmap/imported-polygons"
    try:
        r = cf_requests.get(url, impersonate="chrome", timeout=30)
        if r.status_code == 200:
            data = r.json()
            return set(data.get("polygon_ids", []))
    except Exception as exc:
        log.error(f"Failed to fetch imported polygons: {exc}")
    return set()


def post_deals_to_backend(deals: list[dict]) -> bool:
    """POST a batch of deals to /api/ingest/govmap-deals. Returns True on success."""
    url = f"{PDIS_API_URL}/api/ingest/govmap-deals"
    payload = {"deals": deals}
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {INGEST_SECRET}",
    }
    consecutive_failures = 0
    for attempt, delay in enumerate([0] + RETRY_DELAYS):
        if delay:
            log.warning(f"Retrying POST govmap-deals in {delay}s (attempt {attempt+1})")
            time.sleep(delay)
        try:
            r = cf_requests.post(url, json=payload, headers=headers, impersonate="chrome", timeout=60)
            log.info(f"POST /api/ingest/govmap-deals → HTTP {r.status_code} ({len(deals)} deals)")
            if r.status_code in (200, 201):
                return True
            if r.status_code >= 500:
                consecutive_failures += 1
                log.warning(f"Backend 5xx: {r.text[:300]}")
                continue
            log.error(f"Backend rejected batch: HTTP {r.status_code} — {r.text[:300]}")
            return False
        except Exception as exc:
            consecutive_failures += 1
            log.error(f"POST govmap-deals failed: {exc}")
            continue
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Govmap closed-sale scraper")
    parser.add_argument("--resume", action="store_true", help="Skip already-imported polygons")
    parser.add_argument("--monthly", action="store_true", help="Only deals from the last 35 days")
    args = parser.parse_args()

    if not INGEST_SECRET:
        log.error("INGEST_SECRET is not set — cannot POST to backend. Exiting.")
        sys.exit(1)

    log.info("run_govmap: starting")
    log.info(f"Backend: {PDIS_API_URL}")
    log.info(f"Resume: {args.resume} | Monthly: {args.monthly}")

    # Monthly cutoff date
    monthly_cutoff = None
    if args.monthly:
        monthly_cutoff = (date.today() - timedelta(days=35)).isoformat()
        log.info(f"Monthly mode: only deals >= {monthly_cutoff}")

    # Fetch already-imported polygons if resuming
    imported_polygons: set[str] = set()
    if args.resume:
        log.info("Fetching already-imported polygons for resume...")
        imported_polygons = fetch_imported_polygons()
        log.info(f"Skipping {len(imported_polygons)} already-imported polygons")

    # Build grid of (x, y) points
    xs = list(range(GRID_X_MIN, GRID_X_MAX + 1, GRID_STEP))
    ys = list(range(GRID_Y_MIN, GRID_Y_MAX + 1, GRID_STEP))
    total_points = len(xs) * len(ys)
    log.info(f"Grid: {len(xs)} x {len(ys)} = {total_points} points at {GRID_STEP}m step")

    seen_polygons: set[str] = set()
    pending_deals: list[dict] = []
    total_deals_sent = 0
    consecutive_failures = 0
    polygons_processed = 0

    with cf_requests.Session(impersonate="chrome") as session:
        for xi, x in enumerate(xs):
            for yi, y in enumerate(ys):
                # Get polygon IDs near this grid point
                polygon_ids = get_polygon_ids_near(x, y, 200, session)
                time.sleep(REQ_DELAY)

                for polygon_id in polygon_ids:
                    if polygon_id in seen_polygons:
                        continue
                    seen_polygons.add(polygon_id)

                    if args.resume and polygon_id in imported_polygons:
                        continue

                    # Fetch deals for this polygon
                    raw_deals = get_deals_for_polygon(polygon_id, session)
                    time.sleep(REQ_DELAY)

                    for raw in raw_deals:
                        parsed = parse_deal(raw, polygon_id)
                        if not parsed:
                            continue
                        # Monthly filter
                        if monthly_cutoff and parsed["deal_date"] < monthly_cutoff:
                            continue
                        pending_deals.append(parsed)

                    polygons_processed += 1

                    # Flush batch
                    if len(pending_deals) >= BATCH_SIZE:
                        ok = post_deals_to_backend(pending_deals)
                        if ok:
                            total_deals_sent += len(pending_deals)
                            consecutive_failures = 0
                        else:
                            consecutive_failures += 1
                            log.error(f"Consecutive backend failures: {consecutive_failures}")
                            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                                log.error("Too many consecutive failures — hard exit")
                                sys.exit(1)
                        pending_deals = []

                    if polygons_processed % 100 == 0:
                        log.info(f"Progress: {polygons_processed} polygons, {total_deals_sent} deals sent, grid ~{xi*len(ys)+yi}/{total_points}")

    # Flush remaining
    if pending_deals:
        ok = post_deals_to_backend(pending_deals)
        if ok:
            total_deals_sent += len(pending_deals)
        else:
            log.error("Final batch failed to post")

    log.info(f"run_govmap: done — {polygons_processed} polygons, {total_deals_sent} deals sent")


if __name__ == "__main__":
    main()
