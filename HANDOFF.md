# HANDOFF — April 14, 2026

## What we did today

Shipped **3 features + 1 major integration** across 4 commits to main:

1. **Amit Fit UX polish** (commit `9357619`): emerald cross-preset Amit Fit pill on dashboard; 7-source PresetManager dropdown (Yad2/Madlan/Facebook + all combos); inactive presets hidden from pill strip; legacy `both` → `yad2_madlan` normalized; Yad2 forsale scanner cleanly skips with `status='skipped_vm'` when VM flag is on.

2. **Auto-reclassify on threshold/feature-adjustment edits** (part of commit `9357619`): saving in PresetManager now immediately recomputes buyer_fit_tags for the affected neighborhood+category, with TRIM to handle Madlan rows that only match by name. Wrapped in try/except — threshold save always succeeds even if recompute fails (returns `recompute_warning` in 200 response).

3. **Govmap closed-sale comps integration** (commits `86dce73`, `6a62f83`, `2078efd`): new `closed_transactions` table, tiered comps lookup (building via gush+parcel → 30m radius → 150m street → neighborhood), 2 new signals (`below_closed_comps`, `above_closed_comps_20pct`), Closed Comps panel on PropertyDetailPage with English Tax Authority attribution, emerald/gray card badge, VM scraper for TLV grid walk with monthly refresh.

4. **Oracle VM setup for govmap scraper** — cloned repo, set up venv + deps, wrote `.env` with shared `INGEST_SECRET`, verified end-to-end: `test_govmap.py` POSTed 2 Lev-Ha'ir deals → HTTP 200 → rows in Neon. Two bugs found + fixed live: wrong base URL (`api.govmap.gov.il/govmap/api` → 403; correct is `www.govmap.gov.il/api/real-estate`), missing centroid on per-deal response (patched to fall back to grid query point).

QA: 17/17 Amit Fit work + 20/20 govmap work — 0 console errors, 0 React #310. All 4 commits auto-deployed to Render.

## What's half-done

### Govmap TLV full backfill — ready to run, not started
The VM is fully set up and verified working (one small test inserted 2 real deals). The full 14-42h grid walk needs to be kicked off in a `tmux` session so SSH disconnect doesn't kill it. This should run on a weekend. Exact command is in TASKS.md → "READY TO RUN" section.

### Feature flags state on Render
- `INGEST_SECRET` — set ✅
- `GOVMAP_INGESTION_ENABLED=true` — set ✅ (ingest endpoint active)
- `YAD2_VM_INGESTION_ENABLED=false` — set ✅ (Render still tries local Yad2 forsale; flip to true AFTER Yad2 VM cron is running)
- `FB_INGESTION_ENABLED` — NOT SET (FB scraper deployment still pending from days-old brief)

## What to do next (next session)

**Highest priority:** walk Alan through kicking off the govmap full backfill in a tmux session (see TASKS.md command block). Monitor via `tail -f /tmp/govmap_full.log`. Once it finishes, verify ~500k-1M rows in `closed_transactions` and that a Florentin property shows the Closed Comps panel with real comps.

**Second priority:** add the monthly cron entry on the VM so the govmap scraper refreshes deals automatically on 1st of each month at 3am Israel time. Exact crontab block is in TASKS.md.

**Third priority:** complete the long-pending FB scraper deployment (8-step checklist in TASKS.md). INGEST_SECRET is already set; just need FB env vars + cookie export + SCP.

## Watch out for

- **Govmap `/street-deals/` endpoint does NOT return per-deal coords.** All deals in one polygon share the same building — centroid has to come from the grid query point (±200m). Fixed in commit `2078efd`; do not regress.

- **Govmap base URL is `https://www.govmap.gov.il/api/real-estate/`** — NOT `api.govmap.gov.il/govmap/api` (that returns 403). Fixed in commit `6a62f83`; hardcoded at `run_govmap.py:64`.

- **Alan's terminal mangles multi-line pastes** during SSH sessions — long commands get split with inserted newlines mid-line. When giving commands to run on the VM, keep to single short lines or use `nano`/`sed` to edit files.

- **Florentin forsale 60-70 bucket** was bumped during QA testing (pref 35000→37000, max 40000→45000). I restored to 35000/40000 after QA. If Amit's original values differ, check with him.

- **Render auto-deploy is actually working** (verified live today — memory from past sessions claiming it was broken has been updated). Push to main → auto deploys. No manual Render click needed anymore.

- **Classification column is vestigial** — persist_signals_batch writes signal_details only. Tier (hot/warm/cold) column doesn't auto-update but nothing in UI reads it anymore since stale-code cleanup commit `8264349`.

- **Server was left running locally** on port 8000 from QA. Kill with `pkill -f "uvicorn pdis.api.main"` if needed.

## Test these (after backfill lands)

- Open a Florentin property in the UI → Closed Comps panel renders with real data (not synthetic QA fixtures).
- Any property where `closed_comp_source='building'` fires a `below_closed_comps` or `above_closed_comps_20pct` signal → PropertyCard shows emerald/gray "−X% vs building median" pill.
- Verify the monthly cron actually fires on May 1st — check `/tmp/govmap_cron.log` on the VM.
- After FB deployment: `SELECT COUNT(*) FROM properties WHERE source='facebook'` should grow daily.

## Deployment state cheat-sheet

| Thing | State | Notes |
|---|---|---|
| Render backend | ✅ live | auto-deploys on push |
| INGEST_SECRET | ✅ set | `921dab0...54e` — shared across FB/Yad2/Govmap VM scrapers |
| Oracle VM | ✅ reachable | `ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214` |
| VM pdis repo | ✅ cloned | `~/pdis` — last pulled commit `2078efd` |
| VM venv | ✅ built | `~/pdis/venv` — all deps installed (pyproj, curl_cffi, httpx, playwright) |
| VM `.env` | ✅ set | `~/pdis/vm-scraper/.env` — has INGEST_SECRET + PDIS_API_URL |
| Govmap ingest flag | ✅ enabled | `GOVMAP_INGESTION_ENABLED=true` on Render |
| Govmap test run | ✅ pass | 2 deals in `closed_transactions` from Lev Ha'ir |
| Govmap full backfill | ⏳ pending | needs weekend + tmux |
| Yad2 forsale VM | ⏳ pending | flag false, cron not installed |
| FB scraper VM | ⏳ pending | cookies not exported, cron not installed |
