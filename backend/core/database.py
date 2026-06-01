import aiosqlite
import os
import json
from typing import Optional
from backend.core.contracts.tournament_types import ProviderSet, ProviderSetState, ProviderEntrant

DB_PATH = os.getenv("DB_PATH", "backend/core/database.sqlite")

async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
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
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS overlays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                config TEXT
            )
        ''')
        await db.execute('''
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
        ''')
        await db.execute('''
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
        ''')
        # ── New tables for the FNC Hub ──────────────────────────────────
        await db.execute('''
            CREATE TABLE IF NOT EXISTS stations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                hidden BOOLEAN DEFAULT FALSE
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS station_overlays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id TEXT NOT NULL,
                overlay_name TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (station_id) REFERENCES stations(id)
            )
        ''')
        await db.execute('''
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
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS conflicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_id TEXT,
                p1_claim TEXT,
                p2_claim TEXT,
                resolved BOOLEAN DEFAULT FALSE,
                resolution TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS bot_feed (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                message TEXT,
                level TEXT DEFAULT 'info'
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS hub_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_text TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS connections (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS player_overrides (
                id TEXT PRIMARY KEY,
                display_name TEXT,
                team TEXT,
                country TEXT,
                cfn TEXT,
                avatar_url TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS global_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS planned_streams (
                set_id          TEXT PRIMARY KEY,
                tournament_slug TEXT NOT NULL,
                stream_id       TEXT,
                note            TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Bio-code verification pending state. One row per discord_id at most.
        # Used when start.gg OAuth is unavailable: player edits their start.gg
        # bio to include `code`, then runs /verify-confirm which compares.
        await db.execute('''
            CREATE TABLE IF NOT EXISTS pending_verifications (
                discord_id   TEXT PRIMARY KEY,
                startgg_slug TEXT NOT NULL,
                code         TEXT NOT NULL,
                expires_at   TIMESTAMP NOT NULL,
                attempts     INTEGER DEFAULT 0,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Indexes for the hottest active_matches filters (tournament_slug, status).
        # IF NOT EXISTS → idempotent; speeds up list / poll / OBS-telemetry reads.
        await db.execute("CREATE INDEX IF NOT EXISTS idx_active_matches_tournament_slug ON active_matches(tournament_slug)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_active_matches_status ON active_matches(status)")
        # ── Safe migrations (add new columns if missing) ─────────────────
        migrations = [
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
        for m in migrations:
            try:
                await db.execute(m)
                await db.commit()
            except Exception:
                pass  # Column already exists

        # One-shot cleanup: purge any "preview_*" rows that earlier builds
        # inserted into active_matches before we filtered them out at sync
        # time. Preview sets are unresolved bracket placeholders that can't
        # be mutated on start.gg, so they have no business in the actionable
        # list. Idempotent — no-ops on a clean DB.
        await db.execute("DELETE FROM active_matches WHERE set_id LIKE 'preview%'")
        await db.commit()

        # Seed default stations if empty
        async with db.execute("SELECT COUNT(*) FROM stations") as c:
            count = (await c.fetchone())[0]
        if count == 0:
            await db.execute("INSERT INTO stations (id, name) VALUES ('station_1', 'Station 1')")
            await db.execute("INSERT INTO stations (id, name) VALUES ('station_2', 'Station 2')")
        await db.commit()

# ── Players ────────────────────────────────────────────────────────────────
async def create_or_update_player(discord_id: str, **kwargs):
    if not kwargs:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT discord_id FROM players WHERE discord_id = ?", (discord_id,)) as cursor:
            exists = await cursor.fetchone()
        if not exists:
            columns = ['discord_id'] + list(kwargs.keys())
            placeholders = ['?'] * len(columns)
            values = [discord_id] + list(kwargs.values())
            query = f"INSERT INTO players ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            await db.execute(query, values)
        else:
            set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values()) + [discord_id]
            query = f"UPDATE players SET {set_clause} WHERE discord_id = ?"
            await db.execute(query, values)
        await db.commit()

async def get_player(discord_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM players WHERE discord_id = ?", (discord_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

# ── Overlays ───────────────────────────────────────────────────────────────
async def save_overlay(name: str, config: str):
    if not isinstance(config, str):
        try:
            config = json.dumps(config)
        except Exception as e:
            print(f"Error serializing overlay config: {e}")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO overlays (name, config) VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET config = excluded.config
        ''', (name, config))
        await db.commit()

async def get_overlays():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM overlays") as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def delete_overlay(name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM overlays WHERE name = ?", (name,))
        await db.commit()

# ── Tournaments ────────────────────────────────────────────────────────────
async def upsert_tournament(slug: str, name: str, event_name: str, event_id: str, game: str, raw_data: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO tournaments (slug, name, event_name, event_id, game, raw_data)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name=excluded.name, event_name=excluded.event_name,
                event_id=excluded.event_id, game=excluded.game, raw_data=excluded.raw_data
        ''', (slug, name, event_name, event_id, game, raw_data))
        await db.commit()

async def update_tournament_settings(slug: str, **kwargs):
    if not kwargs:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [slug]
        await db.execute(f"UPDATE tournaments SET {set_clause} WHERE slug = ?", values)
        if "bot_manage_limit" in kwargs:
            limit_setting = kwargs["bot_manage_limit"]
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT set_id, round_name, phase_group FROM active_matches WHERE tournament_slug = ?", (slug,)) as cursor:
                rows = [dict(r) for r in await cursor.fetchall()]
            update_data = []
            for r in rows:
                bot_enabled = should_bot_manage_match(r["round_name"], r["phase_group"], limit_setting)
                update_data.append((bot_enabled, r["set_id"]))
            if update_data:
                await db.executemany("UPDATE active_matches SET bot_enabled = ? WHERE set_id = ?", update_data)
        await db.commit()

async def get_tournaments():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tournaments ORDER BY created_at DESC") as cursor:
            return [dict(r) for r in await cursor.fetchall()]

async def get_tournament(slug: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tournaments WHERE slug = ?", (slug,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def delete_tournament(slug: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tournaments WHERE slug = ?", (slug,))
        await db.commit()


async def set_tournament_streams(slug: str, streams: list):
    """Persist the start.gg stream list for a tournament as JSON.

    `streams` is a list of dicts with keys: id, name, source, game.
    """
    payload = json.dumps(streams or [])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tournaments SET streams_json = ? WHERE slug = ?", (payload, slug))
        await db.commit()


async def get_tournament_streams(slug: str) -> list:
    """Return the cached start.gg stream list for a tournament."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT streams_json FROM tournaments WHERE slug = ?", (slug,)) as cursor:
            row = await cursor.fetchone()
    if not row or not row[0]:
        return []
    try:
        return json.loads(row[0])
    except Exception:
        return []


async def get_station_stream_id(station_id: str) -> str | None:
    """Return the start.gg streamId mapped to a local station, or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT startgg_stream_id FROM stations WHERE id = ?", (station_id,)) as cursor:
            row = await cursor.fetchone()
    return (row[0] if row else None) or None


async def get_station_by_stream_id(stream_id: str) -> dict | None:
    """Find the local station mapped to a given start.gg streamId, or None."""
    if not stream_id:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM stations WHERE startgg_stream_id = ? LIMIT 1", (stream_id,)) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


# ── Planned Streams ──────────────────────────────────────────────────────
async def add_planned_stream(set_id: str, tournament_slug: str,
                             stream_id: str | None = None, note: str | None = None):
    """Mark a (potentially preview) set for inclusion on stream once it goes live."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO planned_streams (set_id, tournament_slug, stream_id, note)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(set_id) DO UPDATE SET
                tournament_slug=excluded.tournament_slug,
                stream_id=excluded.stream_id,
                note=excluded.note
        ''', (set_id, tournament_slug, stream_id, note))
        await db.commit()


async def remove_planned_stream(set_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM planned_streams WHERE set_id = ?", (set_id,))
        await db.commit()


async def list_planned_streams(tournament_slug: str | None = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if tournament_slug:
            q = "SELECT * FROM planned_streams WHERE tournament_slug = ? ORDER BY created_at DESC"
            args: tuple = (tournament_slug,)
        else:
            q = "SELECT * FROM planned_streams ORDER BY created_at DESC"
            args = ()
        async with db.execute(q, args) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_planned_stream(set_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM planned_streams WHERE set_id = ?", (set_id,)) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


# ── Pending Bio-Code Verifications ──────────────────────────────────────
import datetime as _dt


async def create_pending_verification(discord_id: str, startgg_slug: str,
                                       code: str, ttl_seconds: int = 300):
    """Create or replace a pending bio-code verification for this Discord user."""
    expires = (_dt.datetime.utcnow() + _dt.timedelta(seconds=ttl_seconds)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO pending_verifications (discord_id, startgg_slug, code, expires_at, attempts) "
            "VALUES (?, ?, ?, ?, 0) "
            "ON CONFLICT(discord_id) DO UPDATE SET "
            "  startgg_slug=excluded.startgg_slug, code=excluded.code, "
            "  expires_at=excluded.expires_at, attempts=0, created_at=CURRENT_TIMESTAMP",
            (discord_id, startgg_slug, code, expires)
        )
        await db.commit()


async def get_pending_verification(discord_id: str) -> dict | None:
    """Return the pending verification, or None if missing/expired."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM pending_verifications WHERE discord_id = ?",
            (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        expires = _dt.datetime.fromisoformat(d["expires_at"])
        if _dt.datetime.utcnow() > expires:
            return None
    except Exception:
        return None
    return d


async def increment_verification_attempts(discord_id: str) -> int:
    """Increment attempts counter; return new value. Used to rate-limit retries."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE pending_verifications SET attempts = attempts + 1 WHERE discord_id = ?",
            (discord_id,)
        )
        await db.commit()
        async with db.execute(
            "SELECT attempts FROM pending_verifications WHERE discord_id = ?",
            (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def delete_pending_verification(discord_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM pending_verifications WHERE discord_id = ?", (discord_id,))
        await db.commit()

# ── Match Results ──────────────────────────────────────────────────────────
async def save_match_result(set_id: str, tournament_slug: str, stream_slot: str,
                            p1_name: str, p2_name: str, winner: str,
                            p1_score: str, p2_score: str, round_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO match_results
                (set_id, tournament_slug, stream_slot, p1_name, p2_name, winner, p1_score, p2_score, round_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (set_id, tournament_slug, stream_slot, p1_name, p2_name, winner, p1_score, p2_score, round_name))
        await db.commit()

async def get_match_results(tournament_slug: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if tournament_slug:
            async with db.execute("SELECT * FROM match_results WHERE tournament_slug = ? ORDER BY created_at DESC", (tournament_slug,)) as cursor:
                return [dict(r) for r in await cursor.fetchall()]
        async with db.execute("SELECT * FROM match_results ORDER BY created_at DESC LIMIT 100") as cursor:
            return [dict(r) for r in await cursor.fetchall()]

# ── Stations ───────────────────────────────────────────────────────────────
async def get_stations():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM stations ORDER BY id") as cursor:
            return [dict(r) for r in await cursor.fetchall()]

async def create_station(station_id: str, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO stations (id, name) VALUES (?, ?)", (station_id, name))
        await db.commit()

async def update_station(station_id: str, **kwargs):
    if not kwargs:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [station_id]
        await db.execute(f"UPDATE stations SET {set_clause} WHERE id = ?", values)
        await db.commit()

async def update_station_active_overlay(station_id: str, overlay_name: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE stations SET active_overlay = ? WHERE id = ?", (overlay_name, station_id))
        await db.commit()

async def get_station_active_overlay(station_id: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT active_overlay FROM stations WHERE id = ?", (station_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def delete_station(station_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM station_overlays WHERE station_id = ?", (station_id,))
        await db.execute("DELETE FROM stations WHERE id = ?", (station_id,))
        await db.commit()

# ── Station Overlays ───────────────────────────────────────────────────────
async def get_station_overlays(station_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM station_overlays WHERE station_id = ? ORDER BY sort_order",
            (station_id,)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]

async def add_station_overlay(station_id: str, overlay_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT MAX(sort_order) FROM station_overlays WHERE station_id = ?", (station_id,)
        ) as c:
            row = await c.fetchone()
            next_order = (row[0] or 0) + 1
        await db.execute(
            "INSERT INTO station_overlays (station_id, overlay_name, sort_order) VALUES (?, ?, ?)",
            (station_id, overlay_name, next_order)
        )
        await db.commit()

async def remove_station_overlay(station_id: str, overlay_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM station_overlays WHERE station_id = ? AND overlay_name = ?",
            (station_id, overlay_name)
        )
        await db.commit()

# ── Active Matches ─────────────────────────────────────────────────────────
async def assign_station_to_active_match(set_id: str, station_id: str) -> bool:
    """Fast update of station_id for an existing active match."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "UPDATE active_matches SET station_id = ? WHERE set_id = ?",
            (station_id, set_id)
        ) as cursor:
            await db.commit()
            return cursor.rowcount > 0

async def get_used_station_ids(exclude_set_id: str) -> set[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT station_id
            FROM active_matches
            WHERE station_id IS NOT NULL
              AND status IN ('not_started', 'called', 'in_progress')
              AND set_id != ?
            """,
            (exclude_set_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}

async def get_active_matches(tournament_slug: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if tournament_slug:
            async with db.execute(
                "SELECT * FROM active_matches WHERE tournament_slug = ? ORDER BY created_at",
                (tournament_slug,)
            ) as cursor:
                return [dict(r) for r in await cursor.fetchall()]
        async with db.execute("SELECT * FROM active_matches ORDER BY created_at") as cursor:
            return [dict(r) for r in await cursor.fetchall()]

async def get_active_match(set_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM active_matches WHERE set_id = ?", (set_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_match_occupying_station(station_id: str, exclude_set_id: str = None) -> dict | None:
    query = """
        SELECT * FROM active_matches 
        WHERE station_id = ? 
          AND status IN ('not_started', 'called', 'in_progress')
    """
    params = [station_id]
    if exclude_set_id:
        query += " AND set_id != ?"
        params.append(exclude_set_id)
        
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def upsert_active_match(set_id: str, **kwargs):
    async with aiosqlite.connect(DB_PATH) as db:
        # Get valid columns
        valid_cols = []
        async with db.execute("PRAGMA table_info(active_matches)") as cursor:
            info = await cursor.fetchall()
            valid_cols = [row[1] for row in info]
        
        # Filter kwargs
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_cols}
        
        existing = None
        async with db.execute("SELECT set_id FROM active_matches WHERE set_id = ?", (set_id,)) as c:
            existing = await c.fetchone()

        if existing:
            if filtered_kwargs:
                set_clause = ', '.join([f'"{k}" = ?' for k in filtered_kwargs.keys()])
                values = list(filtered_kwargs.values()) + [set_id]
                await db.execute(f'UPDATE active_matches SET {set_clause} WHERE set_id = ?', values)
        else:
            filtered_kwargs['set_id'] = set_id
            cols = ', '.join([f'"{k}"' for k in filtered_kwargs.keys()])
            placeholders = ', '.join(['?'] * len(filtered_kwargs))
            await db.execute(f"INSERT INTO active_matches ({cols}) VALUES ({placeholders})", list(filtered_kwargs.values()))
        await db.commit()

async def delete_active_match(set_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM active_matches WHERE set_id = ?", (set_id,))
        await db.commit()


# ── Start.gg ActivityState integer → local status ────────────────────────────────
# Canonical state mapping from ProviderSetState to local DB status
_PROVIDER_STATE_TO_LOCAL = {
    ProviderSetState.NOT_STARTED:  'not_started',
    ProviderSetState.CALLED:       'called',
    ProviderSetState.IN_PROGRESS:  'in_progress',
    ProviderSetState.COMPLETE:     'complete',
    ProviderSetState.QUEUED:       'not_started',
}

_TERMINAL_STATES = {ProviderSetState.COMPLETE}
_AUTO_ADD_STATES = {
    ProviderSetState.NOT_STARTED,
    ProviderSetState.IN_PROGRESS,
    ProviderSetState.CALLED,
    ProviderSetState.QUEUED,
}


async def sync_active_matches(tournament_slug: str, provider_sets: list[ProviderSet]):
    """
    Synchronizes local active_matches with provider-agnostic ProviderSet objects.
    Source of Truth: provider — provider complete state always wins for terminal states.
    Hub-only metadata (station, is_stream_match, scores) is preserved.
    Also promotes planned-stream entries: sets in planned_streams get
    is_stream_match=TRUE and (if a stream_id is set) a matching station assigned.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT bot_manage_limit FROM tournaments WHERE slug = ?", (tournament_slug,)) as t_cursor:
            t_row = await t_cursor.fetchone()
            bot_manage_limit = t_row[0] if t_row else "off"

        async with db.execute("SELECT set_id, status FROM active_matches WHERE tournament_slug = ?", (tournament_slug,)) as cursor:
            rows = await cursor.fetchall()
            local_matches = {row[0]: row[1] for row in rows}

        # Preload planned-stream wishlist for this tournament: {set_id: stream_id_or_None}
        async with db.execute(
            "SELECT set_id, stream_id FROM planned_streams WHERE tournament_slug = ?",
            (tournament_slug,)
        ) as cursor:
            planned = {row[0]: row[1] for row in await cursor.fetchall()}

        # Preload station-by-stream map for fast lookup during promotion.
        async with db.execute(
            "SELECT id, startgg_stream_id FROM stations WHERE startgg_stream_id IS NOT NULL AND startgg_stream_id != ''"
        ) as cursor:
            station_by_stream = {row[1]: row[0] for row in await cursor.fetchall()}

        # Preload startgg_id → discord_id map so we can fill p1_discord/p2_discord
        # at sync time. Without this, the Reachability Check is always "unreachable"
        # because the lookup only fires inside create_match_thread, which is too late
        # for the dispatcher's pre-call gating logic.
        async with db.execute(
            "SELECT startgg_id, discord_id FROM players WHERE startgg_id IS NOT NULL AND startgg_id != ''"
        ) as cursor:
            discord_by_startgg = {str(row[0]): str(row[1]) for row in await cursor.fetchall()}

        def _resolve_discord(entrant: Optional[ProviderEntrant]) -> Optional[str]:
            uid = entrant.user_id if entrant else None
            return discord_by_startgg.get(str(uid)) if uid else None

        found_sids = set()

        for ps in provider_sets:
            sid = ps.id
            found_sids.add(sid)

            # Skip INVALID (bye/DQ sets)
            if ps.state == ProviderSetState.INVALID:
                continue

            # Skip start.gg preview sets — IDs like "preview_xxxxx" reference
            # unresolved bracket placeholders that can't be mutated. Tracking
            # them in active_matches leads to actionable UI cards that fail at
            # send/call time. They remain visible in the bracket view because
            # that data comes from provider.fetch_sets directly, not from here.
            if str(sid).startswith("preview"):
                continue

            p1_name  = ps.entrant1.name if ps.entrant1 else "TBD"
            p2_name  = ps.entrant2.name if ps.entrant2 else "TBD"
            p1_avatar = ps.entrant1.avatar_url if ps.entrant1 else None
            p2_avatar = ps.entrant2.avatar_url if ps.entrant2 else None
            p1_eid   = ps.entrant1.id if ps.entrant1 else None
            p2_eid   = ps.entrant2.id if ps.entrant2 else None
            round_name  = ps.round_name
            match_num   = ps.identifier
            phase_group = ps.phase_group

            provider_status = _PROVIDER_STATE_TO_LOCAL.get(ps.state)

            if sid in local_matches:
                local_status = local_matches[sid]
                # Determine new status:
                # • If provider says COMPLETE → always sync (source of truth)
                # • If provider says NOT_STARTED and local was complete/dq → reset scenario
                # • If local is not_started, upgrade to provider_status
                if ps.state in _TERMINAL_STATES:
                    new_status = 'complete'
                elif ps.state == ProviderSetState.NOT_STARTED and local_status in ('complete', 'dq'):
                    new_status = 'not_started'
                elif provider_status and local_status == 'not_started':
                    new_status = provider_status
                else:
                    new_status = local_status  # keep hub-managed state

                # Resolve discord IDs from current player table on every sync.
                # COALESCE keeps an existing value (e.g. set by a later OAuth) but
                # backfills the column the moment a player verifies.
                p1_discord = _resolve_discord(ps.entrant1)
                p2_discord = _resolve_discord(ps.entrant2)
                await db.execute("""
                    UPDATE active_matches SET
                        p1_name=?, p2_name=?, p1_avatar=?, p2_avatar=?,
                        p1_entrant_id=COALESCE(NULLIF(p1_entrant_id,''), ?),
                        p2_entrant_id=COALESCE(NULLIF(p2_entrant_id,''), ?),
                        p1_discord=COALESCE(NULLIF(p1_discord,''), ?),
                        p2_discord=COALESCE(NULLIF(p2_discord,''), ?),
                        round_name=?, match_number=?, phase_group=?, status=?
                    WHERE set_id=?
                """, (p1_name, p2_name, p1_avatar, p2_avatar,
                       p1_eid, p2_eid,
                       p1_discord, p2_discord,
                       round_name, match_num, str(phase_group), new_status, sid))
                # Promote planned-stream membership onto already-tracked sets too.
                # (Don't downgrade — if a planned set was unplanned, the user can toggle
                #  the active match's stream flag directly via /toggle-stream.)
                if sid in planned:
                    preferred_stream = planned.get(sid)
                    if preferred_stream and preferred_stream in station_by_stream:
                        await db.execute(
                            "UPDATE active_matches SET is_stream_match = 1, "
                            "station_id = COALESCE(station_id, ?) WHERE set_id = ?",
                            (station_by_stream[preferred_stream], sid)
                        )
                    else:
                        await db.execute(
                            "UPDATE active_matches SET is_stream_match = 1 WHERE set_id = ?",
                            (sid,)
                        )
            else:
                # Auto-add matches that provider has put in an active state.
                # Also auto-add planned-stream sets even if not yet in an auto-add state
                # so the operator's pre-planned wishlist appears as soon as it resolves.
                should_add = ps.state in _AUTO_ADD_STATES or sid in planned
                if should_add:
                    new_status = _PROVIDER_STATE_TO_LOCAL.get(ps.state, 'not_started')
                    bot_enabled = should_bot_manage_match(round_name, str(phase_group), bot_manage_limit)
                    # Promote from planned_streams: flag for stream + pick preferred station.
                    is_stream = 1 if sid in planned else 0
                    station_id = None
                    if is_stream:
                        preferred_stream = planned.get(sid)
                        if preferred_stream and preferred_stream in station_by_stream:
                            station_id = station_by_stream[preferred_stream]
                    p1_discord = _resolve_discord(ps.entrant1)
                    p2_discord = _resolve_discord(ps.entrant2)
                    await db.execute("""
                        INSERT INTO active_matches (
                            set_id, tournament_slug, p1_name, p2_name, p1_avatar, p2_avatar,
                            p1_entrant_id, p2_entrant_id, p1_discord, p2_discord,
                            round_name, match_number, phase_group,
                            status, bot_enabled, is_stream_match, station_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (sid, tournament_slug, p1_name, p2_name, p1_avatar, p2_avatar,
                           p1_eid, p2_eid, p1_discord, p2_discord,
                           round_name, match_num, str(phase_group),
                           new_status, bot_enabled, is_stream, station_id))

        # Remove orphans — since provider.fetch_sets retrieves all paginated sets, orphan list is complete
        for sid in list(local_matches.keys()):
            if sid not in found_sids:
                # Orphan: set no longer in provider bracket — remove from hub
                await db.execute("DELETE FROM active_matches WHERE set_id = ?", (sid,))

        await db.commit()

async def delete_tournament_active_matches(slug: str):
    """Wipes all local active matches for a specific tournament."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM active_matches WHERE tournament_slug = ?", (slug,))
        await db.commit()

async def delete_active_match(set_id: str):
    """Deletes a single active match from the local database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM active_matches WHERE set_id = ?", (set_id,))
        await db.commit()


async def update_active_match(match_id: str, **kwargs):
    if not kwargs:
        return

    # Check if status is being updated and validate it
    if "status" in kwargs:
        new_status = kwargs["status"]
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT status FROM active_matches WHERE set_id = ?", (match_id,)) as c:
                    row = await c.fetchone()
                    if row:
                        old_status = row["status"]
                        if old_status and old_status != new_status:
                            from backend.core.match_state import validate_transition
                            if not validate_transition(old_status, new_status):
                                await add_bot_feed(
                                    f"⚠️ Non-standard transition detected: {old_status} ➔ {new_status} for match {match_id}",
                                    "warn"
                                )
        except Exception as e:
            print(f"Error validating status transition: {e}")

    keys = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values())
    values.append(match_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE active_matches SET {keys} WHERE set_id = ?", values)
        await db.commit()

async def get_player_override(entrant_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM player_overrides WHERE id = ?", (entrant_id,)) as c:
            row = await c.fetchone()
            if row:
                return dict(zip([col[0] for col in c.description], row))
            return None

async def save_player_override(entrant_id: str, data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        # First, ensure the row exists
        await db.execute("INSERT OR IGNORE INTO player_overrides (id) VALUES (?)", (entrant_id,))
        await db.commit()
        
        # Build the update query dynamically
        fields = []
        params = []
        mapping = {
            "name": "display_name",
            "team": "team",
            "country": "country",
            "cfn": "cfn",
            "avatar_url": "avatar_url"
        }
        for key, col in mapping.items():
            if key in data and data[key] is not None:
                fields.append(f"{col} = ?")
                params.append(data[key])
        
        if fields:
            params.append(entrant_id)
            await db.execute(f"UPDATE player_overrides SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", params)
            await db.commit()

async def get_all_player_overrides():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM player_overrides") as c:
            rows = await c.fetchall()
            out = {}
            for row in rows:
                d = dict(zip([col[0] for col in c.description], row))
                # Map database column names back to frontend property names
                out[d.get('id', '')] = {
                    "name": d.get('display_name'),
                    "team": d.get('team'),
                    "country": d.get('country'),
                    "cfn": d.get('cfn'),
                    "avatar_url": d.get('avatar_url')
                }
            return out

async def delete_player_override(entrant_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM player_overrides WHERE id = ?", (entrant_id,))
        await db.commit()

async def delete_all_player_overrides():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM player_overrides")
        await db.commit()

# ── Connections ────────────────────────────────────────────────────────────
async def get_connection(key: str, default: str = None) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM connections WHERE key = ?", (key,)) as c:
            row = await c.fetchone()
            return row[0] if row else default

async def set_connection(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO connections (key, value) VALUES (?, ?)", (key, value))
        await db.commit()

async def get_all_connections() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key, value FROM connections") as c:
            rows = await c.fetchall()
            return {r[0]: r[1] for r in rows}

async def get_setting(key: str, default: str = None) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM global_settings WHERE key = ?", (key,)) as c:
            row = await c.fetchone()
            return row[0] if row else default

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES (?, ?)", (key, value))
        await db.commit()

async def get_all_settings() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key, value FROM global_settings") as c:
            rows = await c.fetchall()
            return {r[0]: r[1] for r in rows}


# ── Conflicts ──────────────────────────────────────────────────────────────
async def add_conflict(set_id: str, p1_claim: str, p2_claim: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conflicts (set_id, p1_claim, p2_claim) VALUES (?, ?, ?)",
            (set_id, p1_claim, p2_claim)
        )
        await db.commit()

async def get_conflicts(resolved: bool = False):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM conflicts WHERE resolved = ? ORDER BY created_at DESC",
            (resolved,)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]

async def get_conflict(conflict_id: int):
    """Fetch a single conflict row (incl. its set_id) for score-based resolution."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM conflicts WHERE id = ?", (conflict_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_conflict_by_set_id(set_id: str, resolved: bool = False):
    """Most recent (un)resolved conflict for a set — used by the Discord investigation."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM conflicts WHERE set_id = ? AND resolved = ? ORDER BY id DESC LIMIT 1",
            (str(set_id), resolved),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def update_conflict_claim(conflict_id: int, slot: str, text: str):
    """Store a player's investigation statement (slot is 'p1' or 'p2')."""
    col = "p1_claim" if slot == "p1" else "p2_claim"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE conflicts SET {col} = ? WHERE id = ?", (text, conflict_id)
        )
        await db.commit()

async def update_conflict_summary(conflict_id: int, summary: str):
    """Store the AI-generated one-line dispute summary."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE conflicts SET ai_summary = ? WHERE id = ?", (summary, conflict_id)
        )
        await db.commit()

async def resolve_conflict(conflict_id: int, resolution: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE conflicts SET resolved = TRUE, resolution = ? WHERE id = ?",
            (resolution, conflict_id)
        )
        await db.commit()

# ── Bot Feed ───────────────────────────────────────────────────────────────
async def add_bot_feed(message: str, level: str = "info"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bot_feed (message, level) VALUES (?, ?)",
            (message, level)
        )
        # Keep only the last 200 entries
        await db.execute('''
            DELETE FROM bot_feed WHERE id NOT IN (
                SELECT id FROM bot_feed ORDER BY id DESC LIMIT 200
            )
        ''')
        await db.commit()

async def get_bot_feed(limit: int = 50, offset: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM bot_feed ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def clear_bot_feed():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM bot_feed")
        await db.commit()

# ── Hub Commands ───────────────────────────────────────────────────────────
async def add_hub_command(command_text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO hub_commands (command_text, status) VALUES (?, 'pending')",
            (command_text,)
        )
        await db.commit()

async def get_pending_hub_commands():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM hub_commands WHERE status = 'pending' ORDER BY created_at ASC"
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]
async def purge_incomplete_registrations(tournament_slug: str):
    """
    Deletes players who haven't completed registration after the deadline.
    For simplicity, this deletes all is_verified=FALSE players.
    In a real scenario, you'd filter by tournament participation too.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM players WHERE is_verified = FALSE")
        await db.commit()

async def update_hub_command_status(command_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE hub_commands SET status = ? WHERE id = ?",
            (status, command_id)
        )
        await db.commit()


# ── Auto-Dispatcher Queries ──────────────────────────────────────────────
async def get_dispatch_eligible_tournaments() -> list[dict]:
    """Tournaments with the auto-dispatcher armed."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT slug, name, auto_dispatch_concurrency, auto_dispatch_stop_at "
            "FROM tournaments WHERE auto_dispatch_enabled = 1"
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def count_active_dispatched(tournament_slug: str) -> int:
    """Currently-occupying-time matches the dispatcher has on the wire.
    Counts called + in_progress matches that are bot-managed for the tournament."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM active_matches "
            "WHERE tournament_slug = ? AND bot_enabled = 1 AND status IN ('called', 'in_progress')",
            (tournament_slug,)
        ) as cursor:
            row = await cursor.fetchone()
    return int(row[0] if row else 0)


async def count_remaining_event_matches(tournament_slug: str) -> int:
    """Total uncompleted matches the dispatcher knows about for the tournament.
    Includes TBD/unresolved sets so a Top-8 threshold isn't tripped prematurely
    by pool matches still being resolved."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM active_matches "
            "WHERE tournament_slug = ? AND status NOT IN ('complete', 'dq')",
            (tournament_slug,)
        ) as cursor:
            row = await cursor.fetchone()
    return int(row[0] if row else 0)


async def get_dispatch_candidates(tournament_slug: str, limit: int) -> list[dict]:
    """Find the next bot-managed matches that are safe to auto-call.

    Excludes:
      - matches with TBD/missing entrants (upstream bracket unresolved)
      - matches that are already planned for stream (those wait for the TO / featured queue)
      - anything already called or in progress (those are counted toward concurrency)
    Orders by phase_group then match_number for predictable pool progression.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM active_matches
            WHERE tournament_slug = ?
              AND status = 'not_started'
              AND bot_enabled = 1
              AND p1_entrant_id IS NOT NULL AND p1_entrant_id != ''
              AND p2_entrant_id IS NOT NULL AND p2_entrant_id != ''
              AND p1_name IS NOT NULL AND p1_name != '' AND p1_name != 'TBD'
              AND p2_name IS NOT NULL AND p2_name != '' AND p2_name != 'TBD'
              AND set_id NOT IN (
                SELECT set_id FROM planned_streams WHERE tournament_slug = ?
              )
            ORDER BY
              COALESCE(NULLIF(phase_group, ''), 'zzzz'),
              COALESCE(match_number, 999999),
              created_at
            LIMIT ?
            """,
            (tournament_slug, tournament_slug, int(limit))
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]

def should_bot_manage_match(round_name: str, phase_group: str, limit_setting: str) -> bool:
    if not limit_setting or limit_setting == "off":
        return False
    if limit_setting == "all" or limit_setting == "on":
        return True
        
    round_lower = (round_name or "").lower()
    phase_lower = (phase_group or "").lower()
    limit_lower = (limit_setting or "").lower()
    
    if limit_lower == "top8":
        is_top8 = "top 8" in phase_lower or "top8" in phase_lower or "final" in round_lower or "semi" in round_lower or "quarter" in round_lower
        return not is_top8
        
    if limit_lower == "top16":
        is_top16 = "top 16" in phase_lower or "top16" in phase_lower or "top 8" in phase_lower or "top8" in phase_lower or "final" in round_lower or "semi" in round_lower or "quarter" in round_lower
        return not is_top16
        
    if limit_lower in phase_lower:
        return True
        
    return True

async def get_player_in_progress_match(discord_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM active_matches WHERE status = 'in_progress' AND (p1_discord = ? OR p2_discord = ?)",
            (discord_id, discord_id)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
