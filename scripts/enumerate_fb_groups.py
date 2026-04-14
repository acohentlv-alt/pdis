"""
Enumerate all Facebook groups you are a member of, using your stored FB session.

Produces fb_groups_discovered.json in the script directory, suitable for
import via scripts/seed_fb_groups.py.

WARNING: Do NOT run while VM scraper is active — two-IP simultaneous login = ban risk.

Usage:
    python3 scripts/enumerate_fb_groups.py

Requires: playwright (pip install playwright && playwright install chromium)
Reads:    vm-scraper/fb_state.json  (your stored FB session from export_fb_cookies.py)
Writes:   scripts/fb_groups_discovered.json
"""

import json
import pathlib
import random
import re
import time
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
STATE_FILE = SCRIPT_DIR.parent / "vm-scraper" / "fb_state.json"
OUTPUT_FILE = SCRIPT_DIR / "fb_groups_discovered.json"


def _extract_group_id(href: str) -> str | None:
    """Extract numeric or slug group ID from a Facebook groups URL."""
    # Normalise: strip query strings and trailing slashes
    path = urlparse(href).path.rstrip("/")
    # Match /groups/<id> or /groups/<id>/anything
    m = re.search(r"/groups/([^/?#]+)", path)
    if not m:
        return None
    gid = m.group(1)
    # Skip generic navigation anchors
    if gid in ("feed", "discover", "create", "joins", "notifications"):
        return None
    return gid


def main():
    if not STATE_FILE.exists():
        print(f"ERROR: fb_state.json not found at {STATE_FILE}")
        print("Run export_fb_cookies.py on the VM first to capture your session.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(storage_state=str(STATE_FILE))
        page = ctx.new_page()

        page.goto("https://m.facebook.com/groups/?nav_source=tab", timeout=30000)
        time.sleep(2.0)

        print(
            "\nOpened your FB groups list. Confirm your groups are visible, then press Enter "
            "to begin scrolling. If the page looks wrong, navigate to your groups list manually "
            "first, then press Enter."
        )
        input()

        seen: dict[str, dict] = {}

        def _collect():
            for el in page.query_selector_all('a[href*="/groups/"]'):
                try:
                    href = el.get_attribute("href") or ""
                    gid = _extract_group_id(href)
                    if not gid or gid in seen:
                        continue
                    name = (el.inner_text() or "").strip()
                    if not name:
                        continue
                    # Build canonical full URL
                    full_url = f"https://www.facebook.com/groups/{gid}"
                    seen[gid] = {"group_id": gid, "name": name, "url": full_url}
                except Exception:
                    pass

        _collect()

        for i in range(10):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            pause = random.uniform(1.5, 3.0)
            time.sleep(pause)
            _collect()
            print(f"  Scroll {i + 1}/10 — {len(seen)} groups found so far")

        browser.close()

    groups = list(seen.values())

    if not groups:
        print(
            f"No groups found. Check current URL: {page.url} and page title: {page.title()}. "
            "Try navigating manually before rerunning."
        )
        return

    OUTPUT_FILE.write_text(json.dumps(groups, ensure_ascii=False, indent=2))
    print(f"\nDone. Found {len(groups)} groups. Written to {OUTPUT_FILE}")
    print("Next step: run scripts/seed_fb_groups.py to import into the database.")


if __name__ == "__main__":
    main()
