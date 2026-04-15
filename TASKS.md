# PDIS — Task List
*April 15, 2026*

---

## AWAITING QA / VERIFICATION (deployed tonight, needs Alan's eyes in the browser)

### Scan button UX + progress bar
Shipped but needs manual test in deployed environment after Render auto-deploy:
- Click Run Now → button reads `Scanning X%` with live emerald bar
- Other presets disable with "Scan running"
- Last-scan line per preset (`Xm ago · N listings` / `Never scanned` / red `failed` / amber `blocked`)
- Error banner surfaces readable messages

### FB groups multi-select UI
Hard-refresh browser then edit FB preset → verify 49 checkboxes appear, tick relevant ones, save, reopen → persistence check.

---

## READY TO RUN (Alan's hands, ~30-45 min)

### FB VM scraper deployment — A2 brief drafted, awaiting /review and /exec
Investigation Apr 15 (late session) confirmed three stacked off-switches: feature flag default-False, empty fb_groups linkage on the active preset, scraper never ran. Planner produced a full A2 brief (in conversation transcript, planner agent `ab7b1cef88493c91a`).

Brief summary:
- **New:** `pdis/utils/city.py` with `normalize_city()` supporting 6 TLV variants (Hebrew with/without hyphen, English variants → canonical `"תל אביב יפו"`)
- **Remove:** `TLV_CITY_STRING` + `GROUP_CITY_MAP` from `routes.py:2057-2065`; delete `scripts/enumerate_fb_groups.py`; re-point `seed_fb_groups.py` at `vm-scraper/groups.json`
- **Harden:** `vm-scraper/run.py` — new `--dry-run` flag, selector-drift detection, hard-fail when `PROXY_URL` missing (no warn-and-proceed)
- **Schedule:** systemd timer (Alan picked over cron) with `OnCalendar=*-*-* 08:00:00`, `RandomizedDelaySec=300`, `Restart=on-failure RestartSec=600 StartLimitBurst=2`
- **Probation:** `FB_SCANS_PER_DAY=1` for 14 days, then flip to 2

Open decisions before `/exec`:
1. **Proxy vendor** — Smartproxy ~$5–15/mo recommended (lowest-cost legit residential). Alan said "gold standard for free" — flagged as not possible; alternatives are Bright Data (~$15–45/mo) or no proxy (high FB ban risk on Oracle VM IP).
2. **Retroactive city normalization** of 1,952 existing `properties.address_city` rows. Alan said "every point of data needs to be accurate" → likely yes; planner didn't include the migration in the printed brief, needs to be added before `/exec`.

Prereqs Alan owns: buy proxy → prep FB account (member of 5 TLV groups + 2FA on) → verify VM SSH → set Render env (`FB_INGESTION_ENABLED=false`, `FB_SCANS_PER_DAY=1`).

Then: `/review` → `/exec` → manual dry-run on VM → install systemd timer → flip flag.

---

## FB UX POLISH (post-A2 follow-ups)

### FilterBar — Facebook source option missing
`frontend/src/components/FilterBar.tsx:124-126` only offers "All sources / Yad2 / Madlan". Once FB ingestion is live, add `<option value="facebook">Facebook</option>`. "All sources" already includes FB rows, so this is dropdown-only UX.

### Apply `normalize_city()` across Yad2/Madlan ingest + filters
After A2 ships and the canonical is proven stable, extend the normalizer to:
- `pdis/scraper.py:182` — Yad2 `item.get("city")` on ingest
- `pdis/scraper_madlan.py:250` — Madlan `addr.get("city")`
- Any route that filters `properties.address_city` by string equality
Goal: one canonical value per city across all sources.

### Govmap full backfill completion + monthly cron
Still running in tmux session `govmap` on VM. Check status:
```
ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214 "tail -5 /tmp/govmap_full.log"
```
When complete, verify:
```sql
SELECT COUNT(*) FROM closed_transactions;  -- expect 500k-1M
```
Then install monthly cron (exact block in `TASKS_2026-04-14.md`).

---

## NOT STARTED

### 💰 Consolidate on Oracle VM — kill Render (post-A2)
Once A2 (FB laptop daemon + queue) ships and stabilizes, move the whole app off Render onto the Oracle VM (`129.159.158.214`). Render costs ~$7/mo and its only remaining value is `git push` auto-deploy + managed HTTPS — both replaceable.

**What moves:**
- FastAPI backend (uvicorn under systemd)
- React frontend (served as static files by uvicorn or Caddy)
- Yad2 rent + Madlan scrapers (move from cron-job.org → systemd timers on VM)
- Ingest receiver endpoints (VM scrapers and laptop daemon already POST to Render; repoint to VM)

**What stays:**
- Neon Postgres (free tier, no reason to move)
- Oracle VM (already there)
- cron-job.org — optional; systemd timers on VM replace it, or keep for external heartbeat

**What to set up:**
- Caddy (or nginx) in front of uvicorn for HTTPS — Caddy does Let's Encrypt auto-renew with one config line
- Domain → `129.159.158.214` (DuckDNS or a real domain)
- systemd units: `pdis-api.service`, `pdis-yad2-rent.timer`, `pdis-madlan.timer`
- Deploy hook or simple `git pull && systemctl restart pdis-api`
- `.env` on VM (DATABASE_URL + all flags from `CLAUDE.md` env table)

**Risk:** 1GB-RAM micro VM is tight. Adding uvicorn + React build on top of existing scrapers might hit memory pressure. Monitor with `free -m` / `htop` after go-live. Fallback: Oracle free tier offers 4-core ARM with up to 24GB RAM — migrate to a bigger instance if the micro chokes.

**Rule:** do this **after A2 ships and proves stable for 1+ week.** Don't compound moving pieces mid-flight.

### 🔍 Haifa Buy preset — blocked (root cause found, fix pending)
Screenshot flagged by Alan Apr 15. Investigated same day, **root cause is NOT ShieldSquare** (initial hypothesis was wrong — three other forsale presets succeeded Apr 14, so `/forsale` is not IP-blocked from Render).

**Actual root cause:** Preset 9 (`Haifa Buy`, `city_code=4000`, `category=forsale`) has **zero filters** — no price, no rooms, no property types. It asks Yad2 for *every* Haifa for-sale listing, which is too broad → Yad2's anti-bot throttles → "Yad2 blocked the request — zero listings retrieved". The Apr 3 run surfaced the warning ("Partial block detected on final page but 240 listings collected") — it was always borderline.

**Evidence (from `scan_sessions` query Apr 15):**
- Preset 9 (no filters): 2 sessions total in 12 days, last blocked Apr 13
- Preset 11 (Haifa Buy - Small Apts, has filters): 3 sessions, last done Apr 14
- Preset 12 (Haifa Buy - Buildings, has filters): 1 session, last done Apr 14
- Preset 23 (Florentin Buy - Amit, has filters): 5 sessions, last done Apr 14

**Two open questions to confirm:**
1. **Why is preset 9 not on the main rotation?** Only 2 sessions in 12 days vs 5 for Florentin. Suggests a scanner cooldown on blocked presets or manual-trigger-only. Check `scanner.py::run_all_scans` for skip logic.
2. **Why Haifa presets at all?** PDIS is documented as Tel Aviv. Intentional market expansion, Alan's personal use, or test presets?

**Recommended fix (pick one):**
- **Option A (simplest):** Delete preset 9 — redundant with presets 11 + 12 which cover Haifa with filters and already work.
- **Option B:** Add `max_price` and `max_rooms` filters to preset 9 to narrow the result set.
- **Option C (wrong):** Deploy VM forsale path — does not address the actual cause (unfiltered query, not IP block).

### ₪/m² math fix on PropertyCard
First card shows `4,299,999 ₪ · 82m² (95 total) · 52,439 ₪/m²`. The ₪/m² uses the smaller (build) area. Israeli real estate convention = gross/total. One-line fix in `frontend/src/components/PropertyCard.tsx`: prefer total area, or show both. Quick win.

### Govmap comps rework — Option 2 (Amit-approved)
Planned but not coded. Remove `below_closed_comps` / `above_closed_comps_20pct` averages-based signals. Replace with raw list of last 3-5 closed sales in same building on PropertyDetailPage. Amit explicitly said he doesn't want neighborhood averages — just real comparable deals. See Apr 14 conversation for full scoping.

### Phone numbers — still broken
- Madlan: scraper reads `poc.displayNumber` but 0/713 properties get one. Broken or API changed.
- Yad2: requires separate click-to-reveal API call (not wired).
- FB: works once FB ingest is flowing (depends on deployment above).

### FB Groups Brief #2 (re-plan after 1 week of real FB data)
FB-aware dedup, new FB-specific signals (no-broker badge, multi-group cross-post = high distress), Nominatim geocoding pass for neighborhoods.

### FB Groups Brief #3
Source filter dropdown, "Hide brokers" toggle, "Report this listing" link.

### Telegram bot for scan alerts
Send alerts when notable properties found after a scan completes.

### F6 — Neighborhood pulse (24-month ₪/m² sparkline)
Depends on full-city govmap backfill (in progress) + Amit providing thresholds for more neighborhoods.

---

## PARKED

### FB Marketplace integration
Different from FB Groups (which we shipped). Needs Playwright + perceptual image hashing. Revisit after FB Groups pipeline is proven.
