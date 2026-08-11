# Rent Benchmarks — CBS + Madlan (research note)

*Filed 2026-08-11. Reference note, not a plan. PDIS is FROZEN — these are integration ideas for when it unfreezes.*

## Why this exists

PDIS already fires a `below_avg_price` distress signal (`signals.py`: price/sqm > 20%
below the neighborhood average). Today that "average" is derived from the **same
scraped asking listings** it is comparing against — a partly circular baseline. This
note records an **independent, real-rent reference layer** to calibrate that signal and
to seed `neighborhood_thresholds` (only Florentin is populated today).

---

## Source 1 — CBS (הלמ"ס), the only public *signed-rent* data

There is **no public registry of signed rental contracts in Israel** (unlike sales,
which are reported to the Tax Authority and are public — that is why Madlan/govmap sale
data is reliable). The closest public signal for *actual paid* rents is CBS survey data.

**Primary source (read 2026-08-11):**
https://www.cbs.gov.il/he/subjects/Pages/מחירים-ממוצעים-של-שכר-דירה.aspx

What CBS publishes:
- **Table 4.9** — "average monthly free-market rent (₪), by residence district, large
  cities, and dwelling-size groups (rooms)." Published monthly, **updated quarterly**,
  broken down by geographic area + room-count. This is the useful table.
- **Table 4.2 / 5.2** — the CPI rent sub-index (code 120460). Trend only, **no**
  geographic or dwelling-type split.

**CBS's own hard caveat (methodology doc, section ד — quote it before trusting a number):**
the average prices are an **order-of-magnitude indicator only**. CBS explicitly says they
must **not** be used to compute % change between periods (composition of reporters shifts).
For trend, use the index; for "roughly what does a 3-room in TA cost", use Table 4.9.

**Granularity limit that matters for PDIS:** Table 4.9 is at **city / district level**
(Tel Aviv-Yafo as a whole), split by rooms — **NOT by neighborhood**. So CBS can anchor
"is our city-wide baseline sane", never "is this Florentin listing underpriced".

**Directional figures (aggregator-sourced, dated — NOT yet pulled from Table 4.9 primary):**
- Tel Aviv average rent ≈ **₪6,700/mo** (~3-room, Jan 2026, ~+3.2% YoY).
- National average ≈ **₪4,950/mo** (2025, ~+4.3% YoY).
- New tenants pay ~**+6%** vs renewing tenants; rental supply **−8%** (2026).
- Fair Rent Law caps **renewals at ~2% + index** (relevant to asking→signed gap).
- ⚠️ These specific ₪ values are secondary-sourced and must be replaced with the exact
  Table 4.9 Tel Aviv figures before any are used in code. See TASKS.

## Source 2 — Madlan live data (already in PDIS's stack)

PDIS's `scraper_madlan.py` already hits `madlan.co.il/api3`. Beyond scraping listings,
the same surface exposes (verified 2026-08-11 on the Florentin area page):
- Full **sold-deal** dataset (price, size, ₪/m², construction year, date) — `searchDeals`
  GraphQL, the endpoint PDIS already uses.
- Live for-sale/for-rent listings carrying **days-on-market**, Madlan's modeled yield,
  approximate rent, and **urban-renewal status** per listing.
- Observed Florentin rents: **₪128–142 /m² /mo, roughly flat across sizes** (no
  small-unit rent premium — heavy studio supply). A ~48 m² 2-room ≈ ₪6,400/mo.

**Cross-validation:** the Madlan-scraped ~₪6,400/mo for a TA 2-room lines up with the
CBS TA-wide ~₪6,700 anchor. The scraped-asking baseline PDIS relies on is **not
systematically off** — which is the main thing CBS is good for here.

---

## How this helps PDIS (concrete, tied to existing code)

1. **Calibrate `below_avg_price`** (`signals.py`). Keep the per-neighborhood baseline
   computed from scraped listings, but add a periodic **city-level sanity check against
   CBS Table 4.9**: if the scraped TA median drifts far from the CBS anchor, the baseline
   (not the market) is suspect. CBS is a guardrail, not a per-listing benchmark.

2. **Seed `neighborhood_thresholds`** (only Florentin today; the "Amit neighborhood
   threshold data" item under WAITING ON EXTERNAL INPUT). CBS can't give per-neighborhood
   numbers, but the Madlan `searchDeals` + live-listing extraction proven today **can**
   compute median ₪/m² (rent and sale) per TLV neighborhood to seed every hood — with CBS
   as the city-level reality check on top.

3. **Interpret asking-based signals correctly.** All PDIS signals fire on **asking**
   prices. The asking→signed gap is **small for rent (~5%, capped at renewal by law)** but
   larger for sale. So a rent listing below the expected benchmark is a **high-confidence**
   distress signal; CBS is the only public signed-rent check on that.

4. **Higher-confidence distress lead** = priced below the scraped neighborhood median
   **and** below the CBS city anchor, rather than below the (circular) scraped median alone.

**Do NOT:** use CBS averages for trend/% change (their rule), or as a per-neighborhood
benchmark (they're city-level). Keep it as a calibration anchor only.

---

## Sources
- CBS rent methodology (primary, read 2026-08-11): https://www.cbs.gov.il/he/subjects/Pages/מחירים-ממוצעים-של-שכר-דירה.aspx
- Market direction (secondary, dated): klikatnadlan.co.il/rentdemand2026 · ynet.co.il/economy/article/yokra14681378
- Madlan Florentin area data: extracted live 2026-08-11 (asking rents + sold deals via api3 store).
