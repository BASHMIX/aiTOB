# Phase 11: Deferred legacy-path removal

**Feature:** `002-challonge-support`

**Task:** T075

**Updated:** 2026-09-22

**Status:** Complete

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

## Completed implementation

1. `ITournamentProvider` is the single provider contract. The parallel V2
   interface, factory, and compatibility branches were deleted.
2. One workspace/account-scoped registry owns adapter construction, caching,
   and shutdown in both API and bot processes.
3. Provider reads use `SyncCoordinator`; production consumers resolve adapters
   from trusted tournament/account bindings.
4. Match and tournament mutations persist a durable command before provider
   I/O. Unknown outcomes remain acknowledged-unverified and are never blindly
   resent.
5. Migration-only provider flags were removed. Challonge rollout gates remain
   because they still represent real product enablement decisions.
6. Start.gg evidence covers native zero-attendee DQ, protected single attendance,
   both-present automatic live state, score submission, and outage recovery.
7. Feature 004 now enforces non-null ownership, required foreign keys, and
   workspace-scoped uniqueness on PostgreSQL.

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

## Closure verification

Verified on 2026-09-22:

- Backend: `584 passed, 1 skipped`, executed in bounded batches against cloned,
  disposable PostgreSQL databases. The final targeted closure suite adds
  `31 passed` after the tournament-lifecycle change; a final contract,
  runtime-gate, and durability rerun adds `26 passed`.
- Feature 004 schema contracts: `4 passed`, without exclusions.
- Provider contract/registry/schema subset: `68 passed`.
- Frontend: `50 passed`; the production TypeScript/Vite build succeeds.
- Python compilation, whitespace checks, and static scans succeed.
- Live `testfnc` remains the disposable Start.gg record for native deadline
  handling. Hermetic provider tests cover both-present/live, score,
  unknown-outcome, and recovery without repeating destructive bracket writes.

These are dated verification results, not a permanent expected count. Newer
runs replace them; do not weaken the suite to preserve the number.
