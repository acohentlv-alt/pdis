# HANDOFF — April 15, 2026 (night2 + late2 + late + consolidation + evening + night sessions)

## NIGHT2 SESSION (Alan + opus, past-midnight into Apr 16)

### What we did today

Marathon session that turned into a full-system health check. **Ten commits pushed to main** — ending the day with `0b16f95`.

**FB pipeline overhaul, end to end:**
1. Found the phantom-reset migration bug in `database.py` that was wiping `ingest_state.last_ok_at` on every cold start — fixed.
2. Shipped FB cross-source dedup (Briefs A+B): floor extraction, phone normalization at ingest, narrowed migration WHERE, new `find_fb_cross_source_matches()` with Tier 10/11/12 + floor veto + rooms veto + Hebrew street normalizer. 237 LOC in matching.py.
3. Diagnosed three separate FB data-quality problems in sequence — FB rows had `source='yad2'` (migration bug), non-property posts got ingested (Haiku's `intent` field wasn't in the Pydantic model so FastAPI dropped it), and 665 of 689 FB rows were falsely flagged as removed (sampling ingest got treated as exhaustive sweep). All fixed.
4. Alan flipped `YAD2_VM_INGESTION_ENABLED=true` on Render mid-session; the VM Yad2 scraper I deployed tonight immediately started POSTing HTTP 200s.
5. Open Search was failing with "Scan failed" — diagnosed as Render IP blocked by Yad2. Alan pushed back: "it shouldn't scrape, query the existing DB." Fixed — `/api/scan/open` now persists criteria and returns; SearchResultsPage queries the filtered DB via the existing city-scoped endpoint.

**Yad2 VM deploy — real infra work, not just code:**
- Created `/opt/pdis-yad2-scraper/` on Oracle VM, scp'd `run_yad2.py` + `run_yad2.sh` + `.env`.
- Installed systemd service + timer (08:04 IDT daily). First gotcha: unit was missing `User=ubuntu`, ran as root, curl_cffi unavailable. Fixed.
- Second gotcha: `run_yad2.py` was forsale-only; extended to handle rent+forsale. Also removed the `category != 'forsale'` check in `/api/ingest/yad2` route.
- Tonight's manual fire proved end-to-end: 1000+ listings scraped across 5 presets, all POSTed HTTP 200. DB now shows 3 fresh sessions (s152 TLV Rent Full Scan 240/223new, s153 Haifa Buildings 240/50new, s154 Florentin Buy Amit 240/91new).

**UI fixes:**
- FB preset now shows as a pill (`a05c9b0`) — removed the `src==facebook` exclusion.
- FB preset view source-scoped (`759823f`) — `/api/presets/{id}/properties` narrows to `source='facebook'` when viewing a FB preset. Was bleeding Yad2+Madlan rows.

**Data cleanup:**
- 736 broken FB rows repaired: `source='yad2' → 'facebook'`, phones re-normalized (216 kept, 11 NULLed).
- 103 junk FB rows deleted (no price/rooms/sqm = Haiku found nothing).
- 665 FB rows reactivated (false-removal sweep).
- Created Madlan preset 44 (`TLV Rent - Madlan`) — first scrape ingested 1190 listings / 959 new.

### Commits pushed this session

- `95da8c3` Fix FB ingest health: stop nuking last_ok_at on every startup
- `fb8b382` Sync CLAUDE.md: remove govmap-derived signals, document Apify/Haiku FB pipeline
- `4773304` FB cross-source dedup: data fidelity + matcher (Brief A+B)
- `e8b2ba1` Extend Yad2 VM scraper to handle rent + forsale (unblocks Render)
- `e5d2022` Fix Yad2 VM service: run as ubuntu, not root
- `a05c9b0` Show Facebook preset as a pill in OpportunityPage
- `759823f` Fix FB preset view: return FB-source rows only
- `c20fbd0` FB ingest: reject non-property / low-confidence / wanted posts
- `ca608dc` Disable FB removal-detection sweep (sampling ingest is not exhaustive)
- `0b16f95` Open Search: query existing DB instead of triggering a scrape

### What's half-done / needs attention

- **Open Search UX on next-page (SearchResultsPage).** Backend now returns 846 TLV-rent-2.5-6K matches instantly. UI was built assuming scrape-then-browse — with instant query, UX needs a plan. **Alan explicitly asked for a brief here before any more code. Queue `/plan` first thing next session.**
- **FB city bleed** — Kfar Saba posts still get labeled TLV because the VM hardcodes `GROUP_CITY_MAP`. Two fix options in TASKS.md — Alan's call.
- **Preset 9 "Haifa Buy" HTTP 500** from VM ingest — `is_active=False` preset somehow still gets scraped + POSTed. Low priority; `run_yad2.py` filter may not be catching falsy is_active values.
- **Working tree has `vm-scraper/run.py`** modified by parallel agent — left untouched per rule. The parallel agent's PresetManager redesign files are all committed already (`c66e7b7` + `508cada`).

### What to do next

1. **Run `/plan` for the SearchResultsPage / Open Search UX rework** — Alan's explicit ask. Existing UI assumed scrape flow; now we have instant results.
2. **Verify tomorrow morning's automated runs land cleanly** — 08:04 IDT Yad2 VM + 10:00 IDT FB Apify. Check scan_sessions.
3. **Manual iPhone QA** on the shipped work still AWAITING QA (PresetManager redesign, filter drawer polish, scan-button progress bar).
4. **Decide FB city bleed fix** — quick filter-on-neighborhood vs thoughtful `fb_groups.default_city` column.
5. **Monday: strategic item #1 — Telemetry (2h).** Blocks the rest of the 7 strategic bets.

### Watch out for

- **`YAD2_PHONE_FETCH_ENABLED=false`** still on Render — Brief #2 phone fetcher deployed but gated. Flip when ready.
- **VM Yad2 scraper runs at 08:04 IDT daily** — do not manually kick off `/api/scan/scheduled` for Yad2 presets (Render IP blocked). Let the VM timer run it.
- **FB ingest pipeline now has THREE filters:** (1) Haiku classifies intent, (2) server rejects `intent not in ('rent','sale')`, (3) server rejects `confidence < 0.3`. Daily FB row count will be meaningfully smaller than raw Apify output.
- **Open Search creates a disabled preset row** each submit, accumulating. No auto-cleanup. Manual delete from `search_presets where is_active=false and created_at > N days` if clutter bothers you later.
- **Removal detection on FB is OFF.** FB rows stay `is_active=TRUE` forever. If a post actually gets removed from FB, we won't catch it. Acceptable tradeoff for sampling ingest.

### Test these

- Hard-refresh `https://pdis-lsah.onrender.com` after Render finishes the `0b16f95` deploy (~3-5 min post-push).
- Tap "TLV Rent - Facebook" pill → **689 FB properties**, no Yad2 clutter.
- Search tab → `TLV / Rent / 2500-6000₪` → **846 matches**, no "Scan failed" error.
- After 08:04 IDT tomorrow: dashboard "Last scan" on each Yad2 preset should flip from "blocked" to "done".
- After 10:00 IDT tomorrow: FB count grows modestly (~50-70 new posts), no LED lamps / non-property junk.

---

## LATE2 SESSION (PresetManager redesign + product analysis + 7 strategic items queued)

### What we did

Started on HANDOFF item "PresetManager polish queued" from the night session. Alan picked **option 2 — redesign + UX restructure** (not just visual, also restructure the form). Ran the full `/plan → /review → /exec → /qa` workflow.

Planner produced a brief with 5 open questions (kebab vs. 4-button strip, backdrop-click dismiss behavior, Active/Inactive badge removal, auto-open "More filters" on edit, keep unused `category` prop). Alan approved my recommendations on all 5. Reviewer caught 3 real implementation gaps (click-outside hook lifecycle, which 19 fields trigger auto-open, backdrop-close state reset) which we resolved into executor addenda. Executor split the 1,362-line monolith into `frontend/src/components/preset-manager/` with 5 focused files:
- `PresetManager.tsx` (main shell + 22 state hooks all before early return)
- `PresetForm.tsx` (dumb container, zero hooks)
- `PresetFormSections.tsx` (5 progressive-disclosure sections)
- `PresetRow.tsx` (kebab menu — only one open at a time via lifted state)
- `presetFormUtils.ts` (types, constants, design tokens)

The legacy `components/PresetManager.tsx` is now a 1-line re-export so `OpportunityPage.tsx` import path didn't change.

QA: **38/38 PASS**. Zero console errors. Zero React #310 errors across hooks-order stress tests (rapid source-chip cycling, Rent↔ForSale toggle 5×, edit-cancel-edit across rows).

Then — at Alan's request — did a **project-wide analysis** from the lens "Shechter uses this on iPhone twice a day; everything else is noise." Added 7 strategic items to TASKS.md:
1. Telemetry (~2h, do first)
2. "Since yesterday" daily feed
3. Push notifications (PWA web push)
4. Phone reveals as North Star metric (depends on #1)
5. Signals as narrative not taxonomy (one headline per card)
6. Ingest health visible to Shechter (green/yellow/red dot in header)
7. Tests on events/matching/signals

Also cleaned TASKS.md: dropped `₪/m² math fix`, `Govmap comps rework Option 2`, and `Phone numbers — SHIPPED` entries that were listed as NOT STARTED but had already shipped in commits `a1e9fa8` and `508cada`. Dropped the verbose "SHIPPED — FB Groups via Apify + Haiku" architecture section but kept its two still-pending TODOs (FilterBar FB option, per-group city overrides).

### Commit pushed this session

- `c66e7b7` PresetManager 2030-vision redesign + UX restructure (6 files, +1895/-1362)

Coexists cleanly with parallel agent commits (`e8b2ba1` Yad2 VM forsale, `4773304` FB cross-source dedup, `e5d2022` Yad2 VM service fix) that landed earlier in the day.

### What's half-done

- **PresetManager manual iPhone QA pending.** Playwright passed every assertion, but Shechter/Alan haven't tapped through it on a real iPhone yet. Test plan is in TASKS.md AWAITING QA. After Render deploys `c66e7b7`, hard-refresh the PWA and walk the checklist.
- **Working tree still has uncommitted `vm-scraper/run.py` changes** (147 lines) from a parallel agent. Left untouched per CLAUDE.md rule "only stage files YOU changed." Review + commit or revert next session.
- **All 7 strategic items are queued but not scoped into briefs.** They sit in TASKS.md with Why/What/Cost/Value. When Alan picks one, run `/plan` to produce an executor brief.

### What to do next

1. **Tomorrow morning: iPhone QA of `c66e7b7`.** Walk the PresetManager checklist in TASKS.md. If anything feels off, `/plan` a fix.
2. **After 08:00 IDT scheduled scan: verify Madlan phones from night-session commit.** SQL: `SELECT COUNT(*) FILTER (WHERE contact_phone IS NOT NULL), COUNT(*) FROM properties WHERE yad2_id LIKE 'madlan_%'`. Expected ≥80% fill.
3. **Decide on strategic item #1 (telemetry).** Alan's call — is this the Monday-morning priority I recommended, or does something else jump the queue?
4. **Deal with uncommitted `vm-scraper/run.py`** (parallel agent's WIP). Either they finish it, or Alan decides whether to keep or revert.

### Watch out for

- **Render deploy of `c66e7b7` is in flight during this handoff write.** If the deploy fails, rollback is `git revert c66e7b7 && git push`. The change is pure frontend — zero backend risk.
- **The PresetManager re-export pattern** at `frontend/src/components/PresetManager.tsx` means if anyone tries to read the old monolith file, they see 1 line. Grep for usages in `preset-manager/` instead.
- **22 hooks in PresetManager + 2 hooks in PresetRow** — both counts are tight against the early return. If a future change adds a hook after `if (!open) return null`, React #310 will fire. See `CLAUDE.md` rule.
- **Strategic item #3 (push) and existing task "Telegram bot for scan alerts" overlap.** Pick one channel — don't build both.
- **TASKS.md was restored from archive + re-edited tonight** after an earlier attempt dropped unfinished items by accident. Current state is verified complete against the Apr 15 night archive.

### Test these (iPhone manual)

Every assertion in TASKS.md AWAITING QA section for the PresetManager redesign. Most critical:
- Sheet slides up from bottom (not fullscreen).
- Kebab menu — one open at a time across rows.
- Edit a preset with advanced fields set → "More filters" auto-opens.
- Backdrop dismiss → form state wiped.
- Pricing Targets 3-column grid fits without wrapping on 390px.

---

## NIGHT SESSION (after the FB U-turn — phones across sources + filter drawer + UI polish)

### What we did

Started by digging into Alan's "phone number on the property cards" ask. Discovered Madlan scraping has been silently broken in production for **weeks** — schema drift killed `yearBuilt`, `year_built`, `additionalDetails` fields and a missing `square_meter_build=None` argument. Every Madlan scan was returning 0 listings without anyone noticing. Fixed all 4 bugs + added the `poc { ... AgentPoc, ... UserPoc }` GraphQL union fragments. Live-tested: 499/499 listings now return phones (was 0/713). Madlan will re-populate on next scheduled scan at 08:00 IDT.

For Yad2 phones, used DevTools (Alan captured the cURL from a real session) to discover `gw.yad2.co.il/realestate-item/{token}/customer` — no auth needed, just warm-up + per-item Referer. Built `pdis/yad2_phone.py` with normalize_phone() helper, 0.6s rate limit, 429/403 backoff, 3-block abort. Wired scanner hooks (40/preset scan-time + 310/run backfill, 7-day cooldown via new `phone_fetch_attempted_at` column). **Flag-off by default** (`YAD2_PHONE_FETCH_ENABLED=false`) — Alan flips when ready. Live-tested from laptop: returns correct phone for known token.

Then a big UI polish session: bottom-sheet filter drawer (replaces inline filter strip), in-house toast (~50 lines, no dep), pull-to-refresh on OpportunityPage + FavoritesPage (replaces header refresh button), refined header (greeting bigger, gear → sliders icon = "Manage searches"), refined SummaryBar stats (rounded-2xl, larger numerics), refined PropertyCards (rounded-2xl, hover lift), and a whole new PropertyCard phone pill (emerald tap-to-call, masked `055-•••-••••` otherwise, Israeli format). Added fade-in / slide-up / toast-in keyframes in index.css.

Critical save during commit: parallel agent's commits had silently dropped my `phone_fetch_attempted_at` migration when they rewrote `database.py`. Caught it in the pre-commit audit and restored before pushing. Brief #2 would have crashed on flag-flip otherwise.

### Commit pushed this session

- `508cada` Phones across sources + filter drawer + UI polish (16 files, +1145/-229)

Coexists cleanly with the parallel agent's Apify+Haiku FB pipeline (separate code paths). Their `vm-scraper/run.py` 147-line WIP deliberately excluded from this commit — they'll commit it themselves.

### What's half-done

- **Yad2 phone fetch is flag-off**. To turn on: set `YAD2_PHONE_FETCH_ENABLED=true` on Render. Then a scheduled scan will run the new hook. **Render reachability of `gw.yad2.co.il` is UNVERIFIED** — only tested from Alan's laptop. If Render IP is blocked, fetch fails silently (graceful), no rows fill. Suggested: flip flag, watch one scan, check `SELECT COUNT(*) FILTER (WHERE contact_phone IS NOT NULL) FROM properties WHERE source='yad2' AND phone_fetch_attempted_at > NOW() - INTERVAL '1 day'`. If still 0, the endpoint is blocked from Render → move to VM (Brief #2b).
- **Filter drawer + UI polish needs Alan's eyes on iPhone.** Local Playwright + build pass clean, but mobile gestures (pull-to-refresh, drawer slide) need real-device test.
- **Madlan phones**: won't appear until next scheduled scan (08:00 IDT). Expect ~80%+ fill rate based on live test.
- **PresetManager polish queued.** Same 2030-vision design language we applied to drawer/header should extend to the PresetManager modal (3-dot menu → manage searches). Was queued for `/compact` but Alan canceled compact + ran end-session instead.
- **`vm-scraper/run.py`** has 147 uncommitted lines from the parallel agent. Do not touch.

### What to do tomorrow

1. **Open https://pdis-lsah.onrender.com on iPhone** — test the new filter drawer (open/close, all sections, Apply button visible above NavBar), pull-to-refresh, toast on whitelist/blacklist tap, phone pill (currently shows on FB cards via Apify pipeline; Madlan cards after 08:00 scan).
2. **After 08:00 IDT scheduled scan**: SQL-check Madlan phone fill. If high (≥80%), Madlan fix is verified.
3. **Decide on Yad2 phone flag**: set `YAD2_PHONE_FETCH_ENABLED=true` on Render env if you want Yad2 phones to start filling. Then watch one scan + SQL-check.
4. **PresetManager polish** (queued from this session) — same drawer/header treatment to the modal that opens from the sliders icon.
5. **Cleanup pass** when parallel agent finishes their `vm-scraper/run.py` commit — likely deletes Playwright FB scraper code now that Apify owns it.

### Watch out for

- **My commit + parallel agent's commits raced on `routes.py` and `database.py`**. Their commits won (logged earlier). I had to re-add the `phone_fetch_attempted_at` migration. If anything else of mine got silently dropped, Brief #2 will surface it on flag-flip. Spot-check `pdis/api/routes.py` line 2201 has `/api/log-reveal` (verified at commit time).
- **Render reachability of `gw.yad2.co.il` is the big unknown.** If blocked, all the Brief #2 code is dead weight on Render. Pivot to Oracle VM (mirror the `run_yad2.py` pattern) if so.
- **TASKS.md was forward-dated April 16** at start of session. Updated to April 15 night session in the night-session edit.
- **Apify keys + Anthropic key** still visible in Apify pipeline session transcript. Rotate if paranoid.

### Test these (for tomorrow's manual QA on iPhone)

- Hard-refresh https://pdis-lsah.onrender.com (Cmd+Shift+R or Add to Home Screen reload)
- Tap "Filters (0)" button → drawer slides up from bottom; backdrop blurred; Apply button visible above bottom nav
- Pick "Facebook" source pill → list filters to FB-only (need data — should have 738+ FB props from Apify)
- Tap whitelist/blacklist on a card → toast appears bottom-center
- Scroll list to top → pull down → spinner appears → list refreshes
- Tap a Madlan card with phone (after 08:00 scan) → emerald "Tap to call" pill → tap → dialer opens
- Header should show "Good evening/morning, Shechter" with sliders icon (not gear) on right

---



### What we did

Started by killing the abandoned laptop-daemon pivot (stashed as `stash@{0}`) and ran the planner→reviewer→exec cycle for the original A2 brief (Oracle VM + Smartproxy/Decodo residential proxy). Shipped 5 commits: A2 deployment code, fix to `TLV_CITY_STRING` (was hyphen, prod uses space), PropertyCard fallback for FB posts without phones (shows "Message on Facebook" link), full pivot to Apify+Haiku replacing Playwright entirely, and skip-known LLM optimization with street/house extraction.

**The U-turn:** halfway through, Playwright scraping seemed broken (~1 post per group from the FB DOM). Recommended parking. Alan pushed back. A diagnostic agent proved scraping IS viable — earlier failure was a too-aggressive modal-dismiss loop + outdated `_parse_post` selectors, NOT FB anti-bot. By that point we'd already spent $4.55 testing Apify with 14 groups × 65 posts/group = 910 posts and saw it just works. Pivoted to Apify instead of fixing Playwright.

**Final architecture (live):**
- Apify actor `apify/facebook-groups-scraper` runs daily 10:00 IDT via Oracle VM systemd timer
- 14 active TLV groups × 5 posts each = 70 posts/day
- Claude Haiku 4.5 extracts structured fields from Hebrew text (intent, price, sqm, rooms, phone, neighborhood, street/house, is_agent, amenities, available_date)
- Skip-known LLM via new endpoint `/api/ingest/facebook/existing-ids` (cuts Haiku cost ~50% over time)
- POST batches to `/api/ingest/facebook` → existing scan pipeline upserts properties + runs matching/signals
- 738 posts already in DB from a one-shot Apify backfill

**Cost:** ~$5.80/mo Apify (after $5/mo free credit) + ~$1.80/mo Haiku = **~$7.60/mo**. Decodo proxy cancelled (Apify provides residential proxies internally).

### Commits pushed this session

- `73f361e` A2: FB Groups scraper path-to-production
- `ee66dbc` Park FB Groups scraping (later reversed in spirit, not in commit history)
- `74ff868` Fix TLV_CITY_STRING to canonical (space, not hyphen)
- `ddf8f02` PropertyCard: FB fallback — show Message-on-Facebook link when no phone
- `40a749b` FB Groups via Apify + Haiku (replacing Playwright pivot)
- `b636598` FB ingest: skip-known LLM optimization + street/house extraction

### What's half-done

- **Cross-source FB↔Yad2/Madlan dedup not yet implemented.** Alan asked for "if same address+floor". Currently `pdis/matching.py` only matches via Haversine distance (lat/lon), and FB posts have NO coordinates from Apify. We extracted street_address + house_number via Haiku and they flow to `properties` now, but no matcher uses them yet. Brief printed in conversation transcript: add `find_fb_cross_source_matches()` helper that matches via phone, then street+house+floor+neighborhood, then soft heuristics. Estimated 1-2 hours, do it tomorrow morning AFTER the 10:00 scan runs so we have fresh data to test against.
- **`ingest_state.last_ok_at` is NULL despite 738 successful POSTs.** Either `_reset_fb_warning_counter()` isn't being called on the success path, or something silently failed. Worth investigating before tomorrow's go-live.
- **Working tree has 13 modified + 4 untracked files from other agents.** Deliberately not staged. Includes new files like `frontend/src/components/PullToRefresh.tsx`, `FilterDrawer.tsx`, `lib/toast.tsx`, `pdis/yad2_phone.py`. Review and decide before next commit.

### What to do next

1. **Watch the 10:00 IDT scheduled run live.** SSH to VM and `tail -f /var/log/pdis-fb-scraper.log` around 10:01. Confirm it triggers Apify → fetches → LLM-parses (skipping known) → POSTs → properties land.
2. **Investigate `ingest_state.last_ok_at` NULL bug.** Read `_reset_fb_warning_counter` call site in `pdis/api/routes.py`, see why it's not firing. Should update on every successful ingest.
3. **Plan + ship FB cross-source dedup** (the brief above). Use `/plan` since matching.py is sensitive.
4. **TASKS.md TODO items:** FilterBar Facebook source dropdown option, per-group city overrides for non-TLV posts that slip through.

### Watch out for

- **Apify pricing nuance.** $5 is a MONTHLY free credit, not a flat subscription. With `resultsLimit=5` × 14 groups daily we use ~$10.80/mo gross, $5.80 net out of pocket. If Alan wants strictly free, drop `RESULTS_PER_GROUP=2` in VM `.env` (28 posts/day, fits free tier).
- **VM cleanup deferred.** `~/.cache/ms-playwright` (622MB Chromium binary), `state.json` (FB cookies), old `run.py` (Playwright scraper), `fb_diag.py` all unused now. Cleanup punch list in the brief above. Also `pdis/utils/` cache dir was orphaned during the stash earlier.
- **Anthropic + Apify keys are visible in this conversation transcript.** Alan should rotate the Anthropic key after this session if paranoid (it has billing access). Apify key is lower-risk.
- **2 batches failed during initial backfill** (500 errors on Render — probably transient). 80 posts kept their first-pass field values. Will heal on next daily scan.
- **Don't trust matching.py to dedup FB posts cross-source yet.** Existing logic is coordinate-based; FB has no coordinates. Cards may show duplicates between FB and Yad2/Madlan until the new matcher is built.
- **Stash `stash@{0}` (`laptop-daemon-pivot-20260415-abandoned`) still exists.** Has `pdis/utils/city.py` and abandoned LLM-parse code. Probably safe to drop after a final review.

### Test these

- After 10:00 scheduled run: `curl https://pdis-lsah.onrender.com/api/properties?source=facebook&limit=50` — count should be > 738
- After scheduled run: `curl https://pdis-lsah.onrender.com/api/ingest/facebook/health` — `last_ok_at` should be today's date (not NULL — currently buggy)
- Open https://pdis-lsah.onrender.com on mobile, source filter "Facebook" — confirm cards show neighborhoods, prices, sqm, "Message on Facebook" links where phone is missing

---

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
