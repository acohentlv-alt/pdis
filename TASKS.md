# PDIS — Task List
*April 12, 2026*

---

## DONE (today)

*(Nothing yet — session just started.)*

---

## AWAITING TEST (carried from Apr 5 late night)

### Verify latest push on production
Late-night Apr 5 push added two changes — still need verification on production:
- Preset Manager scrolls to bottom with padding (`pb-16` + `z-[60]` fix)
- Sort dropdown shows "Market time + Signals" as default
- Cards sorted by longest on market first (days_on_market DESC, signal count DESC as tiebreaker)

### Scheduled scans behavior with new code
cron-job.org is set up (08:00 + 18:00 Israel time) but scan behavior needs checking against the latest code.

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
