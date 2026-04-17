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
        max_size=15,
        kwargs={"row_factory": dict_row},
        open=False,
        # Bumped to 15s to absorb concurrent VM ingest pipelines (Yad2 + FB) running
        # alongside the Madlan scheduled scan. With max_size=15 we have headroom on
        # Neon (free tier supports 100 concurrent connections).
        timeout=15.0,
        # Neon pauses idle connections after ~5 min; without liveness checks the pool
        # hands out dead sockets and the caller sees `SSL connection closed unexpectedly`.
        check=AsyncConnectionPool.check_connection,
        max_idle=240.0,
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
                    signal_details  JSONB DEFAULT '{}',
                    updated_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_classifications_class ON property_classifications(classification)"
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
                CREATE TABLE IF NOT EXISTS favorites (
                    id              SERIAL PRIMARY KEY,
                    property_id     INTEGER NOT NULL UNIQUE REFERENCES properties(id),
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
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # Add yad2_date_added column if not present
            await cur.execute(
                "ALTER TABLE properties ADD COLUMN IF NOT EXISTS yad2_date_added TIMESTAMPTZ"
            )

            # Backfill yad2_date_added from raw_data for existing properties
            await cur.execute("""
                UPDATE properties
                SET yad2_date_added = (raw_data->>'date_added')::timestamptz,
                    days_on_market = CURRENT_DATE - (raw_data->>'date_added')::date
                WHERE raw_data->>'date_added' IS NOT NULL
                AND yad2_date_added IS NULL
            """)

            # Add new enrichment columns
            for col_def in [
                "source TEXT DEFAULT 'yad2'",
                "latitude REAL",
                "longitude REAL",
                "parking BOOLEAN",
                "elevator BOOLEAN",
                "safe_room BOOLEAN",
                "renovated BOOLEAN",
                "balcony BOOLEAN",
                "pets_allowed BOOLEAN",
                "furnished BOOLEAN",
                "air_conditioning BOOLEAN",
                "is_agent BOOLEAN",
                "agent_office TEXT",
                "move_in_date DATE",
                "hood_id INTEGER",
                "customer_id TEXT",
                "accessibility BOOLEAN",
            ]:
                await cur.execute(f"ALTER TABLE properties ADD COLUMN IF NOT EXISTS {col_def}")

            # Backfill enrichment columns from raw_data for existing properties
            await cur.execute("""
                UPDATE properties SET
                    source = 'yad2',
                    latitude = (raw_data->'coordinates'->>'latitude')::real,
                    longitude = (raw_data->'coordinates'->>'longitude')::real,
                    parking = COALESCE(raw_data->>'Parking_text', '') != '',
                    elevator = COALESCE(raw_data->>'Elevator_text', '') != '',
                    safe_room = COALESCE(raw_data->>'mamad_text', '') != '',
                    renovated = COALESCE(raw_data->>'Meshupatz_text', '') != '',
                    balcony = COALESCE(raw_data->>'Porch_text', '') != '' AND COALESCE(raw_data->>'Porch_text', '') != 'אין',
                    pets_allowed = COALESCE(raw_data->>'PetsInHouse_text', '') != '',
                    furnished = COALESCE(raw_data->>'Furniture_text', '') != '',
                    air_conditioning = COALESCE(raw_data->>'AirConditioner_text', '') != '',
                    is_agent = COALESCE((raw_data->>'merchant')::boolean, false),
                    agent_office = raw_data->>'merchant_name',
                    move_in_date = CASE WHEN raw_data->>'date_of_entry' IS NOT NULL AND raw_data->>'date_of_entry' != ''
                                   THEN (raw_data->>'date_of_entry')::date ELSE NULL END,
                    hood_id = (raw_data->>'hood_id')::integer,
                    customer_id = raw_data->>'customer_id',
                    accessibility = COALESCE(raw_data->>'handicapped_text', '') != ''
                WHERE source IS NULL
                  AND yad2_id NOT LIKE 'fb_%'
                  AND yad2_id NOT LIKE 'madlan_%'
            """)
            rowcount = cur.rowcount
            if rowcount and rowcount > 0:
                logger.warning("db.migration_updated_rows", count=rowcount)

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS property_operator_input (
                    id              SERIAL PRIMARY KEY,
                    property_id     INTEGER NOT NULL UNIQUE REFERENCES properties(id),
                    agent_name      TEXT,
                    manual_days_on_market INTEGER,
                    flexibility     TEXT,
                    condition       TEXT,
                    updated_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_preset_stats_session ON scan_preset_stats(session_id)"
            )

            # Add address_home_number column
            await cur.execute(
                "ALTER TABLE properties ADD COLUMN IF NOT EXISTS address_home_number TEXT"
            )

            # Backfill address_home_number from raw_data
            await cur.execute("""
                UPDATE properties SET address_home_number = raw_data->>'address_home_number'
                WHERE address_home_number IS NULL AND raw_data->>'address_home_number' IS NOT NULL
            """)

            # Add square_meter_build column — actual indoor area (vs total including balcony/roof)
            await cur.execute(
                "ALTER TABLE properties ADD COLUMN IF NOT EXISTS square_meter_build INTEGER"
            )

            # Amit Fit: buyer threshold table per neighborhood/size bucket
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS neighborhood_thresholds (
                    id                               SERIAL PRIMARY KEY,
                    neighborhood                     TEXT NOT NULL,
                    hood_id                          INTEGER,
                    category                         TEXT NOT NULL DEFAULT 'forsale',
                    size_min                         INTEGER NOT NULL,
                    size_max                         INTEGER NOT NULL,
                    target_price_per_sqm_preferred   INTEGER NOT NULL,
                    target_price_per_sqm_max         INTEGER NOT NULL,
                    created_at                       TIMESTAMPTZ DEFAULT NOW(),
                    updated_at                       TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT neighborhood_thresholds_unique
                      UNIQUE (neighborhood, size_min, size_max, category),
                    CONSTRAINT neighborhood_thresholds_valid_size
                      CHECK (size_min >= 0 AND size_max > size_min),
                    CONSTRAINT neighborhood_thresholds_valid_targets
                      CHECK (target_price_per_sqm_preferred > 0 AND target_price_per_sqm_max >= target_price_per_sqm_preferred),
                    CONSTRAINT neighborhood_thresholds_valid_category
                      CHECK (category IN ('forsale', 'rent'))
                )
            """)
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_neighborhood_thresholds_lookup
                  ON neighborhood_thresholds(neighborhood, hood_id, category)
            """)

            # Building metadata: cached year_built per normalized address
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS building_metadata (
                    id                  SERIAL PRIMARY KEY,
                    city_norm           TEXT NOT NULL,
                    street_norm         TEXT NOT NULL,
                    house_number_norm   TEXT NOT NULL,
                    year_built          INTEGER,
                    source              TEXT NOT NULL,
                    confidence          REAL DEFAULT 1.0,
                    raw_lat             REAL,
                    raw_lon             REAL,
                    created_at          TIMESTAMPTZ DEFAULT NOW(),
                    updated_at          TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT building_metadata_unique_addr
                      UNIQUE (city_norm, street_norm, house_number_norm),
                    CONSTRAINT building_metadata_year_sane
                      CHECK (year_built IS NULL OR (year_built >= 1850 AND year_built <= 2050)),
                    CONSTRAINT building_metadata_source_valid
                      CHECK (source IN ('tlv_municipality', 'madlan_cache', 'manual'))
                )
            """)
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_building_metadata_lookup
                  ON building_metadata(city_norm, street_norm, house_number_norm)
            """)
            await cur.execute("""
                ALTER TABLE properties ADD COLUMN IF NOT EXISTS year_built INTEGER
            """)

            # Phase 2B-1: Per-neighborhood feature adjustments (year, floor, parking, mamad)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS neighborhood_feature_adjustments (
                    id                          SERIAL PRIMARY KEY,
                    neighborhood                TEXT NOT NULL,
                    hood_id                     INTEGER,
                    category                    TEXT NOT NULL DEFAULT 'forsale',
                    year_old_pref_pct           NUMERIC(5,2) NOT NULL DEFAULT -18,
                    year_old_max_pct            NUMERIC(5,2) NOT NULL DEFAULT -18,
                    year_mid_old_pref_pct       NUMERIC(5,2) NOT NULL DEFAULT -8,
                    year_mid_old_max_pct        NUMERIC(5,2) NOT NULL DEFAULT -8,
                    year_mid_pref_pct           NUMERIC(5,2) NOT NULL DEFAULT 0,
                    year_mid_max_pct            NUMERIC(5,2) NOT NULL DEFAULT 0,
                    year_new_pref_pct           NUMERIC(5,2) NOT NULL DEFAULT 5,
                    year_new_max_pct            NUMERIC(5,2) NOT NULL DEFAULT 5,
                    walkup_pct_per_floor        NUMERIC(4,2) NOT NULL DEFAULT 3,
                    parking_bonus_pref          INTEGER NOT NULL DEFAULT 0,
                    parking_bonus_max           INTEGER NOT NULL DEFAULT 0,
                    mamad_pct_pref              NUMERIC(5,2) NOT NULL DEFAULT 0,
                    mamad_pct_max               NUMERIC(5,2) NOT NULL DEFAULT 0,
                    created_at                  TIMESTAMPTZ DEFAULT NOW(),
                    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT nfa_unique UNIQUE (neighborhood, category),
                    CONSTRAINT nfa_valid_category CHECK (category IN ('forsale', 'rent')),
                    CONSTRAINT nfa_walkup_range CHECK (walkup_pct_per_floor >= 0 AND walkup_pct_per_floor <= 10),
                    CONSTRAINT nfa_year_old_order CHECK (year_old_max_pct >= year_old_pref_pct),
                    CONSTRAINT nfa_year_mid_old_order CHECK (year_mid_old_max_pct >= year_mid_old_pref_pct),
                    CONSTRAINT nfa_year_mid_order CHECK (year_mid_max_pct >= year_mid_pref_pct),
                    CONSTRAINT nfa_year_new_order CHECK (year_new_max_pct >= year_new_pref_pct),
                    CONSTRAINT nfa_parking_order CHECK (parking_bonus_max >= parking_bonus_pref),
                    CONSTRAINT nfa_mamad_order CHECK (mamad_pct_max >= mamad_pct_pref)
                )
            """)
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_nfa_lookup
                  ON neighborhood_feature_adjustments(neighborhood, hood_id, category)
            """)

            # Add FB columns to properties
            for col_def in ["author_name TEXT", "group_url TEXT", "like_count INTEGER"]:
                await cur.execute(f"ALTER TABLE properties ADD COLUMN IF NOT EXISTS {col_def}")

            # Enrich properties with gush/parcel
            for col_def in ["gush_num INTEGER", "parcel_num INTEGER", "sub_parcel_num INTEGER"]:
                await cur.execute(f"ALTER TABLE properties ADD COLUMN IF NOT EXISTS {col_def}")
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_properties_gush_parcel
                  ON properties(gush_num, parcel_num)
            """)

            # New closed_transactions table
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS closed_transactions (
                    deal_id          TEXT PRIMARY KEY,
                    polygon_id       TEXT NOT NULL,
                    gush_num         INTEGER,
                    parcel_num       INTEGER,
                    sub_parcel_num   INTEGER,
                    settlement       TEXT,
                    neighborhood     TEXT,
                    street           TEXT,
                    house_number     TEXT,
                    floor            INTEGER,
                    rooms            REAL,
                    sqm              INTEGER,
                    sale_price       BIGINT NOT NULL,
                    deal_date        DATE NOT NULL,
                    year_built       INTEGER,
                    shape_wkt        TEXT,
                    centroid_lat     DOUBLE PRECISION,
                    centroid_lng     DOUBLE PRECISION,
                    price_per_sqm    INTEGER GENERATED ALWAYS AS
                                         (CASE WHEN sqm > 0 THEN (sale_price / sqm)::INTEGER END) STORED,
                    source           TEXT NOT NULL DEFAULT 'govmap',
                    raw_data         JSONB,
                    imported_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_closed_tx_gush_parcel
                  ON closed_transactions(gush_num, parcel_num)
            """)
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_closed_tx_centroid
                  ON closed_transactions(centroid_lat, centroid_lng)
            """)
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_closed_tx_hood_date
                  ON closed_transactions(neighborhood, deal_date DESC)
            """)
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_closed_tx_date
                  ON closed_transactions(deal_date DESC)
            """)
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_closed_tx_polygon
                  ON closed_transactions(polygon_id)
            """)

            # Ingest state singleton table (tracks per-source health counters)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS ingest_state (
                    source TEXT PRIMARY KEY,
                    warning_count INTEGER NOT NULL DEFAULT 0,
                    last_ok_at TIMESTAMPTZ,
                    last_check_at TIMESTAMPTZ
                )
            """)
            await cur.execute("INSERT INTO ingest_state (source) VALUES ('facebook') ON CONFLICT (source) DO NOTHING")

            # Add progress column to scan_sessions for live progress bar
            await cur.execute(
                "ALTER TABLE scan_sessions ADD COLUMN IF NOT EXISTS progress INTEGER DEFAULT 0"
            )

            # Yad2 phone fetch: cooldown bookkeeping for the per-listing customer endpoint
            await cur.execute(
                "ALTER TABLE properties ADD COLUMN IF NOT EXISTS phone_fetch_attempted_at TIMESTAMPTZ"
            )

            # Cleanup migrations — idempotent, removes stale columns/indexes
            await cur.execute("DROP INDEX IF EXISTS idx_classifications_score")
            await cur.execute("ALTER TABLE property_classifications DROP COLUMN IF EXISTS distress_score")
            await cur.execute("ALTER TABLE scan_preset_stats DROP COLUMN IF EXISTS opportunities")

            # A2: Seed fb_groups array per preset — one-shot, idempotent.
            # GUARDED: only populates presets where fb_groups is NULL or empty.
            # Never overwrites Alan's manual curation via the admin UI.
            await cur.execute("""
                UPDATE search_presets sp
                   SET extra_params = COALESCE(sp.extra_params, '{}'::jsonb)
                                   || jsonb_build_object(
                                          'fb_groups',
                                          COALESCE(
                                              (SELECT jsonb_agg(g.group_id ORDER BY g.group_id)
                                                 FROM fb_groups g
                                                WHERE g.is_active = TRUE),
                                              '[]'::jsonb
                                          )
                                      )
                 WHERE sp.is_active = TRUE
                   AND COALESCE(sp.extra_params->>'source', 'yad2') IN ('yad2', 'facebook')
                   AND (sp.extra_params->'fb_groups' IS NULL
                        OR sp.extra_params->'fb_groups' = '[]'::jsonb)
            """)

        await conn.commit()
    logger.info("db.migrations_done")
    await seed_presets()


async def seed_presets() -> None:
    """Insert default search presets if the table is empty. Always seeds FB preset idempotently."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) AS cnt FROM search_presets")
            row = await cur.fetchone()

            if not (row and row["cnt"] > 0):
                presets = [
                    {
                        "name": "TLV Rent - Golden",
                        "category": "rent",
                        "city_code": "5000",
                        "neighborhood": "848,205,1483,1461,204,1519,1516,1520,1521",
                        "min_price": None,
                        "max_price": None,
                        "min_rooms": None,
                        "max_rooms": None,
                    },
                    {
                        "name": "TLV Rent - Full Scan",
                        "category": "rent",
                        "city_code": "5000",
                        "neighborhood": None,
                        "min_price": None,
                        "max_price": None,
                        "min_rooms": None,
                        "max_rooms": None,
                    },
                    {
                        "name": "Haifa Buy",
                        "category": "forsale",
                        "city_code": "4000",
                        "neighborhood": None,
                        "min_price": None,
                        "max_price": None,
                        "min_rooms": None,
                        "max_rooms": None,
                    },
                ]

                for p in presets:
                    await cur.execute(
                        """
                        INSERT INTO search_presets
                            (name, category, city_code, neighborhood, min_price, max_price, min_rooms, max_rooms)
                        VALUES
                            (%(name)s, %(category)s, %(city_code)s, %(neighborhood)s,
                             %(min_price)s, %(max_price)s, %(min_rooms)s, %(max_rooms)s)
                        """,
                        p,
                    )

            # Idempotent FB seed (runs every startup, regardless of table emptiness)
            await cur.execute(
                "SELECT id FROM search_presets WHERE extra_params->>'source' = 'facebook' LIMIT 1"
            )
            existing_fb = await cur.fetchone()
            if not existing_fb:
                await cur.execute(
                    """INSERT INTO search_presets (name, category, city_code, extra_params)
                       VALUES ('TLV Rent - Facebook', 'rent', '5000', '{"source": "facebook"}'::jsonb)"""
                )

            # FB groups table — no seed data, populated via scripts/seed_fb_groups.py
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS fb_groups (
                    id              SERIAL PRIMARY KEY,
                    group_id        TEXT NOT NULL UNIQUE,
                    name            TEXT NOT NULL,
                    url             TEXT NOT NULL,
                    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
                    discovered_at   TIMESTAMPTZ DEFAULT NOW(),
                    last_seen_at    TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_fb_groups_is_active ON fb_groups(is_active)"
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
