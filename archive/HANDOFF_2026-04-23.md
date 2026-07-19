# HANDOFF — April 23, 2026

## What we did today

Two cleanups while waiting on Amit thresholds + Alan's new FB groups. Full `/plan → /review → /exec → /qa` on each.

**PR #3 (merged):**
1. **Playwright-era cleanup** — deleted `vm-scraper/run.py` (455 lines dead), fixed `vm-scraper/run.sh` (the repo copy was stale — still called `run.py`, deployed VM already calls `apify_to_pdis.py`), deleted `tests/test_fb_parser.py` (tested regex helpers that lived only in `run.py`), stripped `PROXY_URL` stanza from `vm-scraper/.env.example`, fixed `vm-scraper/README.md:14`, removed the "legacy scraper retained pending cleanup" sentence from CLAUDE.md.
2. **Removed `/api/debug/recent-errors`** — added Apr 16 for Neon pool debugging, root cause fixed Apr 18, buffer empty 5+ days, zero callers, unauthenticated. Stripped the `RECENT_ERRORS` deque + the GET route + the buffer-append block from the global exception handler. KEPT the structlog `unhandled_exception` emission and the 500 JSON response — those are the durable replacement for the buffer (Render logs still capture the signal). Also dropped now-unused imports: `traceback`, `deque`, `datetime`/`timezone`.

Net: -644 lines on Playwright side, -29 lines on debug endpoint.

## What's half-done / deferred

- **VM deploy still deferred** (same as yesterday) — `vm-scraper/llm_parse.py` + `apify_to_pdis.py` + the new `run.sh` haven't been pushed to Oracle VM. Waiting on new FB groups + Amit's threshold data so first post-deploy scrape lands clean end-to-end.
- **`scripts/fb_price_sweep_20260418.py` and `scripts/madlan_field_probe.py`** — still not run (same as yesterday).
- **Mid-session git state mess** — the worktree's cleanup commits forked from an older main state, so `git rebase origin/main` hit conflicts in TASKS.md/HANDOFF.md/CLAUDE.md. Resolved by taking the incoming (branch) versions and letting end-session fix up the handoff files on main. Future sessions: before starting cleanup work in a worktree, make sure the worktree is at `origin/main` HEAD, not forked from days ago.

## What to do next

**Still waiting on external inputs** (Amit thresholds + Alan's FB groups list). While waiting, continue the stale-code cleanup shortlist:

1. **`pdis/scraper.py` Yad2-on-Render fallback** — target was ~Apr 26 (1 week post-migration). Today is Apr 23. 3 days early, but VM rent scrape has been stable for 4+ days now. Bundle with `fetch_item_detail` removal (same file, both dead) + `else: scrape_preset(...)` branch removal in `scanner.py:~645` + `scanner.py:14` import.
2. **Drop `search_presets.is_active` column** — target Apr 24, basically on schedule. Schema migration, so slightly higher risk surface than the above.
3. **Payload bloat in `/api/favorites`, `/api/whitelist`, `/api/blacklist`** — same `SELECT p.*` → explicit columns pattern used for preset 44 Madlan fix. Pure perf, low risk.

Recommended order: 1 → 3 → 2 (safest to risky). #1 is the natural next `/plan`.

## Watch out for

- **Render should auto-deploy PR #3.** Commit `c08d01c` on main. Verify deploy succeeded via the Render dashboard.
- **`/api/debug/recent-errors` curl will return 200, not 404** — SPA catch-all. To verify it's really gone, check the response body (`<!doctype html>` = SPA, not JSON).
- **Git state:** branch `claude/elegant-spence` is now up to date with main (squash-merged). If you reuse the same worktree for next cleanup, `git pull origin main` inside the worktree first.
- **Don't touch the 5-intent FB prompt or display_sqm plumbing** — all live on Render, just not yet on VM. Any "fix" there will double-apply when VM deploys.

## Test these

- [ ] Render deploy of `c08d01c` succeeded (dashboard)
- [ ] `curl https://pdis-lsah.onrender.com/api/presets | jq 'length'` — integer, no error
- [ ] iPhone: dashboard loads, favorites star works, property detail page renders
- [ ] `grep -r "RECENT_ERRORS\|recent-errors" pdis/ frontend/src/` — zero matches
- [ ] Amit Fit rent count stays at ~4 (expected until thresholds load)

---

---

## Appended — late-afternoon Madlan→VM migration (Claude Opus 4.7 session)

### What happened

Alan noticed Madlan hadn't scanned on schedule for ~5 days. Investigation:
1. **Discovered cron-job.org was firing daily with 200 OK** (Alan confirmed via screenshot), but Render's `BackgroundTask` was dying silently after the response — no scan_session rows being created despite the "success."
2. **Confirmed the VM already had the latest FB scripts** deployed (MD5 match) — earlier HANDOFFs saying "VM deploy deferred" for `llm_parse.py`+`apify_to_pdis.py` were stale.
3. **Facebook still returns 402 Payment Required** — Apify $5 trial exhausted. Known, parked pending top-up.

### What we shipped (3 commits on main)

- **`848483d`** — Move Madlan scheduled scan to Oracle VM; retire `/api/scan/scheduled`. New `vm-scraper/run_madlan.{py,sh}` + systemd units firing daily at 06:00 IDT. Deleted `trigger_scheduled_scan` route + `scheduled_scan` wrapper + `cron_secret` config field. CLAUDE.md + TASKS.md updated.
- **`a31c2db`** — First test-fire crashed on `ModuleNotFoundError: No module named 'pdis'`. Added `export PYTHONPATH=/opt/pdis-madlan-scraper` to `run_madlan.sh`.
- **`01e0f39`** — Second test-fire (session 268) ran successfully through scrape + upsert + events + matching, then crashed inside `persist_signals_batch` with `server conn crashed?` — Neon killed the connection because the per-row INSERT loop held it open for 5+ min. Fix: replace per-row loop with single `executemany` call. Connection hold time drops from minutes to <1s.

### VM state as of end-session

- `/opt/pdis-madlan-scraper/` cloned with full repo + deps installed (`psycopg[binary]`, `psycopg-pool`, `pydantic-settings`, `structlog`, `curl_cffi` already present)
- `.env` written with `DATABASE_URL` + `YAD2_VM_INGESTION_ENABLED=true` (critical — without it, Yad2 presets don't short-circuit to `skipped_vm`)
- `pdis-madlan-scraper.timer` enabled, next fire tomorrow **06:00:15 IDT**
- Log file: `/var/log/pdis-madlan-scraper.log`

### Late-session update — wrong fix, found real one

Test-fire #2 (session 275, post-executemany) **crashed the same way** at 14:53:08. The executemany change was a real improvement but targeted the wrong loop.

**Real root cause:** `pdis/signals.py:90-171` opens a pool connection (`async with _db.pool.connection() as conn:`) and inside that block calls `compute_building_comps_batch` — which has a **1194-iteration per-property loop** (N+1, each call opens its own pool conn). The OUTER `conn` sits idle for 5-6 minutes during that loop, Neon idle-kills it, and the surrounding `async with conn:` raises on exit.

**Commit `4ace127`** dedents the `compute_building_comps_batch` call out of the outer `async with conn:` block. Three lines, one indent change. No reason to hold the outer conn during that loop — it's not used.

Test-fire #3 was kicked off at end-session after this fix pushed. Monitor is watching for `signals.persisted` or another `server conn crashed?`.

**First thing tomorrow: check `/var/log/pdis-madlan-scraper.log` on VM.**
- If you see `signals.persisted count=~1200` followed by `madlan_vm.done status=done`: fix is correct, migration is fully shipped.
- If you see another `server conn crashed?`: the underlying architecture (N+1 in comps_batch) is also a problem. Next step would be batching the closed_transactions query by lat/lng envelope once for the whole batch instead of per-property. That's a real `/plan` task, not a 3-line fix.

### Manual action still needed from Alan

1. **Delete/disable the cron-job.org Madlan job.** It'll start firing HTTP 422s at 10:00 IDT (since `/api/scan/scheduled` is gone and Render now routes it into `POST /api/scan/{preset_id}` which 422's on "scheduled" as non-int). Harmless but annoying.
2. Optional: remove `CRON_SECRET` env var from Render — nothing reads it anymore.

### Watch out for

- **Session 268 is marked `error` in Neon** with partial data (1039 snapshots + 103 events + 270 classifications + 0 scan_preset_stats). Leave it — tomorrow's 06:00 will heal classifications via `ON CONFLICT DO UPDATE`. One-day cosmetic gap in `scan_preset_stats` for preset 44 is fine.
- **Yad2 VM at 10:00 and Madlan VM at 06:00 — no collision.** But if someone manually hits "Run Yad2 now" button around 06:00, they'll overlap. The DB-backed `is_scan_running` lock that would have prevented this was removed with the deleted endpoint — per-preset scans don't check it.
- **CLAUDE.md still says Madlan scan was "10:00 IDT" at one historical point** — updated to 06:00 today, but if you see stale references elsewhere, grep.

### Deferred to separate briefs (in TASKS FOLLOW-UPS)

- `_upsert_properties` (per-row loop, 1194 rows, survived today)
- `_create_snapshots` (per-listing SELECT+INSERT, 2400 round-trips)
- `backfill_year_built_from_buildings` (per-property SELECT+UPDATE)

Same `executemany` pattern fixes all three. Worth bundling into one PR this week — they're all variants of the same bug.

---

*Archived sessions:*
- *HANDOFF_2026-04-19.md — Apr 18-19 late-night Yad2 rent→VM + phone-hook fix.*
- *HANDOFF_2026-04-18_evening.md — Apr 18 evening Madlan latency fix.*
- *HANDOFF_2026-04-18_morning.md — Apr 17-18 day→evening pool fix + telemetry.*
- *HANDOFF_2026-04-17.md — Apr 17 is_active split session.*
