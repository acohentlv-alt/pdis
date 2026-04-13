"""
Layer 0: One-shot bulk import of Tel Aviv-Yafo building year_built data.

Pulls from TLV Municipality ArcGIS REST:
  - Layer 513 (Buildings): polygons + 'year' field
  - Layer 527 (Addresses): points + street/house/lat/lon
Spatial-joins (point-in-polygon) and upserts into building_metadata.
TLV Municipality WINS over madlan_cache (authoritative city source).
Idempotent. Safe to re-run monthly.
Usage: python3 scripts/import_tlv_buildings.py
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

import pdis.database as _db
from pdis.signals import _normalize_address

BUILDINGS_URL = "https://gisn.tel-aviv.gov.il/arcgis/rest/services/IView2/MapServer/513/query"
ADDRESSES_URL = "https://gisn.tel-aviv.gov.il/arcgis/rest/services/IView2/MapServer/527/query"
TLV_CITY_NAME = "תל אביב יפו"  # canonical normalized
PAGE_SIZE = 2000
SLEEP = 1.0


def _fetch_paged(url, where, out_fields, return_geometry):
    all_features = []
    offset = 0
    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "true" if return_geometry else "false",
            "f": "geojson" if return_geometry else "json",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
            "outSR": 4326,
        }
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        features = data.get("features", [])
        if not features:
            break
        all_features.extend(features)
        if len(features) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(SLEEP)
    return all_features


def _build_year_index(building_features):
    polygons = []
    year_by_idx = {}
    for f in building_features:
        props = f.get("properties") or f.get("attributes") or {}
        year = props.get("year")
        if not year:
            continue
        try:
            year = int(year)
        except (TypeError, ValueError):
            continue
        if not (1850 <= year <= 2050):
            continue
        geom = f.get("geometry")
        if not geom:
            continue
        try:
            poly = shape(geom)
        except Exception:
            continue
        idx = len(polygons)
        polygons.append(poly)
        year_by_idx[idx] = year
    tree = STRtree(polygons) if polygons else None
    return tree, polygons, year_by_idx


def _join_addresses_to_years(address_features, tree, polygons, year_by_idx):
    rows = []
    for f in address_features:
        props = f.get("attributes") or {}
        street = props.get("t_rechov")
        house_num = props.get("ms_bayit")
        lat = props.get("lat")
        lon = props.get("lon")
        if not (street and house_num is not None and lat and lon):
            continue
        c, s, h = _normalize_address(TLV_CITY_NAME, street, str(house_num))
        if not (c and s and h):
            continue
        pt = Point(float(lon), float(lat))
        candidates = list(tree.query(pt)) if tree else []
        year = None
        for idx in candidates:
            if polygons[idx].contains(pt):
                year = year_by_idx.get(idx)
                break
        if year is None:
            for idx in candidates:
                if polygons[idx].distance(pt) < 0.000135:  # ~15m in degrees
                    year = year_by_idx.get(idx)
                    break
        if year is None:
            continue
        rows.append((c, s, h, year, float(lat), float(lon)))
    return rows


async def _upsert_rows(rows):
    inserted = 0
    updated = 0
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            for c, s, h, y, lat, lon in rows:
                await cur.execute(
                    """INSERT INTO building_metadata
                       (city_norm, street_norm, house_number_norm, year_built, source, raw_lat, raw_lon, updated_at)
                       VALUES (%s, %s, %s, %s, 'tlv_municipality', %s, %s, NOW())
                       ON CONFLICT (city_norm, street_norm, house_number_norm) DO UPDATE SET
                           year_built = EXCLUDED.year_built,
                           source = 'tlv_municipality',
                           raw_lat = EXCLUDED.raw_lat,
                           raw_lon = EXCLUDED.raw_lon,
                           updated_at = NOW()
                       RETURNING (xmax = 0) AS was_inserted""",
                    (c, s, h, y, lat, lon),
                )
                row = await cur.fetchone()
                if row and row[0]:
                    inserted += 1
                else:
                    updated += 1
        await conn.commit()
    return inserted, updated


async def main():
    print("Initializing DB pool...")
    await _db.init_pool()

    print(f"Fetching buildings from {BUILDINGS_URL} ...")
    buildings = _fetch_paged(
        BUILDINGS_URL,
        where="year IS NOT NULL AND year > 1850",
        out_fields="id_binyan,year",
        return_geometry=True,
    )
    print(f"  Got {len(buildings)} buildings")

    print("Building spatial index...")
    tree, polygons, year_by_idx = _build_year_index(buildings)
    print(f"  Indexed {len(polygons)} polygons")

    print(f"Fetching addresses from {ADDRESSES_URL} ...")
    addresses = _fetch_paged(
        ADDRESSES_URL,
        where="ms_bayit IS NOT NULL",
        out_fields="t_rechov,ms_bayit,lat,lon",
        return_geometry=False,
    )
    print(f"  Got {len(addresses)} addresses")

    print("Joining addresses to building years...")
    rows = _join_addresses_to_years(addresses, tree, polygons, year_by_idx)
    print(f"  Joined {len(rows)} address->year pairs")

    print("Upserting into building_metadata...")
    inserted, updated = await _upsert_rows(rows)
    print(f"\nDone. Inserted {inserted}, updated {updated}, skipped {len(addresses) - len(rows)}.")

    await _db.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
