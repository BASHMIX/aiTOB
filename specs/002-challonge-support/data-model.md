# Data Model: Challonge Tournament Support

## Tournament

Existing entity, extended additively.

| Field | Purpose | Validation / migration |
|-------|---------|------------------------|
| `slug` | Existing Hub-local tournament key used by routes and subscriptions | Retain legacy Start.gg values; assign a collision-safe key for new Challonge rows. |
| `provider_type` | Owning provider (`startgg` or `challonge`) | Non-null; legacy rows default to `startgg`. |
| `provider_tournament_id` | Canonical remote identifier used by the adapter | Non-empty and unique with `provider_type`; normalize before persistence. |
| `provider_url_slug` | Current provider display URL segment | Mutable metadata; never used as the durable foreign identity. |
| `provider_community_id` | Remote community ID when applicable | Optional; used for scoped discovery. |
| `provider_subdomain` | Challonge community/subdomain label | Optional normalized lowercase display/discovery metadata. |
| `provider_connection_key` | Reference to the server-side provider credential/configuration | Never returned in API responses. |
| `provider_sync_status` | `ready`, `syncing`, `failed`, or `stale` | Drives bot and UI action gating. |
| `provider_sync_error` | Last redacted synchronization error | Clear only after successful sync. |
| `provider_last_synced_at` | Last successful sync timestamp | Used for freshness display and startup readiness. |
| existing configuration fields | DQ, dispatcher, check-in, event, and streams settings | Continue to work; provider capability controls whether they apply remotely. |

## Provider Connection

| Field | Purpose |
|-------|---------|
| `key` | Existing internal connection/settings key, e.g. Challonge API credential. |
| `provider_type` | Identifies the credential owner. |
| `authorization_state` | Valid, invalid, expired, or insufficient permission. |
| `capabilities` | Connection-level permissions discovered by a safe probe. |
| `last_checked_at` | Timestamp of the last permission check. |

Secrets are stored server-side only and shown as masked values in settings.

## Tournament Loading Session

Ephemeral browser state used only while discovering/importing a tournament.

| Field | Purpose |
|-------|---------|
| `selected_provider` | Explicit Start.gg or Challonge choice for the current browser session. |
| `identifier_input` | Unsaved slug, numeric ID, or URL. |
| `parsed_locator` | Client-safe normalized preview without credentials. |
| `connection_status` | Provider readiness shown before discovery. |
| `preview` | Server-confirmed tournament name, provider, ID, community, state, and format. |

This state belongs in `sessionStorage` and MUST NOT determine the provider of an existing tournament.

## Challonge Tournament Locator

| Field | Purpose |
|-------|---------|
| `numeric_id` | Stable v2.1 tournament ID when supplied or resolved. |
| `url_slug` | Mutable Challonge URL segment. |
| `subdomain` | Optional normalized custom/community subdomain from the host, explicit choice, or legacy identifier. `null` for direct ID/normal URL loading. |
| `community_id` | Optional resolved Challonge community scope when subdomain/community discovery is requested and authorized. |
| `original_input` | Redacted user input for validation messages; contains no credential. |

Validation rejects unsupported hosts, empty identifiers, ambiguous path forms, credentials embedded in a URL, and inconsistent community/tournament results. It never requires `subdomain` when `numeric_id` or a normal `url_slug` is available.

## Active Match

Existing entity, extended to separate Hub identity from remote identity.

| Field | Purpose | Validation / migration |
|-------|---------|------------------------|
| `set_id` | Canonical Hub match key used by existing UI, Discord thread, and OBS references | Keep existing Start.gg values; new provider rows use a provider-safe canonical key. |
| `provider_type` | Match owner, denormalized from tournament for safe routing | Must equal the owning tournament's provider. |
| `provider_set_id` | Raw provider match identifier | Used only by the owning provider adapter for remote requests. |
| `provider_state_raw` | Exact provider state text | Examples: `open`, `complete`, `ACTIVE`; never inferred from Hub status. |
| `provider_state_normalized` | Latest adapter-normalized remote state | Stored by enum name, not numeric representation. |
| `provider_revision`, `provider_observed_at` | Remote ordering evidence | Rejects out-of-order snapshot writes when a revision/timestamp is supplied. |
| `hub_status` | Local coordination lifecycle | `not_started`, `available`, `called`, `ready`, `in_progress`, or `complete`; rendered as aiTOB workflow state. |
| `hub_status_origin` | Authority for the latest Hub status | `provider_sync`, `local_workflow`, `remote_mutation`, or `migration`. |
| `sync_status`, `sync_reason`, `last_successful_snapshot_at` | Reconciliation axis | `synced`, `local_only`, `pending`, `acknowledged_unverified`, `retrying`, `failed`, `conflict`, or `needs_review`. |
| Discord workflow fields | Durable Discord axis | `call_message_id`, `thread_id`, `called_at`, Ready timestamps, attendance deadline, and notification timestamp. |
| `result_kind` | Final result representation | `score`, `dq`, `double_dq`, `void`, or null; never guesses a provider-native DQ flag. |
| `status` | Legacy compatibility field | Mirrors `hub_status` while readers move to the new field. |
| `progression` | Canonical stage and bracket-location value object | Replaces no existing lifecycle field; provider raw fields remain auditable. |
| existing Hub fields | Entrants, scores, station, stream intent, readiness, thread, and local status | Preserved across synchronization unless the remote source of truth changes the matching provider field. |

The old `provider_state` column is retained only during migration as a compatibility
source. It is not a diagnosis field because its present values may be stringified enum
integers rather than the upstream response.

## Tournament Progression

Provider-neutral value object attached to every synchronized match.

| Field | Meaning |
|-------|---------|
| `stage` | Named competition stage, such as a pool/group or playoffs. |
| `stage_kind` | `single`, `group`, `final`, or `unknown`. |
| `group` | Provider group/pool name when applicable. |
| `bracket_side` | `winners`, `losers`, `finals`, `round_robin`, `swiss`, or `unknown`. |
| `round` | Provider display round name or number. |
| `round_order` | Sortable numeric order when known. |
| `display_path` | Organizer-facing composed label, for example `Groups / Pool A / Round 2`. |
| `provider_raw_progression` | Original provider fields retained for diagnostics. |

This object MUST NOT contain `lifecycle_state`. Lifecycle remains a separate normalized state used by call, readiness, score, DQ, and completion workflows.

## Provider Capability

Value object returned by each adapter and optionally refined per tournament.

| Capability | Meaning |
|------------|---------|
| `fetch_tournament`, `fetch_sets` | Readable remote bracket data. |
| `report_score`, `report_winner`, `mark_dq` | Supported remote result mutations. |
| `mark_called`, `mark_in_progress`, `reset_set`, `double_dq` | Optional lifecycle mutations. |
| `native_check_in`, `stream_queue` | Provider-native features; callers must not infer these from Hub functionality. |
| `match_attachments` | The provider accepts or returns match evidence/attachments. |
| `head_to_head_coordination` | The format and match have exactly two resolved sides and are eligible for existing Discord match workflow. |

Each capability is exposed to callers as an action descriptor with `kind` (`remote`,
`local`, `unavailable`), safe explanation, and Hub-state prerequisites. The final
action decision also considers match eligibility, snapshot freshness, pending command,
organizer permission, and feature flag. Capability data has no credentials and does not
imply a local station/overlay action changes the remote provider.

## Synchronization Run

An observable operation, initially represented by tournament status and bot-feed entries; a dedicated history table is deferred unless operational evidence requires long-term audit history.

State flow: `idle → syncing → ready` on success, or `idle → syncing → failed/stale` on error. During startup, tournament match actions remain gated until each tracked tournament reaches `ready` or an explicit failure state is surfaced.

## Provider Command Ledger

An additive, short-lived audit record for the repair migration and command diagnostics.

| Field | Purpose |
|---|---|
| `id` | Local audit identifier. |
| `tournament_slug`, `set_id`, `provider_type` | Scope; uses saved Hub/provider identity. |
| `action` | `sync`, `score`, `dq`, `reset`, `reopen`, `migration_preview`, or `migration_apply`. |
| `state` | `pending`, `sending`, `acknowledged`, `snapshot_verified`, `retryable`, `permanent_failure`, `conflict`, or `needs_review`. |
| `idempotency_key`, `payload_digest` | Stable mutation identity without storing secrets. |
| `expected_result`, `precondition_revision` | Snapshot verification target and stale-write protection. |
| `lease_until`, `next_retry_at`, `attempt_count` | Crash-safe worker ownership and provider-local backoff. |
| `before_hub_status`, `after_hub_status` | Explain a state change without reconstructing it from logs. |
| `provider_state_raw`, `reason` | Remote evidence and safe merge/migration reason. |
| `created_at` | Operator-visible timestamp. |

It records no secrets or raw authorization messages. A retention window may remove old
entries, but the active repair report remains visible until the organizer acknowledges it.

Provider Command Ledger is exclusively for operations that are sent to a remote bracket
provider. Hub-local Call, Ready, station, and lifecycle changes are recorded in the Hub
workflow/audit path and must not create a provider command.

## Workflow Outbox

| Field | Purpose |
|---|---|
| `event_id`, `match_id`, `event_type` | Durable external side-effect identity and target. |
| `payload`, `deduplication_key` | Safe event data and idempotency key for Discord/OBS handling. |
| `status`, `attempts`, `next_attempt_at`, `completed_at` | Crash-safe retry state and completion evidence. |

Hub workflow transition plus intended outbox event are inserted in one SQLite
transaction. Event types include Discord Call, thread create/update, DQ warning, OBS
update, match-message close, and next-match announcement. The worker may retry safely;
a local `called` row without a completed Call event remains visibly pending/failed rather
than falsely implying players were notified.

## Provider API Budget and Snapshot Cache

| Field | Purpose |
|---|---|
| `provider_type`, `provider_account_id` | Isolate limits for the correct provider connection/account. |
| `window_started_at`, `estimated_used`, `remaining_if_known`, `reset_at` | Durable quota estimate; provider portal remains source of account-wide truth. |
| `backoff_until`, `last_429_at` | Provider/account-local throttle state that survives restart. |
| `tournament_slug`, `scope`, `reason`, `cost_class` | Attribute calls as cheap/normal/expensive by intent and smallest requested scope. |
| `in_flight_key`, `requested_at`, `completed_at` | Coalescing and audit for `provider + account + tournament + scope`. |
| `scope_coverage`, `entity_coverage`, `freshness_revision` | Prove whether an in-flight broader request safely satisfies a narrower entity/range request. |
| `revision`, `etag`, `last_modified`, `content_hash`, `expires_at` | Adapter-supported conditional/incremental cache data; nullable when unavailable. |

Scopes are `tournament_metadata`, `participants`, `bracket_structure`, `active_matches`,
`single_match`, `result_verification`, `advancement_neighborhood`, and `full_snapshot`.
Consumers never query a provider directly: they read the durable projection/cache while
the coordinator refreshes it when policy permits.

## Participant Identity Link

| Field | Purpose |
|---|---|
| `provider_type`, `provider_participant_id`, `provider_entrant_id` | Stable provider-side identity; names are display metadata only. |
| `aitob_participant_id` | Durable local identity across providers and tournaments. |
| `discord_user_id` / `discord_role_id` | Verified recipient or team routing target. |
| `tournament_slug`, `scope` | Permit tournament-specific or reusable verified links. |
| `verification_state`, `source`, `verified_at` | Distinguish imported, organizer-overridden, and user-confirmed mappings. |
| `display_name_snapshot`, `aliases` | Audit aid; never used as the sole mention key. |

Teams may map an entrant to an aiTOB team identity and multiple Discord users. Ambiguous
or absent links explicitly block automatic mentions until organizer review.
