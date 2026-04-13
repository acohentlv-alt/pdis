#!/usr/bin/env python3
"""
Run on your laptop to export your personal Facebook session cookies.
Saves fb_state.json for transfer to the Oracle VM.

Usage:
  python3 export_fb_cookies.py
  # Log in with your personal Facebook account, confirm you can see group posts, press Enter
  # Then transfer to VM:
  #   scp fb_state.json ubuntu@129.159.158.214:/opt/pdis-fb-scraper/state.json
  #   ssh ubuntu@129.159.158.214 "chmod 600 /opt/pdis-fb-scraper/state.json"

IMPORTANT: Never use state.json from two places at once.
If you log into Facebook on your laptop while the VM scraper is running,
Facebook sees the same account from two IPs simultaneously — ban risk.
"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto('https://m.facebook.com/login')
    input('Log in with your personal Facebook account, confirm you can see group posts, then press Enter...')
    ctx.storage_state(path='fb_state.json')
    print('Saved fb_state.json. Transfer to VM:')
    print('  scp fb_state.json ubuntu@129.159.158.214:/opt/pdis-fb-scraper/state.json')
    print('  ssh ubuntu@129.159.158.214 "chmod 600 /opt/pdis-fb-scraper/state.json"')
    browser.close()
