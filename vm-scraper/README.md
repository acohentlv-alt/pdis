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
