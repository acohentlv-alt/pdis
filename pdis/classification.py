"""Signal persistence — writes signal_details to property_classifications."""
import json

import structlog

import pdis.database as _db
from pdis.signals import compute_signals_batch

logger = structlog.get_logger(__name__)


async def persist_signals_batch(property_ids: list[int]) -> None:
    """
    Compute signals for a batch of properties and persist signal_details
    to property_classifications (batched UPSERT). No tier classification.

    Uses executemany so psycopg3 pipelines all inserts in a single round
    trip — keeps the connection hold time under 1s even for 1000+ rows,
    which dodges Neon's ~5-min idle-kill window that previously crashed
    long VM scans (session 268, 2026-04-23).
    """
    if not property_ids:
        return

    signals = await compute_signals_batch(property_ids)

    rows: list[tuple[int, str]] = []
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
        try:
            rows.append((pid, json.dumps(signal_details)))
        except (TypeError, ValueError) as exc:
            logger.warning("signals.serialize_failed", pid=pid, error=str(exc))

    if not rows:
        return

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.executemany(
                """INSERT INTO property_classifications
                   (property_id, signal_details, updated_at)
                   VALUES (%s, %s::jsonb, NOW())
                   ON CONFLICT (property_id) DO UPDATE SET
                       signal_details = EXCLUDED.signal_details,
                       updated_at = NOW()""",
                rows,
            )
        await conn.commit()

    logger.info("signals.persisted", count=len(rows))
