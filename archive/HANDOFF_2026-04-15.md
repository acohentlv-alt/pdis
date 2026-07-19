# HANDOFF — April 15, 2026

## What we did today

Two big features shipped + pushed to main:

1. **FB groups multi-select preset + sqm regex** (commit `2986523`): new `fb_groups` catalog table, two endpoints (`GET /api/fb-groups` for the catalog, `GET /api/fb-groups/active` for the VM scraper driver), checkbox multi-select inside PresetManager with empty-state message, scanner FB-skip (was dormant bug — would've scraped FB preset as Yad2), PUT `/api/presets` fixed to preserve `fb_groups` on rename (silent-wipe bug caught in review), VM scraper now pulls active groups from API instead of `groups.json`. Plus Hebrew/English sqm regex in `_extract_sqm()` on the scraper — unblocks Amit Fit + below_avg_price signals on FB posts once they land. QA 17/17 after one regex-fix (m2 variant).

2. **Scan button UX + real progress bar** (uncommitted — still on local, see "Watch out for"): click Scan → button reads `Scanning 42%` with live emerald bar, ticks every 1.5s, pulls real percentage from scanner module state (no DB hit on every poll). Other presets disable with "Scan running" while any scan is active. Per-preset `Last scan: Xm ago · N listings` line. Dismissible red error banner for failures. Scheduled/cron scans intentionally have no bar (MVP limit). New `progress` column on `scan_sessions`, `_update_progress()` helper, phase ticks (snapshot=92, events=95, matches=97, signals=99, done=100). Error message scrubber truncates to 200 chars and strips URLs. `PresetRow` extracted as local component — hooks before early return (React #310 burned us 3x; explicit comment in code).

Also ran FB enumeration end-to-end: cookies exported on laptop (fb_state.json, 9 cookies), `scripts/enumerate_fb_groups.py` found 49 groups, `scripts/seed_fb_groups.py` upserted into Neon. Catalog is live — Alan can now open PresetManager and tick groups.

Govmap backfill still running on Oracle VM: ~1843/7676 grid points (24%), 22,694 deals sent, no errors. Will keep chugging overnight.

## What's half-done

### FB groups deployment — catalog seeded, VM scraper not yet running
4 of 6 deployment steps complete:
- [x] Code shipped to Render
- [x] Alan ran `enumerate_fb_groups.py` on laptop (49 groups captured)
- [x] Alan ran `seed_fb_groups.py` against Neon (49 upserted)
- [ ] Alan still needs to tick groups in PresetManager UI (hard-refresh browser first)
- [ ] VM scraper deployment: `scp fb_state.json` to VM, install playwright on VM, test run, install cron at 08:00/18:00 Israel time
- [ ] `FB_INGESTION_ENABLED=true` on Render

Until the last two steps are done and cron fires, zero FB posts will appear in PDIS even with groups ticked.

### ₪/m² math issue on property cards — NOT FIXED
Alan noticed: first property card shows `4,299,999 ₪ · 82m² (95 total) · 52,439 ₪/m²`. The math is using the smaller/build area (82) to compute ₪/m², inflating the rate vs Israeli real estate convention (which uses gross/total area, 95). Should use the larger number, or show both. One-liner fix in PropertyCard.tsx — not touched tonight.

### Govmap backfill — running but slower than initial projection
At 24% after ~4-5h. Extrapolation now: ~20h total (was 8-9h earlier estimate). Will finish overnight or tomorrow. No errors, no action needed — just let it run.

### Scan UX code is on disk but NOT committed
10 modified files sitting uncommitted: `pdis/database.py`, `pdis/scanner.py`, `pdis/scraper.py`, `pdis/scraper_madlan.py`, `pdis/api/routes.py`, `frontend/src/api/client.ts`, `frontend/src/api/queries.ts`, `frontend/src/components/PresetManager.tsx`, `scripts/seed_fb_groups.py` (dict-access bugfix), `TASKS.md`. End-session commit will push these — Render will auto-deploy.

## What to do next

**Highest priority — 5 minutes of Alan's time:**
1. Hard-refresh browser (Cmd+Shift+R) after the end-session push deploys to Render.
2. Open PresetManager → edit the FB preset → see 49 checkboxes → tick the TLV-rental ones (skip Claude community, finance, French security, etc.) → Save.
3. Click Run Now on a Yad2 preset and verify the new scan progress bar works in the deployed UI (it was tested locally; verify on Render).

**Second — the 30-45 min deployment:**
4. SCP `vm-scraper/fb_state.json` to the Oracle VM, install playwright on the VM venv, do a manual test run of `vm-scraper/run.py` to confirm FB ingest end-to-end, then install the twice-daily cron, then flip `FB_INGESTION_ENABLED=true` on Render.

**Third — quick UX polish:**
5. Fix the ₪/m² math in PropertyCard.tsx: prefer gross/total area over build area for the per-sqm rate display. Consider showing both when they differ. One-line change in the component.

**Fourth — govmap backfill wrap-up:**
6. Check backfill status tomorrow. When it hits 100%, verify row count (`SELECT COUNT(*) FROM closed_transactions`) — expect 500k–1M for full TLV. Install the monthly cron on the VM (block already in prior TASKS_2026-04-14.md).

## Watch out for

- **End-session commit is fat — 10 files, ~400 lines net added.** All reviewed in scan-UX brief, no surprises, but it's a bigger push than usual. Render auto-deploy will take ~3 min after push.

- **FB cookies on laptop (`fb_state.json`) + VM scraper running simultaneously = FB ban risk** once the VM goes live. Rule: stay logged out of FB on your laptop browser, or use a separate profile. Already logged out today — just remember.

- **The FB preset shows zero posts on the dashboard right now.** Not a bug. No ingest has ever happened. Also per commit `9357619`, pure-FB presets are intentionally hidden from the dashboard pill strip — FB listings will surface as FB-badged cards inside mixed-source views once data flows.

- **uvicorn was killed once tonight (`zsh: killed`).** Not OOM (checked macOS jetsam logs — clean). Probably a `--reload` worker fluke. If running local dev, skip `--reload` until a pattern emerges: `python3 -m uvicorn pdis.api.main:app --port 8000`.

- **Govmap rework scope (drop averages, show raw building-level deals) is still planned but not touched.** Alan approved Option 2 — show last 3-5 raw closed sales per building, no neighborhood medians. Not started because FB groups took the session. That's the next big feature after FB is flowing.

- **Seed script had a bug** (`row[0]` vs `row["was_inserted"]`) caught during Alan's first run — fixed tonight. Included in this commit.

## Test these

- [ ] After Render deploys this commit: click Run Now on a Yad2 preset in the UI. Button shows `Scanning X%`. Progress bar visible. Ticks up smoothly (3s transitions). Finishes at 100%, bar disappears, `Last scan: 0m ago · N listings` line updates.
- [ ] Trigger a scan while another is running → red error banner appears with readable message (not `API error: 409`).
- [ ] Edit the FB preset, tick a few groups, Save. Reopen edit → ticks persist. Rename the preset via PUT, reopen → ticks STILL persist (the regression test for the PUT-wipes-fb_groups bug).
- [ ] Check `SELECT COUNT(*) FROM fb_groups WHERE is_active = TRUE` — expect 49.
- [ ] Once VM scraper is running: `SELECT COUNT(*) FROM properties WHERE source='facebook'` should grow after each scrape run.
- [ ] Govmap: `SELECT COUNT(*) FROM closed_transactions` growing over time, no Antarctica coords (lat should be ~32, lng ~34.7).

## Deployment state cheat-sheet

| Thing | State | Notes |
|---|---|---|
| Render backend | ✅ live | auto-deploys on push |
| FB groups catalog | ✅ seeded | 49 groups in Neon |
| FB preset UI | ⏳ needs hard-refresh | check after Render deploys this commit |
| FB VM scraper | ❌ not deployed | Alan's ~30 min task |
| `FB_INGESTION_ENABLED` | ❌ off | flip after VM cron verified |
| Govmap backfill | 🏃 ~24% | running on VM, tmux session `govmap` |
| Govmap monthly cron | ❌ not installed | after backfill completes |
| ₪/m² math fix | ❌ not started | 1-line change, quick win |
