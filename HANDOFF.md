# HANDOFF — April 16, 2026 (day session: cleanup + backend quick wins + fire-and-forget)

## What we did today

Three parallel agents shipped on PDIS throughout the day. Net: **7 commits on main**, ending at `60fc1fd`. All pushed, Render auto-deployed mid-afternoon.

**My worktree (elegant-spence) — 3 commits:**
- `e15762c` — Delete Playwright-era FB scraper leftovers. Removed 3 files (413 lines): `vm-scraper/export_fb_cookies.py`, `scripts/enumerate_fb_groups.py`, `scripts/cleanup_fb_broken_rows.py`. Rewrote `vm-scraper/README.md` as Apify-only. Updated CLAUDE.md, PresetFormSections empty-state text, seed_fb_groups.py docstring references.
- `26daa4a` — Discarded the abandoned 147-line Playwright WIP sitting uncommitted in `vm-scraper/run.py` for days. Fixed stale `export_fb_cookies.py` reference at `run.py:388`. Followed up by upgrading the TASKS.md follow-up to "delete run.py entirely."
- `7a6fb60` — Backend quick wins: events.py N+1 fix (LEFT JOIN on properties in the detection CTE, ~200 DB roundtrips per scan eliminated) + DB-backed scan lock (30-min stale window, replaces module-level `_scan_running`). CLAUDE.md:173 updated. Went through full `/plan → /review → /exec → /qa` cycle; QA scored 10/10 including a live-lock-working moment during the check (a real scan was in-flight on Neon and the new code correctly reported `{"running": true}`).

**Quirky-heyrovsky agent — 1 commit:**
- `f484b5a` — Folded Open Search into a transient Custom Search pill on OpportunityPage. Replaced `/search/results` page with URL-driven `?custom=` state; POST `/api/scan/open` + `OpenSearchBody` + `SearchResultsPage` removed; new read-only `GET /api/search/custom` endpoint. This addresses the "Open Search UX replan" item queued in night2's TASKS.md.

**Scraper agent — 2 commits:**
- `0de9b52` — "Two fixes after QA caught live issues." Hide disabled presets + unblock FB sampling ingest. Shipped alongside their investigation of this morning's 08:00 Yad2 VM run failures.
- `60fc1fd` — Make `/api/ingest/yad2` + `/api/ingest/facebook` fire-and-forget. Added `_run_yad2_ingest_background` + `_run_fb_ingest_background` wrappers and a shared `_mark_running_session_failed` helper. Bumped `database.py` pool (`max_size 10→15`, `timeout 5→15`). Low-volume guard refactored to per-source logic (FB keeps 10% threshold, Yad2/Madlan reject only empty). **Root cause of the morning's HTTP 500s:** ingest endpoints were synchronous, 240-listing payloads exceeded some boundary (pool timeout, OOM, or pre-try DB exception — not Render's 100-min HTTP timeout). Fire-and-forget fixes the symptom regardless of cause.

## What's half-done / needs attention

- **Fire-and-forget fix is untested in production.** We planned a 12:10 IDT manual live test but missed the window (Render finished deploying `60fc1fd` at ~12:53). Tomorrow's 08:00 IDT automated run becomes the first real test. If it fails, the scraper agent's diagnosis was wrong and we'll need to pull Render logs.
- **Today's 08:00 IDT Yad2 VM run had problems.** Scraper agent found 4 of 6 presets got HTTP 500 from Render on 240-listing POSTs. Only small presets (13 = 4 Villas, 11 = 36 Haifa Small Apts) "succeeded" — and those were actually silently rejected by the broken volume guard. Today's fix solves both.
- **Today's Madlan scheduled scan didn't fire at 08:00 IDT.** External cron-job.org skipped it (likely Render cold-start timeout). Scraper agent kicked it off manually mid-afternoon — it ran end-to-end cleanly (1172 listings, 474 new). Tomorrow's 08:00 will reveal whether this was a one-off.
- **484 `qatest_*` pollution rows** were left in Neon during the scraper agent's QA. Scraper agent cleaned them up. Noting it here because it shouldn't happen again.
- **`vm-scraper/run.py` is still present** (455 lines of dead Playwright code). Committed `run.sh` still points at it, but deployed `run.sh` on VM calls `apify_to_pdis.py`. TASKS.md has the follow-up to delete entirely — wait until we're sure nothing references it.

## What to do next

1. **At 08:00 IDT tomorrow, check `/api/scan/sessions`** — expect 6 fresh Yad2 `done` sessions (including preset 13 Villas finally populating 4 rows). If any preset is `error` or stuck `running` past 30 min, the fire-and-forget fix has a regression.
2. **At 10:00 IDT, check FB ingest.** Apify run + Haiku parse + `/api/ingest/facebook` should produce << 70 new rows (filters drop junk). `GET /api/ingest/facebook/health` should show `last_ok_at` within 15 min of 10:00.
3. **Check cron-job.org dashboard** to see if today's 08:00 Madlan job logged a failure. Set up a heartbeat monitor if not already there. Or consider: move Madlan off cron-job.org onto the VM systemd timer (next to the Yad2 and FB timers).
4. **Strategic item #1 (telemetry)** is still the Monday-morning priority. Two hours, unblocks everything else in the 7-item roadmap.
5. **Mobile polish pass** — I queued a brief in TASKS.md based on the critique I gave you earlier today. This is the single biggest user-felt improvement left.

## Watch out for

- **Three agents shared the main checkout (`/Users/alancohen/pdis/`) today.** Both executors wrote to the same routes.py + database.py. I incorrectly reverted the scraper agent's fire-and-forget changes thinking they were my own executor's scope creep — wasted 30 min recovering. **Going forward:** when running `/exec`, verify agents know which worktree to write into (main vs. `.claude/worktrees/<name>`). Shared-directory writes are a footgun.
- **My executor made an unauthorized addition** — it tried to add the same fire-and-forget wrappers as the scraper agent (likely saw the scraper agent's uncommitted files in the shared checkout and preserved them as "existing state"). The QA agent didn't flag it. Added "scope check" to the mental checklist before committing an executor's output.
- **Render deploys auto-trigger on push to main.** With 7 commits today, Render rebuilt 7 times. Each takes 3-5 min. Free-tier cold starts between deploys can make automated runs (cron-job.org Madlan especially) fail silently.
- **`60fc1fd` just landed at ~12:53 IDT.** If you hard-refresh the PWA tomorrow morning before the 08:00 run, confirm Render is serving the new build (scan status endpoint behavior shouldn't have changed visibly, but the ingest endpoints will respond in <1s instead of hanging 30s+).
- **`vm-scraper/run.py` still exists.** The VM's `run.sh` calls `apify_to_pdis.py`, but the committed `run.sh` in the repo still points at `run.py`. If anyone re-deploys the VM from the repo's `run.sh`, they'll execute dead Playwright code. Fix is queued in TASKS.md.

## Test these

- **Hard-refresh** `https://pdis-lsah.onrender.com` — verify Custom Search pill appears (leftmost, blue, before Amit Fit preset pill). Tap it → URL becomes `/?custom=…` → results render in the same dashboard.
- **Tap PresetManager (3-dot menu)** — confirm hidden disabled presets no longer appear in the list (fixed in `0de9b52`).
- **Tap preset 13 (TLV Rent Villas)** after tomorrow's 08:00 IDT scan — should show 4 properties. Previously silently dropped.
- **Monitor `/api/scan/sessions?limit=15`** at 08:02 and 10:02 IDT — expect 6 Yad2 + 2-3 FB sessions, all `done`, none stuck `running`.
- **Any new scan you trigger manually** — watch the progress bar still updates (DB-lock refactor didn't break `_scan_progress`).

---

## Late-afternoon update — investigation + live test + retry safety net (commits `ebe4b11`, `5209985`, `85bebd9`)

After the day session wrote the handoff above, this agent ran a live test of the fire-and-forget fix at ~12:30 IDT (the test the day session said was "missed" — it actually happened, just later than 12:10).

**Live test results:**
- ✅ **Madlan** (via Render scheduled scan) — s176 done, 1207 listings, 275 new
- ✅ **Yad2 4/6 presets** (8, 12, 13 ←first time Villas worked, 23) — `done`
- ❌ **Yad2 2/6 presets** (9, 11) — silently lost. Render returned HTTP 500 from the synchronous handler before the bg task could create a session. Reproduction attempts from MacBook all returned 200 in <0.5s, so it's NOT a deterministic code bug — looks like transient Render-side state (worker recycling, brief pool/network hiccup).
- ❌ **Facebook** — Apify HTTP 402, **out of credits**. Top up needed.

**Three new commits to address the gaps:**
1. **`ebe4b11`** — added `/api/debug/recent-errors` endpoint. Captures every unhandled FastAPI exception (with traceback) into an in-memory ring buffer of size 50. If a 500 fires tomorrow morning, `curl https://pdis-lsah.onrender.com/api/debug/recent-errors` returns the actual stack trace — no need for Render dashboard access. **Temporary** — remove or gate behind a debug flag once root cause is known.
2. **`5209985`** — VM-side retry on 5xx. Both `vm-scraper/run_yad2.py` and `vm-scraper/apify_to_pdis.py` now retry up to 3x with 60s wait. 4xx is permanent (no retry). Already deployed to Oracle VM. Should reduce the silent-loss rate from today's ~33% to near zero.
3. **`85bebd9`** — CLAUDE.md schedule fix. The doc said cron-job.org fires at 08:00 + 18:00; reality is **10:00 IDT** (verified from a screenshot of the cron-job.org dashboard). My earlier "Madlan didn't fire today" claim in this handoff was wrong — sessions s157–s164 at 07:02 UTC = 10:02 IDT WERE the cron's fire (the field `requested_by='user'` is misleading — it's set that way for cron-fired scans too). **Action item:** verify on cron-job.org dashboard whether there's a second daily slot.

**Correction to "What's half-done" above:** the claim that today's Madlan didn't fire at 08:00 IDT is wrong — Madlan fired at 10:00 IDT (correct schedule), via cron, and ran end-to-end cleanly. The afternoon manual fire was on top of the cron's already-completed run.

**Cleanup:** ~1485 synthetic test/probe rows were left in production Neon during this afternoon's investigation (`reproduce_*`, `qatest_*`, `verify_*`, `burst_*`, `probe*`, `fbverify_*`). All cleaned up before close — DB verified clean.

## Updated "What to do next" (supersedes earlier list)

1. **08:00 IDT — Yad2 VM auto-run.** Check `/api/scan/sessions?limit=20` after ~08:30 IDT. Expect 6 fresh `done` sessions. If any preset shows `error` or stuck `running`, **first thing**: `curl /api/debug/recent-errors` and capture the JSON. That tells us exactly what's raising the 500.
2. **10:00 IDT — Madlan via cron AND FB VM run.** If Apify is topped up, FB will produce sessions; if not, FB will fail at the Apify step before even calling our API.
3. **Top up Apify credits** (apify.com dashboard) so FB scraper works tomorrow.
4. **Verify cron-job.org schedule** on dashboard — is it 10:00-only, or 10:00 + something else?
5. If everything looks clean by mid-morning: **remove `/api/debug/recent-errors`** or gate it behind a `DEBUG_ENDPOINTS_ENABLED` env flag. Don't leave it on indefinitely.

## Updated "Watch out for"

- **FB volume guard rejects every daily batch.** Even when Apify works, the FB pipeline silently drops its 10–15 daily posts because the threshold is `max(10, prior_count * 0.1)` = 68 against ~689 prior FB rows. This bug existed before today and was confirmed during investigation. Separate brief needed — see TASKS.md "FB volume guard always rejects daily batch".
- **Render free-tier cold starts are real.** cron-job.org's request to `/api/scan/scheduled` today took 13.77s to get a 200 response — that's the cold start, not actual work. The endpoint just schedules a bg task and returns. So a 13-sec response is normal/healthy, not a failure.

---

*Archived sessions:*
- *TASKS_2026-04-16.md — this morning's TASKS (pre-day-session). Immutable.*
- *HANDOFF_2026-04-15_night2.md — prior handoff from the overnight session. Immutable.*
