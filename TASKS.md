# PDIS — Task List
*April 18, 2026 late-night (fresh — carried forward from `TASKS_2026-04-18_evening.md` + Yad2→VM session)*

---

## READY TO RUN — TOMORROW MORNING, IN ORDER 🚨

### 1. VM deploy for Yad2 rent→VM migration
Branch `claude/yad2-vm-rent` is pushed to origin but **NOT merged to main**. Must deploy VM first or Render will blow away rent data for ~24h.

```bash
# On your Mac:
cd /Users/alancohen/pdis/.claude/worktrees/yad2-vm-rent
scp -i ~/.ssh/oracle_vm \
  vm-scraper/run_yad2.py \
  vm-scraper/trigger_server.py \
  ubuntu@129.159.158.214:/tmp/
scp -i ~/.ssh/oracle_vm \
  vm-scraper/systemd/pdis-yad2-scraper.timer \
  vm-scraper/systemd/pdis-yad2-trigger.service \
  ubuntu@129.159.158.214:/tmp/

# On VM:
ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214
sudo mv /tmp/run_yad2.py /tmp/trigger_server.py /opt/pdis-yad2-scraper/
sudo chown ubuntu:ubuntu /opt/pdis-yad2-scraper/*.py

# Create writable log files (trigger_server hardcodes /var/log/)
sudo touch /var/log/pdis-yad2-manual.log /var/log/pdis-yad2-trigger.log
sudo chown ubuntu:ubuntu /var/log/pdis-yad2-manual.log /var/log/pdis-yad2-trigger.log

# Generate shared secret (save this for Render step below)
TRIGGER_SECRET=$(openssl rand -hex 32)
echo "TRIGGER_SECRET=$TRIGGER_SECRET" >> /opt/pdis-yad2-scraper/.env
echo "SAVE THIS FOR RENDER → $TRIGGER_SECRET"

# Install systemd units
sudo mv /tmp/pdis-yad2-scraper.timer /etc/systemd/system/
sudo mv /tmp/pdis-yad2-trigger.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart pdis-yad2-scraper.timer
sudo systemctl enable --now pdis-yad2-trigger.service

# Verify
systemctl list-timers pdis-yad2-scraper.timer   # next run should be 10:00 IDT
systemctl status pdis-yad2-trigger.service      # should be "active (running)"

# Smoke test trigger from VM itself
curl -s -X POST -H "Authorization: Bearer $TRIGGER_SECRET" \
  http://localhost:8787/trigger
# Expect: {"status":"started"}
```

### 2. Merge `claude/yad2-vm-rent` → main (triggers Render deploy)
**Only after VM is verified.** GitHub PR URL offered at push time:
`https://github.com/acohentlv-alt/pdis/pull/new/claude/yad2-vm-rent`

Note: branch is **1 commit behind main** (evening's Madlan latency fix). Either rebase or merge — both should conflict-free since different code areas, but worth eyeballing if GitHub flags it.

### 3. Set Render env vars (after main deploy finishes)
- `VM_TRIGGER_URL=http://129.159.158.214:8787/trigger`
- `VM_TRIGGER_SECRET=<same hex you saved in step 1>`
- `YAD2_VM_INGESTION_ENABLED=true` (should already be; verify)

### 4. Run historical category fix SQL on Neon
QA found **958 rent-preset rows mistagged as `category='forsale'`** due to the old `run_yad2.py:209` hardcode. One-shot UPDATE:

```sql
-- Verify schema first:
\d properties

-- Then fix:
UPDATE properties p SET category = sp.category
FROM search_presets sp
WHERE sp.id = p.preset_id
  AND p.source = 'yad2'
  AND p.category != sp.category;
-- Expect ~958 rows updated.
```

### 5. iPhone test the full flow
- Open PresetManager modal → **"Run Yad2 now"** button visible in header
- Tap it → button disables, shows running state
- Check `/api/scan/sessions?limit=10` — fresh Yad2 sessions appear from VM ingest
- Tap again while running → 429 or 409 (rate-limited / already-running)

---

## AWAITING QA / VERIFICATION

### Yad2→VM + phone-hook bug fix (branch `claude/yad2-vm-rent`, commit `0ae108e`)
- Phone hook now called from `run_scan_from_listings` (was missing → every VM-ingested Yad2 forsale row had NULL contact_phone since Apr 13)
- VM-skip guard widened from `category == "forsale"` to all Yad2 when `YAD2_VM_INGESTION_ENABLED=true`
- `_backfill_built_sqm` deleted from scanner.py (VM fills `square_meter_build` pre-ingest now)
- `POST /api/scan/yad2/manual` + "Run Yad2 now" UI button in PresetManager header
- VM timer moved 08:00 → 10:00 IDT
- `vm-scraper/trigger_server.py` + `pdis-yad2-trigger.service` — bearer-auth HTTP daemon on port 8787
- `vm-scraper/run_yad2.py` parameterized for rent+forsale (was hardcoded forsale)
- Local QA 22/24 PASS (2 env-only fails: Mac port collision + `/var/log/` permissions — neither is a code bug)
- Playwright confirmed button renders + click produces error state correctly

### Madlan latency fix (commit `9d0bd17`, evening session)
- Preset 44 payload 8.6 MB → 3.9 MB via `SELECT p.*` → explicit 35-column list
- Verify on iPhone: cards render in 2-3s not 8-14s
- `curl ... /api/presets/44/properties?per_page=2000 -w "%{size_download}"` ≈ 3.9 MB

### Still pending from earlier
- **Telemetry v1** (`04b5685`) — caught Madlan bug on day 1, working as intended
- **Neon pool fix** (`c0d0433`) — 24h quiet window ends tomorrow morning; `/api/debug/recent-errors` should stay flat
- **Split `is_active` → `scan_enabled` + `is_visible`** (`c2682b9`) — backend verified, iPhone test still pending
- Fire-and-forget ingest, low-volume guard, DB-backed scan lock, events.py N+1 fix — passive monitoring
- Custom Search pill, VM-side retry on 5xx — tomorrow's scan is the test
- CLAUDE.md cron schedule — verify on cron-job.org dashboard
- PresetManager 2030-vision redesign, Phones across sources, Filter drawer, Scan button progress bar

---

## NOT STARTED

### Payload bloat in 3 more list endpoints
Same `SELECT p.*` pattern in `/api/favorites`, `/api/whitelist`, `/api/blacklist` (`pdis/api/routes.py:1709, 1731, 1870`). Follow-up from evening session reviewer.

### 🆕 Drop `pdis/scraper.py` (Yad2-on-Render fallback)
Kept in this Yad2→VM migration as rollback safety. After 1 week (target: ~Apr 25) of clean VM rent scans, delete it + remove the `else: scrape_preset(...)` branch in scanner.py (~line 645) + scanner.py:14 import. Also `fetch_item_detail` is already dead — QA found it's defined but uncalled.

### 🆕 Log path configurability for `trigger_server.py`
LOG_FILE hardcoded to `/var/log/pdis-yad2-manual.log`. Fine for VM, fails locally on Mac. Make env-configurable if local testing ever needed.

### 🆕 Error toast for "Run Yad2 now" button
Executor chose inline warning icon + native tooltip over a full toast (proportionate for a header button). If you want a proper toast pattern, small follow-up.

### 🆕 Strategic vision — "Golden Sources" + "Profit Floor" (late-night Apr 18 discussion)

Alan pasted a full product brief from his claude.ai "fortress" project chat. Two new modules proposed; broken into three feasibility tiers during end-of-session discussion. Full vision in HANDOFF.md under "Strategic vision dump." Short version:

**Tier 1 — Profit Floor / מחיר רצפה (ships in days, pure PDIS extension):**
Reverse-engineered pricing. For each listing, compute the max rent/purchase price Amit can pay and still hit his target margin, using existing neighborhood rental distributions. Surface as a single headline on the PropertyCard: **"אל תשלם יותר מ-X ש״ח בחודש"**. Implementation: new `max_negotiation_price` field in `signals.py → details`; React render on card. No new data sources. **This is the safest/fastest next step.** Needs its own `/plan`.

**Tier 2 — The Vault / מקורות הזהב (ships in weeks, needs new scrapers):**
Separate "Golden Sources" feed/pill surfacing properties from:
- **Maya (maya.tase.co.il)** — TASE disclosure portal. Public, stable, easy ingest. But only ~500 listed companies; narrow TAM.
- **Official Gazette (רשומות)** — receiver sale notices. Free, public, fragile to parse (Hebrew gov PDFs).
- **insolvency.gov.il / כונס הנכסים הרשמי** — some case data public. Legacy site, fragile scraping.

Surfaces as a separate pill with its own property feed — NOT cross-referenced to Yad2 listings (see Tier 3). Useful to Amit as a curated "properties being sold by receivers this week" feed. **Needs a feasibility spike FIRST** (90 min, one agent, hands-on testing of each source) before writing any scraper code.

**Tier 3 — Ultra-Distress cross-referencing (BLOCKED on data access):**
The exciting part: a Yad2 card lights up because its owner is in insolvency. Requires linking debtor name → property address. Bridge is TABU (land registry), which is paid-per-query — **violates PDIS's "free forever" rule**. Without TABU or an equivalent DB, the automated version isn't feasible. Alternative: manual-operator flow where Amit inputs debtor names he's researched externally, and PDIS matches to existing listings. **Parked pending a change to the free-forever constraint or a manual-workflow design.**

**Also in the brief (for reference):**
- "Vibe coding" for negotiation — auto-generated call scripts combining signals + market price + target margin. Natural extension of Tier 1, could ship after.
- Interactive arbitrage calculator (claude.ai chameleon component) — nice UX prototype but Alan's decision: bake the math into PropertyCard, skip the standalone calculator page.

**Next step when we pick this back up:** `/plan` Tier 1 first (fast, self-contained); in parallel, `/plan` a Tier 2 data-source feasibility spike.

### Remove or gate `/api/debug/recent-errors`
Temporary diagnostic (`ebe4b11`). Gate behind `DEBUG_ENDPOINTS_ENABLED` or remove after pool fix 24h-clean.

### Amit Fit category filter ignored
`/api/amit-fit/properties?category=rent` and `?category=forsale` both return 81 rows. Silent param-ignore.

### Drop `search_presets.is_active` column
After 1 week of `scan_enabled`/`is_visible` running clean (~Apr 24), drop column + remove `?is_active` alias.

### Mystery error, double page_view on redirect, QA `ui_events` cleanup
Low-priority housekeeping from evening session.

### 🧭 STRATEGIC — remaining bets
1. ~~Telemetry~~ ✅
2. "Since yesterday" daily feed (1-2d)
3. Push notifications (web PWA) (2-3d)
4. Phone reveals as North Star metric — needs ~30 days telemetry
5. Signals as narrative, one headline per card (0.5d)
6. Ingest health dot in header (0.5d)
7. Tests on signals/matching/events (3d)

### Optional VM cleanup: disable failing FB timer
Apify free $5 trial exhausted. Timer fires daily and exits 1. No cost, just log noise. One SSH command.

### Enter Florentin rent feature adjustments via unlocked UI
Parking (+500–1000), mamad (+600), elevator/walk-up. 5-min task.

### Flip `YAD2_PHONE_FETCH_ENABLED=true` on Render
After Yad2→VM migration is proven + category SQL is run. Activates click-to-reveal phone fetcher. With today's phone-hook fix, VM-ingested Yad2 rows will now participate in phone capture.

### Govmap full backfill
Covers 4.5% of TLV/Haifa. Hours. tmux on VM.

### Amit Fit thresholds, Telegram bot, F6 neighborhood pulse, mobile polish pass, Open Search UX
Queued from earlier.

### 💰 Consolidate on Oracle VM — kill Render (post-A2)
Moot while FB pipeline dormant.

---

## DONE (today — Apr 23)

- Playwright-era cleanup — delete `vm-scraper/run.py` (455 lines dead), fix `tests/test_fb_parser.py` imports, update `vm-scraper/run.sh` to invoke `apify_to_pdis.py`.

---

## PARKED

### FB Marketplace integration
Revisit if Groups volume insufficient AND FB pipeline revived.

---

*Archived sessions:*
- *TASKS_2026-04-18_evening.md — Apr 18 evening Madlan latency fix session.*
- *TASKS_2026-04-18_morning.md — Apr 18 morning (pool fix + telemetry).*
- *TASKS_2026-04-18.md — start-of-Apr-18 (yesterday evening's end-state).*
- *TASKS_2026-04-17.md — Apr 17 post-is_active-split.*
