# HANDOFF — April 18-19, 2026 (late-night session: Yad2 rent→VM + phone-hook fix)

## What we did today

Fixed this morning's Yad2 scraper outage the right way instead of the fast way. `/plan → /review → /exec → /qa` cycle on branch `claude/yad2-vm-rent`, one commit (`0ae108e`), pushed to origin but **deliberately NOT merged to main** — VM must deploy first tomorrow morning before Render picks up the changes, or rent data blanks out for ~24h.

Three things landed in one commit:

- **Yad2 rent routed through Oracle VM** (consolidating with forsale that's been on VM for weeks). Render's IPs began getting blocked on `/rent` around April 17 evening — sessions 203/204/207 today's manual trigger all came back `blocked`. Widened the VM-skip guard in `pdis/scanner.py:603-619` from `category == "forsale"` to all Yad2 when `YAD2_VM_INGESTION_ENABLED=true`. VM's `run_yad2.py` parameterized for rent+forsale (was hardcoded `"category": "forsale"` at line 209, `/forsale` slug in the URL at 351-352). VM timer moved 08:00 → 10:00 IDT to consolidate with the rest of the schedule. Render-side fallback `pdis/scraper.py` **kept in place** as rollback safety — reviewer's call; delete in a week after VM rent proves stable.

- **Phone-hook bug caught + fixed.** During the Yad2 plan, reviewer noticed `_yad2_phone_scan_hook` was called from `run_scan` (Render-side path) but **never from `run_scan_from_listings`** (the VM-ingest path). Bug was introduced in commit `508cada` (Apr 15) when the phone hook was wired in — `run_scan_from_listings` had been generalized for Yad2 two days earlier and the hook-wiring author missed that path. Impact: every VM-ingested Yad2 forsale row since Apr 13 has had NULL `contact_phone`. One-line fix: `scanner.py:805-806` now calls `await _yad2_phone_scan_hook(session_id)` when `source == "yad2"`. Currently dormant because `YAD2_PHONE_FETCH_ENABLED=false` on Render — fix pre-positions the pipeline for the flag-flip.

- **"Run Yad2 now" button in PresetManager modal header.** Render's new `POST /api/scan/yad2/manual` endpoint proxies to a new VM HTTP daemon (`vm-scraper/trigger_server.py`, stdlib-only, bearer-auth on port 8787, 10-minute rate limit, 409 if already running, logs every inbound request). UI reuses the existing `useScanStatus()` polling pattern — the VM's ingest POST creates a `scan_sessions` row with progress, so status flows through the normal plumbing. No new progress mechanism needed.

QA ran 22/24 PASS (2 env-only Mac failures, not code bugs). Playwright confirmed the button renders and the error state shows when the mutation 503s.

## What's half-done / needs attention

- **Branch is 1 commit behind main** (evening's Madlan latency fix). Different code areas — should be conflict-free but worth eyeballing the merge.
- **Nothing deployed yet.** Code is on `claude/yad2-vm-rent` on GitHub. Tomorrow morning: VM first, then merge to main, then set Render env vars, then SQL cleanup. **Order matters** — see TASKS.md step sequence.
- **958 rows mistagged** — QA found 958 Yad2 properties under rent presets have `category='forsale'` from the historical `run_yad2.py:209` hardcode bug. One-line UPDATE SQL in TASKS.md step 4. Alan runs it against Neon post-deploy.
- **Today's Madlan latency fix** (committed to main earlier this evening, commit `9d0bd17`) is independent — still needs iPhone test on Render after deploy.

## What to do next

**Execute TASKS.md steps 1-5 in order, first thing:**

1. VM deploy (scp + ssh + systemd). Full copy-paste block in TASKS.md. Generate `TRIGGER_SECRET` with `openssl rand -hex 32` and save it.
2. Merge `claude/yad2-vm-rent` → main via GitHub PR. Render auto-deploys.
3. Set `VM_TRIGGER_URL` + `VM_TRIGGER_SECRET` env vars on Render.
4. Run the 958-row category UPDATE on Neon.
5. iPhone test the "Run Yad2 now" button.

After all that settles, pick back up the product-direction conversation Alan raised yesterday (distressed sellers / הוצאה לפועל / פשיטות רגל).

## Watch out for

- **Deploy order is not optional.** If you merge to main before VM deploy, Render starts returning `skipped_vm` for all Yad2 — but VM has the old `run_yad2.py` that only does forsale. Rent data gap for ~24h until VM catches up. The commit message in `0ae108e` spells this out.
- **`/var/log/` is root-owned on fresh Ubuntu.** Must `sudo touch` + `sudo chown ubuntu:ubuntu` the two log files before starting `pdis-yad2-trigger.service`, or the service crashes on module load. QA caught this locally on Mac (hardcoded path = Mac permission denied). TASKS.md step 1 includes the commands.
- **`fetch_item_detail` in `pdis/scraper.py` is now dead code.** QA found it defined but uncalled anywhere in `pdis/` after `_backfill_built_sqm` was deleted. Not a bug — gets cleaned up in a week when we delete `scraper.py` entirely per rollback-safety plan.
- **Branch push, not main push.** This is deliberate. Don't be confused by the HANDOFF being written without a Render deploy in flight — that's tomorrow's job, not tonight's.
- **Trigger server is bearer-only, no firewall.** Alan couldn't find Render's egress IPs to lock UFW, so we rely on a 32-byte random secret + IP logging on every attempt. If the secret leaks, rotate both ends (VM `.env` TRIGGER_SECRET + Render `VM_TRIGGER_SECRET`) and restart the service.
- **Executor made three judgment calls worth remembering:** (1) added `httpx>=0.25` to requirements.txt (it was transitive, now explicit — harmless); (2) also removed `fetch_item_detail` from the scanner import since its only caller was deleted; (3) chose inline warning icon + native tooltip over a full toast for the Yad2-trigger error. All sensible.

## Test these

- [ ] VM `systemctl list-timers pdis-yad2-scraper.timer` → next run is tomorrow 10:00 IDT
- [ ] VM `curl -s http://localhost:8787/status` → `{"running":false}` (or true if mid-run)
- [ ] VM `sudo journalctl -u pdis-yad2-trigger.service -n 30` → no errors, service active
- [ ] Render env vars `VM_TRIGGER_URL` + `VM_TRIGGER_SECRET` set
- [ ] `curl -X POST https://pdis-lsah.onrender.com/api/scan/yad2/manual` (with whatever auth you use) returns 202 or 503-if-not-configured, NOT 404
- [ ] Run the 958-row UPDATE; `SELECT sp.category, p.category, COUNT(*) FROM properties p JOIN search_presets sp ON sp.id = p.preset_id WHERE p.source='yad2' GROUP BY 1, 2` should show rent/rent increased, rent/forsale at 0
- [ ] iPhone tap "Run Yad2 now" — button disables, sessions appear in `/api/scan/sessions`
- [ ] Tomorrow at 10:00 IDT: fresh Yad2 sessions from VM (rent AND forsale presets), Madlan preset 44 session, Yad2 presets on Render all `skipped_vm`
- [ ] After 10:00 run: `/admin/ux-health` — no new `slow_response` for Yad2 scrape (since Render is no longer scraping)
- [ ] (From evening session) iPhone preset 44 Madlan: cards render 2-3s not 8-14s
- [ ] 24h later: `/api/debug/recent-errors` count stays flat (pool fix from `c0d0433`)

---

*Archived sessions:*
- *HANDOFF_2026-04-18_evening.md — Apr 18 evening (Madlan latency fix + VM git pull + FB-pipeline mystery resolved).*
- *HANDOFF_2026-04-18_morning.md — Apr 17-18 day→evening (pool fix + telemetry).*
- *HANDOFF_2026-04-17.md — Apr 17 is_active split session.*
