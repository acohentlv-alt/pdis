# PDIS — Task List
*April 14, 2026*

---

## READY TO RUN (next session, on VM)

### Govmap full TLV backfill (~14-42h weekend run)
Pipeline is fully verified end-to-end (commit `2078efd`). Test run inserted 2 Lev-Ha'ir deals, POST 200.

On the Oracle VM, in a tmux session:
```
sudo apt install -y tmux && tmux new -s govmap
cd ~/pdis && git pull
cd vm-scraper && set -a && source .env && set +a && python3 run_govmap.py 2>&1 | tee /tmp/govmap_full.log
```
Detach: `Ctrl+B` then `D`. Reattach later: `tmux attach -t govmap`.

After completion:
- Verify row count: `SELECT COUNT(*) FROM closed_transactions` (expect 500k–1M for full TLV)
- Spot-check coords landed in Tel Aviv (not Antarctica): `SELECT centroid_lat, centroid_lng FROM closed_transactions LIMIT 10` — lat should be ~32.0, lng ~34.7
- Open a Florentin property in the UI — Closed Comps panel should render with real data

### Add monthly cron on VM (after backfill succeeds)
```
crontab -e
# add:
CRON_TZ=Asia/Jerusalem
0 3 1 * * cd /home/ubuntu/pdis/vm-scraper && set -a; source .env; set +a; /home/ubuntu/pdis/venv/bin/python3 run_govmap.py --monthly >> /tmp/govmap_cron.log 2>&1
```
Runs first of each month at 3am Israel time.

---

## AWAITING DEPLOY (code shipped, Alan's manual steps remain)

### FB scraper — original brief #1 still not deployed
Code has been on main since commit `c53e651` (days ago). Deployment checklist:
1. Verify Render deploy finished: `curl https://pdis-lsah.onrender.com/api/ingest/facebook/health`
2. Verify `TLV_CITY_STRING` = `"תל אביב-יפו"` on Neon
3. `INGEST_SECRET` is already set on Render (done today). FB uses same secret.
4. Add Render env: `FB_INGESTION_ENABLED=false`, `FB_SCANS_PER_DAY=1`
5. On laptop: `python3 export_fb_cookies.py` → log in with personal FB → `fb_state.json`
6. SCP scraper + cookies to VM, install deps, manual test run
7. Crontab on VM at 08:00 + 18:00 Israel time
8. Flip `FB_INGESTION_ENABLED=true`

### Yad2 forsale VM deployment (commit 21941f2)
Similar pattern to govmap. Script is at `vm-scraper/run_yad2.py` already on the VM.
1. Add Render env: `YAD2_VM_INGESTION_ENABLED=true` (currently false)
2. On VM, add crontab entry for `vm-scraper/run_yad2.sh` at 08:30 + 18:30 (30 min stagger after rent scans)

---

## NOT STARTED

### Phone numbers — critical per Alan, not yet wired
- Madlan: scraper reads `poc.displayNumber` but 0/713 properties get one. Broken or API changed.
- Yad2: requires separate click-to-reveal API call (not wired).
- FB: works in theory but depends on FB scraper deployment above.
Needs its own `/plan` session.

### FB Groups Brief #2 (re-plan after 1 week of real FB data)
FB-aware dedup, new FB-specific signals (no-broker badge, multi-group cross-post = high distress), Nominatim geocoding pass.

### FB Groups Brief #3
Source filter dropdown, "Hide brokers" toggle, "Report this listing" link.

### Telegram bot for scan alerts
Send alerts when notable properties found after a scan completes.

### F6 — Neighborhood pulse (24-month ₪/m² sparkline)
Depends on full-city govmap backfill + Amit providing thresholds for more hoods.

---

## PARKED

### FB Marketplace integration
Reviewed and parked. Needs Playwright + perceptual image hashing.
