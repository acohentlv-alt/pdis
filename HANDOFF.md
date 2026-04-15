# HANDOFF — April 15, 2026 (late session + consolidation session)

## CONSOLIDATION SESSION (Alan + second agent, after "late session")

### What we did

Opened Pandora's box: compared CLAUDE.md against the actual code. Audit found 10 drift items (8 doc-stale, 2 real code bugs). Decided to drop the hot/warm/cold classification concept entirely (code never computed it anyway — Alan chose not to resurrect it) and delete the `move_in_urgent` weak signal line (never built). Rewrote CLAUDE.md to match code reality: added FB Groups as an active source, added 6 missing tables (fb_groups, ingest_state, closed_transactions, building_metadata, neighborhood_thresholds, neighborhood_feature_adjustments), added the Render-vs-VM "What runs where" table, added the Govmap section, documented 12 env vars, fixed scan pipeline order (matching runs before signals), noted FB removal-detection exception. Ran a reviewer to verify — 30 of 33 load-bearing claims matched code ✅, 2 gaps fixed, 1 minor unverified.

Then answered Alan's strategic question "why do I still need Render?" — honestly, he probably doesn't. Queued a **post-A2 Render → Oracle VM consolidation** task (save ~$7/mo, one deploy target instead of two, trade `git push` convenience for Caddy + systemd on the VM).

Investigated the Haifa Buy screenshot Alan flagged: **root cause is NOT ShieldSquare IP block** (initial hypothesis was wrong — three other forsale presets succeeded Apr 14). Real cause: preset 9 has zero filters → asks Yad2 for every Haifa for-sale listing → anti-bot throttles. Fix = delete preset 9 (redundant with filtered Haifa variants 11+12) or add filters. **Not** a VM deployment problem.

### Commits pushed this session

- `74e9232` Update CLAUDE.md to match code reality
- `022d585` Queue Haifa Buy scan-blocked investigation
- `86f3ea9` Queue Render → Oracle VM consolidation (post-A2)
- `5bf1d44` Resolve Haifa Buy diagnosis (not ShieldSquare, unfiltered query)

### Heads-up on the working tree

Working tree has substantial uncommitted WIP from the **parallel agent building A2**: new `pdis/utils/city.py` (normalize_city helper), new `laptop-daemon/` directory (macOS launchd + daemon.py polling Render for FB jobs), edits to `routes.py` (fb_scan_queue system), `database.py` (new fb_scan_queue table + retroactive city UPDATE), `config.py` (probation settings), `PresetManager.tsx` (two JSX→function-call tweaks).

**Per Alan's correction mid-session:** the A2 plan pivoted from "Oracle VM + paid residential proxy" to "laptop daemon polling a DB-backed queue" because Alan wants the whole app FREE. This is a **legitimate approved re-plan**, not divergence. The second agent is shipping that. Do NOT touch their files. Future CLAUDE.md updates (post-ship) should change "FB Groups runs on Oracle VM" → "FB Groups runs on Alan's laptop via daemon polling `/api/fb-scan/next`".

### What to do tomorrow morning

1. **Let the other agent finish A2.** Their code is mid-flight. Give them the morning.
2. Once they commit + push, **update CLAUDE.md** to reflect the laptop-daemon architecture (replacing the "VM for FB" claim I just committed tonight).
3. **Fix Haifa Buy** (Option A: delete preset 9 — one SQL statement).
4. **Optionally** knock out the ₪/m² PropertyCard one-liner while waiting.

---

## LATE SESSION (original handoff, preserved below)

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

---

## LATE APR 15 SESSION — Govmap Option 2 + bug fixes + FB parked

Latest commit: **`a1e9fa8`** pushed to main.

### What we did today

1. **FB Groups scraper PARKED** — investigated with playwright, `mbasic.facebook.com` is deprecated (FB redirects to `www.facebook.com` React app with obfuscated classes that rotate weekly). 4kirot does it via paid residential proxies + ongoing engineering — breaks Alan's free-forever rule. Laptop daemon + queue + UI button + Ollama/Gemma 4 parsing + 14-group curated catalog are all SHIPPED but idle (daemon unloaded from launchd). When Alan relaxes the free constraint (Smartproxy ~$7/mo), 80% of the work is already done. Full parked entry in TASKS.md.
2. **Govmap Option 2 (Amit-approved) shipped** — removed median-based `below_closed_comps` + `above_closed_comps_20pct` signals. PropertyDetailPage now only shows raw "Recent sales in this building" panel at building-level. Street/neighborhood tiers hidden (Amit called them "averages").
3. **Govmap 2-bug double fix** — `run_govmap.py` had wrong CRS (EPSG:2039 declared vs actual EPSG:3857 Web Mercator) causing all 17,717 centroids to be in Arctic Ocean. Also scraper read `dealArea` but govmap returns `assetArea`, so `sqm` never populated → `price_per_sqm` (generated col) was NULL on 17,715 rows. Both fixed in scraper + `scripts/backfill_closed_transactions.py` repaired all existing rows.
4. **₪/m² math fix** on PropertyCard — was using build area, now uses total (gross) area per Israeli RE convention.
5. **Pydantic `extra=ignore`** — local daemon env vars (`OLLAMA_*`) no longer crash server Settings() parsing.
6. **Haifa preset 9 deactivated** — had zero filters → was being blocked by Yad2 every run.
7. **Catalog curation** — 35 non-real-estate FB groups deactivated, 14 keepers active.

### What's half-done

- **Govmap coverage is Bat Yam only** (117 of 2,567 properties = 4.5%). TLV + Haifa = 0%. Existing 17,715 rows are now correct data-wise but geographically limited. Tomorrow's job: check VM tmux `govmap` session status, ship fixed `run_govmap.py` there, resume backfill. Or run locally on MacBook.
- **Amit Fit** — Alan asked for (a) rent/buy toggle on dashboard and (b) hard 30% cap on preferred (non-negotiable). Two readings still pending: display-time filter vs auto-derive `max = pref × 1.30`. Alan to pick. Also: only Florentin has thresholds seeded, rest of TLV empty. Rent thresholds are 40-50% below market → almost nothing qualifies.
- **FB daemon/scheduler** unloaded from launchd but plist files still exist. To re-enable: `launchctl load ~/Library/LaunchAgents/com.pdis.fb-daemon.plist` (same for scheduler).

### What to do next

1. **Check VM govmap backfill status** — `ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214 "tmux list-sessions; tail -20 /tmp/govmap_full.log"`. If stopped, scp fixed `run_govmap.py` + resume with `--resume`.
2. **Flip `FB_INGESTION_ENABLED=false` on Render** (cleaner state since FB is parked).
3. Verify deploy of `a1e9fa8` is green; spot-check one Bat Yam property's PropertyDetailPage — should show "Recent sales in this building" if ≥3 nearby comps.
4. Amit Fit — get Alan to pick interpretation (a) or (b) for the 30% cap, then ship.

### Watch out for

- **TASKS.md is dated "April 16, 2026"** — one day ahead. An earlier end-session rolled it forward prematurely. Today's real archive is `TASKS_2026-04-15.md`.
- **3 Render env vars to verify** — `INGEST_SECRET`, `CRON_SECRET` (Alan's value = "shechter"), `FB_INGESTION_ENABLED` (should be `false` now).
- **Ollama on laptop** — `gemma4:e2b` (~7GB) and `gemma4:e4b` (~9.6GB) both installed. Warm inference ~3s, cold start ~50s. Currently idle.
- **CLAUDE.md still references removed signals** (`below_closed_comps`, `above_closed_comps_20pct`) at lines 188, 189, 288. Doc cleanup pending.

### Test these

Things shipped today but not eyeballed in deployed UI:
- PropertyCard ₪/m² — open any property with both build + total sqm, confirm ₪/m² uses total
- PropertyDetailPage → "Recent sales in this building" panel — only shows for Bat Yam properties with ≥3 comps
- Preset editor on FB preset — no more multi-select checkbox list (confirmed during session)
- Preset form Name field typing — no longer loses focus per letter (fixed earlier today)
