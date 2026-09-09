# Implementation Plan: Provider-isolated match control and Challonge reconciliation

**Branch**: `002-challonge-support` | **Date**: 2026-09-04 | **Spec**: [spec.md](./spec.md)

**Input**: Existing Challonge-support specification, the connected FNC test tournament, and the observed Hub/remote-state divergence.

## Summary

Make bracket providers independently pluggable. **aiTOB is the tournament's persistent
operations manager**: it owns calls, attendance, Discord, stations, overlays, recovery,
and organizer workflow. The provider remains the authoritative reference for bracket
structure, reported results, advancement, and provider-native state.

An operation the provider does not natively model is not discarded. It becomes an
explicit Hub-owned operation. For example, a Challonge match can be `called` locally:
aiTOB notifies the correct players in Discord, creates/recovers the Match Thread, runs
the attendance deadline and warning, records each Ready response, assigns a station,
and updates OBS/UI. It must label this as `local_only`, rather than pretending it
changed Challonge or hiding the workflow.

Start.gg retains its current native lifecycle and stream-queue behavior. Challonge
receives no synthetic `called`, `in_progress`, station, or stream mutation: those are
Hub-only operations. It receives only verified remote operations, such as a completed
score or an explicit forfeit/DQ result. Remote state, normalized remote state, and Hub
workflow state are stored separately, reconciled with explicit ownership rules, and
shown separately in the UI.

The implementation repairs the current false `in_progress` Challonge rows without
changing any Start.gg row. It introduces a four-axis state model, durable provider
command ledger, provider-local adapters, bidirectional reconciliation, recovery after
restart/outage, identity mapping, budget-aware synchronization, and contract tests so a
third provider is added by implementing one boundary rather than editing Hub routes,
the state machine, Discord effects, and React action handlers.

**Mandatory provider-access rule**: no React view, API route, Discord handler, bot
handler, overlay, or workflow service may call a provider directly. They read the local
durable projection in SQLite. All provider reads and mutations pass through one
budget-aware Sync Coordinator that coalesces concurrent work, applies provider-specific
caching/backoff, chooses the smallest sufficient snapshot scope, and prioritizes
tournament-critical work over background freshness.

## Technical Context

**Language/Version**: Python 3.12+, TypeScript 6 / React 19  
**Primary Dependencies**: FastAPI, aiosqlite, httpx, Pydantic v2, Vite, Zustand  
**Storage**: SQLite (`tournaments`, `active_matches`, station and sync tables)  
**Testing**: pytest / pytest-asyncio, mocked provider-contract tests, React build; one documented live sandbox verification for Challonge mutations  
**Target Platform**: Local Windows organizer deployment, FastAPI `:8000`, Vite `:5173`  
**Project Type**: Web API + React dashboard + Discord/OBS coordination  
**Performance Goals**: No periodic Challonge requests in Economy mode; Live mode has a per-tournament five-minute minimum; a manual sync coalesces duplicate upstream calls.  
**Constraints**: Never expose provider secrets; never call unsupported remote operations; preserve Start.gg behavior; never write a Challonge stream assignment; no upstream acknowledgement alone is final; snapshots are revision-aware; every external mutation is durable and idempotent; a provider outage must not stop the unrelated provider or Hub-local operations.  
**Scale/Scope**: Current providers are `startgg` and `challonge`; contracts support a future `manual` or third-party provider without edits to generic routes, transitions, or React actions.

## Constitution Check

The repository constitution is an unfilled template and has no enforceable gate. This
plan therefore applies these safety gates:

- Provider adapters own upstream IDs, payloads, rate limiting, and remote mutations.
- Generic Hub code consumes typed capability and reconciliation results only.
- Existing Start.gg test coverage passes unchanged before Challonge behavior is enabled.
- Challonge write behavior is enabled only after a disposable sandbox proves the exact
  v2.1 payload and public-bracket display.
- No credential enters a URL, browser state, test fixture, log, or spec example.

**Post-design check**: Pass. The design introduces no cross-provider database key,
network payload, or generic API path that relies on a provider name.

## Current Findings That Drive the Design

1. `backend/core/match_state.py` calls `mark_in_progress` for every provider and binds
   an on-stream station from the generic transition. `backend/api/routers/matches.py`
   similarly attempts remote stream assignment from a generic toggle. Both are
   Start.gg assumptions and must be capability-gated.
2. `backend/core/database.py::_update_existing_match` preserves a local active state
   when a later provider snapshot says `NOT_STARTED`. This is right for a Hub-owned
   call/local-live workflow but caused imported Challonge `open` matches to remain
   falsely `in_progress`; it also stores `str(enum)` rather than raw provider state.
3. `backend/core/providers/challonge/provider.py` reports winner-only/DQ as generic
   `1-0`. That is not a verified public Challonge DQ representation; it becomes an
   adapter-owned forfeit policy and is sandboxed before production.
4. `frontend-react/src/features/hub/components/MatchDashboard.tsx` maps raw sets with
   Start.gg terminology and labels generic actions as Start.gg actions. The server
   needs an action projection so the UI never infers support from a provider name.
5. A station occupied by a Start.gg `testfnc` match is independent of this Challonge
   tournament. The migration must not release, assign, or alter that station.

## Architecture and Isolation Boundary

```text
React Match Card
  └─ local durable projection + action projection (enabled, local-only, remote, unavailable)
       └─ Match command service
            ├─ Hub workflow: call, Discord, readiness, local start, station, overlay
            ├─ Reconciliation policy: merges remote snapshot with Hub workflow
            └─ API Budget & Sync Coordinator
                 ├─ coalescing, scope selection, cache, priority, backoff, telemetry
                 └─ Provider registry: resolves owning adapter from saved tournament
                      ├─ StartGGProvider: GraphQL lifecycle, DQ, stream queue
                      ├─ ChallongeProvider: v2.1 snapshot, score, sandboxed forfeit
                      └─ FutureProvider: implements the same typed boundary
```

No `if provider == "challonge"` or `if provider == "startgg"` belongs in generic
match routes, `match_state.py`, `score_reporting.py`, or React action handlers.
Provider-specific rules belong to an adapter or provider-owned policy. A provider-name
switch is permitted only in registry construction and one-time migrations, where it is
explicit and test-covered.

The Coordinator is deliberately narrow and must not become a second state machine:

```text
Scheduler / Command Service  → requests an operation and declares intent
Sync Coordinator             → budget admission, coverage-aware coalescing, timing, cache, backoff
Provider Adapter             → provider protocol, scope translation, payload/revision details
Reconciliation Engine        → compares durable local/remote facts and emits decisions
Completion Service           → applies idempotent Hub/Discord/station/overlay effects
SQLite                       → durable projection read by all other components
```

The Coordinator does not own Discord, Hub lifecycle transitions, provider payload
semantics, or reconciliation decisions.

## Provider Capability Matrix

| Capability / action | Start.gg | Challonge | Hub behavior |
|---|---:|---:|---|
| Fetch bracket structure, participants, match updates | Remote | Remote | Adapter-owned, paginated/cached; incremental only when supported |
| Call / native match check-in | Remote | Not supported | Start.gg remote; Challonge local Discord call |
| Mark match in progress | Remote | Not supported | Start.gg remote; Challonge local workflow only |
| Report a completed score / forfeit | Remote | Remote score convention, **after sandbox proof** | Adapter validates payload, entrant slots, ranks, advancement |
| Double DQ | Current Start.gg technical resolution | Not supported remotely | Pause for organizer decision; never fabricate a Challonge winner |
| Reset / reopen | Start.gg where upstream allows | Not supported | Explicit capability and policy; reopening after downstream advance needs review |
| Provider stream queue / station | Remote | Not supported in this release | Local station/OBS remains available to both; no Challonge upstream call |
| Local station, overlay, Discord thread | Local | Local | Hub-owned, no provider mutation |

The provider contract explicitly declares `fetch_bracket_structure`,
`fetch_participants`, `fetch_match_updates`, `report_score`, `report_forfeit`,
`reset_match`, `reopen_match`, `native_check_in`, `mark_called`, `mark_in_progress`,
`assign_stream`, `fetch_incremental_changes`, `supports_remote_revision`, and
`supports_idempotency`.

The action projection includes `kind: remote | local | unavailable`, a reason, and
Hub-state prerequisites. Final permission to render or execute an action is the
intersection of provider capability, match eligibility, Hub state, snapshot freshness,
pending command state, organizer permission, and feature flag. A new provider declares
these policies once rather than requiring copied route and UI conditionals.

## State Ownership and Reconciliation Rules

### Persisted model

Replace the overloaded active-match state representation with four independently owned
axes. `conflict` is not a Hub lifecycle state: a match can be locally in progress while
the synchronization state needs review.

| Axis / fields | Owner | Purpose |
|---|---|---|
| `provider_state_raw`, `provider_state_normalized`, `provider_revision`, `provider_observed_at` | adapter snapshot | What Start.gg/Challonge says, exact raw text plus normalized value and ordering evidence. |
| `hub_status`, `hub_status_origin` | aiTOB workflow | `not_started`, `available`, `called`, `ready`, `in_progress`, `complete`; origin is `provider_sync`, `local_workflow`, `remote_mutation`, or `migration`. |
| `call_message_id`, `thread_id`, `called_at`, `player1_ready_at`, `player2_ready_at`, `attendance_deadline`, `last_notification_at` | Discord workflow | Durable call, readiness, message, and timer details. It is deliberately field-based, not one lossy enum. |
| `sync_status`, `sync_reason`, `last_successful_snapshot_at` | reconciliation engine | `synced`, `local_only`, `pending`, `acknowledged_unverified`, `retrying`, `failed`, `conflict`, or `needs_review`. |
| `result_kind` | provider command / completion | `score`, `dq`, `double_dq`, `void`, or null. |
| existing `status` | compatibility phase | Mirrors `hub_status` through one accessor until legacy readers migrate. |

`ProviderSet` gains raw state, normalized state, bracket structure/progression, remote
revision/update timestamp when supplied, and two-side eligibility. It never carries
Hub station, Discord readiness, timer, or local workflow state.

### Merge policy

1. A valid remote completion with no pending/local divergence is adopted. The engine
   emits `COMPLETE_MATCH_FROM_PROVIDER`; it does not write station, Discord, overlay,
   or dispatch fields directly.
2. A remote result matching a locally pending command verifies that command and changes
   `sync_status` from `acknowledged_unverified` to `synced`.
3. A remote result differing from a local pending or completed result becomes
   `conflict`; it never silently overwrites either side.
4. Remote `void`, deleted, invalid, cancelled, or missing matches become
   `needs_review`, not automatic Hub completion. A reopen after downstream matches have
   progressed also becomes `needs_review` until an organizer applies a policy.
5. A stale snapshot, lower remote revision, or older observation cannot undo a newer
   command or snapshot.
6. A remote non-terminal observation updates provider-owned state and bracket metadata
   only. It does not downgrade Hub `called`, `ready`, or `in_progress`.
7. A new Challonge `open` match creates `hub_status=available`; it can be called
   locally but is not automatically live. `pending` is `not_started` until two sides
   resolve. Start.gg native `CALLED`/`IN_PROGRESS` uses only Start.gg policy.
8. Local Challonge call/ready/start updates Hub and Discord axes and sets
   `sync_status=local_only`; it makes no lifecycle request. A remote score/DQ command
   first enters the command ledger, then becomes terminal only through completion.
9. Snapshots never reassign `is_stream_match` or station. The completion service frees
   only a station still bound to that exact match, then updates overlay, Discord, and
   newly available matches idempotently.

### Repair migration

For rows whose tournament has `provider_type='challonge'`, run a one-time idempotent
repair after a fresh successful snapshot:

- Populate raw and normalized provider state from that snapshot.
- Change only rows with `hub_status_origin='provider_sync'` (or legacy rows proven to
  have no call/start time, Discord thread, readiness, station, score, or local action
  audit) from false `in_progress` to `not_started` when remote state is `open`.
- Preserve every Start.gg row and every Challonge match with actual Hub-workflow proof.
- Emit a report with tournament, match key, prior status, remote state, new status, and
  eligibility reason. It offers a dry-run preview and never cleans a station.

## Provider Command Ledger and Verified Completion

Only **provider-backed remote operations** are durable in the Provider Command Ledger
before they are sent. Hub-local Call, Ready, station, and workflow transitions commit
through the Hub workflow/audit path and create no provider command. `200 OK` for a
provider command means only that a request was acknowledged; it does not mean aiTOB has
verified score, winner, advancement, and remote match state.

| Ledger state | Meaning |
|---|---|
| `pending` | Intent persisted with match, provider, idempotency key/payload digest, expected result, and precondition revision. |
| `sending` | A worker owns the attempt; leases make crash recovery safe. |
| `acknowledged` | Provider accepted/responded, awaiting an authoritative snapshot. |
| `snapshot_verified` | Snapshot matches expected score, winner, advancement, and state; terminal effects may complete. |
| `retryable` | Transient network, timeout, 429, or authorized retry failure; scheduled with provider-local backoff. |
| `permanent_failure` | Validation/permission/unsupported failure; no local completion. |
| `conflict` | Remote result differs from expected/current result. |
| `needs_review` | Ambiguous recovery, void/deletion, unsafe reopen, or unresolved dependent bracket effect. |

The ledger has a durable client idempotency key where the provider supports one. Where it
does not, the worker uses provider match ID, payload digest, observed revision, and a
post-timeout snapshot before retrying; it must never blindly submit the same result
twice. All command status is visible to the organizer and survives restart.

The reconciliation engine emits domain decisions such as
`COMPLETE_MATCH_FROM_PROVIDER`, `INVALIDATE_CALL_FOR_CHANGED_ENTRANTS`, and
`NEEDS_REVIEW`. A single idempotent Completion Service consumes completion decisions:

1. records final result and Hub status;
2. verifies the station still belongs to that match before releasing it;
3. broadcasts the correct overlay update;
4. updates/archive-notifies the correct Discord thread once;
5. discovers newly eligible matches and permits their local call workflow.

Repeated snapshots and reprocessed events must not repeat a Discord mention, release a
different match's station, or create duplicate threads.

Hub workflow and its local external effects use a separate durable `workflow_outbox`.
The same SQLite transaction that records a local transition writes its intended Discord,
thread, warning, OBS, match-message-close, or next-match announcement event with
`event_id`, `match_id`, `event_type`, payload, `deduplication_key`, status, attempts,
`next_attempt_at`, and `completed_at`. The outbox worker retries idempotently after a
crash, so `hub_status=called` cannot survive without an eventually delivered or visibly
failed Call effect.

## Bidirectional Reconciliation and Recovery

The organizer may change a tournament directly in Start.gg or Challonge. Every provider
snapshot therefore detects and reconciles, rather than only pushing aiTOB-originated
changes:

- remote score, DQ/forfeit, reset/reopen, deletion/cancellation, and tournament end;
- changed entrants, seeds, bracket structure, rounds, and downstream opponents;
- newly completed matches and the next matches that become two-sided/available.

When a valid remote result has no conflicting local command, Completion Service adopts
it, releases its own station if still bound, updates Discord/OBS, and makes subsequent
matches callable. When entrants change, a stale call is invalidated safely: its old
deadline/thread is retained for audit, the old players receive no further prompts, and
new Discord notifications require verified identity links.

On startup, aiTOB restores and resumes:

- called matches, ready timestamps, attendance deadlines, station bindings, overlay
  intent, Discord thread/message references, and local notifications;
- the latest successful snapshot and each command ledger entry that is pending,
  acknowledged-but-unverified, retryable, conflict, or needs review;
- provider-local retry/backoff state and sync freshness.

During Internet/provider/token/rate-limit failure, local call, readiness, timer,
station, overlay, and operator workflow remain available. Only remote operations stay
clearly `pending`, `retrying`, `failed`, or `needs_review`; aiTOB never presents them as
complete. A Challonge outage/429/token failure cannot pause Start.gg, and vice versa.

## Participant Identity Mapping

Create a durable identity-link model rather than resolving Discord users from display
names. Each link joins `provider_type + provider participant/entrant ID` to an aiTOB
participant identity and optionally one or more Discord users/roles, with source,
verification state, timestamps, and tournament scope. It supports teams as distinct
entities and retains aliases/history when a name changes.

No Discord mention is sent solely because two display names match. A missing or
ambiguous link makes the match locally callable only after the organizer links or
explicitly overrides the intended recipients; the event is audited.

## Challonge Result and DQ Policy

The published Challonge bracket must show a recognizable DQ outcome, not only an
aiTOB badge. The adapter owns a `ForfeitPolicy`:

- Start.gg keeps `reportBracketSet(..., isDQ: true)` and does not use generic `-1`.
- Challonge has no verified native DQ flag in the current adapter. The candidate public
  convention is winner `0`, DQ side `-1` (slot-aware), with winner/advancing participant
  explicit in the v2.1 match payload. It must not ship as `1-0`.
- Before enabling it for any production event, test a disposable Challonge tournament,
  refetch the match, and visually confirm the published bracket's score and advancement.
- If that sandbox fails or upstream cannot represent it, Challonge DQ stays
  `unavailable` and the UI directs the organizer to resolve it in Challonge. It never
  marks local DQ as remotely accepted.

The v2.1 adapter sends its documented JSON:API resource type/attributes, not legacy
`scores_csv`. Payload assembly and score orientation remain in
`backend/core/providers/challonge/`, with request-shape tests.

## Synchronization and API-budget Plan

### Coordinator contract

Introduce `API Budget & Sync Coordinator` as the sole gateway to provider reads and
mutations. A provider adapter declares how to execute a scope, its expected cost,
minimum interval, cache policy, revision/conditional-request support, and its own rate
limit constraints; it does not decide when UI/Discord callers may bypass the coordinator.

Every read uses the coalescing key:

```text
provider + provider_account_id + tournament_id + snapshot_scope
```

The first compatible request starts one upstream operation. Concurrent dashboard, bot,
Discord, and manual requests join that operation and receive the same persisted result.
Compatibility is coverage-aware, not literal scope equality: an in-flight
`advancement_neighborhood` may satisfy a `single_match` request it includes, and a
`full_snapshot` may satisfy narrower requests only when its freshness/revision and
requested entities cover them. The coordinator stores a scope coverage graph plus
actual entity/range coverage in the in-flight record; it starts another upstream call
only for an uncovered requirement.

The coordinator applies single-in-flight-per-tournament, short debounce, a provider
minimum sync interval, and provider-safe `force=true` only for an authorized organizer;
force cannot bypass an upstream rate limit or backoff.

### Modes and adaptive cadence

**Economy is the default.** It has no periodic polling and may synchronize only on
initial import, explicit `Sync Bracket`, result/DQ command, recovery of a pending
command, first open after stale data, or transition into Live mode. Refreshing the
dashboard, opening a Match Card, reading a Discord status, pressing Ready, calling a
match, assigning a station, opening a thread, or updating OBS is local-only SQLite work.
Because direct changes at a provider are not discovered automatically in Economy mode,
every tournament dashboard visibly shows **Last provider sync**, **Data freshness**, and
**Sync now**. The organizer chooses Live mode during active operation when automatic
remote-change discovery is required.

**Live mode** uses adaptive scheduling, with values stored in tournament/provider
settings rather than hard-coded. An adapter may impose a stricter minimum:

| Tournament condition | Default scheduling policy |
|---|---|
| No active/pending matches | Every 10–15 minutes |
| One or more `called` / `ready` matches | Every 5 minutes |
| One or more `in_progress` matches | Every 2–5 minutes, constrained by budget |
| `acknowledged` result awaiting verification | Targeted fast verification, then backoff |
| Complete or archived tournament | No polling |
| Dashboard closed and bot idle | Automatically reduce cadence |

### Smallest sufficient snapshot scope

The coordinator selects only the information needed for an operation:

```text
tournament_metadata | participants | bracket_structure | active_matches |
single_match | result_verification | advancement_neighborhood | full_snapshot
```

After a result, prefer `single_match`, result/winner/advancement verification, and the
affected next match or matches (`advancement_neighborhood`). A full participant/page or
full-bracket read is prohibited unless the adapter cannot fetch a narrower scope, the
first import occurs, bracket structure changes, a revision gap/conflict requires it, a
long outage demands recovery, or the organizer explicitly requests Full Sync.

### Verification, cache, and incremental policy

After acknowledgement, verification is `wait/debounce → targeted scope →
snapshot_verified`. The default retry schedule is configurable and adapter-overridable:
`5s → 15s → 30s → 60s → 2m`, capped by attempts/budget. A later compatible snapshot
cancels redundant verification. Exhaustion becomes `acknowledged_unverified`, never
infinite polling or repeated mutation.

Cache entries have independent TTL/invalidation policy for tournament metadata,
participants and identity links, completed matches, open/active matches, bracket
structure, provider capabilities, public URLs, and rate-limit state. Completed matches
are not reprocessed unless a newer revision/`updated_at` proves they changed.

Adapters declare `supports_incremental_sync`, `supports_conditional_requests`,
`supports_webhooks`, `supports_targeted_match_fetch`, and the previously declared remote
revision/idempotency capabilities. When unsupported, they return a budgeted snapshot and
the coordinator compares durable local hashes/revisions; the Hub never assumes an
incremental API exists.

### Budget, priority, and telemetry

Persist provider-account budget state: `window_started_at`, `estimated_used`,
`remaining_if_known`, `reset_at`, `backoff_until`, and `last_429_at`. Each planned
operation declares estimated cost `cheap`, `normal`, or `expensive` and a reason/scope.
Priority is: result/DQ command, verification, pending-command recovery, active-match
sync, manual sync, background refresh, then noncritical metadata. Near a limit, stop
background freshness first; do not discard an essential result command merely because a
dashboard refresh was expensive.

Record request count by provider, account, tournament, reason, scope, method/path, and
outcome. It is aiTOB's estimate; the provider portal remains account-wide truth. A 429
pauses only that provider/account and does not halt the other provider or Hub-local work.

## API, UI, and Bot Changes

### API contracts

- `GET /api/active-matches` and cached set responses add provider identity, the four
  state axes, command-ledger summary, eligibility, and action projection without secrets.
- All mutations go through a `MatchCommandService` that resolves tournament and
  capability before creating a durable command and any provider work. `CompletionService`
  alone performs terminal Hub/Discord/station/overlay effects.
- Before score, DQ/forfeit, reset, or reopen is admitted, `MatchCommandService` checks
  snapshot freshness. A stale local match requests at most one coalesced targeted
  preflight snapshot; changed entrants/state rejects the mutation or returns
  `needs_review`, and provider unavailability retains a local draft without sending an
  unsafe mutation.
- Compatibility routes remain, but summaries/messages become provider-neutral. A
  capability rejection is structured 409/422 with capability, provider, and safe reason.
- `/verify-stream` and `/streams` return local-only results for a provider without a
  remote stream queue; neither calls Challonge in this release.

### Dashboard

- Remove `mapStartggState` from provider-neutral rendering. Render Hub, provider, and
  sync state from the server; show Discord details/timer in a dedicated local-workflow
  panel rather than collapsing them into one badge.
- Display textual provider badge plus `Hub:`, provider-state, and sync-status chips when
  they differ; pending/acknowledged commands must be visible.
- In Economy mode, show `Last provider sync`, derived `Data freshness`, and a visible
  `Sync now` control. Never imply direct provider changes are live until that refresh;
  Live mode is the explicit choice for automatic discovery during an active event.
- Render actions from API projection. Challonge Call/Ready/Start/Station are clearly
  local; Score is remote; DQ is remote only after release flag; Reset and double-DQ
  explain why unavailable.
- Station occupancy shows owning tournament/provider and never attributes a Start.gg
  station to a Challonge import.

### Discord / bot

- Keep Discord call/readiness provider-neutral.
- Replace generic-flow literal `startgg_*` commands with provider-neutral events that
  dispatch to an adapter hook only when capability permits it.
- Auto-DQ checks capabilities first. Unsupported Challonge double-DQ pauses and asks
  the organizer rather than choosing a technical winner.
- Persist timers/messages/thread IDs and make Discord effects idempotent across restart
  and repeated snapshots. Mention resolution uses verified identity links only.

## Exact Source Areas Expected to Change

| Area | Planned change | Start.gg safety boundary |
|---|---|---|
| `backend/core/contracts/tournament_types.py` | Add raw/normalized state, progression, capabilities, action/result types. | Additive types; retain mappings. |
| `backend/core/contracts/tournament_provider.py` | Replace implicit no-op methods with declared capabilities and typed commands. | Start.gg declares its existing support. |
| `backend/core/providers/registry.py` | Register adapter metadata/factories only. | Registry is the allowed provider-name switch. |
| `backend/core/providers/startgg/{provider.py,client.py,queries.py}` | Adapt to contract without changing GraphQL semantics. | Regression tests freeze lifecycle/DQ/stream behavior. |
| `backend/core/providers/challonge/{provider.py,client.py,mapper.py,state_map.py}` | v2.1 raw mapping, payload builder, DQ policy, participant cache, local-only declarations. | No import/mutation of Start.gg code. |
| `backend/core/provider_sync_manager.py`, `backend/core/sync_coordinator.py` (new) | Sole provider gateway: scoped snapshots, coalescing, adaptive scheduler, caches, budget, priority, backoff, telemetry. | Separate provider/account keys and failure state; consumers read SQLite only. |
| `backend/core/database_schema.py`, `backend/core/database.py` | Four state axes, remote-command ledger, local workflow audit/outbox, identity links, migration report, provider-safe merge. | Migration predicates Challonge-only. |
| `backend/core/match_state.py` | Hub workflow only; move terminal effects to completion service. | Explicit Start.gg transition handler. |
| `backend/core/match_commands.py`, `backend/core/completion_service.py`, `backend/core/workflow_outbox.py` (new) | Remote command verification plus local-effect outbox/recovery and idempotent terminal effects. | Provider-neutral orchestration; adapters remain isolated. |
| `backend/core/score_reporting.py` | Typed report/forfeit and post-result sync policy. | No provider-name special case. |
| `backend/api/routers/matches.py` | Command service, capability errors, local stream path. | No remote stream call unless declared. |
| `backend/api/routers/tournaments.py`, `providers.py`, `main.py` | Neutral serialization, lifecycle/sync policy delegation. | Existing Start.gg API compatibility test. |
| `backend/api/schemas.py` | Non-secret response/action/error types. | Additive fields. |
| `frontend-react/src/store/useHubStore.ts` | Type provider state/action projection. | Existing Start.gg shape accepted. |
| `frontend-react/src/features/hub/components/{MatchDashboard.tsx,MatchCard.tsx,MatchSettingsModal.tsx,TournamentSettings.tsx,StationSettingsModal.tsx}` | Capability-driven controls/copy/state chips. | Start.gg controls remain from projection. |
| `backend/bot/{main.py,match_threads.py,bracket_sync.py}` | Neutral command dispatch/capability-aware auto-DQ. | Existing handlers stay tested. |

## Test and Release Plan

### Automated tests

1. Provider contract suite: every adapter passes read/result/capability/error tests;
   unsupported commands make zero remote calls.
2. Start.gg regression: existing score, `isDQ`, call, active, reset, stream queue,
   bot/check-in, and overlay tests run unchanged with no Challonge dependency.
3. Challonge mapper: v2.1 `points_by_participant`, pending/open/complete/raw-state,
   unresolved/TBD, URL/community, pagination, and cache TTL fixtures.
4. Reconciliation: local call/start versus remote `open`, matching remote result,
   conflicting remote result, void/deletion, stale snapshot, unsafe reopen, four
   false-FNC-like records, and migration preserving Start.gg/stream bindings.
5. Command/API: rejected DQ does not complete local row; local Challonge call makes no
   remote lifecycle call; remote score schedules one sync; station toggle makes no
   Challonge call.
6. Recovery/idempotency: crash after provider acknowledgement, duplicate submit,
   restored timer/thread/station, pending command retry, and no duplicate Discord effect.
7. Identity/UI/build: no name-only mention, changed entrants invalidate old call,
   buttons/copy follow projection, state chips explain ownership, Hide TBD remains, and
   `npm run build` passes.

### Required acceptance criteria

The feature is not complete until all of the following pass in controlled tests:

1. A player follows the Challonge bracket while receiving a Hub-owned Call in Discord.
2. A result entered in aiTOB appears at the owning provider and snapshot-verifies the
   winner, result, advancement, and final provider state.
3. A result entered directly at either provider closes the correct aiTOB match through
   Completion Service, with no duplicate Discord/station effects.
4. A crash after provider acceptance but before a local response/save recovers the
   ledger, snapshots the match, and resolves it as verified, retryable, or reviewable.
5. Repeating Send Result does not duplicate a mutation, whether the provider supports
   idempotency directly or aiTOB must resolve a timeout by snapshot.
6. Restart resumes calls, Ready state, attendance timer, station/overlay intent,
   Discord references, pending/retrying commands, last snapshot, and conflicts.
7. A Challonge outage, expired token, or 429 does not halt Start.gg; a Start.gg outage
   does not halt Challonge. Hub-local workflows continue with their true sync state.
8. Differing local and remote results become conflict; neither is silently replaced.
9. Reopen after downstream bracket progress is `needs_review`, not automatic rollback.
10. Call, Ready, and station state survive even when the provider cannot model them.
11. Repeated sync does not re-send Discord notifications or duplicate a thread.
12. Changed entrants invalidate an old Call safely and block notifications to former
    opponents until verified identities are linked.
13. No Discord mention is selected from a name match alone.
14. Refreshing a dashboard or Match Card ten times causes zero provider requests.
15. Simultaneous Sync requests from UI, bot, and Discord create one compatible upstream
    operation; a manual sync during it joins the same work unless an authorized scope
    expansion is genuinely required.
16. Local-only Call, Ready, station, Discord thread, and OBS actions create zero provider
    requests, even under repeated player interaction.
17. When targeted match fetch exists, post-result verification avoids full-bracket and
    participant requests; participant pages remain cached inside their TTL unless an
    invalidating change is observed.
18. A complete/archived tournament polls zero times; an affected provider 429 stops only
    its polling and leaves other providers' essential result commands available.
19. Request telemetry reports provider, account, tournament, reason, scope, cost, and
    outcome for every admitted provider operation.

### Manual sandbox gate

Use a disposable Challonge tournament, never FNC production:

1. Start a known bracket and sync once.
2. Call/start locally; public Challonge remains `open` until a result.
3. Send normal score; fetch and inspect published bracket.
4. Test DQ in both slots using `0/-1`; confirm display, rank, and advancement.
5. Test rejected score/DQ, token expiry, and quota response; Hub must remain
   non-terminal with safe error.
6. Run Start.gg regression tournament in parallel and verify no stream/station/control
   behavior changed.

Enable Challonge DQ only after every sandbox check passes. Otherwise leave it disabled
with an organizer instruction.

## Delivery Sequence

1. Add the four state axes, capability/action contracts, durable local projection, and
   API Budget & Sync Coordinator behind a feature flag; no behavior change.
2. Route existing Start.gg reads through the Coordinator, prove coalescing/cache/budget
   behavior, then wrap Start.gg in the new contract and prove its lifecycle, DQ, stream, Discord, and
   station behavior did not change.
3. Add the command ledger, recovery worker, idempotent Completion Service, and identity
   links; prove restart/duplicate-submit behavior before any new provider write path.
4. Move Challonge read/snapshot mapping and bidirectional reconciliation to the new
   contract; run a read-only FNC repair preview.
5. Enable Hub-local calls, readiness, Discord, station, and OBS for Challonge; prove
   zero remote Challonge lifecycle/stream calls.
6. Implement score reporting through the ledger and verify it by snapshot, including
   provider-originated score/DQ/reopen/entrant changes.
7. Test Challonge DQ in a disposable sandbox. Enable it only after both-slot public
   bracket verification succeeds.
8. Review the dry-run repair report with organizer, then apply to Challonge rows only;
   never alter `testfnc` station assignment.
9. Keep Economy as default. Add Live polling only later, per tournament, after telemetry
   and failure-isolation checks.

## Risks and Explicit Non-goals

- A public Challonge `DQ` label is not assumed; the visible `-1` convention is tested.
- Challonge native station/stream queue and reopen/reset are out of this release even
  if documentation hints at related resources; each needs a future capability decision.
- No automatic Challonge double DQ. The organizer chooses the bracket outcome.
- Existing Start.gg station usage is not data corruption and is unchanged by repair.

## Project Structure

```text
backend/
├── api/routers/                 # Provider-neutral Hub endpoints
├── core/contracts/              # Provider, capability, command types
├── core/providers/
│   ├── startgg/                 # Start.gg-only GraphQL adapter
│   └── challonge/               # Challonge-only v2.1 adapter and policy
├── core/provider_sync_manager.py
├── core/match_state.py          # Hub workflow after refactor
└── tests/                       # Contract, sync, migration, API regressions

frontend-react/src/
├── features/hub/components/     # Capability-driven dashboard/cards/settings
└── store/                       # Typed API projection
```

**Structure Decision**: Retain the monorepo. Provider behavior lives under
`backend/core/providers/<provider>/`; orchestration talks only to
`backend/core/contracts/`, never a sibling adapter.

## Complexity Tracking

| Added element | Why needed | Simpler alternative rejected because |
|---|---|---|
| Capability/action projection | Prevents unsupported remote calls and extends UI. | Scattered provider-name checks regress with a third provider. |
| Separate remote and Hub states | Explains local workflow without corrupting source state. | One state column already created false live Challonge matches. |
| Provider-local sync policy | Protects quota and isolates 429 failures. | Global timer/backoff couples providers. |
| Sandbox DQ gate | Makes public bracket display trustworthy. | Guessed `1-0`/`-1` can advance or display wrong side. |
