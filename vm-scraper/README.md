# PDIS VM Scrapers

Runs on the Oracle VM (`ubuntu@129.159.158.214`).

## Facebook Groups (Apify + Haiku pipeline)

Since Apr 15, 2026, FB Groups are scraped via the Apify actor
`apify/facebook-groups-scraper` and parsed by Claude Haiku 4.5. The VM
runs an orchestrator that calls Apify and POSTs to the Render ingest
endpoint — no Playwright, no cookies, no proxy on the VM.

- Orchestrator: `apify_to_pdis.py`
- LLM parse: `llm_parse.py`
- Entry: `run.sh` → `run.py` (systemd: `pdis-fb-scraper.timer`, daily 10:00 IDT)
- Group catalog: upsert via `scripts/seed_fb_groups.py` reading
  `scripts/fb_groups_discovered.json`
- Env: `APIFY_TOKEN`, `ANTHROPIC_API_KEY`, `INGEST_SECRET`, `PDIS_API_URL`
- Render gate: `FB_INGESTION_ENABLED=true`
- Health: `GET /api/ingest/facebook/health`

See CLAUDE.md "Facebook Groups (active)" for the full pipeline description.

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
