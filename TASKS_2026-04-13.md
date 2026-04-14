# PDIS — Task List
*April 13, 2026*

---

## DONE (today)

*(Nothing yet — session just started.)*

---

## AWAITING DEPLOY (FB Brief #1 — code on main, Alan's manual steps remain)

### Alan's ~30 min deployment checklist
Code shipped in commit `c53e651`. Frontend shipped in `29706c9`. Render should have auto-deployed the backend by now.

1. Verify Render deploy: `curl https://pdis-lsah.onrender.com/api/ingest/facebook/health`
2. Verify `TLV_CITY_STRING` = `"תל אביב-יפו"` against Neon (exact byte match with Yad2's city string)
3. `openssl rand -hex 32` → `INGEST_SECRET`
4. Set Render env vars: `INGEST_SECRET`, `FB_INGESTION_ENABLED=false`, `FB_SCANS_PER_DAY=1`
5. `python3 export_fb_cookies.py` on laptop → log in with personal FB → saves `fb_state.json`
6. SCP scraper + cookies to Oracle VM (commands in `vm-scraper/README.md`)
7. Install deps on VM, test-run `./run.sh` manually, check `posts_found > 0`
8. Add crontab with `CRON_TZ=Asia/Jerusalem`
9. Flip `FB_INGESTION_ENABLED=true` → watch first real scan

---

## NOT STARTED

### Facebook Groups Brief #2 (re-plan after 1 week of real FB data)
FB-aware dedup (same author + price match across groups), new FB-specific signals (no-broker badge, multi-group cross-post = high distress, broker-flooding filter). Nominatim geocoding pass for posts with extracted street name.

### Facebook Groups Brief #3
Source filter dropdown, "Hide brokers" toggle, "Report this listing" link, optional image proxy/cache for expiring FB CDN URLs.

### Telegram bot for scan alerts
Send alerts when notable properties found after a scan completes.

### Backfill descriptions for existing properties
Scanner now captures `info_text` from Yad2 detail API as description. ~450 existing properties still have placeholder descriptions. Backfilled automatically on next scan run — just needs a scan trigger.

### Facebook Marketplace integration (PARKED)
Reviewed and parked. Needs Playwright + perceptual image hashing.
