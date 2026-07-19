# PDIS — Task List
*April 18, 2026 (carried forward from `TASKS_2026-04-17.md`)*

---

## AWAITING QA / VERIFICATION

### Today's shipped work — needs Alan's iPhone test on Render
- **Split `is_active` into `scan_enabled` + `is_visible`** (`c2682b9`) — PresetManager now has a scanning toggle (green dot) separate from visibility (kebab menu → "Hide from app" / "Show in app"). Presets 9/12/13/44 backfilled: all hidden from dashboard pills; 12/13/44 still scan daily; preset 9 stays scan-off. Local QA 15/15 passed. Verify tomorrow:
  - Dashboard pills do NOT show presets 9, 12, 13, 44.
  - PresetManager "Show hidden" reveals them greyed out.
  - Kebab menu shows "Hide from app" / "Show in app".
  - Green dot on each row toggles scan_enabled independently.
  - Tomorrow's 08:00 IDT VM run includes Madlan (preset 44 scans) but excludes preset 9.
  - Old `?is_active=true` query param still works as deprecated alias (belt-and-suspenders for any old caller).

### Still pending from earlier sessions
- **Fire-and-forget ingest** (`60fc1fd`) — today's 08:00 run had 4/4 active Yad2 presets clean. Monitor next run.
- **Low-volume guard per-preset** (`0de9b52`) — passive verification only.
- **DB-backed scan lock** (`7a6fb60`) — still needs cron collision to prove itself.
- **events.py N+1 fix** (`7a6fb60`) — passive.
- **Open Search → Custom Search pill** (`f484b5a`) — iPhone tap-through still pending.
- **VM-side retry on 5xx** (`5209985`) — tomorrow's run is the test.
- **`/api/debug/recent-errors`** (`ebe4b11`) — temporary. Remove or gate after today's issues resolved.
- **CLAUDE.md cron schedule corrected** (`85bebd9`) — verify on cron-job.org dashboard.

### Older unverified
- **PresetManager 2030-vision redesign** (`c66e7b7`) — manual iPhone QA.
- **Phones across sources** (`508cada`) — Madlan phones working; Yad2 still gated behind `YAD2_PHONE_FETCH_ENABLED=false`.
- **Filter drawer + UI polish** (`508cada`) — mobile eye-test.
- **Scan button UX + progress bar** — still needs manual test.

---

## READY TO RUN (Alan's hands)

### 🛑 Shut down FB pipeline — URGENT ($5/day bleed)
Alan flagged Apify is burning $5/day. Two steps to stop it:
1. **SSH to Oracle VM** and disable the systemd timer:
   ```
   ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214
   sudo systemctl disable --now pdis-fb-scraper.timer
   ```
2. **Flip `FB_INGESTION_ENABLED=false` on Render** (belt-and-suspenders; Apify is what costs money, but this stops ingest too).

### 🆕 Git pull on Oracle VM (for today's ship)
`vm-scraper/run_yad2.py` now filters on `scan_enabled` instead of `is_active`. Until VM pulls, it still uses old field (will still work because backfill keeps `is_active` TRUE for everything scan-enabled, but cleaner to pull):
```
ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214
cd ~/vm-scraper && git pull
```

### Top up Apify credits (ONLY if FB pipeline kept alive)
Dashboard at apify.com. Moot if the "Shut down FB pipeline" item above is done.

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

### 🆕 Amit Fit category filter ignored
QA noticed: `/api/amit-fit/properties?category=rent` and `?category=forsale` both return 81 rows. Commit `0f97418` added the param but the implementation silently ignores it. Pre-existing bug unrelated to today's work. Revisit after `is_active` split is proven.

### 🆕 Drop `search_presets.is_active` column
Today kept the column for safety. After 1 week of `scan_enabled`/`is_visible` running clean, drop the column + remove the `?is_active` deprecated alias from `GET /api/presets`.

### 🆕 FB city bleed — non-TLV posts mislabeled as TLV
From earlier. Moot if FB pipeline shut down.

### 🆕 FB volume guard always rejects daily batch
From earlier (`scanner.py:803-833`). Moot if FB pipeline shut down.

### 🆕 Mystery error — investigate (low priority)
Session `s194` has `error_message="server conn crashed?"`. String doesn't exist in codebase.

### 🆕 Remove or gate `/api/debug/recent-errors`
Shipped as temporary diagnostic (`ebe4b11`). Gate or remove once intermittent ingest 500s fully understood.

### 🧭 STRATEGIC — 7 bigger bets from Apr 15 product analysis
1. **Telemetry** (2h) — Monday-morning priority.
2. **"Since yesterday" daily feed** (1-2d).
3. **Push notifications (web PWA)** (2-3d).
4. **Phone reveals as North Star metric** — needs telemetry 30 days first.
5. **Signals as narrative, one headline per card** (0.5d).
6. **Ingest health dot in header** (0.5d).
7. **Tests on signals/matching/events** (3d).

### 💰 Consolidate on Oracle VM — kill Render (post-A2)
Rule: after FB pipeline proven stable 1+ week. Moot if FB killed.

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
Quirky-heyrovsky's Custom Search pill addressed the core. Remaining: sort order, pagination, "save this search".

---

## PARKED

### FB Marketplace integration
Different actor from FB Groups. Revisit only if Groups volume insufficient AND FB pipeline kept alive.

---

*Archived sessions:*
- *TASKS_2026-04-17.md — Apr 17 (carry-forward state from Apr 16 + today's shipped work).*
- *TASKS_2026-04-16_evening.md — Apr 16 evening.*
