#!/usr/bin/env python3
"""
PDIS Facebook Groups scraper.
Scrapes 5 TLV rental FB groups via Playwright using a personal account's stored cookies.
POSTs parsed posts to the PDIS ingest endpoint on Render.

Run via run.sh (which handles probation mode and proxy check) or directly for testing.

PROXY_URL env var is required in production — personal FB account on a datacenter IP = ban.

IMPORTANT — Step 0b deferred: The m.facebook.com DOM selectors used here
(h3 a, abbr/time, [data-testid="post_message"], div[dir="auto"]) were specified in
the brief but have NOT been verified against a live FB session.
Verify these selectors before flipping FB_INGESTION_ENABLED=true.
"""

import json
import logging
import os
import pathlib
import random
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page

load_dotenv()

INGEST_SECRET = os.environ["INGEST_SECRET"]
PDIS_API_URL = os.environ.get("PDIS_API_URL", "https://pdis-lsah.onrender.com")
PROXY_URL = os.environ.get("PROXY_URL", "")

SCRIPT_DIR = pathlib.Path(__file__).parent
STATE_FILE = SCRIPT_DIR / "state.json"
CONSECUTIVE_EMPTY_FILE = SCRIPT_DIR / ".consecutive_empty"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ── Proxy config ─────────────────────────────────────────────────────────────

def _build_proxy_config(proxy_url: str) -> dict | None:
    """
    Parse PROXY_URL into a Playwright proxy config dict.
    Returns None if proxy_url is empty (local dev / testing only).
    Format: http://username:password@host:port
    """
    if not proxy_url:
        return None
    parsed = urlparse(proxy_url)
    cfg: dict = {
        "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
    }
    if parsed.username:
        cfg["username"] = parsed.username
    if parsed.password:
        cfg["password"] = parsed.password
    return cfg


# ── Hebrew relative time parser ──────────────────────────────────────────────

def _parse_hebrew_relative_time(text: str) -> str | None:
    """
    Parse Hebrew relative time strings into ISO 8601 UTC timestamps.
    Returns None if unparseable.

    Patterns handled:
      לפני X דקות      → now − X minutes
      לפני שעה          → now − 1 hour
      לפני שעתיים       → now − 2 hours
      לפני X שעות       → now − X hours
      אתמול             → yesterday 12:00 local (approximated as UTC)
      לפני X ימים       → now − X days
      לפני שבוע         → now − 7 days
      לפני X שבועות     → now − X*7 days
    """
    now = datetime.now(timezone.utc)
    t = text.strip()

    # X minutes
    m = re.search(r"לפני\s+(\d+)\s+דקות", t)
    if m:
        return (now - timedelta(minutes=int(m.group(1)))).isoformat()

    # 1 hour
    if "לפני שעה" in t and "שעתיים" not in t and "שעות" not in t:
        return (now - timedelta(hours=1)).isoformat()

    # 2 hours
    if "לפני שעתיים" in t:
        return (now - timedelta(hours=2)).isoformat()

    # X hours
    m = re.search(r"לפני\s+(\d+)\s+שעות", t)
    if m:
        return (now - timedelta(hours=int(m.group(1)))).isoformat()

    # Yesterday
    if "אתמול" in t:
        yesterday = now - timedelta(days=1)
        return yesterday.replace(hour=12, minute=0, second=0, microsecond=0).isoformat()

    # X days
    m = re.search(r"לפני\s+(\d+)\s+ימים", t)
    if m:
        return (now - timedelta(days=int(m.group(1)))).isoformat()

    # 1 week
    if "לפני שבוע" in t and "שבועות" not in t:
        return (now - timedelta(weeks=1)).isoformat()

    # X weeks
    m = re.search(r"לפני\s+(\d+)\s+שבועות", t)
    if m:
        return (now - timedelta(weeks=int(m.group(1)))).isoformat()

    return None


# ── Text extraction helpers ──────────────────────────────────────────────────

_PRICE_RE = re.compile(r"(\d[\d,]*)\s*(?:₪|ש[\"״]ח|שקל)")
_ROOMS_RE = re.compile(r"(\d(?:\.\d)?)\s*חדר")
_PHONE_RE = re.compile(r"0(?:5[0-9]|[23489])-?\d{3,4}-?\d{4}")
_BROKER_KEYWORDS = ("תיווך", "מתווך", "סוכן")
_SKIP_KEYWORDS = ("מחפש שותף", "מחפשת שותף", "שותף לדירה")

# Square-meters extraction — Hebrew and English patterns
# e.g. "דירה 80 מ"ר", "דירה 80 מטר", "80 sqm", "80 sq m", "80 m²"
_SQM_HE_QUOTED_RE = re.compile(r"(\d{2,3})\s*מ[\"״]ר")       # 80 מ"ר
_SQM_HE_METER_RE = re.compile(r"(\d{2,3})\s*מטר")             # 80 מטר
_SQM_EN_RE = re.compile(r"(\d{2,3})\s*(?:sqm|sq\.?\s*m|m\^?2|m²|square\s*met)", re.IGNORECASE)
_SQM_MIN = 20
_SQM_MAX = 500


def _extract_sqm(text: str) -> int | None:
    """Extract square metres from Hebrew/English listing text. Returns None if not found."""
    for pattern in (_SQM_HE_QUOTED_RE, _SQM_HE_METER_RE, _SQM_EN_RE):
        m = pattern.search(text)
        if m:
            try:
                val = int(m.group(1))
                if _SQM_MIN <= val <= _SQM_MAX:
                    return val
            except ValueError:
                pass
    return None
_NEIGHBORHOOD_RE = re.compile(
    r"(?:ב|ב-|בשכונת\s+)"
    r"([\u05D0-\u05EA][\u05D0-\u05EA\s]{2,20})"
    r"(?:\s*,|\s*\.|\s+\d|\s*$)"
)


def _extract_price(text: str) -> int | None:
    m = _PRICE_RE.search(text)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _extract_rooms(text: str) -> float | None:
    m = _ROOMS_RE.search(text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def _extract_phone(text: str) -> str | None:
    m = _PHONE_RE.search(text)
    return m.group(0) if m else None


def _is_agent(text: str) -> bool:
    # "ללא תיווך" (without broker) is a private-listing signal — must not match.
    # Strip those phrases before checking for broker keywords.
    cleaned = text.replace("ללא תיווך", "").replace("לא תיווך", "")
    return any(kw in cleaned for kw in _BROKER_KEYWORDS)


def _should_skip(text: str) -> bool:
    """Return True for roommate-wanted posts and other non-rental posts."""
    return any(kw in text for kw in _SKIP_KEYWORDS)


def _extract_neighborhood(text: str) -> str | None:
    m = _NEIGHBORHOOD_RE.search(text)
    return m.group(1).strip() if m else None


# ── Per-post parsing ─────────────────────────────────────────────────────────

def _parse_post(post_el, group_id: str, group_url: str) -> dict | None:
    """
    Parse a single FB post element into a dict suitable for the ingest API.
    Returns None if the post should be skipped.

    NOTE (Step 0b deferred): Selectors below are based on m.facebook.com mobile DOM
    as described in the brief. They must be verified against a live FB session before
    enabling FB_INGESTION_ENABLED=true.
    """
    try:
        # Author name from h3 a
        author_el = post_el.query_selector("h3 a")
        author_name = author_el.inner_text().strip() if author_el else None

        # Timestamp from abbr or time element
        time_el = post_el.query_selector("abbr") or post_el.query_selector("time")
        posted_at = None
        if time_el:
            # Try datetime attribute first
            dt_attr = time_el.get_attribute("datetime") or time_el.get_attribute("data-utime")
            if dt_attr:
                posted_at = dt_attr
            else:
                raw_time = time_el.inner_text().strip()
                posted_at = _parse_hebrew_relative_time(raw_time)

        # Post text — prefer data-testid="post_message", fall back to dir="auto" divs
        msg_el = post_el.query_selector('[data-testid="post_message"]')
        if not msg_el:
            msg_el = post_el.query_selector('div[dir="auto"]')
        description = msg_el.inner_text().strip() if msg_el else ""

        if not description:
            return None

        if _should_skip(description):
            return None

        # Permalink — find an anchor whose href contains /permalink/ or /posts/
        permalink_el = post_el.query_selector('a[href*="/permalink/"], a[href*="/posts/"]')
        listing_url = ""
        post_id = ""
        if permalink_el:
            href = permalink_el.get_attribute("href") or ""
            # Normalise to m.facebook.com URL
            if href.startswith("/"):
                href = f"https://m.facebook.com{href}"
            listing_url = href.split("?")[0]
            # Extract numeric post ID from URL
            id_match = re.search(r"/(?:permalink|posts)/(\d+)", listing_url)
            if id_match:
                post_id = id_match.group(1)

        if not post_id:
            # Fall back to a hash of author + description snippet
            post_id = str(abs(hash(f"{author_name}:{description[:80]}")))

        # Images — scontent CDN only
        image_urls = []
        for img in post_el.query_selector_all('img[src*="scontent"]'):
            src = img.get_attribute("src")
            if src and src not in image_urls:
                image_urls.append(src)

        price = _extract_price(description)
        rooms = _extract_rooms(description)
        sqm = _extract_sqm(description)
        phone = _extract_phone(description)
        neighborhood = _extract_neighborhood(description)
        is_agent_flag = _is_agent(description)

        # Skip posts with no price and no phone (likely not a real rental ad)
        if price is None and phone is None:
            return None

        return {
            "post_id": post_id,
            "group_url": group_url,
            "group_id": group_id,
            "author_name": author_name,
            "posted_at": posted_at,
            "description": description,
            "contact_phone": phone,
            "price": price,
            "rooms": rooms,
            "square_meters": sqm,
            "neighborhood": neighborhood,
            "address_city": None,  # resolved server-side from group_id
            "image_urls": image_urls,
            "like_count": None,
            "listing_url": listing_url,
            "is_agent": is_agent_flag,
        }
    except Exception as exc:
        log.warning("parse_post_error: %s", exc)
        return None


# ── Per-group scraping ───────────────────────────────────────────────────────

def _scrape_group(page: Page, group_id: str) -> list[dict]:
    """Scrape a single FB group — 3 to 5 scrolls with human-like pauses."""
    slug = group_id  # group IDs can be numeric or slug
    url = f"https://m.facebook.com/groups/{slug}"
    log.info("scraping group %s → %s", group_id, url)

    page.goto(url, timeout=30000)
    time.sleep(random.uniform(2.0, 4.0))

    posts_seen: set[str] = set()
    results: list[dict] = []

    num_scrolls = random.randint(3, 5)
    for scroll_n in range(num_scrolls):
        # Mouse movement between scrolls to appear human
        page.mouse.move(random.randint(100, 800), random.randint(100, 600))
        time.sleep(random.uniform(0.3, 0.7))

        # Scroll down
        page.evaluate("window.scrollBy(0, window.innerHeight * 1.5)")
        time.sleep(random.uniform(2.0, 5.0))

        # Parse visible post elements
        # NOTE (Step 0b deferred): selector "article" may need adjustment for m.facebook.com
        post_elements = page.query_selector_all("article")
        if not post_elements:
            # Fallback: try role=article
            post_elements = page.query_selector_all('[role="article"]')

        for el in post_elements:
            parsed = _parse_post(el, group_id, url)
            if parsed and parsed["post_id"] not in posts_seen:
                posts_seen.add(parsed["post_id"])
                results.append(parsed)

        log.info("scroll %d/%d: %d posts so far", scroll_n + 1, num_scrolls, len(results))

    log.info("group %s done: %d posts", group_id, len(results))
    return results


# ── Consecutive-empty counter ────────────────────────────────────────────────

def _read_consecutive_empty() -> int:
    try:
        return int(CONSECUTIVE_EMPTY_FILE.read_text().strip())
    except Exception:
        return 0


def _write_consecutive_empty(n: int) -> None:
    CONSECUTIVE_EMPTY_FILE.write_text(str(n))


def _send_alert(msg: str) -> None:
    """Send a mail alert. Uses the system `mail` command if available."""
    import subprocess
    try:
        subprocess.run(
            ["mail", "-s", "PDIS FB Scraper Alert", "root"],
            input=msg.encode(),
            timeout=10,
            check=False,
        )
    except Exception as exc:
        log.warning("mail alert failed: %s", exc)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    # Proxy check — mandatory for production (personal account on datacenter IP = ban)
    proxy_config = _build_proxy_config(PROXY_URL)
    if not proxy_config:
        log.warning(
            "WARN: No PROXY_URL set — running without residential proxy. "
            "Account ban risk elevated."
        )
    else:
        log.info("proxy configured: server=%s", proxy_config["server"])

    if not STATE_FILE.exists():
        log.error("state.json not found at %s — run export_fb_cookies.py first", STATE_FILE)
        raise SystemExit(1)

    r = httpx.get(f"{PDIS_API_URL}/api/fb-groups/active", timeout=30)
    r.raise_for_status()
    groups = r.json()["groups"]
    if not groups:
        log.warning("no active FB groups returned by API — nothing to scrape")
        return

    all_posts: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            proxy=proxy_config,  # None is acceptable for local dev
        )
        ctx = browser.new_context(storage_state=str(STATE_FILE))
        page = ctx.new_page()

        for i, group in enumerate(groups):
            if i > 0:
                delay = random.uniform(30, 90)
                log.info("waiting %.0fs before next group", delay)
                time.sleep(delay)

            gid = group.get("group_id") or group["id"]
            posts = _scrape_group(page, gid)
            all_posts.extend(posts)

        browser.close()

    log.info("posts_found=%d", len(all_posts))

    # Consecutive-empty tracking
    if len(all_posts) == 0:
        n = _read_consecutive_empty() + 1
        _write_consecutive_empty(n)
        log.warning("consecutive_empty_runs=%d", n)
        if n >= 3:
            _send_alert(f"PDIS FB scraper: {n} consecutive runs with 0 posts found. Check FB login.")
    else:
        _write_consecutive_empty(0)

    if not all_posts:
        log.info("no posts to send, exiting")
        return

    # POST to PDIS ingest endpoint
    payload = {"posts": all_posts}
    headers = {
        "Authorization": f"Bearer {INGEST_SECRET}",
        "Content-Type": "application/json",
    }
    url = f"{PDIS_API_URL}/api/ingest/facebook"
    log.info("posting %d posts to %s", len(all_posts), url)

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        log.info("ingest response: %s", resp.json())
    except Exception as exc:
        log.error("ingest POST failed: %s", exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
