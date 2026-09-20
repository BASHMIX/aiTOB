# Phase 11: Deferred legacy-path removal

**Feature:** `002-challonge-support`

**Task:** T075

**Updated:** 2026-09-20

**Status:** Open

## Objective

Finish with one provider contract and one production path for provider reads,
mutations, construction, and shutdown. Remove the remaining V1/V2 split only
after the canonical path has equivalent automated and disposable-provider
evidence.

## Decisions already settled

- PostgreSQL is the only runtime, test, backup, restore, and maintenance store.
  The embedded adapter, dependency, migration utilities, fixtures, and stored
  database artifacts have been removed.
- A provider is the source of truth for bracket state and progression. aiTOB
  sends an authorized intent, records it durably, and reconciles the resulting
  provider state. It never invents a winner to satisfy a mutation.
- Provider state, Hub lifecycle, entrant attendance, and broadcast state are
  separate axes.
- A match becomes `live` automatically when both entrants are present. A
  stream-designated match is not sent live merely because one entrant checked
  in.
- Start.gg attendance is recorded per entrant as `present` or `withdrawn`.
  Organizer controls and verified Discord self-service use the same attendance
  command service.
- For Start.gg, neither entrant present remains on the native provider-owned
  Double-DQ path. With exactly one attendee at the deadline, the verified
  single-player DQ path may advance that attendee. There is no entrant-1
  technical-winner fallback.
- Challonge permits organizer-approved single-player DQ only, represented by
  loser `-1` and advancing entrant `0`. Every Challonge surface hides
  Double-DQ.
- Automatic or AI-selected DQ is prohibited. Timeout handling verifies and
  reconciles provider state; it does not guess an external result.

## Completed prerequisites

- The application, test harness, dependencies, and operational scripts are
  PostgreSQL-only.
- Start.gg per-entrant attendance and the shared
  `AttendanceCommandService` are implemented.
- Match cards expose `Present` and `Withdrawn`; they do not expose a synthetic
  Start.gg Double-DQ command.
- The obsolete auto-DQ callback cannot mutate a bracket or fabricate a winner.
- `broadcast_state` distinguishes queued/ready/live/ended presentation from the
  provider and Hub match states.
- Disposable `testfnc` evidence established native Start.gg zero-attendee
  closure and verified single-attendee protection/progression behavior.
- The Start.gg global-credential fallback is not an accepted account-bound
  runtime path.

## Remaining implementation

1. Replace `ITournamentProvider` and `ITournamentProviderV2` with one canonical
   provider contract. Preserve behavior while moving consumers; do not add a
   third compatibility interface.
2. Replace the dark V2 factory registry and ad-hoc provider singletons with one
   workspace/account-scoped registry that owns adapter construction and
   shutdown.
3. Route provider reads through the gateway/`SyncCoordinator`. API, bot,
   workflow, registration, and projection code must not construct or import a
   concrete provider/client directly.
4. Route remote mutations through the durable command service. Persist the
   command before calling the adapter and verify unknown outcomes before any
   retry.
5. Remove migration-only provider flags after all consumers use the canonical
   path. Keep product rollout gates only where a real dark-launch decision still
   exists.
6. Complete disposable Start.gg evidence for both-present score/live behavior
   and for provider outage/recovery reconciliation.
7. Resolve the outstanding Feature 004 PostgreSQL schema contracts:
   non-null workspace ownership for `integration_accounts` and
   `ai_usage_ledger`, required foreign keys, and workspace-scoped unique
   constraints.

## Closure gates

Phase 11 closes only when all of the following are true:

- No production consumer imports or constructs `StartGGProvider`,
  `ChallongeProvider`, `StartGGClient`, or `ChallongeClient` outside the single
  registry/composition boundary.
- `ITournamentProviderV2`, its factory map, and compatibility branches are
  deleted; one contract remains.
- Reads use the coordinator and remote mutations use the durable command
  service, including recovery and unknown-outcome handling.
- Automated provider contract, lifecycle, attendance, reconciliation, and
  outage tests pass on PostgreSQL.
- Disposable-provider acceptance covers score submission, both-present
  automatic live state, single-player withdrawal, native zero-attendee DQ, and
  outage recovery.
- The Feature 004 schema contract suite passes without exclusions.
- Static scans find no embedded-database runtime/dependency/configuration path
  and no retired provider fallback.
- The backend suite, frontend suite, and production frontend build are green.

## Current verification baseline

After the PostgreSQL-only conversion on 2026-09-20:

- Backend excluding the known Feature 004 schema-contract file:
  `581 passed, 1 skipped`.
- The three remaining failures are the schema-contract items listed above; they
  are not embedded-database compatibility failures.
- Frontend: `50 passed`; production build succeeds.
- Python compilation and whitespace checks succeed.

These numbers are a dated baseline, not a permanent expected result. Newer test
runs replace them; do not weaken the suite to preserve the count.
