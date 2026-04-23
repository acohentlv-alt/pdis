"""Scheduled scan runner for Oracle VM.

Calls run_all_scans() which scans every scan_enabled preset.
On this VM, Yad2 presets short-circuit with status=skipped_vm (because
YAD2_VM_INGESTION_ENABLED is set), so only Madlan (preset 44) actually
scrapes. Removal detection runs at the end of run_all_scans — keeping
parity with the old cron-fired Render path.

Exits non-zero on failure so systemd records it.
"""

import asyncio
import os
import sys
import structlog

from pdis.database import init_pool, close_pool
from pdis.scanner import run_all_scans

log = structlog.get_logger("run_madlan")


async def main() -> int:
    commit = os.environ.get("GIT_COMMIT", "unknown")
    log.info("madlan_vm.start", commit=commit)
    await init_pool()
    try:
        results = await run_all_scans()
        # results is a list of per-preset summaries
        statuses = [(r.get("preset_id"), r.get("status")) for r in results]
        log.info("madlan_vm.done", statuses=statuses, count=len(results))
        # Succeed if Madlan (preset 44) ran cleanly OR was at least attempted
        madlan = next((r for r in results if r.get("preset_id") == 44), None)
        if not madlan:
            log.error("madlan_vm.madlan_preset_not_found")
            return 1
        return 0 if madlan.get("status") == "done" else 1
    except Exception as exc:
        log.exception("madlan_vm.error", error=str(exc))
        return 1
    finally:
        await close_pool()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
