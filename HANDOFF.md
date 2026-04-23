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

*Archived sessions:*
- *HANDOFF_2026-04-19.md — Apr 18-19 late-night Yad2 rent→VM + phone-hook fix.*
- *HANDOFF_2026-04-18_evening.md — Apr 18 evening Madlan latency fix.*
- *HANDOFF_2026-04-18_morning.md — Apr 17-18 day→evening pool fix + telemetry.*
- *HANDOFF_2026-04-17.md — Apr 17 is_active split session.*
