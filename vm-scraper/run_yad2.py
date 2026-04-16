"""
Standalone Yad2 forsale scraper for the Oracle VM.

Render's IP is blocked by ShieldSquare on the /forsale endpoint.
This script runs on the Oracle VM, scrapes Yad2 forsale presets,
and POSTs results to the PDIS backend at /api/ingest/yad2.

No pdis.* imports — this script is standalone on the VM.
"""

import logging
import os
import random
import re
import sys
import time

try:
    from curl_cffi import requests as cf_requests
except ImportError:
    print("ERROR: curl_cffi not installed. Run: pip install 'curl_cffi>=0.7'")
    sys.exit(1)

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
log = logging.getLogger("run_yad2")

# ---------------------------------------------------------------------------
# Config from env
# ---------------------------------------------------------------------------

INGEST_SECRET = os.environ.get("INGEST_SECRET", "")
PDIS_API_URL = os.environ.get("PDIS_API_URL", "https://pdis-lsah.onrender.com").rstrip("/")

# ---------------------------------------------------------------------------
# Yad2 constants (mirrored from pdis/scraper.py)
# ---------------------------------------------------------------------------

YAD2_FEED_BASE = "https://www.yad2.co.il/api/pre-load/getFeedIndex/realestate"
YAD2_BASE_URL = "https://www.yad2.co.il"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
}

PROPERTY_TYPE_MAP = {
    "דירה": "apartment",
    "בית פרטי": "house",
    "דופלקס": "duplex",
    "גג/פנטהאוז": "penthouse",
    "סטודיו/לופט": "studio",
    "דירת גן": "garden_apartment",
    "מיני פנטהאוז": "mini_penthouse",
    "מגרש": "land",
    "קוטג'": "cottage",
    "יחידת דיור": "housing_unit",
    "מחסן": "storage",
    "חניה": "parking",
}

SCRAPE_MAX_PAGES = 10
SCRAPE_REQUEST_TIMEOUT = 15
SCRAPE_PAGE_DELAY_MIN = 1.5
SCRAPE_PAGE_DELAY_MAX = 3.5
PRESET_DELAY_MIN = 30
PRESET_DELAY_MAX = 60

# ---------------------------------------------------------------------------
# Helpers (mirrored from pdis/scraper.py — no pdis.* imports)
# ---------------------------------------------------------------------------

def _bool_field(item: dict, key: str) -> bool:
    val = item.get(key)
    return bool(val) and str(val).strip() != ""


def _parse_price(raw_price) -> "int | None":
    if raw_price is None:
        return None
    if isinstance(raw_price, (int, float)):
        return int(raw_price)
    cleaned = re.sub(r"[^\d]", "", str(raw_price))
    return int(cleaned) if cleaned else None


def _extract_row4_value(row4: list, key: str):
    for item in row4:
        if item.get("key") == key:
            val = item.get("value")
            if val is not None:
                return val
    return None


def _parse_listing(item: dict) -> "dict | None":
    """Parse a single feed item into a plain dict matching Yad2IngestListing schema."""
    if item.get("type") != "ad" or item.get("ad_type") not in ("ad", "platinum"):
        return None

    yad2_id = item.get("id") or item.get("link_token")
    if not yad2_id:
        return None

    row4 = item.get("row_4") or []

    rooms_raw = item.get("Rooms") or _extract_row4_value(row4, "rooms")
    rooms = None
    if rooms_raw is not None:
        try:
            rooms = float(rooms_raw)
        except (ValueError, TypeError):
            pass

    floor_raw = _extract_row4_value(row4, "floor")
    floor = None
    if floor_raw is not None:
        try:
            floor = int(floor_raw)
        except (ValueError, TypeError):
            pass

    sqm_raw = item.get("square_meters") or _extract_row4_value(row4, "SquareMeter")
    square_meters = None
    if sqm_raw is not None:
        try:
            square_meters = int(str(sqm_raw).strip())
        except (ValueError, TypeError):
            pass

    price = _parse_price(item.get("price"))

    property_type_he = item.get("HomeTypeID_text") or item.get("title_2")
    property_type = PROPERTY_TYPE_MAP.get(property_type_he, property_type_he)

    yad2_date_added = item.get("date_added")

    image_urls = item.get("images_urls") or []

    link_token = item.get("id") or item.get("link_token", "")
    listing_url = f"{YAD2_BASE_URL}/item/{link_token}" if link_token else ""

    raw_description = item.get("search_text") or item.get("address_more") or None
    if raw_description:
        # Strip Yad2's unresolved template tokens like $HomeNum, $Floor_text, $FurnitureInfo
        cleaned = re.sub(r"\$[A-Za-z_]+", "", raw_description)
        # Collapse comma debris like ", , " → ", "
        cleaned = re.sub(r"\s*,\s*,\s*", ", ", cleaned)
        # Collapse whitespace runs and trim
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        description = cleaned if cleaned else None
    else:
        description = None

    coords = item.get("coordinates") or {}
    latitude = None
    longitude = None
    try:
        latitude = float(coords["latitude"]) if coords.get("latitude") is not None else None
        longitude = float(coords["longitude"]) if coords.get("longitude") is not None else None
    except (ValueError, TypeError):
        pass

    parking = _bool_field(item, "Parking_text")
    elevator = _bool_field(item, "Elevator_text")
    safe_room = _bool_field(item, "mamad_text")
    renovated = _bool_field(item, "Meshupatz_text")
    balcony_val = item.get("Porch_text")
    balcony = bool(balcony_val) and str(balcony_val).strip() != "" and str(balcony_val).strip() != "אין"
    pets_allowed = _bool_field(item, "PetsInHouse_text")
    furnished = _bool_field(item, "Furniture_text")
    air_conditioning = _bool_field(item, "AirConditioner_text")
    accessibility = _bool_field(item, "handicapped_text")
    is_agent = item.get("merchant") is True
    agent_office = item.get("merchant_name") or None

    move_in_date = None
    move_in_raw = item.get("date_of_entry")
    if move_in_raw and str(move_in_raw).strip():
        try:
            move_in_date = str(move_in_raw).strip()[:10]
        except Exception:
            pass

    hood_id = None
    if item.get("hood_id") is not None:
        try:
            hood_id = int(item["hood_id"])
        except (ValueError, TypeError):
            pass

    customer_id = str(item["customer_id"]) if item.get("customer_id") is not None else None
    address_home_number = str(item["address_home_number"]) if item.get("address_home_number") is not None else None

    return {
        "yad2_id": str(yad2_id),
        "category": "forsale",
        "address_street": item.get("street"),
        "address_home_number": address_home_number,
        "address_city": item.get("city"),
        "neighborhood": item.get("neighborhood"),
        "rooms": rooms,
        "floor": floor,
        "total_floors": None,
        "square_meters": square_meters,
        "square_meter_build": None,  # filled in by detail fetch below
        "price": price,
        "currency": "ILS",
        "property_type": property_type,
        "description": description,
        "contact_name": item.get("contact_name"),
        "contact_phone": None,
        "yad2_date_added": yad2_date_added,
        "source": "yad2",
        "latitude": latitude,
        "longitude": longitude,
        "parking": parking,
        "elevator": elevator,
        "safe_room": safe_room,
        "renovated": renovated,
        "balcony": balcony,
        "pets_allowed": pets_allowed,
        "furnished": furnished,
        "air_conditioning": air_conditioning,
        "is_agent": is_agent,
        "agent_office": agent_office,
        "move_in_date": move_in_date,
        "hood_id": hood_id,
        "customer_id": customer_id,
        "accessibility": accessibility,
        "image_urls": image_urls,
        "listing_url": listing_url,
        # raw_data intentionally excluded — large + unused on ingest
    }


def _build_params(preset: dict, page: int = 1) -> dict:
    """Build query params from a search preset dict."""
    params: dict = {"page": page}

    if preset.get("city_code"):
        params["city"] = preset["city_code"]

    if preset.get("area_code"):
        params["area"] = preset["area_code"]

    min_price = preset.get("min_price")
    max_price = preset.get("max_price")
    if min_price or max_price:
        lo = min_price or 0
        hi = max_price or 99999999
        params["price"] = f"{lo}-{hi}"

    min_rooms = preset.get("min_rooms")
    max_rooms = preset.get("max_rooms")
    if min_rooms or max_rooms:
        lo = min_rooms or 0
        hi = max_rooms or 20
        params["rooms"] = f"{lo}-{hi}"

    if preset.get("property_types"):
        params["property"] = ",".join(preset["property_types"])

    if preset.get("neighborhood"):
        params["neighborhood"] = preset["neighborhood"]

    extra = preset.get("extra_params") or {}

    if extra.get("min_sqm") or extra.get("max_sqm"):
        min_s = extra.get("min_sqm", "")
        max_s = extra.get("max_sqm", "")
        params["squaremeter"] = f"{min_s}-{max_s}"

    if extra.get("min_floor") or extra.get("max_floor"):
        min_f = extra.get("min_floor", "")
        max_f = extra.get("max_floor", "")
        params["floor"] = f"{min_f}-{max_f}"

    if extra.get("enter_date"):
        params["enterDate"] = extra["enter_date"]

    yad2_key_map = {
        "airConditioner": "air_conditioning",
        "handicapped": "accessible",
    }
    for yad2_key in ["parking", "elevator", "airConditioner", "balcony", "pets", "furniture", "mamad", "handicapped"]:
        our_key = yad2_key_map.get(yad2_key, yad2_key)
        if extra.get(our_key):
            params[yad2_key] = "1"

    if extra.get("img_only"):
        params["imgOnly"] = "1"

    if extra.get("renovated"):
        params["Meshupatz"] = "1"

    if extra.get("property_condition"):
        params["propertyCondition"] = extra["property_condition"]

    return params


def _is_blocked(response) -> bool:
    if response.status_code in (403, 429):
        return True
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type:
        body = response.text.lower()
        if "captcha" in body or "blocked" in body or "robot" in body:
            return True
    return False


def fetch_item_detail(yad2_id: str) -> "dict | None":
    """Fetch detail for a single Yad2 listing to get square_meter_build."""
    url = f"{YAD2_BASE_URL}/api/item/{yad2_id}"
    try:
        r = cf_requests.get(
            url,
            headers={
                **HEADERS,
                "Referer": f"{YAD2_BASE_URL}/realestate/item/{yad2_id}",
            },
            impersonate="chrome",
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def scrape_preset_forsale(preset: dict) -> list:
    """Scrape all pages for a forsale preset. Returns list of listing dicts."""
    listings = []
    preset_id = preset.get("id")

    feed_url = f"{YAD2_FEED_BASE}/forsale"
    referer = f"https://www.yad2.co.il/realestate/forsale"

    log.info(f"[preset {preset_id}] Starting scrape")

    with cf_requests.Session(impersonate="chrome") as session:
        session.headers.update(HEADERS)
        session.headers.update({"Referer": referer})

        page = 1
        last_page = 1

        while page <= min(last_page, SCRAPE_MAX_PAGES):
            params = _build_params(preset, page=page)

            try:
                response = session.get(
                    feed_url,
                    params=params,
                    timeout=SCRAPE_REQUEST_TIMEOUT,
                )
            except Exception as exc:
                log.warning(f"[preset {preset_id}] Page {page} request failed: {exc}")
                break

            if _is_blocked(response):
                log.warning(f"[preset {preset_id}] BLOCKED on page {page} (status {response.status_code})")
                break

            if response.status_code != 200:
                log.warning(f"[preset {preset_id}] Page {page} returned HTTP {response.status_code}")
                break

            try:
                data = response.json()
            except Exception as exc:
                log.warning(f"[preset {preset_id}] Page {page} JSON parse error: {exc}")
                break

            feed = data.get("feed", {})
            feed_items = feed.get("feed_items", [])

            if not feed_items:
                log.info(f"[preset {preset_id}] Empty page {page} — stopping")
                break

            pagination = data.get("pagination", {})
            last_page = pagination.get("last_page", 1)

            page_listings = []
            for item in feed_items:
                parsed = _parse_listing(item)
                if parsed:
                    page_listings.append(parsed)

            listings.extend(page_listings)
            log.info(f"[preset {preset_id}] Page {page}/{last_page}: {len(page_listings)} listings (total {len(listings)})")

            page += 1

            if page <= min(last_page, SCRAPE_MAX_PAGES):
                delay = random.uniform(SCRAPE_PAGE_DELAY_MIN, SCRAPE_PAGE_DELAY_MAX)
                time.sleep(delay)

    log.info(f"[preset {preset_id}] Scrape done: {len(listings)} total listings")
    return listings


def fill_detail_for_missing(listings: list) -> list:
    """Fetch detail endpoint for listings without square_meter_build and fill it in."""
    missing_ids = [l["yad2_id"] for l in listings if l.get("square_meter_build") is None]
    if not missing_ids:
        return listings

    log.info(f"Fetching detail for {len(missing_ids)} listings missing square_meter_build")

    detail_map = {}
    for yad2_id in missing_ids:
        detail = fetch_item_detail(yad2_id)
        if detail:
            sqmb = detail.get("square_meter_build")
            if sqmb is not None:
                try:
                    detail_map[yad2_id] = int(sqmb)
                except (ValueError, TypeError):
                    pass
        # small delay to avoid hammering detail API
        time.sleep(random.uniform(0.3, 0.8))

    for listing in listings:
        yid = listing["yad2_id"]
        if yid in detail_map:
            listing["square_meter_build"] = detail_map[yid]

    log.info(f"Filled square_meter_build for {len(detail_map)} listings")
    return listings


def post_to_backend(preset_id: int, listings: list, max_attempts: int = 3, retry_wait_s: int = 60) -> int:
    """POST listings to /api/ingest/yad2 with retry on transient failures.
    Render's free-tier worker can return intermittent 500s when bg tasks are stacked
    (worker recycling, transient pool/connectivity issues). Retry once or twice with
    a wait so the next attempt hits a different worker state.
    Returns the final HTTP status code."""
    url = f"{PDIS_API_URL}/api/ingest/yad2"
    payload = {
        "preset_id": preset_id,
        "listings": listings,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {INGEST_SECRET}",
    }
    last_status = 0
    for attempt in range(1, max_attempts + 1):
        try:
            r = cf_requests.post(
                url,
                json=payload,
                headers=headers,
                impersonate="chrome",
                timeout=60,
            )
            last_status = r.status_code
            log.info(f"[preset {preset_id}] POST /api/ingest/yad2 → HTTP {r.status_code} (attempt {attempt}/{max_attempts})")
            if r.status_code in (200, 201):
                return r.status_code
            log.warning(f"[preset {preset_id}] Backend response body: {r.text[:500]}")
            # Non-2xx — retry only on 5xx; 4xx is a permanent error (bad payload, auth, flag)
            if r.status_code < 500:
                return r.status_code
        except Exception as exc:
            log.error(f"[preset {preset_id}] POST failed (attempt {attempt}/{max_attempts}): {exc}")
            last_status = 0
        if attempt < max_attempts:
            log.info(f"[preset {preset_id}] Retrying in {retry_wait_s}s...")
            time.sleep(retry_wait_s)
    log.error(f"[preset {preset_id}] All {max_attempts} attempts failed; final status {last_status}")
    return last_status


def fetch_presets() -> list:
    """GET /api/presets from backend (no auth). Returns list of preset dicts."""
    url = f"{PDIS_API_URL}/api/presets"
    try:
        r = cf_requests.get(url, impersonate="chrome", timeout=15)
        if r.status_code == 200:
            data = r.json()
            # Backend may return {"presets": [...]} or a plain list
            if isinstance(data, list):
                return data
            return data.get("presets", [])
    except Exception as exc:
        log.error(f"Failed to fetch presets: {exc}")
    return []


def main():
    if not INGEST_SECRET:
        log.error("INGEST_SECRET is not set — cannot POST to backend. Exiting.")
        sys.exit(1)

    log.info("run_yad2: starting")
    log.info(f"Backend: {PDIS_API_URL}")

    presets = fetch_presets()
    log.info(f"Fetched {len(presets)} total presets from backend")

    # Filter to active Yad2 presets (both rent and forsale — /rent is now blocked on Render too)
    yad2_presets = [
        p for p in presets
        if p.get("category") in ("forsale", "rent")
        and p.get("is_active") is True
        and (p.get("extra_params") or {}).get("source", "yad2") in (None, "yad2")
    ]
    log.info(f"Active Yad2 presets (rent+forsale): {len(yad2_presets)}")

    if not yad2_presets:
        log.info("No Yad2 presets to scrape — exiting")
        return

    for i, preset in enumerate(yad2_presets):
        preset_id = preset["id"]
        try:
            listings = scrape_preset_forsale(preset)

            if listings:
                listings = fill_detail_for_missing(listings)

            log.info(f"[preset {preset_id}] Posting {len(listings)} listings to backend")
            status = post_to_backend(preset_id, listings)
            log.info(f"[preset {preset_id}] Done — backend status {status}")

        except Exception as exc:
            log.error(f"[preset {preset_id}] Unexpected error: {exc}")

        # Delay between presets (skip after last one)
        if i < len(yad2_presets) - 1:
            delay = random.uniform(PRESET_DELAY_MIN, PRESET_DELAY_MAX)
            log.info(f"Waiting {delay:.0f}s before next preset")
            time.sleep(delay)

    log.info("run_yad2: all presets done")


if __name__ == "__main__":
    main()
