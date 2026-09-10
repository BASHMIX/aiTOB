TABLE_SCHEMAS = [
    # Additive identity foundation. Existing operational rows are deliberately
    # not workspace-scoped until their ownership migration is separately proven.
    '''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL COLLATE NOCASE UNIQUE,
        display_name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        email_verified_at TIMESTAMP,
        is_platform_admin BOOLEAN NOT NULL DEFAULT FALSE,
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'disabled')),
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS workspaces (
        id TEXT PRIMARY KEY,
        slug TEXT NOT NULL COLLATE NOCASE UNIQUE,
        name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'disabled')),
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS workspace_memberships (
        workspace_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('owner', 'tournament_organizer', 'stream_operator', 'moderator', 'viewer', 'organizer', 'operator')),
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'disabled')),
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(workspace_id, user_id),
        FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS user_sessions (
        id TEXT PRIMARY KEY,
        token_hash TEXT NOT NULL UNIQUE,
        user_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        revoked_at TIMESTAMP,
        last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS user_mfa_credentials (
        user_id TEXT PRIMARY KEY REFERENCES users(id),
        encrypted_totp_secret TEXT NOT NULL,
        enabled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_verified_counter BIGINT,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS user_mfa_setup (
        user_id TEXT PRIMARY KEY REFERENCES users(id),
        session_id TEXT NOT NULL REFERENCES user_sessions(id),
        encrypted_secret TEXT NOT NULL,
        expires_at TIMESTAMP NOT NULL
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS user_recovery_codes (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id),
        code_hash TEXT NOT NULL UNIQUE,
        used_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id),
        token_hash TEXT NOT NULL UNIQUE,
        expires_at TIMESTAMP NOT NULL,
        used_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS email_verification_tokens (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id),
        token_hash TEXT NOT NULL UNIQUE,
        expires_at TIMESTAMP NOT NULL,
        used_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS auth_rate_limits (
        action TEXT NOT NULL,
        subject_hash TEXT NOT NULL,
        window_started_at TIMESTAMP NOT NULL,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(action, subject_hash)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS workspace_invitations (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        email TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('tournament_organizer', 'stream_operator', 'moderator', 'viewer')),
        token_hash TEXT NOT NULL UNIQUE,
        expires_at TIMESTAMP NOT NULL,
        accepted_at TIMESTAMP,
        cancelled_at TIMESTAMP,
        created_by TEXT NOT NULL REFERENCES users(id),
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS workspace_entitlements (
        workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id),
        plan_key TEXT NOT NULL DEFAULT 'free',
        billing_state TEXT NOT NULL DEFAULT 'non_billed',
        limits_json TEXT NOT NULL DEFAULT '{}',
        usage_json TEXT NOT NULL DEFAULT '{}',
        expires_at TIMESTAMP,
        suspended_at TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS audit_events (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        actor_id TEXT,
        action TEXT NOT NULL,
        target_type TEXT,
        target_id TEXT,
        outcome TEXT NOT NULL,
        trace_id TEXT,
        detail_json TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    # Redacted server-side error telemetry.  This is deliberately separate
    # from the audit trail: it contains no request body, provider response, or
    # credential material, and may be retained/queried by operators without
    # exposing user activity details to the browser.
    '''
    CREATE TABLE IF NOT EXISTS error_events (
        id TEXT PRIMARY KEY,
        workspace_id TEXT,
        trace_id TEXT,
        method TEXT NOT NULL,
        path TEXT NOT NULL,
        exception_type TEXT NOT NULL,
        detail_json TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
    )
    ''',
    # Organizer Assistant configuration is service-scoped, not tied to the
    # Discord bot or a tournament provider.  The secret lives in its own
    # authenticated-encryption store; this table is always safe to project to
    # the browser.
    '''
    CREATE TABLE IF NOT EXISTS ai_service_config (
        id INTEGER PRIMARY KEY CHECK(id = 1),
        provider_type TEXT NOT NULL DEFAULT 'gemini' CHECK(provider_type IN ('gemini', 'openai')),
        model TEXT NOT NULL DEFAULT 'gemini-2.5-flash',
        mode TEXT NOT NULL DEFAULT 'disabled' CHECK(mode IN ('disabled', 'read_only', 'propose_only')),
        request_limit INTEGER NOT NULL DEFAULT 30,
        token_limit INTEGER NOT NULL DEFAULT 60000,
        context_char_limit INTEGER NOT NULL DEFAULT 12000,
        response_char_limit INTEGER NOT NULL DEFAULT 4000,
        request_timeout_seconds INTEGER NOT NULL DEFAULT 30,
        policy_version TEXT NOT NULL DEFAULT 'organizer-assistant-v1',
        last_test_status TEXT NOT NULL DEFAULT 'not_tested',
        last_tested_at TIMESTAMP,
        last_test_message TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS ai_service_secrets (
        secret_type TEXT PRIMARY KEY,
        ciphertext TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    # A reservation is written before calling a model, so concurrently-arriving
    # requests cannot evade an hourly request/token budget.  Neither prompts,
    # responses, nor API keys are retained here.
    '''
    CREATE TABLE IF NOT EXISTS ai_usage_ledger (
        id TEXT PRIMARY KEY,
        tournament_slug TEXT NOT NULL,
        provider_type TEXT NOT NULL,
        model TEXT NOT NULL,
        policy_version TEXT NOT NULL,
        period_key TEXT NOT NULL,
        estimated_input_tokens INTEGER NOT NULL,
        response_tokens INTEGER NOT NULL DEFAULT 0,
        outcome TEXT NOT NULL CHECK(outcome IN ('reserved', 'completed', 'failed', 'rejected')),
        proposal_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    )
    ''',
    # Account-scoped integration identities are deliberately separate from legacy
    # global settings. Credential ciphertext is stored separately and never joins
    # into browser/API projections.
    '''
    CREATE TABLE IF NOT EXISTS integration_accounts (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        provider_type TEXT NOT NULL,
        external_account_id TEXT NOT NULL,
        display_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'disabled')),
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(owner_id, provider_type, external_account_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS integration_credentials (
        owner_kind TEXT NOT NULL CHECK(owner_kind IN ('account', 'application')),
        owner_id TEXT NOT NULL,
        secret_type TEXT NOT NULL,
        ciphertext TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(owner_kind, owner_id, secret_type)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS integration_oauth_applications (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        provider_type TEXT NOT NULL,
        client_id TEXT NOT NULL,
        redirect_uri TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'disabled')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(owner_id, provider_type, client_id, redirect_uri)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS integration_destinations (
        id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        destination_type TEXT NOT NULL,
        external_id TEXT NOT NULL,
        display_name TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'disabled')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(account_id, destination_type, external_id),
        FOREIGN KEY(account_id) REFERENCES integration_accounts(id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS integration_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id TEXT,
        action TEXT NOT NULL,
        detail_json TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
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
        name TEXT NOT NULL,
        config TEXT,
        workspace_id TEXT,
        UNIQUE (workspace_id, name)
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
        hidden BOOLEAN DEFAULT FALSE,
        active_match_id TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS media_assets (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        asset_type TEXT NOT NULL,
        owner_type TEXT,
        owner_id TEXT,
        storage_url TEXT NOT NULL,
        storage_key TEXT,
        mime_type TEXT,
        byte_size INTEGER,
        width INTEGER,
        height INTEGER,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        deleted_at TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS overlay_access_tokens (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        station_id TEXT NOT NULL REFERENCES stations(id),
        token_hash TEXT NOT NULL UNIQUE,
        created_by TEXT NOT NULL REFERENCES users(id),
        -- NULL means a station-scoped link that follows the active slide;
        -- a value pins the link to one overlay preset on this station.
        overlay_name TEXT,
        expires_at TIMESTAMP,
        revoked_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
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
        event_id TEXT,
        event_name TEXT,
        station_id TEXT,
        p1_name TEXT, p1_score INTEGER DEFAULT 0,
        p2_name TEXT, p2_score INTEGER DEFAULT 0,
        p1_entrant_id TEXT, p2_entrant_id TEXT,
        p1_avatar TEXT, p2_avatar TEXT,
        p1_discord TEXT, p2_discord TEXT,
        p1_team TEXT, p2_team TEXT,
        p1_country TEXT, p2_country TEXT,
        round_name TEXT,
        -- Provider labels may be nonnumeric (for example a bracket slot "A").
        -- Text preserves the provider key across SQLite and PostgreSQL.
        match_number TEXT,
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
        level TEXT DEFAULT 'info',
        workspace_id TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS hub_commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command_text TEXT,
        source TEXT NOT NULL DEFAULT 'manual',
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
    # Short-lived, single-use OAuth anti-CSRF values. Provider tokens remain in
    # the connections table and states are deleted as soon as they are consumed.
    '''
    CREATE TABLE IF NOT EXISTS oauth_states (
        provider TEXT NOT NULL,
        state TEXT PRIMARY KEY,
        account_id TEXT,
        expires_at INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS player_overrides (
        id TEXT PRIMARY KEY,
        workspace_id TEXT,
        display_name TEXT,
        team TEXT,
        country TEXT,
        cfn TEXT,
        avatar_url TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    # A bracket entrant is scoped to a tournament. This explicit link connects
    # that imported entrant to the durable aiTOB/Discord player profile without
    # treating provider participant IDs as globally stable.
    '''
    CREATE TABLE IF NOT EXISTS tournament_player_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_slug TEXT NOT NULL,
        entrant_id TEXT NOT NULL,
        player_discord_id TEXT NOT NULL,
        workspace_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (workspace_id, tournament_slug, entrant_id),
        FOREIGN KEY (tournament_slug) REFERENCES tournaments(slug),
        FOREIGN KEY (player_discord_id) REFERENCES players(discord_id)
    )
    ''',
    # Provider snapshots let the Hub render a bracket without turning every
    # WebSocket update or page visit into another external API request.
    '''
    CREATE TABLE IF NOT EXISTS provider_bracket_snapshots (
        tournament_slug TEXT PRIMARY KEY,
        sets_json TEXT NOT NULL DEFAULT '[]',
        synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tournament_slug) REFERENCES tournaments(slug)
    )
    ''',
    # Local audit only: no secrets or response bodies.  This is an estimate of
    # provider usage because Challonge does not expose a quota endpoint to V1.
    '''
    CREATE TABLE IF NOT EXISTS provider_api_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_type TEXT NOT NULL,
        method TEXT NOT NULL,
        path TEXT NOT NULL,
        status_code INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    # Provider V2 foundation tables. They are intentionally dark: init_db only
    # creates storage and starts no worker, backfill, or reconciliation action.
    '''
    CREATE TABLE IF NOT EXISTS provider_command_ledger (
        id TEXT PRIMARY KEY,
        tournament_slug TEXT NOT NULL,
        set_id TEXT NOT NULL,
        provider_type TEXT NOT NULL,
        provider_account_id TEXT NOT NULL,
        action TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'pending',
        idempotency_key TEXT NOT NULL,
        payload_digest TEXT NOT NULL,
        expected_result_json TEXT NOT NULL DEFAULT '{}',
        precondition_revision TEXT,
        lease_owner TEXT,
        lease_until TIMESTAMP,
        next_retry_at TIMESTAMP,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        error_message TEXT,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(provider_type, provider_account_id, idempotency_key)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS workflow_outbox (
        event_id TEXT PRIMARY KEY,
        match_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        deduplication_key TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        lease_owner TEXT,
        lease_until TIMESTAMP,
        next_attempt_at TIMESTAMP,
        completed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS provider_reconciliation_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_slug TEXT NOT NULL,
        set_id TEXT,
        provider_type TEXT NOT NULL,
        action TEXT NOT NULL,
        before_hub_status TEXT,
        after_hub_status TEXT,
        provider_state_raw TEXT,
        reason TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS challonge_state_repair_reports (
        report_id TEXT PRIMARY KEY,
        snapshot_id TEXT NOT NULL,
        snapshot_observed_at TIMESTAMP NOT NULL,
        fingerprint TEXT NOT NULL,
        report_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        applied_at TIMESTAMP,
        applied_by TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS provider_identity_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workspace_id TEXT,
        provider_type TEXT NOT NULL,
        provider_participant_id TEXT,
        provider_entrant_id TEXT,
        aitob_participant_id TEXT,
        discord_user_id TEXT,
        discord_role_id TEXT,
        tournament_slug TEXT,
        scope TEXT NOT NULL DEFAULT 'tournament',
        verification_state TEXT NOT NULL DEFAULT 'unverified',
        source TEXT NOT NULL DEFAULT 'imported',
        display_name_snapshot TEXT,
        aliases_json TEXT NOT NULL DEFAULT '[]',
        verified_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS provider_api_budgets (
        provider_type TEXT NOT NULL,
        provider_account_id TEXT NOT NULL,
        window_started_at TIMESTAMP,
        estimated_used INTEGER NOT NULL DEFAULT 0,
        remaining_if_known INTEGER,
        reset_at TIMESTAMP,
        backoff_until TIMESTAMP,
        last_429_at TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (provider_type, provider_account_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS provider_snapshot_cache (
        provider_type TEXT NOT NULL,
        provider_account_id TEXT NOT NULL,
        tournament_slug TEXT NOT NULL,
        scope TEXT NOT NULL,
        entity_coverage_json TEXT NOT NULL DEFAULT '[]',
        revision TEXT,
        etag TEXT,
        last_modified TEXT,
        content_hash TEXT,
        payload_json TEXT NOT NULL DEFAULT '{}',
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (provider_type, provider_account_id, tournament_slug, scope)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS provider_locator_aliases (
        provider_type TEXT NOT NULL,
        provider_account_id TEXT NOT NULL,
        community_id TEXT NOT NULL DEFAULT '',
        locator_key TEXT NOT NULL,
        canonical_tournament_id TEXT NOT NULL,
        tournament_slug TEXT NOT NULL,
        resolved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (provider_type, provider_account_id, community_id, locator_key)
    )
    ''',
    # Read-only provider participant projection.  This is intentionally not a
    # Discord identity link: names are display snapshots only.
    '''
    CREATE TABLE IF NOT EXISTS provider_snapshot_participants (
        provider_type TEXT NOT NULL,
        provider_account_id TEXT NOT NULL,
        tournament_slug TEXT NOT NULL,
        provider_participant_id TEXT NOT NULL,
        display_name TEXT NOT NULL,
        observed_at TIMESTAMP NOT NULL,
        PRIMARY KEY (provider_type, provider_account_id, tournament_slug, provider_participant_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS provider_request_telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_type TEXT NOT NULL,
        provider_account_id TEXT NOT NULL,
        tournament_slug TEXT NOT NULL,
        scope TEXT NOT NULL,
        priority INTEGER NOT NULL,
        disposition TEXT NOT NULL,
        cost_class TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS global_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''',
    # Dispatcher decisions are a compact audit of deterministic policy output.
    # Repeated ticks update the same row rather than flooding the operator feed.
    '''
    CREATE TABLE IF NOT EXISTS dispatcher_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        decision_key TEXT NOT NULL UNIQUE,
        tournament_slug TEXT NOT NULL,
        event_id TEXT NOT NULL DEFAULT '',
        set_id TEXT,
        decision TEXT NOT NULL CHECK(decision IN ('select', 'skip', 'blocked')),
        reason_code TEXT NOT NULL,
        explanation TEXT NOT NULL,
        first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        seen_count INTEGER NOT NULL DEFAULT 1
    )
    ''',
    # Short-lived claims make duplicate dispatcher cycles harmless. A claim is
    # separate from the manual Hub command queue so the kill switch can cancel
    # pending automatic work without touching organizer-initiated commands.
    '''
    CREATE TABLE IF NOT EXISTS dispatcher_dispatch_claims (
        set_id TEXT PRIMARY KEY,
        workspace_id TEXT,
        tournament_slug TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('claimed', 'queued', 'cancelled')),
        claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    # A proposal is a reviewed intent, not an AI command and not an execution.
    # Approval and execution deliberately have separate axes so a successful
    # approval never looks like a delivered Discord message or completed Call.
    '''
    CREATE TABLE IF NOT EXISTS action_proposals (
        id TEXT PRIMARY KEY,
        tournament_slug TEXT NOT NULL,
        match_id TEXT,
        action_type TEXT NOT NULL CHECK(action_type IN ('call', 'announcement_draft')),
        payload_json TEXT NOT NULL DEFAULT '{}',
        reason TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        state_version TEXT NOT NULL,
        state_snapshot_json TEXT NOT NULL DEFAULT '{}',
        approval_status TEXT NOT NULL DEFAULT 'pending'
            CHECK(approval_status IN ('pending', 'approved', 'rejected', 'expired', 'needs_review')),
        execution_status TEXT NOT NULL DEFAULT 'not_started'
            CHECK(execution_status IN ('not_started', 'queued', 'executing', 'workflow_started', 'outbox_queued', 'failed', 'blocked')),
        approved_by TEXT,
        approved_at TIMESTAMP,
        rejected_by TEXT,
        rejected_at TIMESTAMP,
        rejection_reason TEXT,
        command_id INTEGER UNIQUE,
        outbox_event_id TEXT,
        execution_error TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS planned_streams (
        set_id          TEXT PRIMARY KEY,
        tournament_slug TEXT NOT NULL,
        stream_id       TEXT,
        note            TEXT,
        workspace_id    TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    # Bio-code verification pending state. One row per discord_id at most.
    # Used when start.gg OAuth is unavailable: player edits their start.gg
    # bio to include `code`, then runs /verify-confirm which compares.
    '''
    CREATE TABLE IF NOT EXISTS pending_verifications (
        discord_id   TEXT PRIMARY KEY,
        workspace_id TEXT,
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
    "CREATE INDEX IF NOT EXISTS idx_active_matches_status ON active_matches(status)",
    "CREATE INDEX IF NOT EXISTS idx_tournament_player_links_player ON tournament_player_links(player_discord_id)"
    ,"CREATE INDEX IF NOT EXISTS idx_provider_api_usage_month ON provider_api_usage(provider_type, created_at)"
    ,"CREATE INDEX IF NOT EXISTS idx_oauth_states_expiry ON oauth_states(expires_at)"
    ,"CREATE INDEX IF NOT EXISTS idx_provider_command_ledger_due ON provider_command_ledger(state, next_retry_at)"
    ,"CREATE INDEX IF NOT EXISTS idx_workflow_outbox_due ON workflow_outbox(status, next_attempt_at)"
    ,"CREATE INDEX IF NOT EXISTS idx_provider_identity_links_lookup ON provider_identity_links(provider_type, provider_entrant_id, tournament_slug)"
    ,"CREATE INDEX IF NOT EXISTS idx_provider_request_telemetry_lookup ON provider_request_telemetry(provider_type, provider_account_id, created_at)"
    ,"CREATE INDEX IF NOT EXISTS idx_provider_locator_aliases_tournament ON provider_locator_aliases(provider_type, provider_account_id, canonical_tournament_id, community_id)"
    ,"CREATE INDEX IF NOT EXISTS idx_provider_snapshot_participants_tournament ON provider_snapshot_participants(tournament_slug)"
    ,"CREATE INDEX IF NOT EXISTS idx_dispatcher_decisions_scope ON dispatcher_decisions(tournament_slug, event_id, last_seen_at)"
    ,"CREATE INDEX IF NOT EXISTS idx_hub_commands_dispatcher_pending ON hub_commands(source, status, created_at)"
    ,"CREATE INDEX IF NOT EXISTS idx_action_proposals_review ON action_proposals(tournament_slug, approval_status, expires_at)"
    ,"CREATE INDEX IF NOT EXISTS idx_ai_usage_budget ON ai_usage_ledger(period_key, outcome)"
    ,"CREATE INDEX IF NOT EXISTS idx_workspace_memberships_user ON workspace_memberships(user_id, status)"
    ,"CREATE INDEX IF NOT EXISTS idx_media_assets_workspace ON media_assets(workspace_id, deleted_at)"
    ,"CREATE INDEX IF NOT EXISTS idx_user_sessions_lookup ON user_sessions(token_hash, expires_at)"
    ,"CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id, revoked_at)"
    ,"CREATE INDEX IF NOT EXISTS idx_auth_rate_limits_window ON auth_rate_limits(window_started_at)"
    ,"CREATE INDEX IF NOT EXISTS idx_workspace_entitlements_expiry ON workspace_entitlements(expires_at, suspended_at)"
    ,"CREATE INDEX IF NOT EXISTS idx_error_events_created ON error_events(created_at)"
    ,"CREATE UNIQUE INDEX IF NOT EXISTS uq_stations_workspace_public_id ON stations(workspace_id, public_id)"
    ,"CREATE INDEX IF NOT EXISTS idx_overlay_access_station ON overlay_access_tokens(workspace_id, station_id, revoked_at)"
]

# ── Safe migrations (add new columns if missing) ─────────────────
MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMP",
    "ALTER TABLE users ADD COLUMN is_platform_admin BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE workspace_entitlements ADD COLUMN expires_at TIMESTAMP",
    "ALTER TABLE workspace_entitlements ADD COLUMN suspended_at TIMESTAMP",
    # Preparatory ownership migration. These remain nullable until a designated
    # Owner workspace performs and validates the legacy backfill.
    "ALTER TABLE tournaments ADD COLUMN workspace_id TEXT",
    "ALTER TABLE active_matches ADD COLUMN workspace_id TEXT",
    "ALTER TABLE players ADD COLUMN workspace_id TEXT",
    "ALTER TABLE tournament_player_links ADD COLUMN workspace_id TEXT",
    "ALTER TABLE provider_identity_links ADD COLUMN workspace_id TEXT",
    "ALTER TABLE stations ADD COLUMN workspace_id TEXT",
    "ALTER TABLE stations ADD COLUMN public_id TEXT",
    "ALTER TABLE overlays ADD COLUMN workspace_id TEXT",
    "ALTER TABLE integration_accounts ADD COLUMN workspace_id TEXT",
    "ALTER TABLE integration_destinations ADD COLUMN workspace_id TEXT",
    "ALTER TABLE action_proposals ADD COLUMN workspace_id TEXT",
    "ALTER TABLE hub_commands ADD COLUMN workspace_id TEXT",
    "ALTER TABLE hub_commands ADD COLUMN lease_owner TEXT",
    "ALTER TABLE hub_commands ADD COLUMN lease_expires_at TIMESTAMP",
    "ALTER TABLE hub_commands ADD COLUMN attempts INTEGER DEFAULT 0",
    "ALTER TABLE hub_commands ADD COLUMN last_error TEXT",
    "ALTER TABLE workflow_outbox ADD COLUMN workspace_id TEXT",
    "ALTER TABLE provider_command_ledger ADD COLUMN workspace_id TEXT",
    "ALTER TABLE provider_snapshot_cache ADD COLUMN workspace_id TEXT",
    "ALTER TABLE provider_api_budgets ADD COLUMN workspace_id TEXT",
    "ALTER TABLE dispatcher_decisions ADD COLUMN workspace_id TEXT",
    "ALTER TABLE dispatcher_dispatch_claims ADD COLUMN workspace_id TEXT",
    "ALTER TABLE ai_usage_ledger ADD COLUMN workspace_id TEXT",
    "ALTER TABLE provider_api_usage ADD COLUMN workspace_id TEXT",
    "ALTER TABLE provider_api_usage ADD COLUMN provider_account_id TEXT",
    "ALTER TABLE pending_verifications ADD COLUMN workspace_id TEXT",
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
    "ALTER TABLE player_overrides ADD COLUMN workspace_id TEXT",
    "ALTER TABLE planned_streams ADD COLUMN workspace_id TEXT",
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
    # A browser-source link may be station-scoped (NULL, follows active slide)
    # or pinned to one overlay slide. Existing links remain station-scoped.
    "ALTER TABLE overlay_access_tokens ADD COLUMN overlay_name TEXT",
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
    # Default OFF: featured/on-stream matches remain under explicit TO control.
    "ALTER TABLE tournaments ADD COLUMN auto_dispatch_on_stream BOOLEAN DEFAULT 0",
    # TO override for the activity guard — when ON, fetch_sets loads
    # matches even for tournaments/phases that aren't ACTIVE on start.gg.
    "ALTER TABLE tournaments ADD COLUMN ignore_activity_guard BOOLEAN DEFAULT 0",
    # Dual-mode check-in: 'discord' (bot-driven I'm-Ready + auto-DQ) or
    # 'startgg' (markSetCalled → start.gg owns the check-in wave + DQ).
    "ALTER TABLE tournaments ADD COLUMN check_in_source TEXT DEFAULT 'discord'",
    # Provider ownership. Existing rows keep the safe Start.gg default.
    "ALTER TABLE tournaments ADD COLUMN provider_type TEXT DEFAULT 'startgg'",
    "ALTER TABLE tournaments ADD COLUMN provider_tournament_id TEXT",
    "ALTER TABLE tournaments ADD COLUMN provider_subdomain TEXT",
    "ALTER TABLE tournaments ADD COLUMN provider_account_id TEXT",
    "ALTER TABLE tournaments ADD COLUMN discord_account_id TEXT",
    "ALTER TABLE tournaments ADD COLUMN provider_sync_status TEXT DEFAULT 'ready'",
    "ALTER TABLE tournaments ADD COLUMN provider_sync_error TEXT",
    "ALTER TABLE tournaments ADD COLUMN provider_last_synced_at TIMESTAMP",
    "ALTER TABLE tournaments ADD COLUMN challonge_sync_mode TEXT DEFAULT 'economy'",
    "ALTER TABLE tournaments ADD COLUMN economy_sync_on_stale_open BOOLEAN DEFAULT 1",
    # Per-tournament presentation accent. It only affects Hub visuals and is
    # intentionally independent of the provider's own branding.
    "ALTER TABLE tournaments ADD COLUMN accent_color TEXT",
    "ALTER TABLE active_matches ADD COLUMN provider_set_id TEXT",
    "ALTER TABLE active_matches ADD COLUMN provider_state TEXT",
    # V2 state fields are additive only. Phase 2 deliberately does not backfill,
    # reinterpret, or write existing legacy status rows.
    "ALTER TABLE active_matches ADD COLUMN provider_state_raw TEXT",
    "ALTER TABLE active_matches ADD COLUMN provider_state_normalized TEXT",
    "ALTER TABLE active_matches ADD COLUMN provider_revision TEXT",
    "ALTER TABLE active_matches ADD COLUMN provider_observed_at TIMESTAMP",
    "ALTER TABLE active_matches ADD COLUMN hub_status TEXT",
    "ALTER TABLE active_matches ADD COLUMN hub_status_origin TEXT",
    "ALTER TABLE active_matches ADD COLUMN sync_status TEXT",
    "ALTER TABLE active_matches ADD COLUMN sync_reason TEXT",
    "ALTER TABLE active_matches ADD COLUMN last_successful_snapshot_at TIMESTAMP",
    "ALTER TABLE active_matches ADD COLUMN result_kind TEXT",
    "ALTER TABLE active_matches ADD COLUMN call_message_id TEXT",
    "ALTER TABLE active_matches ADD COLUMN thread_id TEXT",
    "ALTER TABLE active_matches ADD COLUMN player1_ready_at TIMESTAMP",
    "ALTER TABLE active_matches ADD COLUMN player2_ready_at TIMESTAMP",
    "ALTER TABLE active_matches ADD COLUMN attendance_deadline TIMESTAMP",
    "ALTER TABLE active_matches ADD COLUMN last_notification_at TIMESTAMP",
    # Local workflow ownership is explicit so completion can never free another
    # match's station after a restart or a repeated reconciliation decision.
    "ALTER TABLE stations ADD COLUMN active_match_id TEXT",
    # Makes a previously deployed dark outbox reclaimable after a crash. New
    # installations receive this through CREATE TABLE; duplicate ALTER is safe.
    "ALTER TABLE workflow_outbox ADD COLUMN lease_until TIMESTAMP",
    "ALTER TABLE workflow_outbox ADD COLUMN lease_owner TEXT",
    "ALTER TABLE workflow_outbox ADD COLUMN effect_started_at TIMESTAMP",
    "ALTER TABLE provider_command_ledger ADD COLUMN lease_owner TEXT",
    # Reachability / Emergency-fallback workflow per match
    "ALTER TABLE active_matches ADD COLUMN auto_dq_disarmed BOOLEAN DEFAULT 0",
    # AI Discord conflict-investigation summary (one-line dispute synopsis)
    "ALTER TABLE conflicts ADD COLUMN ai_summary TEXT",
    "ALTER TABLE hub_commands ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'",
    "ALTER TABLE bot_feed ADD COLUMN workspace_id TEXT",
    # Event scoping — tag each match with its owning event so multi-event
    # tournaments (e.g. Tekken 8 + SF6) don't cross-contaminate the hub.
    "ALTER TABLE active_matches ADD COLUMN event_id TEXT",
    "ALTER TABLE active_matches ADD COLUMN event_name TEXT",
    # Stream-station binding & green-room credentials (commit #7).
    # event_id binds a station to one game so stream matches never cross-route;
    # is_stream_station marks broadcaster setups; room_* hold the lobby creds the
    # bot delivers privately only after both players check in.
    "ALTER TABLE stations ADD COLUMN event_id TEXT",
    "ALTER TABLE stations ADD COLUMN is_stream_station BOOLEAN DEFAULT 0",
    "ALTER TABLE stations ADD COLUMN room_name_or_id TEXT",
    "ALTER TABLE stations ADD COLUMN room_password TEXT",
    "ALTER TABLE oauth_states ADD COLUMN account_id TEXT",
]
