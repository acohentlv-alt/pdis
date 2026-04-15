"""
scripts/cleanup_fb_broken_rows.py
----------------------------------
Gated cleanup script for the 738 FB rows that were backfilled with wrong source/empty
raw_data during the yad2-only migration pass (Brief A).

Run ONLY after the investigation SQL in Brief A-7 confirms preconditions.

Modes
-----
Mode 1 (default) — Apify dataset retrievable
  Full DELETE of all fb_* rows plus all FK-dependent rows, inside a single transaction.

Mode 2 (--fallback-in-place) — Apify dataset expired
  In-place UPDATE only: fix source column, re-normalize phone numbers.
  Addresses stay NULL — they will populate on the next daily scrape.

Required flags
--------------
  --confirm          Must be passed explicitly, or the script will dry-run and exit.
  --fallback-in-place  Switch to Mode 2 instead of Mode 1.

Usage
-----
  # Dry run (shows plan, does nothing):
  python scripts/cleanup_fb_broken_rows.py

  # Mode 1 — full delete (Apify dataset still available):
  python scripts/cleanup_fb_broken_rows.py --confirm

  # Mode 2 — in-place fix (Apify dataset expired):
  python scripts/cleanup_fb_broken_rows.py --fallback-in-place --confirm
"""

import argparse
import asyncio
import os
import sys

# Ensure project root is on path when run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import structlog
import psycopg
from psycopg.rows import dict_row

from pdis.yad2_phone import normalize_phone

logger = structlog.get_logger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

# FK-dependent tables to delete from (in dependency order, child tables first)
FK_TABLES = [
    "property_matches",        # references property_id_a, property_id_b
    "property_events",         # references property_id
    "property_snapshots",      # references property_id
    "property_classifications", # references property_id
    "property_operator_input", # references property_id (UNIQUE)
    "favorites",               # references yad2_id (text FK)
    "whitelist",               # references yad2_id (text FK)
    "blacklist",               # references yad2_id (text FK)
    "operator_notes",          # references property_id or yad2_id
]

# Tables that use integer property_id FK
FK_BY_PROPERTY_ID = [
    "property_matches",
    "property_events",
    "property_snapshots",
    "property_classifications",
    "property_operator_input",
    "operator_notes",
]

# Tables that use yad2_id (text) FK — delete by yad2_id LIKE 'fb_%'
FK_BY_YAD2_ID = [
    "favorites",
    "whitelist",
    "blacklist",
]


async def run(mode_delete: bool, confirm: bool) -> None:
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable is not set.", flush=True)
        sys.exit(1)

    async with await psycopg.AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as conn:

        # --- Count target rows ---
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) AS n FROM properties WHERE yad2_id LIKE 'fb_%'")
            total_fb = (await cur.fetchone())["n"]

            await cur.execute(
                "SELECT COUNT(*) AS n FROM properties WHERE yad2_id LIKE 'fb_%' AND source = 'yad2'"
            )
            wrong_source = (await cur.fetchone())["n"]

            await cur.execute(
                "SELECT COUNT(*) AS n FROM properties WHERE yad2_id LIKE 'fb_%' AND contact_phone IS NOT NULL"
            )
            has_phone = (await cur.fetchone())["n"]

        print("=" * 60, flush=True)
        print("FB cleanup plan", flush=True)
        print("=" * 60, flush=True)
        print(f"  Total fb_* rows:          {total_fb}", flush=True)
        print(f"  Rows with source='yad2':  {wrong_source}", flush=True)
        print(f"  Rows with phone:          {has_phone}", flush=True)

        if mode_delete:
            print(f"\n  MODE: Full DELETE (Mode 1)", flush=True)
            print(f"  Will delete all fb_* rows and all FK-dependent rows.", flush=True)
        else:
            print(f"\n  MODE: In-place UPDATE (Mode 2 --fallback-in-place)", flush=True)
            print(f"  Will fix source column and re-normalize phone numbers.", flush=True)
            print(f"  Addresses will stay NULL (populated on next daily scrape).", flush=True)

        if not confirm:
            print("\n  DRY RUN — pass --confirm to execute.", flush=True)
            return

        print("\n  Executing...", flush=True)

        if mode_delete:
            await _mode1_full_delete(conn, total_fb)
        else:
            await _mode2_in_place(conn, total_fb, has_phone)

        print("\nDone.", flush=True)


async def _mode1_full_delete(conn, total_fb: int) -> None:
    """Mode 1: Full transactional DELETE of all fb_* rows + FK-dependent data."""
    async with conn.transaction():
        async with conn.cursor() as cur:

            # Fetch property ids for all fb_* rows
            await cur.execute(
                "SELECT id FROM properties WHERE yad2_id LIKE 'fb_%'"
            )
            rows = await cur.fetchall()
            property_ids = [r["id"] for r in rows]
            print(f"  Found {len(property_ids)} property IDs to delete.", flush=True)

            if not property_ids:
                print("  Nothing to delete.", flush=True)
                return

            # Delete from property_matches — either side
            await cur.execute(
                """DELETE FROM property_matches
                   WHERE property_id_a = ANY(%s) OR property_id_b = ANY(%s)""",
                (property_ids, property_ids),
            )
            print(f"  property_matches deleted: {cur.rowcount}", flush=True)

            # Delete from tables with integer property_id FK
            for table in [
                "property_events",
                "property_snapshots",
                "property_classifications",
                "property_operator_input",
                "operator_notes",
            ]:
                try:
                    await cur.execute(
                        f"DELETE FROM {table} WHERE property_id = ANY(%s)",
                        (property_ids,),
                    )
                    print(f"  {table} deleted: {cur.rowcount}", flush=True)
                except Exception as exc:
                    # Some tables may not have property_id — fall through
                    print(f"  WARN: {table} delete skipped ({exc})", flush=True)

            # Delete from tables with yad2_id text FK
            for table in ["favorites", "whitelist", "blacklist"]:
                try:
                    await cur.execute(
                        f"DELETE FROM {table} WHERE yad2_id LIKE 'fb_%%'"
                    )
                    print(f"  {table} deleted: {cur.rowcount}", flush=True)
                except Exception as exc:
                    print(f"  WARN: {table} delete skipped ({exc})", flush=True)

            # Finally delete the properties themselves
            await cur.execute(
                "DELETE FROM properties WHERE yad2_id LIKE 'fb_%'"
            )
            deleted = cur.rowcount
            print(f"  properties deleted: {deleted} (expected ~{total_fb})", flush=True)

    logger.warning(
        "cleanup_fb.mode1_complete",
        deleted_properties=deleted,
        total_expected=total_fb,
    )


async def _mode2_in_place(conn, total_fb: int, has_phone: int) -> None:
    """Mode 2: In-place fix — correct source column and re-normalize phone numbers."""
    async with conn.transaction():
        async with conn.cursor() as cur:

            # Fix source column
            await cur.execute(
                """UPDATE properties SET source = 'facebook', updated_at = NOW()
                   WHERE yad2_id LIKE 'fb_%' AND source = 'yad2'"""
            )
            source_fixed = cur.rowcount
            print(f"  source fixed: {source_fixed} rows", flush=True)

            # Re-normalize phone numbers for fb_* rows that have one
            await cur.execute(
                """SELECT id, contact_phone FROM properties
                   WHERE yad2_id LIKE 'fb_%' AND contact_phone IS NOT NULL"""
            )
            rows = await cur.fetchall()
            print(f"  Phone rows to normalize: {len(rows)}", flush=True)

            updated_phone = 0
            nulled_phone = 0
            for row in rows:
                normed = normalize_phone(row["contact_phone"])
                await cur.execute(
                    "UPDATE properties SET contact_phone = %s, updated_at = NOW() WHERE id = %s",
                    (normed, row["id"]),
                )
                if normed is None:
                    nulled_phone += 1
                else:
                    updated_phone += 1

            print(
                f"  Phones re-normalized: {updated_phone} kept, {nulled_phone} set to NULL",
                flush=True,
            )

    logger.warning(
        "cleanup_fb.mode2_complete",
        source_fixed=source_fixed,
        phones_kept=updated_phone,
        phones_nulled=nulled_phone,
        total_fb=total_fb,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cleanup broken FB rows from the yad2-only migration pass."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually execute (without this flag, only a dry-run plan is printed).",
    )
    parser.add_argument(
        "--fallback-in-place",
        action="store_true",
        dest="fallback",
        help="Mode 2: in-place UPDATE instead of full DELETE (use when Apify dataset has expired).",
    )
    args = parser.parse_args()

    mode_delete = not args.fallback

    asyncio.run(run(mode_delete=mode_delete, confirm=args.confirm))


if __name__ == "__main__":
    main()
