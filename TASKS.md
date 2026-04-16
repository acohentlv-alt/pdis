# PDIS — Task List
*April 16, 2026 (after day session — stale code cleanup + backend quick wins + fire-and-forget ingest)*

---

## AWAITING QA / VERIFICATION

### Today's shipped work — still needs eyes
- **Fire-and-forget ingest** (`60fc1fd`) — scraper agent's fix. Tomorrow morning's 08:00 Yad2 VM run is the real test: all 6 presets should now POST cleanly without HTTP 500 on 240-listing payloads. Preset 13 (Villas, 4 listings) should no longer get silently dropped. Monitor `/api/scan/sessions`.
- **Low-volume guard per-preset** (`0de9b52`) — applies per-source: FB keeps 10% threshold; Yad2/Madlan only reject empty batches. Verify small presets (Villas) actually land rows.
- **DB-backed scan lock** (`7a6fb60`) — replaced module-level `_scan_running` with `scan_sessions.status='running'` check. 30-min stale window. If Render restarts mid-scan, the next cron fires without locking itself.
- **events.py N+1 fix** (`7a6fb60`) — ~200 DB roundtrips/scan eliminated by LEFT JOIN on `properties` in the detection CTE. Logic unchanged.
- **Open Search → Custom Search pill** (`f484b5a`) — quirky-heyrovsky agent. Results render as URL-driven `?custom=` on the main dashboard; `/search/results` page removed. Needs iPhone tap-through.

### 12:10 IDT live test — NOT executed today
Was planned but skipped when we ran past the window (deploy finished ~12:53). Tomorrow's 08:00 IDT automated run becomes the real first test of fire-and-forget.

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

---

## NOT STARTED

### 🧹 Playwright-era cleanup — delete `vm-scraper/run.py` + fix `tests/test_fb_parser.py`
Today's work handled the peripheral cleanup (`export_fb_cookies.py`, `enumerate_fb_groups.py`, `cleanup_fb_broken_rows.py`, 147-line WIP in run.py, stale `:388` reference). The big piece remains:
- **Delete `vm-scraper/run.py`** (455 lines of Playwright scaffolding) and update `vm-scraper/run.sh` to invoke `apify_to_pdis.py`. Kills the whole legacy pipeline.
- **Fix `tests/test_fb_parser.py`** — imports helpers (`_extract_price` etc.) from `run.py`. Move them to `llm_parse.py` / `apify_to_pdis.py`, or delete the tests if they cover dead code.

### 🆕 FB city bleed — non-TLV posts mislabeled as TLV
Unchanged from this morning's TASKS. FB posts from Kfar Saba etc. get `address_city='תל אביב יפו'` because `vm-scraper/apify_to_pdis.py` hardcodes city per group via `GROUP_CITY_MAP`. Two fix options: (a) trust Haiku's neighborhood detection, skip posts where neighborhood is null AND text lacks TLV keywords; (b) add `default_city` column to `fb_groups` + validate Haiku output. Alan's call.

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
