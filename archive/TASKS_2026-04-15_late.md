# PDIS — Task List
*April 15, 2026 (late2 session — PresetManager redesign)*

---

## AWAITING QA / VERIFICATION

### PresetManager 2030-vision redesign (commit `c66e7b7`, shipped tonight)

Split the 1,362-line PresetManager into 5 focused files under `preset-manager/`. Redesign matches the filter drawer pattern — bottom sheet, chip pills, sticky CTA, progressive disclosure. Full behavior preserved.

**Automated QA:** 38/38 PASS, zero console errors, zero React #310 errors across hooks-order stress tests.

**Manual iPhone QA (needs Alan's eyes on deployed site):**
- Hard-refresh `https://pdis-lsah.onrender.com` on iPhone after Render deploy settles.
- Tap sliders icon in header → "Manage Presets" sheet slides up from bottom.
- Each preset card: toggle + name + kebab `⋮` + "Run Now" (no 4-button strip, no Active/Inactive text badge).
- Tap kebab → Edit / Clone / Delete menu. Tap another kebab → first closes (only one open at a time).
- Tap outside kebab or press ESC → kebab closes.
- Edit a preset that has neighborhoods or property types set → "More filters" auto-opens.
- Fill form, tap backdrop (outside sheet) → reopen → form empty (no stale state).
- For a For Sale preset: Pricing Targets shows 3-column `Size | Preferred | Max` grid that fits 390px width without wrapping.
- Save a preset → sticky "Save" CTA disables with "Saving…" then closes form.
- "+ Add Preset" now at TOP of the list (not the bottom).

### Phones across sources (commit 508cada from night session)
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

### 🧭 STRATEGIC — bigger bets from Apr 15 product analysis

These 7 items came out of a project-wide analysis on the night of Apr 15. Reframed from the lens "Shechter uses this on iPhone twice a day — everything else is noise." Ordered by leverage, not effort.

#### 1. Telemetry — wire up before building more features
**Why:** Right now nobody knows whether Shechter actually uses what we ship. Half the code could be dead weight.
**What:** Log 5 events — `preset_opened`, `card_clicked`, `phone_revealed`, `favorite_added`, `property_detail_viewed`. Simple `app_events` table with (event_name, property_id, preset_id, user_id, ts). One POST endpoint, one `useEffect` per component.
**Cost:** ~2 hours.
**Value:** 10 days of data tells us what's underused. Every decision on this list becomes cheaper to make.
**Recommended:** do this Monday morning before anything else.

#### 2. "Since yesterday" daily feed — the product Shechter actually wants
**Why:** He opens the app twice a day expecting to see what's NEW. Today he sees everything mixed and has to remember which cards he's seen.
**What:** Default dashboard view = a timeline of changes since his last visit. New strong-distress listings, price drops ≥10%, reappearances. Chronological, not aggregated. The current "Opportunities" tab becomes secondary.
**Implementation:** track `last_visited_at` per user. Query `property_events` + new `property_snapshots` since that timestamp. Sort descending.
**Cost:** ~1-2 days.
**Value:** Turns a database browser into a product with a daily habit.

#### 3. Push notifications (web push, PWA)
**Why:** Twice-daily scans with zero alerts means Shechter finds the good stuff 6 hours late. This is the single biggest "Shechter feel" upgrade.
**What:** iOS 16.4+ supports web push from installed PWAs. Pipe a notification when a scan produces a property with 2+ strong signals (or his own threshold). No App Store, no native code.
**Implementation:** Service worker + VAPID keys + a per-user notification preference. Fire from the scan pipeline.
**Cost:** ~2-3 days including PWA install polish and Apple's WebPush quirks.
**Value:** Competitive moat — manual refreshing loses to instant alerts.

#### 4. Phone reveals as the North Star metric
**Why:** The whole point is "contact the landlord." If nobody calls, everything else is vanity.
**What:** Track `phone_revealed` (already covered by item 1) and analyze which signals correlate with reveals. If "price drop >10%" never triggers a call, maybe it's not actually a distress signal for rentals. Reshape the signal set from this data.
**Dependency:** needs item 1 deployed for ~30 days.
**Cost:** queryable after 30 days of telemetry, ~half a day of SQL + analysis.

#### 5. Signals as narrative, not taxonomy — one headline per card
**Why:** Cards with 5–8 badges wrap awkwardly on 375px iPhone. Overwhelming, not scannable.
**What:** Replace badge soup on list cards with ONE headline — "₪500 price drop 4 days ago" or "Relisted 3× — 87 days on market." Pick the strongest signal, format as narrative text, rest goes to PropertyDetailPage.
**Rule of thumb:** pick by priority order: `price_drop_gt_10pct` > `relisted_2plus` > `listed_90plus_days` > `weak_language` > `condition_keywords` > `below_avg_price`. Falls back to weak signals if no strong. No signal = no headline.
**Cost:** ~half a day. Changes PropertyCard.tsx and adds a signal-to-narrative helper.
**Value:** Core UX lift. Cards become scannable. Rule already holds: "no numeric scores" → sister rule: "one headline per card."

#### 6. Ingest health visible to Shechter
**Why:** When Madlan broke for weeks (schema drift) nobody noticed until Alan asked about phones. Shechter sees stale data and doesn't know.
**What:** Header gets a green/yellow/red dot. Yellow if any source hasn't succeeded in 24h. Red if >48h. Tap → modal showing per-source `last_ok_at`. Data already in `ingest_state` table; just needs UI.
**Cost:** ~half a day (new small API endpoint + header indicator).
**Value:** Catches silent breakage. Also builds trust — when the dot is green, he knows the data is fresh.

#### 7. Tests on load-bearing modules — signals, matching, events
**Why:** Only `test_signals_amit_adjusted*.py` exists. Zero coverage on the three modules that decide what Shechter sees.
**What:** Start with `events.py` — 5 golden cases for price_drop, relisting, removal detection. Then `matching.py` (Haversine thresholds, cross-source dedup edge cases). Then `signals.py` at large. Pytest fixtures with synthetic snapshots.
**Cost:** ~1 day per module = 3 days total.
**Value:** One bad commit silently corrupts Shechter's view for weeks. Even shallow tests catch the obvious.

---

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

### Amit Fit — add rent/buy toggle + expand threshold coverage
1. **Toggle UI** — Amit Fit dashboard currently shows a mixed stream. Add explicit toggle: "Buying opportunities" vs "Rental opportunities" (Shechter's current view is mostly buy because thresholds are seeded for buy; rent has 93 candidates in Florentin but most miss Amit's aggressive rent targets).
2. **Threshold coverage gap** — only פלורנטין (hood_id=205) has thresholds seeded. Expand admin UI seeding for more neighborhoods OR scope Amit Fit explicitly to Florentin-only until more are seeded.
3. **Threshold realism audit (rent)** — Florentin rent pref=₪47-71/m²/mo vs market avg ₪120/m²/mo. Amit's rent targets are 40-50% below market → virtually nothing qualifies. Alan to decide: raise targets, or explicit "deals only" framing.
4. **Hard 30% cap (non-negotiable)** — Alan wants to lock Amit Fit such that any property >30% above preferred target gets NO tag, regardless of the per-bucket `max` column. Two readings pending: (a) display-time filter (keep admin columns, enforce cap at signal time) or (b) auto-derive `max = pref × 1.30` (make max a computed field). Alan to pick before implementation.

### Telegram bot for scan alerts
Send alerts when notable properties found after a scan completes.

### F6 — Neighborhood pulse (24-month ₪/m² sparkline)
Depends on full-city govmap backfill (in progress) + Amit providing thresholds for more neighborhoods.

### TODO — FilterBar Facebook source option
`frontend/src/components/FilterBar.tsx:124-126` only offers Yad2/Madlan. Add `<option value="facebook">Facebook</option>` so Shechter can filter to FB-only. (Note: FilterDrawer.tsx already has Facebook as a pill — verify FilterBar is still the one Shechter sees before investing time here.)

### TODO — Per-group city overrides
Some FB groups include posts from non-TLV cities. Either: (a) add a `default_city` column to `fb_groups` table and pass through to `_fb_post_to_listing`, or (b) trust the LLM's neighborhood detection and skip non-TLV posts when neighborhood is null AND text doesn't contain TLV keywords.

---

## PARKED

### FB Marketplace integration
Different from FB Groups (which now ships via Apify). Marketplace would need a separate Apify actor — revisit only if Groups doesn't give enough volume for Shechter.
