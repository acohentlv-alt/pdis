# PDIS — Task List
*April 20, 2026 (fresh — carried forward from `TASKS_2026-04-19.md`)*

---

## 🛑 WAITING ON EXTERNAL INPUT

### Amit neighborhood threshold data (unblocks Amit Fit for all TLV)
Root cause for "only 4 Amit Fit rent matches" is missing data — only פלורנטין has rows in `neighborhood_thresholds`. Need from Amit: per-neighborhood, per-size-bucket (30-40, 40-50, ..., 90-100 sqm) values for `target_price_per_sqm_preferred` + `target_price_per_sqm_max`. Priority neighborhoods: לב תל אביב, נווה צדק, כרם התימנים, רוטשילד, הצפון הישן (צפון + דרום), הצפון החדש (כיכר המדינה), מרכז העיר. Existing admin UI at `pdis/api/routes.py:2074-2352` supports CRUD with auto-recompute; Amit can enter directly.

### New Facebook groups (including building-for-sale)
Alan adding groups to `fb_groups` table. Mix of rent + building-for-sale posts. **Code is already ready** — new 5-intent Haiku prompt + building_forsale handling shipped today (PR #2 merged), but VM not yet deployed. VM deploy pending completion of group additions.

---

## 🚨 DEPLOY PENDING

### VM deploy for Items 2+3 of today's PR
PR #2 (FB source cleanup + Haiku 5-intent + display_sqm) merged to main. Render side live. **VM still running old `llm_parse.py` + `apify_to_pdis.py`.** Deferred until new FB groups added + Amit data loaded — so first scrape after VM deploy lands clean with correct categorization end-to-end.

Deploy commands when ready:
```bash
cd /Users/alancohen/pdis/.claude/worktrees/elegant-spence
scp -i ~/.ssh/oracle_vm \
  vm-scraper/llm_parse.py \
  vm-scraper/apify_to_pdis.py \
  ubuntu@129.159.158.214:/tmp/
ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214
sudo mv /tmp/llm_parse.py /tmp/apify_to_pdis.py /opt/pdis-fb-scraper/
sudo chown ubuntu:ubuntu /opt/pdis-fb-scraper/*.py
sudo systemctl restart pdis-fb-scraper.timer
```

### Historical FB price sweep (AFTER VM deploy + one clean scrape)
`scripts/fb_price_sweep_20260418.py` has interactive y/N gate. Nulls `price` on FB rent rows where `price < 2500` (captures ארנונה/ועד בית misreads from pre-prompt-fix data). Spot-check sample before confirming.

### Madlan field probe → micro-brief (any time)
`scripts/madlan_field_probe.py` is standalone read-only. Run it, paste output back to Claude, receive a follow-up brief for Madlan GraphQL field updates to fix balcony detection + net-sqm.

---

## AWAITING QA / VERIFICATION

### PR #2 — FB source + Haiku + display_sqm (Render side live Apr 20)
- Item 1 fix script ran: 690 source→facebook, 58 matches deleted, 690 classifications cleared
- Render endpoints emit `display_sqm` (9 handlers patched)
- Frontend 5 files swap to `p.display_sqm`
- FacebookPost model: sqm_net + sqm_balcony + intent
- `_INTENT_TO_CATEGORY` map + raw_data.fb_intent preservation live
- iPhone: confirm `display_sqm` renders consistently on card + detail
- Amit Fit rent count should already have re-computed for the 690 reclassified FB rows; verify with `curl /api/amit-fit/properties?category=rent` — still gated by threshold data, so count won't jump until Amit data arrives

### Yad2→VM migration (merged Apr 19)
- VM timer fires 10:00 IDT → check fresh Yad2 sessions + no errors in journalctl
- iPhone "Run Yad2 now" button works end-to-end (verified Apr 19)

### Still pending from earlier
- Telemetry v1 — passive monitoring
- Neon pool fix — passive monitoring
- `scan_enabled` / `is_visible` split — iPhone test still pending
- Fire-and-forget ingest, low-volume guard, DB-backed scan lock, events.py N+1 fix — passive

---

## NOT STARTED

### 🧹 Next session: cleaning stale code
Alan's request for the next session while waiting on external inputs. Candidates:
- **Drop `pdis/scraper.py`** (Yad2-on-Render fallback kept as rollback safety in Yad2→VM migration). Target: 1 week post-deploy = ~Apr 26. Also `fetch_item_detail` is dead per QA. Plus remove `else: scrape_preset(...)` branch in scanner.py and scanner.py:14 import.
- **Drop `search_presets.is_active` column** — 1 week after `scan_enabled`/`is_visible` split (~Apr 24 target).
- **Playwright-era cleanup** — delete `vm-scraper/run.py` (455 lines dead), fix `tests/test_fb_parser.py` imports, update `vm-scraper/run.sh` to invoke `apify_to_pdis.py`.
- **Remove or gate `/api/debug/recent-errors`** — temporary diagnostic.
- **Payload bloat in 3 endpoints** — `/api/favorites`, `/api/whitelist`, `/api/blacklist` (`pdis/api/routes.py:1709, 1731, 1870`) — follow-up to evening Apr 18 Madlan latency fix, same `SELECT p.*` pattern.

### From prior sessions
- Log path configurability for `vm-scraper/trigger_server.py` (hardcoded `/var/log/`, fails locally on Mac)
- Error toast for "Run Yad2 now" button (currently inline warning icon + native tooltip)
- Amit Fit category filter — verify it's actually honored now (4 vs 114 split suggests yes)
- Flip `YAD2_PHONE_FETCH_ENABLED=true` on Render (gated on Yad2→VM stable + category SQL done; both done, can flip any time)
- Govmap full backfill — tmux on VM, long-running
- Amit Fit thresholds (covered above), Telegram bot, F6 neighborhood pulse, mobile polish pass, Open Search UX
- Custom Search pill
- Mystery error, double page_view on redirect, QA `ui_events` cleanup

### 🧭 Strategic bets (carried forward)
1. ~~Telemetry~~ ✅
2. "Since yesterday" daily feed (1-2d)
3. Push notifications (web PWA) (2-3d)
4. Phone reveals as North Star metric — needs ~30 days telemetry
5. Signals as narrative, one headline per card (0.5d)
6. Ingest health dot in header (0.5d)
7. Tests on signals/matching/events (3d)

### 🆕 Strategic vision — Golden Sources + Profit Floor (from Apr 18 late-night)
Full vision captured in `HANDOFF_2026-04-19.md` under "Strategic vision dump". Three tiers:
- **Tier 1 — Profit Floor** (days, pure PDIS extension) — reverse-engineered pricing, "אל תשלם יותר מ-X ש״ח בחודש" headline on PropertyCard. Recommended next `/plan` target after current cleanup + data loading.
- **Tier 2 — The Vault / Golden Sources** (weeks, new scrapers) — Maya/Rashumot/insolvency.gov.il. Needs feasibility spike first.
- **Tier 3 — Ultra-Distress cross-referencing** (BLOCKED on TABU paid access).

### Optional VM cleanup: disable failing FB timer (Apify trial)
Apify free $5 trial exhausted. Timer fires daily exits 1. No cost, just log noise. **Moot once VM deploy ships and we're paying for Apify** — revisit then.

---

## PARKED

### FB Marketplace integration
Revisit if Groups volume insufficient AND FB pipeline revived.

### 💰 Consolidate on Oracle VM — kill Render
Moot while Render carries the API + FB ingest endpoint.

---

*Archived sessions:*
- *TASKS_2026-04-19.md — Apr 18 late-night → Apr 20 morning: Yad2 rent→VM deploy + PR #2 (FB source + Haiku 5-intent + display_sqm), Amit Fit threshold investigation.*
- *TASKS_2026-04-18_evening.md — Apr 18 evening Madlan latency fix session.*
- *TASKS_2026-04-18_morning.md — Apr 18 morning (pool fix + telemetry).*
- *TASKS_2026-04-18.md — start-of-Apr-18 (yesterday evening's end-state).*
- *TASKS_2026-04-17.md — Apr 17 post-is_active-split.*
