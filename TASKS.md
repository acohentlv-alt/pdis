# PDIS — Task List
*April 23, 2026 (fresh — carried forward from `TASKS_2026-04-23.md`)*

---

## 🔥 BROKEN — PDIS laptop daemon has been silently failing

**Discovered 2026-04-25** during Agentic OS planning session.

**Symptom:** `com.pdis.fb-daemon` launchd job last exit status = `2` (error). The job is loaded and keeps retrying, but the daemon log (`~/pdis/laptop-daemon/daemon.log`, 156 KB, last modified Apr 24 12:16) is full of the same error hundreds of times:
```
can't open file '/Users/alancohen/pdis/laptop-daemon/daemon.py':
[Errno 2] No such file or directory
```

**Root cause:** the Python file `~/pdis/laptop-daemon/daemon.py` that the plist points to **does not exist on disk**. At some point it was moved, renamed, or deleted — but the plist `~/Library/LaunchAgents/com.pdis.fb-daemon.plist` was never updated.

**Impact:**
- Whatever the laptop daemon was doing has NOT been running
- PDIS on Render (`https://pdis-lsah.onrender.com`) still responds 200 OK — the web app itself is fine
- Scheduler log (`scheduler.log`, 31 bytes) only contains `{"detail":"Method Not Allowed"}` — meaningless curl response

**Open questions for `/plan`:**
1. What was `daemon.py` supposed to do — and is that work already covered by the VM scraper + Render?
2. If still needed, restore from git or rewrite. If not, unload and delete the plist.
3. Same check: `com.pdis.fb-scheduler.plist` — is its target still valid?

**Effort:** ~30 min investigation + fix. Not urgent if PDIS end-to-end is otherwise healthy.

---

## 🛑 WAITING ON EXTERNAL INPUT

### Amit neighborhood threshold data (unblocks Amit Fit for all TLV)
Root cause for "only 4 Amit Fit rent matches" is missing data — only פלורנטין has rows in `neighborhood_thresholds`. Need from Amit: per-neighborhood, per-size-bucket (30-40, 40-50, ..., 90-100 sqm) values for `target_price_per_sqm_preferred` + `target_price_per_sqm_max`. Priority neighborhoods: לב תל אביב, נווה צדק, כרם התימנים, רוטשילד, הצפון הישן (צפון + דרום), הצפון החדש (כיכר המדינה), מרכז העיר. Admin UI at `pdis/api/routes.py:2074-2352` supports CRUD with auto-recompute.

### New Facebook groups (including building-for-sale)
Alan adding groups to `fb_groups` table. Mix of rent + building-for-sale posts. Code is already ready (5-intent Haiku prompt + building_forsale handling shipped PR #2), but VM not yet deployed pending group additions.

---

## 🚨 DEPLOY PENDING

### VM deploy for PR #2 (Haiku 5-intent + net/balcony sqm)
PR #2 merged Apr 20. Render live. **VM still running old `llm_parse.py` + `apify_to_pdis.py`.** Deferred until new FB groups added + Amit data loaded — so first scrape after VM deploy lands clean end-to-end.

Deploy commands when ready:
```bash
cd /Users/alancohen/pdis
scp -i ~/.ssh/oracle_vm \
  vm-scraper/llm_parse.py \
  vm-scraper/apify_to_pdis.py \
  ubuntu@129.159.158.214:/tmp/
ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214
sudo mv /tmp/llm_parse.py /tmp/apify_to_pdis.py /opt/pdis-fb-scraper/
sudo chown ubuntu:ubuntu /opt/pdis-fb-scraper/*.py
sudo systemctl restart pdis-fb-scraper.timer
```

Also scp the updated `vm-scraper/run.sh` (from PR #3 — now calls `apify_to_pdis.py` directly, drops stale PROXY_URL warning).

### Historical FB price sweep (AFTER VM deploy + one clean scrape)
`scripts/fb_price_sweep_20260418.py` has interactive y/N gate. Nulls `price` on FB rent rows where `price < 2500` (captures ארנונה/ועד בית misreads from pre-prompt-fix data).

### Madlan field probe → micro-brief (any time)
`scripts/madlan_field_probe.py` is standalone read-only. Run it, paste output back, receive a follow-up brief for Madlan GraphQL field updates to fix balcony detection + net-sqm.

---

## 🔄 FOLLOW-UPS — same stale-conn risk in other loops

- `pdis/scanner.py:_upsert_properties` — per-row loop over all scraped listings (1194 on Madlan). Survived session 268 but close to Neon's 5-min idle-kill window. Apply same `executemany` pattern as the `classification.py` fix. Needs its own `/plan`.
- `pdis/scanner.py:_create_snapshots` — per-listing SELECT + INSERT = ~2400 round-trips on 1194 rows. Same risk when VM scans grow.
- `pdis/matching.py:backfill_year_built_from_buildings` (around line 754) — per-property SELECT + UPDATE loop. Was the last step logged before session 268 crashed — may be the setup victim that left the connection in a dying state.

---

## AWAITING QA / VERIFICATION

### Madlan→VM migration + stale-conn fix — DONE, awaiting push
- Madlan→VM migration shipped: cron-job.org retired, `/api/scan/scheduled` deleted, VM systemd timer at 06:00 IDT running daily.
- `classification.py` stale-conn fix applied: replaced per-row `execute` loop with single `executemany` call — keeps connection hold time under 1s for 1000+ rows.
- Session 268 was the test-fire — scrape + events + matching landed clean; signals/stats failed at the crash point. This fix closes that last loose end.
- **Push to main before 06:00 IDT tomorrow so the VM `git pull` picks it up before the next scan.**

### Madlan→VM migration (pending Alan's VM setup + QA)
- `vm-scraper/run_madlan.py` + `run_madlan.sh` + systemd units created
- `POST /api/scan/scheduled` endpoint deleted from routes.py; `scheduled_scan()` wrapper deleted from scanner.py
- VM setup: clone repo to `/opt/pdis-madlan-scraper`, install deps, write `.env` with `DATABASE_URL`, install + enable systemd timer
- First run: `systemctl start pdis-madlan-scraper.service` then check `/var/log/pdis-madlan-scraper.log`
- cron-job.org job can be disabled/deleted after first successful VM run confirmed

### PR #3 — Playwright cleanup + debug endpoint removal (merged Apr 23)
- Verify Render deploy of `c08d01c` succeeded
- `curl https://pdis-lsah.onrender.com/api/debug/recent-errors` → 404 (will be SPA catch-all 200; inspect response body for `<!doctype html>`)
- Normal browsing on iPhone — no regressions

### PR #2 — FB source + Haiku + display_sqm (Render side live Apr 20)
- Amit Fit rent count should already have re-computed for the 690 reclassified FB rows; verify with `curl /api/amit-fit/properties?category=rent` — still gated by threshold data.

### Yad2→VM migration (merged Apr 19)
- VM timer fires 10:00 IDT daily — passive monitoring, no issues reported

### Still pending from earlier
- Telemetry v1 — passive monitoring
- Neon pool fix — 5+ days clean, fully proven
- `scan_enabled` / `is_visible` split — iPhone test still pending
- Fire-and-forget ingest, low-volume guard, DB-backed scan lock, events.py N+1 fix — passive

---

## NOT STARTED

### 🧹 Stale code cleanup (in progress)
- **Drop `pdis/scraper.py`** (Yad2-on-Render fallback). Target was ~Apr 26. Also `fetch_item_detail` is dead per QA. Plus remove `else: scrape_preset(...)` branch in scanner.py and scanner.py:14 import.
- **Drop `search_presets.is_active` column** — 1 week after `scan_enabled`/`is_visible` split (~Apr 24 target).
- **Payload bloat** in `/api/favorites`, `/api/whitelist`, `/api/blacklist` (`pdis/api/routes.py:1709, 1731, 1870`) — same `SELECT p.*` pattern.

### From prior sessions
- Log path configurability for `vm-scraper/trigger_server.py` (hardcoded `/var/log/`, fails locally on Mac)
- Error toast for "Run Yad2 now" button (currently inline warning icon + native tooltip)
- Amit Fit category filter — verify it's actually honored now
- Flip `YAD2_PHONE_FETCH_ENABLED=true` on Render
- Govmap full backfill — tmux on VM, long-running
- Custom Search pill
- Mystery error, double page_view on redirect, QA `ui_events` cleanup

### 🧭 Strategic bets
1. ~~Telemetry~~ ✅
2. "Since yesterday" daily feed (1-2d)
3. Push notifications (web PWA) (2-3d)
4. Phone reveals as North Star metric — needs ~30 days telemetry
5. Signals as narrative, one headline per card (0.5d)
6. Ingest health dot in header (0.5d)
7. Tests on signals/matching/events (3d)

### 🆕 Strategic vision — Golden Sources + Profit Floor
- **Tier 1 — Profit Floor** (days, pure PDIS extension) — reverse-engineered pricing, "אל תשלם יותר מ-X ש״ח בחודש" headline on PropertyCard. Recommended next `/plan` target.
- **Tier 2 — The Vault / Golden Sources** (weeks, new scrapers) — Maya/Rashumot/insolvency.gov.il. Needs feasibility spike first.
- **Tier 3 — Ultra-Distress cross-referencing** (BLOCKED on TABU paid access).

---

## PARKED

### FB Marketplace integration
Revisit if Groups volume insufficient AND FB pipeline revived.

### 💰 Consolidate on Oracle VM — kill Render
Moot while Render carries the API + FB ingest endpoint.

---

*Archived sessions:*
- *TASKS_2026-04-23.md — Apr 23 stale-code cleanup (PR #3: Playwright + debug endpoint removal).*
- *TASKS_2026-04-20.md — Apr 20 morning session (PR #2 FB source + Haiku 5-intent + display_sqm).*
- *TASKS_2026-04-19.md — Apr 18 late-night Yad2→VM migration.*
- *TASKS_2026-04-18_evening.md — Apr 18 evening Madlan latency fix.*
- *TASKS_2026-04-18_morning.md — Apr 18 morning (pool fix + telemetry).*
- *TASKS_2026-04-17.md — Apr 17 post-is_active-split.*
