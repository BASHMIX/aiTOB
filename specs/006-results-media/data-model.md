# Data Model: Tournament Results Media

## Overview

The model separates provider evidence, immutable publication data, frozen output configuration, and mutable station playback state. Every persisted row is owned by one Workspace. Provider refresh occurs before the write transaction; PostgreSQL stores only validated observations and operator state.

## Entity: Tournament Result Version

Immutable observation of one provider event plus resolved presentation.

| Field | Type | Rules |
|-------|------|-------|
| `id` | text UUID | Primary key |
| `workspace_id` | text | Required FK to Workspace; included in every lookup and uniqueness boundary |
| `tournament_slug` | text | Required local tournament identity |
| `provider_type` | text | `startgg` or `challonge` initially |
| `provider_account_id` | text | Required account used for the observation; never contains a credential |
| `provider_tournament_id` | text | Required provider tournament identity |
| `event_id` | text | Required provider event identity; Challonge uses its tournament identity as the single event scope |
| `event_name` | text | Required frozen label |
| `game_id` | text nullable | Provider/catalog game identity when available |
| `game_name` | text nullable | Frozen display name |
| `capture_status` | text | Immutable `provisional` or `final`; stale/failed are derived request/readiness states rather than mutations of a version |
| `provider_state_raw` | text | Required provider evidence |
| `provider_revision` | text nullable | Provider revision/timestamp when available |
| `provider_payload_hash` | text | SHA-256 of canonical provider evidence |
| `presentation_hash` | text | SHA-256 of canonical resolved presentations |
| `observation_hash` | text | SHA-256 of provider plus presentation payloads; used for idempotent reuse |
| `observed_at` | timestamptz | Provider observation time |
| `finalized_at` | timestamptz nullable | Provider completion time when available, otherwise observation time for a verified final event |
| `warning_json` | jsonb | Bounded, non-secret diagnostics and missing-field warnings |
| `event_metadata_json` | jsonb | Frozen tournament/event title, date, provider, logo references, and game facts |
| `entry_count` | integer | Must equal stored entry rows |
| `created_by` | text | Required FK to User |
| `created_at` | timestamptz | Required |

**Constraints and indexes**:

- Unique `(workspace_id, tournament_slug, event_id, observation_hash)`.
- Index `(workspace_id, tournament_slug, event_id, created_at DESC)`.
- Index `(workspace_id, capture_status, created_at DESC)`.
- Rows are insert-only; superseding is represented by a later version.

### Derived readiness state

- `final`: latest usable capture is Final and within the configured freshness window.
- `provisional`: latest usable capture was observed before provider finality.
- `stale`: latest usable capture exists but is older than the refresh window required for a new publication; the stored version remains unchanged.
- `failed`: the current refresh attempt failed validation or provider access; no failed version row is created, and safe diagnostics are returned/audited.

## Entity: Tournament Result Entry

One immutable provider standing inside a result version.

| Field | Type | Rules |
|-------|------|-------|
| `version_id` | text | Required FK to Tournament Result Version with cascade delete disabled for published versions |
| `workspace_id` | text | Required and must match the parent version |
| `ordinal` | integer | Stable provider page/order, starting at 1 |
| `placement` | integer | Required, greater than 0, provider-owned and read-only |
| `entrant_id` | text | Required provider entrant identity |
| `entrant_name` | text | Required frozen provider fallback name |
| `provider_user_id` | text nullable | Cross-event provider user identity when available |
| `player_profile_id` | text nullable | Linked reusable profile identity at observation time |
| `is_tied` | boolean | True when another entry in the version has the same placement |
| `presentation_json` | jsonb | Frozen display name, prefix, country, avatar, character, image references, and field provenance |
| `provider_entry_json` | jsonb | Bounded provider facts used for diagnostics; no credentials or unbounded response bodies |

**Constraints and indexes**:

- Primary key `(version_id, entrant_id)`.
- Unique `(version_id, ordinal)`.
- Index `(workspace_id, version_id, placement, ordinal)`.
- Placement order is `(placement ASC, ordinal ASC)`; the platform never renumbers ties.
- `Top N` selects `placement <= N` and may return more than N entries.

## Entity: Results Media Output

Immutable receipt binding a result version to a frozen scene configuration and output purpose.

| Field | Type | Rules |
|-------|------|-------|
| `id` | text UUID | Primary key |
| `workspace_id` | text | Required Workspace owner |
| `result_version_id` | text | Required FK to Tournament Result Version |
| `output_kind` | text | `static` or `live` |
| `overlay_name` | text nullable | Source preset label when created from a saved overlay |
| `scene_schema_version` | integer | Initially `2` |
| `scene_config_json` | jsonb | Frozen normalized Results scene; no generated instances |
| `scene_hash` | text | SHA-256 of canonical scene config |
| `cutoff` | text | `top8`, `top16`, or `all` |
| `page_number` | integer | Required, starting at 1 |
| `output_profile_json` | jsonb | Width, height, safe area, background/transparent intent |
| `export_byte_size` | bigint nullable | Client-reported PNG size for completed static export |
| `export_sha256` | text nullable | Client-computed PNG digest for audit, not content trust |
| `created_by` | text | Required FK to User |
| `created_at` | timestamptz | Required |

**Constraints and indexes**:

- Index `(workspace_id, result_version_id, created_at DESC)`.
- `scene_config_json.dataSource.kind` must equal `tournament-results`.
- The referenced version must have `capture_status = final` and pass the current publication freshness gate for a newly created Final output.
- Static output receipt is created after rasterization succeeds and before download begins.
- Live output receipt is created before a station session binds it.

## Entity: Results Overlay Session

Mutable station playback state with optimistic concurrency.

| Field | Type | Rules |
|-------|------|-------|
| `workspace_id` | text | Required Workspace owner |
| `station_id` | text | Required FK to Station |
| `media_output_id` | text nullable | Required in `ready`, `live`, `held`, or `complete`; cleared on explicit reset if desired |
| `state` | text | `cleared`, `ready`, `live`, `held`, `complete`, `error` |
| `cue_index` | integer | `-1` before first reveal; bounded by resolved cue count |
| `session_revision` | bigint | Incremented atomically on every command |
| `controller_user_id` | text nullable | Last authorized controller |
| `error_code` | text nullable | Safe diagnostic code only |
| `updated_at` | timestamptz | Required |

**Constraints and indexes**:

- Primary key `(workspace_id, station_id)`.
- Station and media output must belong to the same Workspace.
- Command update requires `expected_revision == session_revision` and increments revision atomically.
- The scene and result version come from the frozen media output, never the mutable overlay preset.

### Session transitions

```text
cleared ──bind──> ready ──take-live/play-all/next──> live
   ▲                 │                                  │
   │                 └────────clear─────────────────────┤
   │                                                    │
   └────────────────────────clear───────────────────────┘

live ──hold──> held ──next/previous/play-all──> live
live ──last cue completes──> complete
complete ──restart/previous──> live
ready/live/held/complete ──invalid binding on recovery──> error
error ──clear──> cleared
```

## Scene Document v2

Saved as overlay JSON and frozen in Results Media Output.

### Root document

| Field | Type | Rules |
|-------|------|-------|
| `schemaVersion` | integer | `2` |
| `canvas` | object | Width, height, background, safe area, font library |
| `rootIds` | array of node IDs | Authoring root order only |
| `nodes` | map of node ID to node | Contains authoring nodes, shared card definitions, and explicitly inserted linked cards; never template/Auto Sequence runtime cards |
| `dataSource` | object | `kind: current-match` for existing scenes or `kind: tournament-results` with result binding settings |

### Common authoring node

- `id`, `type`, `name`, `parentId`, `order`, `visible`, `locked`, `zIndex`.
- Relative transform: `x`, `y`, `width`, `height`, optional rotation/opacity.
- Existing style/source/animation properties are retained on primitive nodes.

### Group node

- `type: group`.
- `childIds`: ordered authoring children.
- Group transform applies to descendants.
- Group animation may wrap child animations.

### Result Card definition

- `type: group` with `definitionRole: result-card`.
- Owns ordered authoring children bound to approved result fields or literal content.
- Has design-space width/height and optional internal child animations.
- Is not itself placed in `rootIds` and does not carry a standing identity.
- May be referenced by freeform Result Card instances and Results Groups.

### Freeform Result Card instance

- `type: result-card`.
- `definitionId`: required reference to one Result Card definition.
- `instanceRole`: `stage` for the primary authored card or `linked` for an explicitly materialized card.
- `standingSelector`: mock/provider ordinal or explicit frozen-entry selector; it cannot override provider placement.
- Carries the scene transform, z-index, visibility, lock state, and optional outer-animation override.
- Does not copy definition children.

### Results Cards scheduling parent

- `type: results-cards`.
- `childIds`: ordered freeform `result-card` instances only.
- Created automatically by Add Result Card when a suitable parent is not selected.
- Carries only playback order, delay/stagger, overlap/with-previous behavior, keep-previous-visible, loop, and transport state defaults.
- Carries no layout slots or mandatory variants and never clamps child transforms.
- Optional one-shot Gallery/Grid commands update child transforms and are not persistent layout constraints.

### Results Group node

- `type: results-group`.
- `cardDefinitionId`: exactly one shared Result Card definition.
- `mode`: `board` or `sequence`.
- `cutoff`: `top8`, `top16`, or `all`.
- `pageSize`, `pageNumber`.
- `layoutPresetId` and optional validated custom layout slots.
- `variantRules`: map placement ranges to `champion`, `podium`, or `standard`.
- `sequence`: order preset, start delay, interval, hold, exit, loop, and cue mode.
- `preview`: mock dataset key and preview page; editor-only and ignored by published binding.
- Generated template cards are ephemeral renderer values and never authoring nodes.
- A deliberate materialization action converts resolved slot geometry into linked freeform Result Card instances referencing the same definition.

### Result Card animation lifecycle

- `start`, `visible`, and `exit` transforms each allow relative/absolute x/y, scale, opacity, and optional rotation.
- Enter and exit phases have bounded duration and easing; Visible has an optional hold.
- A linked instance may inherit the stage animation or supply an instance override.
- Internal definition-child animations run relative to the instance start and do not rewrite the outer transform.

### Auto Sequence settings

- Attached to a Results Cards scheduling parent or its stage card.
- `range`: `top8`, `top16`, or `all` plus page/batch controls.
- `order`: placement ascending, placement descending, or explicit stable ordinal list.
- `delayBetweenStartsMs`: non-negative stagger where instance `i` starts at `base + i × delay`.
- `endBehavior`: follow card exit, keep visible, or clear after hold.
- Runtime instances carry resolved standing content, transform-at-time, and stable runtime cue ID only; they are never serialized.

### Layout slot

- Stable `slotId`.
- `x`, `y`, `width`, `height`, optional rotation.
- `variant`.
- Placement selector or ordinal selector.
- Used by Results Group only; does not carry player content or freeform animation timing.

### Sequence cue

- Stable `cueId` generated from consumer node plus standing identity/order.
- Standing selector and resolved display order.
- Enter/hold/exit timing.
- Does not carry z-index or modify layout slots.
- For Auto Sequence, start time is derived directly from ordinal and Delay Between Starts so overlapping lifecycles are valid.

## Presentation precedence

Frozen result-entry presentation retains existing precedence:

```text
event/tournament entrant override
→ confirmed player profile and selected game profile
→ provider snapshot
→ placeholder
```

Featured-character edits default to the event override. Promotion to Player Archive is a separate audited mutation; it never rewrites prior result versions.

## Transaction and concurrency rules

1. Authorize Workspace, tournament, provider account, event, and role.
2. Perform provider HTTP request outside a database transaction.
3. Resolve presentation in bounded batch reads.
4. Canonicalize, validate, and hash outside the write transaction.
5. Start a short transaction and acquire a transaction-scoped advisory lock derived from Workspace/tournament/event.
6. Reuse an existing observation hash or insert version plus all entries atomically.
7. Record the audit event in the same transaction.
8. Commit, then notify Workspace subscribers.

Live commands use a single conditional update on `(workspace_id, station_id, expected_revision)` followed by broadcast after commit. A failed revision returns conflict and does not broadcast.

## Retention

- Final published result versions and their entries are retained with tournament history.
- Provisional versions may be pruned only by an explicit future retention policy; this feature does not delete them automatically.
- Results media outputs are retained as audit/config receipts; PNG bytes are not stored in v1.
- Clearing a live session changes playback state but does not delete the referenced output or result version.
