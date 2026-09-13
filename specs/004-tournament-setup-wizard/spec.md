# Feature Specification: Tournament Setup Wizard, Player Registration, and Workspace AI Keys

**Feature Branch**: `main` (no new branch created, per user request)

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "Create a simple five-step tournament setup wizard for provider/event selection, tournament review and branding, Discord setup, organizer AI setup, and final activation. Preserve the existing assistant settings and let each workspace owner connect their own preferred Gemini or OpenAI API key so aiTOB does not resell AI tokens. Add tournament-scoped Discord player registration with an opening/closing window, optional required provider registration, configurable Gamertag/Discord-name matching or server nickname changes, optional Start.gg bio verification, roster synchronization, player image upload, manual Discord ID linking from the Event participant list, and canonical Prefix/Gamertag player naming across aiTOB."

## Clarifications

### Session 2026-09-13

- Q: Should assistant provider, model, mode, and limits be shared by all tournaments in a Workspace or configurable per tournament? → A: One Workspace-wide configuration shared by all tournaments (Option A).
- Q: Who supplies and manages external connections? → A: The customer organizer connects and uses credentials from their own Start.gg, Challonge, Gemini, and OpenAI accounts; the aiTOB Platform Administrator supplies no shared customer credentials. The organizer authorizes the separately specified managed aiTOB Discord bot for their own server.
- Q: When multiple organizers belong to one Workspace, are external connections shared or private to the user who added them? → A: Connections are shared Workspace resources governed by permissions (Option A); authorized organizers may add multiple provider accounts, members never see the secrets, each tournament selects its Start.gg/Challonge account, and AI keeps one Workspace-wide active selection.
- Q: Which providers must support remote bracket start in this Epic? → A: Both Start.gg and Challonge must support an explicit remote-start action; the feature is not complete until both provider operations are authorized and verified.
- Q: Which `CALLED` transition should trigger the Discord player call? → A: Every real transition to `CALLED` triggers the same Discord call whether its source is Start.gg synchronization or an authorized Dashboard action; duplicate observations of the same transition must not send duplicate messages.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import the intended tournament event (Priority: P1)

An authorized organizer connects or selects a Start.gg or Challonge account, identifies the tournament they want to manage, and confirms the exact bracket scope before anything is saved as an active tournament.

**Why this priority**: Every later setting, message, result, and overlay depends on selecting the correct external tournament and event.

**Independent Test**: Connect a provider account, enter a Start.gg Event slug and separately a tournament-level link, and verify that the direct Event is preserved while the tournament-level link requires an explicit Event choice; repeat with a Challonge bracket.

**Acceptance Scenarios**:

1. **Given** an organizer has a reusable provider connection, **When** they open the wizard, **Then** they can select that connection without entering its credential again.
2. **Given** a valid Start.gg Event URL or Event slug, **When** it is resolved, **Then** the matching tournament and Event are selected and displayed for confirmation.
3. **Given** a Start.gg tournament link with multiple Events, **When** it is resolved, **Then** no Event is silently chosen and the organizer must select one.
4. **Given** a Challonge tournament identifier, **When** it is resolved, **Then** the single managed bracket is displayed for confirmation.
5. **Given** a failed, expired, or insufficient provider connection, **When** the organizer tries to continue, **Then** the wizard explains the problem and preserves all entered draft data.
6. **Given** a customer organizer is setting up a tournament, **When** they connect Start.gg or Challonge, **Then** the connection uses credentials issued for that customer’s own provider account rather than credentials owned by the aiTOB platform operator.

---

### User Story 2 - Review branding and safe operating defaults (Priority: P1)

The organizer reviews provider facts, fills any presentation gaps, and chooses a simple manual or assisted operating preset before configuring optional services.

**Why this priority**: The organizer must understand what was imported and what aiTOB will do before enabling tournament operations.

**Independent Test**: Import an Event with incomplete metadata, apply a local name, logo, timezone, and assisted preset, and verify the summary and editor-visible tournament identity use the reviewed values without overwriting provider-owned facts.

**Acceptance Scenarios**:

1. **Given** imported provider data, **When** the review step opens, **Then** it distinguishes provider facts from editable local presentation fields.
2. **Given** the provider does not supply a date, state, timezone, or logo, **When** the data is reviewed, **Then** the missing value is shown explicitly and the organizer can provide an allowed local value where applicable.
3. **Given** an uploaded tournament logo and local display name, **When** the wizard is saved, **Then** the same tournament identity is available to the Hub, overlays, and Editor bindings.
4. **Given** a Start.gg tournament, **When** wave readiness is checked, **Then** the wizard shows verified enabled, verified disabled, unsupported, or unknown rather than guessing.
5. **Given** the assisted preset, **When** its defaults are reviewed, **Then** player absence produces reminders and organizer escalation without automatic disqualification.
6. **Given** advanced operating settings are left untouched, **When** the organizer continues, **Then** safe recommended defaults are applied and summarized in plain language.
7. **Given** Start in wave is verified enabled or explicitly confirmed by the organizer when provider verification is unavailable, **When** the bracket starts and Start.gg first reports matches as `CALLED`, **Then** aiTOB synchronizes those transitions and sends the affected players one Discord call per match.
8. **Given** an authorized organizer changes a match to `CALLED` in the aiTOB Dashboard, **When** Discord is enabled and ready, **Then** the same player-call workflow runs without waiting for a Start.gg-originated transition.

---

### User Story 3 - Connect Discord and tailor the bot experience (Priority: P1)

An organizer optionally connects Discord, selects a server and tournament destinations, verifies required permissions, and previews the messages players will receive.

**Why this priority**: Discord is the main player interaction channel, and a stored bot credential alone does not prove that the bot can operate in the selected server and channels.

**Independent Test**: Add the managed aiTOB bot to a test server, select match and escalation destinations, customize a call template, and verify permissions and previewed output before activation.

**Acceptance Scenarios**:

1. **Given** Discord has not been connected, **When** the organizer selects Connect Discord, **Then** they can authorize installation and select a server they are permitted to manage.
2. **Given** the bot is installed, **When** server configuration loads, **Then** the organizer can select the match destination, organizer escalation destination, and moderator role from readable lists.
3. **Given** a selected destination lacks a required permission, **When** readiness is checked, **Then** the exact missing capability and correction are shown.
4. **Given** a message template, **When** the organizer edits it, **Then** a realistic preview renders supported variables and identifies invalid variables before save.
5. **Given** the shared aiTOB bot is selected, **When** server-specific identity customization is available, **Then** the organizer may set the permitted server-specific bot identity without affecting other servers.
6. **Given** Discord is skipped, **When** the organizer completes the wizard, **Then** the tournament remains usable through manual Hub operations and Discord can be added later.

---

### User Story 4 - Use a workspace-owned AI connection (Priority: P1)

A workspace owner or other explicitly authorized administrator connects their own Gemini or OpenAI API key, keeps the existing assistant controls, tests the selected connection, and uses the assistant without purchasing AI tokens from aiTOB.

**Why this priority**: Workspace-owned credentials keep provider billing under the customer's control while preserving the current organizer assistant experience.

**Independent Test**: In two workspaces, configure different providers and keys, retain distinct assistant settings, run connection tests and assistant requests, rotate one key, and verify neither workspace can see or use the other's credential or configuration.

**Acceptance Scenarios**:

1. **Given** a workspace owner opens AI settings, **When** they select Gemini or OpenAI, **Then** they can add their own API key and understand that the external provider bills their account directly.
2. **Given** a saved key, **When** any settings screen is opened later, **Then** the key value is never returned or displayed and only its configured and test status is shown.
3. **Given** an existing assistant configuration, **When** workspace-owned connections are introduced, **Then** provider, model, operating mode, request limit, token limit, context limit, response limit, timeout, and assistant safety policy remain available with their existing meaning.
4. **Given** both Gemini and OpenAI credentials have been saved by the workspace, **When** the organizer changes the selected provider, **Then** the matching saved connection is used and the other connection remains protected for later reuse.
5. **Given** a new or replacement key, **When** the owner explicitly runs a connection test, **Then** the wizard reports success or an actionable failure without exposing the key or provider response secrets.
6. **Given** an invalid, revoked, rate-limited, or out-of-credit key, **When** the assistant is invoked, **Then** the assistant fails safely, tournament operations continue, and the organizer receives an actionable status.
7. **Given** the assistant is disabled or no AI key is configured, **When** the tournament is active, **Then** non-AI bot templates and manual organizer controls continue to work.
8. **Given** a member without integration-management permission, **When** they view AI settings, **Then** they cannot add, replace, test, disable, or remove a workspace credential.
9. **Given** multiple tournaments belong to one workspace, **When** an authorized administrator changes the active AI provider, model, mode, or limits, **Then** the updated workspace configuration applies to new assistant requests for all of those tournaments without per-tournament overrides.
10. **Given** a customer organizer connects Gemini or OpenAI, **When** the assistant makes a request, **Then** it uses that customer’s saved key and provider account, with no aiTOB-owned key, shared token pool, or hidden platform fallback.

---

### User Story 5 - Review, save, and activate safely (Priority: P2)

The organizer reviews one consolidated readiness summary, returns to any completed step to correct it, and chooses an action that accurately reflects provider and local tournament state.

**Why this priority**: Activation can trigger player-facing operations, so the final decision must be explicit, reviewable, and truthful about what is ready.

**Independent Test**: Complete the wizard with mixed ready, optional, and blocked services; follow edit links, reload and resume the draft, save and activate local management, then start separate disposable Start.gg and Challonge brackets through explicit confirmed provider actions and verify each resulting provider state.

**Acceptance Scenarios**:

1. **Given** a partially completed wizard, **When** the organizer leaves and returns, **Then** the latest saved draft and completed-step status are restored.
2. **Given** a final review, **When** a summary item is selected, **Then** the organizer returns to the relevant step without losing later entries.
3. **Given** a required readiness failure, **When** activation is attempted, **Then** activation is blocked and the summary links directly to the correction.
4. **Given** only optional Discord or AI configuration is incomplete, **When** the organizer chooses to skip it, **Then** activation is allowed and the limitation is shown in the final summary.
5. **Given** remote bracket start is temporarily unavailable because of state, freshness, credential, permission, or provider outage, **When** setup completes, **Then** the organizer may still save or activate aiTOB management and sees the exact blocked start reason without a false success claim.
6. **Given** a configured Start.gg or Challonge bracket passes remote-start preflight, **When** the organizer explicitly confirms Start bracket, **Then** aiTOB sends one idempotent provider-specific start operation, verifies the resulting state, and reports any unknown outcome for reconciliation rather than retrying blindly.
7. **Given** a reusable setup is desired, **When** the organizer saves it as a template, **Then** reusable preferences exclude tournament identifiers, credentials, dates, player data, and other tournament-specific secrets.

---

### User Story 6 - Resume and administer connections outside the wizard (Priority: P2)

Customer organizers with integration-management permission manage shared provider, Discord, and AI connections from a central settings area. Authorized workspace members select permitted reusable connections and apply non-AI tournament-specific overrides in the wizard without receiving secret values.

**Why this priority**: Connections live longer than one tournament and should not require repeating sensitive setup for each Event.

**Independent Test**: Configure reusable connections centrally, use them in two tournament drafts, rotate or disable one connection, and verify each affected tournament reports its readiness without losing its configuration.

**Acceptance Scenarios**:

1. **Given** a reusable connection, **When** multiple tournaments select it, **Then** each tournament retains an explicit binding and its own destinations and behavior settings.
2. **Given** a connection is rotated, **When** dependent tournament readiness is checked, **Then** the new credential is used without re-entering it in each tournament.
3. **Given** a connection is disabled or removed, **When** a dependent tournament is opened, **Then** it shows a non-secret connection error and offers an authorized replacement.
4. **Given** workspace defaults exist, **When** a new wizard starts, **Then** non-AI tournament preferences are inherited visibly and can be overridden for that tournament without changing other tournaments; AI configuration remains Workspace-wide.
5. **Given** an authorized organizer adds another account for the same bracket provider, **When** a tournament is configured, **Then** the organizer selects the exact account used for that tournament and other authorized members can use it without seeing its credential.

---

### User Story 7 - Register and verify tournament players in Discord (Priority: P1)

An organizer configures a tournament-specific Discord registration period. During that period, players confirm their tournament entry, link their Discord identity to the exact provider entrant, and upload or retain a broadcast image according to the tournament policy.

**Why this priority**: Match calls cannot reliably reach the right players unless tournament enrollment, provider participation, Discord identity, and image readiness are tracked separately and synchronized before bracket operation.

**Independent Test**: Open a registration window for a Start.gg Event, require provider registration, register entrants through exact Gamertag matching, bot-managed server nickname change, optional bio-code verification, and manual Discord ID linking from an entrant row; upload a valid image and verify ready/pending/conflict states. Repeat with bio verification disabled, provider registration optional, and a Challonge entrant using the same Gamertag/nickname or manual-ID policy.

**Acceptance Scenarios**:

1. **Given** Discord player registration is configured, **When** the opening time arrives, **Then** the bot publishes or enables the tournament-specific registration action in the configured channel and shows the closing time in the tournament timezone.
2. **Given** the registration window has not opened or has closed, **When** a player tries to begin or confirm registration, **Then** the bot rejects the action with the applicable opening or closing time and does not create a verified tournament enrollment.
3. **Given** provider registration is required and Gamertag matching is enabled, **When** a player begins Discord registration, **Then** the bot verifies that an entrant with the exact configured Gamertag exists in the selected Event or bracket and either confirms an exact Discord-name match or applies the organizer-approved server nickname change before completing that verification method.
4. **Given** the organizer optionally enables Start.gg bio verification, **When** a Start.gg entrant uses that method, **Then** the bot issues a short-lived one-use code for that tournament and confirms control only after the code is observed in the matching Start.gg profile bio.
5. **Given** a player has a reusable verified provider identity in the Workspace, **When** they join another tournament using the same provider identity, **Then** the bot can reuse the identity proof while still checking entry in the new exact Event or bracket.
6. **Given** provider registration is optional, **When** a Discord user completes the permitted local flow, **Then** their tournament enrollment is recorded without pretending that a provider entrant was matched; automated match calls remain blocked until an exact entrant link exists.
7. **Given** the tournament allows or requires a broadcast image, **When** the player uploads one through the bot, **Then** the image is decoded, validated, normalized, stored as a Workspace-owned asset, and attached to that player without using an undisclosed global AI key.
8. **Given** an image is optional and the player has an existing valid image, **When** they register, **Then** they can keep it, replace it, or skip according to the configured policy; a required image cannot be skipped.
9. **Given** Challonge does not provide the Start.gg bio method, **When** a player registers, **Then** the tournament's configured exact Gamertag policy remains available: their Discord name must equal the registered Gamertag or the bot changes their server nickname to that Gamertag, with collisions sent to organizer review.
10. **Given** provider entrant data changes during the registration window, **When** synchronization or an explicit recheck runs, **Then** affected enrollment states update idempotently and removed entrants are marked for review without deleting their Discord identity or image.
11. **Given** the organizer opens registration status, **When** player records exist, **Then** they can filter provider-confirmed, identity-pending, image-pending, ready, rejected, and needs-review states and see a safe corrective action for each.
12. **Given** the organizer knows a participant's Discord ID, **When** they add or edit it from that entrant's row, **Then** the system validates the ID and guild membership, prevents conflicting links, records the manual link, and uses it for future tournament Discord actions.

### Edge Cases

- A Start.gg Event slug identifies an Event that is archived, completed, inaccessible to the connected account, or belongs to a different tournament than the displayed parent.
- A tournament-level Start.gg link has zero, one, or many Events; zero blocks activation, one can be preselected and confirmed, and many require an explicit selection.
- A provider returns contradictory, stale, or timezone-free metadata; the wizard identifies its source and freshness and does not silently reinterpret it.
- The same external tournament or Event is connected in two workspaces; local configuration remains separate while shared external mutations and conflicts are disclosed.
- OAuth returns after the draft session has expired or in another browser; the connection result remains recoverable without leaking state between users or workspaces.
- An uploaded logo is invalid, too large, removed, or already referenced by another tournament or overlay.
- Discord installation succeeds but the bot is later removed, its role is moved below a required role, a channel is deleted, or a user closes direct messages.
- A template references an unknown variable, produces an empty message, or exceeds the destination's message limit.
- An AI key is valid but has no access to the selected model, reaches provider usage limits, expires during a request, or is replaced while another request is active.
- The selected AI provider changes while both providers have stored keys; usage and test status remain attributable to the correct connection.
- The workspace encryption service is unavailable; secret changes and AI use fail closed while non-secret draft editing remains available.
- A user loses permission while the wizard is open; the next protected action is rejected and no stale session can write integration changes.
- Automatic match dispatch is requested while identities are unverified, provider data is stale, a match is on stream, or the configured automatic-call stop threshold has been reached.
- A Discord attendance timeout expires; the system reminds and escalates but does not automatically disqualify a player.
- The remote bracket starts, finishes, or changes after review but before activation; readiness must be refreshed before any state-dependent action.
- A Start.gg or Challonge start request times out after the provider may have accepted it; the outcome becomes unknown and must be reconciled from a fresh provider read before any retry.
- Start.gg synchronization and a Dashboard action observe or create the same `CALLED` transition concurrently; one durable Discord call is created for that match occurrence and duplicate observations do not create another message.
- A player starts verification shortly before registration closes; the challenge expires at the earlier of its normal expiry and the tournament closing time.
- A player changes their Start.gg bio after successful verification; the stored proof remains the verification event, while Event membership is checked independently on later synchronization.
- Two entrants have the same Gamertag, normalized names collide, or a player changes Gamertag; the bot does not guess and sends the conflict to organizer review.
- A provider entrant is removed after Discord confirmation; the enrollment becomes `needs_review` without deleting the reusable identity link or image.
- The bot receives a registration interaction in the wrong guild, channel, or tournament context; it rejects the interaction instead of using a global active tournament.
- An organizer enters a malformed Discord ID, an ID for a user outside the configured guild, a bot account, or an ID already linked to another entrant; the row shows a precise pending/conflict state and does not become ready.
- An organizer edits or removes a manual Discord ID while a match call is already queued or sent; completed delivery history remains unchanged and future actions use the reconciled current link.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a five-step tournament setup flow covering provider and Event, tournament review, Discord, organizer assistant, and final review.
- **FR-002**: The system MUST display the current step and total step count, allow navigation back to completed steps, retain entered values, and clearly mark optional sections.
- **FR-003**: The system MUST save resumable drafts without activating tournament operations and MUST restore the latest authorized draft after navigation, reload, and external authorization redirects.
- **FR-004**: The system MUST isolate every draft, connection, credential, tournament, destination, template, assistant configuration, usage record, and audit event to exactly one workspace.
- **FR-005**: Only members with the required tournament-management permission MAY create or activate a tournament, and only members with the required integration-management permission MAY add, replace, test, disable, or remove credentials.
- **FR-006**: The system MUST support reusable Start.gg and Challonge organizer connections and show connection identity, status, last successful test, and required corrective action without exposing credentials.
- **FR-007**: The system MUST let an organizer select an existing permitted provider connection or initiate a provider connection from the first step.
- **FR-008**: The system MUST accept Start.gg Event URLs and Event slugs as direct Event selectors and MUST preserve the resolved Event identifier as the managed scope.
- **FR-009**: The system MUST require explicit Event selection for a Start.gg tournament with multiple Events and MUST not silently default to the first Event.
- **FR-010**: The system MUST model a Challonge tournament as one managed bracket unless the connected provider explicitly supplies a different scoped structure.
- **FR-011**: The system MUST show a provider-data preview before creating the active local tournament and MUST identify stale, incomplete, incompatible, or inaccessible data.
- **FR-012**: The system MUST persist the selected provider account and exact provider tournament and Event scope as explicit tournament bindings.
- **FR-013**: The tournament review MUST display provider name, Event name, game, scheduled date and time, timezone, provider state, bracket format, synchronization freshness, and the source of each displayed fact when available.
- **FR-014**: The system MUST allow a local display name, short name, logo, and accent color without silently overwriting provider-owned facts.
- **FR-015**: The system MUST expose the reviewed tournament identity, including logo, to authorized Hub and Editor contexts and to the tournament's permitted public overlay projection.
- **FR-016**: Tournament logos MUST be validated, protected from unauthorized access or deletion, and shown with a clear fallback when absent or invalid.
- **FR-017**: For Start.gg, the system MUST show wave readiness as verified enabled, verified disabled, unsupported, or unknown; it MUST not claim to change the provider setting unless that capability and account permission have been verified.
- **FR-018**: The setup flow MUST offer manual and assisted operating presets, show the behaviors included in each preset, and allow tournament-specific overrides under an advanced section.
- **FR-019**: Operating settings MUST include attendance source and duration, reminder behavior, organizer escalation, result approval policy, automatic call enablement, maximum concurrent bot-managed matches, automatic-call stop threshold, and stream-match handling where applicable.
- **FR-020**: The automatic-call stop threshold MUST be described and calculated as a count of unfinished matches rather than remaining players or a bracket label such as Top 8.
- **FR-021**: Automatic disqualification and AI-controlled disqualification MUST remain prohibited; attendance expiration MUST result in notification or escalation for an authorized human decision.
- **FR-022**: The system MUST refuse assisted dispatch when required player identity links, fresh provider state, resolved entrants, or other readiness conditions are missing.
- **FR-023**: Discord setup MUST be optional and MUST support reusable workspace connections, server selection, tournament-specific destinations, moderator or organizer escalation, and permission verification.
- **FR-024**: The system MUST persist an explicit tournament-to-Discord-account binding and MUST not infer a destination from unrelated or legacy global settings.
- **FR-025**: The Discord step MUST support a match destination, organizer escalation destination, moderator role, per-match conversation preference, bot behavior selection, and a testable message preview.
- **FR-026**: The system MUST provide reusable templates for welcome, match call, reminder, result receipt, clarification, and escalation messages, with documented variables and validation.
- **FR-027**: Bot language, response tone, templates, and permitted server-specific identity settings MUST be inheritable from workspace defaults and overridable by tournament without changing other tournaments.
- **FR-028**: The system MUST show player identity-link coverage and a clear fallback for unlinked players or unavailable direct messages before assisted Discord operation is enabled.
- **FR-029**: The organizer assistant step MUST remain optional, and disabling or skipping it MUST leave non-AI bot templates and manual tournament operation functional.
- **FR-030**: Each workspace MUST be able to store its own Gemini credential, OpenAI credential, or both, and MUST select exactly one provider connection for active assistant requests at a time.
- **FR-031**: aiTOB MUST NOT sell, allocate, pool, or represent itself as billing for AI tokens in this Epic; the workspace uses credentials for an account billed directly by the selected AI provider.
- **FR-032**: The system MUST preserve the existing assistant settings and meanings for provider, model, disabled/read-only/propose-only mode, request limit, token limit, context size limit, response size limit, request timeout, and enforced assistant safety policy.
- **FR-033**: Assistant configuration and AI credentials MUST be workspace-scoped rather than service-global, and changes in one workspace MUST NOT alter another workspace.
- **FR-034**: AI credentials MUST be encrypted at rest, accepted only through protected secret inputs, never returned after submission, and excluded from client state, logs, errors, analytics, audit detail, exports, and reusable templates.
- **FR-035**: The system MUST support add, replace, explicit connection test, disable, and remove operations for each workspace AI credential, with audit records that identify actor, workspace, provider, action, and outcome without secret material.
- **FR-036**: A credential replacement MUST take effect for new requests without requiring tournament-by-tournament re-entry and MUST not expose or restore the previous credential.
- **FR-037**: AI connection tests MUST be deliberate user actions, use the selected workspace credential and model, avoid tournament mutations, and return actionable non-secret statuses for invalid key, unavailable model, quota or billing restriction, rate limit, timeout, and provider outage where distinguishable.
- **FR-038**: The assistant MUST attribute usage limits and usage records to the workspace, selected provider, model, tournament, and applicable policy period without storing prompts, responses, or credentials solely for usage accounting.
- **FR-039**: Failure or absence of an AI connection MUST fail only the AI-assisted action and MUST NOT prevent draft editing, provider synchronization, Discord templates, manual calls, manual result reporting, or authorized tournament administration.
- **FR-040**: Existing assistant authorization boundaries MUST remain in force: read-only mode cannot propose actions; propose-only mode can create only supported pending proposals; the assistant cannot approve or execute them.
- **FR-041**: Translation, conversational player assistance, and result understanding MUST be presented as unavailable or future capabilities until their individual end-to-end safety and approval flows are implemented and verified.
- **FR-042**: Any future result-understanding flow MUST produce a reviewable result claim tied to a known match, preserve player Gamertags and numeric scores, request clarification when ambiguous, and require authorized human approval before reporting to a provider.
- **FR-043**: The final step MUST show one consolidated readiness summary with status and an edit action for provider scope, tournament metadata and behavior, Discord when enabled, and AI when enabled.
- **FR-044**: Required readiness failures MUST block activation, while skipped optional services MUST be allowed and clearly summarized.
- **FR-045**: The system MUST distinguish saving a draft, saving a tournament, activating aiTOB management, and starting the remote bracket as separate outcomes.
- **FR-046**: The system MUST offer a remote start action only for a provider and tournament state for which support, credentials, permissions, freshness, and confirmation are all verified.
- **FR-047**: Reusable setup templates MUST exclude provider tournament identifiers, Event identifiers, credentials, dates, player data, connection test details, and other tournament-specific or secret data.
- **FR-048**: Disabling or removing a reusable connection MUST not delete tournament configuration; dependent tournaments MUST display degraded readiness and allow an authorized replacement connection.
- **FR-049**: The system MUST autosave non-secret wizard progress after meaningful changes and visibly report saving, saved, retrying, and failed states without blocking continued local editing.
- **FR-050**: Validation errors MUST preserve entered values, appear beside the affected control and in a navigable summary, and explain how the organizer can correct the issue.
- **FR-051**: All wizard controls and statuses MUST be usable with keyboard and assistive technology, and the layout MUST remain usable on supported mobile and desktop widths.
- **FR-052**: The system MUST record redacted audit events for connection lifecycle changes, tournament binding changes, readiness decisions, activation, and remote start attempts.
- **FR-053**: Legacy service-global AI configuration MUST not silently become a workspace credential; migration or assignment MUST be an explicit audited administrative action, and the legacy source MUST not remain an undisclosed fallback.
- **FR-054**: Legacy global Discord or tournament settings that no longer control runtime behavior MUST not be shown as active wizard settings; retained compatibility values MUST be labeled and migrated explicitly.
- **FR-055**: When Start in wave is verified enabled, or an authorized organizer explicitly confirms it while provider verification is unavailable, the system MUST monitor bracket start and synchronize provider-reported `CALLED` transitions; each synchronized transition MUST enter the same Discord player-call workflow used by an authorized Dashboard transition.
- **FR-056**: Every real transition of a match to `CALLED` MUST create one durable Discord player-call delivery when Discord is enabled and ready, whether the transition originates from Start.gg synchronization or an authorized Dashboard action; duplicate snapshots, concurrent observations, retries, and worker restarts MUST NOT create duplicate deliveries for the same call occurrence.
- **FR-057**: An organizer confirmation of Start in wave MUST record the actor and time, MUST be labeled as organizer-confirmed rather than provider-verified, and MUST be revocable; without provider verification or this explicit confirmation, the system MUST NOT claim that it is monitoring Start-in-wave behavior, while authorized Dashboard calls remain available.
- **FR-058**: Assistant provider, selected connection, model, mode, limits, timeout, and policy MUST form one Workspace-wide configuration used by every tournament in that Workspace; this Epic MUST NOT create tournament-level AI configuration overrides.
- **FR-059**: A customer organizer MUST be able to connect credentials issued for their own Start.gg, Challonge, Gemini, and OpenAI accounts and use those connections to manage their tournaments; the aiTOB Platform Administrator MUST NOT be required to provision those customer credentials.
- **FR-060**: Runtime provider and assistant requests MUST NOT use an aiTOB-owned shared customer credential, token pool, or undisclosed platform fallback when the selected customer connection is missing, invalid, disabled, or expired.
- **FR-061**: Integration accounts MUST be shared Workspace resources: members with integration-management permission MAY create and maintain them, permitted members MAY select or use them, and no member MAY retrieve their stored credential value after submission.
- **FR-062**: A Workspace MUST support multiple Start.gg or Challonge accounts, and each tournament binding MUST select one exact bracket-provider account; the Workspace-wide assistant configuration MUST likewise select one eligible Gemini or OpenAI connection while leaving other saved connections protected and reusable.
- **FR-063**: The Epic MUST implement explicit remote bracket start for both Start.gg and Challonge through provider-authorized, provider-specific operations with fresh preflight, confirmation, idempotency, resulting-state verification, and unknown-outcome reconciliation; `markSetCalled`, browser automation, and undocumented private mutations MUST NOT substitute for a verified Start.gg start contract.
- **FR-064**: The Discord wizard step MUST include a tournament-specific Player Registration section with enablement, destination, opening and closing date/time, timezone, provider-registration policy, image policy, verified role, and player-facing templates.
- **FR-065**: Registration opening and closing times MUST be stored as instants with a display timezone, MUST require opening before closing, and MUST be enforced server-side for every player-initiated start, confirmation, upload, and scheduled transition; authorized organizer corrections such as manual Discord linking MAY occur after close and MUST be audited.
- **FR-066**: Opening and closing a registration window, publishing or disabling its Discord action, reminders, and verified-role changes MUST use durable idempotent jobs scoped to the workspace and tournament so retries and restarts do not duplicate effects.
- **FR-067**: Provider-backed tournaments MUST default to requiring provider registration; an organizer MAY explicitly allow Discord-only enrollment, and the UI MUST explain that unmatched players cannot receive provider-match automation until linked to an exact entrant.
- **FR-068**: Provider confirmation MUST use the selected provider account and exact Event or bracket. When the organizer enables Gamertag verification, the system MUST require an exact documented normalization match between the provider Gamertag and Discord username/server display name, or MUST apply the authorized server nickname change to the selected entrant's Gamertag; fuzzy matching and avatar matching remain prohibited.
- **FR-069**: During the registration window the system MUST synchronize an idempotent entrant snapshot for the exact selected scope, record freshness, update affected enrollments, and provide an authorized explicit Recheck action.
- **FR-070**: Tournament enrollment state MUST be stored separately from reusable Workspace player identity and provider-identity links so verification can be reused while membership, image readiness, and approval are assessed per tournament.
- **FR-071**: Start.gg bio verification MUST be an organizer-selectable optional method. When enabled and used, it MUST use a random, short-lived, one-use, attempt-limited challenge bound to workspace, tournament, exact Event, Discord user, and claimed provider identity; storage and telemetry MUST not retain the plaintext code or fetched bio after verification processing.
- **FR-072**: A previously verified Start.gg identity MAY skip a new ownership challenge, but the system MUST still verify that identity's entrant membership in the newly selected Event before provider-confirming the enrollment.
- **FR-073**: For Challonge, where Start.gg bio verification is unavailable, the system MUST retain the configured exact Gamertag method: require the Discord username/server display name to equal the registered Gamertag or apply the authorized server nickname change to that Gamertag; duplicate/colliding matches MUST require organizer resolution.
- **FR-074**: When provider registration is optional, the bot MAY create a Discord-only enrollment, but the record MUST remain explicitly unmatched and automated match calls MUST remain blocked for that player until an exact entrant link exists.
- **FR-075**: Each tournament MUST configure its broadcast-image policy as disabled, optional, or required; existing valid Workspace player images MAY be retained or replaced, optional images MAY be skipped, and required images MUST block `ready` status until supplied.
- **FR-076**: Uploaded player images MUST pass deterministic decode, file type, size, dimension, and normalization checks and be stored as Workspace-owned media; mandatory validation MUST NOT silently call a global Gemini/OpenAI key or consume the organizer assistant credential, and any optional AI moderation requires a separate explicit privacy and billing contract.
- **FR-077**: Verification begun outside the registration window MUST be rejected, and an in-progress challenge MUST expire no later than registration close; closing the window MUST NOT erase completed enrollments.
- **FR-078**: The organizer MUST be able to view counts, filter enrollment states, inspect non-secret reason codes and freshness, recheck provider membership, approve a supported manual link, request image correction, reject, or reopen registration according to permission.
- **FR-079**: Enrollment states MUST include at least `awaiting_provider`, `awaiting_discord_link`, `awaiting_identity`, `awaiting_image`, `awaiting_review`, `ready`, `rejected`, and `needs_review`; provider removal or contradictory evidence MUST move the enrollment to review without deleting its reusable identity or media.
- **FR-080**: Discord registration interactions MUST resolve an explicit workspace, tournament, guild, and destination binding; the bot MUST NOT route registration through a process-global active workspace or by scanning unrelated tournaments.
- **FR-081**: A ready enrollment MUST link one Discord identity to at most one entrant in the tournament, and one entrant to at most one Discord identity, with transactional uniqueness and safe organizer conflict resolution.
- **FR-082**: Registration audits MUST record actor, origin, tournament, provider scope, state transition, and safe reason code while excluding challenge plaintext, fetched profile bio, image bytes, provider credentials, and Discord message content.
- **FR-083**: Registration failure, expiration, provider removal, missing image, or attendance timeout MUST NOT automatically disqualify or mutate the provider entrant; organizers receive review and escalation actions.
- **FR-084**: Registration copy MUST include open, closed, awaiting-provider, verification-code, image-required, ready, correction, and rejection messages using the same validated template and locale system as other bot messages.
- **FR-085**: Across aiTOB domain models, API contracts, imports, exports, editor bindings, bot messages, and user-facing labels, the canonical player fields MUST be `prefix` and `gamertag`; legacy player `team` and `name` fields MUST be migrated or exposed only as explicitly deprecated compatibility aliases.
- **FR-086**: Provider adapters MUST map a provider's team, sponsor, clan, or equivalent player prefix into `prefix`, and its entrant tag or competitive display name into `gamertag`, without combining the two into one ambiguous value.
- **FR-087**: The registration configuration MUST let the organizer choose exact Gamertag matching, bot-managed server nickname change, or either method; Start.gg bio verification MUST be a separate optional additional method and MUST not appear for Challonge.
- **FR-088**: The provider participant list for the selected tournament or Event MUST let an authorized organizer add, replace, or remove a participant's Discord ID without editing provider-owned participant data.
- **FR-089**: A manual Discord ID link MUST validate a canonical Discord snowflake format, resolve the user against the configured guild, reject bot/service accounts, and expose `linked`, `not_in_guild`, `invalid`, or `conflict` status without exposing unrelated guild-member data.
- **FR-090**: Within a tournament, one Discord ID MUST link to at most one provider entrant and one entrant MUST have at most one active Discord ID; create, replace, unlink, conflict resolution, actor, time, and safe reason MUST be transactional and audited.
- **FR-091**: A validated manual Discord ID link MUST take precedence for future registration, role, reminder, and match-call routing; changing or removing it MUST reconcile queued future effects without rewriting completed delivery history.

### Scope Boundaries

- This Epic includes the complete wizard, resumable drafts, reusable connections and templates, tournament branding bindings, tournament-scoped Discord player registration and provider-roster synchronization, Discord onboarding and readiness, workspace-owned Gemini/OpenAI credentials, and migration from current settings.
- This Epic preserves the current organizer assistant behavior and permission boundary; it does not add autonomous AI actions.
- Automated translation, player conversation, image or text result extraction, opponent confirmation, and dispute adjudication are specified as future-safe contracts but are not required to ship this Epic.
- Remote bracket start is required for both Start.gg and Challonge. Shipping this Epic requires a documented or provider-authorized and tested Start.gg start operation; absence of that contract is an external blocking dependency, not permission to simulate the operation or claim success.
- A dedicated customer-owned Discord bot application is outside the initial managed-bot path; reusable aiTOB bot installation and permitted server-specific identity are included.
- AI provider prices, credits, resale, and payment collection are outside scope.

### Key Entities

- **Tournament Setup Draft**: Workspace-owned, resumable answers for the five steps, including completion and validation status but excluding raw credentials.
- **Integration Account**: A reusable workspace-owned identity for Start.gg, Challonge, Discord, Gemini, or OpenAI, with provider, display identity, enabled state, and non-secret health metadata.
- **Integration Credential**: An encrypted secret belonging to one integration account; its plaintext is accepted for change operations and never returned.
- **Tournament Binding**: The explicit relationship between a local tournament, its provider account, external tournament, exact Event or bracket scope, Discord account, and selected destinations.
- **Tournament Brand**: Local presentation identity containing display name, short name, logo, and accent color, shared by permitted Hub, Editor, and overlay views.
- **Operating Profile**: Reusable defaults and tournament overrides for attendance, reminders, escalation, result approval, dispatch, concurrency, the automatic-call stop threshold, and stream behavior.
- **Bot Experience Profile**: Reusable defaults and tournament overrides for language, tone, templates, supported variables, per-match conversations, and permitted server identity.
- **Tournament Registration Configuration**: Tournament-specific window, timezone, destination, provider-registration requirement, image policy, role, and message behavior.
- **Tournament Player Enrollment**: The tournament-specific state joining one Discord player, an optional exact provider entrant, provider-membership evidence, image readiness, review status, and timestamps.
- **Player Identity**: A Workspace-owned player record whose canonical competitive fields are `prefix` and `gamertag`; Discord and provider identifiers remain separate identity attributes.
- **Provider Identity Verification Challenge**: A short-lived, hashed, one-use ownership challenge bound to one Workspace, tournament, Event or bracket, Discord user, and claimed provider identity.
- **AI Assistant Configuration**: One Workspace-owned configuration, shared by all tournaments in that Workspace, containing provider selection and the existing model, mode, request, token, context, response, timeout, and policy settings.
- **Connection Health**: Non-secret configured, tested, degraded, disabled, or unknown state with timestamps and actionable failure category.
- **Readiness Check**: A time-stamped assessment of required and optional setup conditions used before activation or a supported remote action.
- **Usage Record**: A workspace-, provider-, model-, and tournament-attributed reservation and outcome used to enforce configured limits without retaining secret content.
- **Setup Template**: Reusable non-secret preferences that can seed a later tournament wizard.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 90% of test organizers complete a standard tournament setup with an existing provider connection in 5 minutes or less without assistance.
- **SC-002**: In usability testing, at least 95% of organizers selecting a Start.gg Event slug activate the intended Event on the first attempt, with zero silent first-Event substitutions.
- **SC-003**: 100% of saved tournament bindings identify one workspace, one provider account, one external tournament, and one explicit Event or bracket scope before activation.
- **SC-004**: 100% of AI credential read responses, user-visible errors, audit records, exports, and reusable templates contain no recoverable credential value.
- **SC-005**: In cross-workspace acceptance testing, zero assistant requests, settings changes, usage records, or connection tests use another workspace's credential or configuration.
- **SC-006**: An authorized workspace owner can add or replace a Gemini or OpenAI credential and obtain a clear connection-test result in under 60 seconds for 95% of provider responses that complete normally.
- **SC-007**: Switching between previously saved Gemini and OpenAI connections requires no credential re-entry and retains all existing assistant settings in 100% of tested switches.
- **SC-008**: In 100% of invalid-key, exhausted-quota, rate-limit, timeout, and provider-outage tests, the AI action fails without interrupting manual tournament operation or non-AI Discord templates.
- **SC-009**: 100% of activation attempts with a required readiness failure are blocked with a direct edit path, while skipped optional Discord or AI steps do not block activation.
- **SC-010**: No tested attendance timeout causes automatic disqualification; every timeout results only in configured reminders and human escalation.
- **SC-011**: At least 90% of usability-test participants correctly distinguish provider facts, local presentation overrides, saving, aiTOB activation, and remote bracket start without facilitator explanation.
- **SC-012**: All five steps, validation messages, status changes, and review edit links can be completed by keyboard at desktop and mobile-supported widths without loss of information or horizontal page scrolling.
- **SC-013**: Returning from provider or Discord authorization, reloading, or resuming on the same authorized account restores 100% of the latest successfully saved non-secret draft fields.
- **SC-014**: A reused setup template pre-fills only approved preferences and includes zero credentials, tournament identifiers, dates, player records, or prior connection-test details.
- **SC-015**: In disposable-provider acceptance, one confirmed start request for each of Start.gg and Challonge produces at most one remote start effect, verifies the resulting bracket state, and classifies a timeout or uncertain response for reconciliation before any retry.
- **SC-016**: With Discord enabled and ready, 100% of tested real `CALLED` transitions from either Start.gg synchronization or an authorized Dashboard action create one intended player-call delivery per match occurrence, while concurrent duplicate observations and worker restart create no additional delivery.
- **SC-017**: 100% of tested player-initiated registration starts, confirmations, and uploads outside the configured server-enforced window are rejected without creating a ready enrollment; audited organizer correction remains available.
- **SC-018**: When provider registration is required, 100% of ready enrollments resolve to an entrant in the exact selected Event or bracket and satisfy the configured exact Gamertag/nickname or optional Start.gg bio method; all duplicate or normalized-name collisions require review.
- **SC-019**: In normal provider operation, 95% of entrant additions or removals observed by the synchronization worker appear in the organizer registration view within two minutes, and an explicit Recheck returns a fresh classified result.
- **SC-020**: Duplicate provider snapshots, Discord interactions, scheduled jobs, and worker restarts create zero duplicate enrollments, announcements, role grants, or verification completions.
- **SC-021**: In cross-workspace and two-tournament tests, zero registration interaction, identity proof, entrant link, player image, or roster update is read from or written to the wrong workspace or tournament.
- **SC-022**: 100% of accepted player images pass deterministic decode and configured file constraints, and default registration completes without any undisclosed AI-provider request.
- **SC-023**: At least 90% of player usability-test participants complete the configured Gamertag/nickname flow, optional Start.gg bio verification when enabled, and image choice within three minutes without organizer help.
- **SC-024**: In schema, API, UI, bot, import/export, and Editor contract tests, 100% of canonical player projections use `prefix` and `gamertag`; legacy `team` and `name` are accepted only at documented migration boundaries.
- **SC-025**: In manual-link acceptance tests, 100% of malformed, bot-account, wrong-guild, and duplicate Discord IDs are prevented from becoming ready, while a valid guild member can be linked, edited, and unlinked from the entrant row with one audit record per change.

## Assumptions

- The workspace is the customer billing and security boundary; its owner pays Gemini or OpenAI directly under the terms of their own provider account.
- “Platform Administrator” means the operator of aiTOB. “Customer organizer” means a user of aiTOB who connects their own external accounts and organizes tournaments; these roles are distinct.
- A workspace may save both Gemini and OpenAI credentials, but the existing assistant chooses one provider and model for active requests at a time.
- Existing assistant modes and limits remain available; this Epic changes their ownership from service-global to workspace-scoped and adds credential connection management.
- Assistant configuration has no tournament-level override in this Epic; changes affect new assistant requests for every tournament in the Workspace.
- Customer organizers who receive integration-management permission may add or maintain shared connections; the permission is enforced independently from the aiTOB Platform Administrator role.
- A Workspace may keep multiple accounts for a provider. Tournament bindings select an exact Start.gg/Challonge account, while the one Workspace-wide AI configuration selects one eligible Gemini/OpenAI connection.
- Credentials are reusable across tournaments in the same workspace and are never copied into tournament drafts or templates.
- Start.gg Event slugs remain supported as the direct and preferred way to select a specific Event.
- Challonge is treated as one bracket for wizard selection under the current provider model.
- Discord and AI are optional. The provider scope, reviewed tournament identity, and required local operating settings are mandatory before activation.
- Discord player registration is optional at tournament level. When enabled, its schedule and policies are tournament-specific even though verified player identities and valid images may be reused inside the same Workspace.
- Exact Gamertag matching or the organizer-approved Discord server nickname change is an available registration method for both providers. Start.gg bio verification is an optional additional method; Challonge retains the Gamertag method because it has no equivalent bio flow.
- Safe assisted defaults use reminders and organizer escalation; manual authorized disqualification remains outside the wizard's automatic behavior.
- Provider data may be incomplete. Local presentation overrides fill display needs while provider facts retain their source and do not get silently overwritten.
- The current workspace isolation, authenticated encryption, audit, role, image, overlay, and provider freshness foundations remain dependencies of this Epic.
