# Research: Challonge Tournament Support

## Decision 1: Use Challonge API v2.1 with header-based authorization

- **Decision**: Add a server-side `ChallongeProvider` backed by API v2.1. For the first release, accept an existing API v1 key through `Authorization-Type: v1` and the `Authorization` header. Keep the connection interface ready for OAuth `Bearer` tokens with `Authorization-Type: v2`.
- **Rationale**: The current July 2026 documentation marks v1/v2.0 endpoints deprecated, identifies v2.1 as current, and explicitly supports existing v1 keys through headers. This preserves the old FNC credential model without preserving its unsafe Basic-auth URL.
- **Alternatives considered**: OAuth authorization-code flow now (better delegated multi-organizer experience, but requires callback, refresh, and consent lifecycle); deprecated v1 endpoints (match the legacy code but miss current group-stage, stations, ties, and stable-ID behavior).

Source: [Challonge API v2.1 schema](https://connect.challonge.com/docs.json).

## Decision 7: Reuse the legacy data flow, not its transport or identity handling

- **Decision**: Preserve the proven sequence from `old FNC index.js`—select a tournament, fetch matches, fetch participants, join by participant ID, and report scores with an explicit winner—but rebuild it on v2.1 with async server-side headers, pagination, stable IDs, normalized provider types, and structured errors.
- **Rationale**: The legacy code demonstrates the required FNC behavior and the importance of matching `player1_id`/`player2_id` to participant objects. However, it embeds credentials in a URL, uses deprecated v1 response wrappers, has no pagination/retry/redaction, and computes provider URLs across route handlers.
- **Alternatives considered**: Port the Express calls literally (unsafe and obsolete); ignore the legacy implementation entirely (would discard the already validated FNC workflow and subdomain requirement).

Legacy findings:

| Legacy behavior | Keep | Replace |
|---|---|---|
| List tournaments and exclude private entries in the UI response | Provider discovery concept | Let authorization and explicit filters drive visibility; do not silently hide a selected private tournament. |
| Append `?subdomain=...` to the tournament list | Need to discover community tournaments | Parse subdomain and resolve it through v2.1 community/tournament discovery. |
| Use returned `tournament.id` for `/matches` and `/participants` | Stable ID traversal | Persist the numeric ID and retain subdomain/slug as display metadata only. |
| Join players by participant ID | Correct relationship strategy | Use an ID map and handle missing/unresolved relationships. |
| PUT `scores_csv` and `winner_id` | Explicit score/winner outcome | Use v2.1 JSON:API match payloads, including ties and group matches. |
| Basic credentials embedded in `apiURL` | Nothing | Store a masked secret server-side and use authorization headers only. |

## Decision 8: Normalize every Challonge locator to a stable numeric tournament ID

- **Decision**: Accept numeric IDs and `challonge.com/{slug}` without any subdomain. Offer subdomain/community as an optional discovery scope for `{subdomain}.challonge.com/{slug}` and legacy `{subdomain}-{slug}` input. Parse into `{numeric_id?, subdomain?, url_slug?}`, resolve once, confirm the tournament preview, and persist the numeric `id` returned by v2.1.
- **Rationale**: Challonge's June 2026 v2.1 upgrade guide says URL was previously used as API identity but can change; v2.1 reverted to integer IDs while still accepting URL lookup. This also fixes the legacy code's inconsistent subdomain handling.
- **Alternatives considered**: Persist only `subdomain-slug` (compatible with v1 but mutable); require users to find the numeric ID manually (safe but poor UX); use tournament name (ambiguous).

Resolution sequence:

1. If input is numeric, fetch directly by ID.
2. If input is a normal URL, normalize path, locale/trailing slash, and URL slug; do not require a community lookup.
3. Only when subdomain/community is present or explicitly selected, resolve its community identifier/ID when authorization permits, then query the scoped tournament collection.
4. Fall back to the documented v2.1 URL lookup form for authorized tournaments.
5. Compare the returned provider numeric ID against existing records before insert.
6. Save numeric ID as canonical; save URL/subdomain only for display and future rediscovery. A missing subdomain remains `null`, not an error.

## Decision 9: Make the provider choice session-scoped but tournament ownership durable

- **Decision**: The import panel stores `selected_provider` and the unsaved form draft in `sessionStorage`. It never rewrites `currentSlug` tournament ownership. Every saved tournament response includes its provider badge, and switching tournaments restores behavior from the server record.
- **Rationale**: The user needs to choose the loading source in each session, while synchronization and mutation must never depend on an ephemeral browser choice.
- **Alternatives considered**: Global provider setting (breaks mixed-provider use); infer solely from pasted URL (fails numeric IDs and can misroute malformed input); persist selected provider indefinitely in localStorage (contradicts per-session choice and hides the decision on later sessions).

## Decision 2: Treat provider capabilities as first-class rather than assuming Start.gg lifecycle semantics

- **Decision**: Extend the provider contract with capability metadata and require API, bot, and frontend callers to use it before exposing mutations.
- **Rationale**: Start.gg has native call/check-in and stream queue concepts that Challonge may not expose in an equivalent form. The Hub can still coordinate Discord readiness and OBS routing locally, but it must never claim a remote state was changed when no provider mutation exists.
- **Alternatives considered**: Add scattered `if provider == ...` checks (hard to audit and prone to regressions); emulate Start.gg states remotely (unsafe and misleading).

## Decision 3: Persist both a local canonical key and the raw provider match ID

- **Decision**: A Hub match will have a provider-safe canonical local key plus a raw remote identifier used only by the owning adapter.
- **Rationale**: The present `active_matches.set_id` is globally primary-keyed and is passed directly to Start.gg. A second provider creates an ID-collision and routing risk. The migration keeps legacy Start.gg keys working and namespaces new provider keys while adapters retain the raw remote ID.
- **Alternatives considered**: Assume IDs are globally unique (not a defensible cross-provider guarantee); replace all existing keys in place (needlessly disrupts existing Discord threads and external references).

## Decision 4: Synchronize before the bot becomes match-ready

- **Decision**: Perform the first synchronization during startup and gate bot match answers and auto-dispatch on per-tournament freshness/readiness.
- **Rationale**: Live review showed the API reconciliation loop sleeps for 45 seconds before its first fetch. During that window the bot answered an existing queued query using stale local set IDs. A periodic loop alone is insufficient for correctness at startup.
- **Alternatives considered**: Reduce the 45-second interval (still leaves a stale window); delete all local matches on startup (loses forensic state and does not establish remote freshness).

## Decision 5: Verify Challonge write semantics in a dedicated sandbox before releasing mutations

- **Decision**: Build deterministic mocked contract tests first, then perform a documented sandbox verification for score and DQ requests using an authorized test tournament.
- **Rationale**: The official documentation describes authentication, pagination, and match resources, while real write acceptance depends on bracket status and organizer authorization. A sandbox prevents accidental mutation of a production bracket.
- **Alternatives considered**: Test mutations against a live production event (unacceptable operational risk); rely exclusively on mocks (cannot validate current upstream behavior).

## Decision 6: Normalize progression separately from match lifecycle

- **Decision**: Add a `TournamentProgression` value object with `stage`, `stage_kind`, `group`, `bracket_side`, `round`, `round_order`, and a human-readable `display_path`. Keep it separate from the existing normalized match lifecycle and retain the raw provider values.
- **Rationale**: Start.gg represents progression through event, phase, phase group, round, and identifier. Challonge supports both one-stage brackets and group-to-final-stage formats, while its matches use lifecycle values such as `pending`, `open`, and `complete`. These are distinct concepts and must not share one enum or one UI label.
- **Alternatives considered**: Store only a display string (not sortable or safely filterable); treat every provider round as a local status (breaks dispatch and completion logic); model an unlimited provider-specific hierarchy in the Hub (unnecessary for the two providers now in scope).

Canonical mapping:

| Concept | Start.gg source | Challonge source | Hub model |
|---|---|---|---|
| Competition stage | event / phase / phase group | single stage, group stage, final stage | `stage`, `stage_kind`, `group` |
| Bracket context | phase group / round text | winners, losers, finals context where supplied | `bracket_side`, `display_path` |
| Round | full round text / identifier | round number / title | `round`, `round_order` |
| Lifecycle | activity state | `pending`, `open`, `complete` | `lifecycle_state` |

## Recent Challonge features relevant to aiTOB

- **Tournament check-in (updated 22 Dec 2025)**: Challonge supports participant pre-tournament check-in, organizer-side check-in management, email notices, and early processing. This is analogous to participant readiness but is at tournament scope, not evidence of a Start.gg-style per-match call API. aiTOB will expose it as a separate capability and keep Discord check-in for individual matches unless sandbox verification proves a supported remote endpoint.
- **Report Scores page (updated 17 Dec 2025)**: Challonge groups ongoing matches by round. This validates the need for a first-class `round` and `display_path` rather than a flat match list.
- **Two-stage formats (current documentation)**: Group stages can feed a final stage. aiTOB must preserve this stage boundary in filters, dispatcher scope, station selection, and overlay labels.
- **Match attachments and social sharing (updated 22 Dec 2025)**: The v2.1 schema exposes match attachments and Challonge's experimental social sharing flow builds on reported scores and attachments. Attachments are a candidate P3 evidence/export capability for aiTOB's AI-referee conflicts; social sharing remains provider-owned and out of scope for initial Hub control.
- **Additional competition formats**: Challonge documents free-for-all, leaderboard, racing, time trial, and grand prix formats. These are not always two-party sets, so the initial integration must identify them rather than force them through Discord match threads, DQ, or best-of scoring controls.
- **v2.1 upgrade additions (June 2026)**: Stable integer tournament IDs, snake_case fields, group-stage configuration/transitions, group-match score updates, Round Robin/Swiss ties, and station options were added or normalized.
- **Stations and Station Queuers (2026 docs)**: v2.1 now documents station resources with `stream_url` and assigned `match_id`, plus station queue resources. This overlaps with aiTOB's stations and planned-stream routing enough to support a capability-aware mapping after sandbox verification.

## Operational constraints discovered

- The provider documentation advertises API-key and OAuth authorization plus separate read/write scopes; connection diagnostics must distinguish invalid credentials from insufficient tournament permissions.
- The provider's published integration information includes plan-based API quotas, so the client must paginate, avoid redundant refreshes, and make the reconciliation cadence configurable.
- Direct automated retrieval of the documentation may be challenged by Cloudflare. The implementation must rely on the published schema but sandbox verification remains a release gate.
- The official v2.1 schema documents both match-score update and match-state-change endpoints. Their accepted payload/state behavior must be captured by sandbox contract tests before enabling each UI control.

Sources: [Challonge API v2.1 getting started](https://challonge.apidog.io/getting-started-1726706m0), [v2.1 upgrade guide](https://challonge.apidog.io/upgrading-from-v2-0-to-v2-1-1726691m0), [list tournaments](https://challonge.apidog.io/list-tournaments-23619739e0), [list matches](https://challonge.apidog.io/list-matches-23619745e0), [list participants](https://challonge.apidog.io/list-participants-23619749e0), [two-stage tournament guide](https://challonge.apidog.io/running-a-two-stage-tournament-1726921m0), [stations](https://challonge.apidog.io/list-stations-27937072e0), [tournament check-in](https://kb.challonge.com/en/article/how-to-use-tournament-check-in-tg3c8l/), and [competition formats](https://kb.challonge.com/en/article/learn-about-challonge-competition-formats-1f8j1cf/).

## Decision 10: Model remote state separately from Hub workflow state

- **Decision**: Persist raw provider state, normalized provider state, Hub workflow
  state, and its origin independently. A provider snapshot reconciles only fields it
  owns; a non-terminal remote state never silently overwrites a local call, local live
  workflow, station, Discord thread, readiness, or score.
- **Rationale**: The current shared `status` column preserved four Challonge matches as
  `in_progress` after their provider state was correctly understood as `open`. The
  existing protection is valuable for real local work, but it cannot distinguish a
  genuine local transition from an import bug. `str(ProviderSetState)` also loses the
  upstream raw value needed for an operator to diagnose divergence.
- **Alternatives considered**: Change the global state map (would risk Start.gg); let
  every provider snapshot overwrite local state (would erase real Discord/OBS workflow);
  add a Challonge-only special case in the database sync (does not scale to a third
  provider).

## Decision 11: Capabilities and commands replace successful local no-ops

- **Decision**: Every provider declares an immutable capability/action projection and
  returns typed command results (`remote_applied`, `local_only`, or `unavailable`).
  Generic Hub code validates that projection before it changes database state or makes
  an upstream call.
- **Rationale**: `ChallongeProvider.mark_in_progress()` currently returns a successful
  no-op while generic code assumes it changed the provider. Stream toggles similarly
  attempt an upstream call based on a Start.gg station mapping. A result must state what
  changed and who owns it, not merely whether an adapter function returned.
- **Alternatives considered**: Default virtual methods that fail only at runtime;
  scattered `provider_name` conditionals; pretending local lifecycle has a remote
  equivalent.

## Decision 12: Treat Challonge DQ as a versioned, sandboxed result policy

- **Decision**: Keep Start.gg DQ as its existing native `isDQ: true` mutation. For
  Challonge, introduce a provider-owned forfeit payload builder and initially keep the
  capability disabled. Its release gate is a disposable-tournament check of the v2.1
  `match` resource payload using explicit participant/rank/advancing fields and a
  public `0/-1` score convention for the disqualified side.
- **Rationale**: The current Challonge adapter uses legacy `scores_csv` and turns DQ
  into `1-0`; neither proves that the public bracket shows a DQ-like result. The v2.1
  Update Match resource documents structured match entries but no dedicated DQ flag.
- **Alternatives considered**: A shared magic `-1` for every provider (wrong for
  Start.gg); an untested `1-0`; a local-only DQ marked as remotely completed.

Source: [Challonge v2.1 Update Match](https://challonge.apidog.io/update-match-23619747e0).

## Decision 13: A provider acknowledgement is not a verified tournament result

- **Decision**: Persist every remote result/forfeit/reset command before sending it,
  then verify it using a newer provider snapshot. The ledger distinguishes pending,
  sending, acknowledged, snapshot-verified, retryable, permanent failure, conflict, and
  needs-review.
- **Rationale**: A timeout can occur after an upstream mutation was accepted, and a
  successful response can still be incomplete or conflict with a changed bracket. A
  durable ledger makes retry/recovery safe and communicates uncertainty honestly.
- **Alternatives considered**: Treat HTTP 200 as final; retry every timeout blindly;
  record a log line only. None prevents duplicate result mutations or supports restart.

## Decision 14: Reconciliation produces decisions; Completion Service owns effects

- **Decision**: Reconciliation returns idempotent domain decisions. A single Completion
  Service performs final local result, station release, overlay update, Discord update,
  and next-match discovery after verifying match ownership.
- **Rationale**: Direct reconciliation writes can release the wrong station or repeat
  Discord notifications on every poll. One effect boundary makes remote and local
  completions consistent and restart-safe.
- **Alternatives considered**: Let every sync path modify stations/messages; rely on
  in-memory deduplication; update a station directly from a snapshot.

## Decision 15: Operations continue locally during provider outage

- **Decision**: Persist Hub workflow separately from provider commands and use
  provider-local retry/backoff. Calls, Ready, timers, Discord, stations, and overlays
  continue during a provider outage, while remote work is prominently pending/retrying/
  failed/reviewable.
- **Rationale**: aiTOB is the permanent operations manager, so an external bracket
  service cannot make a running event operationally blind. It must also never claim an
  unreceived result is complete.
- **Alternatives considered**: Block all tournament activity on any sync failure;
  immediately declare local success; one shared retry queue for all providers.

## Decision 16: Link identity by stable IDs, not names

- **Decision**: Store provider participant/entrant to aiTOB participant to Discord user
  identity links, including scope, verification, aliases, teams, and organizer override
  provenance. Names remain display data only.
- **Rationale**: Entrant names can duplicate/change and can represent teams. Name-based
  Discord mentions risk notifying the wrong person precisely when a live call matters.
- **Alternatives considered**: Global name lookup; first matching Discord profile;
  volatile mappings held only in the browser or bot process.
