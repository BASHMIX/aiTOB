# Tasks: Workspace SaaS Foundation

Status legend: **[x] verified**, **[~] implemented / pending an external
dependency or broader acceptance**, **[ ] not implemented**. Each task includes
implementation, UI/API linkage where relevant, automated verification, and an
operational check; a rehearsal is never a cutover.

## A. PostgreSQL runtime and reliable work

- [x] **T001 / FR-009, FR-011** Add fail-closed `DATABASE_URL` runtime gate and
  PostgreSQL storage adapter; test no URL prevents launcher/API/bot runtime.
- [x] **T002 / FR-011** Prove PostgreSQL query binding preserves literals,
  comments and dollar strings; test two independent approval connections.
- [x] **T003 / FR-011** Lock Outbox and station reservation candidates with
  PostgreSQL row locks; test concurrent workers/reservations and retry after
  transaction rollback.
- [x] **T004 / FR-009–011** Runtime storage conversion and the compatibility
  boundary are closed for API, bot and worker execution. Every runtime database
  call reaches `backend.core.storage.dbapi`; `require_runtime_database()` fails
  closed when `DATABASE_URL` is absent or non-PostgreSQL, and SQLite is accepted
  only for `AITOB_TESTING=1` or the explicit migration-tool mode. PostgreSQL
  repository acceptance and the full PG-targeted regression pass. The remaining
  compatibility entries are enumerated below and are not runtime bypasses:
  `backend/core/database.py:DB_PATH` is a path retained for test/migration
  callers but is resolved by `storage.connect`; `backend/api/auth.py`'s
  `AITOB_LEGACY_HUB_PASSWORD_COMPAT` is disabled by default and can map only to
  the single active Owner (it cannot select a workspace or bypass membership);
  `backend/api/routers/settings.py` exposes global service settings only behind
  the platform-admin gate and rejects migrated provider secrets, while account
  credentials use the integration-account repository; `backend/api/routers/
  tournaments.py`, `providers.py`, and `matches.py` retain direct-call/legacy
  principal signatures solely for staged migration fixtures, with authenticated
  HTTP requests requiring a session-derived workspace; `backend/bot/main.py`
  keeps one explicitly configured integration workspace for service-heartbeat
  and initial-registration contexts until those identities are migrated; and
  `backend/core/schema_migrations.py` plus the two marked SQLite-source tests
  are migration-only. No runtime module imports `aiosqlite`/`sqlite3` directly
  outside the adapter, and no runtime path falls back to a shared SQLite file.
  Function-level acceptance inventory:
  `settings.api_get_settings/api_patch_settings/api_get_env/api_patch_env/
  api_trigger_token_check` are platform-admin-only global controls;
  `hub.api_get_feed/api_clear_feed/api_bot_command/api_hub_command` use the
  session workspace, while `hub.api_get_status/api_reload_workflows/
  api_set_dispatcher_master` are platform-global; `tournaments.api_list_
  tournaments/api_add_tournament/api_get_sets/api_sync_bracket/
  api_tournament_sync_status/api_reset_tournament_hub/api_delete_tournament`
  and `planned_streams.api_*` pass the authenticated workspace into every
  repository; `matches.api_active_matches/api_call_match/api_player_ready/
  api_toggle_stream/api_send_match/api_reset_match/api_dq_match` and conflict
  paths enforce the same scope; provider capability/resolve/list routes require
  an account owned by that workspace. Bot `run_drain`, workflow dispatch,
  `get_players_tool`, CFN propagation and status/validation lookups carry the
  active integration workspace. The only unscoped signatures left are direct
  migration/test hooks, the opt-in owner-only compatibility identity, and
  service startup identity discovery; each is covered by a fail-closed or
  explicit-owner test and cannot be selected by a tenant request.
  Acceptance evidence:
  `test_postgres_storage.py` passes 18 isolated PG cases (2026-09-08), including
  casts, percent literals/modulo, escaped strings, nested comments, concurrent
  bootstrap/invitation/last-Owner protection and crash-after-effect recovery.
  `test_runtime_database_gate.py`: seven passing fail-closed/redaction/path cases.
  Live scheduler shutdown now awaits cancelled-task database cleanup; the
  focused recovery/budget/coordinator group passes 17 tests with unhandled
  thread exceptions treated as errors. OAuth schema test was made
  order-independent in `backend/tests/test_challonge_oauth.py` (9 passing).
  PostgreSQL by starting a normal transaction; no global compatibility lock is
  used. Repository-specific Workspace/row locks remain responsible for
  bootstrap, approvals, reservations, claims and ledger operations, avoiding
  serialization of unrelated organizations. Full local regression after the
  identity-link, overlay-isolation, retention, worker-scope and WebSocket
  authorization fixes: 447 passed, 27 skipped (2026-09-10; the skips are
  explicitly documented test-environment/live-dependency cases). The two bot SQLite
  reads were replaced with
  repository calls and are guarded by `test_runtime_bot_paths_do_not_open_sqlite_directly`.
  The subsequent launcher dotenv-isolation correction was verified by the
  complete local suite at 450 passed / 27 skipped (2026-09-10), including the
  idempotent owner-scoped Start.gg legacy-credential migration regression.
  Player listing and platform-admin checks now use repository functions and are
  guarded by `test_workspace_api_paths_use_repository_boundary`.
  Latest disposable PostgreSQL acceptance (storage, migration and station-overlay
  isolation) is 32/32 passing on 2026-09-09; the current official local backend result is 445
  passed / 21 intentionally skipped. Current focused sync/authorization runs
  also pass (40 tests), including tenant-qualified scheduler keys and revocable
  Hub/Overlay WebSocket access.
  ProviderSyncManager now carries the trusted tournament workspace through
  startup, periodic, stale-open and post-score worker paths; unowned fixtures
  retain the legacy one-argument test hook only. Its in-process refresh lock is
  keyed by `(workspace_id, tournament_slug)` so unrelated tenants do not share
  a serialization bucket. Deferred/stale-open refreshes and Live scheduler
  tasks now use the same tenant-qualified key; `test_sync_budget_acceptance.py`
  covers identical slugs in two workspaces. Provider usage telemetry records the
  account/workspace and uses PostgreSQL-safe month boundaries.
  Recovery timer reads, sync-status writes, and attendance review Outbox events
  now carry the durable match workspace; a wrong-tenant worker context is
  rejected without modifying the match. Tournament Hub reset also requires the
  authenticated workspace, and station-overlay helpers resolve tenant-qualified
  storage IDs before reads or writes.
  Non-blocking compatibility inventory (runtime paths are already on the
  PostgreSQL boundary; these entries are retained only for staged migration or
  explicitly global administration):
  `backend/api/routers/settings.py` (`api_get_settings`, `api_patch_settings`,
  `api_get_env`, `api_patch_env`, `api_trigger_token_check`) now has a narrow
  `require_global_settings_admin` gate: only the platform administrator may
  access service-global settings/connections, preventing an unrelated workspace
  Owner from reading them. Integration account data remains workspace-scoped;
  removing this owner-only compatibility surface is tracked under T022 and is
  not a storage cutover blocker.
  `backend/api/routers/hub.py` feed read/clear and manual queue writes carry the
  authenticated workspace (with `bot_feed.workspace_id` added to fresh schema
  and legacy backfill), covered by `test_bot_feed_workspace_scope.py`. Global
  status, workflow reload and Dispatcher master operations are now restricted to
  the platform administrator; remaining status/worker scope acceptance is in
  `test_event_scoping.py`, `test_dispatch_event_scoping.py`, and a worker
  workspace-claim test.
  `backend/api/routers/tournaments.py` list/import paths remain in the staged
  owner bridge; delete now passes the authenticated workspace through every
  dependent cleanup query and rejects a foreign tournament. Acceptance:
  `test_tournament_removal.py` with two memberships remains required.
  `backend/api/routers/planned_streams.py` now passes workspace ownership to
  stream repositories; station/stream collision acceptance remains in
  `test_station_stream_coupling.py`.
  `backend/bot/main.py` CFN lookup now enumerates only the durable owner
  workspace when the Discord identity is already owned; `registration.py` also
  scopes CFN propagation. `test_worker_workspace_scope.py` proves enumeration
  and CFN writes cannot update the other workspace. Remaining bot task contexts
  without a durable owner (initial registration and service heartbeats) remain
  explicitly platform/global until the worker identity migration is complete.
  `backend/core/database.py` legacy repository functions around stations,
  active_matches, settings and connections remain compatibility callers;
  acceptance is a repository import scan plus PostgreSQL concurrency tests,
  not merely a successful SQL connection.
  Additional regressions now scope HTTP active-match mutations, Discord
  Ready/timeout transitions, action-proposal execution, and Dispatcher
  rechecks with the trusted workspace. Audit redaction covers credential
  aliases and embedded bearer/query secrets without hiding safe identifiers.
  The Discord bot command drain, workflow status/validation, conflict scan,
  agent match listing, Ready-view recovery, and post-score verification now
  use the durable integration workspace; a worker cannot lease another
  workspace's Hub commands. Legacy unowned migration/test callers remain
  explicitly documented rather than being treated as tenant runtime paths.
  The retained read-only `get_players_tool` compatibility entrypoint now also
  passes `ACTIVE_DISCORD_WORKSPACE_ID` into the repository, so it cannot
  enumerate every workspace's players; `test_legacy_player_read_tool_is_bound_to_active_workspace`
  proves the scoped call contract.
  Start.gg permission probing is opt-in (`STARTGG_TOKEN_PROBE_ON_STARTUP=true`);
  API startup no longer issues a provider request merely because a credential
  exists. The default startup path is covered by
  `test_api_shutdown_drains_started_tasks_and_does_not_import_secrets`.
  Tournament refresh/stream lookup and bracket snapshot/status paths now pass
  the authenticated workspace through provider resolution and local snapshot
  storage; `test_provider_snapshot_workspace_scope.py` proves a foreign
  workspace cannot read or write the same snapshot. Direct legacy callers
  retain the unscoped signature only for migration/test fixtures.
  PostgreSQL worker/dispatcher acceptance on 2026-09-10 completed 21 passed / 1
  skipped across `test_auto_dispatcher_service.py`,
  `test_worker_workspace_scope.py`, and `test_provider_recovery.py` after
  correcting event grouping, Boolean predicates, nullable workspace casts, and
  PG-compatible row assertions. This closes the previously observed PG query
  failures; tenant-isolation acceptance and final cutover remain tracked under
  T022/T052/T053.
  Follow-up PostgreSQL runs also cover Challonge identity persistence and
  per-event Dispatcher scoping: 20/20 identity/event cases pass after casting
  nullable workspace predicates, preserving text match numbers in numeric-safe
  ordering, and using Boolean literals in the PG fixtures (2026-09-10).
  Additional PG runtime checks now pass 29/29 for Challonge local workflow,
  SQL-safety, and scoped tournament removal; their fixtures use the shared
  PostgreSQL adapter rather than opening SQLite directly.
- [x] **T005 / FR-009–011** PostgreSQL acceptance now proves concurrent
  provider-ledger idempotency/lease ownership as well as approval, Outbox and
  station and hub-command claims (`test_postgres_storage.py`: 19 passing PG
  cases). A concurrent PostgreSQL rate-window test also proves one accepted
  request and seven rejected requests at limit one. Runtime worker acceptance
  and restart/retry coverage are now complete. Latest isolated runs: 19/19 PG storage
  cases and 17/17 PG workspace/session cases passed (2026-09-09), including
  competing approval, reservation, Outbox, ledger and bootstrap paths.
  The post-recovery workspace-scope and provider-recovery run passes 28/28 on
  disposable PostgreSQL; an untyped nullable workspace predicate found there
  was corrected to an explicit scoped clause without changing SQLite behavior.
  The follow-up worker/dispatcher run is 21/21 passing with one intentional
  skip on 2026-09-10, including restart-safe claims and kill-switch/tournament
  rechecks. Two-organization runtime cutover evidence remains tracked by
  T022/T052/T053 and is not a prerequisite to this repository-level closure.
  Proposal/console/entitlement/session role acceptance contributes a further
  43/43 passing PostgreSQL cases (2026-09-10); live external receipt
  reconciliation and cutover remain outside this isolated proof.
  V2 provider command/outbox lease repositories add 4/4 passing PostgreSQL
  cases; the pre-V2 SQLite migration fixture remains intentionally scoped to
  SQLite because it exercises source-file upgrade semantics.
  A broad `--postgres` sweep exposed 36 legacy fixture/harness incompatibilities
  during the first run; these were not suppressed. After the targeted fixes and
  explicit SQLite-source marker, the complete PostgreSQL-targeted regression
  passes 469/469 with five intentional skips (three source-migration cases,
  the disabled AI Referee benchmark, and one live-network test). The remaining
  T004 work is limited to documented compatibility contexts, not runtime
  SQLite fallback or unscoped transactions.
  Error telemetry redaction and Challonge repair acceptance add 4/4 passing PG
  cases; no external effects are used by these tests.
  Discord thread delivery/restart-view acceptance adds 3/3 passing PG cases
  after seeding its disposable tournament through the repository boundary.
- [x] **T006 / FR-011** `WorkflowOutboxWorker` now marks an explicitly
  ambiguous external outcome `needs_review` and does not retry it; PG acceptance
  also proves cancellation after delivery and before completion persistence
  does not redeliver after lease expiry. `effect_started_at` is durable before
  invoking the sink; only explicit `ExternalEffectNotSent` permits a retry.
  A local deduplication set is no longer misrepresented as Discord receipt
  evidence. The atomic Hub transition now writes state + audit + outbox only
  on the first deduplicated event; unknown external outcomes remain
  `needs_review` and are never blindly resent. Acceptance is complete for the
  local worker contract: sent/failed/unknown outcomes, crash after external
  delivery, lease expiry, explicit queue holds, concurrent claims and restart
  all have PostgreSQL tests. Live receipt reconciliation is intentionally a
  separate operational gate under T043/T052/T053; it is not required to prove
  the no-blind-retry contract, and the old isolated rows remain preserved and
  non-claimable.

  AI safety clarification: `call_match_tool`, `post_announcement_tool`, and
  `reopen_match_tool` were legacy agent entrypoints not covered by the proposal
  workflow. They now return explicit non-mutating responses, covered by
  `test_ai_assistant_safety.py`; the organizer action-proposal announcement
  path remains available. This closes extra execution paths rather than
  removing authorized manual controls.

  Attendance timeouts are warning-only platform-wide: `start_call_timer` never
  invokes `auto_dq_match`; single-player DQ remains an explicit organizer
  action. `test_call_timer_only_warns_and_never_auto_dq` proves the timeout
  cannot create a provider mutation or winner.

## B. Identity, registration and roles

- [~] **T010 / FR-003–005** One-time Owner bootstrap and session base are in
  place. Registration is implemented behind the explicit
  `ALLOW_PUBLIC_REGISTRATION` setting (default closed), and tests prove the
  closed gate. The HTTP registration path is separately rate-limited by
  client origin only after the gate is explicitly opened; the regression
  proves closed=403, one opened registration=201, then 429 at the configured
  bound. Keep the implemented path closed until T022/T053 isolation
  acceptance; add the protected Owner setup/account UI before closure.
  Disposable PostgreSQL HTTP acceptance now proves the bootstrapped Owner
  profile, session-derived workspace (client workspace spoof ignored), logout,
  and durable revocation in `test_postgres_identity_acceptance.py` (3/3 PG
  cases, 2026-09-10). The one-time bootstrap remains environment-gated and no
  default credential is created.
- [~] **T011 / FR-003–005** Email verification, password change/reset, TOTP
  recovery codes, session revocation and auth rate limits are implemented and
  covered by session tests; account UI is present. Email delivery remains
  deployment-dependent and public registration stays closed. The same isolated
  PG HTTP acceptance covers TOTP enable, missing-code rejection, one-use
  recovery login, post-reset session revocation and password replacement; the
  reset token is supplied by an in-process test delivery sink, not SMTP. Live
  SMTP/provider delivery remains an explicit deployment dependency.
- [x] **T012 / FR-003** Canonical Owner / TO / Stream operator / Moderator /
  Viewer permission matrix is now present in `workspace_auth.py`, with legacy
  aliases retained only for staged data migration; session and WebSocket
  authorization tests pass. Exhaustive forbidden-action acceptance remains
  required. The
  Discord `/verify` path no longer matches identities by name similarity: it
  requires an explicit profile URL or organizer-confirmed entrant link, and
  the regression is covered by `test_discord_verify_does_not_target_identities_by_name_similarity`.
  The role matrix now has an explicit forbidden-action parameterized regression
  for TO, Stream operator, Moderator and Viewer
  (`test_every_non_owner_role_denies_mutating_actions`). The HTTP
  positive/negative regression (`test_roles_are_positive_and_negative_over_http`)
  now covers TO Call, Stream operator stream management with result denial,
  Moderator Call with result/DQ denial, and Viewer read access with mutation
  denial. This closes the role-matrix task; broader live multi-membership
  acceptance remains part of T053 rather than an untested claim here.
- [~] **T013 / FR-003–005** Owner-only invite creation, token acceptance, role
  change and membership disable are implemented with last-Owner protection;
  tests cover invitation replay and role/removal safety. Account Settings now
  exposes owner-only role changes and member disable actions, while the API
  remains the enforcement point. Owner-visible invitation listing and
  cancellation are now covered without exposing invitation hashes/tokens. The
  isolated PG HTTP acceptance additionally proves invite acceptance, replay
  rejection, Owner role change, non-Owner role-change denial, cancellation
  invalidation, and last-Owner deletion protection. Email delivery remains a
  deployment dependency; acceptance uses the returned one-time test token and
  does not claim that SMTP sent it.

## C. Ownership and tenant isolation

- [~] **T020 / FR-001–003, FR-006** Preparatory nullable `workspace_id`
  migrations now cover core operational tables. The current legacy Hub rows
  were backfilled to the designated BASHMIX Owner workspace only after a
  successful copy rehearsal and integrity check; service/query scoping remains
  incomplete and is deliberately not enforced until Owner backfill validates
  the data: tournaments, matches,
  players/identities/assets, stations/overlays, integrations/destinations,
  commands/ledger/outbox, caches/budgets, proposals, Dispatcher and audit.
  PostgreSQL acceptance now exercises colliding workspace/station/tournament
  scopes, worker claims, snapshots and WebSocket subscriptions; the latest
  workspace/worker/WS run passes 54 cases. Focused PostgreSQL ownership
  acceptance adds 3 cases for unowned-player/link exclusion, foreign workflow
  mutation rejection, and the two-workspace claim boundary (26 focused cases
  including existing V2 repository coverage). Final non-null ownership enforcement
  for every legacy row remains gated by the controlled cutover backfill.
- [~] **T021 / FR-001, FR-009–010** The current operational SQLite file was
  inspected read-only on 2026-09-09. It contains exactly one active Owner
  workspace (`bashmix-tournament-hub`), one Owner membership, and zero NULL
  `workspace_id` values across tournaments, active matches, players, stations,
  overlays and integration accounts. The corresponding consistent backup is
  `.migration-backups/database-post-owner-workspace-20260908.sqlite`; the
  rehearsal copy is `.migration-backups/workspace-backfill-rehearsal-20260908.sqlite`.
  These artifacts and the database state are evidence that the Owner bootstrap
  and backfill had already been applied before this pass; no write or repeat
  migration was performed here. `backfill_legacy_workspace.py` remains
  idempotent and requires an explicit active Owner before `--apply`.
  PostgreSQL `NOT NULL`/unique constraints and two-tenant acceptance remain.
- [~] **T022 / FR-001–003, FR-006** HTTP match/tournament/station/provider and
  WebSocket hub/overlay paths now derive workspace from trusted session or
  revocable overlay token; worker claims carry durable workspace IDs and
  re-check ownership before effects. Two-workspace station/command/overlay
  collision tests pass. Player reads/creation, entrant links, player overrides
  and conflict resolution derive workspace from the authenticated session.
  Settings and global Hub controls now use a platform-admin-only gate rather
  than exposing global records to an arbitrary workspace Owner; Hub feed and
  manual queue paths carry the session workspace. Legacy unowned rows are not
  exposed to a tenant session. MatchCommandService and Discord Ready/Outbox
  handling now carry the durable match workspace into provider, tournament,
  station and command lookups. The tenant player projection no longer admits
  `workspace_id IS NULL` rows, entrant-link reads require an owned tournament,
  and V2 Hub workflow updates accept an explicit workspace predicate so a known
  set ID cannot mutate another tenant. Background provider-command and Outbox
  claims now apply the worker's durable workspace to row locking, updates and
  returned projections. Remaining work is to remove the compatibility
  bridge after repository parity and finish unowned bot service-heartbeat /
  initial-registration contexts.
  The legacy assistant player projection is no longer an unscoped tenant read:
  `get_players_tool` is bound to the active Discord integration workspace and
  its regression passes in `backend/tests/test_ai_assistant_safety.py`.
  The latest PostgreSQL run also passes authenticated Hub/Overlay WebSocket
  cross-workspace denial and the HTTP role matrix; no tenant request can select
  a foreign workspace. Remaining work is removal of staged owner-only
  compatibility and the final unowned service identity, tracked for cutover.
- [~] **T023 / FR-006** Integration account/destination lookup and credential
  rotation now require an explicit workspace in API paths; the legacy `admin`
  integration ownership marker was normalized during Owner backfill. Unit tests
  prove cross-workspace lookup/rotation rejection. Dispatcher claims now carry
  a durable workspace ID and scoped claim/queue/release checks; bot CFN
  enumeration and propagation are scoped to the trusted owner workspace.
  Provider budgets/caches and remaining global bot service contexts still need
  explicit tenant ownership before the temporary compatibility enumeration is
  removed. In-process budget/backoff state is account-keyed; durable budget/cache
  schema ownership and the legacy bot service contexts remain open for the
  repository parity pass.
  Tournament snapshot/status and refresh/stream lookup now carry the trusted
  workspace; the new regression proves cross-workspace snapshot reads/writes
  are denied. Account isolation, rotation, provider snapshot scoping and worker
  claim acceptance pass on PostgreSQL. Destination creation now inherits the
  owning account workspace, and destination reads verify the account owner as
  well as the requested workspace. The remaining gap is migration of the
  final service identity and durable ownership constraints.

## D. Integrations, assets and overlays

- [~] **T030 / FR-012** Existing encrypted credential blobs are preserved with
  service-key fail-closed/rotation tests and safe projections. Integration UI now
  permits account-scoped Start.gg identities alongside Discord/Challonge; the
  legacy shared Start.gg editor remains visible only as a migration bridge and
  is not used by account-bound clients unless the explicit fallback flag is on.
  With both V2 contract/coordinator flags enabled, tenant-owned Start.gg import
  now rejects a missing `provider_account_id` before provider resolution;
  `test_v2_tenant_import_requires_explicit_startgg_account` covers this gate.
  The latest PostgreSQL integration/assets/overlay/entitlement/retention/error
  regression is 36/36 passing; these tests use isolated accounts and workspaces
  and do not enable external effects. Remaining status reflects legacy preset
  backfill and deployment-level Cloudinary/receipt acceptance, not a failing
  PostgreSQL repository path. On 2026-09-10 the legacy Start.gg credential
  found in the owner-scoped candidate settings was migrated through
  `migrate_legacy_integrations` into an encrypted owner Workspace account,
  idempotently, and `tournament/testfnc` was bound to it; the live candidate
  API then reported three account-scoped integrations and both tournaments
  `provider_sync_status=ready`.
- [~] **T031 / FR-007** New Discord registration and participant avatar uploads
  use `image_store` with MIME/decodability, byte/dimension bounds and safe PNG
  transforms. Managed deployments now fail closed without Cloudinary, while
  local disk is explicit development mode. Generic overlay asset ownership and
  CDN-variant policy remain for T032.
- [~] **T032 / FR-007** Added workspace-owned `media_assets` records for new
  participant and overlay uploads, workspace-filtered listing, and soft deletion that
  refuses referenced player/match assets. Existing image URLs remain untouched;
  generic overlay asset ownership and a full old-URL acceptance pass remain.
  Schema/migration coverage is included in the disposable PostgreSQL migration
  test (1 passing) and image/API regression tests (18 passing). Before deletion,
  inspect station overlay configuration, overlay JSON image/background URLs,
  player overrides, players and active-match projections; referenced assets are
  rejected rather than removed. Overlay writes reject cross-workspace
  overwrite under the legacy global-name constraint. An explicit, idempotent
  ownership-key migration now rebuilds SQLite legacy tables and upgrades
  PostgreSQL constraints to workspace/name and workspace/tournament/entrant
  uniqueness; existing installations must apply its migration receipt before
  relying on cross-workspace duplicate keys. The deletion guard now recursively
  checks every owning-workspace overlay JSON value (including nested image
  `src` and `background_url`) and rejects a referenced asset; SQLite focused
  and disposable-PostgreSQL regressions pass. Legacy unowned preset backfill
  remains a cutover concern. `test_assets_workspace_scope.py` now proves the
  HTTP listing never enumerates shared legacy files: 1 local and 1 PostgreSQL
  case pass after explicitly isolating this SQLite fixture from the PG harness.
  The live candidate smoke also exposed and fixed two projection/configuration
  edges: PostgreSQL timestamps are normalized before the active-match response
  (`test_tournament_progression_and_state_axes.py`, 9/9), and an unbound
  Start.gg integration now returns explicit HTTP 409 setup state rather than a
  500 or global-credential fallback (`test_verify_stream.py`, 7/7).
- [~] **T033 / FR-008** Revocable hashed workspace-station Browser Source tokens
  and least-privilege `/obs/{station}/data` plus authenticated overlay WebSocket
  are implemented; issuance/revocation and cross-workspace tests pass. Existing
  legacy overlay presets still need an explicit ownership backfill before this
  task can close.

## E. Security, plans and operations

- [~] **T040 / FR-012–013** Redacted exception responses, environment-driven
  CORS, health/readiness checks, session cookie controls, auth rate limits and
  a structured redacted `record_audit_event` repository are present. CSRF
  enforcement now rejects cross-origin cookie mutations (5 API-security tests
  pass); asset uploads have a workspace-scoped 60/hour limit and 10 MiB cap.
  General API/AI distributed limits and end-to-end audit coverage remain before
  closure. The remaining acceptance is split into: (a) CSRF and
  origin validation for cookie mutations, (b) multi-process limits for auth,
  uploads, API and AI, (c) secret/content redaction assertions, and (d)
  readiness/error-tracking checks that expose no credentials or local paths.
  `error_events` now provides bounded, redacted server telemetry: the global
  exception handler records only method/path/exception class/trace id and
  returns the same trace id with the generic response; telemetry failure cannot
  replace the original error (`test_error_tracking.py`, 2 passing). The table
  and index are additive/idempotent and no request body, provider response,
  token, or local filesystem path is persisted. Distributed API/AI limits,
  full readiness deployment probes, and end-to-end audit acceptance remain.
- [~] **T041 / FR-014–015** Workspace free/non-billed entitlements and limits
  are persisted and projected safely from the session profile; free-plan
  limits are enforced per workspace for tournaments, stations, integrations,
  invitations, provider usage, and AI usage. No payment gateway is configured,
  so paid checkout is not active. Retention acceptance remains.
- [ ] **T042 / FR-014** If and only if a named payment gateway + merchant
  sandbox are configured, implement signed idempotent checkout/webhooks and
  sandbox acceptance. Otherwise record the external dependency as blocking
  *only paid checkout/webhooks*, never free/non-billed runtime or cutover.
- [~] **T043 / FR-016** Explicit PostgreSQL backup/restore scripts and redacted
  manifests are available, with SQLite fixture mode isolated to migration
  tooling. `backend/core/retention.py` now provides bounded, atomic
  housekeeping for aged authentication artifacts (expired/used reset and
  verification tokens, invitations, MFA setup, sessions and limiter buckets);
  `test_retention.py` proves fresh rows and workspace data are preserved.
  Workspace lifecycle now exposes safe disable-readiness and refuses disable
  while pending Outbox, provider-ledger, Hub-command, or active workflow work
  exists; orphaned-effect and asset-retention regressions pass. Encryption-key
  recovery and external
  Discord/provider reconciliation acceptance remain. The acceptance must
  separately prove backup integrity, restore to a new target, key recovery,
  retention behavior, safe Workspace disable/deletion, and reconciliation of
  external Discord/provider effects. A PostgreSQL `pg_dump` backup was created
  on 2026-09-09 and restored into a newly created disposable database;
  `pg_restore` returned success and the application initialized against that
  target with external probes disabled. Backup restore now verifies the
  reviewed sidecar manifest (filename, byte size and SHA-256) before opening
  either a SQLite or PostgreSQL target; a missing or changed artifact is
  rejected before any restore write. PostgreSQL restore is non-destructive by
  default; `--clean --if-exists` is only emitted with explicit `--force`, and
  focused tests prove both command shapes. The source PostgreSQL database itself
  currently contains only two stations and no workspaces, tournaments or
  integration credentials, so it is not the populated runtime cutover source.
  A separate populated SQLite-to-PostgreSQL rehearsal decrypted all five
  encrypted credential rows using their recorded `owner_kind` (including the
  OAuth application secret), with zero failures. The populated PostgreSQL
  rehearsal was then backed up and restored to a second disposable target;
  reopening it with the existing service-level integration key authenticated
  all five ciphertext rows without emitting the key. Both disposable targets
  were dropped after verification; no production rows changed.
  A direct preflight against the configured runtime PostgreSQL target found
  existing schema history, two stations, and one `workflow_outbox` record in
  `needs_review`; `--allow-schema-only-target` correctly refused the merge
  because the target was not empty. The pending external-effect record remains
  intact for the T052 pause/reconciliation procedure.
  A separate `aitob_cutover_candidate_20260909` PostgreSQL database was then
  created and populated from the latest read-only SQLite copy; content and
  ownership validation passed, all five encrypted credentials authenticated,
  and a verified candidate backup was created. Services still point to the
  original database until the pending effect and cutover pause are resolved.
  Docker Compose now requires the two existing service-level encryption keys
  for API and bot containers; isolated API/bot import checks confirmed both
  values load without exposing them. The containers remain stopped for the
  candidate until provider-contact and pending-effect gates are cleared.
  The candidate Discord credential decrypts correctly. The newly supplied
  replacement was rotated into the account-scoped encrypted row and audited;
  Discord `/users/@me` returned HTTP 200 and a connectivity-only bot process
  reached the Gateway. Workers remained paused and no Discord effect was sent;
  resumption still follows the reviewed cutover sequence.
  API startup now supports the explicit `AITOB_DISABLE_BACKGROUND_WORKERS`
  pause switch for cutover review; a regression proves recovery, Live schedule,
  sync and reconciliation workers are not started while the switch is active.
  The populated cutover candidate was inspected before any worker resume: it has
  eight pending `workflow_outbox` events and nine pending manual Hub commands,
  all owned by the migrated workspace. Its sole provider ledger row is already
  `snapshot_verified` (score), so no provider mutation is eligible for replay.
  These rows are a cutover reconciliation gate; they were not executed,
  rewritten, or deleted.
  An explicit cutover hold was then applied to exactly the reviewed eight Outbox
  event IDs and Hub command IDs 126–134. The single transaction moved only rows
  that were still `pending`, retained their previous status/attempt/lease/effect
  markers in 17 `queue.hold` audit events, and left all matches and the verified
  provider ledger unchanged. A fresh claim after restart returned zero Hub and
  zero Outbox rows; no external effect ran. Local and PostgreSQL hold regressions
  both pass.
  Detailed candidate queue classification (2026-09-09): the eight pending
  Outbox rows are two workflow groups, not eight independent provider actions.
  Four target `challonge:fnc-jo:18449397:471045156` (station-assigned,
  match-complete, Discord-complete and next-match discovery) while four target
  `challonge:fnc-jo:18449397:471045157` (Discord call, OBS-started and two
  station-assigned events). Every row has attempts=0, no lease, no
  `effect_started_at`, no `completed_at` and no receipt. The first match is
  already terminal and the second is already `in_progress`; neither has saved
  Discord identities/thread or a valid current call target. They are therefore
  stale local effects requiring reconciliation, not safe automatic retries.
  Nine pending manual Hub commands were linked by target: 126/129 duplicate
  Calls for 471045156 (terminal), 127 Call for 471045157 (already in progress),
  128 Call for 471045159 (no Discord identity mapping), 130 Call and 131 Score
  for missing set 103903193, 132 Call for missing set 103903199, and untargeted
  legacy commands 133/134. None has a lease, receipt or prior attempt. They are
  all held for review because current state/ownership cannot prove a safe
  replay; no row was converted or deleted.
  The combined regression was then rerun with `AITOB_PG_TEST_URL` pointing at
  the local PostgreSQL admin DSN (tests create/drop isolated databases) while
  ordinary tests retained their explicit temporary SQLite paths in the
  historical mixed run: 455 passed, 1 skipped (2026-09-09). The current
  focused PostgreSQL storage/migration/queue-hold acceptance is 22 passed
  after the uvicorn entrypoint fix. The earlier hang was reproduced as an inherited
  `AITOB_DISABLE_BACKGROUND_WORKERS` pause and fixed by making the lifecycle
  test remove that process setting; three PostgreSQL bootstrap failures were
  likewise traced to test fixtures mutating `os.environ` directly and fixed with
  pytest-managed environment restoration. No runtime data was changed.
  The one skip is the disabled legacy AI Referee accuracy benchmark
  (`test_referee_accuracy_benchmark`), intentionally closed until Result Claims;
  it is not evidence of provider or workspace readiness.

## F. Migration, cutover and acceptance

- [~] **T050 / FR-009–010** SQLite-to-PG rehearsal reads source `mode=ro`,
  rejects nonempty target and validates redacted logical content digests,
  null counts, timestamps, encrypted blobs, source foreign keys and PostgreSQL
  sequences (without printing values). `test_postgres_migration.py` proves a
  disposable PostgreSQL import preserves Owner scope, legacy image references,
  and textual `match_number`; an isolated live rehearsal passed and its target
  was deleted. A second current-copy rehearsal on 2026-09-09 copied 50 tables
  and validated the read-only source/restore path. Remains open for the final
  source-column ownership constraints and cutover; the rehearsal is not full
  production migration acceptance. Latest disposable PostgreSQL migration
  acceptance: 1 passed (2026-09-08) plus the current-copy rehearsal. A fresh
  populated rehearsal on 2026-09-09 migrated the current operational copy into
  a new PostgreSQL database using the project virtualenv, validated 50 tables,
  preserved 1 Owner workspace/2 tournaments/19 active matches/9 overlays/2
  stations/2 players/2 integration accounts, and found zero NULL ownership in
  tournaments, active matches or players; the temporary target was then dropped.
- [~] **T051 / FR-009–010** Rehearsed a faithful copy of the current SQLite
  operational file on 2026-09-09: consistent backup and SQLite restore passed,
  then the read-only source migrated to a disposable PostgreSQL target (50
  tables, row/content validation) and the target was removed after verification.
  This is not the final cutover and does not replace the final ownership
  backfill/production pause procedure.
- [~] **T051a / FR-016** Backup/restore procedure was exercised on the rehearsal
  copy and external effects remain explicitly separate from database restore.
  Restore now requires an exact, locally verified backup manifest, with
  regression coverage for tampered bytes, renamed artifacts, and size
  mismatches; this protects the reviewed backup without claiming external
  effect rollback. No-loss rollback against newer writes and the final
  cutover pause window are
  still required before T052; an older database is never restored over newer
  writes.
- [ ] **T052 / FR-016** Perform final controlled cutover only after required
  T004–T051a work is complete; an unconfigured payment gateway may leave T042
  pending without blocking the free/non-billed cutover. Pause writes/workers,
  create verified backup, inspect pending commands/outbox,
  migrate latest data, start API/bot/workers on PostgreSQL, and verify recovery.
  A bounded candidate-only recheck (2026-09-09) verified the reviewed backup
  manifest and confirmed from two independent PostgreSQL process contexts that
  the explicit queue hold leaves zero claimable Outbox or Hub commands. The
  held rows still require reconciliation before this task can be closed. On
  2026-09-10 the
  duplicate API/Bot processes were identified by project working directory and
  command line, stopped, and replaced with one API process and one Bot process
  using the candidate database; Vite stayed on 5173 and proxied to API 8000.
  Fresh-process health/readiness, Owner login and tournament listing passed;
  Discord Gateway and local Hub WebSocket connected, while all eight held
  Outbox rows and nine held Hub commands remained unclaimable. This is a
  controlled candidate run, not final cutover; the old `aitob` database remains
  preserved and no SQLite re-import was performed. The managed runtime now
  points explicitly at the candidate database; this is runtime-source
  reconciliation, not completion of final cutover acceptance.
- [ ] **T053 / SC-001–006, FR-017** Run final acceptance only after T004–T051a;
  the required matrix is:

  | SC | Scenario and data | Steps | Expected result | Evidence |
  |---|---|---|---|---|
  | SC-001 | Two Workspaces with colliding tournament/station/provider IDs | Exercise HTTP, WebSocket, public overlay, worker and cache access from both memberships | Cross-workspace requests are denied or return only the caller's data | Redacted request matrix, DB ownership assertions, WS close/deny records |
  | SC-002 | Faithful operational copy containing relationships, encrypted blobs, image URLs and overlays | Backup, migrate to disposable PostgreSQL, compare content/relations/nulls/timestamps/sequences, restore | Validated content and existing asset URLs are preserved | Migration digest, FK/unique checks, restore report |
  | SC-003 | Concurrent duplicate approval, Call, station reservation, command, Outbox and provider mutation | Run independent connections and restart during each lease/effect window | At most one durable command/effect; unknown external outcome becomes review | Ledger/Outbox rows and adapter verification traces |
  | SC-004 | Prepared test Owner and member with MFA | Sign in, complete MFA, load workspace dashboard | Access completes within two minutes with trusted session context | Auth timing and session audit record |
  | SC-005 | Revoked session, membership, overlay token and consumed recovery code | Reuse each immediately through HTTP/WS/public link | Every revoked/consumed credential is rejected | HTTP status/WS denial and token state evidence |
  | SC-006 | Workspace with no payment gateway | Open plan/settings screens and attempt checkout | UI identifies free/non-billed state and exposes no live checkout | Screenshot/API projection and absence-of-route test |
  | FR-017 | Authorized TO, Operator/Viewer, AI Assistant and both DQ modes | Submit manual single-player DQ; attempt AI approval, AI DQ, Auto-DQ and double-DQ | Manual DQ follows approved provider policy; AI/Auto-DQ and Challonge double-DQ are unavailable | Role matrix, provider call trace, capability projection |

  No row is accepted when its required external/live test is skipped. The local
  DQ safety behavior has a dedicated regression, but T053 remains open until
  every row has evidence; it is not closed by local unit
  tests alone. The PostgreSQL candidate acceptance subset was re-run with
  external effects mocked: storage/queue-hold/recovery/overlay/asset/workspace
  checks passed (35 PostgreSQL tests and 40 local tests). This proves the
  database and isolation safeguards but does not close live provider/Discord/
  OBS evidence or authorize cutover.
