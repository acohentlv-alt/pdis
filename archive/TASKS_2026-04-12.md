# PDIS — Task List
*April 12, 2026*

---

## DONE (today)

### Phase 1A Amit Fit backend shipped
Commit `8705f0b` on main. Foundation for per-neighborhood pricing intelligence:
- New `neighborhood_thresholds` table (preferred + max per-sqm targets per size bucket, unique + check constraints)
- Signal engine adds `buyer_fit_tags` array to `signal_details` — ORTHOGONAL to distress, does NOT affect hot/warm/cold classification
- 3 API endpoints: GET/PUT/DELETE `/api/thresholds` with full validation
- QA 28/28 PASS. Verified end-to-end on real Florentin property.

### QA of Apr 5 changes → deploy caught up
Preset Manager scroll fix = LIVE. Sort dropdown fix = LIVE (was stale this morning, Render deployed overnight to new bundle `index-ts09WsP6.js`).

---

## IN PROGRESS

### Phase 1B Amit Fit admin UI (NEXT)
Add "Pricing Targets" collapsible in PresetManager.tsx edit form, only when `category='forsale'`. Per neighborhood in preset (comma-sep hood_ids resolved via `useNeighborhoods`): 7 stacked size-bucket rows × 2 inputs (preferred, max ₪/m²). One collapsible per neighborhood, collapsed by default (mobile-friendly). Save calls PUT /api/thresholds. Reviewer recommended batch fetch per preset, not N queries per neighborhood.
**Decisions Alan made (during planning):**
- Consolidate badges (don't stack Amit Fit + Below-avg — Amit takes precedence) [applies to Phase 1C]
- Apply Amit signals to Favorites + SearchResults sort too, not just OpportunityPage
- hood_id for Florentin is NOT 1471 — must be looked up from DB: `SELECT DISTINCT hood_id, neighborhood FROM properties WHERE neighborhood LIKE '%פלורנטין%'`

### Phase 1C Amit Fit display (AFTER 1B)
- Remove old `dealQualityLabel` / `targetPriceSqm` / `computeTargetPriceSqm` (PropertyCard.tsx:14,32,84-93,124; OpportunityPage.tsx:9,270-272,429,445; presetMatch.ts:32-40)
- Gold 🎯 PRIME DEAL banner at top of card when buyer_fit_tags non-empty AND strong_signals.length >= 1
- Green "Amit Fit · −N%" pill when below preferred; yellow "Close · +N%" when between preferred and max
- Consolidate: hide below_avg pill when Amit Fit pill fires (Amit takes precedence)
- Update signalCount helper in OpportunityPage, FavoritesPage, SearchResultsPage to include buyer_fit_tags.length

---

## NOT STARTED

### Telegram bot for scan alerts
Send alerts when notable properties found after a scan completes.

### Backfill descriptions for existing properties
Scanner now captures `info_text` from Yad2 detail API as description. ~450 existing properties still have placeholder descriptions. They'll be backfilled automatically on next scan run — just needs a scan trigger.

### Facebook Marketplace integration (PARKED)
Reviewed and parked. Needs Playwright + perceptual image hashing.

### Facebook Groups Brief #1 — CODE COMPLETE, AWAITING QA + DEPLOY
Apr 12: 4 planner passes + 4 reviews + executor. Code landed (not committed). Approach switched mid-flight from Apify → burner → personal account on Oracle VM via residential proxy.

**5 groups scraped:** `458499457501175` (Couples/Roommates/Families TLV), `RentinTLV` (Singles/Couples No-Broker), `333022240594651` (Fair-Priced TLV), `305724686290054` (TLV Rentals), `457465901082882` (TLV No-Broker).

**Architecture:** VM scraper (`~/pdis/vm-scraper/`) with Playwright + residential proxy + personal FB cookies → POSTs to new `/api/ingest/facebook` on Render → feeds `run_scan_from_listings()` which runs full pipeline (upsert → snapshots → events → classify → matches → relistings → FB-scoped removals → stats). Phone mask `054-***-****` with tap-to-reveal on PropertyCard (FB-only), dashboard banner when health endpoint shows alert. Feature flag `FB_INGESTION_ENABLED=false` until validated.

**Alan's 3 validation steps before flipping flag:**
1. Verify `TLV_CITY_STRING = "תל אביב-יפו"` against prod Neon DB
2. Verify m.facebook.com DOM selectors (`h3 a`, `abbr/time`, `[data-testid="post_message"]`, `article`) after first test-run
3. Subscribe to Smartproxy (~$7/mo residential) — **PROXY_URL mandatory**, `run.sh` hard-exits without it

**Alan's deployment checklist (~30 min):**
- `openssl rand -hex 32` → set `INGEST_SECRET` on Render + VM `.env`
- Set Render env: `FB_INGESTION_ENABLED=false`, `FB_SCANS_PER_DAY=1` (probation)
- Run `export_fb_cookies.py` on laptop → SCP to VM as `state.json` (chmod 600)
- Install deps on VM (`pip install -r requirements.txt && playwright install chromium`)
- Test-run once manually (`./run.sh`), verify `posts_found > 0`
- Add crontab with `CRON_TZ=Asia/Jerusalem` at 08:00 + 18:00 with `flock`
- Flip `FB_INGESTION_ENABLED=true`

**Next:** `/qa` Brief #1 changes, then commit + push, then Alan deploys.

### Facebook Groups Brief #2 — NOT STARTED (re-plan after 1 week of real data)
FB-aware dedup (text+price+coarse-geo), new FB-specific signals (no-broker badge, multi-group cross-post = high distress, broker-flooding filter), Nominatim geocoding pass.

### Facebook Groups Brief #3 — NOT STARTED
Source filter dropdown, "Hide brokers" toggle, "Report this listing" link, optional image proxy/cache.
