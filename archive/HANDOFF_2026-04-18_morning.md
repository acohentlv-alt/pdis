# HANDOFF — April 17-18, 2026 (day→evening session: pool fix + telemetry as UX bug detector)

## What we did today

Two things shipped to main:

- **`c0d0433` — Neon stale-connection pool fix.** Found 17 `SSL connection closed unexpectedly` errors in the `/api/debug/recent-errors` buffer, all idle-connection issues from Neon killing sockets after ~5 min. Added `check=AsyncConnectionPool.check_connection` + `max_idle=240` to the pool config in `pdis/database.py`. 4-line change. VM-side retry from yesterday (`5209985`) had been masking the bug — scans still completed because retries caught the 500s.

- **`04b5685` — Telemetry v1, as a UX bug detector.** Full `/plan → /review → /exec → /qa` cycle (Alan challenged the original framing mid-plan — see below). New `ui_events` table, `POST /api/ui-events` + `GET /api/ui-events/recent-issues` endpoints. New `/admin/ux-health` page (red/yellow/green sections, 30s auto-refresh, session-grouped errors, NavBar hidden). New `lib/telemetry.ts` helper. React error boundary + window error listeners. `apiFetch` instrumented (not monkey-patched) for `api_error` + `slow_response`. `page_view` with StrictMode-safe `useRef` guard. `empty_state` events on dashboard + favorites. Deleted `/api/log-reveal` hack + `LogRevealBody` + frontend fetch (grep returns zero). QA 9/10 passed.

## What's half-done / needs attention

- **Both of today's commits are AWAITING iPhone QA on Render.** The telemetry admin page has only been tested on localhost — the real test is hitting `https://pdis-lsah.onrender.com/admin/ux-health` on your phone after Render deploys (`04b5685` pushed at end-of-session, deploy ~3-5 min).
- **FB pipeline shutdown STILL NOT DONE.** This was urgent from yesterday's handoff (`$5/day bleed`) and we never got to it — the conversation pivoted into the Neon bug, then telemetry. Command list in TASKS.md under "READY TO RUN."
- **Double `page_view` on `/favorites`** — known 0-severity defect. `/favorites` redirects to `/listings` via React Router `<Navigate>` and both pathnames fire the effect. Cosmetic only (admin counts slightly inflated).
- **Test events in prod DB.** QA session left ~20 synthetic events with session_ids like `qa-session-*`. Cleanup SQL is in TASKS.md. Low priority — admin page filters by severity and test events are mostly `info`.
- **`/api/debug/recent-errors` still exposed.** Its job is done now (it helped us find the Neon bug). Task to gate it behind a flag is in NOT STARTED.

## What to do next

1. **iPhone tap-through telemetry on Render.** Hard-refresh, visit `/admin/ux-health` (no NavBar), tap around 30 seconds, watch counts update. Reveal a phone on a property, check it appears in admin within 30s.
2. **SHUT DOWN FB PIPELINE** (carried over urgent). 2 commands, ~2 min. See TASKS.md.
3. **iPhone tap-through the `is_active` split UI from yesterday's session.** (PresetManager green dot, kebab menu, Show hidden toggle.)
4. **Git pull on Oracle VM** for `run_yad2.py scan_enabled` field change.
5. **Monitor `/api/debug/recent-errors` over 24h.** If the pool fix worked, no new `SSL connection closed unexpectedly` errors should accumulate. After 24h clean, gate or remove the debug endpoint.
6. **08:00 IDT scan health check** — expect 6 Yad2 + 1 Madlan sessions (presets 7/8/11/12/13/23 + 44). Preset 9 should NOT appear.

## Watch out for

- **Alan correctly pushed back on the telemetry premise mid-plan.** The first brief I proposed was conversion-analytics ("which signals convert to phone reveals"). Alan challenged it — at n=2 users, direct conversation beats instrumentation. I conceded. We pivoted to **telemetry as UX bug detector** (errors, warnings, friction), which delivers value from day 1 at this scale. **Lesson:** question "strategic priority" items from multiple-hop handoffs against current reality. The "telemetry Monday-morning priority" framing had propagated across 4+ handoffs without anyone checking whether it was still the right frame.
- **Reviewer caught 3 real design issues before exec.** (1) monkey-patching `window.fetch` → instrument `apiFetch` instead (cleaner, no recursive-log risk). (2) rage-tap detector too hand-wavy → cut entirely per Alan. (3) PropertyCard has `yad2_id` not `property_id` → backend must resolve. Alan's decision to ship AFTER revise without a second review was correct — remaining issues were mechanical.
- **Two git worktree footguns dodged:** (a) Worktree `claude/youthful-sammet` started 16 commits behind main — fast-forwarded at session start before any edits. (b) During exec, 2 more commits landed on main from a parallel session (`c2682b9`, `ed31367`). My commit rebased cleanly, no conflicts. Pattern: **always `git fetch && git rebase origin/main` before pushing from a worktree.**
- **Render rebuilds twice today** — once for the pool fix mid-morning, once for telemetry at end-of-session. Free-tier cold starts between deploys can make any automated calls fail. Tomorrow morning's 08:00 IDT should be past the deploy storm.
- **`/admin/ux-health` has no auth.** Documented as acceptable at n=2 (URL is unlisted) but worth revisiting if the user count grows.
- **Conversation with Alan about "pass to remote session from iPhone"** was parked. Short answer: target session must be cloud (remote), not local — local Mac sessions aren't reachable from iPhone. No single settings.json toggle exists; options are a shell alias or just starting sessions from iPhone directly.

## Test these

- [ ] `https://pdis-lsah.onrender.com/admin/ux-health` renders on iPhone (no NavBar)
- [ ] Red section empty (or only real errors)
- [ ] Green strip shows non-zero `page_views_24h`, `phone_reveals_24h`, `sessions_24h`
- [ ] Tap phone reveal on a property → event in admin within 30s, signals snapshotted in metadata
- [ ] Over 24h, `curl .../api/debug/recent-errors | jq '.count'` stays flat (no new SSL-closed entries)
- [ ] 08:00 IDT VM run: 6 Yad2 presets + 1 Madlan preset 44 = 7 `done` sessions
- [ ] PresetManager kebab menu shows "Hide from app" / "Show in app" correctly
- [ ] Dashboard pill count does not include presets 9, 12, 13, 44

---

*Archived sessions:*
- *HANDOFF_2026-04-17.md — yesterday's `is_active` split session.*
- *HANDOFF_2026-04-16_evening2.md — Apr 16 evening.*
- *HANDOFF_2026-04-15_night2.md — Apr 15 night.*
