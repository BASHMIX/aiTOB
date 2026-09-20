# Feature Specification: Challonge Tournament Support

**Feature Branch**: `002-challonge-support`

**Created**: 2026-09-01

**Status**: Draft

**Input**: User description: "Add Challonge as a fully supported tournament provider alongside Start.gg, with a provider selector per tournament, synchronization, match lifecycle controls, score and DQ reporting, dashboard support, and safe migration of existing Start.gg tournaments. Also fix immediate startup synchronization so bot responses never use stale bracket matches."

## Clarifications

### Session 2026-09-20

- Q: How must Start.gg handle individual attendance confirmation or withdrawal from Discord and manual aiTOB controls during a called match? → A: Each entrant can be marked `present` or `withdrawn` through verified Discord self-service or an authorized organizer action. Because the public Start.gg API has no per-entrant attendance mutation, the first verified `present` moves only the provider set to `IN_PROGRESS` to protect it from native no-show DQ; Hub play and broadcast remain called. The second `present` starts Hub play and makes an assigned stream live automatically. At the mirrored deadline, exactly one present entrant is advanced through a verified single-player DQ; zero present sends no winner and waits for Start.gg native Double-DQ.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect and synchronize a Challonge tournament (Priority: P1)

As a tournament organizer, I choose Start.gg or Challonge in each browser loading session, provide a provider-appropriate tournament identifier, and see its current matches and participants in the Hub. The choice used while loading does not change the provider of tournaments already saved.

**Why this priority**: The Hub has no value for a Challonge organizer until it can safely identify the bracket and keep the local match view current.

**Independent Test**: Connect a test Challonge tournament containing scheduled, active, completed, and bye matches; verify that the Hub shows the actionable matches, correct competitors, rounds, and provider status.

**Acceptance Scenarios**:

1. **Given** valid authorization and a valid Challonge tournament identifier, **When** the organizer adds the tournament, **Then** the Hub records it as a Challonge tournament and displays its bracket information without treating it as Start.gg.
2. **Given** a tracked Challonge tournament changes remotely, **When** the next synchronization runs or the organizer requests a refresh, **Then** the Hub reflects changed, newly actionable, and completed matches without duplicating local matches.
3. **Given** invalid authorization or an inaccessible tournament, **When** the organizer attempts to add or refresh it, **Then** the Hub explains the failure and preserves existing local data.
4. **Given** a new browser session, **When** the organizer opens the tournament loading form, **Then** the form requires or clearly presents a platform choice for that session and changes its input guidance to match the selected platform.
5. **Given** the organizer switches the loading platform, **When** previously saved tournaments are displayed, **Then** their stored provider identity and behavior remain unchanged.

---

### User Story 2 - Run a Challonge match through the Hub (Priority: P1)

As a tournament organizer, I can call an eligible Challonge match, coordinate it through the existing Discord/OBS workflow, and report a final score, winner, or disqualification back to the correct Challonge match.

**Why this priority**: Match operations must be trustworthy; a read-only integration does not meet the organizer workflow.

**Independent Test**: From a Hub-synchronized Challonge match, perform each supported match outcome in a sandbox tournament and verify that both the bracket and the Hub show the same result.

**Acceptance Scenarios**:

1. **Given** a ready Challonge match with two resolved entrants, **When** the organizer calls it and participants complete the configured check-in flow, **Then** the Hub moves it through its normal lifecycle without performing an unsupported provider operation.
2. **Given** a completed score confirmation, **When** the organizer reports the result, **Then** the correct winner and score are reflected in Challonge and the Hub.
3. **Given** a player is disqualified, **When** the organizer resolves the match as a DQ, **Then** the correct opponent advances remotely and the Hub records the outcome.
4. **Given** a provider action is unavailable for a particular bracket state, **When** the organizer tries that action, **Then** the Hub prevents or clearly reports it and does not falsely mark the local match complete.

---

### User Story 3 - Manage both providers safely (Priority: P2)

As a tournament organizer, I can operate Start.gg and Challonge tournaments in the same Hub, identify which provider owns each tournament and match, and retain all existing Start.gg behavior.

**Why this priority**: Existing live Start.gg events cannot regress while Challonge is introduced.

**Independent Test**: Track one Start.gg tournament and one Challonge tournament, switch between them in the Hub, and exercise a read and a permitted match action for each.

**Acceptance Scenarios**:

1. **Given** tournaments from both providers, **When** the organizer selects either tournament, **Then** its provider is visible and only its matches, events, and valid controls are shown.
2. **Given** existing Start.gg tournament records, **When** the feature is deployed, **Then** they continue to resolve to Start.gg without organizer migration work.
3. **Given** a provider capability is not available, **When** the organizer views or acts on the tournament, **Then** unsupported controls are absent or disabled with a clear explanation.
4. **Given** a Start.gg match is called with a provider-owned attendance deadline, **When** either entrant confirms attendance or withdraws through their verified Discord interaction or an authorized organizer records it manually in aiTOB, **Then** the per-entrant intent is durably recorded; a first `present` is protected through verified provider `IN_PROGRESS` without starting Hub play or broadcast, while `withdrawn` alone sends no winner.
5. **Given** one Start.gg entrant withdraws during the called window, **When** the provider deadline expires, **Then** Start.gg advances the other entrant only if that entrant appeared; if neither entrant appeared, Start.gg records double-DQ, and aiTOB mirrors the resulting provider snapshot.

---

### User Story 4 - Start with a current bracket (Priority: P2)

As an organizer or Discord participant, I receive match information based on the latest remote bracket immediately after the Hub starts, rather than an older local snapshot.

**Why this priority**: A stale match ID can direct people to the wrong match or cause a rejected provider action.

**Independent Test**: Seed local data that differs from a remote test tournament, restart the services, immediately request currently playable matches, and verify that every returned match identifier exists in the current remote bracket.

**Acceptance Scenarios**:

1. **Given** stale local matches before startup, **When** the API and bot become ready, **Then** the initial bracket synchronization finishes before bot-generated match answers or automatic dispatch use those matches.
2. **Given** initial synchronization fails, **When** a match answer or action is requested, **Then** the Hub reports that bracket data is not current rather than returning stale identifiers.

---

### User Story 5 - View one consistent tournament progression (Priority: P1)

As a tournament organizer, I can see a provider-neutral progression for every supported head-to-head match: tournament stage, group or playoff context, bracket side, round, and live match status. This remains understandable for both Start.gg events/phases and Challonge single-stage or group-to-final-stage competitions.

**Why this priority**: A raw provider status does not tell a tournament operator where a match belongs. Mixing progression with match lifecycle is the source of incorrect dispatch, wrong filtering, and confusing dashboards.

**Independent Test**: Synchronize a Start.gg multi-event bracket and a Challonge two-stage group-to-playoff bracket; confirm each actionable match is shown under the correct stage and round while the same lifecycle labels are used across providers.

**Acceptance Scenarios**:

1. **Given** a provider exposes group and final stages, **When** the organizer views matches, **Then** group matches and playoff matches are separately identifiable and sortable by their stage and round.
2. **Given** a double-elimination bracket, **When** the organizer views a match, **Then** its winners, losers, or final context is visible without inventing a new provider state.
3. **Given** a match is pending, open, called, in progress, complete, invalid, or queued remotely, **When** it is synchronized, **Then** the Hub maps it to one canonical lifecycle state while preserving the raw provider state for diagnostics.
4. **Given** a non-head-to-head format such as a race, time trial, grand prix, or multi-player free-for-all, **When** it is synchronized, **Then** the Hub labels it as unsupported for Discord match coordination rather than incorrectly treating it as a two-player set.

---

### User Story 6 - Load Challonge tournaments from common identifiers (Priority: P1)

As a Challonge organizer, I can load a tournament using its numeric ID, normal Challonge URL, community/subdomain URL, or recognized legacy subdomain identifier without manually constructing an API path.

**Why this priority**: Existing FNC usage relied on subdomain-hosted tournaments, while modern Challonge recommends stable numeric tournament IDs. The Hub must bridge both forms safely.

**Independent Test**: Load the same authorized tournament using its numeric ID and its subdomain URL; verify that both resolve to one saved tournament and return identical participants and matches.

**Acceptance Scenarios**:

1. **Given** `subdomain.challonge.com/tournament-slug`, **When** the organizer previews or loads it, **Then** the Hub separates the community/subdomain and URL slug, resolves the current numeric tournament ID, and shows a confirmation preview before saving.
2. **Given** a direct numeric tournament ID, **When** the organizer loads it, **Then** the Hub retrieves the tournament without requiring a subdomain.
3. **Given** a URL slug changes after a tournament was saved, **When** the Hub refreshes it, **Then** synchronization continues through the saved numeric tournament ID.
4. **Given** two submitted identifiers resolve to the same provider tournament ID, **When** the second is loaded, **Then** the Hub updates/selects the existing tournament instead of creating a duplicate.
5. **Given** the organizer does not use a Challonge subdomain, **When** they load a numeric ID or normal Challonge URL, **Then** the tournament loads without requiring any community/subdomain value.
6. **Given** the organizer enables the optional subdomain/community choice, **When** they provide a valid subdomain or subdomain URL, **Then** discovery is scoped to that community and resolves the same durable tournament identity rules.

### Edge Cases

- A tournament identifier is valid on one provider but invalid or ambiguous on the selected provider.
- A Challonge match has a bye, a missing participant, or a yet-unresolved opponent.
- The remote bracket changes while a local match is called or in progress.
- Authorization expires or lacks permission after a tournament was added.
- Challonge lacks a counterpart for a Start.gg-specific capability such as public stream queues or native check-in waves.
- The same organizer tracks tournaments from both providers with overlapping participant names or match numbers.
- A group-stage match and a final-stage match share a round number or display name.
- A provider changes the progression structure after results are reported or a stage becomes inactive.
- A subdomain or URL slug contains uppercase letters, URL encoding, a trailing slash, or a locale/path suffix.
- A community exists but the credential cannot enumerate it, or the tournament is private.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST let an authorized organizer select the tournament provider when adding or editing a tracked tournament.
- **FR-002**: The system MUST store the provider identity and provider-specific tournament identifier for every tracked tournament.
- **FR-003**: The system MUST preserve existing Start.gg tournaments as Start.gg tournaments after the change.
- **FR-004**: The system MUST validate Challonge authorization and tournament access before adding a Challonge tournament.
- **FR-005**: The system MUST synchronize Challonge participants and actionable matches, including round, entrants, scores, and remote match state, into the existing Hub match view.
- **FR-006**: The system MUST report supported score, winner, and disqualification outcomes to the provider that owns the match and keep the local outcome aligned with the remote result.
- **FR-007**: The system MUST expose only actions supported by the selected provider and current match state.
- **FR-008**: The system MUST continue to support the existing Discord, station, and overlay workflows for provider-backed matches where those workflows do not require a provider-specific capability.
- **FR-009**: The system MUST label provider-specific limitations clearly and allow the organizer to continue with safe Hub-only workflow steps where appropriate.
- **FR-010**: The system MUST run and complete an initial synchronization for each tracked tournament before bot responses or automated match handling can use stored matches after service startup.
- **FR-011**: The system MUST not replace a locally active match with unrelated remote data; mismatches and rejected provider mutations MUST be visible to the organizer.
- **FR-012**: The system MUST record provider synchronization and mutation failures with enough context for an organizer to identify the affected tournament and match.
- **FR-013**: The system MUST represent tournament progression independently from match lifecycle, including stage, group or final-stage context, bracket side, round, and provider display label where available.
- **FR-014**: The system MUST map Start.gg events/phases and Challonge single-stage and two-stage structures into the same progression model without conflating remote state with round or bracket position.
- **FR-015**: The system MUST preserve the raw provider state and raw progression fields for diagnostics while displaying canonical Hub values to organizers.
- **FR-016**: The system MUST identify head-to-head coordination eligibility separately from provider support so that races, time trials, grand prix, and multi-player free-for-all formats are not routed into a two-player Discord workflow.
- **FR-017**: The system MUST expose provider-native pre-tournament check-in independently from Hub and Start.gg per-match readiness flows.
- **FR-018**: The tournament loading UI MUST let the organizer choose Start.gg or Challonge for each browser session and MUST display provider-specific labels, examples, validation, and connection status.
- **FR-019**: A platform choice made for loading MUST be session-scoped; every persisted tournament MUST retain its own provider identity independently of the current session choice.
- **FR-020**: The system MUST accept Challonge numeric IDs and direct URLs without a subdomain, and MUST optionally accept subdomain/community URLs and recognized legacy subdomain identifiers through the same resolver.
- **FR-021**: After resolving a Challonge URL, the system MUST persist and use the provider's stable numeric tournament ID for subsequent participant, match, result, and synchronization operations.
- **FR-022**: The system MUST join Challonge match participant references to the participant collection without assuming that names or array positions are unique.
- **FR-023**: Provider credentials MUST be sent in authorization headers and MUST NOT appear in URLs, browser state, API responses, or logs.
- **FR-024**: The system MUST paginate tournament, participant, and match retrieval until the requested provider collection is complete or a visible provider error occurs.
- **FR-025**: The Challonge loading UI MUST make subdomain/community scoping optional and disabled by default; leaving it empty MUST NOT block direct ID or normal URL loading.
- **FR-026**: The system MUST persist provider state, Hub workflow state, Discord workflow fields, and synchronization/command state independently; a conflict MUST NOT replace the Hub lifecycle state.
- **FR-027**: The system MUST create a durable provider command record before every remote mutation and MUST mark that mutation verified only after a newer authoritative snapshot confirms the resulting remote state. For intent commands such as DQ, aiTOB MUST NOT prescribe or infer a winner or advancement beyond the selected transition.
- **FR-028**: The system MUST reconcile organizer-originated remote changes, including result, DQ/forfeit, reset/reopen, changed entrants/seeding/bracket structure, deletion/cancellation, newly available downstream matches, and tournament completion.
- **FR-029**: The system MUST resume Hub calls, readiness, attendance deadlines, station/overlay intent, Discord references, pending commands, retry/backoff, snapshots, and reviewable conflicts after restart.
- **FR-030**: The system MUST continue Hub-local operations during provider/internet failure while clearly exposing remote operations as pending, retrying, failed, conflict, or needs-review; one provider's outage or rate limit MUST NOT halt another provider.
- **FR-031**: The system MUST use durable provider participant/entrant to aiTOB to Discord identity links for automated notifications and MUST NOT select a Discord recipient from a display-name match alone.
- **FR-032**: Completion effects triggered by reconciliation MUST pass through one idempotent completion service that validates station ownership, updates OBS/Discord, and discovers subsequent eligible matches without repeated side effects.
- **FR-033**: No UI, API route, Discord handler, bot handler, overlay, or Hub workflow consumer MAY call a tournament provider directly; all provider reads and mutations MUST pass through the budget-aware Sync Coordinator while consumers read the local durable projection.
- **FR-034**: The Sync Coordinator MUST coalesce concurrent compatible requests by provider account, tournament, and snapshot scope; it MUST apply provider-specific cache, minimum interval, debounce, budget, priority, and backoff policy.
- **FR-035**: Economy mode MUST be the default and make no periodic provider calls. Live mode cadence MUST be configurable, adaptive to active Hub work and budget, and disabled for complete/archived tournaments.
- **FR-036**: Provider snapshots MUST use the smallest sufficient scope and a Full Sync MUST require import, structure/revision recovery, unresolved conflict, long-outage recovery, provider limitation, or explicit organizer request.
- **FR-037**: The system MUST persist provider-account request-budget/429 state and request telemetry by provider, account, tournament, reason, scope, cost, and outcome; a provider's exhaustion MUST first suppress background work without halting another provider.
- **FR-038**: Request coalescing MUST be coverage-aware: an in-flight broader snapshot may satisfy a narrower request only when it covers the requested entities and meets freshness/revision requirements; scope strings alone are insufficient.
- **FR-039**: In Economy mode, each tournament MUST display last successful provider sync, data freshness, and an explicit Sync now control; it MUST not imply direct provider changes are automatically discovered.
- **FR-040**: Scheduler/Command Service, Sync Coordinator, Adapter, Reconciliation Engine, Completion Service, and SQLite projection MUST retain their separate responsibilities; the Sync Coordinator MUST NOT own Hub lifecycle, Discord effects, reconciliation decisions, or provider payload semantics.
- **FR-041**: Provider Command Ledger MUST contain only provider-backed mutations. Local Hub workflow transitions MUST commit with a durable workflow-outbox event in the same transaction so Discord/OBS effects survive interruption and are deduplicated on retry.
- **FR-042**: Before a provider-backed score, forfeit/DQ, reset, or reopen mutation, MatchCommandService MUST require a fresh snapshot or at most one coalesced targeted preflight snapshot; changed participants/state MUST reject or enter needs-review, and provider outage MUST not send an unsafe mutation.
- **FR-043**: The tournament provider MUST be the sole source of truth for provider-owned bracket state, including remote match state, result, DQ/forfeit state, winner, advancement, and downstream matches; aiTOB MUST own only its operational workflow and durable command/synchronization state.
- **FR-044**: Start.gg called matches MUST model each entrant's attendance independently as `pending`, `present`, or `withdrawn`, and the decision MUST be one-way within that called window. Verified Discord self-service and authorized manual aiTOB controls MUST use the same durable command. The first verified `present` MUST use a fresh entrant/state preflight and verified `markSetInProgress` to protect the remote set while leaving Hub play and broadcast called/queued. The second verified `present` MUST start Hub play; an assigned stream MUST become platform `live` automatically. At the mirrored deadline, exactly one `present` MUST use a fresh preflight and verified single-player DQ; zero present MUST send no result/winner and MUST reconcile Start.gg's native Double-DQ. Challonge MUST expose organizer-approved single-player DQ only, encode the selected loser as `-1` and the advancing entrant as `0`, and hide double-DQ on every UI surface. AI-initiated DQ remains prohibited.
- **FR-045**: Start.gg MUST own its native check-in/DQ timeout. Since the public API does not expose the round DQ timer, aiTOB MUST store an organizer-verified `provider_dq_timer_seconds` mirror distinct from the Challonge/local `dq_timer_seconds`, display that fact in setup/settings, and derive the called deadline from the mirror. The mirror MUST NOT claim to modify Start.gg. Exactly-one-present resolution MAY issue the agreed verified DQ at that deadline; zero-present resolution MUST remain provider-owned.
- **FR-046**: After a Start.gg attendance deadline plus a bounded consistency delay, aiTOB MUST request a targeted authoritative snapshot. If the match remains unchanged, it MUST schedule bounded backoff reads without resending `markSetCalled`, attendance, or DQ mutations. A still-unresolved match after the retry horizon MUST enter `needs_review` with a manual refresh action.

### Key Entities *(include if feature involves data)*

- **Tournament provider**: The bracket service that owns a tournament and defines its available operations.
- **Provider connection**: An organizer-authorized connection to a bracket service, including its authorization status and permitted operations.
- **Provider tournament reference**: The stable remote identifier and provider identity used to synchronize one tracked tournament.
- **Tournament loading session**: The browser-session platform choice, provider-specific input draft, validation state, and preview; it is not the source of truth for saved tournaments.
- **Challonge locator**: Parsed numeric ID or URL components, including optional community/subdomain and tournament URL slug, that resolve to a stable remote ID.
- **Provider capability**: An operation available for a provider and optionally constrained by the tournament or match state.
- **Synchronized match**: A Hub match linked to one remote provider match, with local coordination state and the latest known remote state.
- **Synchronization run**: A recorded attempt to bring a tracked tournament's local matches into agreement with its remote bracket.
- **Provider command ledger**: Durable intent, acknowledgement, verification, retry, and conflict record for a provider mutation; it survives restart and prevents duplicate writes.
- **Completion service**: The idempotent Hub workflow that applies a verified completion to result, station, overlay, Discord, and newly available matches.
- **Participant identity link**: A verified mapping from provider participant/entrant to aiTOB participant and Discord recipient(s), never inferred from a display name alone.
- **Four-axis match state**: Independent provider, Hub workflow, Discord workflow fields, and synchronization state; conflict belongs only to the synchronization axis.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An organizer can add an authorized Challonge tournament and see its actionable bracket matches in the Hub within 60 seconds.
- **SC-002**: In a test tournament with at least 20 matches, 100% of non-bye remote matches map to one correct Hub match after a synchronization run.
- **SC-003**: In supported test cases, 100% of score and DQ actions that the provider accepts show the same winning participant and final state in the Hub within 10 seconds.
- **SC-004**: After restart with intentionally stale local data, 100% of bot-provided playable match identifiers are present in the first completed remote synchronization result.
- **SC-005**: Existing Start.gg tournament workflows pass their regression suite without requiring organizers to reconfigure those tournaments.
- **SC-006**: In a mixed test set covering group stage, final stage, winners bracket, losers bracket, and grand final, 100% of actionable head-to-head matches display the correct canonical progression path and lifecycle state.
- **SC-007**: Numeric ID, normal URL, subdomain URL, and legacy subdomain identifier test cases resolve to the expected Challonge tournament with no duplicate saved records.
- **SC-008**: In automated security tests, no provider credential is present in request URLs, client-visible payloads, or redacted application logs.
- **SC-009**: A result submitted through aiTOB is verified by a subsequent provider snapshot in 100% of supported sandbox cases; an acknowledgement alone is never reported as verified.
- **SC-010**: After an injected crash between provider acknowledgement and local completion, 100% of pending commands recover to snapshot-verified, retryable, conflict, permanent-failure, or needs-review without a duplicate mutation.
- **SC-011**: In mixed-provider outage tests, a 429, expired credential, or unreachable endpoint for one provider produces no failed request or stopped local workflow for the other provider.
- **SC-012**: Repeated snapshots and restart recovery produce at most one Discord Call notification/thread creation and at most one station release per match transition.
- **SC-013**: Ten dashboard/card refreshes cause zero provider requests, and concurrent compatible sync requests result in exactly one upstream operation.
- **SC-014**: In adapters supporting targeted match fetch, 100% of post-result verification checks use a targeted scope rather than a full bracket/participant refresh unless an explicit full-sync condition is recorded.
- **SC-015**: A compatible narrower request joining an in-flight broader covered scope causes zero additional upstream operation; an uncovered entity/range correctly creates a separate admitted operation.
- **SC-016**: An interrupted local Call either delivers its durable Discord/OBS outbox effect once after recovery or remains visibly pending/failed; it never silently remains called without delivery evidence.

## Assumptions

- Version one connects to existing Challonge tournaments; tournament creation and participant registration management are outside the initial scope.
- An organizer supplies credentials authorized for the tournament and is responsible for obtaining the required Challonge API plan and permissions.
- The initial implementation uses documented Challonge API authorization and respects the provider's published request limits.
- Start.gg-only public stream queue behavior remains Start.gg-specific; Challonge matches can still use local stations and overlays when configured.
- If Challonge has no native equivalent to a provider action, the Hub uses its existing safe local coordination workflow or makes the limitation explicit instead of emulating a remote state change.
- Challonge tournament check-in is a pre-tournament participant feature; it is not assumed to be an API-controlled per-match call or readiness state until sandbox validation confirms otherwise.
- Version one coordinates only two-party head-to-head matches. Newer Challonge racing and multi-party formats are recognized and surfaced as non-coordinateable, pending a dedicated competition workflow.
- The loading-platform selector is scoped to the current browser session; provider ownership of a saved tournament is durable server data.
- A Challonge numeric tournament ID is the canonical remote identity. Subdomain is optional; subdomain and URL slug are retained only for discovery and display when present.
