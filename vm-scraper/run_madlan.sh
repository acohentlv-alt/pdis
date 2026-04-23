#!/bin/bash
# Do NOT set -e: we want git-pull failures to fall through to
# last-known-good code rather than skipping the daily scan.
cd /opt/pdis-madlan-scraper

if git pull --ff-only 2>&1; then
    echo "$(date -Is) git pull ok"
else
    echo "$(date -Is) git pull FAILED — running last-known-good code on disk"
fi

GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
export GIT_COMMIT

# Load DATABASE_URL and any MADLAN_* tuning vars
set -a
source .env
set +a

# Allow `from pdis...` imports — this runner reuses run_all_scans() from the main package
export PYTHONPATH=/opt/pdis-madlan-scraper

exec /usr/bin/python3 -u vm-scraper/run_madlan.py
