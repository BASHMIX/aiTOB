# Data Model: AI Tournament Organizer

## Entities

### Player
| Field | Type | Description |
|-------|------|-------------|
| discord_id | TEXT PK | Discord user ID |
| startgg_id | TEXT | Start.gg player ID |
| gamer_tag | TEXT | Display name |
| cfn_id | TEXT | Capcom Fighters Network ID |
| country | TEXT | Player country |
| team | TEXT | Team tag |
| avatar_path | TEXT | Avatar file path |
| is_verified | BOOLEAN | Registration verified flag |
| registration_step | TEXT | Current step in registration flow (startgg_linked, language_set, cfn_provided, avatar_uploaded, complete) |
| preferred_language | TEXT | "ar" or "en" |

**Relationships**: Referenced by `active_matches.p1_entrant_id` / `p2_entrant_id`

---

### ActiveMatch
| Field | Type | Description |
|-------|------|-------------|
| set_id | TEXT PK | Start.gg set ID |
| p1_name | TEXT | Player 1 display name |
| p2_name | TEXT | Player 2 display name |
| p1_entrant_id | TEXT | Player 1 Start.gg entrant ID |
| p2_entrant_id | TEXT | Player 2 Start.gg entrant ID |
| p1_avatar | TEXT | Player 1 avatar URL |
| p2_avatar | TEXT | Player 2 avatar URL |
| round_name | TEXT | Round label (Winners Final, Grands, etc.) |
| tournament_slug | TEXT | Start.gg tournament slug |
| match_number | TEXT | Bracket match identifier |
| status | TEXT | not_started \| called \| in_progress \| complete \| done \| dq |
| p1_score | INTEGER | Player 1 reported score |
| p2_score | INTEGER | Player 2 reported score |
| phase_group | TEXT | Pool/phase group name |
| station_id | TEXT | Assigned station FK |
| is_stream_match | BOOLEAN | Flagged for stream queue |
| started_at | TEXT | ISO timestamp of first in_progress |
| called_at | TEXT | ISO timestamp of last called |
| created_at | TEXT | Creation timestamp |
| updated_at | TEXT | Last update timestamp |

**State transitions**: not_started → called → in_progress → complete | done | dq

---

### Tournament
| Field | Type | Description |
|-------|------|-------------|
| slug | TEXT PK | Start.gg tournament slug |
| name | TEXT | Display name |
| api_endpoint | TEXT | API endpoint (default: https://api.start.gg/gql/alpha) |
| auto_dq_enabled | BOOLEAN | Auto-DQ timer enabled (default: true) |
| dq_timer_seconds | INTEGER | Seconds before auto-DQ (default: 600) |

---

### Station
| Field | Type | Description |
|-------|------|-------------|
| id | TEXT PK | Station identifier |
| name | TEXT | Display name |

---

### StationOverlay
| Field | Type | Description |
|-------|------|-------------|
| station_id | TEXT PK FK | Station identifier |
| overlay_name | TEXT PK FK | Overlay config name |

---

### Overlay
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PK AUTO | Auto-increment ID |
| name | TEXT UNIQUE | Overlay name |
| config | TEXT (JSON) | Element positions/sizes/styles |

---

### MatchResult
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PK AUTO | Auto-increment ID |
| set_id | TEXT | Start.gg set ID |
| tournament_slug | TEXT | Tournament slug |
| winner_id | TEXT | Winning entrant ID |
| p1_score | INTEGER | Player 1 final score |
| p2_score | INTEGER | Player 2 final score |
| reported_by | TEXT | Who reported the result |
| reported_at | TEXT | ISO timestamp |

---

### Conflict
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PK AUTO | Auto-increment ID |
| set_id | TEXT | Start.gg set ID |
| tournament_slug | TEXT | Tournament slug |
| p1_claimed_score | TEXT | Player 1's claimed score |
| p2_claimed_score | TEXT | Player 2's claimed score |
| status | TEXT | open \| resolved |
| resolved_by | TEXT | Admin who resolved it |
| resolved_at | TEXT | ISO timestamp of resolution |

---

### BotFeed
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PK AUTO | Auto-increment ID |
| event_type | TEXT | Notification type |
| message | TEXT | Event description |
| set_id | TEXT | Related set ID |
| tournament_slug | TEXT | Related tournament |
| created_at | TEXT | ISO timestamp |

---

### HubCommand
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PK AUTO | Auto-increment ID |
| command | TEXT | Command text |
| status | TEXT | pending \| executing \| done \| failed |
| result | TEXT (JSON) | Command result |
| created_at | TEXT | ISO timestamp |
| executed_at | TEXT | ISO timestamp |

---

### GlobalSetting
| Field | Type | Description |
|-------|------|-------------|
| key | TEXT PK | Setting key |
| value | TEXT | Setting value |

---

### Connection
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PK AUTO | Auto-increment ID |
| type | TEXT | Connection type (startgg, discord) |
| token | TEXT | Encrypted/plain token |
| label | TEXT | Display label |
| is_active | BOOLEAN | Active status |

---

### PlayerOverride
| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PK AUTO | Auto-increment ID |
| set_id | TEXT | Start.gg set ID |
| field_name | TEXT | Overridden field |
| field_value | TEXT | Overridden value |
| overridden_by | TEXT | Admin who overrode |
| overridden_at | TEXT | ISO timestamp |
