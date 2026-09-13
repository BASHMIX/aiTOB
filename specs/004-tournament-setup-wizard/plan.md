# Implementation Plan: Tournament Setup Wizard, Player Registration, and Workspace AI Keys

**Branch**: `main` (no branch created per user request) | **Date**: 2026-09-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-tournament-setup-wizard/spec.md`

## Summary

Build a resumable five-step setup wizard that resolves one exact Start.gg Event
or Challonge bracket, reviews provider facts and local branding, configures safe
operating defaults, optionally connects Discord and the organizer assistant,
configures a tournament registration window that links Discord players to exact
provider entrants and validated images, and activates local tournament management
only after a server-side readiness check.
The implementation introduces workspace-scoped draft and configuration models,
uses the existing encrypted integration credential store for customer-owned
Gemini/OpenAI keys, preserves every current assistant control, and changes the
Discord runtime from one active workspace to one managed bot routed by explicit
workspace/guild/tournament bindings.

Activation is a local, transactional operation followed by idempotent initial
sync work. It is distinct from any remote bracket start. Start.gg Event input is
resolved directly and tournament-level input never defaults to `events[0]`.
Start-in-wave is reported as `verified_enabled`, `verified_disabled`,
`unsupported`, or `unknown`;
the wizard offers a mutation only after the adapter and account prove support.
When it is verified enabled, or the organizer explicitly confirms it because the
provider cannot verify it, the sync coordinator watches bracket start and every
real provider transition to `CALLED`. Provider synchronization and authorized
Dashboard changes enter one idempotent player-call workflow, so every occurrence
calls its players once even when both sources observe it concurrently.

## Technical Context

**Language/Version**: Python 3.12+, TypeScript 6.0, React 19

**Primary Dependencies**: FastAPI, Pydantic v2, psycopg 3 async compatibility
storage, discord.py 2.x, LangGraph/LangChain provider adapters, React Router 7,
Zustand 5, Axios, Tailwind CSS 3

**Storage**: PostgreSQL 17 is the sole runtime store. Existing SQLite support is
limited to explicit tests and migration/recovery tooling. Tournament logos and
player broadcast images reuse the validated workspace-owned image store and
current Cloudinary/local URL precedence.

**Testing**: pytest/pytest-asyncio; disposable PostgreSQL integration tests for
workspace isolation, concurrency, activation, migration, and outbox behavior;
Vitest/React Testing Library; TypeScript/Vite production build

**Target Platform**: Web administration UI plus FastAPI API, Discord bot, and
background workers in local Docker and hosted deployment

**Project Type**: Web application with API, React frontend, provider adapters,
Discord gateway runtime, and background workers

**Performance Goals**: restore a saved draft in under 1 second at p95 excluding
external provider calls; autosave a valid local change in under 750 ms at p95;
resolve a normally responding provider in under 10 seconds; complete an explicit
AI connection test in under 60 seconds for 95% of normally completing provider
responses; reflect normally observed provider-roster changes within two minutes;
never hold a database transaction open during a network call

**Constraints**: every query and effect is workspace-scoped from the trusted
session; secrets never enter draft JSON, browser state, URLs, logs, errors, audit
details, exports, or templates; encrypted credentials fail closed without the
service key; activation and external effects are idempotent; no automatic or AI
disqualification; no silent provider Event selection; WCAG-oriented keyboard and
responsive behavior; preserve existing overlay asset URLs and precedence;
registration windows and challenge expiry use server time; player fields use the
canonical `prefix` and `gamertag` vocabulary; configured Gamertag matching is
exact and collision-aware

**Scale/Scope**: five wizard steps, two bracket providers, one shared managed
Discord application serving many workspace guild bindings, two customer-owned AI
providers, reusable non-secret templates, and concurrent drafts across many
workspaces. A single workspace may retain both AI provider connections while one
is active. Each tournament may have one Discord registration window and many
tournament-scoped enrollments while reusing verified Workspace player identities.

## Constitution Check

*GATE: Passed before research and passed again after design.*

| Principle | Design evidence | Gate |
|---|---|---|
| I. Workspace isolation | Drafts, integration accounts, settings, bindings, readiness results, assets, usage, WebSocket messages, jobs, and bot routing derive `workspace_id` from the authenticated principal or claimed job. Resource lookup uses `(workspace_id, id)` and cross-workspace results are indistinguishable from not found. | PASS |
| II. PostgreSQL source of truth | New runtime tables and transactions target PostgreSQL. SQLite remains an explicit unit-test/migration source only, with no fallback or dual write. Completion of feature 003 PostgreSQL/workspace identity gates is a blocking prerequisite. | PASS |
| III. Secret and external-effect safety | Gemini/OpenAI credentials use authenticated encryption in `integration_credentials`; OAuth state is hashed and short lived; all public projections are redacted. Activation commits local state first and queues provider/Discord work through idempotent outbox commands. Unknown outcomes reconcile before retry. | PASS |
| IV. Assets and approved operations | Tournament logos and player images reuse deterministic validation and the workspace-owned image store without hidden AI calls. Attendance and registration failures notify or escalate only. Result reporting and manual single-player DQ keep their authorization and approval paths; automatic/AI DQ is removed and regression-tested. | PASS |
| V. Verification before cutover | The rollout requires migration fidelity, two-workspace isolation, encrypted-secret, PostgreSQL concurrency, bot routing, provider failure, activation idempotency, asset preservation, and manual acceptance evidence. | PASS |

No constitution exception is required. Implementation MUST stop before wizard
cutover if the workspace identity/PostgreSQL gates from feature 003 are not
complete or if the automatic-DQ regression gate fails.

## Project Structure

### Documentation (this feature)

```text
specs/004-tournament-setup-wizard/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── tournament-setup-api.md
│   ├── wizard-ui.md
│   └── migration-and-safety.md
└── tasks.md                 # Created later by /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── api/
│   ├── main.py
│   ├── schemas.py
│   └── routers/
│       ├── tournament_setup.py      # Draft, validation, readiness, activation
│       ├── integrations.py          # Reusable account and secret lifecycle
│       ├── ai_service.py            # Workspace assistant config/test projection
│       ├── providers.py             # Provider-neutral discovery/preview
│       ├── player_registration.py   # Config, roster recheck, organizer actions
│       ├── assets.py                # Existing validated logo upload path
│       └── discord_oauth.py         # Managed-bot install callback and guild binding
├── core/
│   ├── database_schema.py
│   ├── schema_migrations.py
│   ├── integrations.py
│   ├── ai_service.py
│   ├── tournament_setup.py          # Draft aggregate and activation transaction
│   ├── tournament_readiness.py
│   ├── player_registration.py       # Window, enrollment, proof, image policy
│   ├── registration_sync.py         # Exact-scope roster reconciliation
│   ├── tournament_templates.py
│   ├── bot_routing.py               # Workspace/guild/tournament resolution
│   ├── provider_discovery.py
│   ├── image_store.py
│   ├── workflow_outbox.py
│   └── providers/
│       ├── startgg/
│       └── challonge/
├── bot/
│   ├── main.py                      # Multi-guild managed bot runtime
│   ├── registration.py              # Tournament-bound registration flow
│   ├── match_threads.py
│   └── messages.py                  # Validated template rendering
└── tests/
    ├── test_tournament_setup_*.py
    ├── test_workspace_ai_*.py
    ├── test_discord_routing_*.py
    ├── test_provider_resolution_*.py
    └── test_no_automatic_dq.py

frontend-react/
└── src/
    ├── App.tsx
    ├── features/
    │   ├── tournament-setup/
    │   │   ├── TournamentSetupPage.tsx
    │   │   ├── api.ts
    │   │   ├── types.ts
    │   │   ├── store.ts
    │   │   ├── components/
    │   │   └── __tests__/
    │   ├── hub/components/AISettings.tsx
    │   └── editor/
    └── store/
```

**Structure Decision**: Keep the existing API/BOT/VITE layout. Add one bounded
frontend feature and domain services behind thin routes. Reuse the integration,
image, provider, outbox, authentication, and editor infrastructure instead of
creating wizard-only credential or upload systems.

## Architectural Decisions

### 1. Server-owned resumable draft

`TournamentSetupDraft` is a workspace-owned aggregate with a UUID, lifecycle,
current step, integer version, selected reusable account identifiers, and a
validated non-secret JSONB answer document. The UI keeps an editing copy, but the
server is authoritative. Debounced PATCH requests include the last version;
stale writes receive `409 draft_version_conflict` with the latest safe draft.
OAuth callbacks return to the draft through a short-lived hashed state record.

### 2. Explicit provider scope and provenance

A provider-neutral resolver accepts an account ID plus a locator. It returns a
preview with canonical tournament and scope identifiers, display metadata,
source, freshness, access state, and a capability matrix. A Start.gg Event slug
selects exactly that Event. A tournament locator returns all Events and leaves
selection empty until the organizer chooses. Challonge currently exposes one
managed bracket. The active tournament stores the exact account/tournament/scope
binding; display overrides live separately from provider facts.

### 3. Workspace BYOK for AI

Gemini and OpenAI become normal workspace integration accounts whose API key is
stored as encrypted `api_key` credential material. `WorkspaceAIConfiguration`
references one active AI integration and retains the current provider, model,
mode, limits, timeout, and immutable safety-policy meaning. API responses expose
only configured/test/health metadata. Replacing a key is atomic for new requests;
in-flight requests keep the already decrypted value in process memory only.

The legacy `ai_service_config(id=1)` and `ai_service_secrets` rows are not used as
fallbacks. A platform administrator may explicitly copy the legacy configuration
to one chosen workspace through an audited migration command, then disable the
legacy source. No API key is copied into a draft or tournament row.

### 4. Shared managed Discord bot with explicit routing

The initial product uses one platform-managed Discord application/token. A
workspace authorizes the installation and selects a guild it may manage; the
workspace account stores installation identity and safe health metadata, while
the application bot token remains a platform secret. Tournament bindings select
match and escalation destinations, moderator role, thread behavior, language,
tone, and templates. The bot resolves every inbound guild/channel/thread and
outbound command to exactly one enabled workspace/tournament binding. Ambiguous
or absent routing fails closed. The existing single
`ACTIVE_DISCORD_WORKSPACE_ID`/`ACTIVE_DISCORD_ACCOUNT_ID` process assumption is
removed before wizard activation is enabled.

### 5. Readiness, materialization, and activation

Readiness is computed server-side and grouped by wizard step. Required failures
block materialization or activation; optional Discord/AI omissions are explicit
warnings. Materialization locks the draft, verifies its version and readiness,
creates a configured tournament and its child settings in one PostgreSQL
transaction, and marks the draft materialized. Activation is a separate endpoint
that locks the configured tournament, rechecks readiness, changes local status to
active, and inserts one idempotent initial-sync outbox record.
Repeated calls with the same idempotency key return the same result. No provider
network call occurs inside either transaction.

Remote start for both Start.gg and Challonge is a separate confirmed command with
provider-authorized adapters, capability, freshness, permission, idempotency,
resulting-state verification, and reconciliation checks. The Epic remains
blocked if either provider lacks an authorized and tested contract; ordinary
local activation remains separate and available.

### 6. Safe operating profile and future AI capabilities

Manual and assisted presets are immutable seeds copied to a tournament profile,
then edited through explicit overrides. Both use human result approval. Attendance
expiry can remind and escalate but cannot disqualify. Existing automatic-DQ
fields, timer calls, API wording, and UI toggles are removed or permanently
disarmed as a prerequisite.

Translation, player conversation, result extraction, opponent confirmation, and
dispute handling remain visibly unavailable. The data model reserves no generic
"AI action" switch. Any later capability needs a typed proposal, known match,
score/Gamertag preservation, ambiguity handling, and authorized human approval.

For provider-verified or explicitly organizer-confirmed Start-in-wave, assisted
dispatch waits for bracket start and consumes fresh provider match-state
transitions. Every real transition to `CALLED`, including the first provider wave,
uses the same durable call-occurrence key as an authorized Dashboard transition.
Duplicate snapshots, concurrent sources, delivery retries, and worker restarts
therefore create one Discord call per match occurrence. Organizer confirmation
stores actor and time and remains labeled separately from provider verification.
Unknown, stale, or contradictory provider evidence blocks provider-wave
monitoring while authorized Dashboard calls remain available.

### 7. Tournament-scoped Discord player registration

Registration is configured inside the Discord step but stored independently from
bot presentation settings. A server-enforced opening/closing window controls one
tournament registration destination. Provider registration defaults to required
for provider-backed tournaments; an optional policy may create explicitly
unmatched Discord enrollments, but match automation waits for an exact entrant
link.

Reusable Workspace player records expose `prefix` and `gamertag`; legacy player
`team` and `name` survive only at documented migration boundaries. Provider
adapters map sponsor/team/clan data to `prefix` and competitive tags to
`gamertag` without combining them.

Reusable Workspace player and provider-identity records hold identity proof.
`TournamentPlayerEnrollment` separately holds exact Event/bracket membership,
provider snapshot freshness, image readiness, and review status. The organizer
chooses exact Gamertag matching, a bot-managed server nickname change to the
Gamertag, or either method. Duplicate/normalized collisions go to review.
Start.gg bio verification is a separate optional method and uses a hashed,
one-use, attempt-limited challenge bound to workspace, tournament, Event,
Discord user, and claimed profile. Challonge retains the Gamertag/nickname method
because it has no equivalent bio flow. Scheduled open/close notices, roster
diffs, role grants, and Discord
responses run through idempotent jobs. Player images use deterministic validation;
the registration path does not call a service-global AI key or silently consume
the Workspace assistant credential.

The organizer may also manage an explicit Discord ID from each provider entrant
row. The service validates snowflake shape, resolves a non-bot member in the
bound guild, enforces one-to-one tournament uniqueness, and audits link, replace,
and unlink. A valid manual link is authoritative for future tournament routing;
queued effects reconcile on change while completed deliveries remain historical.

## Delivery Sequence

1. **Safety and platform gates** — finish feature 003 PostgreSQL/workspace
   identity cutover, establish a stable workspace-scoped tournament identity,
   remove all automatic-DQ behavior and misleading UI/schema defaults, and add
   regression tests before exposing the wizard.
2. **Schema and repositories** — add draft, AI config, provider binding, brand,
   operating profile, Discord binding, registration configuration, enrollment,
   verification challenge, bot experience, template, readiness, and idempotency
   storage with workspace foreign keys and PostgreSQL constraints.
3. **Workspace AI BYOK** — reuse encrypted integration credentials, add Gemini
   and OpenAI adapters behind the existing assistant interface, scope config and
   usage to workspace/account/tournament, implement explicit test/rotate/disable/
   remove flows, and add the one-time legacy assignment command.
4. **Provider discovery and operations** — implement non-persisting Start.gg and
   Challonge resolution, exact Event selection, entrant snapshots,
   provenance/freshness/capability projection, authorized remote start for both
   providers, Start-in-wave monitoring, and errors that preserve the draft.
5. **Draft and activation services** — implement create/resume/versioned patch,
   validation/readiness, template seeding, atomic activation, and outbox-driven
   initial sync.
6. **Discord onboarding and routing** — add managed-bot authorization return,
   guild/channel/role discovery, effective permission checks, explicit tournament
   destinations, message-template validation/preview, and multi-workspace bot
   routing.
7. **Player registration** — add tournament windows, registration messages,
   exact-scope roster synchronization, canonical Prefix/Gamertag fields,
   configurable exact Gamertag/nickname verification, optional Start.gg bio
   challenges, Challonge fallback, manual Discord ID linking from entrant rows,
   image policy, enrollment dashboard, role updates, and migration from the
   global registration flow.
8. **Branding projection** — bind validated logo assets and local names/colors to
   Hub, Editor, and authorized overlay projections while preserving existing
   asset URLs and fallbacks.
9. **Wizard UI** — add protected routes, accessible stepper, step summaries,
   debounced save state, authorization return recovery, advanced sections,
   actionable inline/summary errors, connection drawers, and final review with
   distinct save/activate/remote-start language.
10. **Acceptance and rollout** — run two-workspace isolation, migration,
   concurrency, provider outage, AI error mapping, Discord permission/routing,
   keyboard/mobile, asset preservation, and activation recovery suites. Enable
   the route behind a feature flag only after the blocking gates pass.

## Verification Strategy

- Unit tests cover locator parsing, Event selection, capability projection,
  preset expansion, registration-window boundaries, verification challenge
  expiry, Prefix/Gamertag mapping, exact/collision-aware name matching, nickname
  changes, Discord ID validation/uniqueness, image policy, template variables, readiness
  rules, redaction, provider error classification, and the absence of automatic
  DQ.
- PostgreSQL integration tests cover workspace predicates, foreign keys,
  optimistic draft concurrency, one-time activation, credential rotation races,
  usage reservations, registration uniqueness, roster-diff and Discord-job
  idempotency, and two workspaces tracking the same external Event.
- Adapter contract tests use recorded redacted fixtures/fakes for Start.gg,
  Challonge, Discord, Gemini, and OpenAI. Default CI never spends customer AI
  quota or mutates a live bracket/server.
- Frontend tests cover keyboard traversal, focus on errors, step restoration,
  auth-return restoration, secret input clearing, provider Event choice, optional
  skip states, responsive layout, and final action labels.
- Operational acceptance verifies bot routing across two guilds/workspaces,
  registration routing across two simultaneous tournaments, optional Start.gg bio
  proof without retained plaintext code/profile content, Challonge Gamertag
  fallback, nickname permission behavior, and manual Discord ID link/edit/unlink,
  explicit legacy migration, service-key fail-closed startup, encrypted values at
  rest, redacted telemetry, logo preservation, and recovery after process failure
  between activation commit and initial sync.

## Rollout and Rollback

Ship schema and read-compatible services first, with the wizard route and
activation endpoint disabled. Migrate only non-secret legacy settings
automatically. Require explicit platform-admin selection for any legacy AI secret
or global Discord compatibility record. Run shadow readiness against existing
tournaments without changing them, then enable draft creation, then activation.

Rollback disables new draft creation/activation and leaves already activated
tournaments on the canonical tables. Pending outbox work is paused and reconciled
before retry. Additive columns/tables remain until retention permits removal;
credentials are disabled or re-bound, never decrypted for export. Legacy global
AI/Discord fallbacks stay disabled throughout rollback so isolation is not
weakened.

## Post-Design Constitution Re-check

The completed data model and contracts keep workspace ownership on every new
resource, place runtime state in PostgreSQL, keep credentials behind authenticated
encryption, separate local commits from idempotent external effects, preserve the
validated image path, and prohibit automatic/AI DQ. No unresolved clarification
or constitutional violation remains.
