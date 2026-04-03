# PDIS — Claude Code Operating Guide
*Last updated: March 31, 2026*

---

## Golden Rule

Alan is not a coder. Every explanation must be in **plain English**. Explain the WHAT and WHY so Alan can make informed decisions. No jargon without explanation.

**Approval required before editing code.** Explain what you're changing and why, then wait for Alan's go-ahead. He will challenge decisions — be ready to defend or change course.

---

## What PDIS Is

PDIS (Property Distress Intelligence System) is a rental property monitoring tool for the Israeli market. It scans Yad2 and Madlan for rental listings in Tel Aviv, tracks them over time, detects distress signals (price drops, relistings, long time on market), and classifies properties as hot/warm/cold. Built for Alan's friend Shechter.

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

## Architecture

### Backend (Python FastAPI)

| Module | Purpose |
|--------|---------|
| `pdis/scraper.py` | Yad2 scraper — REST API via curl_cffi with Chrome TLS impersonation |
| `pdis/scraper_madlan.py` | Madlan scraper — GraphQL API via curl_cffi, PerimeterX cookie handling |
| `pdis/scanner.py` | Scan orchestrator — `run_scan()` and `run_all_scans()` pipeline |
| `pdis/signals.py` | Distress signal calculator — tier-based signal detection (strong/weak signals) |
| `pdis/events.py` | Event detection — compares snapshots between sessions |
| `pdis/classification.py` | Tier-based: 1+ strong signal = hot, 3+ weak = hot, 2 weak = warm, else cold |
| `pdis/matching.py` | Cross-source dedup — coordinates, customer_id, text similarity |
| `pdis/database.py` | Migrations + connection pool |
| `pdis/config.py` | Settings from environment variables |
| `pdis/api/main.py` | FastAPI app + lifespan + SPA routing |
| `pdis/api/routes.py` | All API endpoints (~43) |

### Frontend (React + TypeScript + Vite + Tailwind)

| Page | Route | Purpose |
|------|-------|---------|
| HomePage | `/` | Main dashboard: opportunities/fullscan tabs, SummaryBar, filters |
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

### Facebook Marketplace (planned, not built)
- Reviewed and parked. Needs Playwright + perceptual image hashing.
- See TASKS.md for full reviewer findings.

---

## Key Tables

| Table | Purpose |
|-------|---------|
| `search_presets` | Saved search queries (city, price range, rooms, source) |
| `scan_sessions` | Each scan execution (status, listings found, timing) |
| `properties` | All tracked properties (address, price, rooms, coordinates, etc.) |
| `property_snapshots` | Point-in-time snapshots per scan session |
| `property_events` | Detected changes (price_drop, relisting, removal, etc.) |
| `property_classifications` | hot/warm/cold classification + signal details |
| `property_matches` | Cross-source duplicate matches |
| `whitelist` / `blacklist` | Manual overrides for classification |
| `operator_notes` | Free-text notes on properties |
| `favorites` | Starred properties |
| `scan_preset_stats` | Aggregated stats per preset per session |
| `property_operator_input` | Operator input fields: agent_name, manual_days_on_market, flexibility, condition |

### The `yad2_id` column
Named for historical reasons but used as the universal external ID for ALL sources:
- Yad2: raw listing ID
- Madlan: `madlan_{bid}`
- Facebook (future): `fb_{listing_id}`

---

## Scan Pipeline (how data flows)

```
run_scan(preset_id):
  1. Load preset (must be is_active = TRUE)
  2. Create scan_session (status = running)
  3. Scrape (route to Yad2 or Madlan based on extra_params.source)
  4. Upsert properties (ON CONFLICT updates all fields)
  5. Create property_snapshots (deduplicated)
  6. Detect events (compare to previous session)
  7. Classify properties (hot/warm/cold)
  8. Find matches (cross-source dedup)
  9. Detect customer relistings
  10. Record preset stats
  11. Update session to done/blocked/error
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

Tier-based signal classification in `signals.py`. No numeric scores — signals are either **strong** or **weak**.

### Strong Signals (any 1 = hot)

| Signal | Detection |
|--------|-----------|
| `price_drop_gt_10pct` | Largest price drop > 10% |
| `relisted_2plus` | Relisted 2+ times (relisting events) |
| `listed_90plus_days` | Days on market >= 90 |
| `weak_language` | Hebrew distress keywords in description (דחוף, גמיש, חייב, etc.) |
| `condition_keywords` | Renovation/old property keywords (שיפוץ, סבתא, ריענון) |
| `below_avg_price` | Price/sqm > 20% below neighborhood average |

### Weak Signals (3+ = hot, 2 = warm, 1 = cold)

| Signal | Detection |
|--------|-----------|
| `price_drop_small` | Any price drop ≤ 10% |
| `relisted_once` | Relisted exactly once |
| `listed_30_60_days` | Days on market 30–89 |
| `desc_changes` | Description changed since first seen |
| `img_changes` | Images changed since first seen |
| `move_in_urgent` | Move-in date within 14 days |

Classification: whitelist forces hot, blacklist forces cold.

**DO NOT show numeric scores in the UI.** Show signal badges and classification labels only.

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
- Removal detection only runs in `run_all_scans()`, not per-preset
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

- **Target:** Render (render.yaml exists, not yet deployed)
- **Database:** Neon (cloud PostgreSQL)
- **Scheduled scans:** cron-job.org → `POST /api/scan/scheduled` with `CRON_SECRET`
- **Build:** `pip install -r requirements.txt && cd frontend && npm install && npm run build`
- **Start:** `uvicorn pdis.api.main:app --host 0.0.0.0 --port $PORT`
