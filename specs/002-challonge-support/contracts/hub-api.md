# Hub API Contract Changes

## Tournament representation

All tournament responses add non-secret fields:

```json
{
  "slug": "challonge:weekly-42",
  "name": "Weekly 42",
  "provider_type": "challonge",
  "provider_tournament_id": "weekly-42",
  "provider_sync_status": "ready",
  "provider_last_synced_at": "2026-09-01T09:00:00Z",
  "provider_capabilities": {
    "report_score": true,
    "mark_dq": true,
    "native_check_in": false,
    "stream_queue": false
  }
}
```

Existing Start.gg rows serialize with `provider_type: "startgg"` after migration.

## Add tournament

`POST /api/tournaments` accepts the existing Start.gg form for backward compatibility and a provider-aware form:

```json
{
  "provider_type": "challonge",
  "provider_tournament_id": "weekly-42"
}
```

The server validates authorization and access before persisting. Credentials are configured through authenticated settings endpoints and never placed in this request or response.

Provider-aware body:

```json
{
  "provider_type": "challonge",
  "identifier": "482901"
}
```

Optional subdomain-scoped body:

```json
{
  "provider_type": "challonge",
  "identifier": "weekly-42",
  "subdomain": "fnc-jo"
}
```

`subdomain` is optional and should be omitted, not sent as an empty string, for account-level numeric IDs or normal `challonge.com/{slug}` URLs.

The response returns the durable Hub key and provider numeric ID. Repeating the request with a different URL that resolves to the same `(provider_type, provider_tournament_id)` selects/updates the existing row.

## Provider discovery and preview

`POST /api/providers/{provider_type}/tournaments/resolve` accepts `{ "identifier": "..." }` and returns a credential-free preview. Challonge resolution may include `provider_tournament_id`, `url_slug`, `subdomain`, `community_id`, name, tournament state, format, group-stage flag, and capability summary.

`GET /api/providers/{provider_type}/tournaments` lists tournaments accessible to the configured connection with pagination/filtering. Challonge accepts an optional `community_id` or `subdomain`; omitting both lists/resolves account-level tournaments and is always valid. The backend performs all authenticated upstream calls.

The frontend never sends or receives a Challonge API key through these endpoints.

## Refresh and set endpoints

The existing refresh, events, streams, and sets routes remain keyed by Hub `slug`. They resolve the stored provider internally. Responses add provider identity and capability data where needed. A failed sync returns a provider-safe error and must not erase existing local matches.

## Match representation and controls

`GET /api/active-matches` adds `provider_type`, `provider_set_id`,
`provider_state_raw`, `provider_state_normalized`, `hub_status`, Discord workflow
fields, `sync_status`, command-ledger summary, and a non-secret action projection. The
projection is authoritative for controls:

```json
{
  "actions": {
    "call": { "kind": "local", "enabled": true, "label": "Call in aiTOB" },
    "start": { "kind": "local", "enabled": true, "label": "Start locally" },
    "report_score": { "kind": "remote", "enabled": true, "label": "Report to Challonge" },
    "dq": {
      "kind": "remote",
      "enabled": true,
      "label": "Disqualify",
      "targets": ["p1", "p2"]
    }
  }
}
```

`sync_status` values make remote uncertainty explicit: `pending`,
`acknowledged_unverified`, `retrying`, `failed`, `conflict`, and `needs_review` never
render as a verified provider result. The response includes no credential, raw request
payload, or provider authorization error.

Mutation endpoints keep the canonical `set_id` path; the server resolves remote
identity and rejects unsupported operations with a structured 409/422 before any
database terminal update or provider request. A remote mutation returns a `command_id`
and initially reports `pending`/`acknowledged_unverified`; `snapshot_verified` is
observable through match/command status. A successful response states whether it was
`remote_applied` or `local_only`; it never says "reported to Start.gg" for a
provider-neutral operation.

For Start.gg, the canonical interaction during the provider-owned called window is:

`POST /api/active-matches/{set_id}/attendance`

```json
{ "player": "p1", "state": "present" }
```

`player` is `p1` or `p2`; `state` is `present` or `withdrawn`. The authenticated
Discord entrant and an organizer using manual aiTOB controls call the same command
service. The command records actor, source, call occurrence, and provider deadline,
then submits the corresponding provider-authorized per-entrant attendance transition.
An acknowledgement never completes the match or selects a winner.

`markSetCalled` starts or confirms the Start.gg native called/check-in flow. The
response may expose `provider_timer.deadline` or `provider_timer.duration_seconds`
only when read from or accepted by Start.gg; otherwise it exposes
`provider_timer.managed_by="startgg"` with an unknown deadline. It MUST NOT substitute
the Hub's local `dq_timer_seconds`.

At deadline, Start.gg resolves the bracket: the sole present entrant advances, while
neither present becomes double-DQ. aiTOB learns this only from a newer snapshot.
`POST /api/active-matches/{set_id}/dq` remains the organizer-only immediate result
operation for providers such as Challonge that support single-player DQ; Challonge
projects only `targets: ["p1", "p2"]` and never exposes `both`.

Station/OBS actions are Hub-local unless the action projection explicitly exposes a
verified `remote` stream queue. Challonge is local-only in this release.

## Status

`GET /api/status` adds provider-specific connection and startup-sync readiness summaries. It exposes only boolean/diagnostic state, never keys, tokens, or raw upstream authorization headers.
