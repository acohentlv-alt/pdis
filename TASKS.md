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

### Facebook Groups as 3rd source (PLANNING)
Add 8 TLV/RG/Givatayim Hebrew rental Facebook groups as a 3rd data source alongside Yad2 and Madlan. Modeled on competitor 4kirot.com (Apify-based ingestion). 3-phase rollout planned:
- Brief #1: Apify integration + free-text parser + new `fb_*` properties + scanner pipeline plumbing (hidden behind a feature flag)
- Brief #2: FB-aware dedup (text+price+coarse-geo), new FB-specific signals (no-broker badge, multi-group cross-post = high distress, broker-flooding filter)
- Brief #3: UI badges, source filter, "Hide brokers" toggle, polish
Open questions awaiting Alan's answers before /exec — see planner output for full list.
