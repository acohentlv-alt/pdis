"""
Yad2 phone fetch — per-listing customer endpoint on gw.yad2.co.il.

The feed index does not include phones; each listing's phone lives at
GET https://gw.yad2.co.il/realestate-item/{token}/customer and is returned
without authentication once a warm-up hit to www.yad2.co.il has seeded the
Incapsula cookies.

Response shape: {"data": {"phone", "brokerPhone", "brokers": [...], ...},
                 "message": "OK"}.
"""

import asyncio
import random
import re

import structlog
from curl_cffi import requests as cf_requests

from pdis.config import settings

logger = structlog.get_logger(__name__)

GW_BASE = "https://gw.yad2.co.il"
WARMUP_URL = "https://www.yad2.co.il/realestate/rent"
ITEM_REFERER_BASE = "https://www.yad2.co.il/item"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://www.yad2.co.il",
}


_DIGITS = re.compile(r"\D+")


def normalize_phone(raw: str | None) -> str | None:
    """Normalize Yad2 phone to Israeli 0XXXXXXXXX (10 digits) format.

    Returns None for None, empty, or unparseable input.
    """
    if not raw:
        return None
    digits = _DIGITS.sub("", raw)
    if not digits:
        return None
    if digits.startswith("972"):
        digits = "0" + digits[3:]
    if len(digits) != 10 or not digits.startswith("0"):
        return None
    return digits


def _extract_phone(body: dict) -> str | None:
    """Pull phone from a /customer response. Fallback chain covers both
    agent-listed and private-seller payload shapes."""
    if not isinstance(body, dict):
        return None
    data = body.get("data") or {}
    if not isinstance(data, dict):
        return None
    for key in ("phone", "brokerPhone"):
        v = normalize_phone(data.get(key))
        if v:
            return v
    brokers = data.get("brokers") or []
    if isinstance(brokers, list) and brokers:
        first = brokers[0] or {}
        if isinstance(first, dict):
            v = normalize_phone(first.get("phone"))
            if v:
                return v
    return None


async def fetch_phones(yad2_ids: list[str]) -> dict[str, str | None]:
    """Fetch contact phones for Yad2 listing tokens.

    Returns a dict mapping every input id to a phone string (normalized) or
    None. Never raises — failures map to None. On three consecutive blocks,
    aborts the remaining batch and returns partial results (unseen ids are
    absent from the dict).
    """
    results: dict[str, str | None] = {}
    if not yad2_ids:
        return results

    def _do_fetch() -> dict[str, str | None]:
        session = cf_requests.Session(impersonate="chrome")

        # Warm-up: seeds __uzm* Incapsula cookies. One attempt only; if it
        # fails we still try the per-item calls — they sometimes work cold.
        try:
            session.get(WARMUP_URL, timeout=settings.scrape_request_timeout)
        except Exception as exc:
            logger.warning("yad2_phone.warmup_failed", error=str(exc))

        base_delay = settings.yad2_phone_fetch_delay_seconds
        current_delay = base_delay
        elevated_calls_remaining = 0
        consecutive_blocks = 0

        for i, token in enumerate(yad2_ids):
            if i > 0:
                import time
                time.sleep(current_delay + random.uniform(0, base_delay))
            try:
                r = session.get(
                    f"{GW_BASE}/realestate-item/{token}/customer",
                    headers={
                        **HEADERS,
                        "Referer": f"{ITEM_REFERER_BASE}/{token}",
                    },
                    timeout=settings.scrape_request_timeout,
                )
            except Exception as exc:
                logger.warning("yad2_phone.request_failed", token=token, error=str(exc))
                results[token] = None
                consecutive_blocks += 1
                if consecutive_blocks >= 3:
                    logger.warning("yad2_phone.batch_aborted", completed=i + 1, total=len(yad2_ids))
                    break
                continue

            if r.status_code in (429, 403):
                logger.warning("yad2_phone.rate_limited", token=token, status=r.status_code)
                results[token] = None
                current_delay = base_delay * 2
                elevated_calls_remaining = 5
                consecutive_blocks += 1
                if consecutive_blocks >= 3:
                    logger.warning("yad2_phone.batch_aborted", completed=i + 1, total=len(yad2_ids))
                    break
                continue

            consecutive_blocks = 0

            if elevated_calls_remaining > 0:
                elevated_calls_remaining -= 1
                if elevated_calls_remaining == 0:
                    current_delay = base_delay

            if r.status_code != 200:
                logger.warning("yad2_phone.bad_status", token=token, status=r.status_code)
                results[token] = None
                continue

            try:
                phone = _extract_phone(r.json())
            except Exception as exc:
                logger.warning("yad2_phone.parse_failed", token=token, error=str(exc))
                phone = None
            results[token] = phone

        return results

    return await asyncio.to_thread(_do_fetch)
