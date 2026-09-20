# Runtime storage contract

## Startup

`DATABASE_URL` is required for API, Discord bot, workers, and WebSocket runtime.
If absent or the connection/migrations fail, startup terminates before it begins
serving requests. There is no alternate runtime, test, migration, backup, or
restore database engine.

## Transaction rules

1. A command, approval, reservation, or outbox claim has an idempotency key.
2. The service begins a transaction and locks the target record on PostgreSQL
   with `FOR UPDATE` (or performs a conditional atomic claim).
3. It validates workspace, permissions, current state, and key uniqueness.
4. It persists all local state and the durable work item atomically.
5. A worker performs an external side effect only after it owns an unexpired
   lease and rechecks state. Success is recorded using the effect's
   deduplication key.

`BEGIN IMMEDIATE` is not a PostgreSQL concurrency primitive and must not be
treated as one.

## Failure behavior

Unknown remote mutation outcomes go to verification before retry. Database
restore does not retract Discord or provider side effects; reconciliation uses
the ledger/outbox records.
