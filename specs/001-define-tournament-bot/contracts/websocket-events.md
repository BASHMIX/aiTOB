# WebSocket Events: AI Tournament Organizer

## Connection

### /ws/hub
Subscribe to tournament slug for live match updates.

```javascript
// Client connects using window.location.host for proxy/direct compatibility
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const ws = new WebSocket(`${protocol}//${window.location.host}/ws/hub?slug=fnc1ststartgg`)
```

### /ws/overlay/{slot}
Per-slot overlay broadcast for OBS browser sources.

```javascript
// No query params needed
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const ws = new WebSocket(`${protocol}//${window.location.host}/ws/overlay/station_1`)
```

## Event Types

### match_update
```json
{
  "type": "match_update",
  "payload": {
    "set_id": "102995547",
    "status": "in_progress",
    "p1_score": 2,
    "p2_score": 1
  }
}
```

### overlay_update
```json
{
  "type": "overlay_update",
  "payload": {
    "p1": { "name": "Khalid", "score": 2 },
    "p2": { "name": "FNC | BASHMIX", "score": 1 }
  }
}
```

### bot_feed
```json
{
  "type": "bot_feed",
  "payload": {
    "event_type": "match_called",
    "message": "Match 1 called: Khalid vs FNC | BASHMIX",
    "set_id": "102995547"
  }
}
```

### hub_command_result
```json
{
  "type": "hub_command_result",
  "payload": {
    "command_id": 5,
    "status": "done",
    "result": "3 active matches found"
  }
}
```

## Error Handling

- Client implements exponential backoff reconnection
- Server closes connection on invalid subscription
- No auth required for /ws/overlay/* (OBS sources)
- /ws/hub validates Bearer token
