# PDIS Facebook Groups Scraper

Runs on the Oracle VM (`ubuntu@129.159.158.214`).
Scrapes 5 TLV rental Facebook groups and sends results to the PDIS Render backend.

## Setup steps (personal Facebook account)

1. **Purchase residential proxy** (REQUIRED — ~$5–15/mo):
   - Recommended: **Smartproxy** (smartproxy.com) — $7/mo entry tier, Israel IPs available
   - Alternatives: Bright Data, Oxylabs, IPRoyal
   - Get the proxy URL: `http://username:password@gate.smartproxy.com:7000` (or similar)
   - **Critical:** verify it's a RESIDENTIAL proxy, not datacenter

2. **On your laptop, run `export_fb_cookies.py`** — logs you in, saves `fb_state.json`

3. **Transfer cookies + code to VM:**
   ```bash
   scp -r vm-scraper ubuntu@129.159.158.214:/opt/pdis-fb-scraper
   scp fb_state.json ubuntu@129.159.158.214:/opt/pdis-fb-scraper/state.json
   ssh ubuntu@129.159.158.214 'chmod 600 /opt/pdis-fb-scraper/state.json /opt/pdis-fb-scraper/.env && chmod 700 /opt/pdis-fb-scraper'
   ```

4. **Create `.env` on VM** with `INGEST_SECRET`, `PDIS_API_URL`, `PROXY_URL`

5. **Install dependencies:**
   ```bash
   ssh ubuntu@129.159.158.214
   cd /opt/pdis-fb-scraper
   python3 -m pip install -r requirements.txt
   playwright install chromium
   playwright install-deps  # may need sudo
   ```

6. **Test run manually before enabling the timer:**
   ```bash
   cd /opt/pdis-fb-scraper && ./run.sh
   # Watch output — verify PROXY_URL is being used
   # Verify posts are parsed, POST to PDIS returns 200
   ```

## Install (systemd, Ubuntu VM)

Copy unit files:
    sudo cp systemd/pdis-fb-scraper.service /etc/systemd/system/
    sudo cp systemd/pdis-fb-scraper.timer /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now pdis-fb-scraper.timer

Verify:
    systemctl list-timers pdis-fb-scraper.timer
    # NEXT column should show 10:00 Asia/Jerusalem tomorrow

If an old crontab entry exists, remove it:
    crontab -e
    # Delete the line invoking run.sh; save.

7. **Flip `FB_INGESTION_ENABLED=true` in Render env vars.**

## Important rules (personal account ban prevention)

- **WARN (not hard-fail) if `PROXY_URL` is unset** — run.sh prints a warning and continues. Low volume (once/day) on Oracle VM IP is manageable but raises ban risk.
- **NEVER use `state.json` cookies from two places at once** — if you log into FB on laptop while scraper is running, FB sees same account from 2 IPs = ban risk
- **If you ever see "unusual activity detected" or "verify it's you" in your personal FB app** — STOP the timer immediately (`sudo systemctl stop pdis-fb-scraper.timer`), log in manually on your laptop, resolve it

## Render environment variables to set

| Variable | Purpose |
|----------|---------|
| `INGEST_SECRET` | Shared bearer token — scraper and backend must match |
| `FB_INGESTION_ENABLED` | Set to `true` to enable FB ingest (default: `false`) |

## Before flipping FB_INGESTION_ENABLED=true — manual verification checklist

1. **Step 0a**: Verify `TLV_CITY_STRING = "תל אביב-יפו"` matches the `address_city` value in your
   prod DB for existing TLV properties. Run on Neon:
   ```sql
   SELECT DISTINCT address_city FROM properties WHERE source IN ('yad2','madlan') LIMIT 20;
   ```

2. **Step 0b**: Verify m.facebook.com DOM selectors in `run.py` match the actual FB mobile HTML.
   After exporting cookies, open a session and inspect the group page DOM. Selectors to check:
   - Post container: `article` or `[role="article"]`
   - Author: `h3 a`
   - Timestamp: `abbr` or `time[datetime]`
   - Post text: `[data-testid="post_message"]` or `div[dir="auto"]`
   - Permalink: `a[href*="/permalink/"]` or `a[href*="/posts/"]`

## Security notes

- Never commit `state.json`, `fb_state.json`, or `.env` — they are in `.gitignore`
- `state.json` contains FB session cookies — treat like a password, `chmod 600`
- `INGEST_SECRET` is never logged by the scraper

## When the scraper stops returning posts

If three consecutive scheduled runs return 0 posts AND
  SELECT warning_count FROM ingest_state WHERE source='facebook';
returns 3 or more, your Facebook session cookies have likely expired.

To refresh:
1. On your laptop: cd vm-scraper && python3 export_fb_cookies.py
2. scp -i ~/.ssh/oracle_vm vm-scraper/fb_state.json ubuntu@129.159.158.214:/opt/pdis-fb-scraper/state.json
   (run.py reads state.json — that is the correct destination filename)
3. ssh -i ~/.ssh/oracle_vm ubuntu@129.159.158.214 "sudo systemctl restart pdis-fb-scraper.timer"

## When to re-run seed_fb_groups.py

Only after discovering new groups via enumerate_fb_groups.py.
It upserts from scripts/fb_groups_discovered.json (49 rows today) into
the fb_groups table. Not needed on every scrape.

## VM memory note

The Oracle VM is a 1GB micro. Tight when Playwright + Chromium run
alongside the govmap backfill. After go-live, monitor `free -m` during
the 10:00 window. If memory pressure appears, stagger govmap backfill
to pause 09:55-10:10 (simple cron tweak, out of A2 scope).

---

## Yad2 forsale scraper

### Why

Render's IP is blocked by ShieldSquare (Yad2's anti-bot system) on the `/forsale` endpoint.
The `/rent` endpoint works fine on Render. For forsale, scraping must run from the Oracle VM
which uses a residential-grade Oracle Cloud IP that is not on Yad2's blocklist.

### Deploy

```bash
# Copy files to VM
scp vm-scraper/run_yad2.py vm-scraper/run_yad2.sh ubuntu@129.159.158.214:/opt/pdis-fb-scraper/

# On VM: make executable + install dependency
ssh ubuntu@129.159.158.214
chmod +x /opt/pdis-fb-scraper/run_yad2.sh
pip install 'curl_cffi>=0.7'
```

### Test manually

```bash
ssh ubuntu@129.159.158.214
cd /opt/pdis-fb-scraper
./run_yad2.sh
```

Watch the output — verify presets are fetched, listings scraped, and backend returns HTTP 200.

### Cron entry

Add to VM crontab (`crontab -e`):

```
CRON_TZ=Asia/Jerusalem
30 8,18 * * * flock -n /var/lock/pdis-yad2-scraper.lock /opt/pdis-fb-scraper/run_yad2.sh >> /var/log/pdis-yad2-scraper.log 2>&1
```

Note: runs 30 minutes after the rent scan (which runs at :00) to avoid DB contention.

### Enable in production

Set the following in Render environment variables:

```
YAD2_VM_INGESTION_ENABLED=true
```

Without this flag the `/api/ingest/yad2` endpoint returns 503 and no data is stored.
`INGEST_SECRET` is the same secret used by the FB scraper — no separate secret needed.

---

## Govmap closed-sale ingestion

Scrapes closed real-estate transactions from the Israel Tax Authority via govmap.gov.il.
Walks a grid over Tel Aviv, collects unique polygon IDs, fetches deals per polygon,
projects coordinates from EPSG:2039 (ITM) to WGS-84, and POSTs batches of 100 deals
to `/api/ingest/govmap-deals` on the PDIS backend.

### Dependencies

Install on VM before first run:

```bash
pip install 'pyproj>=3.6' 'curl_cffi>=0.7'
# Or install everything from requirements.txt:
pip install -r requirements.txt
```

### Deploy

```bash
# Copy files to VM
scp vm-scraper/run_govmap.py vm-scraper/run_govmap.sh ubuntu@129.159.158.214:/opt/pdis-fb-scraper/

# On VM: make executable
ssh ubuntu@129.159.158.214
chmod +x /opt/pdis-fb-scraper/run_govmap.sh
```

### Backfill (one-off — run on a weekend, takes 14-42 hours)

```bash
ssh ubuntu@129.159.158.214
cd /opt/pdis-fb-scraper
./run_govmap.sh >> /var/log/pdis-govmap-scraper.log 2>&1
```

To resume a partial backfill without re-importing already-loaded polygons:

```bash
./run_govmap.sh --resume >> /var/log/pdis-govmap-scraper.log 2>&1
```

### Monthly refresh cron entry

Add to VM crontab (`crontab -e`) — only fetches deals from the last 35 days:

```
CRON_TZ=Asia/Jerusalem
0 3 1 * * flock -n /var/lock/pdis-govmap-scraper.lock /opt/pdis-fb-scraper/run_govmap.sh --monthly >> /var/log/pdis-govmap-scraper.log 2>&1
```

Runs at 3am on the 1st of each month (Israel time) to keep comps current.

### Enable in production

Set the following in Render environment variables:

```
GOVMAP_INGESTION_ENABLED=true
```

Without this flag the `/api/ingest/govmap-deals` endpoint returns 503 and no data is stored.
`INGEST_SECRET` is the same secret used by other scrapers — no separate secret needed.
