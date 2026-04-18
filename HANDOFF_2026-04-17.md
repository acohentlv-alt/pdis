# HANDOFF — April 17, 2026

## What we did today

Shipped one big refactor: **split `search_presets.is_active` into two independent booleans — `scan_enabled` + `is_visible`**. One commit on main (`c2682b9`), pushed, Render rebuilding.

**Root cause we fixed:** yesterday Alan hid preset 44 (Madlan) via the new "Show hidden" toggle thinking it would just hide the pill — but the single `is_active` flag controlled BOTH "show in UI" AND "scan this preset." Result: Madlan (and three other hidden Yad2 presets) silently stopped scanning. Data went stale, no price drops, no removals detected.

Now the two concerns are independent. Preset row's green dot toggles scanning; kebab menu → "Hide from app"/"Show in app" toggles visibility. Backfill applied as: 9 → both OFF (throttling, stays off), 12/13/44 → scanning ON, hidden from UI.

Ran the full `/plan → /review → /exec → /qa` cycle. Reviewer caught 5 wrong-table citations (`properties.is_active` vs `search_presets.is_active`), backfill DEFAULT-TRUE bug that would have left preset 9 silently scanning, and missing `/toggle` endpoint consumer list. All fixed in revision. QA 15/15 locally.

Morning check confirmed yesterday's ship (fire-and-forget, Amit Fit split, Show hidden toggle, Yad2 token cleanup) all worked — 4/4 active Yad2 presets done clean at 08:09–08:32 IDT.

## What's half-done / needs attention

- **Oracle VM still on old `run_yad2.py`.** Today's commit changed `p.get("is_active")` → `p.get("scan_enabled")`. Until VM pulls, VM keeps reading `is_active` (which is still TRUE for scan-enabled presets because backfill matched them, so functionally fine — but cleaner to pull). SSH command in TASKS.md.
- **Apify FB pipeline still running — burning $5/day.** Alan flagged it this morning and asked to shut down. We never got to it (pivoted into the `is_active` split instead). Still hot. Shutdown procedure in TASKS.md.
- **Alan mentioned "new ideas" he wanted to discuss after the FB shutdown.** Never got to those. Pick this up next session.
- **Amit Fit `category` param silently ignored.** QA noticed `/api/amit-fit/properties?category=rent` and `?category=forsale` both return 81 rows. Pre-existing bug from `0f97418`. Backlog.
- **`/api/debug/recent-errors`** still temporary. Today's monitoring didn't need it — remove or gate soon.

## What to do next

1. **SHUT DOWN FB pipeline** (see TASKS.md "READY TO RUN"). Two commands, ~2 min. This was Alan's explicit request this morning.
2. **Git pull on Oracle VM** for `run_yad2.py` scan_enabled fix. One command.
3. **iPhone tap-through the split UI on Render:**
   - Dashboard pills — presets 9/12/13/44 absent.
   - PresetManager → "Show hidden" toggle reveals them greyed out.
   - Kebab menu → "Hide from app" / "Show in app" items visible.
   - Green dot toggles scanning independent of visibility.
4. **Verify tomorrow's 08:00 + 10:00 IDT scans.** Expect Yad2 sessions for presets 7/8/11/12/13/23 + Madlan for preset 44. Preset 9 should NOT appear.
5. **Pick up "new ideas" conversation** Alan flagged this morning.
6. **Strategic item #1 (telemetry)** still the Monday-morning priority.

## Watch out for

- **Deploy gap window, ~5 min.** Old frontend builds calling `/api/presets?is_active=true` will still work — the deprecated alias maps to `scan_enabled`. But between push (~14:05 IDT) and Render finishing (~14:10 IDT), users may see brief glitches if the browser cache mixes old FE + new BE.
- **`search_presets.is_active` column kept for now.** Nothing writes to it. In 1 week, drop the column + remove the deprecated `?is_active` alias. Task is queued.
- **Worktree branch was 28 commits behind main.** Caused a painful rebase/cherry-pick round with 5 conflicts including PresetManager.tsx being moved into a subdirectory between the branch's base and main. Lost ~30 min. Lesson for future: rebase worktree onto main before starting work, not after.
- **Executor initially wrote edits to the OLD `frontend/src/components/PresetManager.tsx`** (which on current main is just a 1-line re-export stub). Had to spawn a second executor for the real `preset-manager/` subdir. This worked but was wasteful. Pattern to watch: when a worktree is stale, grep both the worktree tree AND current main before exec.
- **The `YAD2_PHONE_FETCH_ENABLED` flag** still false on Render. Yad2 phones NOT yet being fetched. Not related to today's work but reminding.

## Test these

- [ ] **Hard-refresh** `https://pdis-lsah.onrender.com` on iPhone after Render finishes. Dashboard pill row should NOT include presets 9, 12, 13, 44. Pill count drops by 4 vs yesterday.
- [ ] **Open PresetManager → toggle "Show hidden"** — greyed rows for the 4 hidden presets appear.
- [ ] **Tap a hidden preset's kebab** — menu item reads "Show in app". Tap it → refresh dashboard → pill reappears.
- [ ] **Tap a visible preset's green dot** — dot greys out. Refresh PresetManager → still grey. Tap again → green.
- [ ] **Create a new test preset** → both defaults checked, appears in dashboard immediately. Delete when done.
- [ ] **Tomorrow 08:00 IDT** — `/api/scan/sessions?limit=20` shows 6 Yad2 sessions (7/8/11/12/13/23, NOT 9).
- [ ] **Tomorrow 10:00 IDT** — Madlan session for preset 44 appears.
- [ ] **Curl check:** `curl .../api/presets?is_active=true | jq '.presets | length'` returns same count as `?scan_enabled=true` (deprecated alias still works).

---

*Archived: HANDOFF_2026-04-16_evening2.md (the Apr 16 evening session's handoff + morning check from this session).*
