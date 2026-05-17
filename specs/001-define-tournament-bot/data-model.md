# Data Model: AI Tournament Organizer Platform

**Date**: 2026-05-16
**Feature**: `001-define-tournament-bot`

## Entity Relationship Diagram

```mermaid
erDiagram
    PLAYER ||--o{ ACTIVE_MATCH : "participates in"
    TOURNAMENT ||--o{ ACTIVE_MATCH : "contains"
    TOURNAMENT ||--o{ MATCH_RESULT : "archives"
    ACTIVE_MATCH ||--o| CONFLICT : "may have"
    STATION ||--o{ ACTIVE_MATCH : "hosts"
    STATION ||--o{ STATION_OVERLAY : "displays"
    OVERLAY ||--o{ STATION_OVERLAY : "used by"

    PLAYER {
        TEXT discord_id PK
        TEXT startgg_id
        TEXT gamer_tag
        TEXT cfn_id
        TEXT country
        TEXT team
        TEXT avatar_path
        BOOLEAN is_verified
        TEXT preferred_language
    }

    TOURNAMENT {
        TEXT slug PK
        TEXT name
        TEXT event_name
        TEXT event_id
        TEXT game
        TEXT stream_slot
        TEXT raw_data
        INTEGER dq_timer_seconds
        BOOLEAN auto_dq_enabled
        TIMESTAMP created_at
    }

    ACTIVE_MATCH {
        TEXT set_id PK
        TEXT tournament_slug FK
        TEXT station_id FK
        TEXT p1_name
        TEXT p2_name
        INTEGER p1_score
        INTEGER p2_score
        TEXT p1_entrant_id
        TEXT p2_entrant_id
        TEXT p1_discord
        TEXT p2_discord
        TEXT p1_team
        TEXT p2_team
        TEXT p1_country
        TEXT p2_country
        TEXT p1_cfn
        TEXT p2_cfn
        BOOLEAN p1_ready
        BOOLEAN p2_ready
        TEXT round_name
        INTEGER match_number
        BOOLEAN swapped
        BOOLEAN bot_enabled
        BOOLEAN is_stream_match
        TEXT status
        TEXT dq_player
        TEXT phase_group
        TIMESTAMP called_at
        TIMESTAMP started_at
        TIMESTAMP created_at
    }

    MATCH_RESULT {
        INTEGER id PK
        TEXT set_id
        TEXT tournament_slug
        TEXT stream_slot
        TEXT p1_name
        TEXT p2_name
        TEXT winner
        TEXT p1_score
        TEXT p2_score
        TEXT round_name
        TIMESTAMP created_at
    }

    CONFLICT {
        INTEGER id PK
        TEXT set_id FK
        TEXT p1_claim
        TEXT p2_claim
        BOOLEAN resolved
        TEXT resolution
        TIMESTAMP created_at
    }

    STATION {
        TEXT id PK
        TEXT name
        BOOLEAN hidden
    }

    STATION_OVERLAY {
        INTEGER id PK
        TEXT station_id FK
        TEXT overlay_name FK
        INTEGER sort_order
    }

    OVERLAY {
        INTEGER id PK
        TEXT name UK
        TEXT config
    }

    BOT_FEED {
        INTEGER id PK
        TIMESTAMP timestamp
        TEXT message
        TEXT level
    }

    HUB_COMMAND {
        INTEGER id PK
        TEXT command_text
        TEXT status
        TIMESTAMP created_at
    }

    CONNECTION {
        TEXT key PK
        TEXT value
    }

    GLOBAL_SETTING {
        TEXT key PK
        TEXT value
    }

    PLAYER_OVERRIDE {
        TEXT id PK
        TEXT display_name
        TEXT team
        TEXT country
        TEXT cfn
        TEXT avatar_url
        TIMESTAMP updated_at
    }
```

## State Transitions

### Match (ACTIVE_MATCH.status)

```mermaid
stateDiagram-v2
    [*] --> not_started : Match created from Start.gg
    not_started --> called : Admin clicks "Call" / auto-call
    called --> in_progress : Both players ready-check confirmed
    called --> dq : Ready-check timeout (single player)
    called --> dq : Ready-check timeout (both players - double DQ)
    in_progress --> complete : AI referee verifies agreed scores
    in_progress --> conflict : AI referee detects score mismatch
    conflict --> complete : Admin resolves conflict (force score)
    conflict --> dq : Admin DQs a player
    complete --> [*] : Archived to match_results
    dq --> [*] : Archived to match_results
    complete --> not_started : Admin reopens match
```

### Player Registration (PLAYER.is_verified)

```mermaid
stateDiagram-v2
    [*] --> pending : Player clicks Register in Discord
    pending --> startgg_linked : Start.gg OAuth / manual link
    startgg_linked --> language_set : Language selection (AR/EN)
    language_set --> cfn_provided : CFN ID submitted
    cfn_provided --> avatar_uploaded : Avatar passes quality + safety checks
    avatar_uploaded --> verified : All steps complete (is_verified = TRUE)
    cfn_provided --> cfn_provided : Avatar fails checks (retry)
    pending --> purged : Event registration deadline passes
    startgg_linked --> purged : Event registration deadline passes
    language_set --> purged : Event registration deadline passes
    cfn_provided --> purged : Event registration deadline passes
```

## Validation Rules

| Entity | Field | Rule |
|--------|-------|------|
| Player | discord_id | Required, unique, TEXT primary key |
| Player | startgg_id | Optional until verified, unique when set |
| Player | cfn_id | Required for verified players |
| Player | avatar_path | Must pass dimension check (min 100x100px) and AI safety scan |
| Player | preferred_language | Must be 'ar' or 'en', default 'ar' |
| Tournament | slug | Required, unique, TEXT primary key |
| Tournament | dq_timer_seconds | Default 600 (10 min), configurable per event |
| Active Match | set_id | Required, unique, from Start.gg |
| Active Match | status | One of: not_started, called, in_progress, complete, conflict, dq |
| Active Match | p1_score, p2_score | Non-negative integers, default 0 |
| Conflict | set_id | Must reference an existing active match |
| Bot Feed | level | One of: info, warn, error |
| Overlay | name | Required, unique |
| Overlay | config | JSON string with element positions, sizes, styles |
