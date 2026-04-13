"""
Unit tests for the Facebook scraper parser helpers.
Tests the text extraction functions from vm-scraper/run.py.
"""

import importlib.util
import pathlib
import sys

import pytest

# Dynamically import the scraper module without requiring its dependencies to be installed.
# We only test the pure helper functions (no Playwright, no httpx needed).
_SCRAPER_PATH = pathlib.Path(__file__).parent.parent / "vm-scraper" / "run.py"


def _load_scraper_helpers():
    """
    Load extraction helper functions from run.py without executing __main__.
    Returns a namespace object with all module-level names.
    """
    spec = importlib.util.spec_from_file_location("fb_run", _SCRAPER_PATH)
    module = importlib.util.module_from_spec(spec)
    # Patch out the dependencies that would fail on import
    sys.modules.setdefault("playwright", type(sys)("playwright"))
    sys.modules.setdefault("playwright.sync_api", type(sys)("playwright.sync_api"))
    sys.modules.setdefault("httpx", type(sys)("httpx"))
    sys.modules.setdefault("dotenv", type(sys)("dotenv"))

    # Stub load_dotenv so the import doesn't fail
    import unittest.mock as mock
    with mock.patch.dict("os.environ", {"INGEST_SECRET": "test"}):
        with mock.patch("builtins.__import__", side_effect=_safe_import):
            try:
                spec.loader.exec_module(module)
            except Exception:
                pass  # Some top-level code may fail; helpers are already loaded
    return module


def _safe_import(name, *args, **kwargs):
    if name in ("playwright", "playwright.sync_api", "httpx", "dotenv"):
        return type(sys)(name)
    raise ImportError(name)


# Load helpers once at module level
try:
    import unittest.mock as _mock
    import os as _os

    _spec = importlib.util.spec_from_file_location("fb_run", _SCRAPER_PATH)
    _mod = importlib.util.module_from_spec(_spec)

    # Stub heavy deps
    _stub = type(sys)
    for _dep in ("playwright", "playwright.sync_api", "httpx"):
        sys.modules.setdefault(_dep, _stub(_dep))
    sys.modules["playwright.sync_api"].sync_playwright = lambda: None
    sys.modules["playwright.sync_api"].Page = object

    # Stub load_dotenv
    _dotenv_stub = _stub("dotenv")
    _dotenv_stub.load_dotenv = lambda: None
    sys.modules["dotenv"] = _dotenv_stub

    with _mock.patch.dict(_os.environ, {"INGEST_SECRET": "test"}):
        _spec.loader.exec_module(_mod)

    _extract_price = _mod._extract_price
    _extract_rooms = _mod._extract_rooms
    _extract_phone = _mod._extract_phone
    _is_agent = _mod._is_agent
    _should_skip = _mod._should_skip
    _extract_neighborhood = _mod._extract_neighborhood
    _HELPERS_LOADED = True
except Exception as _e:
    _HELPERS_LOADED = False
    _LOAD_ERROR = str(_e)


@pytest.mark.skipif(not _HELPERS_LOADED, reason=f"Could not load scraper helpers")
class TestFbParserHelpers:
    """Tests for the regex-based text extraction helpers in vm-scraper/run.py."""

    # ── Fixture 1: Typical private listing ──────────────────────────────────

    def test_typical_private_listing_price(self):
        """Price extracted correctly from a standard rental post."""
        text = "דירת 3 חדרים ברחוב פלורנטין, 7500 ש״ח, ללא תיווך, 052-1234567"
        assert _extract_price(text) == 7500

    def test_typical_private_listing_rooms(self):
        """Room count extracted from a standard listing."""
        text = "דירת 3 חדרים ברחוב פלורנטין, 7500 ש״ח, ללא תיווך"
        assert _extract_rooms(text) == 3.0

    def test_typical_private_listing_phone(self):
        """Phone number extracted from listing text."""
        text = "דירת 3 חדרים ברחוב פלורנטין, 7500 ש״ח, ללא תיווך, 052-1234567"
        assert _extract_phone(text) == "052-1234567"

    def test_typical_private_listing_not_agent(self):
        """Private listing (ללא תיווך) does not trigger is_agent."""
        text = "דירת 3 חדרים ברחוב פלורנטין, 7500 ש״ח, ללא תיווך, 052-1234567"
        assert _is_agent(text) is False

    def test_typical_private_listing_not_skipped(self):
        """Private rental listing is not skipped."""
        text = "דירת 3 חדרים ברחוב פלורנטין, 7500 ש״ח, ללא תיווך, 052-1234567"
        assert _should_skip(text) is False

    # ── Fixture 2: Broker listing ────────────────────────────────────────────

    def test_broker_listing_is_agent_true(self):
        """Post containing broker keyword is flagged as agent."""
        text = "תיווך בלעדי! דירת 4 חדרים, 9000 ₪, יד שניה"
        assert _is_agent(text) is True

    def test_agent_keyword_metavech(self):
        """מתווך keyword triggers is_agent."""
        text = "מתווך מציע דירה יפה, 3 חדרים, 6500 ₪"
        assert _is_agent(text) is True

    def test_agent_keyword_sochen(self):
        """סוכן keyword triggers is_agent."""
        text = "סוכן נדל\"ן: דירת 2 חדרים, 5800 ₪, בוגרשוב"
        assert _is_agent(text) is True

    # ── Fixture 3: Roommate-wanted post (should be skipped) ─────────────────

    def test_roommate_post_skipped(self):
        """מחפש שותף לדירה posts are skipped."""
        text = "מחפש שותף לדירה בפלורנטין, 2500 ₪ לחדר, מעשן/ת בסדר"
        assert _should_skip(text) is True

    def test_roommate_feminine_skipped(self):
        """מחפשת שותף לדירה posts are skipped."""
        text = "מחפשת שותף לדירה, ברמת אביב"
        assert _should_skip(text) is True

    # ── Fixture 4: No price (should return None from parse logic) ────────────

    def test_no_price_returns_none(self):
        """Post with no price and no phone should not have a price."""
        text = "דירה להשכרה בדיזנגוף, פרטים בפרטי, ללא תיווך"
        assert _extract_price(text) is None
        assert _extract_phone(text) is None

    def test_price_with_shekel_symbol(self):
        """₪ symbol extracted correctly."""
        text = "3 חדרים ב-7500 ₪ לחודש"
        assert _extract_price(text) == 7500

    def test_price_with_comma(self):
        """Prices with thousand separators parsed correctly."""
        text = "דירה יפה, 10,500 ש״ח"
        assert _extract_price(text) == 10500

    # ── Fixture 5: Phone + neighborhood ─────────────────────────────────────

    def test_ramt_gan_neighborhood(self):
        """Neighborhood extracted when mentioned with ב prefix."""
        text = "דירת 2 חדרים ברמת גן, 5500 ₪, 054-9876543"
        neighborhood = _extract_neighborhood(text)
        # Neighborhood extraction may return 'רמת גן' or similar
        assert neighborhood is not None
        assert "רמת" in neighborhood

    def test_phone_extracted(self):
        """Phone number with dash separators extracted."""
        text = "דירת 2 חדרים ברמת גן, 5500 ₪, 054-9876543"
        assert _extract_phone(text) == "054-9876543"

    def test_phone_without_dashes(self):
        """Phone number without dashes also extracted."""
        text = "התקשרו 0509876543"
        assert _extract_phone(text) is not None

    # ── Additional edge cases ────────────────────────────────────────────────

    def test_half_rooms(self):
        """Half-room counts (e.g. 2.5) parsed correctly."""
        text = "דירת 2.5 חדרים בתל אביב, 6000 ₪"
        assert _extract_rooms(text) == 2.5

    def test_no_broker_keyword_not_agent(self):
        """Post without broker keywords is not flagged as agent."""
        text = "דירה פרטית, 3 חדרים, 7000 ₪ לחודש"
        assert _is_agent(text) is False
