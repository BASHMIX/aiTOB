# Contract: Migration, Safety, and Cutover

## Blocking gates

The wizard activation flag remains off until all of these are true:

1. Feature 003 has one PostgreSQL runtime source and non-null workspace ownership
   for tournaments, accounts, assets, commands, usage, WebSockets, and workers.
2. Tournaments have a stable UUID and workspace-scoped slug lookup.
3. Runtime repositories have no legacy global provider/Discord/AI fallback.
4. Automatic-DQ timers, service calls, schema defaults, API copy, and UI controls
   are removed or converted to notification/escalation-only behavior.
5. Multi-workspace Discord routing passes two-guild/two-workspace acceptance.
6. Credential encryption fails closed and all secret-redaction tests pass.
7. Registration routing passes two-simultaneous-tournament acceptance and no
   runtime path uses a global active Workspace/tournament fallback.

## Additive migration order

1. Add stable tournament identity and validate/backfill ownership.
2. Change integration account uniqueness to workspace scope and validate legacy
   `owner_id`/`workspace_id` agreement.
3. Add draft, connection-health, workspace-AI-config, provider binding, brand,
   profile, Discord binding, registration config/enrollment/challenge/roster,
   template, readiness, and idempotency structures.
4. Add required AI usage attribution columns and quarantine historical rows that
   cannot be mapped unambiguously. Never guess a workspace.
5. Deploy new repositories in dark/read-compatible mode.
6. Migrate safe non-secret defaults only.
7. Run explicit selected-workspace migrations for legacy AI/Discord/provider
   records where needed.
8. Switch API/bot/worker reads atomically to workspace paths and disable fallback.
9. Enable draft creation, then materialization/activation after acceptance.

## Legacy AI assignment

A platform-admin-only command receives a target workspace and expected provider.
It previews only whether legacy config/key exist and their provider type. On
execute it:

1. locks the migration record and verifies it was not completed;
2. decrypts legacy ciphertext using `AITOB_AI_SERVICE_MASTER_KEY`;
3. validates provider/config compatibility;
4. creates/updates the target workspace integration account;
5. re-encrypts plaintext using `AITOB_INTEGRATION_MASTER_KEY`;
6. creates the workspace assistant config and health `configured_untested`;
7. writes a redacted standard audit event and completion marker;
8. clears plaintext from process references as soon as practical.

The command is idempotent. Failure rolls back the target write and does not mark
completion. It never copies ciphertext between encryption domains, assigns a key
to multiple workspaces, returns the key, or enables a legacy runtime fallback.
Legacy rows remain read-only for the approved rollback window, then follow the
secret retention/purge procedure.

## Legacy Discord/provider settings

Global settings are compatibility input only. An explicit migration selects the
workspace/account/guild/tournament binding and writes safe audit evidence. Values
that cannot be attributed unambiguously remain quarantined and appear as an
operator migration blocker, not an active wizard default.

The shared Discord bot token is a platform deployment secret. Customer workspace
records contain installation/guild identity and encrypted user OAuth refresh
material only when needed for discovery. Existing per-account bot tokens are not
silently treated as shared-bot installations.

## Generic automatic-DQ removal

The implementation removes executable mutation behavior from `auto_dq_match`
and removes the generic setting from new API/UI contracts. Existing stored
`auto_dq_enabled=true` rows are migrated to false. Provider-specific attendance
uses the shared command service: Start.gg keeps zero attendance on its native
Double-DQ path, resolves exactly one verified attendee only after the mirrored
deadline, and starts Hub/broadcast play when both attend. Challonge supports
authorized single-player DQ only.

Acceptance proves:

- no AI proposal, unverified identity, or speculative local timer selects a
  winner;
- deadline resolution uses fresh entrant/provider state and verifies the remote
  result before local completion;
- provider-native completed/DQ state may synchronize inward but is never claimed
  as an aiTOB automatic action.
- provider-verified or explicitly organizer-confirmed Start-in-wave waits for the
  remote start and sends one Discord call for every real provider-owned `CALLED`
  transition, including the first wave. Provider sync and authorized Dashboard
  transitions share one durable occurrence key, so concurrent observation and
  restart do not duplicate delivery. Organizer confirmation remains labeled and
  auditable rather than being rewritten as provider verification.

## Legacy player registration cutover

The current global Discord registration flow is compatibility input only. Cutover
creates tournament-scoped configuration and enrollments; it does not infer a
tournament by the process-global active workspace or by scanning all tracked
tournaments. Existing player identity and valid image references may be assigned
to one Workspace after ownership is proven. Existing Start.gg identity links may
be reused as identity proof, but each tournament still checks exact Event
membership.

Player schema migration adds canonical `prefix` and `gamertag` fields. It maps
legacy player `team` to `prefix` and player `name` to `gamertag`, validates the
backfill, changes bot/API/Editor/overlay/import/export readers and writers, then
keeps the old columns only as versioned read-only compatibility aliases for the
published migration window. Tournament names, Workspace names, bot names, and
other non-player `name` fields are not renamed.

Legacy `registration_deadline` may populate `closes_at` only when its tournament
and timezone are unambiguous. `opens_at`, destination, provider requirement, and
image policy require explicit organizer review. Unattributable records remain
quarantined and cannot become `ready` automatically.

Legacy Discord IDs may be copied only when Workspace, tournament, and entrant
ownership are unambiguous. Every copied ID is re-resolved against the selected
guild, checked for bot/conflict status, and marked pending until that validation
succeeds. The migration does not guess links from global player rows.

Existing pending bio verifications are invalidated at cutover because they lack
the complete workspace/tournament/Event binding and may store plaintext codes.
They are not copied to the new challenge table. The migration records safe counts,
purges plaintext under retention policy, and asks players to start a fresh
challenge. Fetched provider bio is never persisted in the new flow.

The existing image-safety helper must not invoke `GOOGLE_API_KEY` or
`GEMINI_API_KEY` from the default registration path. Technical image validation
stays deterministic. Any future external content moderation requires a separate
Workspace-scoped, disclosed privacy/billing contract and must fail according to
that contract rather than silently allowing or blocking registration.

## External effects

Provider sync/start/report and Discord delivery occur through durable commands
with workspace, actor/origin, operation, target, idempotency key, state, attempt,
lease, and safe outcome. Local transactions may enqueue work but do not wait on
network calls. A crash after the remote effect and before local success yields an
unknown outcome and reconciliation check, never an immediate blind retry.

Connection tests are deliberate read/minimal-completion operations. Their
classified outcomes may update health but cannot mutate tournaments, brackets,
Discord channels, or assistant policy.

## Secret and privacy assertions

Automated tests search API responses, database non-secret columns, logs, audit,
error telemetry, exports, drafts, templates, URLs, and browser persistence for
submitted test secrets. The plaintext must appear nowhere. Wrong/missing service
keys fail credential operations and AI use, while non-secret draft editing and
manual tournament operation continue.

OAuth state is random, hashed at rest, expires, is consumed once, and binds
provider/workspace/user/draft/return step. Callback query data is redacted before
access logging and never becomes browser state after exchange.

## Rollback

Rollback disables route/activation feature flags, pauses new commands, and
reconciles pending/unknown external effects. Already materialized tournaments
remain on canonical workspace tables. Additive schema remains until retention
allows removal. Legacy read paths are not re-enabled automatically because that
would restore cross-workspace/global secret behavior; any emergency legacy use
requires an explicit operator procedure and containment record.

## Required evidence

- Migration rehearsal and final PostgreSQL row-count/constraint report.
- Two-workspace isolation matrix, including guessed IDs and duplicate external
  Event imports across workspaces.
- PostgreSQL draft conflict, activation idempotency, usage reservation, and outbox
  concurrency results.
- Redaction and encryption failure tests.
- Start.gg direct Event and multi-Event selection tests.
- Challonge OAuth refresh and preview tests.
- Discord effective-permission and two-guild routing tests.
- Tournament registration window boundaries, exact-Event roster synchronization,
  exact Gamertag and bot-managed nickname policies, optional Start.gg hashed bio
  challenge, Challonge fallback, manual Discord ID add/edit/unlink and guild
  validation, Prefix/Gamertag projections, deterministic image validation, and
  two-tournament Discord routing tests.
- Migration evidence that legacy pending plaintext verification codes are not
  copied and that no global active-workspace registration fallback remains.
- Gemini/OpenAI classified failure tests using fakes; optional live smoke is
  manually invoked with disposable credentials.
- Keyboard, RTL, mobile, OAuth-return, and error-focus UI acceptance.
- Existing image URL/overlay snapshot comparison.
- No-automatic-DQ regression and human result-approval evidence.
