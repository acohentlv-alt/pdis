# HANDOFF — April 5, 2026 (Evening Session)

---

## What we did today

Major UX overhaul: replaced the old Rent/Buy tab navigation with a preset-pill-based dashboard. Shechter now sees all his search presets as scrollable pills at the top, taps one to see its properties. Property cards redesigned with money first (big price + NIS/m²), then specs (rooms, floor, elevator ✓/✗, parking ✓/✗), then description preview. Removed Hot/Warm/Cold classification entirely — Shechter reads the individual signals himself. Fixed false relisting detection. Built neighborhood picker with real names instead of numeric IDs. Created 3 new presets matching Shechter's exact investment criteria.

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
Scanner now captures `info_text` from Yad2 detail API as description. ~450 existing properties still have placeholder descriptions (just street names). They'll be backfilled on next scan run automatically.

### Relisting data is historically inflated
Fixed the logic going forward (no more false relistings from scan gaps), but existing signal_details still have inflated relisting_count values. The "Reappeared" stat card shows high numbers. Will correct over time as signals are recomputed on future scans.

---

## What to do next

**First:** Verify on production that everything works — preset pills, switching, neighborhood picker, card layout, description display.

**Second:** Run a scan to backfill descriptions for existing properties. Check that `info_text` gets saved correctly.

**Third:** Telegram bot for scan alerts.

---

## Watch out for

- **per_page=2000**: Frontend fetches up to 2000 properties per preset. If a preset grows beyond this, results will be truncated. Monitor preset 8 (Full Scan TLV) which currently has 950.
- **Neighborhood picker depends on existing data**: The checkbox list shows neighborhoods that have properties in the DB. New neighborhoods only appear after a scan finds properties there.
- **City code mapping is indirect**: Presets store city_code (5000=TLV, 4000=Haifa) but properties don't have city_code — matching works via preset_id chain. Properties with preset_id=NULL are included via OR clause.
- **Classification still exists in backend**: The hot/warm/cold classification is still computed during scans and stored in DB. It's just hidden from the UI. If Alan ever wants it back, the data is there.
- **Run Now is now async**: POST /api/scan/{preset_id} returns immediately and runs in background. Uses the _scan_running lock to prevent collisions.
- **All previous watch-outs still apply**: English UI, hooks before returns, route ordering, Render cold start.
