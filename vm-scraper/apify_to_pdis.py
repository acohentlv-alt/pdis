#!/usr/bin/env python3
"""One-shot: fetch Apify dataset of FB posts, map to PDIS FacebookPost schema,
POST in small batches to the ingest endpoint. Optional Claude Haiku parsing
if ANTHROPIC_API_KEY is set.
"""
import os
import re
import sys
import json
import time
import httpx

_LLM_ENABLED = bool(os.environ.get("ANTHROPIC_API_KEY"))
if _LLM_ENABLED:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from llm_parse import parse_post as llm_parse_post, estimate_cost as llm_estimate_cost
    from anthropic import Anthropic
    _llm_client = Anthropic()
    print(f"LLM parse: ENABLED (Haiku 4.5)", flush=True)
else:
    print(f"LLM parse: disabled (set ANTHROPIC_API_KEY to enable)", flush=True)

APIFY_TOKEN = os.environ["APIFY_TOKEN"]
DATASET_ID = os.environ.get("DATASET_ID")  # if set, skip trigger and reuse existing dataset
PDIS_API_URL = os.environ.get("PDIS_API_URL", "https://pdis-lsah.onrender.com")
INGEST_SECRET = os.environ["INGEST_SECRET"]
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "40"))
RESULTS_PER_GROUP = int(os.environ.get("RESULTS_PER_GROUP", "5"))


def trigger_apify_run() -> str:
    """Trigger a fresh Apify run on all active FB groups; return dataset ID."""
    # Pull group URLs from PDIS
    with httpx.Client(timeout=60) as client:
        r = client.get(f"{PDIS_API_URL}/api/fb-groups/active")
        r.raise_for_status()
        groups = r.json()["groups"]
    start_urls = [{"url": g["url"]} for g in groups]
    print(f"Triggering Apify on {len(start_urls)} groups, resultsLimit={RESULTS_PER_GROUP}", flush=True)
    payload = {
        "startUrls": start_urls,
        "resultsLimit": RESULTS_PER_GROUP,
        "viewOption": "CHRONOLOGICAL",
    }
    with httpx.Client(timeout=60) as client:
        r = client.post(
            "https://api.apify.com/v2/acts/apify~facebook-groups-scraper/runs",
            json=payload,
            headers={"Authorization": f"Bearer {APIFY_TOKEN}"},
        )
        r.raise_for_status()
        run = r.json()["data"]
    run_id = run["id"]
    dataset_id = run["defaultDatasetId"]
    print(f"Apify run {run_id} started; dataset {dataset_id}", flush=True)

    # Poll until done (max ~10 min)
    deadline = time.time() + 600
    with httpx.Client(timeout=60) as client:
        while time.time() < deadline:
            r = client.get(
                f"https://api.apify.com/v2/acts/apify~facebook-groups-scraper/runs/{run_id}",
                headers={"Authorization": f"Bearer {APIFY_TOKEN}"},
            )
            r.raise_for_status()
            status = r.json()["data"]["status"]
            print(f"  apify status={status}", flush=True)
            if status == "SUCCEEDED":
                return dataset_id
            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                raise RuntimeError(f"Apify run ended with status={status}")
            time.sleep(20)
    raise RuntimeError("Apify run did not complete within 10 minutes")

_PRICE_PATTERNS = [
    re.compile(r"(?:מחיר|price)\s*[:\-]?\s*([\d,]+)", re.IGNORECASE),
    re.compile(r"([\d,]{3,})\s*(?:₪|ש[\"״'׳]ח|שח|שקל|שקלים|nis|NIS)"),
    re.compile(r"(?:₪|NIS)\s*([\d,]+)", re.IGNORECASE),
    re.compile(r"([\d,]{4,})\s*(?:לחודש|month|/mo|ל\s*\d+\s*חודשים)"),
]

_SQM_PATTERNS = [
    re.compile(r"(\d{2,4})\s*מ[\"״'׳]?\s*ר"),
    re.compile(r"(\d{2,4})\s*(?:מטר מרובע|מטרים מרובעים|מטר|sqm|m²|m2|SQM)", re.IGNORECASE),
    re.compile(r"(?:שטח|size)\s*[:\-]?\s*(\d{2,4})", re.IGNORECASE),
    re.compile(r"(?:בגודל|בנוי|בגודל של)\s*(?:כ[\-\s]?)?(\d{2,4})"),
]

_ROOMS_RX = re.compile(r"(\d+(?:\.\d+)?)\s*(?:חדרים|חד['׳]?|רום|room)", re.IGNORECASE)
_PHONE_RX = re.compile(r"(05\d)[\s\-\.]?(\d{3,4})[\s\-\.]?(\d{4})")

# TLV neighborhoods — Hebrew canonical → list of Hebrew spelling variants.
# Hit order matters: more specific first (e.g. "הצפון הישן" before "צפון").
_TLV_NEIGHBORHOODS: list[tuple[str, list[str]]] = [
    ("פלורנטין", ["פלורנטין", "פלורינטין"]),
    ("נווה צדק", ["נווה צדק", "נוה צדק"]),
    ("כרם התימנים", ["כרם התימנים", "כרם"]),
    ("לב תל אביב", ["לב תל אביב", "לב העיר"]),
    ("הצפון הישן", ["הצפון הישן", "צפון ישן"]),
    ("הצפון החדש", ["הצפון החדש", "צפון חדש"]),
    ("יפו העתיקה", ["יפו העתיקה", "יפו עתיקה"]),
    ("יפו", ["יפו", "jaffa"]),
    ("שפירא", ["שפירא"]),
    ("שבזי", ["שבזי"]),
    ("נוה אביבים", ["נווה אביבים", "נוה אביבים"]),
    ("רמת אביב", ["רמת אביב"]),
    ("תל ברוך", ["תל ברוך", "תל-ברוך"]),
    ("חובבי ציון", ["חובבי ציון"]),
    ("מונטיפיורי", ["מונטיפיורי", "מונטיפיורי"]),
    ("דיזנגוף", ["דיזנגוף"]),
    ("רוטשילד", ["רוטשילד"]),
    ("בצלאל", ["בצלאל"]),
    ("ביצרון", ["ביצרון"]),
    ("יד אליהו", ["יד אליהו", "יד-אליהו"]),
    ("הרב קוק", ["הרב קוק", "רב קוק"]),
    ("בבלי", ["בבלי"]),
    ("כוכב הצפון", ["כוכב הצפון"]),
    ("אזורי חן", ["אזורי חן"]),
    ("גורדון", ["גורדון"]),
    ("בן יהודה", ["בן יהודה", "בן-יהודה"]),
    ("רבין", ["כיכר רבין", "רבין"]),
    ("נחלת בנימין", ["נחלת בנימין"]),
    ("שוק הכרמל", ["שוק הכרמל", "כרמל"]),
    ("נחלאות", ["נחלאות"]),
    ("מרכז העיר", ["מרכז העיר"]),
    ("הצפון", ["הצפון"]),
]


def extract_neighborhood(text: str):
    """Find the first matching TLV neighborhood in the description.

    Returns canonical name, or None. Matching is case-insensitive for English
    fallbacks. Hebrew substring match is enough since Hebrew lacks articles
    that complicate matching.
    """
    if not text:
        return None
    for canonical, variants in _TLV_NEIGHBORHOODS:
        for v in variants:
            if v in text:
                return canonical
    return None


def extract_price(text: str):
    for rx in _PRICE_PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        try:
            n = int(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if 500 <= n <= 100_000_000:
            return n
    return None


def extract_sqm(text: str):
    for rx in _SQM_PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        try:
            n = int(m.group(1))
        except ValueError:
            continue
        if 15 <= n <= 1000:
            return n
    return None


def extract_rooms(text: str):
    m = _ROOMS_RX.search(text)
    if not m:
        return None
    try:
        r = float(m.group(1))
    except ValueError:
        return None
    if 1.0 <= r <= 10.0:
        return r
    return None


def extract_phone(text: str):
    m = _PHONE_RX.search(text)
    if not m:
        return None
    return m.group(1) + m.group(2) + m.group(3)


def main() -> None:
    dataset_id = DATASET_ID
    if not dataset_id:
        dataset_id = trigger_apify_run()
    print(f"Fetching Apify dataset {dataset_id}...", flush=True)
    with httpx.Client(timeout=120) as client:
        r = client.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            params={"clean": "true", "limit": 2000},
            headers={"Authorization": f"Bearer {APIFY_TOKEN}"},
        )
        r.raise_for_status()
        items = r.json()
    print(f"Got {len(items)} Apify items", flush=True)

    posts: list[dict] = []
    skipped_no_text = 0
    skipped_no_id = 0
    for item in items:
        text = (item.get("text") or "").strip()
        if not text:
            skipped_no_text += 1
            continue
        legacy_id = item.get("legacyId")
        if not legacy_id:
            skipped_no_id += 1
            continue
        fb_url = item.get("facebookUrl") or ""
        group_id = ""
        m = re.search(r"/groups/([^/?]+)", fb_url)
        if m:
            group_id = m.group(1)
        image_urls: list[str] = []
        for att in item.get("attachments") or []:
            thumb = att.get("thumbnail")
            if thumb and thumb.startswith("http") and thumb not in image_urls:
                image_urls.append(thumb)
            if len(image_urls) >= 8:
                break
        author_name = (item.get("user") or {}).get("name")
        _sqm_regex = extract_sqm(text)
        base = {
            "post_id": str(legacy_id),
            "group_url": fb_url,
            "group_id": group_id,
            "author_name": author_name,
            "posted_at": item.get("time"),
            "description": text,
            "contact_phone": extract_phone(text),
            "price": extract_price(text),
            "rooms": extract_rooms(text),
            "sqm_net": _sqm_regex,
            "sqm_balcony": None,
            "intent": None,
            "neighborhood": extract_neighborhood(text),
            "address_city": None,
            "floor": None,
            "intent": None,
            "confidence": None,
            "image_urls": image_urls,
            "like_count": item.get("topReactionsCount") or 0,
            "listing_url": item.get("url") or "",
        }
        posts.append(base)
    print(f"Mapped {len(posts)} posts (skipped no_text={skipped_no_text}, no_id={skipped_no_id})", flush=True)

    def _count(posts_list, keys):
        return {k: sum(1 for p in posts_list if p.get(k) is not None) for k in keys}
    before = _count(posts, ["price", "sqm_net", "rooms", "contact_phone", "neighborhood"])
    print(f"Regex extraction: {before}", flush=True)

    if _LLM_ENABLED:
        # Fetch already-known fb_* yad2_ids so we can skip LLM on dupes (cost saver)
        known_ids: set[str] = set()
        try:
            with httpx.Client(timeout=30) as client:
                kr = client.get(f"{PDIS_API_URL}/api/ingest/facebook/existing-ids")
                kr.raise_for_status()
                known_ids = set(kr.json().get("ids", []))
            print(f"Known fb_* yad2_ids: {len(known_ids)} (will skip LLM for these)", flush=True)
        except Exception as exc:
            print(f"WARN: could not fetch known IDs ({exc}); LLM will parse all posts", flush=True)

        limit = int(os.environ.get("LLM_LIMIT", str(len(posts))))
        print(f"Running LLM parse on up to {min(limit, len(posts))} posts...", flush=True)
        usage_stats: list[dict] = []
        llm_errors = 0
        llm_skipped = 0
        for i, p in enumerate(posts[:limit]):
            if i % 25 == 0 and i > 0:
                print(f"  [{i}/{limit}] llm_errors={llm_errors} skipped_known={llm_skipped}", flush=True)
            yad2_id = f"fb_{p['post_id']}"
            if yad2_id in known_ids:
                llm_skipped += 1
                continue
            result = llm_parse_post(_llm_client, p["description"], p["author_name"])
            if result.get("_error"):
                llm_errors += 1
                continue
            if "_usage" in result:
                usage_stats.append(result["_usage"])
            # Override fields only if LLM returned a non-null value; keep regex otherwise
            if result.get("price_ils") is not None:
                p["price"] = int(result["price_ils"])
            if result.get("sqm_net") is not None:
                p["sqm_net"] = int(result["sqm_net"])
            if result.get("sqm_balcony") is not None:
                p["sqm_balcony"] = int(result["sqm_balcony"])
            if result.get("intent"):
                p["intent"] = str(result["intent"])
            if result.get("rooms") is not None:
                p["rooms"] = float(result["rooms"])
            if result.get("phone"):
                p["contact_phone"] = re.sub(r"\D", "", str(result["phone"])) or None
            if result.get("neighborhood"):
                p["neighborhood"] = result["neighborhood"]
            if result.get("street_address"):
                p["address_street"] = str(result["street_address"]).strip()
            if result.get("house_number") is not None:
                try:
                    p["address_home_number"] = int(result["house_number"])
                except (TypeError, ValueError):
                    pass
            if result.get("floor") is not None:
                try:
                    p["floor"] = int(result["floor"])
                except (TypeError, ValueError):
                    pass
            if result.get("intent"):
                p["intent"] = str(result["intent"]).strip().lower()
            if result.get("confidence") is not None:
                try:
                    p["confidence"] = float(result["confidence"])
                except (TypeError, ValueError):
                    pass
        cost = llm_estimate_cost(usage_stats)
        attempted = min(limit, len(posts)) - llm_skipped
        print(
            f"LLM done: parsed={attempted - llm_errors} skipped_known={llm_skipped} "
            f"errors={llm_errors} in_tokens={cost['in']:,} out_tokens={cost['out']:,} "
            f"cache_read={cost['cache_read']:,} cache_write={cost['cache_write']:,} "
            f"cost=${cost['usd']:.4f}",
            flush=True,
        )
        after = _count(posts[:limit], ["price", "sqm_net", "rooms", "contact_phone", "neighborhood"])
        print(f"After LLM: {after}", flush=True)

    # --- Per-intent sanity bands (runs for ALL posts, regardless of LLM) ---
    # Band rules: null the price if out of range; drop the post if intent is wanted/other.
    _PRICE_BANDS: dict[str, tuple[int, int]] = {
        "rent": (2500, 50_000),
        "apartment_forsale": (300_000, 50_000_000),
        "building_forsale": (5_000_000, 200_000_000),
    }
    _DROP_INTENTS = {"wanted", "other"}
    filtered_posts: list[dict] = []
    dropped_count = 0
    out_of_band_count = 0
    for p in posts:
        intent = p.get("intent")
        if intent in _DROP_INTENTS:
            print(
                f"fb.post_dropped post_id={p['post_id']} intent={intent}",
                flush=True,
            )
            dropped_count += 1
            continue
        if intent in _PRICE_BANDS and p.get("price") is not None:
            lo, hi = _PRICE_BANDS[intent]
            if not (lo <= p["price"] <= hi):
                print(
                    f"fb.price_out_of_band post_id={p['post_id']} intent={intent} "
                    f"received_price={p['price']}",
                    flush=True,
                )
                p["price"] = None
                out_of_band_count += 1
        filtered_posts.append(p)
    print(
        f"Sanity bands: dropped={dropped_count} price_nulled={out_of_band_count} "
        f"remaining={len(filtered_posts)}",
        flush=True,
    )
    posts = filtered_posts

    headers = {
        "Authorization": f"Bearer {INGEST_SECRET}",
        "Content-Type": "application/json",
    }
    url = f"{PDIS_API_URL}/api/ingest/facebook"

    MAX_ATTEMPTS = 3
    RETRY_WAIT_S = 60

    sent = 0
    with httpx.Client(timeout=300) as client:
        for i in range(0, len(posts), BATCH_SIZE):
            batch = posts[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            success = False
            for attempt in range(1, MAX_ATTEMPTS + 1):
                print(f"POST batch {batch_num}: {len(batch)} posts (attempt {attempt}/{MAX_ATTEMPTS})...", flush=True)
                t0 = time.time()
                try:
                    resp = client.post(url, json={"posts": batch}, headers=headers)
                    resp.raise_for_status()
                    body = resp.json()
                    elapsed = time.time() - t0
                    sent += len(batch)
                    print(f"  OK in {elapsed:.1f}s: {json.dumps(body)[:200]}", flush=True)
                    success = True
                    break
                except httpx.HTTPStatusError as exc:
                    code = exc.response.status_code
                    print(f"  FAIL {code}: {exc.response.text[:300]}", flush=True)
                    # Retry only on 5xx; 4xx is permanent (auth, validation, etc.)
                    if code < 500 or attempt == MAX_ATTEMPTS:
                        break
                except Exception as exc:
                    print(f"  EXC: {exc}", flush=True)
                    if attempt == MAX_ATTEMPTS:
                        break
                if attempt < MAX_ATTEMPTS:
                    print(f"  retrying in {RETRY_WAIT_S}s...", flush=True)
                    time.sleep(RETRY_WAIT_S)
            if not success:
                print(f"  batch {batch_num} dropped after {MAX_ATTEMPTS} attempts", flush=True)

    print(f"Done. {sent}/{len(posts)} posts POSTed.", flush=True)


if __name__ == "__main__":
    main()
