# Research: workspace SaaS and PostgreSQL conversion

## Durable PostgreSQL access

**Decision:** Use one `DATABASE_URL`-backed PostgreSQL connection path at runtime
through `backend.core.storage`; retain SQLite only for explicit test fixtures and
the read-only migration/restore tools.

**Rationale:** The API, Discord bot, workers, and WebSocket handlers must share
the same transactional semantics. A runtime fallback silently reintroduces a
second source of truth and defeats the cutover.

**Alternatives considered:** Keeping SQLite as a runtime fallback was rejected;
it makes a connection failure look like a successful but divergent deployment.

## Concurrent operations

**Decision:** Replace SQLite's process-local `BEGIN IMMEDIATE` intent with
PostgreSQL row locking (`SELECT … FOR UPDATE`), unique idempotency keys, and
atomic conditional updates. Every worker claims work in one transaction and
re-checks its state before an external effect.

**Rationale:** `BEGIN` alone does not reserve a row on PostgreSQL. Durable
claims need both a lock for the current transaction and an invariant that
survives retries and process crashes.

**Alternatives considered:** Advisory locks alone were rejected because they do
not document or enforce idempotency in persisted data. Retrying a remote
mutation after an unknown response was rejected; verification precedes retry.

## SQL parameter adaptation

**Decision:** The compatibility adapter transforms only executable qmark and
named parameter markers. It leaves string literals, quoted identifiers,
line/block comments, and PostgreSQL dollar-quoted text unchanged.

**Rationale:** Regex substitution across SQL text can corrupt JSON examples,
messages, or comments containing `?` and produces a different query.

**Alternatives considered:** Global replacement was rejected. The longer-term
direction is to use PostgreSQL-native query syntax in converted repositories,
but the parser provides a safe bridge while direct SQLite repositories are
being eliminated.

## Workspace ownership migration

**Decision:** A one-time bootstrap/migration creates a designated owner user,
workspace, and owner membership before assigning legacy operational rows. The
first future registrant never inherits orphaned data.

**Rationale:** Existing data has operational value and cannot be safely assigned
based on an untrusted later registration.

**Alternatives considered:** Null workspace ownership and an automatic
"first-user wins" assignment were rejected as isolation violations.

## Public overlay access

**Decision:** Browser sources use a revocable, rotated, least-privilege token
bound to one workspace/station/overlay. They do not carry an organizer session
and cannot call administrative APIs.

**Rationale:** OBS needs a stable display URL but must not inherit a dashboard
credential.

**Alternatives considered:** Reusing a hub password or authenticated web session
was rejected because it would expose administration through a public source.

## Secrets and migrations

**Decision:** Keep encryption keys outside the database; migrate encrypted
blobs byte-for-byte, then test decryptability with the same configured service
key. Never log decrypted material.

**Rationale:** Database backups remain useful only if the separately protected
key recovery procedure is known and tested.

**Alternatives considered:** Re-encrypting every historical secret during the
data-copy phase was rejected because it increases migration risk and makes
rollback harder.

## External effects and rollback

**Decision:** Database rollback and external-effect recovery are separate
procedures. Provider commands and Discord outbox entries are reconciled by
their durable ledgers after a restart; restoring an old database is never used
to undo a result or message already accepted externally.

**Rationale:** External providers cannot be transactionally rolled back with
PostgreSQL.

**Alternatives considered:** Treating backup restore as a global undo was
rejected because it would invite duplicated or contradictory external actions.
