# PDIS — Task List
*April 3, 2026*

---

## DONE (today)

*(empty — new day)*

---

## AWAITING TEST

### Whitelist/blacklist buttons on PropertyCard
**What:** Two buttons (✓ / ✕) next to the favorite star on every property card. Green when whitelisted, red when blacklisted. Toggle on click. Backend /api/whitelist/ids and /api/blacklist/ids endpoints added.

### PresetManager advanced filters
**What:** Collapsible "Advanced Filters" section with: area code, neighborhood, property types (8 checkboxes), sqm range, floor range, move-in date, 8 amenity checkboxes, photos only. Backend accepts and stores all fields, Yad2 scraper sends them as API params.

### Property search across all data
**What:** When keyword search returns 0 results in current view, shows "Search all properties" link. Clicks it → searches entire database via GET /api/properties/search?q=... ILIKE on address, neighborhood, city, description.

### Rent/Buy page separation
**What:** /rent shows Rental Hunter (category=rent), /buy shows Purchase Hunter (category=forsale). All APIs filter by category. NavBar: Rent, Buy, Favorites, Search. / redirects to /rent.

### Stat card click behavior
**What:** 4 stat cards (Scanned, Opportunities, Price Drops, Reappeared). All clickable, filters reset on click. Numbers match click results. Active card has dark background.

---

## NOT STARTED

### Fix Save/favorite button on property detail page
**What:** The "Save" button on the property detail page doesn't turn yellow when the property is favorited. It should show a filled yellow star (⭐) when the property is in favorites, matching the behavior on property cards.

### Create buy presets for Haifa
**What:** Create forsale presets in PresetManager for Haifa. Need to find Haifa's Yad2 city code. Run a scan to populate buy data on the /buy page.

### Create GitHub repo + push
**What:** Initialize a GitHub repo, push all local commits, connect to Render for auto-deploy.

### Deploy to Render
**What:** render.yaml exists. Connect repo, verify production works (Neon DB, static files, SPA routing). Set CRON_SECRET env var, configure cron-job.org for 08:00/18:00 Israel time.

### Telegram bot
**What:** Send alerts when new hot properties are detected after a scan. Shechter gets a Telegram message with property summary + link.

### Classification threshold tuning
**What:** Alan wants to finetune: price drop % for strong signal (currently >10%), days on market thresholds (currently 90+ strong, 30-89 weak), relisting count, below-average price %, weak signal count for hot (currently 3+). Needs more data first.

### Facebook Marketplace integration (PARKED)
**What:** Third data source. Needs Playwright + perceptual image hashing. Multiple blockers identified in reviews. Parked until other priorities done.
