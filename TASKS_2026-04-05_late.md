# PDIS — Task List
*April 5, 2026 (late night session)*

---

## DONE (today)

### Default sort: Market time + Signals
Combined sort: days on market descending, then signal count as tiebreaker. Single dropdown option replaces old separate "Most signals" and "Days on market".

### Preset Manager scroll fix
Added pb-16 padding and bumped z-index to z-[60] so bottom nav bar doesn't overlap last preset card.

---

## AWAITING TEST

### Verify latest push on production
- Preset Manager scrolls to bottom with padding
- Sort dropdown shows "Market time + Signals" as default
- Cards sorted by longest on market first

### Scheduled scans still need verification
cron-job.org set up but scan behavior with new code needs checking.

---

## NOT STARTED

### Telegram bot
Send alerts when notable properties found after scan.

### Backfill descriptions for existing properties
Scanner now captures descriptions, but ~450 existing properties have none. Next scan run will backfill them automatically.

### Facebook Marketplace integration (PARKED)
