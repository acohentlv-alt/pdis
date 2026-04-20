#!/usr/bin/env python3
"""One-shot: find and optionally null-out suspect prices on Facebook rent listings.

Run this AFTER fix_fb_source_20260418.py and after deploying the Render build
that includes the new sanity bands. This cleans up any historical rows that
slipped through before the bands existed.

Steps:
  1. Count rows where source='facebook' AND category='rent' AND price < 2500
     AND price IS NOT NULL.
  2. Print 10 sample rows so Alan can verify they're garbage.
  3. Prompt for explicit 'y' confirmation.
  4. Only on 'y': UPDATE those rows SET price=NULL in a single transaction.

Runs read-only if Alan answers anything other than 'y'.
"""
import os
import sys
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ["DATABASE_URL"]

_WHERE = (
    "source = 'facebook' "
    "AND category = 'rent' "
    "AND price < 2500 "
    "AND price IS NOT NULL"
)


def main() -> None:
    print("Connecting to Neon...", flush=True)
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:

            # --- Count ---------------------------------------------------
            cur.execute(f"SELECT COUNT(*) AS n FROM properties WHERE {_WHERE}")
            count = cur.fetchone()["n"]
            print(
                f"\nRows with source='facebook', category='rent', price < 2500 "
                f"(and price IS NOT NULL): {count}",
                flush=True,
            )

            if count == 0:
                print("Nothing to fix. Exiting.", flush=True)
                return

            # --- Sample rows -------------------------------------------
            cur.execute(
                f"""
                SELECT id, yad2_id, price, LEFT(description, 200) AS desc_snippet
                FROM properties
                WHERE {_WHERE}
                ORDER BY id
                LIMIT 10
                """
            )
            samples = cur.fetchall()
            print("\nSample rows (up to 10):")
            for row in samples:
                print(
                    f"  id={row['id']} yad2_id={row['yad2_id']} price={row['price']}"
                    f"\n    desc: {row['desc_snippet']!r}"
                )

            # --- Confirmation ------------------------------------------
            print(
                f"\n  {count} rows will have price set to NULL. "
                "Type 'y' to proceed, anything else to abort."
            )
            answer = input("  Continue? [y/N]: ").strip().lower()
            if answer != "y":
                print("Aborted. No changes made.", flush=True)
                return

            # --- Update -------------------------------------------------
            cur.execute(
                f"UPDATE properties SET price = NULL WHERE {_WHERE}"
            )
            updated = cur.rowcount

        conn.commit()
        print(f"DONE. Nulled price on {updated} Facebook rent rows.", flush=True)


if __name__ == "__main__":
    main()
