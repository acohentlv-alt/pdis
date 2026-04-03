# HANDOFF — April 3, 2026

---

## What we did today

Major UI overhaul and rent/buy separation. Fixed stat cards (4 cards, clickable, show correct data), fixed keyword search (Yad2 now stores real listing descriptions instead of address_more), added whitelist/blacklist buttons to property cards, expanded PresetManager with all Yad2 filter options, added "Search all properties" feature, and split the app into separate Rental Hunter (/rent) and Purchase Hunter (/buy) pages with category-filtered APIs. Also fixed condition keyword false positives by switching from root words to distress phrase matching.

---

## What's half-done

### Manual testing of Tasks 3-5
Whitelist/blacklist buttons, expanded preset filters, and property search were built and passed QA automation but Alan hasn't manually verified them yet.

### Buy presets don't exist yet
The Purchase Hunter page (/buy) works but shows 0 properties because no forsale presets have been created. Shechter needs to create buy presets for Haifa through the PresetManager.

### Classification threshold tuning
Alan wants to finetune the signal thresholds (price drop %, days on market, etc.) once he has more data. The current thresholds are functional but not tuned to his preferences yet.

---

## What to do next

**First:** Alan manually tests whitelist/blacklist buttons, preset advanced filters, and property search on http://localhost:8000/rent.

**Second:** Create a forsale preset for Haifa in the PresetManager, run a scan, verify buy data flows to /buy page.

**Third:** Create GitHub repo, push code, deploy to Render.

---

## Watch out for

- **Port confusion:** Alan had uvicorn on BOTH 8090 and 8000. Always verify which port he's testing on. The built frontend is at whatever port `uvicorn pdis.api.main:app` is running.
- **Condition keywords use PHRASES now**, not root words. "שיפוץ" alone no longer triggers the signal — only "דרוש שיפוץ", "דירת סבתא", etc. Plus renovated=true suppresses it entirely.
- **`/` redirects to `/rent`** — there is no landing page. NavBar has 4 tabs: Rent, Buy, Favorites, Search.
- **API category params are optional** — omitting `?category=` returns all data (backward compatible).
- **Yad2 scraper URL is now dynamic** — uses `/realestate/forsale` for buy presets, `/realestate/rent` for rent. The Referer header also changes.
- **Keyword search persists in URL** (`?keyword=שיפוץ`) — survives navigation to property detail and back.
- **All the existing watch-outs from previous sessions still apply** (English UI, hooks before returns, route ordering, no numeric scores).

---

## Test these

- Whitelist/blacklist buttons on property cards (Task 3)
- PresetManager advanced filters — sqm, floor, amenities, property types (Task 4)
- "Search all properties" fallback when keyword has 0 results in current view (Task 5)
- Buy page (/buy) once a forsale preset is created
- Stat card clicks after fresh page load (Price Drops, Reappeared)
