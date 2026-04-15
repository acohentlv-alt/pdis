# PDIS — Task List
*April 16, 2026*

---

## AWAITING QA / VERIFICATION (deployed tonight, needs Alan's eyes in the browser)

### Scan button UX + progress bar
Shipped but needs manual test in deployed environment after Render auto-deploy:
- Click Run Now → button reads `Scanning X%` with live emerald bar
- Other presets disable with "Scan running"
- Last-scan line per preset (`Xm ago · N listings` / `Never scanned` / red `failed` / amber `blocked`)
- Error banner surfaces readable messages

---

## READY TO RUN (Alan's hands)

### Govmap full backfill — re-run with fixed scraper to cover full TLV + Haifa

**State (Apr 16):** Old scraper had 2 data bugs just fixed in commit-pending. Backfill script `scripts/backfill_closed_transactions.py` already repaired existing 17,715 rows (sqm + price_per_sqm + centroid_lat/lng all populated from raw_data). But existing coverage is **Bat Yam only** — 117 of 2,567 properties (4.5%). TLV, Ramat Gan, Haifa = 0% coverage.

**Bugs that were fixed in `vm-scraper/run_govmap.py`:**
1. Transformer declared `EPSG:2039 → 4326` but grid uses EPSG:3857 (Web Mercator). Changed to correct CRS.
2. `sqm` read from `dealArea` — govmap actually returns `assetArea`. Added to fallback chain (same for `rooms` → `assetRoomNum`).

**Steps to cover rest of the market:**
1. Check if the VM's tmux `govmap` session is still running:
   ```
   ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214 "tmux list-sessions; tail -20 /tmp/govmap_full.log"
   ```
2. If stopped: scp the fixed `vm-scraper/run_govmap.py` to the VM and resume with `--resume` flag
3. If running: kill + restart with fixed code (old code was producing broken rows that backfill already fixed)
4. Monitor progress: `tail -f /tmp/govmap_full.log`
5. When complete, verify: `SELECT COUNT(*) FROM closed_transactions` (expect 100k-1M)
6. Install monthly cron (exact block in `TASKS_2026-04-14.md`)

**Alternative (faster, no VM dep):** run locally on MacBook:
```
cd ~/pdis/vm-scraper && python3 run_govmap.py --resume
```
Expected runtime: several hours at REQ_DELAY=1.0s per polygon.

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

### Amit Fit — add rent/buy toggle + expand threshold coverage
1. **Toggle UI** — Amit Fit dashboard currently shows a mixed stream. Add explicit toggle: "Buying opportunities" vs "Rental opportunities" (Shechter's current view is mostly buy because thresholds are seeded for buy; rent has 93 candidates in Florentin but most miss Amit's aggressive rent targets).
2. **Threshold coverage gap** — only פלורנטין (hood_id=205) has thresholds seeded. Expand admin UI seeding for more neighborhoods OR scope Amit Fit explicitly to Florentin-only until more are seeded.
3. **Threshold realism audit (rent)** — Florentin rent pref=₪47-71/m²/mo vs market avg ₪120/m²/mo. Amit's rent targets are 40-50% below market → virtually nothing qualifies. Alan to decide: raise targets, or explicit "deals only" framing.
4. **Hard 30% cap (non-negotiable)** — Alan wants to lock Amit Fit such that any property >30% above preferred target gets NO tag, regardless of the per-bucket `max` column. Two readings pending: (a) display-time filter (keep admin columns, enforce cap at signal time) or (b) auto-derive `max = pref × 1.30` (make max a computed field). Alan to pick before implementation.

### Phone numbers — still broken
- Madlan: scraper reads `poc.displayNumber` but 0/713 properties get one. Broken or API changed.
- Yad2: requires separate click-to-reveal API call (not wired).

### Telegram bot for scan alerts
Send alerts when notable properties found after a scan completes.

### F6 — Neighborhood pulse (24-month ₪/m² sparkline)
Depends on full-city govmap backfill (in progress) + Amit providing thresholds for more neighborhoods.

---

## PARKED

### FB Groups scraping — PARKED 2026-04-15 (abandoned after two failed bring-up attempts)

**Decision:** Kill direct FB Groups scraping. Ship PDIS on Yad2 + Madlan + govmap only. Revisit only if we're willing to pay a commercial vendor ($30–100/mo) for maintained selectors.

**What's deployed but disabled:**
- Oracle VM at `/opt/pdis-fb-scraper/` — full scraper code, Decodo residential proxy wired, FB cookies loaded, systemd unit files installed
- `pdis-fb-scraper.timer` disabled (`systemctl disable` run 2026-04-15) — does not fire
- Render: `FB_INGESTION_ENABLED=true` (left as-is, endpoint just sits idle with no VM feeder)
- DB migration seeded `extra_params.fb_groups` on FB-source presets (harmless even when scraper is off)
- `fb_groups` table has 49 groups seeded; 14 are `is_active=TRUE`
- FB-source preset in `search_presets` still active — will show no listings, which is correct

**Root cause (confirmed by two independent agents 2026-04-15):**
- `mbasic.facebook.com` deprecated — redirects to `www.facebook.com`
- `m.facebook.com` page loads but content hydrates behind JS; `article`/`role="article"` selectors return 0 matches
- `www.facebook.com` renders empty skeleton `<article>` elements; real post content loads into **obfuscated CSS classes that rotate weekly** (per Meta's anti-scraping posture)
- No stable selector path exists for Playwright + cookies today
- Verified live against 14 TLV rental groups with valid FB session cookies (c_user/xs/datr all present) — zero posts extractable across all URL variants

**Sunk costs:** ~2 days of planning + agent work across two sessions. Decodo trial signed up (no recurring charge yet).

**To resurrect (when/if):**
1. Pick a commercial vendor: Apify (~$30–100/mo, pay-per-run), ScrapFly ($30–100/mo), BrightData Facebook Dataset (per-row pricing). They maintain selectors.
2. Rewrite `vm-scraper/run.py` to call vendor API instead of Playwright. Keep `/api/ingest/facebook` endpoint — it's a stable target.
3. Re-enable the systemd timer: `sudo systemctl enable --now pdis-fb-scraper.timer`
4. FB UX polish tasks below become relevant again.

**FB UX polish (parked — only relevant if FB Groups resurrects):**
- FilterBar dropdown: add `<option value="facebook">Facebook</option>` in `frontend/src/components/FilterBar.tsx:124-126`
- `is_agent` broker flag plumbing: `FacebookPost` model (`pdis/api/routes.py:2068-2083`) → `_fb_post_to_listing` (`pdis/api/routes.py:2125-2160`) → `ScrapedListing` → `properties`. Currently dropped silently by Pydantic default `extra='ignore'`.
- FB Brief #2: FB-aware dedup, new FB-specific signals (no-broker badge, multi-group cross-post = high distress), Nominatim geocoding for neighborhoods
- FB Brief #3: source filter dropdown, "Hide brokers" toggle, "Report this listing" link
- LLM post-parsing via Haiku (~$0.10/mo) for freeform Hebrew — stash reference in abandoned laptop-daemon pivot
- `normalize_city()` helper in `pdis/utils/city.py` (stashed) — was FB-motivated; no current need
- Cleanup if never resurrected: delete `/opt/pdis-fb-scraper/` from VM, delete `vm-scraper/` from repo, drop `fb_groups` + `ingest_state.facebook` rows, remove `/api/ingest/facebook` route, remove FB-source presets

### FB Marketplace integration
Different from FB Groups. Needs Playwright + perceptual image hashing. Blocked by the same Meta-scraping wall as FB Groups — revisit only under the commercial-vendor decision above.
