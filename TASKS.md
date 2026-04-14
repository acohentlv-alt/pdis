# PDIS — Task List
*April 15, 2026*

---

## AWAITING QA / VERIFICATION (deployed tonight, needs Alan's eyes in the browser)

### Scan button UX + progress bar
Shipped but needs manual test in deployed environment after Render auto-deploy:
- Click Run Now → button reads `Scanning X%` with live emerald bar
- Other presets disable with "Scan running"
- Last-scan line per preset (`Xm ago · N listings` / `Never scanned` / red `failed` / amber `blocked`)
- Error banner surfaces readable messages

### FB groups multi-select UI
Hard-refresh browser then edit FB preset → verify 49 checkboxes appear, tick relevant ones, save, reopen → persistence check.

---

## READY TO RUN (Alan's hands, ~30-45 min)

### FB VM scraper deployment
Catalog is seeded (49 groups in Neon), UI works, but no posts are being ingested because the VM scraper hasn't been deployed. Steps:
1. `scp ~/pdis/vm-scraper/fb_state.json ubuntu@129.159.158.214:/opt/pdis-fb-scraper/state.json`
2. SSH to VM, install playwright on venv (`pip install playwright && playwright install chromium`)
3. Transfer `run.py` + requirements, install deps
4. Manual test run — confirm POST /api/ingest/facebook 200
5. Install crontab entry at 08:00 + 18:00 Israel time
6. Flip `FB_INGESTION_ENABLED=true` on Render

Full 8-step checklist from prior day is in archived `TASKS_2026-04-14.md` under "AWAITING DEPLOY".

### Govmap full backfill completion + monthly cron
Still running in tmux session `govmap` on VM. Check status:
```
ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214 "tail -5 /tmp/govmap_full.log"
```
When complete, verify:
```sql
SELECT COUNT(*) FROM closed_transactions;  -- expect 500k-1M
```
Then install monthly cron (exact block in `TASKS_2026-04-14.md`).

---

## NOT STARTED

### ₪/m² math fix on PropertyCard
First card shows `4,299,999 ₪ · 82m² (95 total) · 52,439 ₪/m²`. The ₪/m² uses the smaller (build) area. Israeli real estate convention = gross/total. One-line fix in `frontend/src/components/PropertyCard.tsx`: prefer total area, or show both. Quick win.

### Govmap comps rework — Option 2 (Amit-approved)
Planned but not coded. Remove `below_closed_comps` / `above_closed_comps_20pct` averages-based signals. Replace with raw list of last 3-5 closed sales in same building on PropertyDetailPage. Amit explicitly said he doesn't want neighborhood averages — just real comparable deals. See Apr 14 conversation for full scoping.

### Phone numbers — still broken
- Madlan: scraper reads `poc.displayNumber` but 0/713 properties get one. Broken or API changed.
- Yad2: requires separate click-to-reveal API call (not wired).
- FB: works once FB ingest is flowing (depends on deployment above).

### FB Groups Brief #2 (re-plan after 1 week of real FB data)
FB-aware dedup, new FB-specific signals (no-broker badge, multi-group cross-post = high distress), Nominatim geocoding pass for neighborhoods.

### FB Groups Brief #3
Source filter dropdown, "Hide brokers" toggle, "Report this listing" link.

### Telegram bot for scan alerts
Send alerts when notable properties found after a scan completes.

### F6 — Neighborhood pulse (24-month ₪/m² sparkline)
Depends on full-city govmap backfill (in progress) + Amit providing thresholds for more neighborhoods.

---

## PARKED

### FB Marketplace integration
Different from FB Groups (which we shipped). Needs Playwright + perceptual image hashing. Revisit after FB Groups pipeline is proven.
