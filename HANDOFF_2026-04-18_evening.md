# HANDOFF — April 18, 2026 (afternoon/evening session: Madlan latency fix + VM redeploy)

## What we did today

Four things shipped or handled:

- **Madlan/preset latency fix (this session's commit).** Telemetry flagged `/api/presets/44/properties?per_page=2000` taking 8-14s on mobile (30+ `slow_response` events across 10 user sessions). `/plan` found the root cause wasn't Madlan-specific — it was `SELECT p.*` shipping a 9 KB `raw_data` JSONB blob per row across 1,715 rows. `/review` caught two small issues (is_active contradiction, 5 unaccounted columns); `/exec` swapped three endpoints (`get_preset_properties`, `get_amit_fit_properties` fetch, `custom_search`) to an explicit 35-column list. `/qa` 7/7 PASS: preset 44 payload **8.6 MB → 3.9 MB (-54.6%)**, custom search **10.2 MB → 4.6 MB (-55.6%)**, row counts identical, all UI-critical fields preserved.

- **Oracle VM git pull + run_yad2.py redeploy.** `~/pdis` on the VM was **50+ commits behind origin/main**. Pulled, then `sudo cp ~/pdis/vm-scraper/run_yad2.py /opt/pdis-yad2-scraper/` — otherwise tomorrow's 08:00 IDT scan would have filtered on the dropped `is_active` field (previously silent breakage). Verified: deployed file now uses `scan_enabled` + has the `$HomeNum` template-token stripping from `80aa479`.

- **QA noise cleanup in `ui_events`.** 19 synthetic test events deleted from prod DB (session `5d5cfd73-abfe-428c-bd7c-0e3b400ad033` + `qa-check` — the events that made Alan's iPhone screenshot show "12 events in same session" of 404s against a non-existent property). Admin page error count now 0.

- **FB pipeline mystery resolved.** `pdis-fb-scraper.service` has been `failed, exit code 1` since Apr 10 or so. Alan clarified: Apify was on the free plan with a **$5 trial credit** (not a rate). Credit exhausted → actor returns 402 → scraper exits 1. **The "$5/day bleed" narrative across the last 2-3 handoffs was wrong.** No cost ongoing. Timer still fires daily and noops; disable it if the log noise bothers you.

## What's half-done / needs attention

- **Today's commit is AWAITING Render deploy + iPhone test.** After this HANDOFF is pushed, Render rebuilds (~3-5 min). Then open preset 44 on the iPhone — cards should render in 2-3s, not 8-14s.
- **`/admin/ux-health` warnings** — the `empty_state` events firing on `preset_null` look like false positives from the split-second before a preset is selected on mount. Noisy but harmless. LOW priority to debounce.
- **The same payload bloat pattern exists in 3 more endpoints** that weren't in scope: `/api/favorites`, `/api/whitelist`, `/api/blacklist` (all `SELECT p.*`, all render through `PropertyCard`). Reviewer flagged this as a follow-up task, now in TASKS.md.
- **`is_active` iPhone tap-through** still pending from Apr 17's work. Backend verified but the UI path hasn't been hands-on-phone tested.

## What to do next

1. **iPhone test the Madlan fix on Render.** After the push, wait ~3-5 min for deploy, then tap preset 44 on your phone. It should load in 2-3s instead of 8-14s.
2. **Alan's new product direction — "companies that need to sell" / "הוצאה לפועל" (execution office) / "פשיטות רגל" (bankruptcies).** Raised at end-of-session. This is a meaningful scope expansion: PDIS currently detects distress from **listing signals** (price drops, relistings, time on market, weak language). Alan wants to add a second source — **owner-side distress** (court-ordered sales, bankruptcy liquidations, execution-office proceedings). Needs its own `/plan` session: what Israeli data sources exist, are they scrapable for free, what UI surface this gets in the app, how it interacts with the existing signals model.
3. **Optional cleanup**: disable `pdis-fb-scraper.timer` to stop daily failure log lines. One SSH command.
4. **24h monitor**: `curl .../api/debug/recent-errors | jq '.count'` should stay flat (Neon pool fix from `c0d0433` is 24h old tomorrow morning).

## Watch out for

- **Worktree `claude/youthful-sammet` is 1 commit behind main** as of this session start, and today's commit will go to main from the main checkout (not the worktree). If a future agent reaches for that worktree, they'll need to fast-forward first. Memory note from earlier sessions still applies: parallel agents + shared main checkout = footgun.
- **`/opt/pdis-yad2-scraper/` is NOT a git repo.** Redeploying the VM's Yad2 scraper is a two-step dance: `git pull` in `~/pdis`, then `sudo cp ~/pdis/vm-scraper/run_yad2.py /opt/pdis-yad2-scraper/`. "Git pull on Oracle VM" in prior handoffs was misleading — a plain pull doesn't touch `/opt/`. I've noted this in memory.
- **Apify free plan is a trial balance, not a daily cap.** Once spent, the actor fails permanently unless Alan tops up. Any future "$5/day" phrasing in handoffs is wrong. I've noted this in memory.
- **This session's fix doesn't change the frontend `per_page=2000`.** Planner flagged it as a follow-up — if mobile is still sluggish after the payload shrink, the next lever is paginating the list instead of loading 1,715 cards at once. Not needed yet; re-measure with the new payload first.
- **Reviewer proactively identified the "same bloat in 3 other endpoints" issue** without being asked. Good catch — saved us from a partial fix that would have looked complete until Alan opened the favorites page.

## Test these

- [ ] Preset 44 on iPhone Render: cards visible in 2-3s (was 8-14s)
- [ ] `curl https://pdis-lsah.onrender.com/api/presets/44/properties?per_page=2000 -w "%{size_download}"` ~ 3.9 MB
- [ ] `/admin/ux-health` over 24h: `slow_response` events on `/api/presets/%/properties%` drop to ~0
- [ ] 08:00 IDT tomorrow: 6 Yad2 presets + 1 Madlan preset 44 = 7 `done` sessions. **Preset 9 should NOT appear** (scan_enabled=false).
- [ ] `/api/properties/{yad2_id}` detail page on a property — should still render fully (raw_data intact; out of scope for this fix).

---

*Archived sessions:*
- *HANDOFF_2026-04-18_morning.md — Apr 17-18 day→evening session (pool fix + telemetry).*
- *HANDOFF_2026-04-17.md — Apr 17 is_active split session.*
- *HANDOFF_2026-04-16_evening2.md — Apr 16 evening.*
- *HANDOFF_2026-04-15_night2.md — Apr 15 night.*
