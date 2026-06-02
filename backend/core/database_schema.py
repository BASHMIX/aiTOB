TABLE_SCHEMAS = [
    '''
    CREATE TABLE IF NOT EXISTS players (
        discord_id TEXT PRIMARY KEY,
        startgg_id TEXT,
        gamer_tag TEXT,
        cfn_id TEXT,
        country TEXT,
        team TEXT,
        avatar_path TEXT,
        is_verified BOOLEAN DEFAULT FALSE,
        registration_step TEXT DEFAULT 'startgg_linked',
        preferred_language TEXT DEFAULT 'ar'
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS overlays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        config TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS tournaments (
        slug TEXT PRIMARY KEY,
        name TEXT,
        event_name TEXT,
        event_id TEXT,
        game TEXT,
        stream_slot TEXT,
        raw_data TEXT,
        dq_timer_seconds INTEGER DEFAULT 600,
        auto_dq_enabled BOOLEAN DEFAULT TRUE,
        bot_manage_limit TEXT DEFAULT 'off',
        bot_manage_finish TEXT DEFAULT 'off',
        registration_deadline TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS match_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        set_id TEXT,
        tournament_slug TEXT,
        stream_slot TEXT,
        p1_name TEXT,
        p2_name TEXT,
        winner TEXT,
        p1_score TEXT,
        p2_score TEXT,
        round_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    # ── New tables for the FNC Hub ──────────────────────────────────
    '''
    CREATE TABLE IF NOT EXISTS stations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        hidden BOOLEAN DEFAULT FALSE
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS station_overlays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_id TEXT NOT NULL,
        overlay_name TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0,
        FOREIGN KEY (station_id) REFERENCES stations(id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS active_matches (
        set_id TEXT PRIMARY KEY,
        tournament_slug TEXT,
        station_id TEXT,
        p1_name TEXT, p1_score INTEGER DEFAULT 0,
        p2_name TEXT, p2_score INTEGER DEFAULT 0,
        p1_entrant_id TEXT, p2_entrant_id TEXT,
        p1_avatar TEXT, p2_avatar TEXT,
        p1_discord TEXT, p2_discord TEXT,
        p1_team TEXT, p2_team TEXT,
        p1_country TEXT, p2_country TEXT,
        round_name TEXT,
        match_number INTEGER,
        swapped BOOLEAN DEFAULT FALSE,
        bot_enabled BOOLEAN DEFAULT TRUE,
        status TEXT DEFAULT 'not_started',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS conflicts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        set_id TEXT,
        p1_claim TEXT,
        p2_claim TEXT,
        resolved BOOLEAN DEFAULT FALSE,
        resolution TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS bot_feed (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        message TEXT,
        level TEXT DEFAULT 'info'
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS hub_commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command_text TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS connections (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS player_overrides (
        id TEXT PRIMARY KEY,
        display_name TEXT,
        team TEXT,
        country TEXT,
        cfn TEXT,
        avatar_url TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS global_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS planned_streams (
        set_id          TEXT PRIMARY KEY,
        tournament_slug TEXT NOT NULL,
        stream_id       TEXT,
        note            TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    # Bio-code verification pending state. One row per discord_id at most.
    # Used when start.gg OAuth is unavailable: player edits their start.gg
    # bio to include `code`, then runs /verify-confirm which compares.
    '''
    CREATE TABLE IF NOT EXISTS pending_verifications (
        discord_id   TEXT PRIMARY KEY,
        startgg_slug TEXT NOT NULL,
        code         TEXT NOT NULL,
        expires_at   TIMESTAMP NOT NULL,
        attempts     INTEGER DEFAULT 0,
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    '''
]

# Indexes for the hottest active_matches filters (tournament_slug, status).
# IF NOT EXISTS → idempotent; speeds up list / poll / OBS-telemetry reads.
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_active_matches_tournament_slug ON active_matches(tournament_slug)",
    "CREATE INDEX IF NOT EXISTS idx_active_matches_status ON active_matches(status)"
]

# ── Safe migrations (add new columns if missing) ─────────────────
MIGRATIONS = [
    # active_matches new columns
    "ALTER TABLE active_matches ADD COLUMN is_stream_match BOOLEAN DEFAULT FALSE",
    "ALTER TABLE active_matches ADD COLUMN called_at TIMESTAMP",
    "ALTER TABLE active_matches ADD COLUMN started_at TIMESTAMP",
    "ALTER TABLE active_matches ADD COLUMN p1_cfn TEXT",
    "ALTER TABLE active_matches ADD COLUMN p2_cfn TEXT",
    "ALTER TABLE active_matches ADD COLUMN p1_ready BOOLEAN DEFAULT FALSE",
    "ALTER TABLE active_matches ADD COLUMN p2_ready BOOLEAN DEFAULT FALSE",
    "ALTER TABLE active_matches ADD COLUMN dq_player TEXT",
    "ALTER TABLE active_matches ADD COLUMN phase_group TEXT DEFAULT ''",
    "ALTER TABLE player_overrides ADD COLUMN avatar_url TEXT",
    # tournaments new columns
    "ALTER TABLE tournaments ADD COLUMN dq_timer_seconds INTEGER DEFAULT 600",
    "ALTER TABLE tournaments ADD COLUMN auto_dq_enabled BOOLEAN DEFAULT TRUE",
    # players new columns
    "ALTER TABLE players ADD COLUMN preferred_language TEXT DEFAULT 'ar'",
    "ALTER TABLE players ADD COLUMN registration_step TEXT DEFAULT 'startgg_linked'",
    # tournaments new columns
    "ALTER TABLE tournaments ADD COLUMN registration_deadline TIMESTAMP",
    "ALTER TABLE active_matches ADD COLUMN p1_avatar TEXT",
    "ALTER TABLE active_matches ADD COLUMN p2_avatar TEXT",
    "ALTER TABLE active_matches ADD COLUMN lobby_password TEXT",
    "ALTER TABLE active_matches ADD COLUMN discord_thread_id TEXT",
    "ALTER TABLE tournaments ADD COLUMN bot_manage_limit TEXT DEFAULT 'off'",
    "ALTER TABLE tournaments ADD COLUMN bot_manage_finish TEXT DEFAULT 'off'",
    # stations new columns
    "ALTER TABLE stations ADD COLUMN active_overlay TEXT",
    # start.gg stream queue support — maps local station to a provider stream
    "ALTER TABLE stations ADD COLUMN startgg_stream_id TEXT",
    # cached provider stream list per tournament (JSON: [{id,name,source,game}])
    "ALTER TABLE tournaments ADD COLUMN streams_json TEXT",
    # Station gear-modal fields
    "ALTER TABLE stations ADD COLUMN stream_url TEXT",                # optional override for display URL
    "ALTER TABLE stations ADD COLUMN bot_enabled BOOLEAN DEFAULT 1", # default for matches on this station
    "ALTER TABLE stations ADD COLUMN hidden BOOLEAN DEFAULT 0",      # ensure column exists (was only in CREATE TABLE)
    # Auto-dispatcher (per-tournament; defaults OFF so existing tournaments are unaffected)
    "ALTER TABLE tournaments ADD COLUMN auto_dispatch_enabled BOOLEAN DEFAULT 0",
    "ALTER TABLE tournaments ADD COLUMN auto_dispatch_concurrency INTEGER DEFAULT 1",
    "ALTER TABLE tournaments ADD COLUMN auto_dispatch_stop_at INTEGER DEFAULT 8",
    # TO override for the activity guard — when ON, fetch_sets loads
    # matches even for tournaments/phases that aren't ACTIVE on start.gg.
    "ALTER TABLE tournaments ADD COLUMN ignore_activity_guard BOOLEAN DEFAULT 0",
    # Reachability / Emergency-fallback workflow per match
    "ALTER TABLE active_matches ADD COLUMN auto_dq_disarmed BOOLEAN DEFAULT 0",
    # AI Discord conflict-investigation summary (one-line dispute synopsis)
    "ALTER TABLE conflicts ADD COLUMN ai_summary TEXT",
]
