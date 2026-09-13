# Contract: Tournament Setup HTTP API

All endpoints use JSON unless noted. They require the existing authenticated
session and derive `workspace_id` from it. IDs belonging to another workspace
return the same `404` response as missing IDs. Mutation endpoints retain the
existing CSRF/origin protections. No response contains credentials, OAuth codes,
authorization headers, raw provider errors, or stable credential fingerprints.

## Common types

```ts
type WizardStep = 'provider' | 'tournament' | 'discord' | 'assistant' | 'review';
type DraftStatus = 'editing' | 'ready' | 'materialized' | 'abandoned';
type ReadinessState = 'ready' | 'warning' | 'blocked';

interface ApiProblem {
  code: string;
  message: string;            // safe localized/default message
  trace_id: string;
  step?: WizardStep;
  field_path?: string;
  retryable: boolean;
  latest_draft?: TournamentSetupDraft; // only for revision conflict
}

interface ReadinessCheck {
  code: string;
  step: WizardStep;
  field_path?: string;
  requirement: 'required' | 'optional';
  state: ReadinessState;
  message: string;
  remediation?: string;
  retryable: boolean;
}
```

Expected status codes are `400` malformed input, `401` unauthenticated, `403`
missing permission, `404` missing/inaccessible resource, `409` revision or
lifecycle conflict, `422` field validation, `429` workspace/provider throttling,
and `502`/`503` redacted provider failure.

## Draft lifecycle

### Create a draft

`POST /api/tournament-setup/drafts`

Requires `tournament.manage`.

```json
{
  "template_id": "optional-uuid"
}
```

Returns `201` and a `TournamentSetupDraft`. Template seeding applies allow-listed
preferences only.

### List resumable drafts

`GET /api/tournament-setup/drafts?status=editing,ready&limit=20`

Requires `tournament.manage`. Returns the current workspace’s safe summaries.

### Read a draft

`GET /api/tournament-setup/drafts/{draft_id}`

Requires `tournament.manage`.

```ts
interface TournamentSetupDraft {
  id: string;
  revision: number;
  status: DraftStatus;
  current_step: WizardStep;
  completed_steps: WizardStep[];
  provider_scope: ProviderScopeAnswer | null;
  tournament_review: TournamentReviewAnswer;
  operating_profile: OperatingProfileAnswer;
  discord_setup: DiscordSetupAnswer;
  assistant_setup: AssistantSetupAnswer;
  validation: { errors: ReadinessCheck[]; warnings: ReadinessCheck[] };
  materialized_tournament_id: string | null;
  created_at: string;
  updated_at: string;
}
```

`assistant_setup` contains an account ID and non-secret status only. It never
contains an API key.

### Patch one draft section

`PATCH /api/tournament-setup/drafts/{draft_id}`

Requires `tournament.manage` and `If-Match: "<revision>"`. The body changes one
section so validation and conflict recovery remain precise.

```json
{
  "section": "tournament_review",
  "current_step": "tournament",
  "value": {
    "display_name": "Baghdad Weekly #12",
    "short_name": "BW12",
    "timezone": "Asia/Baghdad",
    "accent_color": "#7C3AED"
  }
}
```

Returns `200` with the new full safe draft and `ETag: "<new revision>"`.
`409 draft_version_conflict` includes the latest safe draft and performs no
partial write. Secret-shaped keys are rejected with
`422 secret_field_not_allowed`.

### Change current step

Step movement uses the same PATCH contract with `section: "navigation"`. Moving
forward validates the current step; moving backward or through already-completed
steps remains available. The URL step is presentation state and cannot mark a
server step complete by itself.

### Abandon a draft

`DELETE /api/tournament-setup/drafts/{draft_id}` with `If-Match`.

Returns `204`. This soft-abandons the draft and applies retention rules to
unreferenced draft logo assets.

## Provider resolution

### Resolve locator without creating a tournament

`POST /api/tournament-setup/drafts/{draft_id}/provider-resolution`

Requires `tournament.manage`, a matching draft revision, and a same-workspace
active Start.gg/Challonge account.

```json
{
  "revision": 3,
  "provider_account_id": "uuid",
  "locator": "tournament/example/event/ultimate-singles",
  "challonge_subdomain": null
}
```

```ts
interface ProviderResolution {
  resolution: 'selected_scope' | 'scope_selection_required';
  provider: 'startgg' | 'challonge';
  account_id: string;
  tournament: ProviderObject;
  scopes: ProviderScope[];
  selected_scope: ProviderScope | null;
  capabilities: {
    remote_start: Capability;
    start_in_wave_read: Capability;
    start_in_wave_write: Capability;
    result_reporting: Capability;
  };
  start_in_wave: {
    state: 'verified_enabled' | 'verified_disabled' | 'unsupported' | 'unknown';
    observed_at: string;
    monitoring_mode: 'off' | 'provider_verified' | 'organizer_confirmed';
    organizer_confirmation: {
      confirmed: boolean;
      confirmed_at: string | null;
    };
    monitoring_state: 'not_applicable' | 'awaiting_bracket_start' |
      'monitoring' | 'blocked';
  };
  observed_at: string;
  freshness_seconds: number;
  draft: TournamentSetupDraft;
}

interface ProviderObject {
  external_id: string;
  canonical_slug?: string;
  name?: ProviderFact<string>;
  starts_at?: ProviderFact<string>;
  timezone?: ProviderFact<string>;
  state?: ProviderFact<string>;
  logo_url?: ProviderFact<string>;
}

interface ProviderScope {
  kind: 'event' | 'bracket';
  external_id: string;
  canonical_slug?: string;
  name: ProviderFact<string>;
  game?: ProviderFact<string>;
  format?: ProviderFact<string>;
  state?: ProviderFact<string>;
}

interface ProviderFact<T> {
  value: T | null;
  source: 'provider' | 'unavailable';
  observed_at: string;
}

interface Capability {
  state: 'supported' | 'unsupported' | 'unknown';
  reason_code: string;
}
```

Start.gg behavior is normative:

- Event slug/URL: select the exact resolved Event.
- Tournament slug/URL with one Event: may return that Event selected, while still
  showing it for confirmation.
- Tournament slug/URL with multiple Events: return
  `scope_selection_required`; `selected_scope` is null.
- Never strip an Event suffix and never choose array index zero implicitly.
- With provider-verified Start-in-wave, or an explicit authorized organizer
  confirmation when verification is unavailable, activation begins in
  `awaiting_bracket_start`. A fresh provider sync that observes bracket start
  advances monitoring; every real provider transition to `CALLED`, including the
  first wave, creates or reuses the same player-call occurrence used by an
  authorized Dashboard transition.
- Stable match and transition versions deduplicate concurrent sources, duplicate
  snapshots, retries, and worker restarts. Unknown/unsupported status without
  organizer confirmation, and stale or contradictory observations, do not enable
  provider-wave monitoring; authorized Dashboard calls remain available.

Organizer confirmation is written through the draft operating-profile PATCH. It
records actor/time server-side, can be revoked, and is always projected as
`organizer_confirmed`, never `verified_enabled`.

### Select one returned scope

`PUT /api/tournament-setup/drafts/{draft_id}/provider-scope`

```json
{
  "revision": 4,
  "external_scope_id": "event-id-from-latest-resolution"
}
```

The ID must belong to the draft’s latest fresh resolution. Returns the updated
draft. Provider failure preserves all prior draft answers.

## Logo binding

Use the existing validated image upload pipeline with the additional owner type
`tournament_setup_draft` and asset type `tournament_logo`:

- `POST /api/tournament-setup/drafts/{draft_id}/logo` (`multipart/form-data`,
  revision included)
- `DELETE /api/tournament-setup/drafts/{draft_id}/logo` (`If-Match`)

The service decodes the image, enforces configured MIME/size/dimension rules,
stores a workspace-owned asset, and returns only its public/authorized asset
projection. On materialization the same asset reference is rebound atomically;
the image is not re-uploaded or copied.

## Discord managed-bot connection

### Start authorization/install

`POST /api/integrations/discord/authorize`

Requires `integrations.manage`.

```json
{
  "draft_id": "uuid",
  "return_step": "discord"
}
```

Returns a short-lived `authorization_url`. It contains opaque state but no
workspace/draft/credential data. The callback atomically consumes the stored
state, reauthorizes the session, stores encrypted user OAuth material only when
needed for guild discovery, and redirects to the enumerated draft route with a
safe outcome code.

`GET /api/integrations/discord/callback?code=...&state=...` is provider-facing.
The code/state must never be copied into logs or a subsequent client API body.

### Discover resources

- `GET /api/integrations/{account_id}/discord/resources`
- `POST /api/integrations/{account_id}/discord/recheck`

Requires a same-workspace Discord account. The safe response contains guild,
text/forum channel, and role IDs/labels plus the bot’s effective permission
checks. Channel lists never include content or member messages.

### Preview a message

`POST /api/tournament-setup/drafts/{draft_id}/discord/template-preview`

```json
{
  "template_key": "match_call",
  "template": "{{player_1}} vs {{player_2}} — report to {{destination}}"
}
```

Returns rendered synthetic sample content and invalid-variable errors. Preview
and delivery share the same renderer, escaping, variable registry, and length
limits. The endpoint sends no Discord message.

## Tournament player registration

### Configure the registration section

The draft `discord` section accepts the following safe object; after
materialization the equivalent resource is available at
`GET|PUT /api/tournaments/{tournament_id}/registration/config`:

```ts
interface TournamentRegistrationConfig {
  enabled: boolean;
  destination_external_id: string | null;
  opens_at: string | null;
  closes_at: string | null;
  display_timezone: string;
  require_provider_registration: boolean;
  gamertag_verification_policy: 'exact_discord_name' |
    'set_server_nickname' | 'match_or_set_nickname';
  startgg_bio_verification_enabled: boolean;
  image_policy: 'disabled' | 'optional' | 'required';
  verified_role_external_id: string | null;
  reminder_offsets_minutes: number[];
  status: 'scheduled' | 'open' | 'closed' | 'disabled' | 'degraded';
}
```

When enabled, destination, opening, closing, and a valid timezone are required;
the server requires `opens_at < closes_at`. Provider-backed tournaments default
`require_provider_registration` to true. Bio verification is an optional
Start.gg-only method and is rejected for Challonge. Disabling registration does
not delete existing enrollments.

### Operate and synchronize registration

- `POST /api/tournaments/{tournament_id}/registration/open`
- `POST /api/tournaments/{tournament_id}/registration/close`
- `POST /api/tournaments/{tournament_id}/registration/recheck`
- `GET /api/tournaments/{tournament_id}/registrations?state=...&cursor=...`
- `PUT /api/tournaments/{tournament_id}/registrations/{enrollment_id}/discord-link`
- `DELETE /api/tournaments/{tournament_id}/registrations/{enrollment_id}/discord-link`
- `POST /api/tournaments/{tournament_id}/registrations/{enrollment_id}/approve-link`
- `POST /api/tournaments/{tournament_id}/registrations/{enrollment_id}/request-image`
- `POST /api/tournaments/{tournament_id}/registrations/{enrollment_id}/reject`

Organizer mutation endpoints require `tournament.manage`, an idempotency key, and
an explicit workspace/tournament binding. Player-facing mutations enforce the
server registration window; authorized organizer corrections remain available
after close and are audited. Open/close also use a
schedule version so a superseded job cannot publish or disable the current
registration message. Recheck reads only the selected account and exact Event or
bracket and returns observation time, safe counts, affected enrollment IDs, and
classified errors; it never returns raw provider profiles.

Manual link accepts a write-only-in-the-form body such as
`{"discord_user_id":"303608372999000111"}`. The server canonicalizes the
snowflake, resolves it through the tournament's configured Discord guild, rejects
bot/service accounts, and enforces unique active Discord-user and provider-entrant
links within the tournament. It returns only the resolved member's safe ID/name,
`linked | not_in_guild | invalid | conflict`, and allowed next actions. Replace
and unlink record actor/time and reconcile queued future deliveries; sent delivery
history is immutable.

The configured Gamertag policy accepts an entrant ID from the latest fresh exact
scope snapshot. It compares the canonical provider `gamertag` with the exact
normalized Discord username/server display name, changes the server nickname to
that Gamertag when authorized, or permits either. Duplicate normalized Gamertags,
nickname permission failure, and collisions return a review state instead of a
first-match result. `approve-link` records organizer, time, and reason for those
review cases.

### Discord player interaction contract

Discord interactions carry a signed/custom ID that resolves server-side to one
workspace, tournament, guild, destination, and registration schedule version.
The bot rejects ambiguous, expired, wrong-guild, or wrong-channel context. It
does not accept a client-supplied workspace and does not scan all tournaments.

When the optional Start.gg bio method is enabled, the flow may create a one-use
bio challenge. Its plaintext code is
returned once only to the requesting Discord user; persistence keeps a keyed hash
and the bound workspace, tournament, Event, Discord user, claimed provider user,
attempt limit, and expiry. The expiry is the earlier of normal challenge TTL and
registration close. Confirmation fetches only the claimed profile, compares
bounded tokens, then discards the bio and plaintext. A reusable verified identity
can skip this proof when the configured policy permits but must still pass exact
Event membership. Challonge exposes only the configured Gamertag/Discord-name or nickname
change path because it has no bio method.

The image interaction accepts multipart content through the existing media
pipeline. It performs deterministic decode, type, size, dimension, and
normalization checks and returns a safe asset projection. The default path does
not invoke Gemini/OpenAI. Optional images may be kept/replaced/skipped; a required
image blocks `ready`.

Canonical player projections expose `prefix` and `gamertag`; `team` and `name`
are accepted only by documented versioned migration adapters and are never emitted
by the new contract. Enrollment responses expose stable local IDs, exact provider
entrant IDs when linked, Discord-link state, verification method/match state, safe state/reason,
image readiness, membership freshness, and allowed
organizer actions. They exclude challenge code/hash, profile bio, image bytes,
credentials, Discord message content, and provider raw payloads.

## AI connections and preserved assistant settings

### Read workspace AI config

`GET /api/ai/config`

Requires `workspace.read`. It returns the preserved assistant settings and safe
connection status:

```json
{
  "active_provider": "gemini",
  "selected_account_id": "uuid",
  "model": "gemini-model-name",
  "mode": "propose_only",
  "request_limit": 30,
  "token_limit": 60000,
  "context_char_limit": 12000,
  "response_char_limit": 4000,
  "request_timeout_seconds": 30,
  "policy_version": "organizer-assistant-v1",
  "connections": {
    "gemini": {
      "account_id": "uuid",
      "configured": true,
      "enabled": true,
      "health": "verified",
      "failure_category": null,
      "last_tested_at": "2026-09-13T10:00:00Z"
    },
    "openai": {
      "account_id": null,
      "configured": false,
      "enabled": false,
      "health": "missing",
      "failure_category": "missing_credential",
      "last_tested_at": null
    }
  }
}
```

### Update assistant settings

`PATCH /api/ai/config`

Requires `integrations.manage`. Accepts the existing model/mode/limit/timeout
fields and the selected AI account. `policy_version` is returned but cannot be
downgraded by a client. Selection validates workspace, provider, active status,
and credential presence transactionally.

### Add or replace a provider key

`PUT /api/ai/connections/{provider}/credential`, where provider is `gemini` or
`openai`.

Requires `integrations.manage`.

```json
{
  "api_key": "write-only-value"
}
```

Returns `200` with safe account/health projection. The request field is never
echoed. Replacement atomically overwrites ciphertext, increments its revision,
and sets health to `configured_untested`. It does not keep old ciphertext and
does not run an automatic paid provider request.

### Test, enable, disable, or remove a provider connection

- `POST /api/ai/connections/{provider}/test` with `{ "model": "..." }`
- `POST /api/ai/connections/{provider}/enable`
- `POST /api/ai/connections/{provider}/disable`
- `DELETE /api/ai/connections/{provider}/credential`

All require `integrations.manage`. Test is explicit and may consume a small
amount of the customer’s provider quota. Responses use safe categories:
`success`, `invalid_key`, `model_unavailable`, `quota_or_billing`,
`rate_limited`, `region_restricted`, `timeout`, `provider_unavailable`, or
`unknown`. Raw provider bodies are discarded after classification.

Disable/remove do not delete tournament settings or bindings. A selected removed
or disabled connection makes AI readiness degraded and AI calls unavailable;
manual operation and non-AI Discord templates continue.

Assistant invocation requires `assistant.use` and resolves the current
workspace configuration/account/key server-side. It never accepts an account ID
or workspace ID from the assistant request as authorization.

## Readiness, save tournament, and activate

### Compute readiness

`POST /api/tournament-setup/drafts/{draft_id}/readiness`

```json
{
  "revision": 9,
  "purpose": "draft_review"
}
```

Returns a timestamped set of required/optional checks grouped by step. Provider
and Discord checks may use cached observations within documented freshness
budgets; explicit recheck endpoints refresh them. A required `blocked` check
prevents materialization. Optional missing Discord/AI produces `warning`.

### Save as a configured tournament

`POST /api/tournament-setup/drafts/{draft_id}/materialize`

Headers: `Idempotency-Key: <uuid>` and `If-Match: "<revision>"`.

The server locks and revalidates the draft, creates one configured tournament and
all child bindings/profiles in one transaction, and marks the draft
`materialized`. Returns `201` on first creation or `200` on an idempotent replay:

```json
{
  "tournament_id": "uuid",
  "status": "configured",
  "draft_id": "uuid",
  "readiness": { "overall_state": "ready", "checks": [] }
}
```

### Activate aiTOB management

`POST /api/tournaments/{tournament_id}/activate`

Headers: `Idempotency-Key: <uuid>`. Requires `tournament.manage`. The server
recomputes readiness, marks the local tournament active, and queues one initial
provider sync after commit. It does not start the remote bracket.

### Start the remote bracket

`POST /api/tournaments/{tournament_id}/provider-start`

This endpoint is implemented for both Start.gg and Challonge through documented
or provider-authorized adapters. It requires a fresh provider snapshot,
sufficient scope/permission, compatible remote state, an idempotency key, and an
explicit confirmation token created from a fresh preflight. Unknown effects
reconcile before retry. If either adapter contract cannot be authorized and
verified, the Epic is blocked rather than substituting `markSetCalled`, browser
automation, or an undocumented mutation.

## Setup templates

- `POST /api/tournament-setup/templates` from a draft’s allow-listed preferences
- `GET /api/tournament-setup/templates`
- `PATCH /api/tournament-setup/templates/{template_id}`
- `DELETE /api/tournament-setup/templates/{template_id}`

All require `tournament.manage`. The serializer excludes provider/account IDs,
Event/bracket identifiers, dates, destinations, players, assets owned by another
tournament, health/test data, and any credential/secret-shaped value.

## Auditing contract

Credential lifecycle changes, tests, configuration changes, provider binding,
registration schedule and enrollment decisions, readiness decisions,
materialization, activation, and remote-start attempts write
the standard redacted `audit_events` row with workspace, actor, action, safe
target ID, outcome, trace ID, and safe categorical detail. Audit detail may list
changed field names and health/readiness codes. It may not contain request bodies,
templates containing player data, raw provider output, verification code/hash,
profile bio, image bytes, Discord message content, credential material, or OAuth
query values.
