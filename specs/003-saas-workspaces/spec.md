# Feature Specification: Workspace SaaS Foundation

**Feature Branch**: `codex/003-saas-workspaces`  
**Created**: 2026-09-07  
**Status**: Planned — implementation in progress  
**Input**: Convert aiTOB into a secure, workspace-isolated SaaS while preserving existing tournament operations and published assets.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run an isolated tournament workspace (Priority: P1)

An organization owner creates a workspace, invites a tournament team, connects only that workspace's services, and runs its tournaments without seeing or affecting another organization.

**Why this priority**: Data ownership and safe operation are prerequisites for every multi-organizer capability.

**Independent Test**: Create two workspaces with intentionally similar tournament, station, and provider identifiers; verify every role, background action, and public display remains scoped to its own workspace.

**Acceptance Scenarios**:

1. **Given** two active workspaces, **When** an organizer requests a tournament, station, identity, command, or integration outside their workspace, **Then** access is denied without revealing whether the target exists.
2. **Given** two workspaces import the same external tournament, **When** each manages its local operations, **Then** their local matches, stations, messages, overlays, budgets, and audit records remain separate while remote changes are clearly treated as shared external effects.
3. **Given** a membership is disabled or its role changes, **When** it makes its next request or uses an existing live connection, **Then** newly prohibited actions stop immediately.

---

### User Story 2 - Manage secure accounts and a team (Priority: P1)

An owner and permitted team members sign in securely, complete account recovery and second-factor checks, manage roles and invitations, and retain no default or shared administrative credential.

**Why this priority**: A SaaS product cannot safely expose tournament operations without accountable identities and authorization.

**Independent Test**: Exercise account registration by invitation, sign-in, sign-out, recovery, second-factor enrollment and recovery, role changes, revocation, and last-owner protection using test identities.

**Acceptance Scenarios**:

1. **Given** a new deployment has no owner, **When** a locally protected, one-time initialization succeeds, **Then** exactly one owner and workspace are created and the initialization path closes.
2. **Given** a team member is assigned a role, **When** they attempt actions outside that role, **Then** the server rejects the action even if a client exposes its control.
3. **Given** an owner attempts to remove or demote the last active owner, **When** the change is submitted, **Then** it is rejected.

---

### User Story 3 - Preserve and migrate operational data (Priority: P1)

An operator migrates the existing Hub safely, preserving all tournament relationships, encrypted credentials, images, overlays, and operational history before switching the live system to its new source of truth.

**Why this priority**: Existing tournaments and credentials are operationally valuable and must not be lost or silently altered.

**Independent Test**: Migrate a faithful copy, compare records, relationships, nullable values, times, unique keys, encrypted secret readability, and image references; restore a backup and run the application against it.

**Acceptance Scenarios**:

1. **Given** an operational data copy, **When** migration completes, **Then** every migrated resource has an explicit workspace owner and equivalent content and references.
2. **Given** an image or overlay reference existed before migration, **When** it is displayed afterwards, **Then** its existing URL, filename, and display precedence are unchanged.
3. **Given** a final switchover is needed, **When** writes and workers are paused, **Then** a current backup, recovery procedure, pending-work review, and no-loss rollback plan are available.

---

### User Story 4 - Manage integrations and public overlays safely (Priority: P2)

An owner manages Start.gg, Challonge, Discord destinations, and organization-scoped settings without exposing secrets. Stream operators use revocable browser-source links that expose only the assigned public overlay data.

**Why this priority**: Integrations and overlays must work in multi-tenant operation without granting administrative access.

**Independent Test**: Connect, rotate, disable, and test accounts in two workspaces; verify secrets never appear in API output or logs and an overlay link cannot access management data.

**Acceptance Scenarios**:

1. **Given** an integration belongs to one workspace, **When** another workspace requests it, **Then** neither its identity, destinations, budget, status, nor secret is exposed.
2. **Given** a public overlay link is revoked or rotated, **When** its old link is used, **Then** it cannot read the overlay and cannot call administrative endpoints.

---

### User Story 5 - Operate under safe limits and service plans (Priority: P3)

An organization can use a clearly identified free service state or assigned plan, receives enforceable usage limits, and retains read access to its data when an entitlement changes.

**Why this priority**: Plans and limits prepare the product for billing without inventing commercial terms or risking data loss.

**Independent Test**: Assign plans and limits to two workspaces, exhaust one limit, and verify the other remains unaffected while historical data stays readable.

## Edge Cases

- A provider mutation is shared externally by two workspaces; each must verify freshness and display a conflict rather than overwrite local history.
- A stale browser-source link, disabled membership, expired session, or consumed recovery code must fail without disclosing data.
- A backup restore must retain access to encrypted secrets through a separately protected service key; it must not create a hidden alternate source of truth.
- Email delivery may be unavailable in development; the system must not claim that verification, invitation, or recovery mail was delivered.
- Manual single-player DQ remains available to authorized tournament staff; AI DQ and auto-DQ remain prohibited.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST assign every operational resource and all derived work to exactly one workspace before enabling multi-workspace access.
- **FR-002**: The system MUST authorize every management action from a trusted active session and membership, never from a client-supplied workspace identifier.
- **FR-003**: The system MUST support Owner, Tournament Organizer, Stream Operator, Moderator, and Viewer roles with server-enforced permissions and last-owner protection.
- **FR-004**: The system MUST provide secure sign-in, sign-out, session revocation, protected one-time owner initialization, password change and recovery, email verification, second-factor authentication, and single-use recovery codes.
- **FR-005**: The system MUST implement invitation- and policy-gated public registration, keep it disabled by configuration until workspace-isolation acceptance tests pass, and never treat that flag as permission to bypass membership checks.
- **FR-006**: The system MUST keep provider accounts, Discord destinations, provider budgets, command history, cache, and encrypted secrets isolated by workspace.
- **FR-007**: The system MUST preserve existing image files and references during migration and use one validated `image_store` path for new Discord and participant images, including MIME/decode validation, size/dimension limits, Cloudinary delivery variants for hosted deployments, OBS display sizing, authorized deletion, and reference protection.
- **FR-008**: The system MUST give every public browser-source link only the minimum read access to its assigned overlay and support revocation and rotation.
- **FR-009**: The system MUST migrate operational data with repeatable, validated migrations and use one authoritative operational data store after cutover.
- **FR-010**: The system MUST validate migrated values, relationships, uniqueness, timestamps, nullable fields, encrypted secrets, and image references, not only record counts.
- **FR-011**: The system MUST make command claims, approvals, station reservations, provider commands, and external-effect delivery idempotent under concurrent requests and restart recovery; an unknown external outcome is verified/reconciled before retry rather than blindly resent.
- **FR-012**: The system MUST retain integration, email, and service secrets using authenticated encryption with service-level key management outside the database, fail closed when the key is unavailable, and never return secrets in management responses, logs, audit records, or errors.
- **FR-013**: The system MUST provide redacted audit records and error tracking, health/readiness status, distributed request limits, CSRF/CORS/session protections, and safe browser-source controls.
- **FR-014**: The system MUST provide organization-level plans, subscriptions, entitlements, and usage limits without inventing commercial prices, trials, or live payment collection; when a specific payment gateway is configured, it MUST support a separately tested sandbox checkout/webhook path.
- **FR-015**: The system MUST preserve read access and retained data when an entitlement expires; it MUST not delete organizational data solely because of plan state.
- **FR-016**: The system MUST provide a documented, tested backup, retention, restore, and cutover/rollback procedure that accounts for external Discord and provider effects separately from database restoration.
- **FR-017**: The system MUST keep manual authorized result reporting and single-player DQ in their approved paths; it MUST prohibit AI approval/execution, AI DQ, and auto-DQ.

### Key Entities

- **Workspace**: The organization boundary that owns members, operational resources, settings, activity, and usage.
- **Membership**: A user's active role and access within one workspace.
- **Integration Account**: A workspace-owned connection to a provider or Discord destination with protected credentials and status.
- **Tournament Resource**: A workspace-local representation of an external bracket, its matches, participants, identity links, and operations.
- **Public Overlay Link**: A revocable, least-privilege display credential for a single overlay context.
- **Entitlement**: A workspace plan state and enforceable service limit, independent of stored historical data.
- **Audit Event**: A redacted record linking workspace, actor, action, target, outcome, and trace reference.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a two-workspace acceptance suite, 100% of cross-workspace HTTP, live-connection, background-work, and public-link access attempts are denied or return only the caller's own data.
- **SC-002**: A faithful migration and restore preserves 100% of validated operational relationships, image references, encrypted-secret readability, and expected unique records.
- **SC-003**: 100% of concurrent duplicate approval, call, reservation, command, and external-effect test cases produce at most one durable operation or effect.
- **SC-004**: An authorized organizer can complete sign-in, second-factor verification, and access to their workspace in under two minutes using a prepared test account.
- **SC-005**: A revoked session, membership, overlay link, or recovery code is rejected on its next use in 100% of acceptance attempts.
- **SC-006**: When no payment provider is configured, 100% of plan screens identify the service as free/non-billed and expose no live checkout path.

## Assumptions

- Existing workspace data belongs to a designated current owner during migration; it is never assigned to the first future registrant.
- Email delivery and live payment collection remain disabled until their respective production providers are configured; all independent account, entitlement, and isolation work proceeds with controlled test delivery.
- Existing provider mutations remain externally shared when organizations connect to the same external tournament; freshness, verification, and conflict handling remain mandatory.
- Existing player images and overlay files remain published assets with unchanged paths during this feature; future cleanup is separate and explicit.
- Legacy ownership backfill occurs only after a designated Owner workspace exists; relationships are validated before `workspace_id` constraints become `NOT NULL`.
- Wizard flows, Result Claims, `/link-startgg`, Console redesign, AI result approval, AI DQ, and auto-DQ are out of scope.
