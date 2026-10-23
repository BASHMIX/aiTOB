# Contract: Results Overlay Playback Protocol

## Station data response

`GET /obs/{station_id}/data` retains its current envelope and adds an explicit projection selector.

### Current match

```json
{
  "projection_kind": "current-match",
  "config": {},
  "active_match": {},
  "results_projection": null
}
```

### Tournament results

```json
{
  "projection_kind": "tournament-results",
  "config": {
    "schemaVersion": 2,
    "dataSource": { "kind": "tournament-results" },
    "rootIds": ["results"],
    "nodes": {}
  },
  "active_match": null,
  "results_projection": {
    "output_id": "uuid",
    "result_version_id": "uuid",
    "capture_status": "final",
    "event": {
      "id": "event-id",
      "name": "Street Fighter 6 Singles",
      "game_name": "Street Fighter 6"
    },
    "entries": [],
    "session": {
      "state": "live",
      "cue_index": 3,
      "session_revision": 9
    }
  }
}
```

The payload is resolved entirely from PostgreSQL and frozen media output. It performs no provider or Player Archive lookup.

## WebSocket server event

After a committed bind or command, the server broadcasts only to the owning Workspace/station:

```json
{
  "type": "results_session_update",
  "station_id": "station_1",
  "session": {
    "media_output_id": "uuid",
    "state": "live",
    "cue_index": 3,
    "session_revision": 9,
    "updated_at": "2026-09-28T12:00:00Z"
  }
}
```

The message contains no credentials, user email, provider raw payload, or data from another Workspace.

## Client command semantics

All commands are issued through the authenticated HTTP endpoint with `expected_revision`; the public OBS socket does not accept operator commands.

| Command | Valid states | Result |
|---------|--------------|--------|
| `take_live` | ready, held, complete | state live; cue remains or starts at -1 |
| `play_all` | ready, live, held, complete | state live; renderer advances from current cue using saved timing |
| `next` | ready, live, held | increment by exactly one, capped at last cue |
| `previous` | live, held, complete | decrement by exactly one, floored at -1 |
| `hold` | live | state held, cue unchanged |
| `restart` | ready, live, held, complete | state live, cue -1 before entrance |
| `clear` | ready, live, held, complete, error | state cleared; OBS renders transparent results scene |

If `expected_revision` is stale, no state changes and no WebSocket event is emitted.

## Renderer behavior

- `current-match` continues through the existing telemetry merge path.
- `tournament-results` bypasses match element merging and does not clear when `active_match` is null.
- `ready` may be previewed in authenticated editor/operator surfaces but public OBS remains transparent until take-live/next/play-all.
- `live` renders cues through `cue_index` and applies active transition state.
- `held` renders the stable state through `cue_index` with no automatic advancement.
- `complete` renders the configured final state until clear/restart.
- `cleared` and `error` render transparent output with safe local diagnostics only in authenticated controls.

## Reconnect and restart

- OBS first loads the HTTP projection, then authenticates its existing revocable station token on WebSocket.
- A reconnect accepts only events whose `session_revision` is greater than the currently rendered revision.
- API restart does not reset the session. The first data read reconstructs it from PostgreSQL.
- If the output/result version is missing or belongs to a different Workspace, recovery changes the session to `error` without rendering data.

## Readiness gate

Take Live is allowed only when:

- The media output and station belong to the authenticated Workspace.
- The output kind is `live` and its scene validates as Scene v2 tournament results.
- The bound result version is Final for a Final-labelled show.
- At least one standing entry resolves for the selected cutoff/page.
- Required images and fonts have resolved or a declared fallback is ready.
- The cue list is non-empty and deterministic.

## Compatibility

Existing OBS URLs, tokens, current-match presets, next-match presets, and WebSocket authentication remain valid. Results support is additive and selected only by an explicit frozen results session.
