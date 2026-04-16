# PDIS — Task List
*April 16, 2026 (after night2 session — FB dedup + Yad2 VM + FB quality)*

---

## AWAITING QA / VERIFICATION

### Tomorrow's automated runs (need to land cleanly)
- **08:04 IDT — Yad2 VM auto-run.** systemd timer `pdis-yad2-scraper.timer` fires on VM. Should scrape all 6 active Yad2 presets, POST to `/api/ingest/yad2`. Expected per preset: 240 listings (blocked ~p7) for TLV Rent Full Scan / Florentin Buy / Haifa Buy Buildings; 36 for Haifa Buy Small Apts; 4 for TLV Rent Villas. Preset 9 (inactive "Haifa Buy") should be skipped — if it still hits the backend it gets HTTP 500 (known bug, low priority).
- **10:00 IDT — FB Apify auto-run.** With tonight's filters deployed: `intent not in ("rent","sale")` and `confidence<0.3` rejected at ingest. Check log `/var/log/pdis-fb-scraper.log` shows non-property posts being skipped. `SELECT COUNT(*) FROM properties WHERE yad2_id LIKE 'fb_%' AND created_at > NOW() - INTERVAL '2 hours'` should be << 70 (the resultsLimit × groups) because junk posts get dropped.
- **FB cross-source matcher** — after the 10:00 FB ingest, check `SELECT match_tier, COUNT(*) FROM property_matches WHERE match_reason LIKE 'fb_%' GROUP BY 1`. Tonight's test had 1 candidate pair (עולי ציון 38) but floor veto blocked it correctly. Tomorrow more pairs may land.

### From prior sessions — still pending Alan's eyes
- **PresetManager 2030-vision redesign** (commit `c66e7b7`) — needs manual iPhone QA per the checklist in `TASKS_2026-04-15_night2.md`.
- **Phones across sources** (commit `508cada`) — Madlan phones should populate on tomorrow's 08:00 scan. Yad2 phones still gated behind `YAD2_PHONE_FETCH_ENABLED=false` — flip on Render when ready.
- **Filter drawer + UI polish** (commit `508cada`) — needs mobile eye-test (drawer animation, toasts, pull-to-refresh, empty-state CTA).
- **Scan button UX + progress bar** — shipped earlier, needs manual test.

---

## READY TO RUN (Alan's hands)

### Govmap full backfill
Unchanged from yesterday. Covers 4.5% of TLV/Haifa only. To run: SSH to VM, check tmux `govmap` session, resume `run_govmap.py --resume` if stopped. Several hours. See `TASKS_2026-04-14.md` for exact cron block once complete.

### Flip `YAD2_PHONE_FETCH_ENABLED=true` on Render
Activates the Yad2 click-to-reveal phone fetcher. Brief #2's behavior gate.

---

## NOT STARTED

### 🧹 Playwright-era cleanup — `vm-scraper/run.py` + `tests/test_fb_parser.py`
Leftovers from the FB legacy-code cleanup (today's session):
- `vm-scraper/run.py` lines 388 and 431 still reference the deleted `export_fb_cookies.py`. Can't touch now — parallel agent has 147 uncommitted lines in this file. Clean once their work lands.
- `tests/test_fb_parser.py` imports helpers from `vm-scraper/run.py`. If the parallel agent moves those helpers to `llm_parse.py`, tests break. Update imports when that happens.

### 🆕 FB city bleed — non-TLV posts mislabeled as TLV
Tonight's investigation showed FB posts from Kfar Saba etc. get `address_city='תל אביב יפו'` because `vm-scraper/apify_to_pdis.py` uses `GROUP_CITY_MAP` to hardcode city per group. Haiku extracts neighborhood but city goes unchecked. **Two fix options:**
- (a) Trust Haiku's neighborhood detection — skip posts where neighborhood is null AND text doesn't contain TLV keywords.
- (b) Add a `default_city` column to `fb_groups` table + validate Haiku's output against an allowlist.

Option (b) is more correct but takes a brief. Option (a) is a one-liner filter at ingest. Alan's call.

### 🆕 Open Search — results page UX planning
Tonight `/api/scan/open` was fixed to query existing DB (was scraping Yad2 on Render → blocked → "Scan failed"). Now returns 846 matches instantly for TLV rent 2.5-6K. **BUT** the SearchResultsPage UI was built assuming scrape-then-browse. With instant DB query, UX needs a rethink: should results show all matching rows up front? Paginate? Sort differently? Alan asked for a plan on this — **defer, queue a proper `/plan` next session.**

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
Unchanged. Rule: do it after FB pipeline proven stable 1+ week.

### Amit Fit — add rent/buy toggle + expand thresholds
4 sub-items, all unchanged. Alan needs to pick interpretation for the 30% cap (display-time filter vs auto-derive max=pref×1.30).

### Telegram bot for scan alerts
Send alerts when notable properties found after a scan completes.

### F6 — Neighborhood pulse (24-month ₪/m² sparkline)
Depends on full-city govmap backfill + Amit thresholds for more neighborhoods.

---

## PARKED

### FB Marketplace integration
Different actor from FB Groups. Revisit only if Groups volume insufficient.

---

## DONE THIS SESSION (night2, 2026-04-15 → early 2026-04-16 IDT)

- **FB ingest health fix** (`95da8c3`) — removed the A2 phantom-reset migration that wiped `ingest_state.last_ok_at` on every Render cold-start.
- **CLAUDE.md sync** (`fb8b382`) — removed govmap signals that were deleted earlier, documented Apify/Haiku FB pipeline.
- **FB cross-source dedup** (`4773304`) — Brief A (data fidelity: floor, normalize_phone, narrowed migration WHERE) + Brief B (matcher with Tiers 10/11/12, floor veto, rooms veto, Hebrew street normalizer).
- **Yad2 VM scraper** (`e8b2ba1`, `e5d2022`) — extended from forsale-only to rent+forsale; deployed to Oracle VM with systemd timer at 08:04 IDT. Proven working: 1000+ listings scraped tonight across 5 presets, all POSTed HTTP 200 after `YAD2_VM_INGESTION_ENABLED=true` flipped on Render.
- **FB preset visibility** (`a05c9b0`) — removed the `src==facebook` exclusion filter so FB preset shows as a pill.
- **FB preset scope** (`759823f`) — `/api/presets/{id}/properties` now source-scopes to FB only when the viewed preset is FB. Was bleeding Yad2/Madlan rows into the FB view.
- **FB ingest quality** (`c20fbd0`) — added `intent` + `confidence` to FacebookPost model; reject non-property / "wanted" / low-confidence posts at ingest. 103 existing junk rows deleted.
- **FB removal sweep disabled** (`ca608dc`) — Apify sampling ingest is not exhaustive; removal detection was falsely nuking 665 of 689 FB rows. Reactivated them via one-off SQL.
- **Open Search → DB query** (`0b16f95`) — no more Yad2 scrape on submit. Instantly returns matching existing properties from the DB.
- **Data cleanup**:
  - 738 broken FB rows repaired (`source='yad2' → 'facebook'`, phones re-normalized).
  - 103 junk FB rows deleted (no price/rooms/sqm extracted).
  - 665 false-removal FB rows reactivated.
  - Created Madlan preset 44 (`TLV Rent - Madlan`, city 5000, rent, 2-4 rooms, ≤10K). First scrape tonight: 1190 listings, 959 new.
- **Infrastructure**:
  - VM gained 2nd systemd scraper: `pdis-yad2-scraper.timer` (08:04 IDT) alongside `pdis-fb-scraper.timer` (10:00 IDT).
  - Render env flipped: `YAD2_VM_INGESTION_ENABLED=true`.
