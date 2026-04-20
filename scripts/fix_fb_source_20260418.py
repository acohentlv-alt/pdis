#!/usr/bin/env python3
"""One-shot idempotent cleanup: fix source='facebook' for fb_* properties.

Run this ONCE against Neon between 10:30-18:00 IDT (before the next FB ingest
at 10:00 IDT tomorrow), after deploying the branch that removes the
`UPDATE properties SET source='yad2' WHERE source IS NULL` migration block.

Steps:
  1. Pre-flight: abort if any properties have source IS NULL (migration hasn't
     been purged from DB yet, or new rows are arriving without a source).
  2. Count fb_* rows whose source is wrong.
  3. UPDATE those rows to source='facebook'.
  4. DELETE orphaned property_matches rows for those property IDs.
  5. DELETE orphaned property_classifications rows for those property IDs.
  6. Commit and report.

Exit code: 0 on success, 1 on assertion failure.
"""
import os
import sys
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ["DATABASE_URL"]


def main() -> None:
    print("Connecting to Neon...", flush=True)
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:

            # --- Pre-flight: abort if any source IS NULL ------------------
            cur.execute("SELECT COUNT(*) AS n FROM properties WHERE source IS NULL")
            null_count = cur.fetchone()["n"]
            if null_count > 0:
                print(
                    f"ABORT: {null_count} properties have source IS NULL. "
                    "The old migration block may still be running or new rows arrived "
                    "without a source. Fix that first.",
                    flush=True,
                )
                sys.exit(1)
            print(f"Pre-flight OK: 0 properties with source IS NULL", flush=True)

            # --- Count bad fb_* rows -------------------------------------
            cur.execute(
                "SELECT COUNT(*) AS n FROM properties "
                "WHERE yad2_id LIKE 'fb_%' AND source != 'facebook'"
            )
            bad_count = cur.fetchone()["n"]
            print(
                f"Found {bad_count} fb_* properties with source != 'facebook'",
                flush=True,
            )

            if bad_count == 0:
                print("Nothing to fix. Exiting.", flush=True)
                return

            # --- Collect their IDs ---------------------------------------
            cur.execute(
                "SELECT id FROM properties "
                "WHERE yad2_id LIKE 'fb_%' AND source != 'facebook'"
            )
            rows = cur.fetchall()
            ids = [r["id"] for r in rows]
            print(f"Property IDs to fix: {ids[:20]}{'...' if len(ids) > 20 else ''}", flush=True)

            # --- UPDATE source -------------------------------------------
            cur.execute(
                "UPDATE properties SET source = 'facebook' "
                "WHERE yad2_id LIKE 'fb_%' AND source != 'facebook'"
            )
            updated = cur.rowcount
            print(f"Updated {updated} rows in properties", flush=True)

            # --- DELETE property_matches ---------------------------------
            # Column names: property_id_a, property_id_b
            cur.execute(
                "DELETE FROM property_matches "
                "WHERE property_id_a = ANY(%s) OR property_id_b = ANY(%s)",
                (ids, ids),
            )
            deleted_matches = cur.rowcount
            print(f"Deleted {deleted_matches} rows from property_matches", flush=True)

            # --- DELETE property_classifications -------------------------
            cur.execute(
                "DELETE FROM property_classifications WHERE property_id = ANY(%s)",
                (ids,),
            )
            deleted_classif = cur.rowcount
            print(f"Deleted {deleted_classif} rows from property_classifications", flush=True)

        # Commit everything atomically
        conn.commit()
        print(
            f"DONE. Updated {updated} properties, "
            f"deleted {deleted_matches} matches, {deleted_classif} classifications.",
            flush=True,
        )


if __name__ == "__main__":
    main()
