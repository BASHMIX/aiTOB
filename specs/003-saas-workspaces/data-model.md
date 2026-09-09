# Data model: workspace SaaS

## Identity and access

| Entity | Required fields | Relationships / rules |
|---|---|---|
| `users` | immutable id, normalized email, password hash, verification state, 2FA state, disabled timestamp | No default password. A disabled user cannot establish or continue a session. |
| `workspaces` | immutable id, display name, status, timestamps | The organization boundary; may not be inferred from a client request. |
| `memberships` | user id, workspace id, role, active state | Unique `(user_id, workspace_id)`; at least one active Owner is required. |
| `user_sessions` | opaque token hash, user id, expiry, revoked timestamp, session metadata | Every request resolves an active session then an active membership. |
| `workspace_invitations` | workspace id, email, requested role, opaque token hash, expiry, lifecycle | Single use; acceptance creates membership atomically. |
| `totp_credentials` / `recovery_codes` | user id, encrypted TOTP secret / hashed one-use codes | Enrolment and recovery code consumption are auditable. |

Roles are `owner`, `tournament_organizer`, `stream_operator`, `moderator`, and
`viewer`. Permissions are checked in services and routes; UI visibility is only
a convenience.

## Operational ownership

All current and new rows that identify operational state receive a non-null
`workspace_id`: tournaments/events/matches/participants, identity links and
images, integration accounts and destinations, stations and overlay links,
dispatcher decisions, proposals, hub/provider commands, workflow outbox,
snapshots/cache/budgets, audit events, and background job claims.

External provider identity remains composite: provider + provider account +
provider-specific canonical tournament/event/match identifiers. The local
primary key is workspace-scoped, so two workspaces may track the same external
tournament without local collisions.

## Integrations and assets

| Entity | Ownership and invariant |
|---|---|
| `integration_accounts` | `workspace_id`; unique provider/external account identity per workspace; encrypted credentials never leave the server. |
| Discord destinations | child of a workspace-owned Discord account, scoped to its guild/channel/thread configuration. |
| Overlay link | workspace and station scoped; opaque secret hash; revocable and rotatable; read-only display projection. |
| Image asset/reference | workspace-owned metadata; pre-existing URLs and filenames are preserved; deletion is rejected while referenced. |

## Reliable execution

`action_proposals`, `hub_commands`, `provider_commands`, and
`workflow_outbox` carry workspace id, actor/origin, idempotency or deduplication
keys, lifecycle state, attempts, lease owner, lease expiry, and timestamps.
Approvals and effects are separate state machines. Unique keys plus row locking
guarantee a single durable decision/effect under retry.

## Entitlements and audit

`workspace_entitlements` records a free/non-billed or externally managed plan,
limits, usage window, and state. It restricts writes/automation when exhausted,
never deletes historical rows. `audit_events` records workspace, actor, action,
safe target reference, result, trace id, and timestamp with redaction.
