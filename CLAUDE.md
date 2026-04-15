# PDIS — Claude Code Operating Guide
*Last updated: April 15, 2026 (govmap signals removed, FB Apify pipeline live)*

---

## Golden Rule

Alan is not a coder. Every explanation must be in **plain English**. Explain the WHAT and WHY so Alan can make informed decisions. No jargon without explanation.

**Approval required before editing code.** Explain what you're changing and why, then wait for Alan's go-ahead. He will challenge decisions — be ready to defend or change course.

---

## What PDIS Is

PDIS (Property Distress Intelligence System) is a rental property monitoring tool for the Israeli market. It scans Yad2, Madlan, and Facebook Groups for rental listings in Tel Aviv, tracks them over time, and detects distress signals (price drops, relistings, long time on market, urgent language, etc.). Built for Alan's friend Shechter.

**How it works:** Automated scans run twice daily (08:00 and 18:00 Israel time). Shechter opens the mobile-first web app and sees fresh opportunities — properties where the landlord might be desperate (price dropped, relisted multiple times, been listed too long).

---

## How to Run Locally

```bash
cd ~/pdis
python3 -m uvicorn pdis.api.main:app --port 8000 --reload
# Open http://localhost:8000
```

- Database is on **Neon** (cloud PostgreSQL)
- `.env` has `DATABASE_URL` and `CRON_SECRET`
- Frontend is React (Vite) — build with `cd frontend && npm run build`
- FastAPI serves the built frontend as static files with SPA catch-all routing
- `--reload` picks up backend changes automatically; frontend needs `npm run build`

---

## Tools Available to Claude

**GitHub MCP server** is configured globally in `~/.claude.json` (user scope, added 2026-04-13). For any GitHub repo lookups — pull requests, issues, file contents at a specific commit/branch, commit history — call the `github` MCP tools instead of shelling out to `git`/`gh` or cloning. MCP returns only what you ask for, which keeps token usage down.

Token reuses `gh auth token` (scopes: `repo, gist, read:org, workflow`). If it stops working, rerun:
`TOKEN=$(gh auth token) && claude mcp add github -s user -e GITHUB_PERSONAL_ACCESS_TOKEN="$TOKEN" -- npx -y @modelcontextprotocol/server-github`

---

## Architecture

### Backend (Python FastAPI)

| Module | Purpose |
|--------|---------|
| `pdis/scraper.py` | Yad2 scraper — REST API via curl_cffi with Chrome TLS impersonation |
| `pdis/scraper_madlan.py` | Madlan scraper — GraphQL API via curl_cffi, PerimeterX cookie handling |
| `pdis/scanner.py` | Scan orchestrator — `run_scan()` and `run_all_scans()` pipeline |
| `pdis/signals.py` | Distress signal calculator — strong/weak signal detection |
| `pdis/events.py` | Event detection — compares snapshots between sessions |
| `pdis/classification.py` | Persists signal details to `property_classifications`. No tier labels (no hot/warm/cold). |
| `pdis/matching.py` | Cross-source dedup — coordinates, customer_id, text similarity |
| `pdis/comps.py` | Closed-transaction comps (govmap) per building/neighborhood |
| `pdis/database.py` | Migrations + connection pool |
| `pdis/config.py` | Settings from environment variables |
| `pdis/api/main.py` | FastAPI app + lifespan + SPA routing |
| `pdis/api/routes.py` | All API endpoints (~65) |

### Frontend (React + TypeScript + Vite + Tailwind)

| Page | Route | Purpose |
|------|-------|---------|
| OpportunityPage | `/` | Main dashboard: opportunities/fullscan tabs, SummaryBar, filters. Also aliased at `/rent` and `/buy`. |
| FavoritesPage | `/favorites` | Starred properties |
| SearchPage | `/search` | Ad-hoc search form |
| SearchResultsPage | `/search/results` | Past open search queries + results |
| PropertyDetailPage | `/property/:yad2Id` | Full property detail + signals + timeline |

### Key Components
- **SummaryBar** — Stat cards (Scanned, Opportunities, Ratio, Price Drops, Reappeared). Clickable — filters the list.
- **FilterBar** — Keyword search, neighborhood pills, room pills, source/sort dropdowns
- **PropertyCard** — Property list item with image, badges, signals, favorite star
- **PresetManager** — CRUD modal for managing search presets (via 3-dot menu)
- **ImageViewer** — Fullscreen lightbox with navigation

---

## Data Sources

### Yad2 (primary)
- REST API: `www.yad2.co.il/api/pre-load/getFeedIndex/realestate/rent`
- curl_cffi with Chrome impersonation (anti-bot bypass)
- Returns ~240 listings per preset, paginated
- Rich structured data: rooms, floor, sqm, coordinates, amenities, description

### Madlan (secondary)
- GraphQL API: `https://www.madlan.co.il/api3`
- PerimeterX cookie required (3 retry attempts)
- City filtering done in Python (server-side filtering returns 400)
- Image base URL: `https://images2.madlan.co.il` (NOT images.madlan.co.il)
- Less structured than Yad2 but provides cross-source validation

### Facebook Groups (active)
- Apify actor `apify/facebook-groups-scraper` triggered daily 10:00 IDT by Oracle VM systemd timer (`pdis-fb-scraper.timer` → `/opt/pdis-fb-scraper/run.sh` → `apify_to_pdis.py`)
- Apify provides residential proxies internally — no separate proxy needed
- 14 active TLV rental groups, `RESULTS_PER_GROUP=5` per run (~70 posts/day)
- VM script first GETs `/api/ingest/facebook/existing-ids` to skip LLM parsing on already-seen posts
- Claude Haiku 4.5 (`vm-scraper/llm_parse.py`) extracts structured fields from Hebrew post text (intent, price, sqm, rooms, phone, neighborhood, street/house, is_agent, amenities, available_date)
- POSTs to Render at `POST /api/ingest/facebook` with `INGEST_SECRET` bearer (40 posts/batch)
- Gated by `FB_INGESTION_ENABLED` flag (must be true on Render)
- Health tracked in `ingest_state` table (last_ok_at, warning counters); exposed at `GET /api/ingest/facebook/health`
- Cost: ~$5.80/mo Apify net + ~$1.80/mo Haiku = ~$7.60/mo
- Legacy Playwright scraper (`vm-scraper/run.py`) + cookies (`vm-scraper/fb_state.json`) are now unused but not yet deleted

### Facebook Marketplace (parked)
- Different from FB Groups. Needs Playwright + perceptual image hashing.
- Revisit after FB Groups pipeline proven.

---

## Key Tables

| Table | Purpose |
|-------|---------|
| `search_presets` | Saved search queries (city, price range, rooms, source) |
| `scan_sessions` | Each scan execution (status, listings found, timing) |
| `properties` | All tracked properties (address, price, rooms, coordinates, etc.) |
| `property_snapshots` | Point-in-time snapshots per scan session |
| `property_events` | Detected changes (price_drop, relisting, removal, etc.) |
| `property_classifications` | Signal details (strong/weak signal lists, buyer_fit_tags) per property per session |
| `property_matches` | Cross-source duplicate matches |
| `whitelist` / `blacklist` | Manual overrides (whitelist surfaces, blacklist hides) |
| `operator_notes` | Free-text notes on properties |
| `favorites` | Starred properties |
| `scan_preset_stats` | Aggregated stats per preset per session |
| `property_operator_input` | Operator input: agent_name, manual_days_on_market, flexibility, condition |
| `fb_groups` | Facebook Groups catalog (group_id, name, url, is_active) |
| `ingest_state` | Per-source ingest health (last_ok_at, consecutive failures) |
| `closed_transactions` | Govmap historical deals (gush/parcel, coords, price, date, year_built) |
| `building_metadata` | Year-built cache per normalized address (source: tlv_municipality, madlan_cache, manual) |
| `neighborhood_thresholds` | Amit-fit buyer price targets per neighborhood |
| `neighborhood_feature_adjustments` | Per-neighborhood year/floor/parking/mamad price adjustments |

### The `yad2_id` column
Named for historical reasons but used as the universal external ID for ALL sources:
- Yad2: raw listing ID
- Madlan: `madlan_{bid}`
- Facebook Groups: `fb_{post_id}`

---

## Scan Pipeline (how data flows)

```
run_scan(preset_id):
  1. Load preset (must be is_active = TRUE)
  2. Create scan_session (status = running)
  3. Scrape (route to Yad2 or Madlan based on extra_params.source; FB ingest arrives via VM scraper)
  4. Upsert properties (ON CONFLICT updates all fields)
  5. Create property_snapshots (deduplicated)
  6. Detect events (compare to previous session)
  7. Find matches (cross-source dedup) — runs BEFORE signals because comp signals need building metadata
  8. Backfill year_built (from building_metadata cache or tlv_municipality)
  9. Compute signals (strong/weak) and persist signal details to property_classifications
  10. Detect customer relistings
  11. Record preset stats
  12. Update session to done/blocked/error
```

`run_all_scans()` runs all active presets sequentially, then detects removals.

### Scheduled Scans
- External cron (cron-job.org) POSTs to `POST /api/scan/scheduled` at 08:00 and 18:00 Israel time
- Requires `Authorization: Bearer {CRON_SECRET}` header
- Fires scan as background task, returns immediately
- Boolean lock prevents overlapping scans (`_scan_running` flag)
- `GET /api/scan/status` returns `{"running": true/false}`

---

## Distress Signals

Computed in `signals.py`. No numeric scores — signals are either **strong** or **weak**, surfaced as badges on each property. No hot/warm/cold tiers.

### Strong Signals

| Signal | Detection |
|--------|-----------|
| `price_drop_gt_10pct` | Largest price drop > 10% |
| `relisted_2plus` | Relisted 2+ times (relisting events) |
| `listed_90plus_days` | Days on market >= 90 |
| `weak_language` | Hebrew distress keywords in description (דחוף, גמיש, חייב, etc.) |
| `condition_keywords` | Renovation/old property keywords (שיפוץ, סבתא, ריענון) |
| `below_avg_price` | Price/sqm > 20% below neighborhood average |

### Weak Signals

| Signal | Detection |
|--------|-----------|
| `price_drop_small` | Any price drop ≤ 10% |
| `relisted_once` | Relisted exactly once |
| `listed_30_60_days` | Days on market 30–89 |
| `desc_changes` | Description changed since first seen |
| `img_changes` | Images changed since first seen |

Whitelist surfaces a property regardless of signals; blacklist hides it.

**DO NOT show numeric scores in the UI.** Show signal badges only.

---

## API Route Ordering Rules

FastAPI matches routes top-to-bottom. Path parameter routes (`{preset_id}`, `{yad2_id}`) capture string literals if registered first.

**Critical ordering:**
- `/api/scan/all` and `/api/scan/scheduled` BEFORE `/api/scan/{preset_id}`
- `/api/favorites/ids` BEFORE `/api/favorites/{yad2_id}`
- `/api/presets/stats/latest` BEFORE `/api/presets/{preset_id}`
- `/api/events/properties` BEFORE `/api/events`

---

## Code Rules (for AI agents)

- All user-facing text is in **English** (NOT French — Shechter doesn't speak French)
- `CREATE TABLE` must use `IF NOT EXISTS`
- All React hooks (useState, useMutation, useMemo) MUST be before any `if (...) return` early returns — this caused React error #310 three separate times
- Property images: Yad2 URLs work directly, Madlan uses `images2.madlan.co.il`
- Removal detection only runs in `run_all_scans()` for Yad2/Madlan scrapes, not per-preset. **Exception:** FB ingest has its own FB-scoped removal sweep in `scanner.py::_mark_fb_removals_for_session`, called from `run_scan_from_listings`.
- Cross-source matching uses Haversine distance (50m same-source, 100m cross-source)
- Hebrew text in property data is fine (comes from listings) — UI labels must be English
- Condition keyword שמור was removed (means "maintained" = positive, not needing work)

---

## Session Workflow

**Flow: `/plan` → `/review` → `/exec` → `/qa`** — then Alan tests manually. If issues found, loop back to `/plan`.

1. **`/plan [task]`** — Planner (Opus) investigates code, presents approach in plain English. Prints brief in terminal — never saves as file. Alan reviews and approves.
2. **`/review`** — Reviewer (Opus) reads the actual code the plan affects, challenges the approach, catches bugs the planner missed. Verdict: APPROVE / REVISE / REJECT. If REVISE, go back to step 1.
3. **`/exec`** — Executor (Sonnet) implements the approved brief. Removes old code when replacing. Does not commit.
4. **`/qa`** — QA agent (Sonnet) runs automated checks: curl API tests, SQL queries, Playwright browser tests with screenshots. Reports PASS/FAIL.
5. **Alan tests manually** — walks through the changes in the browser. If issues found, back to `/plan`.
6. **`/end-session`** — Archives TASKS.md + HANDOFF.md, commits + pushes to main.

**Key rules:**
- No commit until QA passes AND Alan approves
- Alan is the router — he decides what goes where
- Briefs and QA plans are printed in terminal, never saved as files
- No numeric distress scores in the UI
- Bugs found during manual testing loop back to `/plan` for investigation

---

## Task Tracking

- `TASKS.md` — current active task list (in project root)
- `HANDOFF.md` — end-of-day briefing for the next agent
- Archives: `TASKS_YYYY-MM-DD.md` — immutable daily records

---

## Deployment

- **Target:** Render (auto-deploys on push to main) — live at https://pdis-lsah.onrender.com
- **Database:** Neon (cloud PostgreSQL)
- **Scheduled scans:** cron-job.org → `POST /api/scan/scheduled` with `CRON_SECRET`
- **Build:** `pip install -r requirements.txt && cd frontend && npm install && npm run build`
- **Start:** `uvicorn pdis.api.main:app --host 0.0.0.0 --port $PORT`

### What runs where

| Source | Runs on | Reason |
|--------|---------|--------|
| Yad2 rent | Oracle VM (`vm-scraper/run_yad2.py`) | `/realestate/rent` got blocked from Render IP ~2026-04-15; moved to VM with forsale, daily 08:04 IDT systemd timer |
| Madlan | Render | PerimeterX cookie enough; no browser needed |
| Yad2 forsale | Oracle VM (`vm-scraper/run_yad2.py`) | `/forsale` IP-blocked by ShieldSquare on Render; same script handles both rent + forsale since 2026-04-15 |
| Facebook Groups | Apify (cloud) + Oracle VM orchestrator | Apify scrapes via residential proxies; VM systemd timer triggers daily at 10:00 IDT |
| Govmap backfill | Oracle VM (`vm-scraper/run_govmap.py`) | Long-running backfill, tmux/persistent disk |

Rule of thumb: **Render until it breaks, VM when it must.** VM workers POST to Render's ingest endpoints (`/api/ingest/facebook`, `/api/ingest/yad2`, `/api/ingest/govmap-deals`) with `INGEST_SECRET` bearer.

### Oracle VM

`ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214`. 1GB RAM micro — keep processes lean. Logs typically under `~/vm-scraper/logs/` or via `journalctl` for systemd units. See `vm-scraper/README.md`.

---

## Govmap Closed Transactions

`closed_transactions` table stores historical rental/sale deals from govmap (gush/parcel, centroid coords, sale price, deal date, year built). Used by `pdis/comps.py` to compute building-level comps, surfaced as a raw "Recent sales in this building" panel on PropertyDetailPage (Amit-approved Option 2 — no median-derived signals, just the comps themselves).

Backfill script: `vm-scraper/run_govmap.py` on the Oracle VM. POSTs in batches to `POST /api/ingest/govmap-deals`. Gated by `GOVMAP_INGESTION_ENABLED`.

---

## Environment Variables

| Var | Purpose |
|-----|---------|
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `CRON_SECRET` | Bearer for cron-job.org → `/api/scan/scheduled` |
| `INGEST_SECRET` | Bearer for VM scrapers → `/api/ingest/*` |
| `FB_INGESTION_ENABLED` | bool, gate for `/api/ingest/facebook` |
| `FB_SCANS_PER_DAY` | int, FB VM scan cadence (1 during probation, 2 normal) |
| `YAD2_VM_INGESTION_ENABLED` | bool, gate for `/api/ingest/yad2` (forsale) |
| `GOVMAP_INGESTION_ENABLED` | bool, gate for `/api/ingest/govmap-deals` |
| `APIFY_TOKEN` | Apify API token for FB Groups scraper (set on VM, not Render) |
| `ANTHROPIC_API_KEY` | Haiku 4.5 for FB post field extraction (set on VM, not Render) |
| `MADLAN_*` | Timeouts, delays, retries for Madlan scraper |
| `SCRAPE_*` | Page/request settings for Yad2 rent scraper |
| `LOG_LEVEL`, `LOG_FORMAT` | App logging |
| `API_HOST`, `API_PORT` | Uvicorn bind (local dev) |
