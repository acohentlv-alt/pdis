"""CLI script to run full cross-source match reindex.
Usage: python -m pdis.reindex_matches
"""
import asyncio
from pdis.database import init_pool, close_pool
from pdis.matching import run_full_cross_source_match


async def main():
    await init_pool()
    count = await run_full_cross_source_match()
    print(f"Found {count} new cross-source matches")
    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
