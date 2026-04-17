# PDIS — Task List
*April 17, 2026 (fresh — carried forward from `TASKS_2026-04-16_evening.md`)*

---

## AWAITING QA / VERIFICATION

### Tonight's shipped work — needs Alan's iPhone test on Render (deploys ~20 min after push)
- **Amit Fit pill split** (`0f97418`) — two pills "Amit Fit Rent" + "Amit Fit Buy" replace the single pill. Backend endpoint now accepts `?category=rent|forsale`. Admin UI unlocked: PresetManager's Pricing Targets + Feature Adjustments sections now appear for rent presets too (previously forsale-only). Local QA 6/6 green; verify on Render + iPhone: two green pills visible, Rent pill shows 4 Florentin matches, Buy pill shows ~73, rent preset editor shows the Amit sections.
- **Show hidden presets toggle** (`1988ecf`) — new "Show hidden" toggle at top of PresetManager. OFF by default, resets on modal close. ON shows deactivated presets greyed at 60% opacity with their green switch still tappable. Local QA 12/12 green (including the close/reopen reset). Verify on iPhone: opening the modal shows "N active" counter; tapping toggle shows "N active · M hidden"; greyed rows are still tappable to re-enable.
- **Yad2 description token cleanup** (`80aa479`) — scraper now strips `$HomeNum`, `$Floor_text`, `$FurnitureInfo`, etc. from descriptions at ingest. Live scan session 197 already cleaned 6 previously-rotten rows. 141 yad2 rent + 119 forsale still rotten — will clean organically as they're re-scraped in future runs. Verify: after tomorrow's 08:00 IDT Yad2 VM run, the rotten-count in DB should drop further.

### Still pending from earlier sessions
- **Fire-and-forget ingest** (`60fc1fd`) — tomorrow's 08:00 IDT Yad2 VM run is still the first real end-to-end test. If any preset is `error` or stuck `running` past 30 min, fire-and-forget has a regression.
- **Low-volume guard per-preset** (`0de9b52`) — verify small presets (Villas) actually land rows.
- **DB-backed scan lock** (`7a6fb60`) — needs a mid-scan cron collision to prove itself.
- **events.py N+1 fix** (`7a6fb60`) — passive verification on next scan cycle (should just be faster).
- **Open Search → Custom Search pill** (`f484b5a`) — iPhone tap-through still pending.
- **VM-side retry on 5xx** (`5209985`) — tomorrow's 08:00 IDT Yad2 VM run is the real test.
- **`/api/debug/recent-errors`** (`ebe4b11`) — temporary diagnostic. Capture any 500 trace tomorrow morning, then remove/gate.
- **CLAUDE.md cron schedule corrected** (`85bebd9`) — second daily slot still unconfirmed; verify on cron-job.org dashboard.
- **12:30 IDT live test** — 2/6 Yad2 presets (9, 11) silently lost. Tomorrow's auto-run confirms whether the transient 500 is recurring. Apify credits hit 402 — **top up needed**.

### Older unverified
- **PresetManager 2030-vision redesign** (commit `c66e7b7`) — manual iPhone QA per checklist in `TASKS_2026-04-15_night2.md`.
- **Phones across sources** (commit `508cada`) — Madlan phones working. Yad2 phones still gated behind `YAD2_PHONE_FETCH_ENABLED=false`.
- **Filter drawer + UI polish** (commit `508cada`) — needs mobile eye-test.
- **Scan button UX + progress bar** — still needs manual test.

---

## READY TO RUN (Alan's hands)

### Top up Apify credits
Dashboard at apify.com. HTTP 402 killed today's 10:00 IDT FB run. Without this, tomorrow's FB scan fails before it starts.

### Enter Florentin rent feature adjustments via unlocked UI
Shipped `0f97418` unlocked Pricing Targets + Feature Adjustments for rent presets in PresetManager. Amit's rent-side modifiers still not in DB:
- Parking in rent: +500–1000 ₪/month
- Mamad in rent: +600 ₪/month
- Elevator / walk-up-floor effect on rent price

Open a rent preset (e.g., "TLV Rent - Madlan" or "TLV Rent - Full Scan") in the preset editor, scroll to "Feature Adjustments (Amit Fit)", enter values, save. 5-min task.

### Flip `YAD2_PHONE_FETCH_ENABLED=true` on Render
Activates the Yad2 click-to-reveal phone fetcher.

### Govmap full backfill
Covers 4.5% of TLV/Haifa only. SSH to VM, check `govmap` tmux session, resume `run_govmap.py --resume`. Several hours.

---

## NOT STARTED

### 🧹 Playwright-era cleanup — delete `vm-scraper/run.py` + fix `tests/test_fb_parser.py`
- **Delete `vm-scraper/run.py`** (455 lines of Playwright scaffolding) and update `vm-scraper/run.sh` to invoke `apify_to_pdis.py`. Kills the whole legacy pipeline.
- **Fix `tests/test_fb_parser.py`** — imports helpers (`_extract_price` etc.) from `run.py`. Move them to `llm_parse.py` / `apify_to_pdis.py`, or delete the tests if they cover dead code.

### 🆕 FB city bleed — non-TLV posts mislabeled as TLV
FB posts from Kfar Saba etc. get `address_city='תל אביב יפו'` because `vm-scraper/apify_to_pdis.py` hardcodes city per group via `GROUP_CITY_MAP`. Two fix options: (a) trust Haiku's neighborhood detection, skip posts where neighborhood is null AND text lacks TLV keywords; (b) add `default_city` column to `fb_groups` + validate Haiku output. Alan's call.

### 🆕 FB volume guard always rejects daily batch
The `source=='facebook'` branch of the low-volume guard (`scanner.py:803-833`) computes threshold = `max(10, prior_count * 0.1)`. With **689 active FB rows**, threshold = **68**. Typical daily FB batch after Apify scraping + filtering is **10–15 posts**. FB ingest gets `suspicious_low_volume` and silently drops every day. Reset the threshold for FB or use a different scraper-failure signal (rolling 7-day median, or just trust any non-empty batch).

### 🆕 Mystery error — investigate (low priority)
Session `s194` has `error_message="server conn crashed?"`. That string doesn't exist anywhere in the codebase or git history. Worth a glance tomorrow but not blocking.

### 🆕 Remove or gate `/api/debug/recent-errors`
Shipped today as a temporary diagnostic (`ebe4b11`). Once intermittent ingest 500s are fully understood, remove this endpoint or gate it behind a `DEBUG_ENDPOINTS_ENABLED` env flag.

### 🧭 STRATEGIC — 7 bigger bets from Apr 15 product analysis
1. **Telemetry** (2h) — wire event logging before building more. Monday-morning priority.
2. **"Since yesterday" daily feed** (1-2d) — default view = timeline of changes since last visit.
3. **Push notifications (web PWA)** (2-3d) — biggest "Shechter feel" lift.
4. **Phone reveals as North Star metric** — needs telemetry deployed 30 days first.
5. **Signals as narrative, one headline per card** (0.5d) — card UX lift.
6. **Ingest health dot in header** (0.5d) — green/yellow/red, data already in `ingest_state`.
7. **Tests on signals/matching/events** (3d) — zero coverage on the 3 modules that decide what Shechter sees.

### 💰 Consolidate on Oracle VM — kill Render (post-A2)
Rule: after FB pipeline proven stable 1+ week.

### Amit Fit — expand thresholds to more neighborhoods
Rent/buy toggle shipped tonight. Remaining work: seed `neighborhood_thresholds` rows for TLV neighborhoods beyond Florentin (Neve Tzedek, Kerem, Rothschild, Nahalat Binyamin, etc.). Best route: Alan sits with Amit, dictates numbers, Alan enters them via the now-unlocked PresetManager UI for each rent and forsale preset. Zero code change needed — data-only task.

### Telegram bot for scan alerts
Alerts when notable properties found post-scan.

### F6 — Neighborhood pulse (24-month ₪/m² sparkline)
Depends on full-city govmap backfill + Amit thresholds for more neighborhoods.

### 📱 Mobile polish pass (queued from Apr 16 critique)
Shechter uses PDIS exclusively on iPhone. Separate brief needed:
- Empty-state messaging when filters match nothing
- Loading skeletons
- SummaryBar stat-card clickability discoverability
- PropertyCard signal density on 375px (5+ signals wrap awkwardly)
- PresetManager as bottom sheet (today: modal, painful on mobile)
- PropertyDetailPage govmap comps panel as stacked cards

### 🔎 Open Search results UX (deferred — partly resolved by `f484b5a`)
Quirky-heyrovsky's Custom Search pill addressed the core concern. Remaining: sort order, pagination, "save this search" affordance.

---

## PARKED

### FB Marketplace integration
Different actor from FB Groups. Revisit only if Groups volume insufficient.

---

*Archived sessions:*
- *TASKS_2026-04-16.md — Apr 16 morning (pre-day-session). Immutable.*
- *TASKS_2026-04-16_evening.md — Apr 16 after evening session (Amit Fit split + Show hidden toggle + Yad2 token cleanup). Immutable.*
