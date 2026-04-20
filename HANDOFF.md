# HANDOFF — April 20, 2026

## What we did today

Shipped PR #2 — three-item cleanup covering FB source labels, Haiku prompt rewrite, and sqm accuracy. Full `/plan → /review → /exec → /qa` cycle ran cleanly (two review rounds caught the sanity-band loop-placement bug and the wrong endpoint list before exec). Ran the Item 1 fix script against Neon: 690 fb_* rows relabeled to `source='facebook'`, 58 stale cross-source matches deleted, 690 stale classifications cleared. Merged branch to main. Render is live with the new code; frontend now reads only `display_sqm`.

Also investigated the "only 4 Amit Fit rent matches" bug — not a code bug. The `neighborhood_thresholds` table only has rows for פלורנטין. Every other TLV neighborhood is empty, so Amit Fit literally can't match listings outside Florentin. Blocked on Amit's numbers.

## What's half-done / deferred

- **VM deploy deliberately deferred.** `vm-scraper/llm_parse.py` + `vm-scraper/apify_to_pdis.py` haven't been pushed to the Oracle VM. Alan's reasoning: he's about to add new FB groups (including building-for-sale groups) and receive Amit's threshold data. Better to deploy VM after both land so the first post-deploy scrape categorizes everything correctly end-to-end. The Render/VM schema mismatch is safe in the interim — old VM's `intent="sale"` gets legacy-remapped on Render; old single `sqm` field is silently dropped by Pydantic.
- **`scripts/fb_price_sweep_20260418.py` not yet run.** Has an interactive y/N gate. Run AFTER VM deploys + one clean scrape completes, so any remaining bad historical prices get nulled while new scrapes are clean.
- **`scripts/madlan_field_probe.py` not yet run.** Standalone read-only, can run any time. Output feeds a follow-up micro-brief on Madlan GraphQL field fixes (balcony detection + net-sqm).

## What to do next

**Wait on two external inputs:**
1. Amit's per-neighborhood threshold data (target_price_per_sqm_preferred + _max per 7 size buckets)
2. Alan's curated list of new FB groups to add (rent + building-for-sale)

**While waiting — next session's assignment:** clean stale code. Candidates live in TASKS.md under "🧹 Next session" — safest wins are:
- Delete `vm-scraper/run.py` (455 lines dead Playwright) + fix `tests/test_fb_parser.py` imports
- Drop `pdis/scraper.py` Yad2-on-Render fallback (target Apr 26, 1 week post-VM-migration)
- Remove `fetch_item_detail` (dead, per QA finding)
- Gate or remove `/api/debug/recent-errors` temporary diagnostic

## Watch out for

- **Deploy state is intentionally split.** Render has new code, VM has old. Don't let the next agent "fix" this by running the VM deploy — Alan explicitly deferred it. See TASKS.md "DEPLOY PENDING".
- **Rebase landed cleanly** but dropped the pre-existing "Split is_active" commit from the branch (already on main under a different SHA — safe skip during rebase).
- **CLAUDE.md was updated** post-merge with the new FB intent schema + `display_sqm` API convention. Committed directly to main as `c1c054c`.
- **Amit Fit rent count still shows 4** after today's fix. That's expected — it only lifts when Amit's threshold data lands, not from any code change. Do NOT go spelunking for an Amit Fit bug when Alan asks why it's still 4.
- **Executor made a judgment call** during exec: the brief listed 17 endpoints needing `display_sqm`, but 7 of them don't actually return sqm fields (events, matches, snapshots). Those were left with plain `dict(r)`. Sensible — adding display_sqm=None everywhere is noise.
- **Round-3 reviewer found `sqmBuild`/`sqmTotal` references left dangling** in PropertyCard.tsx:95 and PropertyDetailPage.tsx:219 after executor's swap. Fixed inline before PR push — verified `tsc --noEmit` clean.

## Test these

- [ ] iPhone: open a property card, verify `display_sqm` shows the same value on card and detail page for the same property
- [ ] iPhone: check that FB rent cards still render sqm (will be from `square_meters`, i.e., old-schema fallback, until VM deploys)
- [ ] `curl 'https://pdis-lsah.onrender.com/api/presets/8/properties?limit=1' | jq '.properties[0] | {display_sqm, square_meter_build, square_meters}'` — all three present, display_sqm = build OR gross
- [ ] Render dashboard: confirm `c1c054c` deploy succeeded (doc-only change, should be trivial)
- [ ] Amit Fit rent count stays at ~4 (expected until thresholds load)
- [ ] `SELECT source, COUNT(*) FROM properties WHERE yad2_id LIKE 'fb_%' GROUP BY source` on Neon → only `facebook`, no `yad2`

---

*Archived sessions:*
- *HANDOFF_2026-04-19.md — Apr 18-19 late-night session: Yad2 rent→VM + phone-hook fix, queued morning deploy, strategic vision dump.*
- *HANDOFF_2026-04-18_evening.md — Apr 18 evening Madlan latency fix.*
- *HANDOFF_2026-04-18_morning.md — Apr 17-18 day→evening pool fix + telemetry.*
- *HANDOFF_2026-04-17.md — Apr 17 is_active split session.*
