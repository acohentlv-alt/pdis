"""Madlan.co.il scraper — GraphQL API with PerimeterX."""
import asyncio
import random
import time

import structlog
from curl_cffi import requests as cf_requests

from pdis.config import settings
from pdis.models import ScrapedListing, ScrapeResult

logger = structlog.get_logger(__name__)

MADLAN_API_URL = "https://www.madlan.co.il/api3"
MADLAN_HOME_URL = "https://www.madlan.co.il"
MADLAN_IMAGE_BASE = "https://images2.madlan.co.il"
PAGE_SIZE = 200

GRAPHQL_QUERY = """
query($sq: SearchBulletinQueryInput!) {
  searchBulletinWithUserPreferences(searchQuery: $sq) {
    total
    offset
    bulletins {
      id price currency beds area floor floors
      address description dealType
      firstTimeSeen availableDate
      locationPoint { lat lng }
      addressDetails {
        city streetName streetNumber neighbourhood
      }
      amenities {
        elevator airConditioner furnished unitPetsAllowed
        patio terrace garage
      }
      parking sellerType generalCondition
      images { imageUrl }
    }
  }
}
"""


def _init_session() -> cf_requests.Session:
    """Create curl_cffi session and visit homepage to get PX cookie.

    Retries up to 3 times if homepage returns non-200 (PerimeterX challenge).
    The API may still work without the cookie, so we proceed regardless.
    """
    session = cf_requests.Session(impersonate="chrome")
    for attempt in range(3):
        try:
            r = session.get(MADLAN_HOME_URL, timeout=settings.madlan_request_timeout)
            if r.status_code == 200:
                logger.info("madlan.session_ready", attempt=attempt + 1)
                break
            logger.warning("madlan.homepage_non200", status=r.status_code, attempt=attempt + 1)
        except Exception as exc:
            logger.warning("madlan.homepage_fetch_failed", error=str(exc), attempt=attempt + 1)
        import time
        time.sleep(2)
    return session


def _build_variables(preset: dict, offset: int) -> dict:
    """Build GraphQL variables dict from preset params.

    Note: Madlan's API has limited server-side filtering.
    We filter by deal_type only, then filter by city/price/rooms in Python.
    """
    attributes = [
        {
            "operator": "EQUAL",
            "field": "deal_type",
            "intent": "MUST",
            "value": "unitRent" if preset.get("category", "rent") == "rent" else "unitSale",
        }
    ]

    # Note: city filtering is done in Python (post-fetch) because Madlan's
    # API location filter requires fields we don't have. We fetch all listings
    # and filter by city name in _matches_city().
    return {
        "sq": {
            "offset": offset,
            "limit": PAGE_SIZE,
            "userPreferences": {
                "location": [],
                "attributes": attributes,
            },
        }
    }


def _parse_floor(raw) -> int | None:
    """Parse floor value to int. 'ground' or equivalent maps to 0."""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    s = str(raw).strip().lower()
    if s in ("ground", "קרקע", "0"):
        return 0
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _parse_madlan_listing(bulletin: dict, category: str) -> ScrapedListing | None:
    """Map a Madlan bulletin dict to a ScrapedListing."""
    bid = bulletin.get("id")
    if not bid:
        return None

    yad2_id = f"madlan_{bid}"

    addr = bulletin.get("addressDetails") or {}
    amenities = bulletin.get("amenities") or {}
    poc = bulletin.get("poc") or {}

    # Coordinates
    loc = bulletin.get("locationPoint") or {}
    latitude: float | None = None
    longitude: float | None = None
    try:
        if loc.get("lat") is not None:
            latitude = float(loc["lat"])
        if loc.get("lng") is not None:
            longitude = float(loc["lng"])
    except (ValueError, TypeError):
        pass

    # Price — Madlan returns NIS, we store as ILS
    price: int | None = None
    raw_price = bulletin.get("price")
    if raw_price is not None:
        try:
            price = int(raw_price)
        except (ValueError, TypeError):
            pass

    # Rooms from "beds"
    rooms: float | None = None
    raw_beds = bulletin.get("beds")
    if raw_beds is not None:
        try:
            rooms = float(raw_beds)
        except (ValueError, TypeError):
            pass

    # Area
    square_meters: int | None = None
    raw_area = bulletin.get("area")
    if raw_area is not None:
        try:
            square_meters = int(raw_area)
        except (ValueError, TypeError):
            pass

    floor = _parse_floor(bulletin.get("floor"))

    total_floors: int | None = None
    raw_floors = bulletin.get("floors")
    if raw_floors is not None:
        try:
            total_floors = int(raw_floors)
        except (ValueError, TypeError):
            pass

    # Property type — map Madlan types to English
    property_type = bulletin.get("propertyType") or None

    # Amenities booleans
    elevator = bool(amenities.get("elevator"))
    air_conditioning = bool(amenities.get("airConditioner"))
    furnished = bool(amenities.get("furnished"))
    pets_allowed = bool(amenities.get("unitPetsAllowed"))

    # Parking: numeric field or garage amenity
    parking_val = bulletin.get("parking")
    garage_val = amenities.get("garage")
    parking = (isinstance(parking_val, (int, float)) and parking_val > 0) or bool(garage_val)

    # Balcony: patio, terrace or balconyArea > 0
    balcony_area = bulletin.get("balconyArea") or 0
    balcony = (
        bool(amenities.get("patio"))
        or bool(amenities.get("terrace"))
        or (isinstance(balcony_area, (int, float)) and balcony_area > 0)
    )

    renovated = bulletin.get("generalCondition") == "renovated"

    is_agent = bulletin.get("sellerType") == "agent"

    # Contact info — poc can be AgentPoc or UserPoc
    contact_name: str | None = None
    contact_phone: str | None = poc.get("displayNumber") or None
    agent_office: str | None = None

    agent_contact = poc.get("agentContact") or {}
    contact_info = poc.get("contactInfo") or {}

    if agent_contact.get("name"):
        contact_name = agent_contact["name"]
    elif contact_info.get("name"):
        contact_name = contact_info["name"]

    if poc.get("company"):
        agent_office = poc["company"]

    # Image URLs
    image_urls: list[str] = []
    for img in bulletin.get("images") or []:
        url = img.get("imageUrl") or ""
        if not url:
            continue
        if url.startswith("http"):
            image_urls.append(url)
        else:
            image_urls.append(f"{MADLAN_IMAGE_BASE}/{url.lstrip('/')}")

    # Listing URL
    listing_url = bulletin.get("url") or ""

    # Dates
    yad2_date_added: str | None = None
    first_seen_raw = bulletin.get("firstTimeSeen")
    if first_seen_raw:
        try:
            yad2_date_added = str(first_seen_raw)[:10]
        except Exception:
            pass

    move_in_date: str | None = None
    avail_raw = bulletin.get("availableDate")
    if avail_raw:
        try:
            move_in_date = str(avail_raw)[:10]
        except Exception:
            pass

    # Address
    address_street = addr.get("streetName") or bulletin.get("address") or None
    address_home_number = str(addr["streetNumber"]) if addr.get("streetNumber") is not None else None
    address_city = addr.get("city") or None
    neighborhood = addr.get("neighbourhood") or None

    # customer_id
    agent_id = bulletin.get("agentId")
    office_id = bulletin.get("officeId")
    raw_cid = agent_id or office_id
    customer_id = str(raw_cid) if raw_cid is not None else None
    if customer_id == "":
        customer_id = None

    return ScrapedListing(
        yad2_id=yad2_id,
        category=category,
        address_street=address_street,
        address_home_number=address_home_number,
        address_city=address_city,
        neighborhood=neighborhood,
        rooms=rooms,
        floor=floor,
        total_floors=total_floors,
        square_meters=square_meters,
        price=price,
        currency="ILS",
        property_type=property_type,
        description=bulletin.get("description") or None,
        contact_name=contact_name,
        contact_phone=contact_phone,
        yad2_date_added=yad2_date_added,
        source="madlan",
        latitude=latitude,
        longitude=longitude,
        parking=parking,
        elevator=elevator,
        safe_room=False,
        renovated=renovated,
        balcony=balcony,
        pets_allowed=pets_allowed,
        furnished=furnished,
        air_conditioning=air_conditioning,
        is_agent=is_agent,
        agent_office=agent_office,
        move_in_date=move_in_date,
        hood_id=None,
        customer_id=customer_id,
        accessibility=False,
        image_urls=image_urls,
        listing_url=listing_url,
        raw_data=bulletin,
    )


def _matches_city(bulletin: dict, target_city: str) -> bool:
    """Return True if the bulletin's city matches target_city (normalized)."""
    addr = bulletin.get("addressDetails") or {}
    city = addr.get("city") or ""

    def _normalize(s: str) -> str:
        return s.strip().replace("-", " ")

    return _normalize(city) == _normalize(target_city)


def _is_blocked(response: cf_requests.Response) -> bool:
    """Check if PerimeterX or another anti-bot system blocked the request."""
    if response.status_code in (403, 429):
        return True
    try:
        body = response.text.lower()
        if "challenge" in body or "perimeterx" in body or "_pxvid" in body:
            return True
    except Exception:
        pass
    return False


async def scrape_madlan_preset(preset: dict) -> ScrapeResult:
    """
    Scrape all pages for a Madlan preset via GraphQL API.

    preset is a dict with keys matching the search_presets table columns.
    """
    start_time = time.monotonic()
    listings: list[ScrapedListing] = []
    errors: list[str] = []
    pages_scraped = 0
    was_blocked = False
    category = preset.get("category", "rent")

    log = logger.bind(preset_id=preset.get("id"), preset_name=preset.get("name"))
    log.info("madlan.scraper.starting")

    extra = preset.get("extra_params") or {}
    if isinstance(extra, str):
        import json as _json
        extra = _json.loads(extra)

    target_city: str | None = extra.get("madlan_city")
    min_price = preset.get("min_price")
    max_price = preset.get("max_price")
    min_rooms = preset.get("min_rooms")
    max_rooms = preset.get("max_rooms")

    max_pages = settings.scrape_max_pages

    session = _init_session()

    try:
        offset = 0
        total = PAGE_SIZE  # will be updated after first response

        while offset < total and pages_scraped < max_pages:
            variables = _build_variables(preset, offset)

            try:
                response = session.post(
                    MADLAN_API_URL,
                    json={"query": GRAPHQL_QUERY, "variables": variables},
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "Referer": f"{MADLAN_HOME_URL}/",
                        "Origin": MADLAN_HOME_URL,
                    },
                    timeout=settings.madlan_request_timeout,
                )
            except Exception as exc:
                err = f"Offset {offset} request failed: {exc}"
                log.warning("madlan.request_error", error=err)
                errors.append(err)
                break

            if _is_blocked(response):
                log.warning("madlan.blocked", status=response.status_code, offset=offset)
                was_blocked = True
                break

            if response.status_code != 200:
                err = f"Offset {offset} returned HTTP {response.status_code}"
                log.warning("madlan.bad_status", status=response.status_code, offset=offset,
                            body=response.text[:300])
                errors.append(err)
                break

            try:
                data = response.json()
            except Exception as exc:
                err = f"Offset {offset} JSON parse error: {exc}"
                log.warning("madlan.json_error", error=err)
                errors.append(err)
                break

            # Check for GraphQL errors
            if "errors" in data:
                gql_errors = data["errors"]
                log.warning("madlan.graphql_errors", errors=gql_errors, offset=offset)
                errors.append(f"GraphQL errors at offset {offset}: {gql_errors}")
                # Don't crash — continue to next offset or stop if no data
                break

            search_data = (data.get("data") or {}).get("searchBulletinWithUserPreferences") or {}
            total = search_data.get("total") or 0
            bulletins = search_data.get("bulletins") or []

            if not bulletins:
                log.info("madlan.empty_page", offset=offset)
                break

            page_listings = []
            for bulletin in bulletins:
                # Filter by city if target_city is specified
                if target_city and not _matches_city(bulletin, target_city):
                    continue

                # Filter by price range (server-side filtering is unreliable)
                b_price = bulletin.get("price")
                if b_price is not None:
                    if min_price is not None and b_price < min_price:
                        continue
                    if max_price is not None and b_price > max_price:
                        continue

                # Filter by room range
                b_rooms = bulletin.get("beds")
                if b_rooms is not None:
                    if min_rooms is not None and b_rooms < min_rooms:
                        continue
                    if max_rooms is not None and b_rooms > max_rooms:
                        continue

                listing = _parse_madlan_listing(bulletin, category)
                if listing:
                    page_listings.append(listing)

            listings.extend(page_listings)
            pages_scraped += 1

            log.info(
                "madlan.page_done",
                offset=offset,
                total=total,
                page_count=len(page_listings),
                total_so_far=len(listings),
            )

            offset += PAGE_SIZE

            # Rate limit between pages
            if offset < total and pages_scraped < max_pages:
                delay = random.uniform(settings.madlan_delay_min, settings.madlan_delay_max)
                await asyncio.sleep(delay)

    finally:
        session.close()

    duration = time.monotonic() - start_time
    log.info(
        "madlan.scraper.finished",
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
