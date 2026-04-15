#!/bin/bash
set -euo pipefail
cd /opt/pdis-fb-scraper
source .env

if [ -z "${PROXY_URL:-}" ]; then
    echo "WARN: PROXY_URL not set — running without residential proxy. Account ban risk elevated."
fi

/usr/bin/python3 run.py
