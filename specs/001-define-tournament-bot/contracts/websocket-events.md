# WebSocket Events Contract

**Date**: 2026-05-16
**Endpoint**: `ws://localhost:8000/ws`

## Connection

The Admin Hub connects via WebSocket at `/ws` for real-time updates. No authentication is required on the WebSocket itself (the Hub session must be authenticated via the shared password before establishing the connection).

## Server → Client Events

All messages are JSON with a `type` field:

```json
{"type": "<event_type>", "data": { ... }}
```

| Event Type | Description | Data |
|------------|-------------|------|
| `match_update` | A match state changed (created, called, score updated, completed, DQ) | `ActiveMatch` object |
| `match_deleted` | A match was removed from the active list | `{set_id: string}` |
| `bot_feed` | New bot activity log entry | `{message: string, level: string, timestamp: string}` |
| `heartbeat` | Discord bot heartbeat status | `{status: "online"\|"offline", last_seen: string}` |
| `conflict_created` | A new score conflict was detected | `Conflict` object |
| `conflict_resolved` | A conflict was resolved by admin | `Conflict` object |
| `tournament_sync` | Bracket state synced from Start.gg | `{tournament_slug: string, matches_added: int, matches_removed: int}` |
| `command_response` | Response from a hub command/AI agent | `{command_id: int, response: string}` |

## Client → Server Events

| Event Type | Description | Data |
|------------|-------------|------|
| `subscribe` | Subscribe to updates for a specific tournament | `{tournament_slug: string}` |
| `ping` | Keep-alive ping | `{}` |

## Reconnection

If the WebSocket connection drops:
- Frontend MUST attempt automatic reconnection with exponential backoff (1s, 2s, 4s, 8s, max 30s)
- On reconnection, frontend MUST re-subscribe to the active tournament
- Frontend MUST display a "Reconnecting..." indicator during disconnection
