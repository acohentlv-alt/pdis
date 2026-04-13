#!/bin/bash
set -e
cd /opt/pdis-fb-scraper
source .env
export INGEST_SECRET PDIS_API_URL
exec /usr/bin/python3 run_yad2.py
