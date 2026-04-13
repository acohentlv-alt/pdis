# HANDOFF — April 12–13, 2026 (Long Session)

---

## What we did today

Planned, reviewed, built, QA'd, committed, and pushed **Facebook Groups as a 3rd data source for PDIS**. 4 planner passes + 4 reviews before exec — the review cycle caught real schema hallucinations each pass (columns that didn't exist, migration dirs that didn't exist, ordering bugs that would have silently broken dedup). Commit `c53e651` on main — Render is auto-deploying. Also rewrote the `planner.md` agent definition to enforce "cite file:line for every claim" and killed the "write BRIEF_*.md" rule that contradicted Alan's memory.

Architecture pivoted mid-session from paid Apify → burner account → **personal FB account on Oracle VM, no proxy, $0/mo** after Alan pushed back on both the Apify subscription and the 4-week burner warmup. The decision to skip residential proxy matches what 4kirot.com appears to do (Firebase Cloud Functions = datacenter IP) — acceptable risk on an aged personal account at 1 scan/day.

---

## What's live on main (backend auto-deployed)

- **`/api/ingest/facebook`** POST (bearer auth with `INGEST_SECRET`, 403 on bad bearer, 503 when `FB_INGESTION_ENABLED=false`)
- **`/api/ingest/facebook/health`** GET unauth (returns warning_count, last_ok_at, alert flag)
- **`/api/ingest/facebook/log-reveal`** POST unauth (audit trail for phone reveals)
- **New `ingest_state` singleton table** for silent-failure tracking
- **3 new columns on `properties`**: `author_name`, `group_url`, `like_count`
- **`run_scan_from_listings()`** + **`_mark_fb_removals_for_session()`** in `scanner.py` (FB-scoped removal runs AFTER matching per reviewer Pass 4)
- **Idempotent FB preset seed** in `database.py` (survives non-empty search_presets)
- Low-volume guard bypassed on first-ever ingest (`prior_count=0`)
- **Frontend was already live** from `29706c9` (another session bundled my FB frontend changes into Phase 1C commit): phone mask `054-***-****` with tap-to-reveal on FB cards, indigo FB badge, yellow dashboard banner

**Feature flag `FB_INGESTION_ENABLED=false`** — no behavior change for Shechter until Alan flips it.

---

## What's half-done

### Alan's ~30 min deployment checklist (nothing technical left for Claude)
1. Verify Render deploy finished: `curl https://pdis-lsah.onrender.com/api/ingest/facebook/health` returns valid JSON
2. Verify `TLV_CITY_STRING`: `SELECT DISTINCT address_city FROM properties WHERE source='yad2' LIMIT 5` on Neon — if not `"תל אביב-יפו"`, update the constant in `routes.py` before flipping flag
3. Generate `INGEST_SECRET`: `openssl rand -hex 32`
4. Set Render env vars: `INGEST_SECRET=<value>`, `FB_INGESTION_ENABLED=false`, `FB_SCANS_PER_DAY=1`
5. On laptop: `cd ~/pdis/vm-scraper && python3 export_fb_cookies.py` → log in with personal FB → saves `fb_state.json`
6. SCP scraper + cookies to Oracle VM (commands in `vm-scraper/README.md`)
7. Install deps on VM, test-run `./run.sh` manually, verify `posts_found > 0` (this validates m.facebook.com DOM selectors against real FB)
8. Add crontab with `CRON_TZ=Asia/Jerusalem` at 08:00 + 18:00 with `flock`
9. Flip `FB_INGESTION_ENABLED=true` → watch first real scan

### VM scraper code is in repo (`vm-scraper/`) but not yet on VM
Files committed to `~/pdis/vm-scraper/`: `run.py`, `run.sh`, `export_fb_cookies.py`, `groups.json`, `requirements.txt`, `.env.example`, `README.md`. All deployed via `scp -r` when Alan's ready.

---

## What to do next (next session)

**If Alan has already deployed FB Brief #1 and scrape is running:**
- Watch the first day of real FB ingest. Check `/api/ingest/facebook/health` for warning counter. Check `properties WHERE source='facebook'` for parse quality.
- After 1 week of real data, re-plan **Brief #2** (FB-aware dedup, no-broker signal, broker-flooding filter, Nominatim geocoding pass).

**If Alan hasn't deployed yet:**
- Walk him through the 30-min deployment checklist above.

**If blocker hits:**
- If m.facebook.com DOM selectors broke (posts_found=0 on test run): pivot parser to www.facebook.com mobile emulation. Small change in `vm-scraper/run.py`.
- If personal account shows "unusual activity" warnings: stop the cron immediately, fall back to Raspberry Pi ($35 one-time) at home for truly residential IP.

**Unrelated parked items:**
- Telegram bot for scan alerts (not started)
- Backfill descriptions for ~450 properties (next scan will do it automatically)
- FB Marketplace integration (PARKED — needs Playwright + image hashing)

---

## Watch out for

- **Phase 1B and 1C Amit Fit shipped today by a parallel session** (commits `02a3366` and `29706c9`). The Phase 1C commit accidentally bundled my FB frontend changes (PropertyCard.tsx phone mask + OpportunityPage.tsx banner) alongside the Amit Fit display work — that's why today's FB commit only touched backend + vm-scraper, no frontend.
- **`run.sh` was softened from hard-exit to warning** when `PROXY_URL` is unset. That's intentional — Alan chose the 4kirot-style "datacenter IP at low volume" approach. If he ever wants to add residential proxy later (Smartproxy ~$7/mo), just set `PROXY_URL` in VM's `.env`.
- **`_is_agent` bug caught by tests**: the broker detection was firing True on "ללא תיווך" (WITHOUT broker) posts — inverted behavior. Fixed in `vm-scraper/run.py:166-170` by stripping the negation phrase before keyword matching. Do not regress this.
- **Low-volume guard bypass**: `scanner.py:579` — on first-ever FB ingest (prior_count=0), threshold drops to 1. Prevents the bootstrap-forever problem. Do not change without thinking through.
- **Scraper files live in `~/pdis/vm-scraper/`** but deploy to `/opt/pdis-fb-scraper/` on the VM. Different paths — don't confuse.
- **Never commit `state.json`, `.env`, `fb_state.json`** — all in `.gitignore`.
- **The `planner.md` rewrite** is now live at `~/.claude/agents/planner.md`. Future `/plan` and `/review` invocations will enforce the "cite file:line" discipline. This prevented pass-2 and pass-3 hallucinations from surviving to production.

---

## Test these (post-deployment)

- Hit `/api/ingest/facebook/health` in Render — valid JSON response
- Run the scraper manually once on VM — check `posts_found > 0` in log
- Flip flag to true, wait 10 min, `SELECT COUNT(*) FROM properties WHERE source='facebook'` — should be nonzero
- Open PDIS in browser, find an FB property, tap the eye icon — full phone reveals
- Refresh — phone re-masks
- Yad2 cards unchanged (no eye icon, phone always visible)

---

## Cost summary

| Item | Monthly |
|---|---|
| Oracle VM | $0 (free tier, existing) |
| Residential proxy | $0 (not subscribing — datacenter IP accepted) |
| Playwright / Chromium | $0 |
| **Total** | **$0/mo** |

If burner-replacement ever becomes needed: Raspberry Pi $35 one-time, or fallback to Apify ~$5–10/mo.
