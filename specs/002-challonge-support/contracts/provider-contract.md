# Provider Contract Changes

## Provider identity

Every `ITournamentProvider` implementation exposes:

```python
provider_name: str                 # "start.gg" or "challonge"
capabilities: ProviderCapabilities
```

`ProviderCapabilities` contains named action descriptors rather than unqualified
booleans. Every descriptor has `kind` (`remote`, `local`, `unavailable`), a safe
reason, and permitted Hub lifecycle states. It covers `fetch_bracket_structure`,
`fetch_participants`, `fetch_match_updates`, `report_score`, `report_forfeit`,
`reset_match`, `reopen_match`, `native_check_in`, `mark_called`, `mark_in_progress`,
`assign_stream`, `fetch_incremental_changes`, `supports_remote_revision`,
`supports_idempotency`, `match_attachments`, and any legacy compatibility aliases.

`remote` means the adapter has a verified upstream operation. `local` means aiTOB may
perform its own Discord/station/OBS workflow and must report it as local. `unavailable`
means callers must neither make a provider call nor claim local completion. Provider
names may not be used as a substitute for this projection.

## Canonical identifiers

All generic callers pass `set_id` as the Hub canonical match key. The registry resolves the owning tournament/provider, and that adapter translates its stored `provider_set_id` into the remote request. Generic callers must not parse provider-specific identifiers.

## Required operations

Existing operations stay provider-agnostic:

```python
fetch_tournament(identifier) -> ProviderTournament | None
fetch_sets(identifier, *, options) -> list[ProviderSet]
fetch_set_state(provider_set_id) -> ProviderSetState | None
report_score(provider_set_id, winner_id, entrant1_id, entrant2_id, score1, score2) -> ProviderSetResult
report_winner_only(provider_set_id, winner_id) -> ProviderSetResult
mark_dq(provider_set_id, winner_id) -> ProviderSetResult
```

The command result contains `outcome: remote_applied | local_only | unavailable |
rejected`, `new_state`, `result_kind`, expected snapshot evidence, and a safe
error/reason. Remote commands first create a durable command-ledger entry; an adapter
acknowledgement changes it to `acknowledged`, while only a matching snapshot changes it
to `snapshot_verified`. Unsupported operations return `unavailable` before any upstream
call. A rejected/unverified remote operation never allows generic code to mark the Hub
result complete.

## Challonge mapping requirements

`ChallongeProvider` maps remote tournament, participant, and match records into `ProviderTournament`, `ProviderEntrant`, and `ProviderSet`.

- A bye or unresolved opponent maps to a non-actionable set with a missing entrant.
- Remote IDs remain opaque strings.
- Remote match state maps to the normalized state enum **and preserves its exact raw
  value** plus a provider observation/revision timestamp when available.
- Provider errors distinguish authorization, not-found, rate-limit, validation, and transient network failures.
- Pagination is entirely internal to the provider.

## Startup readiness contract

`sync_tournament(tournament)` returns an explicit result containing provider, tournament
key, success state, count of observed sets, a coalescing/request-budget summary, and a
redacted error when applicable. The startup sequence may mark the bot match tools ready
only after each tracked tournament has a success result or is explicitly unavailable. A
stale/failed result blocks provider-backed match action and is displayed to the
organizer.

## Budget-aware snapshot contract

Only the Sync Coordinator may invoke an adapter. It requests a named scope:
`tournament_metadata`, `participants`, `bracket_structure`, `active_matches`,
`single_match`, `result_verification`, `advancement_neighborhood`, or `full_snapshot`.
The adapter maps that scope to the fewest valid upstream calls and returns cache/revision
evidence plus estimated cost (`cheap`, `normal`, `expensive`). It declares its minimum
interval and whether it supports incremental sync, conditional requests, webhooks,
targeted match fetch, remote revision, and idempotency.

The adapter cannot be called by a React/API/Discord/Bot consumer. The coordinator owns
coverage-aware coalescing (not literal scope matching), budget admission, retry/backoff,
and priority; local consumers read the persisted projection. An in-flight broad scope
may satisfy a narrower request only when it covers the requested entity/range and has
sufficient revision/freshness. Adapters that lack a narrow API must declare a budgeted
full snapshot rather than conceal that cost.

## Reconciliation hook

Each provider supplies a reconciliation policy that receives a `ProviderSet` snapshot,
Hub match, pending-command summary, and prior snapshot revision. It detects remote
results, DQs, reopen/reset, changed entrants/seeds/structure, cancellation/deletion,
newly available downstream matches, and tournament completion. The policy returns an
auditable domain decision rather than writing SQL directly. A valid non-conflicting
remote completion can emit `COMPLETE_MATCH_FROM_PROVIDER`; void/deleted/invalid and
unsafe reopen emit `NEEDS_REVIEW`; divergent results emit `CONFLICT`. Start.gg owns its
native call/active side effects; Challonge `open` is ready-to-call and cannot make a
match live.

## Challonge forfeit release gate

`mark_dq` is declared `unavailable` for Challonge until its v2.1 forfeit payload passes
a disposable-tournament test in both participant slots. The verified implementation
must use the documented JSON:API `match` resource entries, not `scores_csv`, and return
the public-bracket score convention separately from Start.gg's native `isDQ` mutation.
