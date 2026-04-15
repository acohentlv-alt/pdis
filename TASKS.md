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

### FB VM scraper deployment — A2 brief drafted, awaiting /review and /exec
Investigation Apr 15 (late session) confirmed three stacked off-switches: feature flag default-False, empty fb_groups linkage on the active preset, scraper never ran. Planner produced a full A2 brief (in conversation transcript, planner agent `ab7b1cef88493c91a`).

Brief summary:
- **New:** `pdis/utils/city.py` with `normalize_city()` supporting 6 TLV variants (Hebrew with/without hyphen, English variants → canonical `"תל אביב יפו"`)
- **Remove:** `TLV_CITY_STRING` + `GROUP_CITY_MAP` from `routes.py:2057-2065`; delete `scripts/enumerate_fb_groups.py`; re-point `seed_fb_groups.py` at `vm-scraper/groups.json`
- **Harden:** `vm-scraper/run.py` — new `--dry-run` flag, selector-drift detection, hard-fail when `PROXY_URL` missing (no warn-and-proceed)
- **Schedule:** systemd timer (Alan picked over cron) with `OnCalendar=*-*-* 08:00:00`, `RandomizedDelaySec=300`, `Restart=on-failure RestartSec=600 StartLimitBurst=2`
- **Probation:** `FB_SCANS_PER_DAY=1` for 14 days, then flip to 2

Open decisions before `/exec`:
1. **Proxy vendor** — Smartproxy ~$5–15/mo recommended (lowest-cost legit residential). Alan said "gold standard for free" — flagged as not possible; alternatives are Bright Data (~$15–45/mo) or no proxy (high FB ban risk on Oracle VM IP).
2. **Retroactive city normalization** of 1,952 existing `properties.address_city` rows. Alan said "every point of data needs to be accurate" → likely yes; planner didn't include the migration in the printed brief, needs to be added before `/exec`.

Prereqs Alan owns: buy proxy → prep FB account (member of 5 TLV groups + 2FA on) → verify VM SSH → set Render env (`FB_INGESTION_ENABLED=false`, `FB_SCANS_PER_DAY=1`).

Then: `/review` → `/exec` → manual dry-run on VM → install systemd timer → flip flag.

---

## FB UX POLISH (post-A2 follow-ups)

### FilterBar — Facebook source option missing
`frontend/src/components/FilterBar.tsx:124-126` only offers "All sources / Yad2 / Madlan". Once FB ingestion is live, add `<option value="facebook">Facebook</option>`. "All sources" already includes FB rows, so this is dropdown-only UX.

### Apply `normalize_city()` across Yad2/Madlan ingest + filters
After A2 ships and the canonical is proven stable, extend the normalizer to:
- `pdis/scraper.py:182` — Yad2 `item.get("city")` on ingest
- `pdis/scraper_madlan.py:250` — Madlan `addr.get("city")`
- Any route that filters `properties.address_city` by string equality
Goal: one canonical value per city across all sources.

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

### 🔍 Haifa Buy preset — "Last scan blocked — source returned nothing" (investigate tomorrow)
Screenshot flagged by Alan Apr 15 late: `Haifa Buy` preset (Yad2, All neighborhoods, Active) shows *"Last scan blocked — source returned nothing"*.

**Leading hypothesis:** it's a Yad2 forsale preset → `/forsale` IP-blocked on Render by ShieldSquare → scrape returns empty → scanner marks session blocked. The fix path is the Oracle VM (`vm-scraper/run_yad2.py` + `YAD2_VM_INGESTION_ENABLED=true`), which is the same unfinished A2-adjacent work as FB.

**But two oddities to verify first:**
1. Why is there a **Haifa** preset at all? PDIS is Tel Aviv–focused. Is this a test preset or Alan's personal use?
2. If forsale scraping is broken on Render, *all* forsale presets should be blocked. Is this the only forsale preset currently active? Check `SELECT * FROM search_presets WHERE is_active AND extra_params->>'source' LIKE '%forsale%'` (approximate — verify actual schema).

**First steps tomorrow:**
- List all active presets, grouped by source + city, to see the scope of the problem.
- Check last 2-3 `scan_sessions` rows for Haifa Buy — what was the exact HTTP status / error body from Yad2?
- If every forsale preset is blocked → same fix as FB (VM cron, flag flip).
- If only Haifa is blocked → dig into Haifa-specific request params (city code, geofence).

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
