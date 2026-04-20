#!/usr/bin/env python3
"""Read-only probe: sample ~20 Madlan listings for TLV and dump all raw fields.

Run standalone — no PDIS server required. Requires PDIS database + curl_cffi.

Usage:
  cd ~/pdis
  python scripts/madlan_field_probe.py

Output goes to stdout. Useful for discovering which sqm-related fields Madlan
returns (area, terrace, patio, etc.) so we can decide how to split net/balcony
in the Madlan scraper.
"""
import json
import sys
import os
import time

# Add project root to path so pdis modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

try:
    from curl_cffi import requests as cf_requests
except ImportError:
    print("ERROR: curl_cffi not installed. Run: pip install curl_cffi", file=sys.stderr)
    sys.exit(1)

MADLAN_API_URL = "https://www.madlan.co.il/api3"
MADLAN_HOME_URL = "https://www.madlan.co.il"

# Expanded GraphQL query — requests all known fields including area sub-fields
PROBE_QUERY = """
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
        __typename
      }
      parking sellerType generalCondition
      images { imageUrl }
      buildingYear
      poc {
        __typename
        ... on AgentPoc {
          displayNumber
          company
          agentContact { name }
        }
        ... on UserPoc {
          displayNumber
          contactInfo { name }
        }
      }
    }
  }
}
"""

TLV_VARIABLES = {
    "sq": {
        "dealType": "RENT",
        "pageSize": 20,
        "offset": 0,
        "bbox": {
            "topLeft": {"lat": 32.12, "lng": 34.74},
            "bottomRight": {"lat": 32.03, "lng": 34.84},
        },
    }
}


def get_px_cookie() -> str | None:
    """Fetch a PerimeterX cookie by visiting the Madlan homepage."""
    try:
        resp = cf_requests.get(
            MADLAN_HOME_URL,
            impersonate="chrome120",
            timeout=30,
        )
        cookie = resp.cookies.get("_px3") or resp.cookies.get("_px2") or resp.cookies.get("_pxvid")
        if cookie:
            print(f"Got PX cookie (_px3/_px2/_pxvid present)", file=sys.stderr)
        else:
            print("WARN: no PX cookie found — request may be blocked", file=sys.stderr)
        return cookie
    except Exception as exc:
        print(f"WARN: could not fetch PX cookie: {exc}", file=sys.stderr)
        return None


def probe() -> None:
    print("Fetching Madlan homepage for PX cookie...", file=sys.stderr)
    get_px_cookie()
    time.sleep(1)

    print(f"Querying Madlan GraphQL for ~20 TLV rent listings...", file=sys.stderr)
    try:
        resp = cf_requests.post(
            MADLAN_API_URL,
            json={"query": PROBE_QUERY, "variables": TLV_VARIABLES},
            headers={"Content-Type": "application/json", "Referer": MADLAN_HOME_URL},
            impersonate="chrome120",
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"ERROR fetching Madlan: {exc}", file=sys.stderr)
        sys.exit(1)

    bulletins = (
        data.get("data", {})
        .get("searchBulletinWithUserPreferences", {})
        .get("bulletins", [])
    )
    total = (
        data.get("data", {})
        .get("searchBulletinWithUserPreferences", {})
        .get("total", "?")
    )

    print(f"\nTotal available: {total}, fetched: {len(bulletins)}", file=sys.stderr)
    print(f"\n{'='*80}", flush=True)
    print(f"RAW FIELD DUMP — {len(bulletins)} Madlan listings", flush=True)
    print(f"{'='*80}\n", flush=True)

    for i, b in enumerate(bulletins, 1):
        print(f"--- Listing {i} (id={b.get('id')}) ---")
        print(json.dumps(b, indent=2, ensure_ascii=False))
        print()


if __name__ == "__main__":
    probe()
