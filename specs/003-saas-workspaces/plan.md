# Implementation Plan: Workspace SaaS Foundation

**Branch**: `codex/003-saas-workspaces` | **Date**: 2026-09-07 | **Spec**: [spec.md](spec.md)

## Summary

Convert aiTOB from a single Hub/SQLite application to a PostgreSQL-backed,
workspace-isolated SaaS without changing the approved manual tournament paths.
The conversion is incremental internally but has one runtime source of truth:
API, bot, workers, WebSocket, and repositories use PostgreSQL; SQLite survives
only as a test fixture and read-only migration source. The work adds secure
identity, workspace ownership, account-scoped integrations, revocable public
overlays, auditable reliable operations, and a free/non-billed entitlement
foundation. AI remains read/propose-only; auto-DQ and AI DQ stay forbidden.
Public registration is implemented but configuration-disabled until isolation
acceptance succeeds; billing remains free/non-billed unless a named gateway is
configured, in which case only its sandbox path is enabled.

## Technical Context

**Language/Version**: Python 3.12, TypeScript/React 19

**Primary Dependencies**: FastAPI, discord.py, psycopg 3 async, PostgreSQL 17,
Pydantic, Vite, Tailwind

**Storage**: PostgreSQL is the runtime source of truth; SQLite is test/migration
source only; existing image files/Cloudinary references remain unchanged

**Testing**: pytest/pytest-asyncio using an explicit temporary SQLite fixture;
dedicated disposable PostgreSQL integration database; React/Vitest and Vite
build

**Target Platform**: Local Docker development then hosted API/bot/worker
deployment

**Project Type**: Web application with API, bot/background workers, and React
administration UI

**Performance Goals**: one worker claim/effect per idempotency key under
concurrency; no cross-workspace reads; dashboard/console reads do not trigger
provider calls

**Constraints**: fail closed without `DATABASE_URL` or the encryption service
key; no dual-write/fallback; authenticated encryption/redacted error tracking;
CSRF/CORS/session protection; preserve public asset paths; provider results
remain externally shared when the same remote tournament is connected twice

**Scale/Scope**: multi-workspace organizations, five roles, per-workspace
integrations/tournaments/stations/overlays/operations. Public registration is
implemented but closed by configuration until isolation acceptance; live billing
is not active at this stage.

## Constitution Check

The repository constitution ratifies workspace isolation, PostgreSQL as the sole
runtime source, secret/external-effect safety, asset preservation, and
verification before cutover. The implementation passes this check only while
those gates remain enforced; T004/T020/T051a/T053 are blocking gates for T052.

## Project Structure

```text
backend/
├── api/                 # FastAPI routes, auth/session and WebSocket entrypoints
├── bot/                 # Discord runtime and worker entrypoints
├── core/                # storage, repositories, domain services, migrations
└── tests/               # isolated SQLite unit tests and explicit PG integration tests
frontend-react/
└── src/                 # authenticated workspace UI and public overlay views
scripts/                 # migration, backup/restore, owner bootstrap and acceptance tools
specs/003-saas-workspaces/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/
└── quickstart.md
```

**Structure Decision**: Retain the existing three-service layout. Centralize
connection acquisition in `backend/core/storage.py`, then convert repository
boundaries and callers rather than maintaining separate SQLite and PostgreSQL
implementations.

## Delivery sequence

1. **Runtime storage correctness** — prove PostgreSQL transactions, parameter
   parsing, claims, retries, and fail-closed startup; convert all direct SQLite
   runtime paths.
2. **Ownership and isolation** — create the designated owner workspace first,
   then backfill and validate ownership/relationships before imposing `NOT NULL`
   ownership on every resource, worker, cache key and WebSocket.
3. **Identity and membership** — complete protected owner bootstrap, sessions,
   roles, invitations, recovery, email verification, 2FA and rate limits.
4. **Resources and integrations** — migrate legacy data to a designated owner,
   remove global provider fallbacks, scope Discord destinations/assets/stations,
   unify new image upload via `image_store` (validation, Cloudinary variants,
   OBS sizing, authorized deletion), and issue revocable overlay tokens.
5. **Operational reliability** — apply PostgreSQL-safe claims to commands,
   reservations, ledger and outbox; prove restart and external-effect recovery,
   including the crash window after an external provider/Discord effect arrives
   but before local success is saved.
6. **Entitlements and operations** — free/non-billed plans, conditional payment
   gateway sandbox, audit/error tracking, CSRF/CORS, backups, retention,
   restore, and deletion policy.
7. **Rehearsal and cutover** — faithful copy validation, write pause, fresh
   backup, pending-work review, runtime restart, isolation acceptance, and a
   no-loss rollback plan. A test rehearsal never substitutes for final cutover.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Compatibility adapter during repository conversion | Existing repository layer contains SQLite query syntax | Global SQL replacement cannot provide safe PostgreSQL transaction/locking behavior |
| Dedicated PG integration database | SQLite tests cannot prove PostgreSQL locking or isolation | Unit-only testing would leave the central migration risk untested |
