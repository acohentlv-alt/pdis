# HANDOFF — April 15, 2026 (late session)

## What we did today

Investigation + planning session. No code shipped.

Alan asked why the Facebook scraper isn't showing any results in the UI. Diagnosed three stacked off-switches: (1) `FB_INGESTION_ENABLED` defaults to False in `pdis/config.py` and is missing from `.env`, so `POST /api/ingest/facebook` returns 503; (2) zero properties in the DB with `yad2_id` starting `fb_`; (3) `ingest_state.last_ok_at` is NULL → no FB ingest has ever succeeded. Also confirmed via Playwright that the FilterBar source dropdown only offers Yad2/Madlan (no Facebook option), but that's a UX gap, not the root cause — "All sources" already includes FB.

Then ran `/plan` for the fix. Alan chose **A2 (real Oracle VM scraper deployment)** over A1 (local smoke test). Planner drafted a full executor brief covering: residential proxy enforcement (hard-fail when `PROXY_URL` missing), `pdis/utils/city.py` with a `normalize_city()` helper supporting 6 TLV variants (Hebrew with/without hyphen, English variants → canonical `"תל אביב יפו"`), removal of `TLV_CITY_STRING` and `GROUP_CITY_MAP` from `routes.py`, deletion of `scripts/enumerate_fb_groups.py` (and re-pointing `seed_fb_groups.py` at `vm-scraper/groups.json` instead), Playwright selector hardening with a new `--dry-run` flag and DOM-drift detection in `vm-scraper/run.py`, systemd timer with 5-min jitter (Alan picked systemd over cron), and 14-day probation mode at 1 scan/day before flipping to 2/day.

Brief is **printed in the conversation only** — not saved to disk. Ready for `/review` next.

## What's half-done

### A2 brief is ready for /review but not yet reviewed or executed
The full executor brief and QA plan are sitting in the conversation transcript (planner agent ID `ab7b1cef88493c91a` if context still warm). Next step is `/review` to critique, then `/exec` to implement.

### Proxy decision unresolved
Alan said "gold standard for free." That doesn't exist for residential proxies — Bright Data, Smartproxy, IPRoyal all charge per GB. Free options are either (a) datacenter IPs = high FB ban risk on the personal account, or (b) compromised-device botnets = illegal/unreliable. Realistic options: **Smartproxy pay-as-you-go ~$5–15/mo** (lowest-cost legit), **Bright Data ~$15–45/mo** (gold standard), or **no proxy** (Oracle VM IP, expect ban within days). Needs to be resolved before `/exec`.

### 10 uncommitted code files from a prior session — NOT touched this session
`pdis/database.py`, `pdis/scanner.py`, `pdis/scraper.py`, `pdis/scraper_madlan.py`, `pdis/api/routes.py`, `frontend/src/api/client.ts`, `frontend/src/api/queries.ts`, `frontend/src/components/PresetManager.tsx`, `scripts/seed_fb_groups.py`, plus `.gitignore`. These are the scan UX progress bar work described in the prior `HANDOFF_2026-04-15.md` archive — author intended them to ship in the prior end-session commit but they didn't. Left untouched in this session per skill rule "only stage files YOU changed." Decide next session whether to commit or revert.

## What to do next

1. **Resolve the proxy decision** (Smartproxy default if no preference) — blocks `/exec`.
2. **`/review`** the A2 brief (planner agent `ab7b1cef88493c91a`). Look for: selector drift assumptions, retroactive city-normalization migration safety on 1,952 existing rows, systemd unit file correctness.
3. **`/exec`** the brief once review passes.
4. **Decide on the 10 uncommitted code files** — commit them (they were intended to ship 2 commits ago) or revert if no longer wanted.
5. Pre-A2 prereqs Alan owns: buy proxy plan, prep FB account (membership in 5 TLV groups + 2FA on), verify Oracle VM SSH works, prep Render env vars (`FB_INGESTION_ENABLED=false`, `FB_SCANS_PER_DAY=1` initially).

## Watch out for

- **Date drift in CLAUDE.md.** It says today is 2026-04-14 but real clock is 2026-04-15 00:23 IDT. Update the date stamp at top of CLAUDE.md when convenient.
- **The FB UX POLISH section was added to TASKS.md by the planner.** Two follow-ups landed there: FilterBar Facebook option and applying `normalize_city()` across Yad2/Madlan paths. Both are deliberately deferred to after A2 ships.
- **Retroactive city normalization.** Alan said "every point of data needs to be accurate" → this means the A2 brief should also include a one-off migration to normalize the 1,952 existing `properties.address_city` rows. Not in the planner's printed brief yet — re-prompt the reviewer/planner to add it before `/exec`.
- **Brief lives only in the conversation transcript.** If this session ends and the conversation is lost, the brief is gone — only the high-level summary in this HANDOFF survives. Worth re-running `/plan` next session if the transcript isn't accessible.
- **PDIS uvicorn was running in the background** (task ID `bbq0jchf3`, port 8000). Will keep running until killed.

## Test these

Nothing shipped. Nothing to test. Restart of the workflow is `/plan` → `/review` → `/exec` → `/qa`.

## Deployment state cheat-sheet

| Thing | State | Notes |
|---|---|---|
| Render backend | ✅ live | last commit shipped: `2986523` (FB groups multi-select) |
| FB groups catalog | ✅ seeded (49 rows) | per prior handoff |
| FB VM scraper | ❌ not deployed | A2 brief drafted, awaiting review + exec |
| `FB_INGESTION_ENABLED` | ❌ off | flip after VM cron verified |
| Proxy vendor | ❓ undecided | "gold standard for free" doesn't exist — pick paid |
| Govmap backfill | ❓ status unknown | check tmux session `govmap` on VM |
| Scan UX progress bar | ⏳ uncommitted code | 10 files in working tree, not pushed |
| `normalize_city()` helper | ❌ not built | A2 brief covers it for FB path only |
