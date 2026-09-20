# Tasks: Provider-isolated tournament operations and Challonge support

**Input**: Design documents in `specs/002-challonge-support/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`  
**Tests**: Tests are required by the feature specification. Write the relevant tests
first, observe them fail, then implement the corresponding task.

**Safety rule**: Do not enable a Challonge behavior or change existing Start.gg behavior
until the phase checkpoint explicitly allows it. No task may expose credentials.

## Phase 1: Setup and frozen Start.gg baseline

**Purpose**: Establish evidence of current Start.gg behavior before adding the new
foundation. This phase has no runtime behavior change.

- [X] T001 Inventory every direct provider call and current Start.gg lifecycle/stream/DQ path in `backend/core/match_state.py`, `backend/core/score_reporting.py`, `backend/api/routers/matches.py`, `backend/bot/main.py`, and `backend/bot/match_threads.py`.
- [X] T002 [P] Add baseline Start.gg lifecycle, DQ (`isDQ`), reset, stream-queue, station, Discord, and overlay regression tests in `backend/tests/test_startgg_provider_baseline.py` and `backend/tests/test_startgg_workflow_baseline.py`.
- [X] T003 [P] Add fake-provider HTTP transports and reusable provider snapshot fixtures in `backend/tests/core/providers/conftest.py` and `backend/tests/core/providers/fixtures/`.
- [X] T004 [P] Add a feature-flag configuration model with every new provider-runtime flag defaulting disabled in `backend/core/provider_feature_flags.py`, `backend/api/schemas.py`, and `.env.example`.
- [X] T005 Record the executable baseline commands and expected no-regression result in `specs/002-challonge-support/quickstart.md`.

**Checkpoint**: Run the baseline suite and `npm run build`; record the result. No new
feature flag is enabled and existing Start.gg responses/actions remain byte-compatible
where contracts require compatibility.

---

## Phase 2: Foundational contracts, durable projection, ledger, and Coordinator

**Purpose**: Add the new architecture behind feature flags while preserving current
Start.gg runtime behavior. This phase blocks all provider behavior migrations.

- [X] T006 [P] Define provider capabilities, snapshot scopes, scope coverage, cost class, action projection, four-axis state, command, reconciliation decision, and completion types in `backend/core/contracts/tournament_types.py`.
- [X] T007 [P] Define `ITournamentProviderV2` alongside the legacy provider interface for scoped snapshots, capabilities, typed remote commands, revisions, and idempotency evidence in `backend/core/contracts/tournament_provider.py`; do not change existing Start.gg consumers while flags are disabled.
- [X] T008 [P] Write V2-only contract tests for capability rejection, targeted scopes, raw state, revision evidence, and no direct V2 consumer provider call in `backend/tests/core/providers/test_tournament_provider_v2_contract.py`.
- [X] T009 Add additive migrations in `backend/core/database_schema.py` in separately testable schema-addition and real-old-database upgrade-fixture steps, with backup guidance for four-axis fields, provider command ledger, `workflow_outbox`, reconciliation audit, identity links, provider budget, and snapshot cache. Do not backfill, reinterpret, or write legacy records in Phase 2; defer any backfill to a reviewed later phase.
- [X] T010 Add transactional repositories and read models in `backend/core/database.py` for those fields/tables, including atomic Hub-workflow plus `workflow_outbox` writes, without changing reads from legacy `status` while flags are disabled.
- [X] T011 Write migration/idempotency tests proving legacy Start.gg rows, streams, stations, and status are unchanged with flags disabled in `backend/tests/test_provider_foundation_migration.py`.
- [X] T012 Implement coverage-aware in-flight records and scope containment rules in `backend/core/sync_coordinator.py`.
- [X] T013 Implement budget admission, per-provider/account backoff, configurable minimum intervals, priority ordering, request telemetry, and durable cache metadata in `backend/core/sync_coordinator.py`.
- [X] T014 [P] Write Coordinator tests for join/coalesce, covered narrower scope, uncovered entity/range, debounce, manual `force`, 429 isolation, and priority in `backend/tests/test_sync_coordinator.py`.
- [X] T015 Create the durable command-ledger repository/worker interfaces and lease recovery primitives in `backend/core/provider_commands.py` and `backend/core/database.py`.
- [X] T016 Create provider-safe registry factories that expose capabilities without moving existing behavior behind flags in `backend/core/providers/registry.py`.
- [X] T017 Add feature-flag-gated API schemas for provider state, Hub state, Discord state, sync state, command summary, freshness, and action projection in `backend/api/schemas.py`.
- [X] T018 Verify the Phase 2 flags leave all existing Start.gg routes and bot paths on the baseline code path in `backend/tests/test_startgg_feature_flag_compatibility.py`.

**Checkpoint**: The schema, contracts, ledger, cache, budget, and Coordinator exist but
are dark. Run the full Start.gg baseline suite again. Do not proceed if any Start.gg
result, station, stream queue, Discord call, or overlay behavior changed.

---

## Phase 3: User Story 3 - Manage both providers safely (Priority: P2)

**Goal**: Establish safe adapter isolation and feature-flagged Start.gg migration before
enabling new Challonge behavior.

**Independent Test**: With flags off, a Start.gg tournament is indistinguishable from
baseline. With the isolated-contract flag on in a test database, it declares the same
capabilities and produces the same GraphQL calls/results without any Challonge import.

- [X] T019 [P] [US3] Write Start.gg adapter parity tests for fetch, call, active, score, DQ, reset, stream assignment, and unsupported errors in `backend/tests/core/providers/startgg/test_provider_parity.py`.
- [X] T020 [US3] Adapt `StartGGProvider` to the new capability, scoped-snapshot, command-result, revision, and idempotency contracts in `backend/core/providers/startgg/provider.py`.
- [X] T021 [US3] Route Start.gg provider reads through the Coordinator behind `PROVIDER_COORDINATOR_ENABLED` while preserving legacy fallback in `backend/core/provider_sync_manager.py` and `backend/core/sync_coordinator.py`.
- [X] T022 [US3] Move Start.gg-specific GraphQL payloads, check-in semantics, DQ `isDQ`, and stream queue behavior behind adapter-only helpers in `backend/core/providers/startgg/client.py` and `backend/core/providers/startgg/queries.py`.
- [X] T023 [US3] Expose saved provider identity/capabilities without secret data in `backend/api/routers/tournaments.py`, `backend/api/routers/providers.py`, and `backend/api/schemas.py`.
- [X] T024 [US3] Render provider badge and capability-safe labels while retaining Start.gg controls from server action projection in `frontend-react/src/store/useHubStore.ts` and `frontend-react/src/features/hub/components/TournamentSettings.tsx`.

**Checkpoint**: Re-run T002 baseline and T019 parity tests with the Start.gg adapter
contract enabled. Freeze this regression baseline before enabling any Challonge flag.

---

## Phase 4: User Story 6 - Load Challonge tournaments from common identifiers (Priority: P1)

**Goal**: Resolve secure Challonge identifiers through the Coordinator and persist one
stable provider identity without direct UI/provider calls.

**Independent Test**: Numeric ID, normal URL, subdomain URL, and legacy identifier
resolve to one durable tournament record, with no empty community scope and no secret in
the request, browser payload, or log.

- [X] T025 [P] [US6] Write locator tests for numeric IDs, URLs, optional subdomains, legacy input, malformed credentials, and duplicate resolution in `backend/tests/core/providers/challonge/test_locator.py`.
- [X] T026 [P] [US6] Write v2.1 client tests for headers/redaction, pagination, scoped reads, conditional requests, rate-limit response, and no URL secret in `backend/tests/core/providers/challonge/test_client.py`.
- [X] T027 [US6] Refactor `ChallongeClient` into adapter-only scoped read/mutation primitives with no UI-facing direct access in `backend/core/providers/challonge/client.py`.
- [X] T028 [US6] Implement stable locator resolution and community-aware numeric-ID persistence in `backend/core/providers/challonge/locator.py`, `backend/core/providers/challonge/provider.py`, and `backend/core/database.py`.
- [X] T029 [US6] Add Coordinator-backed resolve/import endpoints and session-safe validation in `backend/api/routers/providers.py`, `backend/api/routers/tournaments.py`, and `backend/api/schemas.py`.
- [X] T030 [US6] Update the provider selector/preview to read local connection state and call Hub endpoints only in `frontend-react/src/features/hub/components/TournamentSettings.tsx` and `frontend-react/src/store/useHubStore.ts`.

---

## Phase 5: User Story 1 - Connect and synchronize a Challonge tournament (Priority: P1) 🎯 MVP

**Goal**: Import and read a Challonge bracket through scoped, budgeted snapshots into the
local durable projection; no Challonge lifecycle mutation is enabled.

**Independent Test**: A mocked bracket with pending, open, complete, bye, changed
entrants, and downstream matches appears correctly from SQLite after one admitted sync;
ten dashboard reads add no provider requests.

- [X] T031 [P] [US1] Write Challonge v2.1 mapper fixtures for `points_by_participant`, raw state, unresolved entrants, progression, revisions, and two-side eligibility in `backend/tests/core/providers/challonge/test_mapper.py`.
- [X] T032 [P] [US1] Write scoped snapshot/cache tests for participant TTL, `single_match`, advancement neighborhood, full-snapshot fallback, and covered coalescing in `backend/tests/core/providers/challonge/test_snapshot_scopes.py`.
- [X] T033 [US1] Implement ProviderSet raw/normalized state, progression, revision, and identity-safe participant mapping in `backend/core/providers/challonge/mapper.py` and `backend/core/providers/challonge/state_map.py`.
- [X] T034 [US1] Implement Challonge capability declarations and scope translation, including targeted fetch fallback policy, in `backend/core/providers/challonge/provider.py`.
- [X] T035 [US1] Persist provider-owned snapshot data, last successful snapshot, freshness, cache coverage, and no false `open → in_progress` mapping in `backend/core/database.py`.
- [X] T036 [US1] Implement Coordinator-backed Economy sync triggers (import, explicit sync, stale first open, recovery) and no periodic poll in `backend/core/provider_sync_manager.py` and `backend/core/sync_coordinator.py`.
- [X] T037 [US1] Return cached bracket and provider freshness from `GET /api/tournaments/{slug}/sets` and add explicit sync routing in `backend/api/routers/tournaments.py`.
- [X] T038 [US1] Show `Last provider sync`, `Data freshness`, `Sync now`, provider state, and Economy/Live explanation in `frontend-react/src/features/hub/components/MatchDashboard.tsx` and `frontend-react/src/features/hub/components/TournamentSettings.tsx`.

**Checkpoint**: Challonge read/sync is available in Economy mode. Dashboard/Match Card
refreshes are SQLite-only and no Call/Ready/station action invokes Challonge.

---

## Phase 6: User Story 5 - View one consistent tournament progression (Priority: P1)

**Goal**: Display progression and all four state axes without conflating bracket facts,
Hub operations, Discord workflow, and synchronization uncertainty.

**Independent Test**: Start.gg and Challonge fixtures show identical canonical
progression concepts while a local Challonge call remains `provider=open`,
`hub=called`, and `sync=local_only`.

- [X] T039 [P] [US5] Write progression/four-axis serialization tests including conflict-with-live and stale revision cases in `backend/tests/test_tournament_progression_and_state_axes.py`.
- [X] T040 [US5] Create provider-neutral progression and state projection serializers in `backend/core/tournament_progression.py`, `backend/core/database.py`, and `backend/api/routers/tournaments.py`.
- [X] T041 [US5] Add API response types for provider, Hub, Discord, sync, command, and freshness state in `backend/api/schemas.py` and `backend/api/routers/matches.py`.
- [X] T042 [US5] Remove Start.gg-only raw-state mapping from the generic dashboard and render provider/Hub/sync chips plus Discord workflow details in `frontend-react/src/features/hub/components/MatchDashboard.tsx` and `frontend-react/src/features/hub/components/MatchCard.tsx`.
- [X] T043 [US5] Preserve Hide TBD, stage/round sorting, and two-side eligibility while rendering provider-native diagnostics in `frontend-react/src/features/hub/components/MatchDashboard.tsx` and `frontend-react/src/features/hub/components/MatchSettingsModal.tsx`.

---

## Phase 7: User Story 2 - Run a Challonge match through the Hub (Priority: P1)

**Goal**: Run Hub-owned Call/Ready/station/OBS/Discord workflow for Challonge, then send
only verified provider result commands through the Ledger and Completion Service.

**Independent Test**: A Challonge `open` match can be called, made ready, and put on a
local station without provider lifecycle calls. A submitted result creates one command,
is snapshot-verified once, and completes correct local effects.

- [X] T044 [P] [US2] Write command-ledger tests for pending/sending/acknowledged/verified, timeout recovery, idempotency, retryable/permanent failures, conflict, and review states in `backend/tests/test_provider_commands.py`.
- [X] T045 [P] [US2] Write Hub-local Challonge workflow tests proving Call/Ready/station/thread/OBS make zero provider requests in `backend/tests/test_challonge_local_workflow.py`.
- [X] T046 [US2] Implement feature-flagged `MatchCommandService` in `backend/core/match_commands.py` and `backend/api/routers/matches.py`: local-only actions commit through Hub workflow/audit only; provider-backed actions first require a fresh snapshot (or at most one coalesced targeted preflight), reject changed entrants/state as `needs_review`, retain a local draft if unavailable, then create a durable provider command before remote mutation.
- [X] T047 [US2] Refactor `backend/core/match_state.py` so Hub call/ready/in-progress behavior is local and provider writes occur only through Command Service.
- [X] T048 [US2] Implement idempotent `CompletionService` and durable `workflow_outbox` worker in `backend/core/completion_service.py`, `backend/core/workflow_outbox.py`, and `backend/core/database.py`; atomically enqueue Discord call/thread/warning, OBS, close-message, and next-match effects with workflow writes, verify station ownership, and retry/deduplicate effects after failure.
- [X] T049 [US2] Implement reconciliation decisions for matching result, divergent result, void/deletion, reset/reopen, stale snapshot, entrant change, and downstream advancement in `backend/core/reconciliation.py` and `backend/core/provider_sync_manager.py`.
- [X] T050 [US2] Move score reporting/post-result verification scheduling from provider-name conditionals into command/scope policy in `backend/core/score_reporting.py` and `backend/core/sync_coordinator.py`.
- [X] T051 [US2] Implement durable participant/entrant-to-aiTOB-to-Discord links, verification/override workflow, and no-name-only mention guard in `backend/core/identity_links.py`, `backend/core/database.py`, and `backend/bot/match_threads.py`.
- [X] T052 [US2] Replace generic `startgg_*` side effects with provider-neutral workflow events and preserve Start.gg adapter hooks in `backend/bot/main.py`, `backend/bot/match_threads.py`, and `backend/bot/bracket_sync.py`.
- [X] T053 [US2] Project local/remote/unavailable actions, command state, and safe error reasons through `backend/api/routers/matches.py` and `backend/api/schemas.py`.
- [X] T054 [US2] Render local-only Call/Ready/Start/Station, remote result status, pending verification, and unavailable Reset/double-DQ explanations in `frontend-react/src/features/hub/components/MatchCard.tsx`, `frontend-react/src/features/hub/components/MatchSettingsModal.tsx`, and `frontend-react/src/features/hub/components/MatchDashboard.tsx`.
- [X] T055 [US2] Implement v2.1 score payload construction and targeted result verification for Challonge behind `CHALLONGE_SCORE_COMMANDS_ENABLED` in `backend/core/providers/challonge/provider.py` and `backend/core/providers/challonge/client.py`.
- [X] T056 [US2] Write provider score-result request-shape and targeted verification tests, including no legacy `scores_csv`, in `backend/tests/core/providers/challonge/test_provider_results.py`.

**Checkpoint**: Enable only local Challonge operations first. Enable score commands only
after T044–T056 pass in a disposable test environment; no DQ capability yet.

---

## Phase 8: User Story 4 - Start with a current bracket and resume reliably (Priority: P2)

**Goal**: Recover durable operations after restart/outage and safely gate stale provider
operations without blocking local tournament management.

**Independent Test**: Interrupt the process after an acknowledgement, restart, and see
the command resolved exactly once through snapshot verification or an explicit review
state; calls/timers/stations/threads resume.

- [X] T057 [P] [US4] Write restart recovery tests for called matches, Ready timestamps, deadlines, stations, overlays, threads, provider-command leases, `workflow_outbox` pending effects, retry/backoff, and conflicts in `backend/tests/test_provider_recovery.py`.
- [X] T058 [P] [US4] Write mixed-provider outage/429/token-expiry tests proving service and budget isolation in `backend/tests/test_provider_outage_isolation.py`.
- [X] T059 [US4] Implement startup recovery of command leases, timers, snapshot freshness, retry schedule, and review queue in `backend/api/main.py`, `backend/core/provider_commands.py`, and `backend/core/sync_coordinator.py`.
- [X] T060 [US4] Gate only provider-backed operations on freshness/command safety while preserving Hub-local operations during outage in `backend/core/match_commands.py`, `backend/api/routers/matches.py`, and `backend/bot/main.py`.
- [X] T061 [US4] Implement Live-mode adaptive scheduler, idle reduction, complete/archive stop, and transition from Economy mode in `backend/core/sync_coordinator.py` and `backend/core/database.py`.
- [X] T062 [US4] Add organizer-visible sync freshness, retries, review/conflict queue, provider backoff, and Economy/Live state to `backend/api/routers/tournaments.py` and `frontend-react/src/features/hub/components/MatchDashboard.tsx`.

---

## Phase 9: Challonge DQ sandbox and targeted data repair

**Purpose**: Do not enable DQ or alter current FNC rows until remote behavior and
migration evidence are reviewed.

- [X] T063 [P] Write Challonge v2.1 forfeit payload tests for both entrant slots, ranks/advancement, `0/-1`, and unsupported double-DQ/reset in `backend/tests/core/providers/challonge/test_forfeit_policy.py`.
- [X] T064 Implement `ForfeitPolicy` as disabled-by-default provider capability in `backend/core/providers/challonge/forfeit_policy.py` and `backend/core/providers/challonge/provider.py`.
- [X] T065 Execute and record the disposable Challonge sandbox result/DQ verification procedure in `specs/002-challonge-support/quickstart.md` without using the FNC production bracket.
- [ ] T066 Enable `CHALLONGE_DQ_COMMANDS_ENABLED` only after recorded sandbox proof and a feature-flag review in `backend/core/provider_feature_flags.py` and `backend/core/providers/challonge/provider.py`.
- [X] T067 [P] Write dry-run migration tests proving only eligible Challonge false-live rows change and no Start.gg/station row changes in `backend/tests/test_challonge_state_repair.py`.
- [X] T068 Implement reportable dry-run/apply state repair with per-row evidence and organizer acknowledgement in `backend/core/challonge_state_repair.py`, `backend/core/database.py`, and `backend/api/routers/tournaments.py`.
- [X] T069 Review the dry-run report with the organizer and apply it only to approved Challonge rows; do not alter the `testfnc` station assignment in `specs/002-challonge-support/quickstart.md`.

---

## Phase 10: Polish, full acceptance, and controlled rollout

**Purpose**: Prove all documented acceptance criteria and release incrementally.

- [X] T070 [P] Add API/UI tests for Last provider sync, Data freshness, Sync now, and Economy no-auto-discovery messaging in `backend/tests/test_tournament_freshness_api.py` and `frontend-react/src/features/hub/components/MatchDashboard.test.tsx`.
- [X] T071 [P] Add acceptance tests for ten local refreshes, concurrent coalescing, scope coverage, cached participants, no local-only API calls, and complete-tournament polling stop in `backend/tests/test_sync_budget_acceptance.py`.
- [X] T072 Run all provider contract, Start.gg baseline, migration, recovery, API, bot, and frontend build suites through `pytest` and `frontend-react/package.json`; record results in `specs/002-challonge-support/quickstart.md`.
- [ ] T073 Perform the mixed-provider manual acceptance matrix, including provider-originated changes, remote-result conflict, restart recovery, and `workflow_outbox` exactly-once Discord/OBS/station effects, in `specs/002-challonge-support/quickstart.md`.
- [X] T074 Roll out flags in order—foundation dark, Start.gg adapter parity, Challonge read, local Challonge workflow, score verification, DQ after sandbox, then optional Live mode—and document rollback conditions in `specs/002-challonge-support/quickstart.md`.

---

## Phase 11: Deferred legacy-path removal

**Purpose**: Remove dual paths only after rollout evidence proves the V2 contract is
stable; this phase is explicitly deferred and must not begin during initial rollout.

- [ ] T075 Re-run the direct-provider inventory, add an architecture test banning consumer-side provider imports, remove expired feature flags and legacy fallback only after rollout evidence, then rerun the full regression suite in `backend/tests/test_provider_architecture.py`, `backend/core/providers/registry.py`, `backend/core/provider_feature_flags.py`, `backend/core/provider_sync_manager.py`, and `specs/002-challonge-support/quickstart.md`. Execute and close this task against the audited inventory, sequencing, safety gates, and definition of done in `specs/002-challonge-support/phase-11-legacy-removal-plan.md`; do not mark it complete while T073 evidence, the DQ policy/configuration mismatch, a failing provider baseline, or any direct consumer provider path remains.

## Dependencies and execution order

```text
Phase 1 baseline
  → Phase 2 dark foundation
  → Phase 3 Start.gg contract parity (hard release gate)
  → Phase 4 resolver + Phase 5 Challonge read/sync
  → Phase 6 state/progression + Phase 7 Hub operations/result verification
  → Phase 8 recovery/live mode
  → Phase 9 DQ sandbox + data repair
  → Phase 10 full acceptance and rollout
  → Phase 11 deferred legacy removal after stability evidence
```

- US3 blocks every newly enabled provider path because Start.gg parity must be proven.
- US6 and US1 can start after Phase 2, but Challonge read activation waits for US3 gate.
- US5 rendering can proceed after Phase 2 fixtures and joins US1 snapshot work.
- US2 depends on US1/US5 durable read state and the ledger foundation.
- US4 recovery depends on the command ledger, Completion Service, and Coordinator.
- Phase 9 cannot start until score verification is stable; DQ is never part of the MVP.
- Phase 11 is a separate post-rollout decision and requires explicit evidence that every
  consumer uses MatchCommandService and SyncCoordinator.

## Parallel opportunities

- Phase 1: T002, T003, and T004 can run in parallel after T001.
- Phase 2: T006–T008 and T009–T011 can proceed in parallel; T012–T014 can proceed in
  parallel with T015 once the types are agreed.
- Phase 4: T025 and T026 are parallel tests; Phase 5: T031 and T032 are parallel tests.
- Phase 7: T044 and T045 are parallel tests; T051 can proceed alongside T046–T050.
- Phase 8: T057 and T058 are parallel test work. Phase 9: T063 and T067 are parallel.

## Implementation strategy

### Increment 0 — required safety gate

Complete Phases 1–3 only: contracts, fields, command ledger, Coordinator, and feature
flags are present, but Challonge changes are dark and Start.gg has a passing frozen
regression baseline. Stop for review before enabling any new behavior.

### MVP — safe read-only provider integration

Complete Phases 4–6: resolve/import/sync Challonge to SQLite, show freshness and state
axes, and retain Economy as default. This delivers bracket visibility without remote
match lifecycle or score mutation.

### Incremental operations

Complete Phase 7 local workflow first, then score commands with snapshot verification.
Complete Phase 8 recovery/outage support. Only then run Phase 9 sandbox DQ and approved
state repair. Live polling remains opt-in after Phase 10 acceptance.

## Format validation

All 75 tasks use the required checklist format, sequential ID, exact file path, and
story label for user-story phases. `[P]` appears only on tasks intentionally separable
from their neighboring tasks.
