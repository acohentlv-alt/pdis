# PDIS — Task List
*April 5, 2026*

---

## DONE (today)

*(empty — new day)*

---

## AWAITING TEST

### Scheduled scans via cron-job.org
**What:** Two cron jobs set up (08:00 + 18:00 Israel time) hitting POST /api/scan/scheduled with Bearer token. Need to verify first automated scan triggers correctly.

---

## NOT STARTED

### Telegram bot
**What:** Send alerts when new hot properties are detected after a scan. Shechter gets a Telegram message with property summary + link.

### Classification threshold tuning
**What:** Alan wants to finetune: price drop % for strong signal (currently >10%), days on market thresholds (currently 90+ strong, 30-89 weak), relisting count, below-average price %, weak signal count for hot (currently 3+). Needs more data first.

### Facebook Marketplace integration (PARKED)
**What:** Third data source. Needs Playwright + perceptual image hashing. Multiple blockers identified in reviews. Parked until other priorities done.
