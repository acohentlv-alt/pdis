"""Rule-based classification engine."""
import json

import structlog

import pdis.database as _db
from pdis.signals import compute_signals_batch

logger = structlog.get_logger(__name__)


async def classify_batch(property_ids: list[int]) -> dict[int, str]:
    """
    Classify properties as hot/warm/cold and persist to property_classifications.
    Returns {property_id: classification}
    """
    if not property_ids:
        return {}

    # Compute signals for all
    signals = await compute_signals_batch(property_ids)

    async with _db.pool.connection() as conn:
        async with conn.cursor() as cur:
            # Check whitelist/blacklist
            await cur.execute(
                "SELECT property_id FROM whitelist WHERE property_id = ANY(%s)",
                (property_ids,),
            )
            whitelisted = {r["property_id"] for r in await cur.fetchall()}

            await cur.execute(
                "SELECT property_id FROM blacklist WHERE property_id = ANY(%s)",
                (property_ids,),
            )
            blacklisted = {r["property_id"] for r in await cur.fetchall()}

            # Classify each
            results = {}
            for pid in property_ids:
                sig = signals.get(pid, {"distress_score": 0, "details": {}})
                score = sig["distress_score"]

                if pid in blacklisted:
                    classification = "cold"
                elif pid in whitelisted:
                    classification = "hot"
                elif score >= 50:
                    classification = "hot"
                elif score >= 25:
                    classification = "warm"
                else:
                    classification = "cold"

                results[pid] = classification

                # UPSERT into property_classifications
                await cur.execute(
                    """INSERT INTO property_classifications
                       (property_id, classification, distress_score, signal_details, updated_at)
                       VALUES (%s, %s, %s, %s::jsonb, NOW())
                       ON CONFLICT (property_id) DO UPDATE SET
                           classification = EXCLUDED.classification,
                           distress_score = EXCLUDED.distress_score,
                           signal_details = EXCLUDED.signal_details,
                           updated_at = NOW()""",
                    (pid, classification, score, json.dumps(sig["details"])),
                )

        await conn.commit()

    counts: dict[str, int] = {}
    for c in results.values():
        counts[c] = counts.get(c, 0) + 1
    logger.info("classification.done", counts=counts)

    return results
