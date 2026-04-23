# PDIS — Task List
*April 23, 2026 (fresh — carried forward from `TASKS_2026-04-23.md`)*

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

## AWAITING QA / VERIFICATION

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
