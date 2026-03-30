from dataclasses import dataclass, field


@dataclass
class ScrapedListing:
    yad2_id: str
    category: str
    address_street: str | None
    address_city: str | None
    neighborhood: str | None
    rooms: float | None
    floor: int | None
    total_floors: int | None
    square_meters: int | None
    price: int | None
    currency: str
    property_type: str | None
    description: str | None
    contact_name: str | None
    contact_phone: str | None
    image_urls: list[str] = field(default_factory=list)
    listing_url: str = ""
    raw_data: dict = field(default_factory=dict)


@dataclass
class ScrapeResult:
    listings: list[ScrapedListing] = field(default_factory=list)
    pages_scraped: int = 0
    was_blocked: bool = False
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
