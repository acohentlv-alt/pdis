# PDIS — Task List
*April 16, 2026 (after day session + late-afternoon investigation — fire-and-forget LIVE-tested, debug endpoint shipped, VM retry shipped)*

---

## AWAITING QA / VERIFICATION

### Today's shipped work — still needs eyes
- **Fire-and-forget ingest** (`60fc1fd`) — scraper agent's fix. Tomorrow morning's 08:00 Yad2 VM run is the real test: all 6 presets should now POST cleanly without HTTP 500 on 240-listing payloads. Preset 13 (Villas, 4 listings) should no longer get silently dropped. Monitor `/api/scan/sessions`.
- **Low-volume guard per-preset** (`0de9b52`) — applies per-source: FB keeps 10% threshold; Yad2/Madlan only reject empty batches. Verify small presets (Villas) actually land rows.
- **DB-backed scan lock** (`7a6fb60`) — replaced module-level `_scan_running` with `scan_sessions.status='running'` check. 30-min stale window. If Render restarts mid-scan, the next cron fires without locking itself.
- **events.py N+1 fix** (`7a6fb60`) — ~200 DB roundtrips/scan eliminated by LEFT JOIN on `properties` in the detection CTE. Logic unchanged.
- **Open Search → Custom Search pill** (`f484b5a`) — quirky-heyrovsky agent. Results render as URL-driven `?custom=` on the main dashboard; `/search/results` page removed. Needs iPhone tap-through.

### 12:30 IDT live test — DID run (correction to earlier handoff claim)
Fired all three sources together via SSH + curl:
- **Madlan via Render scheduled scan** ✅ s176 done, 1207 listings, 275 new
- **Yad2 VM (6 presets, 240 listings each)** — **4/6 ✅, 2/6 ❌** silently lost. ✅ presets 8, 12, 13 (first time Villas worked!), 23. ❌ presets 9 + 11 returned HTTP 500 from Render's synchronous handler — no session created, data lost. Reproduction attempts from MacBook all returned 200 in <0.5s, so 500s appear to be transient Render-side state (worker recycling, brief pool contention, etc.) not a deterministic code bug.
- **Facebook VM** ❌ Apify returned **HTTP 402 Payment Required** — Apify credits exhausted. **Top up needed** for tomorrow's 10:00 IDT run.

### Late-afternoon shipped — needs eyes tomorrow morning
- **`/api/debug/recent-errors`** (`ebe4b11`) — temporary diagnostic. Captures every unhandled FastAPI exception (with traceback) into an in-memory ring buffer of size 50. If a 500 fires tomorrow at 08:00 IDT, `curl https://pdis-lsah.onrender.com/api/debug/recent-errors` returns it. **Should be removed or gated behind a debug flag once we understand the root cause.**
- **VM-side retry on 5xx** (`5209985`) — `vm-scraper/run_yad2.py` and `vm-scraper/apify_to_pdis.py` now retry up to 3 times with 60s wait between attempts. 4xx responses are treated as permanent (no retry). Already deployed to Oracle VM at `/opt/pdis-yad2-scraper/run_yad2.py` and `/opt/pdis-fb-scraper/apify_to_pdis.py`. Trades a few extra minutes of run time on flaky days for near-zero silent data loss. **Tomorrow's 08:00 IDT VM run is the real test.**
- **CLAUDE.md cron schedule corrected** (`85bebd9`) — was "08:00 and 18:00 IDT", actually fires at **10:00 IDT** (verified from cron-job.org dashboard screenshot). Second daily slot, if any, still unconfirmed — Alan to verify on dashboard.

### From prior sessions — still pending Alan's eyes
- **PresetManager 2030-vision redesign** (commit `c66e7b7`) — manual iPhone QA per checklist in `TASKS_2026-04-15_night2.md`.
- **Phones across sources** (commit `508cada`) — Madlan phones populated on today's 08:00 scan. Yad2 phones still gated behind `YAD2_PHONE_FETCH_ENABLED=false` — flip on Render when ready.
- **Filter drawer + UI polish** (commit `508cada`) — needs mobile eye-test (drawer animation, toasts, pull-to-refresh, empty-state CTA).
- **Scan button UX + progress bar** — shipped earlier, still needs manual test.

---

## READY TO RUN (Alan's hands)

### Govmap full backfill
Unchanged. Covers 4.5% of TLV/Haifa only. SSH to VM, check `govmap` tmux session, resume `run_govmap.py --resume`. Several hours.

### Flip `YAD2_PHONE_FETCH_ENABLED=true` on Render
Activates the Yad2 click-to-reveal phone fetcher. Brief #2's behavior gate.

### Enter Florentin rent feature adjustments via unlocked UI
Shipped `0f97418` unlocked Pricing Targets + Feature Adjustments for rent presets in PresetManager. Amit's rent-side modifiers are NOT yet in DB:
- Parking in rent: +500-1000 ₪/month
- Mamad in rent: +600 ₪/month
- Elevator / walk-up-floor effect on rent price
Open a rent preset (e.g., "TLV Rent - Madlan" or "TLV Rent - Full Scan") in the preset editor, scroll to "Feature Adjustments (Amit Fit)", enter values, save. 5-min task.

---

## NOT STARTED

### 🆕 PresetManager — "Show hidden presets" toggle
Today's commit `0de9b52` filters disabled presets out of the PresetManager list. When Alan toggles a preset OFF (green switch), it disappears entirely — looks like deletion even though `is_active=FALSE` keeps the row safe. No UI path to recover a hidden preset.
Fix: add a small "Show hidden" toggle at the top of PresetManager (default OFF). When ON, list also renders disabled presets greyed out so Alan can re-enable them. Backend already supports it — `GET /api/presets?active=false` or similar. `/plan → /review → /exec`.

### 🆕 Yad2 description placeholder garbage
Yad2's feed API returns some descriptions with unresolved template tokens like `$HomeNum`, `$Floor_text`, `$TotalFloor_text`, `$FurnitureInfo`, `$Tadiran_text`, `$PandorDoors_text`, etc. Our `pdis/scraper.py` stores them raw. Example: property `25u9w93o` (Florentin rent 5200₪/63m²) — description is mostly unreadable placeholder soup in the first paragraph. Two fix approaches:
- **Proper:** substitute tokens with structured Yad2 fields we already have (`floor`, `floor_count`, `furniture_info`, etc.) inside `scraper.py`'s description extraction.
- **Crude:** strip anything matching `\$[A-Za-z_]+\$?` from description before storing.
Needs its own `/plan → /review → /exec` cycle.


### 🧹 Playwright-era cleanup — delete `vm-scraper/run.py` + fix `tests/test_fb_parser.py`
Today's work handled the peripheral cleanup (`export_fb_cookies.py`, `enumerate_fb_groups.py`, `cleanup_fb_broken_rows.py`, 147-line WIP in run.py, stale `:388` reference). The big piece remains:
- **Delete `vm-scraper/run.py`** (455 lines of Playwright scaffolding) and update `vm-scraper/run.sh` to invoke `apify_to_pdis.py`. Kills the whole legacy pipeline.
- **Fix `tests/test_fb_parser.py`** — imports helpers (`_extract_price` etc.) from `run.py`. Move them to `llm_parse.py` / `apify_to_pdis.py`, or delete the tests if they cover dead code.

### 🆕 FB city bleed — non-TLV posts mislabeled as TLV
Unchanged from this morning's TASKS. FB posts from Kfar Saba etc. get `address_city='תל אביב יפו'` because `vm-scraper/apify_to_pdis.py` hardcodes city per group via `GROUP_CITY_MAP`. Two fix options: (a) trust Haiku's neighborhood detection, skip posts where neighborhood is null AND text lacks TLV keywords; (b) add `default_city` column to `fb_groups` + validate Haiku output. Alan's call.

### 🆕 FB volume guard always rejects daily batch
Discovered during late-afternoon investigation. The `source=='facebook'` branch of the low-volume guard (`scanner.py:803-833`) computes threshold = `max(10, prior_count * 0.1)`. With **689 active FB rows**, threshold = **68**. The typical daily FB batch after Apify scraping + filtering is **10-15 posts**. So FB ingest **gets `suspicious_low_volume` and silently drops every day**. Reset the threshold for FB or use a different scraper-failure signal (e.g., compare against rolling 7-day median, or just trust any non-empty batch like we do for Yad2/Madlan now). Today's 10:00 IDT FB run hit this even before Apify ran out of credits.

### 🆕 Mystery error — investigate (low priority)
Session `s194` from late-afternoon reproduction has `error_message="server conn crashed?"`. That string doesn't exist anywhere in the codebase or git history. May be a manual annotation from a parallel session. Worth a glance tomorrow but not blocking.

### 🆕 Remove or gate `/api/debug/recent-errors`
Shipped today as a temporary diagnostic (`ebe4b11`). Once the intermittent ingest 500s are fully understood and fixed, remove this endpoint or gate it behind a `DEBUG_ENDPOINTS_ENABLED` env flag.

### 🧭 STRATEGIC — 7 bigger bets from Apr 15 product analysis
Carry-forward unchanged. Priority order by leverage:
1. **Telemetry** (2h) — wire event logging before building more. Monday-morning priority.
2. **"Since yesterday" daily feed** (1-2d) — default view = timeline of changes since last visit.
3. **Push notifications (web PWA)** (2-3d) — biggest "Shechter feel" lift.
4. **Phone reveals as North Star metric** — needs telemetry deployed 30 days first.
5. **Signals as narrative, one headline per card** (0.5d) — card UX lift.
6. **Ingest health dot in header** (0.5d) — green/yellow/red, data already in `ingest_state`.
7. **Tests on signals/matching/events** (3d) — zero coverage today on the 3 modules that decide what Shechter sees.

### 💰 Consolidate on Oracle VM — kill Render (post-A2)
Unchanged. Rule: after FB pipeline proven stable 1+ week.

### Amit Fit — add rent/buy toggle + expand thresholds
4 sub-items unchanged. Alan needs to pick interpretation for 30% cap (display-time filter vs auto-derive max=pref×1.30).

### Telegram bot for scan alerts
Alerts when notable properties found post-scan.

### F6 — Neighborhood pulse (24-month ₪/m² sparkline)
Depends on full-city govmap backfill + Amit thresholds for more neighborhoods.

### 📱 Mobile polish pass (queued from today's critique)
Shechter uses PDIS exclusively on iPhone. Separate brief needed:
- Empty-state messaging when filters match nothing (today: blank list, no explanation)
- Loading skeletons (today: list flashes empty then appears)
- SummaryBar stat-card clickability discoverability (today: they filter but nothing hints at it — 44px tap targets + active state)
- PropertyCard signal density on 375px (wrap awkwardly when 5+ signals; collapse to "+3 more" pill)
- PresetManager as bottom sheet (today: modal, painful on mobile)
- PropertyDetailPage govmap comps panel as stacked cards (today: likely a table, unreadable)

### 🔎 Open Search results UX (deferred from today — partly resolved by `f484b5a`)
Quirky-heyrovsky's Custom Search pill refactor addressed the core concern (instant DB query, results on dashboard). Remaining open questions: sort order, pagination, "save this search" affordance. If anything feels off on iPhone, queue `/plan`.

---

## PARKED

### FB Marketplace integration
Different actor from FB Groups. Revisit only if Groups volume insufficient.
