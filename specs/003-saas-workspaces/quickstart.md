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
complete operational acceptance. The operational SQLite Hub was first backed up and then assigned to
the designated Owner workspace in one transaction; all scoped operational rows
now have a valid workspace reference.

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

The local complete suite completed without hanging (412 passed / 21 skipped),
but exposed a thread-cleanup warning. The focused recovery/budget/coordinator
group reproduced it with warnings treated as errors. Scheduler `close()` now
awaits stopped tasks, and the explicit test-only SQLite connector drains opening
and closing work on cancellation. The focused group then passed all 17 tests.
The full post-fix rerun completed at 412 passed / 21 skipped (2026-09-09).

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

The remaining T004 inventory is recorded in `tasks.md`: settings/hub
compatibility endpoints, global hub status, tournament/station enumeration, and
broad bot worker contexts still need conversion from the owner-only bridge. Hub
feed and manual command writes now carry workspace ownership (including
`bot_feed` in the legacy backfill). The bot's two direct
SQLite reads were removed and guarded by
`test_runtime_bot_paths_do_not_open_sqlite_directly`. Workspace-facing player
and platform-admin API modules are additionally guarded by
`test_workspace_api_paths_use_repository_boundary`.

The latest PostgreSQL acceptance rerun completed 25/25 tests on disposable
databases after the workspace feed/station changes. The local backend suite is
412 passed / 21 skipped; skipped cases remain the explicitly PostgreSQL-only
cases when no `AITOB_PG_TEST_URL` is supplied to the local command.

On 2026-09-09 a consistent read-only backup of the current SQLite fixture was
restored byte-for-byte, then migrated to a disposable PostgreSQL database and
validated through `app_migrations`. The rehearsal copied 50 tables and the
disposable target was dropped after the check. This was rehearsal only, not a
production cutover; database restore does not roll back accepted external
provider results or Discord deliveries.

Outbox lease ownership is not remote exactly-once delivery. After dispatch starts,
an unknown outcome or restart before local success becomes `needs_review`.
Only an explicit adapter proof of no send permits automatic retry. No live
Discord/provider effects were used by these tests.

## Explicit recovery backup

Runtime backups use PostgreSQL `pg_dump` and never include service secrets in the
manifest. SQLite is accepted only with the explicit `--sqlite` fixture switch:

```powershell
.\.venv\Scripts\python.exe scripts/backup_database.py --output-dir .backups
.\.venv\Scripts\python.exe scripts/backup_database.py --sqlite --source path\to\copy.sqlite
```

Restore always targets an explicitly supplied disposable database or file; it
does not overwrite a non-empty target without `--force`. Restoring SQLite does
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
