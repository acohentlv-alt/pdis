# HANDOFF — July 13, 2026

## What we did today

**Exec A (PDIS Phase 1) shipped end-to-end — the first code on main since April 25, and the first brick of the PDIS→Maison lead-gen pivot.** Recovered the July 7 brief from its session transcript, ran the full loop (review REVISE → 7 findings fixed → exec in verified isolated worktree → QA 19/20 on a disposable Neon branch → L5 fix re-proven → smoke test), and pushed as `6160c58`. Also committed the long-orphaned April 25 session docs (`a16d7ed`).

What shipped: canonical neighborhood taxonomy (817→794 distinct spellings, originals preserved in `raw_data.neighborhood_raw`), "Updated Xd ago" recency badge, shared source-link builder + "View on Facebook" label fix + verify-at-source disclaimer, `property_leads` table + lead endpoints + "Flag as Maison lead" UI, and `pdis/arm_router.py` (R1–R4: wreck→Roi, Amit-fit→Amit, other-forsale→Eliyahu, rent→Alan).

## What's half-done

- **Exec B (Phase 3) is fully specified and decision-complete, not started.** Hidden `/leads` page, leads/suggestions endpoints, turf filter. See "NEXT UP" in TASKS.md — launches on Alan's "exec b".
- Alan never named his own additions to the starter Maison turf list (8 hoods are live in `pdis/neighborhoods.py::MAISON_TURF`).

## What to do next

1. Alan says **"exec b"** → implement Phase 3 from the 07-07 brief (decisions all locked; fold in the FB group_url-fallback fix).
2. Same QA pattern as today: create a Neon branch (`NEON_API_KEY` now in `~/pdis/.env`), QA there, delete after.

## Watch out for

- **PDIS is still FROZEN.** `6160c58` is on main but NOT deployed (Render suspended). The neighborhood backfill + `property_leads` migration will fire on prod automatically at unfreeze — that's intended and idempotent, but whoever unfreezes should expect it and run the AWAITING QA prod checks in TASKS.md.
- **Never start a local server with `.env`'s prod DATABASE_URL** — startup runs migrations. Use a Neon branch (that's what the API key is for).
- **Sweep for stale processes before QA** — an interrupted QA agent left a live uvicorn on the branch mid-session (now a memory rule).
- Amit is now a routed-to PARTNER, not the client — leads UI stays behind an unlinked route (Alan's decision 2b); nothing in his daily views changed except the recency badge.
- Alan's open micro-decision: whether bare `הצפון` stays a valid canonical hood (TASKS anchor).

## Test these

- Everything shipped today was QA'd (19/20 + re-verified fix) and smoke-tested on the branch DB — but **only on the branch**. Prod verification (817→~794 hoods, signal counts stable) can only happen at unfreeze.
- Alan has not yet eyeballed the live UI himself — the QA screenshots are in the 07-12 session scratchpad if wanted; or spin up a fresh Neon branch + local server for a hands-on look.

---

*Archived: HANDOFF_2026-04-25.md (evening, competitor investigation) · HANDOFF_2026-04-25_morning.md (morning, scraper.py findings) · HANDOFF_2026-04-23.md and earlier.*
