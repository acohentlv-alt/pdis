#!/bin/bash
set -euo pipefail
cd /opt/pdis-fb-scraper
source .env

# Proxy check — WARN but proceed if unset.
# Running from datacenter IP (Oracle VM) raises ban risk vs residential,
# but 4kirot-style architectures run without proxy successfully at low volume.
# Keep 1 scan/day, human-paced scrolling, monitor FB account for warnings.
if [ -z "${PROXY_URL:-}" ]; then
    echo "WARN: PROXY_URL not set — running without residential proxy. Account ban risk elevated."
fi

HOUR=$(date +%H)
# Probation mode: FB_SCANS_PER_DAY=1 → skip 18:00 run
if [ "${FB_SCANS_PER_DAY:-2}" = "1" ] && [ "$HOUR" = "18" ]; then
    echo "Probation mode: skipping 18:00 run"
    exit 0
fi
/usr/bin/python3 run.py
