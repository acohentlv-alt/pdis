"""One-shot backfill for closed_transactions data-quality bugs.

Fixes:
  1. sqm pulled from raw_data.assetArea (scraper was reading non-existent 'dealArea')
  2. rooms pulled from raw_data.assetRoomNum
  3. centroid_lat/lng recomputed from raw_data.shape WKT first vertex
     (old centroids were generated with wrong EPSG:2039 transformer → bogus 85°N coords)

price_per_sqm is a GENERATED column — auto-recomputes from sqm + sale_price.

Safe to re-run: only touches rows where the field is NULL/missing/bogus.
"""

from __future__ import annotations
import asyncio
import re
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pdis.database as _db
from pyproj import Transformer

_merc_to_wgs = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

_FIRST_VERTEX_RE = re.compile(r"\(\(+\s*([-\d.]+)\s+([-\d.]+)")


def wkt_first_vertex_to_wgs(wkt: str) -> tuple[float, float] | None:
    """Parse `MULTIPOLYGON(((X Y, X Y, ...` → (lat, lng) via Web Mercator → WGS-84."""
    m = _FIRST_VERTEX_RE.search(wkt or "")
    if not m:
        return None
    try:
        x, y = float(m.group(1)), float(m.group(2))
    except ValueError:
        return None
    if x < 1_000_000 or y < 1_000_000:
        return None  # already in lat/lng range or malformed
    lng, lat = _merc_to_wgs.transform(x, y)
    return lat, lng


async def main():
    await _db.init_pool()
    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            # ── Step 1: backfill sqm from raw_data.assetArea
            await cur.execute("""
                UPDATE closed_transactions
                SET sqm = (raw_data->>'assetArea')::INTEGER
                WHERE sqm IS NULL
                  AND raw_data->>'assetArea' ~ '^[0-9]+$'
                  AND (raw_data->>'assetArea')::INTEGER > 0
            """)
            sqm_fixed = cur.rowcount
            print(f"sqm backfilled:    {sqm_fixed:>6} rows")

            # ── Step 2: backfill rooms from raw_data.assetRoomNum
            await cur.execute("""
                UPDATE closed_transactions
                SET rooms = (raw_data->>'assetRoomNum')::FLOAT
                WHERE rooms IS NULL
                  AND raw_data->>'assetRoomNum' ~ '^[0-9]+(\\.[0-9]+)?$'
            """)
            rooms_fixed = cur.rowcount
            print(f"rooms backfilled:  {rooms_fixed:>6} rows")

            # ── Step 3: recompute centroid_lat/lng from shape WKT
            # Select rows where centroid is bogus (out of Israel bbox) or NULL
            await cur.execute("""
                SELECT deal_id, raw_data->>'shape' AS wkt
                FROM closed_transactions
                WHERE raw_data->>'shape' IS NOT NULL
                  AND (
                       centroid_lat IS NULL
                    OR centroid_lat NOT BETWEEN 29.0 AND 34.0
                    OR centroid_lng NOT BETWEEN 33.0 AND 36.5
                  )
            """)
            rows = await cur.fetchall()
            print(f"centroid candidates: {len(rows):>6} rows")
            centroid_fixed = 0
            batch_pairs: list[tuple[float, float, int]] = []
            for r in rows:
                converted = wkt_first_vertex_to_wgs(r["wkt"])
                if not converted:
                    continue
                lat, lng = converted
                if not (29.0 <= lat <= 34.0 and 33.0 <= lng <= 36.5):
                    continue  # sanity: still outside Israel → skip
                batch_pairs.append((lat, lng, r["deal_id"]))
                if len(batch_pairs) >= 500:
                    await cur.executemany(
                        "UPDATE closed_transactions SET centroid_lat=%s, centroid_lng=%s WHERE deal_id=%s",
                        batch_pairs,
                    )
                    centroid_fixed += len(batch_pairs)
                    batch_pairs = []
            if batch_pairs:
                await cur.executemany(
                    "UPDATE closed_transactions SET centroid_lat=%s, centroid_lng=%s WHERE deal_id=%s",
                    batch_pairs,
                )
                centroid_fixed += len(batch_pairs)
            print(f"centroid backfilled: {centroid_fixed:>6} rows")

            # ── Sanity: recount
            await cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(sqm) AS with_sqm,
                    COUNT(price_per_sqm) AS with_pps,
                    COUNT(CASE WHEN centroid_lat BETWEEN 29.0 AND 34.0
                               AND centroid_lng BETWEEN 33.0 AND 36.5 THEN 1 END) AS with_good_coords
                FROM closed_transactions
            """)
            r = await cur.fetchone()
            print()
            print("Post-backfill state:")
            print(f"  total:             {r['total']:>6}")
            print(f"  with sqm:          {r['with_sqm']:>6}")
            print(f"  with price_per_sqm:{r['with_pps']:>6}  (generated col)")
            print(f"  with Israel coords:{r['with_good_coords']:>6}")
        await conn.commit()
    await _db.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
