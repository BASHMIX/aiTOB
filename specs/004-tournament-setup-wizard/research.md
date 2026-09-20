# Research: Tournament Setup Wizard, Player Registration, and Workspace AI Keys

All implementation unknowns identified during planning are resolved here. Source
links are official provider documentation where an external contract matters.

## 1. Wizard persistence and concurrency

**Decision**: Persist a non-secret setup draft in PostgreSQL and use an integer
revision for optimistic concurrency. The React store is an editable cache only.
PATCH writes one section at a time and requires the last observed revision.

**Rationale**: Server persistence survives reloads and OAuth redirects, can be
authorized by workspace, and prevents two tabs from silently overwriting each
other. A hybrid JSONB answer document plus normalized ownership, lifecycle, and
selected-resource columns permits the five steps to evolve without weakening
critical foreign-key checks.

**Alternatives considered**: `sessionStorage`/`localStorage` cannot establish
tenant ownership or reliably survive another device. Fully normalized storage
for every control creates many joins and migrations without a current query need.
An opaque JSON blob alone cannot enforce account and Event binding invariants.

## 2. Start.gg connection and exact Event resolution

**Decision**: Use one aiTOB Start.gg OAuth application with Authorization Code,
refresh tokens, one-use state, and the minimum required scopes. Resolve an Event
URL/slug with an Event query and preserve its canonical Event ID and parent
tournament ID. A tournament locator returns Events but selects none when more
than one exists. Keep direct Event slug input as the preferred path.

**Rationale**: Start.gg documents Authorization Code plus refresh tokens and
separate `tournament.manager` and `tournament.reporter` scopes. Its Event examples
support direct Event slug lookup. This fixes the current URL truncation and
`events[0]` behavior.

**Alternatives considered**: A pasted personal token remains a migration/import
path, not the primary UX. A “My tournaments” browser is helpful but incomplete
because owner queries need not include every tournament where the user has an
administrative role. Silent first-Event selection is rejected.

**Sources**: [OAuth overview](https://developer.start.gg/docs/oauth/oauth-overview/),
[OAuth scopes](https://developer.start.gg/docs/oauth/scopes/),
[Event by slug](https://developer.start.gg/docs/examples/queries/get-event/), and
[Events by tournament](https://developer.start.gg/docs/examples/queries/events-by-tournament/).

## 3. Start-in-wave and remote start capability

**Decision**: Represent Start-in-wave as `verified_enabled`,
`verified_disabled`, `unsupported`, or `unknown`, with an observation time and
safe explanation. Do not expose a setting mutation until a provider adapter
implements and verifies the exact operation and permission. Implement remote
bracket start for both Start.gg and Challonge only through documented or
provider-authorized operations with preflight and reconciliation; this is a
shipping dependency rather than permission to simulate start.

When Start-in-wave is `verified_enabled`, or an authorized organizer explicitly
confirms it because the provider cannot verify it, monitor bracket start and
fresh provider match transitions. Every real transition to `CALLED`, including
the first wave, enters the same durable Discord player-call workflow as an
authorized Dashboard transition. A call-occurrence key deduplicates provider
snapshots, concurrent Dashboard activity, retries, and worker restarts. Unknown,
stale, empty, or contradictory evidence does not enable provider-wave monitoring,
while authorized Dashboard calls remain available.

**Rationale**: The current repository has a spike-verified `markSetCalled`
operation for a set, but no verified tournament-level Start-in-wave read/write
contract. Start.gg’s public documentation describes schedule waves without
documenting a general setting mutation. A setup check must not mutate a live
match to infer capability.

**Alternatives considered**: Treating `markSetCalled` success as proof or as a
remote tournament start was rejected because it can change live provider/player
state. Assuming disabled when
the field is absent was rejected because it would present unknown data as fact.
Suppressing the initial provider-called wave was rejected because the organizer
requires players to be called whenever a match becomes `CALLED`, regardless of
whether Start.gg or the Dashboard produced the transition.

**Source**: [Start.gg schedule-wave conflict guidance](https://developer.start.gg/docs/e2e/resolve-conflicts/).

## 4. Challonge connection and bracket scope

**Decision**: Reuse and complete the existing Challonge Authorization Code flow,
including token expiry/refresh and `/me` identity verification. Request core
identity/tournament/match/participant scopes and add community management only
when that feature is selected. Model the current Challonge tournament as one
managed bracket and preview it before local persistence.

**Rationale**: Challonge v2.1 documents OAuth, refresh, resource scopes, current
user, and tournament listing. This keeps credentials reusable and provides a
real connect button instead of requiring repeated secret input.

**Alternatives considered**: Always requesting community management is broader
than necessary. Keeping the current legacy-only refresh behavior would leave
workspace accounts to expire. Immediate tournament creation during resolution
prevents review and is rejected.

**Sources**: [Authorization](https://challonge.apidog.io/authorization-1726705m0),
[scopes](https://challonge.apidog.io/scopes-1726710m0),
[resource scoping](https://challonge.apidog.io/resource-scoping-1730219m0), and
[list tournaments](https://challonge.apidog.io/list-tournaments-23619739e0).

## 5. Managed Discord connection

**Decision**: Use one platform-managed aiTOB Discord application and bot token.
“Connect Discord” starts a guild installation using `bot` and
`applications.commands`; a user authorization with `identify guilds` may be used
to list manageable guilds. A workspace Discord account represents an authorized
installation/guild, not a customer bot token.

**Rationale**: Discord documents guild install scopes, user guild listing, and
the requirement that a guild installer can manage the guild. A shared bot is the
simplest supported product and avoids running one gateway process per customer
token.

**Alternatives considered**: Customer-owned bot applications require token
collection, per-token gateway processes, registration/commands, and support; this
is deferred. Storing the shared bot token in every workspace duplicates a
platform secret and is rejected.

**Sources**: [OAuth2 and permissions](https://docs.discord.com/developers/platform/oauth2-and-permissions)
and [application installation](https://docs.discord.com/developers/resources/application).

## 6. Discord permissions and customization

**Decision**: Calculate effective permissions for each chosen channel, including
channel overwrites. Require view, send, embed, history, and the applicable thread
permissions used by the current delivery flow. Store match destination,
escalation destination, and moderator role explicitly. Server-specific bot
nickname/avatar/banner/bio are optional guild connection settings; tournament
identity remains in message embeds/templates.

**Rationale**: Guild-level permissions alone do not prove the bot can send in a
chosen channel. Discord’s current-member update is guild scoped, so one bot
profile cannot vary per simultaneous tournament in the same guild.

**Alternatives considered**: A single global channel setting is ambiguous in a
multi-workspace service. Presenting profile customization as tournament scoped
would promise behavior Discord does not provide.

**Sources**: [Channel permissions](https://docs.discord.com/developers/resources/channel),
[threads](https://docs.discord.com/developers/topics/threads), and
[modify current member](https://docs.discord.com/developers/resources/guild#modify-current-member).

## 7. Multi-workspace Discord runtime

**Decision**: Replace process-global active workspace/account selection with a
routing repository keyed by guild, channel/thread, and explicit tournament
binding. Resolve every inbound event and outbound command to one enabled
workspace. Missing or ambiguous routes fail closed.

**Rationale**: One shared bot can serve multiple guilds only if runtime work is
scoped per event/job. The current `ACTIVE_DISCORD_WORKSPACE_ID` assumption would
otherwise route messages, commands, and AI usage through the wrong tenant.

**Alternatives considered**: One bot process per workspace can isolate state but
does not match the managed shared-bot product and adds orchestration overhead.

## 8. AI credential ownership and encryption

**Decision**: Add Gemini and OpenAI as workspace integration-account provider
types and store one encrypted `api_key` credential for each. Initially allow at
most one Gemini and one OpenAI account per workspace; replacement atomically
overwrites ciphertext and increments a non-secret revision. Store no old secret
history. Require `integrations.manage` for add, replace, test, enable, disable,
and remove.

**Rationale**: The existing `integration_credentials` path already uses
authenticated encryption with `AITOB_INTEGRATION_MASTER_KEY` and safe public
projections. Reuse avoids a second secret system. Both providers instruct
developers to treat API keys as server-side secrets. Provider billing remains
directly attached to the customer’s key; aiTOB’s request/token limits remain
operational guardrails and never claim to be billing limits.

**Alternatives considered**: Adding workspace columns to
`ai_service_secrets` duplicates lifecycle and encryption APIs. Multiple accounts
per AI provider adds naming and health ambiguity not required by the requested
“save both, select one” workflow. Browser storage and client-side provider calls
are rejected.

**Sources**: [OpenAI API authentication](https://platform.openai.com/docs/api-reference/backward-compatibility),
[OpenAI project-key practices](https://help.openai.com/en/articles/9186755), and
[Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key).

## 9. Workspace assistant configuration and test behavior

**Decision**: Create one typed `workspace_ai_configs` row per workspace. It
selects one active AI account and preserves the current model, mode, request
limit, token limit, context limit, response limit, timeout, and safety-policy
meaning. A connection test is a deliberate minimal, non-mutating request against
the selected model. Save only a classified status/code and timestamp.

**Rationale**: Typed columns retain existing validation and allow a workspace row
lock during quota reservation. Independent health per provider permits both keys
to remain saved. A model is treated as user-selectable/testable text rather than
a price-driven or permanently hard-coded catalog.

**Alternatives considered**: JSON inside entitlement/general settings weakens
constraints and locking. Automatic tests during autosave could spend the
customer’s quota. Persisting raw upstream errors may leak account or credential
material.

## 10. AI use authorization and accounting

**Decision**: Keep credential/configuration management owner-only through
`integrations.manage`. Add an explicit `assistant.use` permission for roles that
may spend a workspace-owned key. Reserve usage under a workspace config row lock
and attribute it to workspace, selected integration account, provider, model,
tournament, policy period, and outcome without prompts/responses.

**Rationale**: Existing `workspace.read` is too broad for an action that can
consume the owner’s external quota. Workspace/account attribution proves
isolation and preserves the current request/token guardrails without turning the
ledger into billing.

**Alternatives considered**: Keeping global platform-admin-only configuration
does not provide BYOK. Allowing every viewer to invoke AI preserves a current
accident rather than a safe product boundary.

## 11. Provider facts, local branding, and the Editor

**Decision**: Store the last provider snapshot separately from local display
overrides. Reuse `media_assets` for a draft-owned `tournament_logo`, then rebind
the same asset during materialization. Project a single tournament identity to
Hub, Editor, and authorized overlays: display/short name, logo URL, accent,
Event name, and scheduled time.

**Rationale**: Separating provenance prevents a local label from masquerading as
provider data. Reusing the validated image store preserves access control,
deletion rules, Cloudinary/local URLs, and existing rendering precedence.

**Alternatives considered**: Copying provider images into local storage without
validation changes ownership and may break URLs. Wizard-specific uploads would
duplicate image validation and retention.

## 12. Safe presets and automatic disqualification

**Decision**: Seed manual and assisted operating profiles from versioned,
server-owned defaults. Both require human result approval. Remove the generic
automatic-DQ setting, default-true schema/API field, and UI toggle. Attendance
is provider-specific: Start.gg owns zero-attendee Double-DQ, its verified
exactly-one-attendee path may run after the mirrored deadline, and Challonge
offers authorized single-player DQ only.

**Rationale**: This is required by the project constitution. The deprecated
`auto_dq_match` entry point is now a non-mutating review shim; every real action
must use explicit attendance state and the provider-specific command path.

**Alternatives considered**: Permanently forcing the old flag false would leave
dead and misleading behavior. Delegating winner choice to AI or a speculative
local timer is prohibited. aiTOB acts only on verified attendance and deadline
state, then confirms the provider result.

## 13. Readiness, materialization, activation, and external effects

**Decision**: Keep four distinct actions: save draft, materialize a configured
local tournament, activate aiTOB management, and start the remote bracket through
the separately authorized Start.gg or Challonge adapter. Materialization locks/revalidates the draft and creates
the tournament/configuration transactionally. Activation rechecks freshness and
creates an idempotent initial-sync outbox command after local state changes.
External provider/Discord calls never run in those database transactions.

**Rationale**: The UI can state exactly what will happen, retries cannot create
duplicates, and unknown network outcomes use existing reconciliation patterns.
Optional missing Discord/AI creates warnings; provider scope and local operating
requirements create blocking checks.

**Alternatives considered**: One “Save and start” endpoint conflates local and
remote state. Performing initial sync or remote start inside the transaction
creates unrecoverable network/database split outcomes.

## 14. Migration and rollout

**Decision**: Add and test new tables dark, then switch runtime consumers without
a global fallback. Non-secret defaults may be copied automatically. A legacy AI
config/key can be assigned to exactly one selected workspace only through an
explicit audited platform-admin command that decrypts with the old key and
re-encrypts with the integration master key. Keep legacy rows read-only for a
rollback window, then purge under retention policy.

**Rationale**: Ownership of a service-global secret cannot be inferred. Copying
ciphertext between encryption domains does not prove it is decryptable. The
current global tournament slug key and nullable historical workspace fields also
need feature 003’s identity/backfill gates before this wizard can cut over.

**Alternatives considered**: Copying the global AI key to every workspace would
share billing and violate isolation. A hidden fallback would make behavior
depend on an undisclosed secret. Dual-write is prohibited by the constitution.

## 15. Tournament player registration and provider membership

**Decision**: Add a tournament-scoped registration aggregate instead of extending
the current global Discord-player state. The Discord step configures one opening
instant, closing instant, display timezone, destination, provider-registration
requirement, image policy, verified role, and messages. Server time enforces the
window. A polling/diff worker and explicit Recheck read entrants only from the
selected provider account and exact Event or bracket.

Provider identity proof and tournament membership are independent. Player data
uses `prefix` for team/sponsor/clan and `gamertag` for the competitive player tag;
legacy player `team` and `name` are migration aliases only. Every tournament
checks its own exact provider scope. The organizer chooses one of three base
policies: exact normalized Discord name equals provider Gamertag, the bot changes
the member's server nickname to the selected entrant's Gamertag, or either. A
duplicate/colliding normalized Gamertag cannot be selected automatically and
requires organizer review.

Start.gg bio verification is an independent optional method. When selected, a
random code is stored as a one-use, attempt-limited keyed hash bound to workspace,
tournament, scope, Discord user, and claimed provider user; fetched bio and
plaintext code are discarded after comparison. Challonge retains the configured
Gamertag/nickname policy because it has no equivalent bio field.

An authorized organizer can instead link a provider entrant directly by Discord
ID from the participant list. Resolve the snowflake against the tournament's
bound guild, reject bot accounts and conflicting tournament links, and store the
method as `manual_discord_id`. A member-not-found result remains a visible
`not_in_guild` state that can be rechecked after the player joins. Link, replace,
and unlink are audited and affect future routing only.

If provider registration is optional, Discord-only enrollment is allowed and
clearly remains unmatched. Match automation waits for an exact entrant link.
Provider removal moves a prior enrollment to `needs_review` without erasing the
reusable identity or image. Open/close announcements, reminders, role grants, and
state transitions use durable idempotency keys.

**Rationale**: The current flow keys registration mainly by Discord user and uses
a process-global active workspace plus a scan of tracked tournaments. It cannot
prove which Event the player joined and can route simultaneous tournaments
incorrectly. Separating reusable identity from tournament enrollment supports
safe reuse while preserving exact Event membership and Workspace isolation.

**Alternatives considered**: Fuzzy matching and first-match selection were
rejected because names collide and change. The organizer-requested exact Gamertag
and nickname methods remain available with collision review and an explicit
assurance level. Treating a prior Start.gg verification as proof of every later
tournament was rejected because identity ownership does not prove Event
registration. Requiring Start.gg bio semantics for Challonge was rejected because
providers expose different identity capabilities. Accepting an unresolved raw
Discord ID as ready was rejected because typing errors and wrong-guild IDs would
route player messages incorrectly.

## 16. Player image validation and AI separation

**Decision**: Reuse the Workspace media ledger and deterministic decoding,
type/size/dimension checks, normalization, and access controls for player images.
The tournament policy is disabled, optional, or required. An existing valid image
can be kept or replaced; required images gate `ready`. Default registration does
not call Gemini/OpenAI for image moderation and never consumes the assistant key
without a separate explicit privacy, billing, retention, and failure contract.

**Rationale**: The current image helper can consult a service-global Gemini key
and fail open. That conflicts with Workspace BYOK, makes registration depend on an
undisclosed external request, and may transmit player media without clear consent.
Deterministic technical validation is sufficient for this Epic; organizers retain
review and correction controls.
