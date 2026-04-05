# PDIS — Task List
*April 5, 2026 (evening session)*

---

## DONE (today)

### Dashboard overhaul — preset pills + new navigation
Replaced Rent/Buy tabs with preset-pill-based home page. 3 bottom tabs (Home / My Listings / Search). Preset pills scroll horizontally with criteria summaries. Selected preset saved in localStorage.

### Property card redesign
New order: Image → Money (big price + NIS/m²) → Specs (type/rooms/sqm) → Building (floor, ✓/✗ elevator, ✓/✗ parking) → Location → Signal badges → Actions. Added rooms, floor, property_type display.

### Backend preset properties endpoint
New GET /api/presets/{preset_id}/properties with criteria-based SQL filtering (not preset_id), classification JOIN, sorted by days_on_market DESC.

### Preset management: Clone + Run Now
Clone endpoint, async Run Now with background task, scan completion auto-refresh.

### Removed Hot/Warm/Cold classification from UI
Removed classification badges, stat row, filter dropdown. Individual signal badges remain. Sort by longest on market.

### Fixed relisting logic
Stopped generating false relisting events from scan gaps. Only real relistings (changed yad2_date_added) count.

### Description scraping
Scanner now saves info_text from Yad2 detail API as description. Preview shown on property cards.

### New presets created
Haifa Buy - Small Apts (ID=11), Haifa Buy - Buildings (ID=12), TLV Rent - Villas (ID=13) with Shechter's real criteria.

### Neighborhood picker
Replaced numeric ID text field with checkbox picker showing real Hebrew neighborhood names + listing counts.

### Preset pill summaries
Pills show criteria summary like "1-2.5 rooms · Up to 400K · Apartment · 4 hoods".

### SummaryBar: prop-driven stats
Stats derived from loaded properties, stat cards clickable (Scanned clears filter, Price Drops/Reappeared filter the list).

---

## AWAITING TEST

### Verify all changes on production
Push happened at end of session. Need to verify on https://pdis-lsah.onrender.com:
- Preset pills and switching work
- New presets (11, 12, 13) visible
- Neighborhood picker works
- Description shows on cards (may need a scan to backfill)
- Sort order is longest on market first

### Scheduled scans still need verification
cron-job.org set up but scan behavior with new code needs checking.

---

## NOT STARTED

### Telegram bot
Send alerts when notable properties found after scan.

### Backfill descriptions for existing properties
Scanner now captures descriptions, but ~450 existing properties have none. Next scan run will backfill them automatically.

### Facebook Marketplace integration (PARKED)
