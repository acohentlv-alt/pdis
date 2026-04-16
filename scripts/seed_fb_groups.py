"""
Seed the fb_groups table from fb_groups_discovered.json.

Upserts all groups listed in scripts/fb_groups_discovered.json.
Existing rows are updated (name, url, last_seen_at) but is_active is never touched
— deactivate groups manually in the DB if needed.

Usage:
    python3 scripts/seed_fb_groups.py

Reads:  scripts/fb_groups_discovered.json
Writes: fb_groups table in Neon DB (via DATABASE_URL in .env)
"""

import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pdis.database as _db

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
INPUT_FILE = SCRIPT_DIR / "fb_groups_discovered.json"


async def main():
    if not INPUT_FILE.exists():
        print(f"ERROR: {INPUT_FILE} not found.")
        print("Populate scripts/fb_groups_discovered.json first (manually or via your own enumeration).")
        sys.exit(1)

    groups = json.loads(INPUT_FILE.read_text())
    if not groups:
        print("No groups in file — nothing to seed.")
        return

    print(f"Initializing DB pool...")
    await _db.init_pool()

    inserted = 0
    updated = 0

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            for g in groups:
                group_id = g["group_id"]
                name = g["name"]
                url = g["url"]

                await cur.execute(
                    """
                    INSERT INTO fb_groups (group_id, name, url)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (group_id) DO UPDATE SET
                        name         = EXCLUDED.name,
                        url          = EXCLUDED.url,
                        last_seen_at = NOW()
                    RETURNING (xmax = 0) AS was_inserted
                    """,
                    (group_id, name, url),
                )
                row = await cur.fetchone()
                if row and row.get("was_inserted"):
                    inserted += 1
                else:
                    updated += 1

        await conn.commit()

    print(f"Done. Inserted {inserted} new groups, updated {updated} existing groups.")
    print(f"Total in file: {len(groups)}")

    await _db.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
