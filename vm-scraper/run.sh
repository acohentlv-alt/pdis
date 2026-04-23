#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
source .env

exec /usr/bin/python3 apify_to_pdis.py
