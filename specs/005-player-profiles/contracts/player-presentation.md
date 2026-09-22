# Contract: Player Presentation Hook v1

## Purpose

Provide a local, read-only resolved presentation model for an entrant. It serves
participant review first and future opt-in graphics consumers later. It does not
change current OBS behavior.

## Access and side effects

- Requires an authenticated workspace session; callers cannot supply a workspace ID.
- Input identifies provider, tournament scope, event/bracket scope, and entrant.
- Resolution performs no provider call, provider mutation, match mutation,
  WebSocket broadcast, or asset rewrite.

## Response shape

```json
{
  "version": "v1",
  "entrant": { "provider": "startgg", "tournament_slug": "tournament/example", "event_id": "123", "entrant_id": "456" },
  "player_profile_id": "profile-id-or-null",
  "linked": true,
  "presentation": {
    "display_name": { "value": "FGC | FNCeSports", "source": "player_profile" },
    "prefix": { "value": "FGC", "source": "provider_snapshot" },
    "country": { "value": "JO", "source": "provider_snapshot" },
    "avatar_url": { "value": "/managed/avatar", "source": "player_profile" },
    "character": { "name": "Dhalsim", "id": "2275", "image_url": "https://catalog.example/character.png", "source": "entrant_override" }
  }
}
```

## Compatibility

`broadcast_projection.py`, `/obs/*`, station ownership, `broadcast_state`, and
provider-command behavior do not consume this contract in v1. Any future
consumer declares the supported version and owns a separate regression and
rollback plan.
