# PDIS — Task List
*July 13, 2026 (fresh — carried forward from `TASKS_2026-07-12.md`)*

> **⚠️ PROJECT STATUS: FROZEN (since June 2026).** VM scrapers off, Render suspended, Neon Free. Nothing runs automatically — intentional. **Exec A (commit `6160c58`) is on main but NOT deployed; its neighborhood migration runs on prod automatically at unfreeze.**

---

## 🗺️ ROADMAP
- ✅ Exec A (Phase 1) — canonical hoods + property_leads + arm_router (6160c58, on main, not deployed)
- ⬜ Exec B (Phase 3) — hidden /leads routing UI (decision-complete, launches on "exec b")
- ⬜ Yad2-on-Render fallback removal (Option A: reduce scraper.py to fetch_item_detail)
- ⬜ Unfreeze + prod deploy — verify neighborhood backfill migration on prod

---

## 📊 RENT BENCHMARKS — CBS + Madlan (dormant while frozen)
*Added 2026-08-11. Full reasoning + sources in `docs/rent-benchmarks-cbs.md`. Goal: give the `below_avg_price` signal and `neighborhood_thresholds` an independent, real-rent reference layer instead of a baseline derived from the same scraped asking data.*
- ⬜ [L1] Pull the exact **CBS Table 4.9** Tel Aviv-Yafo rent-by-rooms figures (quarterly) and replace the secondary/aggregator ₪ numbers currently in `docs/rent-benchmarks-cbs.md`. Source URL is in that doc. CBS averages are magnitude-indicators only — never use for % change (their rule), never as a per-neighborhood benchmark (city-level only).
- ⬜ [L3] Add a **city-level CBS sanity check** to the `below_avg_price` baseline in `signals.py`: flag when the scraped Tel Aviv median ₪/m² drifts far from the CBS anchor (baseline drift, not market). Guardrail only — do NOT replace the per-neighborhood baseline. L3 = touches a distress signal (sensitive core logic), review mandatory.
- ⬜ [L2] Seed `neighborhood_thresholds` for all TLV hoods (only Florentin populated today — ties to the "Amit neighborhood threshold data" item under WAITING ON EXTERNAL INPUT) using **median ₪/m² per neighborhood from Madlan `searchDeals` + live listings**. Extraction method proven 2026-08-11 (the `api3` surface `scraper_madlan.py` already uses also exposes sold deals, days-on-market, and urban-renewal status per listing).
- Note: asking→signed rent gap is small (~5%, renewals capped ~2%+index by Fair Rent Law), so asking-based rent signals are high-confidence; the sale-side gap is larger. Keep in mind wherever signals interpret asking prices.

---

## 📌 SESSION ANCHORS (auto-collected)
- **2026-07-08** [review] Bare `הצפון` ("North") is a standalone canonical entry in llm_parse.py:47, ambiguous vs הצפון הישן/החדש — Alan to decide whether it stays a valid canonical (open decision #4 from 07-12; revisit if it pollutes the Leads view) [L2]
- **2026-07-22** [cross-project, found during NZP gap-analysis session] `~/nzp/gap-analysis`'s Yad2 sweep code was copy-adapted from this repo and had a display-URL bug (`/item/` vs `/realestate/item/` — link pointed at the wrong path, not the specific listing). The same pattern exists verbatim in `pdis/scraper.py:130-131` (or the render/display-URL builder near there). Not yet verified whether it's actually reachable/live here given the project is frozen, or already fixed since — worth a quick check whenever PDIS work resumes, before unfreeze [L1]

---

## 🔜 NEXT UP — Exec B (Phase 3: Maison lead routing UI) [L3]
**Ready to launch on Alan's "exec b".** All product decisions locked (07-08: hidden unlinked `/leads` route, status enum, R1–R4 rules, agents included, starter turf list in `pdis/neighborhoods.py::MAISON_TURF`). Scope per the reviewed 07-07 brief:
- `GET /api/leads?status=&arm=&turf=` + `GET /api/leads/suggestions` (register literal routes BEFORE any future `/api/leads/{param}`; do NOT filter `is_active` — delisted = hottest lead)
- `frontend/src/pages/LeadsPage.tsx` + route in App.tsx (unlinked — no NavBar tab per decision 2b), LeadCard (contact reveal, arm badge, status chips), "Maison turf" toggle
- **Fold in:** FB posts with only `group_url` (no `listing_url`) currently render NO "View on" button — add group_url fallback (QA anchor 07-08)
- **Open for Alan:** additions to the starter turf list ("+ Alan's areas" never named)

## 🚧 IN PROGRESS (stalled)

### Yad2-on-Render fallback removal (brief drafting — stalled since Apr 25) [L2]
Findings (verified Apr 25): `fetch_item_detail` is NOT dead (called by `_backfill_built_sqm`, `pdis/scanner.py:388`, feeds `below_avg_price`); VM-skip branch covers only `forsale` (`scanner.py:603-619`), rent falls through to `scrape_preset` at :645. **Alan picked Option A:** reduce scraper.py to `fetch_item_detail` only, delete the rest, broaden VM-skip to rent, fix stale docs. Env cleanup: drop `scrape_delay_*`/`scrape_page_delay_*`; keep `scrape_max_pages`, `scrape_request_timeout`. Needs fresh `/plan` seeded with these findings.

---

## 🛑 WAITING ON EXTERNAL INPUT (dormant while frozen)
- **Amit neighborhood threshold data** — only פלורנטין has `neighborhood_thresholds` rows; need per-hood per-size-bucket targets. Admin UI: `pdis/api/routes.py:2074-2352`. NOTE: post-Exec A, load thresholds under CANONICAL hood names (`pdis/neighborhoods.py`).
- **New Facebook groups** — code ready (PR #2), VM deploy pending; also gated on FB restart decision (Path A self-host vs Apify top-up, see `TASKS_2026-04-25.md`) + unfreeze.

## 🚨 DEPLOY PENDING (dormant while frozen — VM is off)
- **VM deploy for PR #2** (Haiku 5-intent + net/balcony sqm) — commands in `TASKS_2026-07-07.md:94-107`. **Add to same deploy:** sync `vm-scraper/llm_parse.py` canonical hood list with `pdis/neighborhoods.py` (single-sourcing note added 07-07; llm_parse.py now carries a master-pointer comment from Exec A).
- **Historical FB price sweep** (`scripts/fb_price_sweep_20260418.py`) — after VM deploy + one clean scrape.
- **Madlan field probe** (`scripts/madlan_field_probe.py`) — read-only, anytime.

## 🔄 FOLLOW-UPS — stale-conn risk in other loops
- `pdis/scanner.py:_upsert_properties` per-row loop (Neon 5-min idle-kill); apply `executemany` pattern from classification.py fix. Needs `/plan`.
- `pdis/scanner.py:_create_snapshots` ~2400 round-trips / 1194 rows.
- `pdis/matching.py:backfill_year_built_from_buildings` (~:754) per-property loop.

## AWAITING QA / VERIFICATION
- **Exec A migration on PROD** — runs at unfreeze; verify then: distinct hoods 817→~794, `neighborhood_raw` ~1300 rows, signal counts stable (QA-proven on branch 07-12, prod pending).
- PR #3 Render deploy check — unverifiable until unfreeze.
- `scan_enabled`/`is_visible` split — iPhone test never done.
- Telemetry v1, fire-and-forget ingest, low-volume guard, DB scan lock, events.py N+1 — passive.

## NOT STARTED
### 🧹 Stale code cleanup
- Drop `search_presets.is_active` column.
- Payload bloat: `SELECT p.*` in `/api/favorites`, `/api/whitelist`, `/api/blacklist` (`routes.py:1729, 1751, 1890`).
### Small follow-ups (from 07-07 anchors)
- Haifa neighborhood alias map — only if Haifa Buy preset gets real use.
- `property_leads.created_by` actor field — only if partners get their own logins.
### From prior sessions
- `vm-scraper/trigger_server.py` log path configurability · error toast for "Run Yad2 now" · verify Amit Fit category filter · flip `YAD2_PHONE_FETCH_ENABLED` on Render · Govmap full backfill · Custom Search pill · mystery error / double page_view / `ui_events` cleanup.
### 🧭 Strategic bets
"Since yesterday" feed (1-2d) · Push notifications PWA (2-3d) · Phone reveals North Star (~30d telemetry) · Signals as narrative (0.5d) · Ingest health dot (0.5d) · Tests on signals/matching/events (3d)
### 🆕 Golden Sources + Profit Floor
Tier 1 Profit Floor (days) · Tier 2 Vault/Golden Sources (weeks, feasibility spike) · Tier 3 Ultra-Distress (BLOCKED on TABU).

## PARKED
- FB Marketplace · Consolidate on Oracle VM (moot while Render suspended) · Buyer-sourcing feature (scope after Maison validates manual flow; partially realized by the lead-gen pivot).

---

*Archived sessions:*
- *TASKS_2026-07-12.md — Exec A shipped (full loop, QA on Neon branch); Maison lead-gen decisions recorded; anchor roll-up.*
- *TASKS_2026-07-07.md — Apr 25 list + July 7 planning anchors.*
- *TASKS_2026-04-25.md and earlier — see file list.*
