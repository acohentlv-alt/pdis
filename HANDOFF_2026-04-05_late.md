# HANDOFF — April 5, 2026 (Late Night Session)

---

## What we did today

Continued from the evening session. Fixed two UX issues: (1) Preset Manager screen now scrolls fully to the last preset — the bottom nav bar was overlapping, fixed by bumping z-index and adding padding. (2) Default sort is now "longest on market first, then most signals as tiebreaker" — combined into a single "Market time + Signals" dropdown option. Ran QA via Playwright against local to verify both changes. Pushed to main for Render deploy.

---

## What's live

### Production
- **App:** https://pdis-lsah.onrender.com
- **Repo:** github.com/acohentlv-alt/pdis
- **Scheduled scans:** cron-job.org, 08:00 + 18:00 Israel time

### Six presets active
- TLV Rent - Golden (ID=7): 9 premium neighborhoods, condition=5
- TLV Rent - Full Scan (ID=8): all TLV rentals
- Haifa Buy (ID=9): all Haifa for sale
- Haifa Buy - Small Apts (ID=11): 1-2.5 rooms, under 400K, 4 neighborhoods
- Haifa Buy - Buildings (ID=12): house/land types
- TLV Rent - Villas (ID=13): house/cottage, 180m²+, 15-30K

---

## What's half-done

### Description backfill
Scanner now captures `info_text` from Yad2 detail API as description. ~450 existing properties still have placeholder descriptions. They'll be backfilled on next scan run automatically.

### Relisting data is historically inflated
Fixed the logic going forward but existing signal_details still have inflated relisting_count values. Will correct over time as signals are recomputed on future scans.

---

## What to do next

**First:** Verify on production that the two changes deployed correctly — preset manager scrolls to bottom, sort shows "Market time + Signals" as default.

**Second:** Trigger a scan to backfill descriptions for existing properties.

**Third:** Telegram bot for scan alerts.

---

## Watch out for

- **Preset pills are horizontal scroll** — Alan likes this design. Don't change to wrapped/vertical layout.
- **Sort logic:** "Market time + Signals" is the agreed default — days_on_market DESC, then signal count DESC as tiebreaker. Don't separate these into two dropdown options.
- **PresetManager z-index is z-[60]** — bumped above NavBar (z-50) so the bottom nav doesn't poke through. If other modals are added, keep z-index hierarchy in mind.
- **per_page=2000**: Frontend fetches up to 2000 properties per preset. Monitor preset 8 (Full Scan TLV) which currently has 950+.
- **All previous watch-outs still apply**: English UI, hooks before returns, route ordering, Render cold start.

---

## Test these

- Preset Manager: open on mobile, scroll to bottom — "TLV Rent - Villas" should have clear space below it, no nav bar overlap
- Sort dropdown: should show "Market time + Signals" by default, cards sorted by longest on market first
