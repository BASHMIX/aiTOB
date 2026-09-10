# Workspace SaaS development and verification

## PostgreSQL development runtime

Start Docker Desktop, then run the PostgreSQL service defined by
`docker-compose.yml`. Put the local development `DATABASE_URL` and encryption
key only in ignored local environment files. Do not use SQLite at runtime.

```powershell
docker compose --env-file .env.production up -d postgres
$env:DATABASE_URL = 'postgresql://…'
.\.venv\Scripts\python.exe -c "import asyncio; from backend.core.database import init_db; asyncio.run(init_db())"
```

The command must fail clearly when the URL is absent or unreachable. Test-only
SQLite is configured by the root test fixture before importing backend modules.

## Test PostgreSQL explicitly

Use a disposable database, never the application database:

```powershell
$env:AITOB_PG_TEST_URL = 'postgresql://…/aitob_storage_test'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_postgres_storage.py -q --postgres
```

The supplied connection must be a local test administrator with CREATE DATABASE
permission. The storage suite creates a random `aitob_test_*` database per case
and deletes only that database; it never drops the supplied database's schema.
It covers binding, concurrent approvals, reservations, Outbox/Ledger claims,
rollback, bootstrap, invitations and crash-after-effect recovery.

## SQLite-to-PostgreSQL copy rehearsal

The migration tool opens its SQLite source with `mode=ro`; it never modifies
that source. It writes only to an empty disposable PostgreSQL target.

```powershell
.\.venv\Scripts\python.exe scripts/migrate_sqlite_to_postgres.py `
  --source path\to\operational-copy.sqlite --dsn `$env:DATABASE_URL
```

Before a real cutover, validate values, foreign relationships, unique keys,
nullable fields, timestamps, encrypted-secret readability, image/overlay
references, and PostgreSQL sequences—not merely row counts. A database backup
does not undo an already accepted provider result or Discord delivery; use the
provider ledger and outbox reconciliation for those external effects.

### Verified rehearsal evidence (local, redacted)

On 2026-09-08 a read-only SQLite copy was imported into an empty disposable
PostgreSQL database. The migration validated content digests (including opaque
encrypted blobs), null counts, timestamp normalization, foreign-key checks and
identity sequences. The disposable target was deleted after verification.

The corresponding API rehearsal started against that PostgreSQL target, logged
in the designated Owner, returned a PostgreSQL readiness signal, and confirmed
that public registration is closed. External startup calls were not instrumented
in that earlier rehearsal, so it is **not** evidence of zero external calls or
complete operational acceptance. The operational SQLite Hub was first backed
up and then assigned to the designated Owner workspace in one transaction. A
read-only audit on 2026-09-09 found one active Owner workspace and zero NULL
ownership values across the scoped operational tables. The source was not
written during that audit; the evidence files are the post-owner backup and
rehearsal copy under `.migration-backups/`.

## Cutover gate

Do not cut over the operating Hub until every runtime repository has been
converted, workspace ownership migration is proven on a fresh operational copy,
and API/bot/workers run against PostgreSQL with a protected one-time owner
bootstrap. Public registration remains closed.

## Storage and cleanup regression — 2026-09-08

The latest PostgreSQL targeted suite completed 19 passed on fresh isolated
databases (18 storage cases plus one migration case). An earlier broader
rehearsal reported 35 cases; that historical count is not used as the current
acceptance baseline. `BEGIN IMMEDIATE` is translated to a normal PostgreSQL
`BEGIN` only for syntax;
correctness is provided by explicit Workspace/row locks, `SKIP LOCKED` worker
claims, and unique command keys. No global compatibility lock serializes
unrelated Workspaces; bootstrap and other critical paths use scoped locks.
Two independent membership transactions cannot remove both last Owners.

The local complete suite completed without hanging (447 passed / 27 skipped),
but exposed a thread-cleanup warning. The focused recovery/budget/coordinator
group reproduced it with warnings treated as errors. Scheduler `close()` now
awaits stopped tasks, and the explicit test-only SQLite connector drains opening
and closing work on cancellation. The focused group then passed all 17 tests.
The full post-fix rerun completed at 447 passed / 27 skipped (2026-09-10),
including the Windows uvicorn selector-loop regression.

The PostgreSQL-enabled full regression uses the same `.venv` interpreter with
`AITOB_PG_TEST_URL` set to the local PostgreSQL admin DSN; each PostgreSQL test
creates and drops its own disposable database, while ordinary tests keep their
temporary SQLite fixture. The historical mixed run completed at 455 passed / 1
skipped (2026-09-09). The current focused PostgreSQL storage, migration and
queue-hold acceptance is 22 passed after the runtime entrypoint fix; ordinary
repository tests remain on temporary SQLite so legacy fixtures cannot target
the application database.
The single skip is `test_referee_accuracy_benchmark`, the intentionally disabled
legacy AI Referee inference benchmark pending Result Claims (it is not an
external-provider acceptance result). A previous
10-minute hang was caused by inheriting `AITOB_DISABLE_BACKGROUND_WORKERS` into
the lifecycle test; the test now clears that setting. Three PostgreSQL auth
failures were caused by fixtures writing bootstrap variables directly into the
process environment; those fixtures now use pytest-managed restoration.

The official local backend command is:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

The 21 skips are intentional and named: the PostgreSQL-only functions in
`backend/tests/test_postgres_storage.py` (19 PostgreSQL-only functions,
including the concurrent rate-window case),
`test_readonly_sqlite_migration_preserves_workspace_ownership_and_assets`
(`test_postgres_migration.py`, PostgreSQL-only), and
`test_referee_accuracy_benchmark` (`test_referee_accuracy.py`, legacy AI result
inference remains disabled until Result Claims). They are not counted as
accepted local behavior; the first two groups are accepted by their explicit
PostgreSQL runs above, while the referee benchmark remains unavailable by
policy. PostgreSQL acceptance is run separately so legacy SQLite fixtures
cannot silently target an application database.

A manually combined run that executes `test_new_endpoints.py` before
`test_api_security.py` can make the latter bootstrap-login fixture fail because
the process-wide temporary database already contains a different bootstrap
owner. This is a fixture-ordering limitation, not a production auth failure;
the official collection order and each file in isolation pass. Isolated fixture
ownership is tracked before final acceptance.

Match and overlay HTTP routes now derive workspace scope from the authenticated
session; anonymous legacy projections return an empty result rather than tenant
data. The opt-in `AITOB_LEGACY_HUB_PASSWORD_COMPAT` bridge remains owner-only
and is disabled by default. Start.gg account-bound clients no longer silently
fall back to the platform token unless the explicit legacy fallback switch is
enabled.

The latest workspace isolation regression adds an overlay-write collision case:
an overlay name already owned by Workspace A cannot be overwritten by Workspace
B, and the owner projection remains unchanged. New generic overlay uploads are
rate-limited per workspace, capped at 10 MiB, recorded in `media_assets`, and
use a collision-safe filename; existing static URLs remain untouched. The
ownership-key migration is explicit and idempotent: the SQLite rehearsal
`test_workspace_constraint_migration.py` rebuilds legacy link/overlay tables
without changing URLs, while fresh PostgreSQL schema migration creates
`uq_tournament_player_links_workspace` and `uq_overlays_workspace_name`.
Existing installations must apply the migration receipt before relying on
cross-workspace duplicate keys; no operating database was rewritten here.

The bot command drain is now bound to the workspace selected by its encrypted
Discord integration account. Workflow status/validation, conflict scans,
agent match listings, Ready-view recovery, and deferred score verification use
the same durable scope; unscoped calls remain only for migration and legacy
fixtures.

The T004 runtime inventory is closed. The remaining entries in `tasks.md` are
explicitly non-runtime compatibility contexts: platform-admin-only global
settings/status, direct legacy test callers, the opt-in owner-only
`AITOB_LEGACY_HUB_PASSWORD_COMPAT` bridge, and the bot's initial-registration /
service-heartbeat identity before those identities are migrated. All of them
still use the PostgreSQL repository boundary when a service runs; none can select
an arbitrary workspace or fall back to a SQLite file. The bot's two direct
SQLite reads were removed and guarded by
`test_runtime_bot_paths_do_not_open_sqlite_directly`. Workspace-facing player
and platform-admin API modules are additionally guarded by
`test_workspace_api_paths_use_repository_boundary`.

Start.gg permission probing is opt-in: API startup does not contact the
provider merely because a credential exists. An acceptance operator may set
`STARTGG_TOKEN_PROBE_ON_STARTUP=true` for a disposable run; leaving it unset
keeps startup free of provider probes and preserves the explicit manual probe
path.

Manual non-payment entitlements are available only to an authenticated platform
administrator through `/api/platform/workspaces/{workspace_id}/subscription`.
The `activate`, `extend`, and `suspend` actions update the local plan/status
and expiry atomically with a redacted audit event; they do not perform checkout,
charge a card, or call an external billing gateway. A missing payment gateway
therefore blocks only paid checkout/webhooks, not the free/non-billed runtime.
The API returns status metadata only and never payment or integration secrets.
In the isolated cutover candidate, the designated legacy owner was explicitly
marked as the platform administrator through an audited bootstrap update; the
old runtime database was not changed. A candidate API login and subscription
projection request returned 200 while execution workers remained paused.
A fresh PostgreSQL custom-format backup was taken after that candidate-only
update; the prior verified restore drill remains the recovery evidence.

The latest PostgreSQL acceptance rerun completed 32/32 tests on disposable
databases after the workspace feed/station changes. The local backend suite is
447 passed / 27 skipped; skipped cases remain the explicitly PostgreSQL-only
cases when no `AITOB_PG_TEST_URL` is supplied to the local command.

On 2026-09-10 the PostgreSQL worker/dispatcher acceptance was rerun after
fixing nullable workspace predicates, Boolean coercion, event grouping, and
SQLite-only test assertions. `test_auto_dispatcher_service.py`,
`test_worker_workspace_scope.py`, and `test_provider_recovery.py` completed
21 passed / 1 skipped. The run exercised scoped claims, kill-switch and
tournament pause rechecks, outage freshness, deduplicated decisions, and
workspace-safe worker recovery against the disposable PostgreSQL database.
The same PostgreSQL run now includes Challonge local workflow (8/8), identity
and per-event dispatch scoping (20/20), SQL-safety and tournament-removal
checks (7/7); all are passing against disposable databases. SQLite-only
migration-fixture tests remain intentionally separate from this runtime proof.
The post-fix local regression was rerun on 2026-09-10: 447 passed / 27
intentionally skipped, with no hanging subprocesses or unhandled task errors.
The complete PostgreSQL-targeted regression was then rerun with the explicit
DSN: 469 passed / 5 skipped. The five skips are intentional and named: three
SQLite-source migration cases (the PostgreSQL-target migration test remains
active), the disabled legacy AI Referee benchmark, and one live-network test
protected unless `AITOB_ALLOW_LIVE_TESTS=true` is explicitly set.
The runtime boundary guard itself is 8/8 passing, and the deterministic Outbox
contract is 6/6 on PostgreSQL plus 2/2 queue-hold tests locally; T004 and T006
are therefore closed in `tasks.md`. The remaining live receipt and final
cutover evidence is tracked separately under T043/T052/T053.
Action proposals, Organizer Console, manual entitlements, and workspace
session/role acceptance add 43/43 passing PostgreSQL cases in the latest
isolated run; no external provider or Discord side effect was enabled.
The role acceptance now includes HTTP-positive/negative checks for TO, Stream
operator, Moderator and Viewer (the same test passes on SQLite and PostgreSQL),
and policy-level denial coverage for every non-owner mutating permission.
The latest PostgreSQL assets/integrations/overlay/entitlement/retention/error
regression is 36/36 passing; it exercises encrypted account isolation, overlay
token ownership, referenced-asset deletion guards, manual entitlement limits,
retention, and redacted telemetry without external effects. Legacy overlay
preset ownership backfill and final deletion/Cloudinary operational acceptance
remain explicit T032/T033 gates.
The additional `test_assets_workspace_scope.py` regression passes 1/1 locally
and 1/1 on PostgreSQL, proving a workspace cannot enumerate shared legacy
files through the asset listing API.
The V2 provider lease/outbox repositories now also pass 4/4 on PostgreSQL;
the migration-fixture test remains SQLite-only by design because it validates
upgrading a pre-V2 file rather than runtime PostgreSQL behavior.
Redacted error telemetry and Challonge state-repair acceptance add 4/4 passing
PostgreSQL cases (and 4/4 on the isolated local backend).
Discord thread delivery/restart-view acceptance now passes 3/3 on PostgreSQL
with a seeded disposable tournament; no real Discord delivery is enabled.

The broad `pytest backend/tests --postgres` sweep on 2026-09-10 initially
reported 427 passed, 26 failures, 10 errors, and 2 skips. Those failures were
not hidden: the runtime PG issues in identity, Dispatcher, local Challonge
workflow, SQL-safety, tournament removal, and V2 leases were fixed and rerun.
The final PG-targeted regression is 469 passed / 5 intentional skips. The three
SQLite-source migration fixtures are excluded by an explicit marker while the
PostgreSQL-target migration test remains active; the other two skips are the
disabled AI benchmark and the opt-in live-network test.

The post-acceptance additions include two redacted error-telemetry tests,
seven backup-manifest restore-safety tests, the workspace identity acceptance,
and the asset-listing isolation regression; they are included in the 447-pass
count above.

PostgreSQL runtime smoke (2026-09-09) loaded the FastAPI lifespan against the
configured local PostgreSQL DSN with provider probes disabled, initialized the
schema, started the reconciliation task, and shut down cleanly. No production
SQLite or external provider data was written by this check.

The populated PostgreSQL rehearsal was backed up and restored to a second
disposable PostgreSQL database. Re-opening it with the existing service-level
integration key from the ignored development environment authenticated all five
encrypted credential rows. The key was not emitted or copied into this
document; hosted deployments must inject `AITOB_INTEGRATION_MASTER_KEY` and
`AITOB_AI_SERVICE_MASTER_KEY` separately.

A separate PostgreSQL database `aitob_cutover_candidate_20260909` is now
prepared from the latest read-only SQLite copy. Its 50-table content was
validated, all five encrypted credentials authenticated in a service process,
and a fresh custom-format backup with a verified manifest was created. The
candidate is intentionally not referenced by `.env.production`; no worker or
external integration is pointed at it yet.

Before any worker resume, the candidate queues were inspected from the candidate
database itself. It contains eight pending `workflow_outbox` events (Discord/OBS
and next-match local effects) and nine pending manual `hub_commands`, all owned by
the migrated workspace. The only `provider_command_ledger` row is a score command
already at `snapshot_verified`; it is not replayable. No queue row was executed,
rewritten, or deleted, and the old database's `pg-unknown-effect` fixture remains
isolated there. The reviewed rows are explicitly held by allow-list (not a global
worker pause), so they cannot be claimed after restart while unrelated new work
remains eligible. They remain visible for T052 reconciliation and do not justify
changing the external provider.
The queue rows were classified rather than treated as independent work. Four
Outbox events target the already-complete match 471045156 and four target the
already-in-progress match 471045157. All have zero attempts, no lease, no
`effect_started_at`, no completion timestamp and no receipt. The current rows
also have no Discord identity/thread to validate a call. They remain held for
reconciliation because an old path's missing marker is not proof of non-delivery.
Nine pending manual Hub commands were similarly linked: duplicate/terminal Calls
(126, 129), an in-progress Call (127), a Call without identity mapping (128), a
Call and Score for absent set 103903193 (130, 131), a Call for absent set
103903199 (132), and untargeted legacy commands (133, 134). None has a lease or
receipt, and none was executed, rewritten or deleted.

The reviewed cutover slice was explicitly held in the candidate database using
the new allow-list transaction: exactly the eight event IDs above and command
IDs 126–134 moved from `pending` to `needs_review`. Seventeen `queue.hold` audit
events retain the previous status, attempts, lease/effect markers and hold reason.
A fresh service-context claim returned zero Hub commands and zero Outbox events,
confirming the hold survives restart and does not block unrelated future work.
After the queue inspection and test runs, the source SQLite file was reopened
read-only and its 50-table logical fingerprint still matched the candidate's
`app_migrations` record. No SQLite writer or API/BOT worker was running during
this check, so the candidate was not silently based on a stale pre-pause copy.

Docker Compose now requires both service-level encryption keys explicitly for
the API and bot containers. A local configuration check passed after loading
the existing ignored development values; API and bot import smoke checks each
reported both keys present without printing them. Containers were not started
against the candidate because startup workers may contact providers.

The Windows API entrypoint now uses `backend.api.uvicorn_runner`, which forces
uvicorn to use a Selector event loop before application startup. This is
required for psycopg async connections; the stock uvicorn Windows loop selects
Proactor and fails before PostgreSQL can be opened. A fresh runner process was
started against the candidate with background workers paused: `/health` and
`/readiness` both returned 200 (`database=postgresql`), then the process shut
down cleanly. The runner factory has a regression test; no bot login or
external provider request was made.

The current runtime PostgreSQL database was backed up to a custom-format dump
with a sidecar manifest, and the manifest digest/size/name were verified. A
separate backup of the populated candidate was restored into a new disposable
PostgreSQL database and validated before that disposable database was dropped:
1 workspace, 2 tournaments, 19 active matches, 9 overlays, 2 stations, 2
players, 2 integration accounts, 8 held Outbox rows, 9 held Hub commands, and
17 hold audits were preserved. The old runtime database remains untouched.

The candidate's encrypted Discord credential decrypts through the service key.
The newly supplied token was written through the account-scoped rotation path
(with an audit entry and no plaintext persistence); a direct Discord
`/users/@me` probe returned HTTP 200 and a bot connectivity-only process
connected to the Gateway. Workers remained paused, so no Discord effect was
sent. The token is no longer a connectivity blocker; worker resumption still
requires the reviewed cutover sequence.

## Runtime process reconciliation — 2026-09-10

The earlier report mixed two process contexts: a temporary API smoke process
used the populated cutover candidate, while the long-lived API listener on
port 8000 still used the original `aitob` database (which had zero workspaces
and tournaments). This was verified by process cwd/command lines and direct,
redacted row counts; it was not a data rollback or a change to the candidate.

The duplicate project processes were stopped by verified command and working
directory identity only. A single API supervisor/worker now listens on
127.0.0.1:8000, and a single Bot parent/child runs from the same project and
candidate database. The Vite process remains the sole listener on
127.0.0.1:5173 and proxies `/api`, `/static`, `/assets`, and `/ws` to port 8000.
PostgreSQL is the `aitob_postgres` container on host port 5433. No connection
strings or secrets are recorded here.

The managed launcher loads `.env` followed by `.env.production`, applies the
ignored `AITOB_RUNTIME_DATABASE_NAME` selector to the PostgreSQL URL, and
forces the local Bot Hub URL unless an external URL is explicitly opted in.
After a clean `run.py` restart, `.pids.json` contains one managed API, Bot,
and Vite entry; the proxy login and tournament listing were rechecked through
5173. The API reload worker and Vite child process are lifecycle children of
those entries, not additional service launches.

The new API process was started with background workers enabled and provider
startup probes disabled; `/health` and `/readiness` returned 200 with
`database=postgresql`, owner login succeeded, and the two candidate tournaments
were returned. The Bot connected to Discord and the local Hub WebSocket; the
reviewed eight Outbox rows and nine held Hub commands remained unchanged and
unclaimable. The old `aitob` database remains preserved and is not consumed by
any current API or Bot process.

For a cutover review window, set `AITOB_DISABLE_BACKGROUND_WORKERS=true` before
starting the API. It initializes the database and accepts read-only checks but
does not restore workflows, schedule Live polling, sync tournaments, or start
reconciliation. The switch is opt-in and must be removed only after pending
effects are reviewed.

The configured runtime PostgreSQL database was not overwritten: a cutover
preflight found existing schema history, two seeded stations, and one
`workflow_outbox` row in `needs_review`, so the migration tool correctly refused
to merge into it. That pending external-effect record must be reconciled during
the controlled pause before T052; no row was deleted or rewritten.

On 2026-09-09 a consistent read-only backup of the current SQLite fixture was
restored byte-for-byte, then migrated to a disposable PostgreSQL database and
validated through `app_migrations`. The rehearsal copied 50 tables and the
disposable target was dropped after the check. This was rehearsal only, not a
production cutover; database restore does not roll back accepted external
provider results or Discord deliveries.

On 2026-09-09 a second populated rehearsal used the current operational copy as
the read-only source and a fresh PostgreSQL database as target. It validated 50
tables, one Owner workspace, two tournaments, 19 active matches, nine overlays,
two stations, two players and two integration accounts, with zero NULL ownership
in tournaments, active matches and players. The target was dropped after the
checks; this does not authorize production cutover.

Outbox lease ownership is not remote exactly-once delivery. After dispatch starts,
an unknown outcome or restart before local success becomes `needs_review`.
Only an explicit adapter proof of no send permits automatic retry. No live
Discord/provider effects were used by these tests.

PostgreSQL backup/restore drill (2026-09-09): `backup_database.py` created a
custom-format dump from the local Docker PostgreSQL and `restore_database.py`
restored it into a newly created disposable target. The restored API initialized
successfully with provider probes disabled, then the target was dropped. The
source currently contains only two stations and no workspace/tournament/
credential rows, so this proves dump/restore mechanics but not populated
relationship or encrypted-secret recovery. A separate populated SQLite-to-
PostgreSQL rehearsal decrypted all five encrypted credential rows using their
recorded owner kind, including the OAuth application secret, with zero failures.
Neither disposable target was retained or used for production cutover.

## Explicit recovery backup

Runtime backups use PostgreSQL `pg_dump` and never include service secrets in the
manifest. SQLite is accepted only with the explicit `--sqlite` fixture switch:

```powershell
.\.venv\Scripts\python.exe scripts/backup_database.py --output-dir .backups
.\.venv\Scripts\python.exe scripts/backup_database.py --sqlite --source path\to\copy.sqlite
```

Restore always verifies the sidecar manifest (artifact filename, size and
SHA-256) before opening an explicitly supplied disposable database or file. A
missing or changed manifest fails closed before restore. It does not overwrite
a non-empty SQLite target without `--force`. Restoring SQLite does
not undo an already accepted provider mutation or Discord delivery; reconcile
those effects through the Provider Ledger and workflow Outbox.

Authentication artifact retention is explicit and bounded. A future maintenance
worker may call `backend.core.retention.purge_expired_auth_artifacts()`; it
removes only aged reset/verification tokens, invitations, MFA setup challenges,
expired or revoked sessions, and old limiter buckets. It never deletes
workspace, tournament, match, image, provider, or overlay data. The default is
30 days and `AITOB_AUTH_ARTIFACT_RETENTION_DAYS` may be set from 1 to 3650;
invalid values fail closed. `backend/tests/test_retention.py` proves both
atomic cleanup and preservation of fresh/workspace rows.
