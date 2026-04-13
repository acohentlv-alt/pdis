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

4. **Create `.env` on VM** with `INGEST_SECRET`, `PDIS_API_URL`, `PROXY_URL`, `FB_SCANS_PER_DAY=1` (start low, ramp later)

5. **Install dependencies:**
   ```bash
   ssh ubuntu@129.159.158.214
   cd /opt/pdis-fb-scraper
   python3 -m pip install -r requirements.txt
   playwright install chromium
   playwright install-deps  # may need sudo
   ```

6. **Test run manually before cron:**
   ```bash
   cd /opt/pdis-fb-scraper && ./run.sh
   # Watch output — verify PROXY_URL is being used, no "WARN: No PROXY_URL" message
   # Verify posts are parsed, POST to PDIS returns 200
   ```

7. **Add crontab:**
   ```
   CRON_TZ=Asia/Jerusalem
   0 8,18 * * * flock -n /var/lock/pdis-fb-scraper.lock /opt/pdis-fb-scraper/run.sh >> /var/log/pdis-fb-scraper.log 2>&1
   ```

8. **Flip `FB_INGESTION_ENABLED=true` in Render env vars.**

## Important rules (personal account ban prevention)

- **NEVER run the scraper without `PROXY_URL` set in production** — datacenter IP from Oracle VM = ban
- **NEVER use `state.json` cookies from two places at once** — if you log into FB on laptop while scraper is running, FB sees same account from 2 IPs = ban risk
- **Start at `FB_SCANS_PER_DAY=1`** for the first 2 weeks, then ramp to 2
- **If you ever see "unusual activity detected" or "verify it's you" in your personal FB app** — STOP the cron immediately (`crontab -e`, comment out the line), log in manually on your laptop, resolve it
- **Scraper must NEVER log cookie values** (already handled in run.py)

## Render environment variables to set

| Variable | Purpose |
|----------|---------|
| `INGEST_SECRET` | Shared bearer token — scraper and backend must match |
| `FB_INGESTION_ENABLED` | Set to `true` to enable FB ingest (default: `false`) |
| `FB_SCANS_PER_DAY` | `1` = probation (08:00 only), `2` = full (08:00 + 18:00) |

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
