"""
Database setup and connection pool for PDIS.
Creates tables on startup and provides async helpers.
"""

import structlog
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

from pdis.config import settings

logger = structlog.get_logger(__name__)

# Module-level pool, initialised in lifespan
pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    """Initialise the async connection pool and run migrations."""
    global pool
    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        min_size=0,
        max_size=10,
        kwargs={"row_factory": dict_row},
        open=False,
        # Short timeout so startup fails fast when DB is unavailable
        timeout=5.0,
    )
    await pool.open(wait=False)
    logger.info("db.pool_opened")
    try:
        await run_migrations()
    except Exception as exc:
        logger.warning(
            "db.migrations_skipped",
            reason=str(exc),
            hint="Set DATABASE_URL in .env to a real Neon connection string",
        )


async def close_pool() -> None:
    """Close the connection pool."""
    global pool
    if pool:
        await pool.close()
        logger.info("db.pool_closed")


async def run_migrations() -> None:
    """Create all tables and indexes if they do not exist, then seed presets."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS search_presets (
                    id              SERIAL PRIMARY KEY,
                    name            TEXT NOT NULL,
                    category        TEXT NOT NULL DEFAULT 'rent',
                    city_code       TEXT NOT NULL,
                    neighborhood    TEXT,
                    area_code       TEXT,
                    min_price       INTEGER,
                    max_price       INTEGER,
                    min_rooms       REAL,
                    max_rooms       REAL,
                    property_types  TEXT[],
                    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
                    extra_params    JSONB DEFAULT '{}',
                    created_at      TIMESTAMPTZ DEFAULT NOW(),
                    updated_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS scan_sessions (
                    id              SERIAL PRIMARY KEY,
                    preset_id       INTEGER NOT NULL REFERENCES search_presets(id),
                    started_at      TIMESTAMPTZ DEFAULT NOW(),
                    finished_at     TIMESTAMPTZ,
                    status          TEXT NOT NULL DEFAULT 'running',
                    listings_found  INTEGER DEFAULT 0,
                    new_listings    INTEGER DEFAULT 0,
                    error_message   TEXT,
                    pages_scraped   INTEGER DEFAULT 0
                )
            """)

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS properties (
                    id              SERIAL PRIMARY KEY,
                    yad2_id         TEXT NOT NULL UNIQUE,
                    preset_id       INTEGER REFERENCES search_presets(id),
                    category        TEXT NOT NULL DEFAULT 'rent',
                    address_street  TEXT,
                    address_city    TEXT,
                    neighborhood    TEXT,
                    rooms           REAL,
                    floor           INTEGER,
                    total_floors    INTEGER,
                    square_meters   INTEGER,
                    price           INTEGER,
                    currency        TEXT DEFAULT 'ILS',
                    property_type   TEXT,
                    description     TEXT,
                    contact_name    TEXT,
                    contact_phone   TEXT,
                    image_urls      TEXT[],
                    listing_url     TEXT,
                    raw_data        JSONB,
                    first_seen      DATE NOT NULL DEFAULT CURRENT_DATE,
                    last_seen       DATE NOT NULL DEFAULT CURRENT_DATE,
                    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
                    days_on_market  INTEGER DEFAULT 0,
                    created_at      TIMESTAMPTZ DEFAULT NOW(),
                    updated_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_properties_yad2_id ON properties(yad2_id)"
            )
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_properties_preset_id ON properties(preset_id)"
            )
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_properties_is_active ON properties(is_active)"
            )

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS property_snapshots (
                    id              SERIAL PRIMARY KEY,
                    property_id     INTEGER NOT NULL REFERENCES properties(id),
                    session_id      INTEGER NOT NULL REFERENCES scan_sessions(id),
                    price           INTEGER,
                    is_listed       BOOLEAN NOT NULL DEFAULT TRUE,
                    raw_data        JSONB,
                    captured_at     TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(property_id, session_id)
                )
            """)

            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_property_id ON property_snapshots(property_id)"
            )
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_session_id ON property_snapshots(session_id)"
            )

            # Add hash columns to property_snapshots
            await cur.execute(
                "ALTER TABLE property_snapshots ADD COLUMN IF NOT EXISTS description_hash TEXT"
            )
            await cur.execute(
                "ALTER TABLE property_snapshots ADD COLUMN IF NOT EXISTS image_hash TEXT"
            )

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS property_events (
                    id              SERIAL PRIMARY KEY,
                    property_id     INTEGER NOT NULL REFERENCES properties(id),
                    session_id      INTEGER REFERENCES scan_sessions(id),
                    event_type      TEXT NOT NULL,
                    old_value       TEXT,
                    new_value       TEXT,
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_property_id ON property_events(property_id)"
            )
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_session_id ON property_events(session_id)"
            )
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_event_type ON property_events(event_type)"
            )

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS property_classifications (
                    id              SERIAL PRIMARY KEY,
                    property_id     INTEGER NOT NULL UNIQUE REFERENCES properties(id),
                    classification  TEXT NOT NULL DEFAULT 'cold',
                    distress_score  REAL NOT NULL DEFAULT 0.0,
                    signal_details  JSONB DEFAULT '{}',
                    updated_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_classifications_class ON property_classifications(classification)"
            )
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_classifications_score ON property_classifications(distress_score)"
            )

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS whitelist (
                    id              SERIAL PRIMARY KEY,
                    property_id     INTEGER NOT NULL UNIQUE REFERENCES properties(id),
                    reason          TEXT,
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    id              SERIAL PRIMARY KEY,
                    property_id     INTEGER NOT NULL UNIQUE REFERENCES properties(id),
                    reason          TEXT,
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS property_matches (
                    id              SERIAL PRIMARY KEY,
                    property_id_a   INTEGER NOT NULL REFERENCES properties(id),
                    property_id_b   INTEGER NOT NULL REFERENCES properties(id),
                    match_tier      INTEGER NOT NULL,
                    match_reason    TEXT NOT NULL,
                    confidence      REAL DEFAULT 0.0,
                    is_confirmed    BOOLEAN DEFAULT NULL,
                    created_at      TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(property_id_a, property_id_b)
                )
            """)
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_matches_prop_a ON property_matches(property_id_a)"
            )
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_matches_prop_b ON property_matches(property_id_b)"
            )

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS operator_notes (
                    id              SERIAL PRIMARY KEY,
                    property_id     INTEGER NOT NULL REFERENCES properties(id),
                    note            TEXT NOT NULL,
                    created_by      TEXT DEFAULT 'operator',
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_notes_property_id ON operator_notes(property_id)"
            )

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS scan_preset_stats (
                    id              SERIAL PRIMARY KEY,
                    preset_id       INTEGER NOT NULL REFERENCES search_presets(id),
                    session_id      INTEGER NOT NULL REFERENCES scan_sessions(id),
                    total_active    INTEGER DEFAULT 0,
                    new_listings    INTEGER DEFAULT 0,
                    removals        INTEGER DEFAULT 0,
                    price_drops     INTEGER DEFAULT 0,
                    price_increases INTEGER DEFAULT 0,
                    opportunities   INTEGER DEFAULT 0,
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_preset_stats_session ON scan_preset_stats(session_id)"
            )

        await conn.commit()
    logger.info("db.migrations_done")
    await seed_presets()


async def seed_presets() -> None:
    """Insert default search presets if the table is empty."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) AS cnt FROM search_presets")
            row = await cur.fetchone()
            if row and row["cnt"] > 0:
                return

            presets = [
                {
                    "name": "Florentin Rental",
                    "category": "rent",
                    "city_code": "5000",
                    "min_price": 3000,
                    "max_price": 8000,
                    "min_rooms": 1.0,
                    "max_rooms": 4.0,
                },
                {
                    "name": "Neve Tzedek Rental",
                    "category": "rent",
                    "city_code": "5000",
                    "min_price": 5000,
                    "max_price": 15000,
                    "min_rooms": 1.0,
                    "max_rooms": 5.0,
                },
                {
                    "name": "Lev Ha'ir Rental",
                    "category": "rent",
                    "city_code": "5000",
                    "min_price": 4000,
                    "max_price": 12000,
                    "min_rooms": 1.0,
                    "max_rooms": 4.0,
                },
            ]

            for p in presets:
                await cur.execute(
                    """
                    INSERT INTO search_presets
                        (name, category, city_code, min_price, max_price, min_rooms, max_rooms)
                    VALUES
                        (%(name)s, %(category)s, %(city_code)s,
                         %(min_price)s, %(max_price)s, %(min_rooms)s, %(max_rooms)s)
                    """,
                    p,
                )
        await conn.commit()
    logger.info("db.presets_seeded")


async def check_connection() -> bool:
    """Return True if DB is reachable."""
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
        return True
    except Exception:
        return False
