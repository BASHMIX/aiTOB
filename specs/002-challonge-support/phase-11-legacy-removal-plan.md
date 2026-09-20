# Phase 11 Legacy Provider Path Removal Plan

**Feature**: `002-challonge-support`  
**Task**: T075  
**Prepared**: 2026-09-20  
**Status**: In progress; not yet eligible to close

## Implementation checkpoint — 2026-09-20

- Saved the full pre-implementation working tree on `main` as commit
  `9991bb4` before changing Phase-11 behavior.
- Fixed the pre-existing `station_to_advance` initialization failure. The
  Start.gg activation-preflight baseline now passes 7/7 tests.
- Added durable per-entrant Start.gg attendance fields and one shared
  `AttendanceCommandService`. Organizer DQ controls now map `p1|p2` to
  `withdrawn` without sending `winnerId`, completing the match, or advancing a
  bracket. Manual `both` is rejected for Start.gg and remains absent for
  Challonge.
- Converted the deprecated `auto_dq_match()` entry point into a harmless
  review-only shim so an old callback cannot issue `mark_dq()` or fabricate a
  Double-DQ technical winner.
- Updated both React match-card surfaces to show `Present`/`Withdrawn`, removed
  `Both Players`, and stopped presenting the local ten-minute value as a
  Start.gg timer. When no provider deadline is available the cards explicitly
  show `Start.gg` as the timer owner.
- The official public Start.gg schema documents `markSetCalled(setId)`,
  `markSetInProgress(setId)`, and result reporting, but no per-entrant
  attendance mutation. Live `testfnc` evidence proved that
  `reportBracketSet(isDQ:true)` without a winner does not close a set. The
  accepted bridge protects the first verified attendee with a verified
  `markSetInProgress`, starts Hub play only after both attend, and never
  fabricates a winner for zero attendance.
- Live observation of disposable `tournament/testfnc` proved the neither-present
  native path: Start.gg moved two `CALLED` sets to `COMPLETED`, returned
  `displayScore="DQ"`, selected its own `winnerId`, and advanced/completed the
  bracket without any aiTOB timeout mutation. The Event exposed
  `checkInBuffer=900`, matching the organizer-observed 15-minute timer, but no
  public absolute Set deadline. A reset follow-up with a one-minute round timer
  proved an unprotected called set auto-completed at about 66 seconds, while a
  set protected with provider `IN_PROGRESS` remained open. A verified
  single-player DQ then completed that protected set and advanced its attendee.
  The both-attendee score/broadcast and live outage recovery still keep T073 open.
- Focused verification passed: provider/lifecycle, attendance/recovery safety,
  ActiveMatchCard, and production frontend-build checks. The full suites remain
  non-green for pre-existing unrelated fixture/schema and stale frontend-test
  assumptions; see the quickstart run record. T075 remains unchecked until
  those baselines, T073, PostgreSQL, and direct-provider inventory gates pass.

## Outcome

Phase 11 will leave one production provider path:

- consumer code reads provider data through a provider gateway backed by the
  `SyncCoordinator`;
- consumer code requests remote mutations through `MatchCommandService`, which
  writes the durable command ledger before the adapter is called;
- one account- and workspace-scoped registry owns adapter construction and
  shutdown;
- API, bot, workflow, registration, and projection code do not import concrete
  provider classes or clients;
- the legacy `ITournamentProvider` / `ITournamentProviderV2` split, the unused
  V2 factory registry, the Start.gg global-credential fallback, and rollout
  flags that have completed acceptance are removed.

The `V2` suffix on durable database functions and stored schema is not by
itself a second runtime path. Renaming persisted repositories is outside this
task unless required to remove an actual fallback.

## Closure gates

T075 must remain open until every gate below passes.

1. **Working-tree baseline**: the pre-existing `station_to_advance` failure was
   fixed on 2026-09-20 and the focused activation-preflight suite passes 7/7.
   The full repository baseline is still not green: 17 backend tests fail in
   pre-existing setup-schema/fixture and stale lifecycle expectations, while 6
   frontend tests fail because old tests omit a Router or expect an obsolete
   confirmation message. These failures must be resolved or formally isolated
   before Phase 11 closure.
2. **T073 rollout evidence**: the remaining disposable Start.gg live-adapter
   acceptance is recorded, or an explicit constitution-approved exception with
   equivalent evidence is documented. Automated parity alone does not satisfy
   the currently written T073 gate.
3. **Attendance/DQ policy consistency**: the product decision was confirmed on
   2026-09-20. Start.gg called matches accept independent per-entrant attendance
   intents (`present | withdrawn`) from verified Discord self-service or an
   authorized organizer. A withdrawal is not an immediate DQ and does not select
   a winner. The first `present` is protected remotely with verified
   `markSetInProgress`, while Hub play/broadcast stay called until the second
   entrant appears. At the mirrored deadline exactly one present entrant is
   advanced by a verified single-player DQ; neither present remains native
   Start.gg double-DQ. Challonge has no equivalent native
   attendance window: it exposes organizer-approved immediate single-player DQ
   only, represented as loser `-1` / advancing player `0`, and every Challonge UI
   surface hides `both`. aiTOB never fabricates bracket progression. Start.gg
   double-DQ must be implemented only through provider-owned behavior proven
   against a disposable tournament. The 2026-09-20 `testfnc` run proved the
   neither-present provider-owned DQ closure and downstream progression without
   an aiTOB mutation. Start.gg still returned a `winnerId`, so that field is
   provider progression data, not evidence that aiTOB selected a technical
   winner.
   The live matrix now proves native neither-present and protected
   exactly-one-present behavior. T073 must still prove both-present score/live
   behavior and outage recovery. The entrant-1 technical-winner fallback
   remains forbidden. `markSetCalled` accepts only `setId`; because the public
   API exposes no round DQ Timer, `provider_dq_timer_seconds` is an explicitly
   labeled organizer mirror, separate from local/Challonge `dq_timer_seconds`.
   T066, T073, the Phase 10 runbook, capability projection, tests, and deployment
   configuration must be reconciled with this decision before rollout flags are
   removed. AI-DQ and automatic DQ remain prohibited.
4. **PostgreSQL source of truth**: runtime and acceptance use PostgreSQL. SQLite
   is permitted only for isolated unit tests and migration/recovery fixtures.
   Outdated Phase 2/Phase 10 references to a runtime "SQLite projection" must be
   corrected to "durable PostgreSQL projection".
5. **No unsafe pending effects**: no unknown provider mutation may be resent
   during cutover. Pending/sending/acknowledged commands are verified or placed
   in `needs_review`, and outbox work is drained or explicitly held.

## Current runtime inventory

### Contracts and registry

| Area | Current symbols | Finding | Required change |
|---|---|---|---|
| `backend/core/contracts/tournament_provider.py` | `ITournamentProvider`, `ITournamentProviderV2` | Both concrete adapters implement both contracts. V2 reads are live, while V2 command execution is not used. | Replace the two runtime interfaces with one canonical adapter contract. |
| `backend/core/contracts/tournament_types.py` | `ProviderCapabilitiesV2`, `ProviderSnapshotRequestV2`, `ProviderCommandV2` | Snapshot/capability types are live. `ProviderCommandV2` is not dispatched to adapters. | Keep compatible data shapes initially; add a typed in-memory mutation request if needed by the command executor. |
| `backend/core/providers/registry.py` | `_providers`, `get_provider()`, `get_provider_for_tournament()` | Mixes a provider-type singleton with newly constructed account-bound adapters. Account-bound clients are not owned by `shutdown_providers()`. | Replace with one factory/descriptor registry and an account-scoped adapter lifecycle. |
| `backend/core/providers/registry.py` | `_provider_v2_factories`, `register_provider_v2_factory()`, `get_provider_v2_factory()` | Test-only dark registry; no runtime registration or resolution. | Delete after the canonical registry tests exist. |
| `backend/core/providers/startgg/client.py` | `get_client()`, `AITOB_LEGACY_PROVIDER_FALLBACK` | Process-global Start.gg client can read legacy global credentials. | Move connection/identity probes behind account-scoped services and remove the fallback. |

### Read paths

| Consumer | Affected functions | Current direct dependency | Migration target |
|---|---|---|---|
| `backend/core/provider_sync_manager.py` | `sync_bracket()` | Resolves an adapter, branches on flags/interface type, and calls `fetch_sets()` or `fetch_snapshot_v2()`. | `ProviderGateway.fetch_snapshot()` only; V2 snapshot behavior becomes unconditional. |
| `backend/core/match_state.py` | `_startgg_targeted_snapshot()`, `transition_match()`, `auto_dq_match()` | Resolves adapters and performs targeted reads directly. | Move preflight/verification to the gateway and remote actions to command service. Keep local state transitions provider-free. |
| `backend/core/match_commands.py` | `_provider_for_match()`, `_targeted_snapshot()`, `_verify_score()` | Resolves adapters and supplies `fetch_snapshot_v2()` lambdas itself. | Gateway owns resolution and coordinator admission. |
| `backend/core/challonge_resolution.py` | `ChallongeResolutionService.resolve()` | Constructs `ChallongeProvider` directly, though the call is coordinator-wrapped. | Resolve through registry/gateway; gateway owns adapter close/reuse. |
| `backend/api/routers/tournaments.py` | `api_add_tournament()`, `api_refresh_tournament()`, `api_tournament_game_metadata()`, `api_verify_tournament_stream()` | Constructs/resolves providers and calls tournament, catalog, and stream reads. | Provider discovery/metadata services backed by gateway snapshot scopes. |
| `backend/api/routers/tournament_setup.py` | `materialize_setup_draft()` | Resolves provider and calls `fetch_tournament()`. | Gateway metadata/roster snapshot. |
| `backend/api/routers/player_registration.py` and `backend/core/registration_sync.py` | `recheck_registration()`, `recheck_provider_roster()` | Injects an adapter and calls `fetch_tournament()`; imports provider mappers. | Provider-neutral roster snapshot returned by gateway/discovery adapter. |
| `backend/api/routers/tournaments.py` | `api_provider_profile()` | Constructs an adapter for a local capability response. | Registry descriptor/capability projection without an HTTP client. |
| `backend/api/routers/providers.py` | `provider_capabilities()` | Uses unbound `get_provider()`. | Registry descriptor/capability projection. |

The snapshot contract needs explicit scopes (or typed gateway operations) for
event game metadata, stream lists, and registration rosters so these reads do
not escape through ad-hoc adapter methods.

### Mutation paths

Every row below is a remote external effect and must have a durable command
record before dispatch, including Start.gg operations.

| Consumer | Affected functions | Current mutation | Migration target |
|---|---|---|---|
| `backend/core/match_commands.py` | `submit_score()` | Calls `provider.report_score()` after writing a Challonge command. | Call canonical `adapter.execute_command()` through command service; support Start.gg too. |
| `backend/core/score_reporting.py` | `report_score_to_provider()` | Calls `report_score()` and `report_winner_only()`; default global provider fallback remains. | Delete or reduce to a compatibility wrapper during migration, then remove. No winner-only fallback after an unknown outcome. |
| `backend/core/match_state.py` | `transition_match()` | Calls `mark_in_progress()` directly. | Typed `mark_in_progress` command with preflight and postflight verification. |
| `backend/core/match_state.py` | `auto_dq_match()` | Calls state read, `mark_dq()`, or `mark_double_dq()` directly. | Automatic DQ remains prohibited; any manual action uses command service and declared capability. |
| `backend/api/routers/matches.py` | `_sync_provider_stream()`, `_remove_provider_stream()` | Calls `assign_stream()` / `remove_stream()` directly. | Typed stream command or explicit local-only capability. |
| `backend/api/routers/matches.py` | `api_send_match()` | Start.gg score uses legacy reporting; Challonge uses command service. | One command-service score path for both providers. |
| `backend/api/routers/matches.py` | `api_reset_match()`, `api_dq_match()` | Calls `reset_set()`, `mark_dq()`, and `mark_double_dq()` directly. | Command service with capability, ledger, verification, and review outcomes. |
| `backend/bot/match_threads.py` | `_create_startgg_checkin_thread()` | Calls `mark_called()` directly after a Discord call. | Typed `mark_called` command; Discord workflow remains local/outbox-owned. |
| `backend/core/tournament_lifecycle.py` | `run_tournament_lifecycle()` | Calls provider-specific start/reset methods via `getattr()`. | Typed tournament-lifecycle command with capability projection and verification. |
| `backend/api/routers/settings.py`, `backend/api/main.py` | token probe functions | Import global Start.gg client; the probe intentionally emits a dummy mutation. | Account-scoped `ProviderConnectionService`; explicit audit and no startup probe by default. |

### Concrete-provider imports outside adapter packages

The architecture test must distinguish network adapters from pure provider
format parsers, then minimize both. Current imports needing removal or an
explicit boundary include:

- `backend/api/routers/tournaments.py` -> `StartGGProvider`;
- `backend/api/routers/settings.py`, `backend/api/main.py`, and
  `backend/bot/main.py` -> Start.gg global client;
- `backend/core/challonge_resolution.py` -> `ChallongeProvider` and Challonge
  client errors;
- `backend/api/routers/providers.py` and `backend/api/routers/tournaments.py` ->
  Challonge client errors;
- `backend/api/routers/tournament_setup.py` -> provider-specific remote-start
  and wave-monitor classes;
- `backend/core/provider_discovery.py` -> concrete discovery adapters;
- `backend/core/registration_sync.py` -> provider-specific entrant mappers.

Provider-specific construction may remain only inside the provider registry and
provider adapter/discovery packages. API and bot code must consume neutral
services and neutral error types.

### Feature flags and public projections

After acceptance, remove these migration-only controls and all branches/tests
that expose them:

- `PROVIDER_V2_CONTRACTS_ENABLED`;
- `PROVIDER_COORDINATOR_ENABLED`;
- `AITOB_LEGACY_PROVIDER_FALLBACK`.

Also update:

- `backend/core/provider_feature_flags.py`;
- `.env.example` and deployment templates;
- `backend/api/schemas.py` feature-status fields;
- `backend/api/routers/tournaments.py` import gating;
- `backend/core/score_reporting.py` verification gating;
- `backend/tests/test_provider_feature_flags.py` and
  `backend/tests/test_startgg_feature_flag_compatibility.py`.

`CHALLONGE_READ_ENABLED`, `CHALLONGE_LOCAL_WORKFLOW_ENABLED`, and
`CHALLONGE_SCORE_COMMANDS_ENABLED` may be removed only after T073 evidence makes
their enabled state the supported baseline. `CHALLONGE_DQ_COMMANDS_ENABLED`
may become an always-supported manual single-player capability only after
T066's sandbox evidence and documentation are reconciled with the confirmed
`-1/0` policy. Double-DQ stays unavailable.

The external API may retain a stable `contract_version` value for client
compatibility, but it must no longer select between two runtime implementations.

## Target architecture

### Canonical adapter contract

Create one internal contract (name illustrative):

```python
class TournamentProviderAdapter(Protocol):
    provider_type: str
    provider_name: str
    capabilities: ProviderCapabilitiesV2

    async def fetch_snapshot(
        self, request: ProviderSnapshotRequestV2
    ) -> ProviderSnapshotV2: ...

    async def execute_command(
        self, command: ProviderMutationRequest
    ) -> ProviderCommandResultV2: ...

    async def close(self) -> None: ...
```

Legacy granular methods may remain temporarily as private adapter helpers, but
no consumer can call them. Provider parity tests move to snapshots and typed
commands.

### Registry and adapter lifecycle

The registry stores immutable descriptors and factories. Runtime adapters are
keyed by trusted `(workspace_id, provider_type, provider_account_id)`, never by
provider type alone. It must:

- reject missing or cross-workspace account binding;
- expose local capabilities without constructing an HTTP client;
- reuse an account-bound adapter so connection pools and rate-limit state are
  not recreated per request;
- close every constructed adapter during API/bot shutdown;
- contain the only provider-name-to-class switch.

### Provider gateway

`ProviderGateway` owns adapter resolution plus `SyncCoordinator`. Callers submit
a trusted tournament identity and snapshot request; they never receive an
adapter or pass an operation lambda. This makes it mechanically testable that
all provider reads are budgeted and coalesced.

### Command service

`MatchCommandService` (or a generalized provider command service) owns:

1. trusted workspace/tournament/match resolution;
2. capability and local/remote policy;
3. authoritative preflight through `ProviderGateway`;
4. durable command creation and payload digest;
5. exactly one initial adapter dispatch;
6. acknowledgement recording;
7. snapshot verification/reconciliation;
8. `needs_review` on unknown outcomes, never blind resend;
9. completion/outbox effects only after verification.

Score, forfeit, mark-called, mark-in-progress, reset, stream assignment, and
tournament lifecycle commands must all follow this invariant.

### Bracket authority, attendance, and DQ intent

The provider is the sole source of truth for provider-owned bracket state:
remote match state, result, DQ/forfeit state, winner, entrant advancement, and
new downstream matches. aiTOB owns its operational workflow fields such as
calls, readiness, Discord, stations, overlays, command state, and sync state.
Its purpose is to make requested transitions easy and auditable, not to run a
parallel bracket engine.

The canonical Start.gg called-window command is per-entrant attendance:

```text
SetAttendance(set_id, entrant_slot = p1 | p2, state = present | withdrawn)
```

- Discord self-service requires the actor's verified entrant link; organizer
  manual actions require the corresponding permission. Both sources use the same
  command and audit/ledger path.
- Start.gg exposes no documented per-entrant attendance mutation. aiTOB records
  each decision locally; the first `present` uses verified
  `markSetInProgress` as a set-level protection bridge. `withdrawn` sends no
  result by itself.
- Challonge exposes immediate DQ targets `p1` and `p2`; `both` is absent from
  capability projection and hidden in every client.
- An acknowledgement means only that the provider accepted the transition.
  aiTOB projects no remote completion, winner, advancement, or player outcome
  until a newer provider snapshot confirms it.
- Start.gg double-DQ must never fall back to entrant 1 (or entrant 2) as a
  technical winner. The expected native path is `markSetCalled`, zero or more
  per-entrant attendance transitions, the provider-owned timer, then a fresh
  provider snapshot. If native check-in or per-entrant attendance propagation is
  unavailable, rejected, or has an unknown outcome, the command becomes
  failed/`needs_review` and the prior authoritative bracket projection remains
  intact.
- The Start.gg adapter does not send a timeout value. The organizer mirrors the
  round DQ Timer in `provider_dq_timer_seconds`; setup/settings label it as a
  mirror that cannot modify Start.gg. It drives aiTOB reminders and the agreed
  exactly-one-present check, while zero attendance remains native provider truth.

## Implementation sequence

### 0. Stabilize and freeze the baseline

- Resolve/isolate the current `station_to_advance` baseline failure without
  overwriting unrelated working-tree edits.
- Save the direct-call inventory and current test counts.
- Reconcile T066/runbook evidence with the confirmed manual Challonge `-1/0`
  DQ policy before treating the production flag as an accepted baseline.
- Confirm disposable PostgreSQL, provider accounts, Discord test destination,
  and no unsafe pending command/outbox work.

### 1. Add failing architecture and invariant tests

Create `backend/tests/test_provider_architecture.py` with AST-based checks:

- no API/bot module imports `backend.core.providers.*` or registry functions;
- no non-boundary core module imports concrete provider/client classes;
- no runtime reference to `ITournamentProvider`, `ITournamentProviderV2`,
  V2 factory functions, or migration flags after cleanup;
- every remote mutation test observes a ledger insert before adapter dispatch;
- every snapshot test observes coordinator admission;
- account/workspace binding fails closed;
- adapter shutdown closes all cached account-bound clients.

Use a narrow allow-list for the registry, adapter packages, and explicit
provider discovery/connection boundaries. Do not use a broad path exemption
that lets future consumers bypass the gateway.

### 2. Introduce the canonical registry, adapter, and gateway

- Add the canonical adapter contract and neutral provider errors.
- Replace provider-type singleton storage with descriptor factories and
  account-scoped adapter ownership.
- Add `ProviderGateway.fetch_snapshot()`.
- Update both adapters to implement canonical names while preserving internal
  helpers and frozen upstream request shapes.
- Add lifecycle/shutdown tests before migrating callers.

### 3. Migrate all reads

- Migrate sync manager and targeted match reads first.
- Add typed snapshot operations for metadata, streams, event game catalog, and
  roster reads.
- Migrate tournament import/refresh/setup, registration recheck, provider
  profiles, resolution, and stream verification.
- Move provider error translation into neutral boundary services.
- Remove consumer access to adapter instances.

### 4. Migrate all mutations

- Implement typed adapter command dispatch for Start.gg and Challonge.
- Unify score/forfeit submission first because ledger and verification already
  exist there.
- Migrate mark-in-progress and mark-called.
- Migrate reset/DQ and stream assignment/removal. Add a typed Start.gg
  per-entrant attendance command shared by Discord and organizer controls;
  retain a separate immediate single-player DQ result command for Challonge.
- Remove the current Start.gg `mark_double_dq()` behavior that sends entrant 1
  as a technical winner. Implement `p1`, `p2`, and `both` as Start.gg transition
  intents and do not ship a synthetic-winner fallback. For `both`, first validate
  the existing native path (`markSetCalled` -> provider attendance timer -> fresh
  provider snapshot) in the disposable T073 tournament; use a separate immediate
  operation only if Start.gg explicitly supports and acceptance proves it.
- Project Start.gg attendance states/actions separately from result actions.
  Project Challonge `dq_targets=[p1,p2]`. Make Match Dashboard, On-Stream, and
  Discord consume the same projection so an attendance withdrawal is never
  presented or dispatched as an immediate Start.gg result.
- Add post-command snapshot tests proving that acknowledgement alone changes no
  provider-owned local bracket field and that winner, progression, downstream
  matches, and player outcome come only from reconciliation.
- Add a disposable Start.gg native-wave matrix: both players check in, only P1
  checks in, only P2 checks in, and neither checks in. Record the `markSetCalled`
  request, pre/post-expiry snapshots, provider DQ/winner fields, downstream
  bracket result, and confirm that aiTOB sends no timeout DQ mutation of its own.
- Inspect the authorized Start.gg schema/response during T073 for a native
  check-in deadline or duration. Add a typed provider-timer projection when it
  exists; otherwise project an unknown provider-managed timer and remove the
  hard-coded `10-minute` claim from `backend/bot/match_threads.py`. Prove that
  `dq_timer_seconds` cannot alter the Start.gg request or determine completion.
- Migrate tournament lifecycle operations.
- Prove timeout-after-send reconciliation for every mutation family and prove
  that no recovery path resends an unknown operation.

### 5. Migrate connection, identity, and setup helpers

- Replace global Start.gg token probe/client use with an account-scoped
  connection service.
- Replace bot bio verification with a workspace/account-scoped identity
  service.
- Put discovery adapters, entrant mapping, remote-start availability, and wave
  monitoring behind neutral services so architecture rules stay enforceable.

### 6. Remove dual paths and expired controls

- Delete `get_provider()`, direct consumer use of
  `get_provider_for_tournament()`, `_providers`, and the V2 factory registry.
- Delete `ITournamentProvider` and `ITournamentProviderV2`; export only the
  canonical adapter contract.
- Remove flag branches only after their evidence gate passes.
- Remove `AITOB_LEGACY_PROVIDER_FALLBACK` and global credential lookup.
- Remove obsolete compatibility tests and replace them with one-path contract,
  architecture, account isolation, and parity tests.
- Update stale comments and runbook references from SQLite runtime to
  PostgreSQL runtime.

### 7. Verification and cutover

Run, in order:

1. provider contract/parity, registry, gateway, coordinator, command ledger,
   reconciliation, recovery, outbox, local workflow, and architecture tests;
2. complete backend unit suite with explicit test storage;
3. complete disposable PostgreSQL suite with `--postgres`, including concurrent
   command claims, workspace isolation, and restart recovery;
4. frontend tests and `npm run build`;
5. `git diff --check` and an inventory scan proving no forbidden imports/calls;
6. T073 disposable mixed-provider acceptance, including Start.gg live read and
   one approved mutation, Challonge result verification, provider outage,
   restart, conflict, rollback, Discord/outbox, and Browser Source evidence.

No production provider or Discord destination is used for acceptance.

## Required test updates

At minimum, the refactor affects:

- `backend/tests/core/providers/test_registry.py`;
- `backend/tests/core/providers/test_tournament_provider_v2_contract.py`
  (replace with canonical contract tests);
- `backend/tests/core/providers/startgg/test_provider_parity.py`;
- Challonge snapshot/result/forfeit provider tests;
- `backend/tests/test_startgg_v2_read_gateway.py` (replace with unconditional
  canonical gateway tests);
- `backend/tests/test_provider_capability_projection.py`;
- `backend/tests/test_provider_commands.py`;
- `backend/tests/test_startgg_activation_preflight.py`;
- `backend/tests/test_score_reporting.py`;
- `backend/tests/test_challonge_local_workflow.py`;
- API tests for Start.gg `AttendanceRequest` (`p1|p2`, `present|withdrawn`),
  verified Discord/organizer authorization, and Challonge-projected
  `dq_targets=[p1,p2]`;
- `frontend-react/src/features/hub/components/DQPlayerMenu.tsx`,
  `MatchCard.tsx`, and `ActiveMatchCard.tsx`, including tests that Start.gg shows
  per-entrant Present/Withdraw controls while Challonge shows DQ P1/DQ P2 and
  hides Double-DQ everywhere;
- `backend/tests/test_player_result_submission_safety.py`;
- `backend/tests/test_verify_stream.py`;
- `backend/tests/test_character_catalog_workflow.py`;
- `backend/tests/test_provider_feature_flags.py`;
- `backend/tests/test_startgg_feature_flag_compatibility.py`;
- every test that monkeypatches `get_provider_for_tournament()` or
  `get_provider()`.

## T075 definition of done

T075 can be marked complete only when all are true:

- T073's required rollout evidence is complete or explicitly superseded by an
  approved equivalent gate;
- T066, DQ configuration, capability projection, and runbook all match the
  confirmed manual single-player Challonge `-1/0` policy;
- one canonical adapter contract exists and both old interfaces are absent;
- the dark V2 registry and provider-type singleton are absent;
- API, bot, workflow, and registration consumers have zero direct concrete
  provider/client imports and zero direct adapter calls;
- all remote reads enter through the gateway/coordinator;
- all remote mutations create a durable command before dispatch and reconcile
  unknown outcomes without resend;
- Start.gg attendance commands express per-entrant `present | withdrawn`
  intent without selecting a winner; Challonge DQ exposes only `p1 | p2`, and
  no acknowledgement directly mutates provider-owned bracket truth;
- no global provider credential fallback remains;
- adapter lifecycle closes every account-bound client;
- PostgreSQL, full regression, frontend, architecture, and disposable external
  acceptance evidence are recorded in `quickstart.md`;
- the final direct-provider inventory is empty outside the documented provider
  boundaries.
