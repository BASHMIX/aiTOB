# API Endpoints: AI Tournament Organizer

## Base URL: `/api`

## Auth

All endpoints except `/login` and `/obs/` require Bearer token or `X-Hub-Password` header.

## Matches (`/api/active-matches`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/active-matches` | List all active matches |
| POST | `/api/active-matches` | Create active match (from Start.gg set) |
| PATCH | `/api/active-matches/{set_id}` | Update match (score, status, station) |
| DELETE | `/api/active-matches/{set_id}` | Remove from active status |
| POST | `/api/active-matches/{set_id}/call` | Call players via Discord |
| POST | `/api/active-matches/{set_id}/send` | Report score to Start.gg |
| POST | `/api/active-matches/{set_id}/reset` | Reset match on Start.gg |
| POST | `/api/active-matches/{set_id}/dq` | Disqualify player(s) |
| POST | `/api/active-matches/{set_id}/toggle-stream` | Toggle stream flag |
| POST | `/api/active-matches/{set_id}/ready` | Player ready check |
| POST | `/api/active-matches/{set_id}/resolve-conflict` | Resolve score conflict |

### Create Active Match Request
```json
{
  "set_id": "102995547",
  "p1_name": "Khalid",
  "p2_name": "FNC | BASHMIX",
  "p1_entrant_id": "14259653",
  "p2_entrant_id": "14259654",
  "p1_avatar": "",
  "p2_avatar": "",
  "round_name": "Winners Final",
  "tournament_slug": "fnc1ststartgg",
  "match_number": "1",
  "status": "not_started",
  "p1_score": 0,
  "p2_score": 0,
  "phase_group": "Pool A"
}
```

### Send Score Request (POST /send)
*No body required — uses current match scores*

### DQ Request (POST /dq)
```json
{ "player": "p1" }
```
Values: `"p1"`, `"p2"`, `"both"`

### Toggle Stream Request (POST /toggle-stream)
```json
{ "is_stream_match": false }
```

### Ready Request (POST /ready)
```json
{ "player": "p1" }
```

### Resolve Conflict Request (POST /resolve-conflict)
```json
{ "resolution": "Admin resolved" }
```

## Tournaments (`/api/tournaments`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tournaments` | List all tournaments |
| POST | `/api/tournaments` | Add tournament |
| DELETE | `/api/tournaments/{slug}` | Remove tournament |
| GET | `/api/tournaments/{slug}/sets` | Fetch sets from Start.gg |

### Add Tournament Request
```json
{ "slug": "fnc1ststartgg" }
```

## Hub (`/api/hub`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/hub/command` | Execute hub command |
| GET | `/api/hub/status` | Get hub status |

### Hub Command Request
```json
{ "command": "who is playing?" }
```

## Settings (`/api/settings`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings` | List all settings |
| PATCH | `/api/settings` | Update settings |

### Patch Settings Request
```json
{
  "settings": {
    "hub_password": "newpass",
    "startgg_token": "newtoken"
  }
}
```

## Stations (`/api/stations`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stations` | List all stations |
| POST | `/api/stations` | Create station |
| PATCH | `/api/stations/{id}` | Update station name |
| DELETE | `/api/stations/{id}` | Delete station |
| POST | `/api/stations/{id}/overlays` | Assign overlay to station |
| DELETE | `/api/stations/{id}/overlays/{overlay_name}` | Remove overlay from station |

### Create Station Request
```json
{ "id": "station_1", "name": "Station 1" }
```

### Update Station Request
```json
{ "name": "Main Stage" }
```

### Assign Overlay Request
```json
{ "overlay_name": "default" }
```

## Overlays (`/api/overlays`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/overlays` | List all overlay configs |
| POST | `/api/overlays` | Save overlay config |
| DELETE | `/api/overlays/{name}` | Delete overlay config |
| GET | `/api/overlays/{name}` | Get specific overlay config |

### Save Overlay Request
```json
{
  "name": "default",
  "config": {
    "elements": [
      { "type": "player-name", "x": 100, "y": 50, "width": 300, "height": 40, "slot": "p1" }
    ]
  }
}
```

## Assets (`/api/assets`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/assets/upload` | Upload asset file |

## Players (`/api/players`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/players` | List all players |
| POST | `/api/players` | Create player |

### Create Player Request
```json
{
  "discord_id": "123456789",
  "name": "PlayerName",
  "cfn": "CFN_ID",
  "team": "TeamTag"
}
```

## Auth (`/api/auth`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | Authenticate with hub password |

## Response Models

### Success (200)
```json
{
  "message": "Created",
  "ok": true
}
```

### Error (4xx/5xx)
```json
{
  "error": true,
  "message": "Error description"
}
```

### List Response
```json
{
  "matches": [ ... ],
  "sets": [ ... ],
  "tournaments": [ ... ],
  "players": [ ... ],
  "stations": [ ... ],
  "overlays": [ ... ],
  "settings": { ... }
}
```
