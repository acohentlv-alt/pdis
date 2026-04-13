"""Signal persistence — writes signal_details to property_classifications."""
import json

import structlog

import pdis.database as _db
from pdis.signals import compute_signals_batch

logger = structlog.get_logger(__name__)


async def persist_signals_batch(property_ids: list[int]) -> None:
    """
    Compute signals for a batch of properties and persist signal_details
    to property_classifications (UPSERT). No tier classification.
    """
    if not property_ids:
        return

    signals = await compute_signals_batch(property_ids)

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            for pid in property_ids:
                sig = signals.get(pid)
                if not sig:
                    continue

                signal_details = {
                    "strong_signals": sig["strong_signals"],
                    "weak_signals": sig["weak_signals"],
                    "buyer_fit_tags": sig.get("buyer_fit_tags", []),
                    **sig["details"],
                }

                await cur.execute(
                    """INSERT INTO property_classifications
                       (property_id, signal_details, updated_at)
                       VALUES (%s, %s::jsonb, NOW())
                       ON CONFLICT (property_id) DO UPDATE SET
                           signal_details = EXCLUDED.signal_details,
                           updated_at = NOW()""",
                    (pid, json.dumps(signal_details)),
                )

        await conn.commit()

    logger.info("signals.persisted", count=len(signals))
