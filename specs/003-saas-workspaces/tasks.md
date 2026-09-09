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
- [~] **T004 / FR-009–011** Runtime imports now route through
  `backend/core/storage.py`; API, bot and launcher fail closed without
  `DATABASE_URL`, and PostgreSQL repository acceptance is passing. Continue
  converting SQLite-specific SQL/transaction semantics per repository and
  remove the compatibility bridge only after API/bot/worker parity. Evidence:
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
  identity-link, overlay-isolation, retention and worker-scope fixes: 384 passed,
  20 skipped (2026-09-09). The two bot SQLite reads were replaced with
  repository calls and are guarded by `test_runtime_bot_paths_do_not_open_sqlite_directly`.
  Player listing and platform-admin checks now use repository functions and are
  guarded by `test_workspace_api_paths_use_repository_boundary`.
  Latest disposable PostgreSQL acceptance (storage plus migration) is 19/19
  passing on 2026-09-09; the official local backend baseline is 384 passed
  / 20 intentionally skipped.
  ProviderSyncManager now carries the trusted tournament workspace through
  startup, periodic, stale-open and post-score worker paths; unowned fixtures
  retain the legacy one-argument test hook only. Its in-process refresh lock is
  keyed by `(workspace_id, tournament_slug)` so unrelated tenants do not share
  a serialization bucket.
  Remaining runtime inventory to close before cutover (each must use the
  PostgreSQL repository boundary and a trusted workspace context):
  `backend/api/routers/settings.py` (`api_get_settings`, `api_patch_settings`,
  `api_get_env`, `api_patch_env`, `api_trigger_token_check`) now has a narrow
  `require_global_settings_admin` gate: only the platform administrator may
  access service-global settings/connections, preventing an unrelated workspace
  Owner from reading them. Integration account data remains workspace-scoped;
  final removal of the legacy global storage bridge is still pending.
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
- [~] **T005 / FR-009–011** PostgreSQL acceptance now proves concurrent
  provider-ledger idempotency/lease ownership as well as approval, Outbox and
  station and hub-command claims (`test_postgres_storage.py`: 18 passing PG
  cases). Full runtime worker acceptance and restart/retry coverage remain
  required before this task can close. Latest isolated runs: 18/18 PG storage
  cases and 17/17 PG workspace/session cases passed (2026-09-09), including
  competing approval, reservation, Outbox, ledger and bootstrap paths.
- [~] **T006 / FR-011** `WorkflowOutboxWorker` now marks an explicitly
  ambiguous external outcome `needs_review` and does not retry it; PG acceptance
  also proves cancellation after delivery and before completion persistence
  does not redeliver after lease expiry. `effect_started_at` is durable before
  invoking the sink; only explicit `ExternalEffectNotSent` permits a retry.
  A local deduplication set is no longer misrepresented as Discord receipt
  evidence. The atomic Hub transition now writes state + audit + outbox only
  on the first deduplicated event; unknown external outcomes remain
  `needs_review` and are never blindly resent. Real Discord/provider receipt
  reconciliation and restart acceptance remain before closure.

  AI safety clarification: `call_match_tool`, `post_announcement_tool`, and
  `reopen_match_tool` were legacy agent entrypoints not covered by the proposal
  workflow. They now return explicit non-mutating responses, covered by
  `test_ai_assistant_safety.py`; the organizer action-proposal announcement
  path remains available. This closes extra execution paths rather than
  removing authorized manual controls.

## B. Identity, registration and roles

- [~] **T010 / FR-003–005** One-time Owner bootstrap and session base are in
  place. Registration is implemented behind the explicit
  `ALLOW_PUBLIC_REGISTRATION` setting (default closed), and tests prove the
  closed gate. Keep the implemented path closed until T022/T053 isolation
  acceptance; add the protected Owner setup/account UI before closure.
- [~] **T011 / FR-003–005** Email verification, password change/reset, TOTP
  recovery codes, session revocation and auth rate limits are implemented and
  covered by session tests; account UI is present. Email delivery remains
  deployment-dependent and public registration stays closed.
- [~] **T012 / FR-003** Canonical Owner / TO / Stream operator / Moderator /
  Viewer permission matrix is now present in `workspace_auth.py`, with legacy
  aliases retained only for staged data migration; session tests pass. Route,
  WebSocket and exhaustive forbidden-action acceptance remain required. The
  Discord `/verify` path no longer matches identities by name similarity: it
  requires an explicit profile URL or organizer-confirmed entrant link, and
  the regression is covered by `test_discord_verify_does_not_target_identities_by_name_similarity`.
- [~] **T013 / FR-003–005** Owner-only invite creation, token acceptance, role
  change and membership disable are implemented with last-Owner protection;
  tests cover invitation replay and role/removal safety. Cancellation, member
  management UI and mail delivery remain.

## C. Ownership and tenant isolation

- [~] **T020 / FR-001–003, FR-006** Preparatory nullable `workspace_id`
  migrations now cover core operational tables. The current legacy Hub rows
  were backfilled to the designated BASHMIX Owner workspace only after a
  successful copy rehearsal and integrity check; service/query scoping remains
  incomplete and is deliberately not enforced until Owner backfill validates
  the data: tournaments, matches,
  players/identities/assets, stations/overlays, integrations/destinations,
  commands/ledger/outbox, caches/budgets, proposals, Dispatcher and audit.
- [~] **T021 / FR-001, FR-009–010** A one-time local Owner bootstrap created
  the BASHMIX Owner workspace (no default account). `backfill_legacy_workspace.py`
  was rehearsed on a consistent copy and then applied atomically while API
  writes were stopped: all currently scoped operational rows have a valid
  workspace ID, and legacy integration `owner_id='admin'` was normalized.
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
  station and command lookups. Remaining work is to remove the compatibility
  bridge after repository parity and finish unowned bot service-heartbeat /
  initial-registration contexts.
- [~] **T023 / FR-006** Integration account/destination lookup and credential
  rotation now require an explicit workspace in API paths; the legacy `admin`
  integration ownership marker was normalized during Owner backfill. Unit tests
  prove cross-workspace lookup/rotation rejection. Dispatcher claims now carry
  a durable workspace ID and scoped claim/queue/release checks; bot CFN
  enumeration and propagation are scoped to the trusted owner workspace.
  Provider budgets/caches and remaining global bot service contexts still need
  explicit tenant ownership before the temporary compatibility enumeration is
  removed.

## D. Integrations, assets and overlays

- [~] **T030 / FR-012** Existing encrypted credential blobs are preserved with
  service-key fail-closed/rotation tests and safe projections. Integration UI now
  permits account-scoped Start.gg identities alongside Discord/Challonge; the
  legacy shared Start.gg editor remains visible only as a migration bridge and
  is not used by account-bound clients unless the explicit fallback flag is on.
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
  relying on cross-workspace duplicate keys.
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
- [~] **T041 / FR-014–015** Workspace free/non-billed entitlements and limits
  are persisted and projected safely from the session profile; no payment
  gateway is configured, so paid checkout is not active. Enforcement and
  retention acceptance remain.
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
  Workspace disable/deletion policy, encryption-key recovery and external
  Discord/provider reconciliation acceptance remain. The acceptance must
  separately prove backup integrity, restore to a new target, key recovery,
  retention behavior, safe Workspace disable/deletion, and reconciliation of
  external Discord/provider effects.

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
  acceptance: 1 passed (2026-09-08) plus the current-copy rehearsal.
- [~] **T051 / FR-009–010** Rehearsed a faithful copy of the current SQLite
  operational file on 2026-09-09: consistent backup and SQLite restore passed,
  then the read-only source migrated to a disposable PostgreSQL target (50
  tables, row/content validation) and the target was removed after verification.
  This is not the final cutover and does not replace the final ownership
  backfill/production pause procedure.
- [~] **T051a / FR-016** Backup/restore procedure was exercised on the rehearsal
  copy and external effects remain explicitly separate from database restore.
  No-loss rollback against newer writes and the final cutover pause window are
  still required before T052; an older database is never restored over newer
  writes.
- [ ] **T052 / FR-016** Perform final controlled cutover only after required
  T004–T051a work is complete; an unconfigured payment gateway may leave T042
  pending without blocking the free/non-billed cutover. Pause writes/workers,
  create verified backup, inspect pending commands/outbox,
  migrate latest data, start API/bot/workers on PostgreSQL, and verify recovery.
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

  No row is accepted when its required external/live test is skipped. T053
  remains open until every row has evidence; it is not closed by local unit
  tests alone.
