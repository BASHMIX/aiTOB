# Migration and cutover report

Additive migrations create workspace-owned setup, provider binding, Discord,
registration, AI-health, roster and outbox tables. Player `team`/`gamer_tag`
values are backfilled into canonical `prefix`/`gamertag`; legacy aliases remain
inside `legacy_player_adapter.py` for older exports. AI legacy assignment is an
explicit operator script and never copies a secret. Discord/provider accounts
remain quarantined when credentials or workspace ownership are missing.

The final PostgreSQL non-null ownership enforcement is intentionally gated until
the feature-003 backfill is approved. No automatic registration cutover occurs
while that gate is blocked.
