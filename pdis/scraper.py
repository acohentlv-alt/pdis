"""
Yad2 rental scraper using curl_cffi for TLS fingerprinting.

Uses https://www.yad2.co.il/api/pre-load/getFeedIndex/realestate/rent
which returns JSON feed data with pagination.
"""

import asyncio
import random
import re
import time
from typing import Any

import structlog
from curl_cffi import requests as cf_requests

from pdis.config import settings
from pdis.models import ScrapedListing, ScrapeResult

logger = structlog.get_logger(__name__)

YAD2_FEED_URL = "https://www.yad2.co.il/api/pre-load/getFeedIndex/realestate/rent"
YAD2_BASE_URL = "https://www.yad2.co.il"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.yad2.co.il/realestate/rent",
}

# Property type mapping from HomeTypeID_text (Hebrew) to English
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


def _bool_field(item: dict, key: str) -> bool:
    val = item.get(key)
    return bool(val) and str(val).strip() != ""


def _parse_price(raw_price: Any) -> int | None:
    """Parse price string like '7,000 ₪' or integer to int."""
    if raw_price is None:
        return None
    if isinstance(raw_price, (int, float)):
        return int(raw_price)
    # Strip non-numeric characters except digits
    cleaned = re.sub(r"[^\d]", "", str(raw_price))
    return int(cleaned) if cleaned else None


def _extract_row4_value(row4: list[dict], key: str) -> Any:
    """Extract a value from row_4 array by key."""
    for item in row4:
        if item.get("key") == key:
            val = item.get("value")
            if val is not None:
                return val
    return None


def _parse_listing(item: dict, category: str = "rent") -> ScrapedListing | None:
    """Parse a single feed item into a ScrapedListing."""
    # Skip non-ad items (promotions, banners, etc.)
    if item.get("type") != "ad" or item.get("ad_type") not in ("ad", "platinum"):
        return None

    yad2_id = item.get("id") or item.get("link_token")
    if not yad2_id:
        return None

    row4 = item.get("row_4") or []

    # Rooms: prefer explicit Rooms field, fall back to row_4
    rooms_raw = item.get("Rooms") or _extract_row4_value(row4, "rooms")
    rooms: float | None = None
    if rooms_raw is not None:
        try:
            rooms = float(rooms_raw)
        except (ValueError, TypeError):
            pass

    # Floor
    floor_raw = _extract_row4_value(row4, "floor")
    floor: int | None = None
    if floor_raw is not None:
        try:
            floor = int(floor_raw)
        except (ValueError, TypeError):
            pass

    # Square meters: prefer explicit field, fall back to row_4
    sqm_raw = item.get("square_meters") or _extract_row4_value(row4, "SquareMeter")
    square_meters: int | None = None
    if sqm_raw is not None:
        try:
            square_meters = int(str(sqm_raw).strip())
        except (ValueError, TypeError):
            pass

    # Price
    price = _parse_price(item.get("price"))

    # Currency: ₪ → ILS
    currency = "ILS"

    # Property type
    property_type_he = item.get("HomeTypeID_text") or item.get("title_2")
    property_type = PROPERTY_TYPE_MAP.get(property_type_he, property_type_he)

    # Yad2 upload date
    yad2_date_added = item.get("date_added")

    # Images
    image_urls: list[str] = item.get("images_urls") or []

    # Listing URL
    link_token = item.get("id") or item.get("link_token", "")
    listing_url = f"{YAD2_BASE_URL}/item/{link_token}" if link_token else ""

    # Description from search_text is verbose; use address_more if available
    description = item.get("address_more") or None

    coords = item.get("coordinates") or {}
    latitude = None
    longitude = None
    try:
        latitude = float(coords.get("latitude")) if coords.get("latitude") is not None else None
        longitude = float(coords.get("longitude")) if coords.get("longitude") is not None else None
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

    return ScrapedListing(
        yad2_id=str(yad2_id),
        category=category,
        address_street=item.get("street"),
        address_home_number=address_home_number,
        address_city=item.get("city"),
        neighborhood=item.get("neighborhood"),
        rooms=rooms,
        floor=floor,
        total_floors=None,  # API does not provide total_floors directly
        square_meters=square_meters,
        price=price,
        currency=currency,
        property_type=property_type,
        description=description,
        contact_name=item.get("contact_name"),
        contact_phone=None,  # Phone not exposed in feed index, requires separate call
        yad2_date_added=yad2_date_added,
        source="yad2",
        latitude=latitude,
        longitude=longitude,
        parking=parking,
        elevator=elevator,
        safe_room=safe_room,
        renovated=renovated,
        balcony=balcony,
        pets_allowed=pets_allowed,
        furnished=furnished,
        air_conditioning=air_conditioning,
        is_agent=is_agent,
        agent_office=agent_office,
        move_in_date=move_in_date,
        hood_id=hood_id,
        customer_id=customer_id,
        accessibility=accessibility,
        image_urls=image_urls,
        listing_url=listing_url,
        raw_data=item,
    )


def _build_params(preset: dict, page: int = 1) -> dict:
    """Build query params from a search preset dict."""
    params: dict[str, Any] = {"page": page}

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

    # Merge any extra_params
    extra = preset.get("extra_params") or {}
    params.update(extra)

    return params


def _is_blocked(response: cf_requests.Response) -> bool:
    """Detect whether Yad2 has blocked the request."""
    if response.status_code in (403, 429):
        return True
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type:
        body = response.text.lower()
        if "captcha" in body or "blocked" in body or "robot" in body:
            return True
    return False


async def scrape_preset(preset: dict) -> ScrapeResult:
    """
    Scrape all pages for a given search preset.

    preset is a dict with keys matching the search_presets table columns.
    """
    start_time = time.monotonic()
    listings: list[ScrapedListing] = []
    errors: list[str] = []
    pages_scraped = 0
    was_blocked = False
    category = preset.get("category", "rent")

    log = logger.bind(preset_id=preset.get("id"), preset_name=preset.get("name"))
    log.info("scraper.starting")

    with cf_requests.Session(impersonate="chrome") as session:
        session.headers.update(HEADERS)

        page = 1
        last_page = 1

        while page <= min(last_page, settings.scrape_max_pages):
            params = _build_params(preset, page=page)

            try:
                response = session.get(
                    YAD2_FEED_URL,
                    params=params,
                    timeout=settings.scrape_request_timeout,
                )
            except Exception as exc:
                err = f"Page {page} request failed: {exc}"
                log.warning("scraper.request_error", error=err)
                errors.append(err)
                break

            if _is_blocked(response):
                log.warning("scraper.blocked", status=response.status_code, page=page)
                was_blocked = True
                break

            if response.status_code != 200:
                err = f"Page {page} returned HTTP {response.status_code}"
                log.warning("scraper.bad_status", status=response.status_code, page=page)
                errors.append(err)
                break

            try:
                data = response.json()
            except Exception as exc:
                err = f"Page {page} JSON parse error: {exc}"
                log.warning("scraper.json_error", error=err, page=page)
                errors.append(err)
                break

            feed = data.get("feed", {})
            feed_items = feed.get("feed_items", [])

            if not feed_items:
                log.info("scraper.empty_page", page=page)
                break

            # Parse pagination
            pagination = data.get("pagination", {})
            last_page = pagination.get("last_page", 1)

            page_listings = []
            for item in feed_items:
                listing = _parse_listing(item, category=category)
                if listing:
                    page_listings.append(listing)

            listings.extend(page_listings)
            pages_scraped += 1

            log.info(
                "scraper.page_done",
                page=page,
                last_page=last_page,
                page_count=len(page_listings),
                total_so_far=len(listings),
            )

            page += 1

            # Rate limit between pages
            if page <= min(last_page, settings.scrape_max_pages):
                delay = random.uniform(
                    settings.scrape_page_delay_min, settings.scrape_page_delay_max
                )
                await asyncio.sleep(delay)

    duration = time.monotonic() - start_time
    log.info(
        "scraper.finished",
        listings=len(listings),
        pages=pages_scraped,
        blocked=was_blocked,
        duration=round(duration, 2),
    )

    return ScrapeResult(
        listings=listings,
        pages_scraped=pages_scraped,
        was_blocked=was_blocked,
        errors=errors,
        duration_seconds=round(duration, 2),
    )
