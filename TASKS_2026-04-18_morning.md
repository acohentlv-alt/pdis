# PDIS — Task List
*April 18, 2026 (fresh — carried forward from `TASKS_2026-04-18.md`)*

---

## AWAITING QA / VERIFICATION

### Today's shipped work — needs Alan's iPhone test on Render

- **Telemetry v1 — UX bug detector** (`04b5685`) — `/admin/ux-health` page with red/yellow/green sections, 30s auto-refresh, session grouping, NavBar hidden. New `ui_events` table; `POST /api/ui-events` + `GET /api/ui-events/recent-issues`. `/api/log-reveal` hack fully DELETED (replaced by `phone_reveal` event). `apiFetch` instrumented for `api_error` + `slow_response`. React error boundary + window error listeners. `page_view` tracked via StrictMode-safe useRef guard. `empty_state` events on dashboard + favorites. Local QA: 9/10 passed. Verify on iPhone:
  - Hard-refresh PWA, tap around 30 seconds
  - `https://pdis-lsah.onrender.com/admin/ux-health` renders (NO NavBar at bottom)
  - Red errors section: empty or real errors only — if anything weird appears, expand for metadata
  - Green summary strip shows `page_views_24h`, `phone_reveals_24h`, `sessions_24h`
  - Tap phone reveal on a property → event appears in admin page within 30s
  - **Known 0-severity:** `/favorites` fires TWO `page_view` events per visit because it redirects to `/listings`. Admin counts slightly inflated, no data corruption. Cosmetic only.

- **Neon stale-connection pool fix** (`c0d0433`) — Added `check=AsyncConnectionPool.check_connection` + `max_idle=240.0` to the async DB pool. Fixes the "SSL connection closed unexpectedly" errors the `/api/debug/recent-errors` buffer had been catching (17 in 24h prior). Verify:
  - `curl https://pdis-lsah.onrender.com/api/debug/recent-errors | jq '.count'` over next 24h — should stay flat after new traffic, NOT accumulate SSL-closed errors
  - After 24h clean, remove or gate `/api/debug/recent-errors` (separate task in NOT STARTED)

### Still pending from yesterday's (Apr 17) session

- **Split `is_active` into `scan_enabled` + `is_visible`** (`c2682b9`) — PresetManager toggle pattern. Verify on iPhone:
  - Dashboard pills do NOT show presets 9, 12, 13, 44
  - PresetManager "Show hidden" toggle reveals them greyed out
  - Kebab menu shows "Hide from app" / "Show in app"
  - Green dot on each row toggles scan_enabled independently
  - Tomorrow's 08:00 IDT VM run includes Madlan (preset 44 scans) but excludes preset 9
  - Old `?is_active=true` query param still works as deprecated alias

### Still pending from earlier sessions

- **Fire-and-forget ingest** (`60fc1fd`) — monitor tomorrow's 08:00 run.
- **Low-volume guard per-preset** (`0de9b52`) — passive.
- **DB-backed scan lock** (`7a6fb60`) — still needs cron collision to prove itself.
- **events.py N+1 fix** (`7a6fb60`) — passive.
- **Open Search → Custom Search pill** (`f484b5a`) — iPhone tap-through still pending.
- **VM-side retry on 5xx** (`5209985`) — tomorrow's run is the test.
- **CLAUDE.md cron schedule corrected** (`85bebd9`) — verify on cron-job.org dashboard.

### Older unverified

- **PresetManager 2030-vision redesign** (`c66e7b7`) — manual iPhone QA.
- **Phones across sources** (`508cada`) — Madlan phones working; Yad2 still gated behind `YAD2_PHONE_FETCH_ENABLED=false`.
- **Filter drawer + UI polish** (`508cada`) — mobile eye-test.
- **Scan button UX + progress bar** — still needs manual test.

---

## READY TO RUN (Alan's hands)

### 🛑 Shut down FB pipeline — STILL URGENT ($5/day bleed)

Carried from yesterday. Not done during today's session. Two steps:

1. **SSH to Oracle VM** and disable the systemd timer:
   ```
   ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214
   sudo systemctl disable --now pdis-fb-scraper.timer
   ```
2. **Flip `FB_INGESTION_ENABLED=false` on Render** (belt-and-suspenders).

### Git pull on Oracle VM (from yesterday's is_active split)

`vm-scraper/run_yad2.py` now filters on `scan_enabled` instead of `is_active`:

```
ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214
cd ~/vm-scraper && git pull
```

### Enter Florentin rent feature adjustments via unlocked UI

From `0f97418`. Open a rent preset → "Feature Adjustments (Amit Fit)" → enter parking (+500–1000), mamad (+600), elevator/walk-up effect. 5-min task.

### Flip `YAD2_PHONE_FETCH_ENABLED=true` on Render

Activates Yad2 click-to-reveal phone fetcher.

### Govmap full backfill

Covers 4.5% of TLV/Haifa only. SSH to VM → `govmap` tmux session → `run_govmap.py --resume`. Hours.

---

## NOT STARTED

### 🧹 Playwright-era cleanup — delete `vm-scraper/run.py` + fix `tests/test_fb_parser.py`

- Delete `vm-scraper/run.py` (455 lines dead Playwright) + update `vm-scraper/run.sh` to invoke `apify_to_pdis.py`.
- Fix `tests/test_fb_parser.py` — imports helpers from `run.py`.

### 🆕 Remove or gate `/api/debug/recent-errors`

Shipped as temporary diagnostic (`ebe4b11`). After 24h of clean logs post pool fix (`c0d0433`), gate behind `DEBUG_ENDPOINTS_ENABLED` env flag or remove.

### Amit Fit category filter ignored

From Apr 17 QA: `/api/amit-fit/properties?category=rent` and `?category=forsale` both return 81 rows. Silent param-ignore. Pre-existing.

### Drop `search_presets.is_active` column

After 1 week of `scan_enabled`/`is_visible` running clean (target: ~Apr 24), drop the column + remove `?is_active` alias.

### 🆕 FB city bleed — non-TLV posts mislabeled as TLV

Moot if FB pipeline shut down (per READY TO RUN above).

### 🆕 FB volume guard always rejects daily batch

Moot if FB pipeline shut down.

### 🆕 Mystery error — investigate (low priority)

Session `s194` has `error_message="server conn crashed?"`. String doesn't exist in codebase.

### 🆕 Fix double `page_view` on redirect aliases (LOW priority)

Today's telemetry fires TWO `page_view` events when navigating to `/favorites` because it redirects to `/listings`. Fix options: debounce with 50ms window, OR hardcode alias list. Cosmetic — admin counts slightly inflated. Only worth doing if admin page becomes noisy.

### 🧹 Clean test/QA `ui_events` from prod DB

Today's QA session left synthetic events in the `ui_events` table with session_ids starting with `qa-session-`, `qa_test`, etc. Low priority — they won't pollute real metrics since the admin page filters by severity and these are mostly `info`. Optional cleanup:
```sql
DELETE FROM ui_events WHERE session_id LIKE 'qa-%' OR event_name LIKE 'qa_%';
```

### 🧭 STRATEGIC — remaining bets from Apr 15 product analysis

1. **~~Telemetry~~ ✅ SHIPPED today** (`04b5685`) — as UX bug detector rather than conversion analytics.
2. **"Since yesterday" daily feed** (1-2d).
3. **Push notifications (web PWA)** (2-3d).
4. **Phone reveals as North Star metric** — telemetry now captures `phone_reveal`, need 30 days of data before validating.
5. **Signals as narrative, one headline per card** (0.5d).
6. **Ingest health dot in header** (0.5d).
7. **Tests on signals/matching/events** (3d).

### 💰 Consolidate on Oracle VM — kill Render (post-A2)

Moot if FB killed.

### Amit Fit — expand thresholds to more neighborhoods

Data-only task. Amit dictates, Alan enters via unlocked PresetManager UI.

### Telegram bot for scan alerts

Alerts when notable properties found post-scan.

### F6 — Neighborhood pulse (24-month ₪/m² sparkline)

Depends on full govmap backfill + Amit thresholds.

### 📱 Mobile polish pass (queued from Apr 16 critique)

Separate brief needed:
- Empty-state messaging when filters match nothing
- Loading skeletons
- SummaryBar stat-card discoverability
- PropertyCard signal density on 375px (5+ signals wrap awkwardly)
- PresetManager as bottom sheet
- PropertyDetailPage govmap comps panel as stacked cards

### 🔎 Open Search results UX

Remaining after Custom Search pill: sort order, pagination, "save this search".

---

## PARKED

### FB Marketplace integration

Revisit only if Groups volume insufficient AND FB pipeline kept alive.

---

*Archived sessions:*
- *TASKS_2026-04-18.md — start-of-Apr-18 state (= Apr 17 evening end-state before today's session).*
- *TASKS_2026-04-17.md — Apr 17 (post-is_active-split).*
- *TASKS_2026-04-16_evening.md — Apr 16 evening.*
