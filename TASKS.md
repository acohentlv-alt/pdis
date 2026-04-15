# PDIS — Task List
*April 15, 2026 (night session)*

---

## AWAITING QA / VERIFICATION (commit 508cada deployed tonight)

### Phones across sources
Commit `508cada` shipped tonight. Test in deployed environment:
- **Madlan**: next scheduled scan (08:00 IL time) should populate `contact_phone` for ~80%+ of Madlan rows. SQL: `SELECT COUNT(*) FILTER (WHERE contact_phone IS NOT NULL), COUNT(*) FROM properties WHERE yad2_id LIKE 'madlan_%'`. Was 0/713 due to GraphQL schema drift (4 bugs) — fixed.
- **Yad2 phones**: code shipped but `YAD2_PHONE_FETCH_ENABLED=false` by default. To enable: set env var to `true` on Render, then a scheduled scan will populate phones at 40/preset (scan-time) + 310/run (backfill). 7-day cooldown via `phone_fetch_attempted_at` column. Endpoint live-tested from laptop (`fetch_phones(['n8zlan18']) → '0554360641'`).
- **`/api/log-reveal` endpoint**: replaces old `/api/ingest/facebook/log-reveal`. Frontend wired.
- **PropertyCard phone pill**: emerald tap-to-call when revealed, masked `055-•••-••••` otherwise. Israeli `0XX-XXX-XXXX` formatting.

### Filter drawer + UI polish (commit 508cada)
- New bottom-sheet drawer: tap "Filters (N)" button → drawer slides up. Sections: Price, Rooms, Sqm, Price/Sqm, Neighborhood, Source (now includes Facebook), Signals (split strong/weak with plain-English labels).
- Drawer drops below NavBar (z-60); sticky "See results" footer.
- Toast on whitelist/blacklist: "✓ Whitelisted" / "Removed from whitelist" etc. Fires on mutation onSuccess.
- Pull-to-refresh on OpportunityPage + FavoritesPage (replaces header refresh button).
- Header: greeting larger, gear → sliders icon (semantic "Manage searches"), tooltips.
- SummaryBar: rounded-2xl, larger numerics, scale-on-tap.
- PropertyCard: rounded-2xl, refined shadow, hover lift.
- Empty-state on filtered list: explicit "Clear all filters" CTA.

Manual test on iPhone:
- Drawer opens/closes smoothly, scroll lock works, Apply button visible above bottom nav
- Pull down at top of list → spinner → list refreshes
- Tap whitelist/blacklist → toast appears bottom of screen (above NavBar)
- Filters (N) badge updates as you change filters

### Scan button UX + progress bar (still pending from prior session)
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

### Phone numbers — SHIPPED 2026-04-15 (commit 508cada)
- ~~Madlan: 0/713~~ → fixed (GraphQL drift). 4 schema bugs patched. Awaits next scheduled scan.
- ~~Yad2: not wired~~ → wired (`pdis/yad2_phone.py`). Flag-off, ready to flip.
- FB phones already flow via Apify+Haiku pipeline (separate commit by parallel agent).

### Telegram bot for scan alerts
Send alerts when notable properties found after a scan completes.

### F6 — Neighborhood pulse (24-month ₪/m² sparkline)
Depends on full-city govmap backfill (in progress) + Amit providing thresholds for more neighborhoods.

---

## SHIPPED — FB Groups via Apify + Haiku (2026-04-15 evening pivot)

**Resurrected after the "park" decision when a fresh diagnostic revealed FB IS scrapeable** — the original failure was a too-aggressive modal-dismiss loop + outdated `_parse_post` selectors, NOT FB anti-bot. By that point we'd already validated Apify works perfectly (910 real posts in 90s), so we pivoted to Apify instead of fixing Playwright.

**Architecture (live):**
- **Daily scrape:** Apify actor `apify/facebook-groups-scraper` runs at 10:00 Asia/Jerusalem
  - Triggered by Oracle VM systemd timer (`/etc/systemd/system/pdis-fb-scraper.timer`)
  - VM script: `/opt/pdis-fb-scraper/run.sh` → `apify_to_pdis.py`
  - 14 active TLV rental groups, `resultsLimit=5` per group = ~70 posts/run
- **LLM parse:** Claude Haiku 4.5 extracts structured fields from Hebrew post text
  - `vm-scraper/llm_parse.py` — system prompt cached for ~80% input cost reduction
  - Extracts: intent, price, sqm, rooms, phone, neighborhood, is_agent, floor, property_type, balcony, elevator, parking, ac, furnished, available_date, confidence
- **Ingest:** POST to `/api/ingest/facebook` (40 posts/batch); existing scan pipeline upserts properties, runs matching/signals
- **PropertyCard:** when a FB post has no phone, shows "Message on Facebook" link to permalink

**Cost:**
- Apify: ~$10/mo (PAYG, $5 free credit covers ~half)
- Haiku: ~$1.80/mo
- Decodo proxy: cancelled (Apify provides residential proxies internally)
- **Total: ~$12/mo**

**Initial backfill (2026-04-15):** 738 posts ingested from a one-shot 14-group×65-post Apify run that we paid $4.55 for during testing.

**Known gaps (TODO if Shechter wants):**
- Some posts reference non-TLV cities (e.g. פרדס חנה) and get mislabeled as TLV — need server-side text-based city detection or per-group city overrides in `fb_groups` table
- 2 batches failed during initial backfill with 500 errors — those 80 posts kept first-pass field values; healed on next daily scan
- LLM `is_agent` flag flows through but isn't used in PropertyCard yet (UI shows "Agent" badge based on `item.is_agent` — works once data is queryable)
- FilterBar dropdown still missing `Facebook` option (see TODO below) — for now "All sources" includes FB

**Resurrection-time architecture notes (kept for posterity):**
- Real fix to original Playwright path was: don't dismiss the auth modal (it doesn't block hydration), use `[role="article"]` selector, parse via `inner_text()` on the article element, switch to `www.facebook.com`. We now have Apify so this is academic.

### TODO — FilterBar Facebook source option
`frontend/src/components/FilterBar.tsx:124-126` only offers Yad2/Madlan. Add `<option value="facebook">Facebook</option>` so Shechter can filter to FB-only.

### TODO — Per-group city overrides
Some FB groups include posts from non-TLV cities. Either: (a) add a `default_city` column to `fb_groups` table and pass through to `_fb_post_to_listing`, or (b) trust the LLM's neighborhood detection and skip non-TLV posts when neighborhood is null AND text doesn't contain TLV keywords.

---

## PARKED

### FB Marketplace integration
Different from FB Groups (which now ships via Apify). Marketplace would need a separate Apify actor — revisit only if Groups doesn't give enough volume for Shechter.
