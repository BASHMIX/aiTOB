# API Endpoints Contract

**Date**: 2026-05-16
**Base URL**: `http://localhost:8000`

## Authentication

All Hub endpoints require a shared password. The password is stored in `global_settings` table under key `hub_password`.

- **Mechanism**: Session-based (password submitted once per browser session)
- **Unauthenticated access**: OBS overlay endpoints (`/obs/*`) are public (no auth required)

## REST Endpoints

### Players

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| GET | `/api/players` | List all registered players | — | `Player[]` |
| GET | `/api/players/{discord_id}` | Get player by Discord ID | — | `Player` |
| POST | `/api/players` | Create/update player | `Player` body | `Player` |

### Tournaments

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| GET | `/api/tournaments` | List all tournaments | — | `Tournament[]` |
| GET | `/api/tournaments/{slug}` | Get tournament by slug | — | `Tournament` |
| POST | `/api/tournaments` | Create/update tournament | `Tournament` body | `Tournament` |
| DELETE | `/api/tournaments/{slug}` | Delete tournament | — | `204` |
| PATCH | `/api/tournaments/{slug}/settings` | Update tournament settings (DQ timer, etc.) | `{key: value}` | `Tournament` |

### Active Matches

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| GET | `/api/matches` | List active matches (optional `?tournament=slug`) | — | `ActiveMatch[]` |
| GET | `/api/matches/{set_id}` | Get match by set ID | — | `ActiveMatch` |
| POST | `/api/matches/{set_id}/call` | Call a match (start Discord thread) | — | `ActiveMatch` |
| POST | `/api/matches/{set_id}/score` | Report/force score | `{p1_score, p2_score, winner}` | `ActiveMatch` |
| POST | `/api/matches/{set_id}/dq` | Disqualify a player | `{player: "p1"\|"p2"\|"both"}` | `ActiveMatch` |
| POST | `/api/matches/{set_id}/reopen` | Reopen a completed match | — | `ActiveMatch` |
| DELETE | `/api/matches/{set_id}` | Remove match from active list | — | `204` |

### Match Results (Archive)

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| GET | `/api/results` | List match results (optional `?tournament=slug`) | — | `MatchResult[]` |

### Conflicts

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| GET | `/api/conflicts` | List unresolved conflicts | — | `Conflict[]` |
| POST | `/api/conflicts/{id}/resolve` | Resolve a conflict | `{resolution: string}` | `Conflict` |

### Bot Feed

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| GET | `/api/bot-feed` | Get recent bot activity (default 50) | — | `BotFeedEntry[]` |
| DELETE | `/api/bot-feed` | Clear bot feed | — | `204` |

### Hub Commands (AI Agent)

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| POST | `/api/hub/command` | Submit a command (NL or structured) | `{command: string}` | `{response: string}` |

### Overlays

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| GET | `/api/overlays` | List all overlays | — | `Overlay[]` |
| POST | `/api/overlays` | Save overlay config | `{name, config}` | `Overlay` |
| DELETE | `/api/overlays/{name}` | Delete overlay | — | `204` |

### Stations

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| GET | `/api/stations` | List all stations | — | `Station[]` |
| POST | `/api/stations` | Create station | `{id, name}` | `Station` |
| DELETE | `/api/stations/{id}` | Delete station | — | `204` |

### Settings & Connections

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| GET | `/api/settings` | Get all global settings | — | `{key: value}` |
| POST | `/api/settings` | Update a setting | `{key, value}` | `200` |
| GET | `/api/connections` | Get all connection configs | — | `{key: value}` |
| POST | `/api/connections` | Update a connection | `{key, value}` | `200` |

### OBS Overlay Pages (Public, No Auth)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/obs/{overlay_name}` | Rendered HTML overlay page for OBS browser source |
| GET | `/obs/{overlay_name}/data` | JSON data feed for the overlay |

## Start.gg GraphQL Operations

| Operation | Type | Description |
|-----------|------|-------------|
| `getTournamentSets` | Query | Fetch all sets for a tournament event (state filtering) |
| `reportBracketSet` | Mutation | Report match result (winner, scores) |
| `markSetDQ` | Mutation | DQ a player and advance opponent |
| `resetSet` | Mutation | Reset/reopen a completed set |
