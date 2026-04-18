# PDIS — Task List
*April 18, 2026 evening (fresh — carried forward from `TASKS_2026-04-18_morning.md`)*

---

## AWAITING QA / VERIFICATION

### Today's shipped work — needs iPhone test on Render after deploy

- **List-endpoint payload shrink** (this session's commit) — `SELECT p.*` replaced with an explicit 35-column list in three endpoints: `get_preset_properties`, `get_amit_fit_properties` (fetch only), `custom_search` in [pdis/api/routes.py](pdis/api/routes.py). Drops `raw_data` (9 KB JSONB blob per row) and 18 other unused columns. Local QA passed 7/7: preset 44 payload **8.6 MB → 3.9 MB (-54.6%)**, custom search **10.2 MB → 4.6 MB (-55.6%)**, row counts identical. Detail endpoint untouched (still carries `raw_data`). Verify on iPhone:
  - Open preset 44 (Madlan) on `https://pdis-lsah.onrender.com` — first cards should render in ~2-3s, not 8-14s
  - `/admin/ux-health` should stop accumulating `slow_response` warnings on `/api/presets/%/properties%` over 24h
  - `curl -w "size=%{size_download} time=%{time_total}s" https://pdis-lsah.onrender.com/api/presets/44/properties?per_page=2000` — expect size ~3.9 MB

### Still pending from the morning handoff

- **Telemetry v1** (`04b5685`) — `/admin/ux-health` already verified in Alan's iPhone screenshot today. Red section was only QA test noise (cleaned up). Green section shows `page_views_24h=32, phone_reveals_24h=1, sessions_24h=18`. One real signal caught: the Madlan latency bug, now fixed.
- **Neon stale-connection pool fix** (`c0d0433`) — 24h quiet window ends tomorrow morning. Verify: `curl https://pdis-lsah.onrender.com/api/debug/recent-errors | jq '.count'` stays flat (no new `SSL connection closed unexpectedly`).
- **Split `is_active` → `scan_enabled` + `is_visible`** (`c2682b9`) — backend verified; **Alan has not yet iPhone-tested the PresetManager kebab menu / Show hidden toggle**.
- **VM deploy of new `run_yad2.py`** — **done this session** (git pull on `~/pdis` + `sudo cp` to `/opt/pdis-yad2-scraper/`). Tomorrow's 08:00 IDT run is the first to use the new `scan_enabled` filter + `$HomeNum` stripping.

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

### Optional: disable the failing FB timer

FB scraper is self-failing at 10:02 IDT every day because the Apify free $5 trial is exhausted (confirmed today: `pdis-fb-scraper.service` returns exit 1, was spending $0/day for 8 days). Daily log noise only, no cost. If you want a clean `systemctl status`:
```
ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214
sudo systemctl disable --now pdis-fb-scraper.timer
```

### Git pull on Oracle VM — DONE this session ✅

Was on yesterday's list. Done: `~/pdis` pulled (was 50+ commits behind), `run_yad2.py` copied to `/opt/pdis-yad2-scraper/`, verified on-disk filter is now `scan_enabled`.

### Enter Florentin rent feature adjustments via unlocked UI

From `0f97418`. Open a rent preset → "Feature Adjustments (Amit Fit)" → enter parking (+500–1000), mamad (+600), elevator/walk-up effect. 5-min task.

### Flip `YAD2_PHONE_FETCH_ENABLED=true` on Render

Activates Yad2 click-to-reveal phone fetcher.

### Govmap full backfill

Covers 4.5% of TLV/Haifa only. SSH to VM → `govmap` tmux session → `run_govmap.py --resume`. Hours.

---

## NOT STARTED

### 🆕 Same payload bloat in `/api/favorites`, `/api/whitelist`, `/api/blacklist`

Reviewer flagged that these three endpoints (`pdis/api/routes.py:1709, 1731, 1870`) also `SELECT p.*` and render through the same `PropertyCard`. Out of scope for today's brief but the exact same 35-column swap applies. Plan a follow-up.

### 🆕 New product direction — "companies that need to sell" (הוצאה לפועל / פשיטות רגל)

Alan raised at end-of-session. Needs its own /plan brief: data sources, what "distressed company" means for rental/sale listings, feasibility of scraping execution-office / bankruptcy filings in Israel, how this changes PDIS's scope (currently listing-centric → becomes owner-centric too).

### 🧹 Playwright-era cleanup — delete `vm-scraper/run.py` + fix `tests/test_fb_parser.py`

- Delete `vm-scraper/run.py` (455 lines dead Playwright) + update `vm-scraper/run.sh` to invoke `apify_to_pdis.py`.
- Fix `tests/test_fb_parser.py` — imports helpers from `run.py`.

### Remove or gate `/api/debug/recent-errors`

Shipped as temporary diagnostic (`ebe4b11`). After 24h of clean logs post pool fix (`c0d0433`), gate behind `DEBUG_ENDPOINTS_ENABLED` env flag or remove. Partial: telemetry is now the primary UX-error surface; the `recent-errors` buffer is mostly duplicative.

### Amit Fit category filter ignored

From Apr 17 QA: `/api/amit-fit/properties?category=rent` and `?category=forsale` both return 81 rows. Silent param-ignore. Pre-existing.

### Drop `search_presets.is_active` column

After 1 week of `scan_enabled`/`is_visible` running clean (target: ~Apr 24), drop the column + remove `?is_active` alias.

### 🆕 FB city bleed — MOOT (FB pipeline self-stopped)

### 🆕 FB volume guard always rejects — MOOT

### 🆕 Mystery error — investigate (low priority)

Session `s194` has `error_message="server conn crashed?"`. String doesn't exist in codebase.

### 🆕 Fix double `page_view` on redirect aliases (LOW priority)

Telemetry fires TWO `page_view` events on `/favorites` (redirects to `/listings`). Cosmetic.

### 🧹 Clean test/QA `ui_events` from prod DB — PARTIAL

Session `5d5cfd73...` and `qa-check` events deleted today (19 rows). `qa-%` / `qa_%` prefix patterns still match whatever residual test events exist. Low priority.

### 🧭 STRATEGIC — remaining bets from Apr 15 product analysis

1. ~~Telemetry~~ ✅ SHIPPED Apr 17 — caught the Madlan latency bug on day 1.
2. **"Since yesterday" daily feed** (1-2d).
3. **Push notifications (web PWA)** (2-3d).
4. **Phone reveals as North Star metric** — telemetry captures it; need ~30 days.
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

Revisit only if Groups volume insufficient AND FB pipeline revived.

---

*Archived sessions:*
- *TASKS_2026-04-18_morning.md — Apr 18 morning (carried-forward Apr 17 evening end-state).*
- *TASKS_2026-04-18.md — start-of-Apr-18 (yesterday evening's end-state).*
- *TASKS_2026-04-17.md — Apr 17 post-is_active-split.*
- *TASKS_2026-04-16_evening.md — Apr 16 evening.*
