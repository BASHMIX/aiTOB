# Feature Specification: AI Tournament Organizer Platform

**Feature Branch**: `001-define-tournament-bot`

**Created**: 2026-05-16

**Status**: Draft

**Input**: User description: "Define what are we building — updated from phased implementation plan"

## Clarifications

### Session 2026-05-16

- Q: What happens when a player does not respond to the ready check within a time limit? → A: Two-stage timeout — warn at 3 min, auto-DQ at 5 min, with admin notification.
- Q: How is Admin Hub access secured? → A: Single shared password set in configuration.
- Q: Does the system support one or multiple concurrent tournaments? → A: Multiple concurrent tournaments; each managed via a separate Hub tab/instance with a tournament selector.
- Q: What happens if a player abandons the registration flow midway? → A: Partial progress is saved; incomplete registrations are purged after the event registration deadline ends.
- Q: How does the system handle a double-forfeit where neither player shows up? → A: Auto double-DQ — both players are DQ'd after the ready-check timeout, bracket advances, Start.gg updated.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Player Registration via Discord (Priority: P1)

As a tournament player, I want to register for the tournament through Discord by linking my Start.gg account, providing my CFN ID, choosing my language, and uploading an avatar — so that I am fully enrolled and ready to be matched.

**Why this priority**: Registration is the prerequisite for all tournament activity. No players means no matches.

**Independent Test**: Create a dummy tournament, have two Discord accounts register via the bot's DM prompts, and verify their profiles (Start.gg link, CFN ID, language, avatar) appear correctly in the database.

**Acceptance Scenarios**:

1. **Given** a player clicks the "Register" button in a Discord channel, **When** they complete the DM flow (Start.gg linking, language selection, CFN ID, avatar upload), **Then** their profile is saved in the database and synced with Start.gg.
2. **Given** a player uploads an avatar during registration, **When** the image fails quality checks (dimensions/clarity) or AI safety checks (prohibited content), **Then** the bot prompts them to upload a valid image before proceeding.
3. **Given** a player has already registered, **When** they attempt to register again, **Then** the system informs them they are already enrolled and offers to update their profile.

---

### User Story 2 - Automated Match Coordination & AI Refereeing (Priority: P1)

As a tournament player, I want the system to automatically create a Discord thread for my match, prompt both players for a ready check, and use an AI referee to verify our reported scores — so that matches progress quickly without waiting for a human admin.

**Why this priority**: This is the core automation loop. Without it, every match requires manual admin intervention, defeating the purpose of the platform.

**Independent Test**: Create a mock tournament on Start.gg, advance the bracket to generate a match, verify a Discord thread is created with both players, complete a ready check, report agreeing scores, and confirm Start.gg reflects the result within 5 seconds.

**Acceptance Scenarios**:

1. **Given** a match is marked as ready on Start.gg, **When** the system detects it, **Then** a Discord thread is created for the two matched players.
2. **Given** both players are in a match thread, **When** they are prompted with a ready check, **Then** they must confirm readiness before score reporting begins.
3. **Given** two players report agreeing scores (e.g., "I won 2-1" and "he won 2-1"), **When** the AI referee verifies agreement, **Then** the match is completed, scores are reported to Start.gg, and the thread is locked.
4. **Given** two players report conflicting scores, **When** the AI referee detects the mismatch, **Then** the match is flagged as "Conflict", an admin is pinged in the thread, and the match is highlighted in the Admin Hub.
5. **Given** a player has not confirmed readiness, **When** 3 minutes elapse, **Then** the bot sends a warning message in the thread. **When** 5 minutes elapse without confirmation, **Then** the non-responding player is auto-DQ'd, the opponent advances, and an admin is notified.
6. **Given** neither player confirms readiness, **When** the 5-minute timeout expires for both, **Then** both players are auto-DQ'd, the result is reported to Start.gg as a double-DQ, and the bracket advances.

---

### User Story 3 - Admin Hub Real-Time Monitoring (Priority: P2)

As a tournament admin, I want a web dashboard that shows real-time match statuses, bot health, player conflicts, and system activity — so that I can monitor the tournament and intervene only when needed.

**Why this priority**: Admins need visibility and manual override capabilities. The dashboard is the control center for the entire event.

**Independent Test**: Open the Hub, mock match events from the backend, verify the UI updates within 1 second, simulate a bot heartbeat failure and confirm "Offline" status appears within 10 seconds.

**Acceptance Scenarios**:

1. **Given** a user navigates to the Admin Hub URL, **When** they have not authenticated, **Then** they are prompted for the shared password before accessing any Hub functionality.
2. **Given** the Admin Hub is open, **When** a match state changes (created, completed, conflict), **Then** the dashboard reflects the change immediately without a page reload.
3. **Given** the Discord bot stops sending heartbeats, **When** 10 seconds pass, **Then** the Hub displays the bot's status as "Offline".
4. **Given** a match is flagged as "Conflict", **When** an admin opens the Hub, **Then** the conflict is prominently displayed with options to force a score, disqualify a player, or reassign the match.
5. **Given** an admin wants to override a match result, **When** they use the Hub controls to force a score or DQ a player, **Then** the change is applied to the local database and synced to Start.gg.

---

### User Story 4 - AI Admin Assistant (Priority: P3)

As a tournament organizer, I want to type natural language commands into the Hub to quickly query match statuses, fetch player info, or trigger Discord announcements — so I can manage the event faster than navigating menus.

**Why this priority**: Streamlines admin tasks but is a quality-of-life enhancement on top of the manual controls.

**Independent Test**: Type "Who is currently playing?" in the agent chat and verify it returns the correct list of active matches. Type "announce next round in 5 minutes" and verify the message posts to Discord.

**Acceptance Scenarios**:

1. **Given** an admin types "announce that the next round starts in 5 minutes", **When** they submit, **Then** the AI agent formats and posts the announcement to the public Discord channel.
2. **Given** an admin asks for the status of a specific player, **When** the AI processes the query, **Then** it returns the player's CFN ID, Start.gg status, and current match.
3. **Given** an admin types a structured command like `msg <P1> vs <P2>`, **When** the system processes it, **Then** a formatted match call is sent to the public Discord channel.

---

### User Story 5 - OBS Stream Overlay System (Priority: P3)

As a tournament streamer, I want customizable OBS-compatible overlays that display live match information, player avatars, and scores — so that the broadcast looks professional and updates automatically.

**Why this priority**: Essential for streamed events but not required for the tournament itself to function.

**Independent Test**: Open the OBS overlay URL in a browser, start a match, and verify the overlay displays both players' names, avatars, and scores with live updates.

**Acceptance Scenarios**:

1. **Given** a match is active, **When** the OBS overlay page is loaded, **Then** it displays both players' names, avatars, and current scores.
2. **Given** a match score is updated, **When** the overlay receives the update, **Then** the displayed score changes immediately without a page reload.
3. **Given** an admin uses the Overlay Editor in the Hub, **When** they reposition or resize overlay elements, **Then** the changes are reflected in the OBS source.

---

### Edge Cases

- What happens when a player disconnects mid-match and stops responding in the Discord thread? *(Resolved: Two-stage timeout — warning at 3 min, auto-DQ at 5 min, admin notified.)*
- How does the system handle Start.gg API rate limits (80 req/60s) or complete outages during a live tournament?
- What happens if the AI referee misinterprets a chat message (e.g., a player jokingly says "he won 10-0")?
- What happens if a player abandons the registration flow midway (e.g., provides CFN ID but never uploads an avatar)? *(Resolved: Partial progress is saved; incomplete registrations are purged after the event registration deadline ends.)*
- How does the system handle a double-forfeit where neither player shows up? *(Resolved: Auto double-DQ — both DQ'd after timeout, bracket advances, Start.gg updated.)*
- What happens if the Admin Hub loses its WebSocket connection to the backend? *(Resolved: The React client implements graceful exponential backoff reconnection, ensuring state isn't lost and avoiding race conditions like `ECONNABORTED` during backend reloads.)*
- How are connection tokens (Start.gg, Discord) managed? *(Resolved: Tokens are stored dynamically in a `global_settings` database table to allow live updates without restarting the backend, gracefully falling back to `.env` if missing.)*

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST poll or receive webhooks from Start.gg to detect bracket state changes and match readiness.
- **FR-002**: System MUST report match results back to Start.gg within 5 seconds of score verification.
- **FR-003**: System MUST host a Discord bot that handles registration DMs, creates match threads, and reads thread messages.
- **FR-004**: System MUST support a multi-step registration flow: Start.gg linking → language selection → CFN ID → avatar upload (with quality and AI safety validation).
- **FR-005**: System MUST implement an AI referee that reads match thread chat history, extracts agreed scores, and detects conflicts with >95% accuracy.
- **FR-006**: System MUST provide a web-based Admin Hub with real-time match status, bot health monitoring, and manual override controls.
- **FR-007**: System MUST allow admins to force scores, disqualify players, reopen matches, and reset match state from the Hub.
- **FR-008**: System MUST support a natural language AI agent in the Hub that can query matches, fetch player info, and post Discord announcements.
- **FR-009**: System MUST support structured admin commands (`msg`, `announce`, `call_match`) for instant execution.
- **FR-010**: System MUST provide OBS-compatible overlay pages with live match data and a visual editor for customization.
- **FR-011**: System MUST implement a heartbeat system where the bot reports its status every 10 seconds; the Hub MUST display "Offline" if the heartbeat is missed.
- **FR-012**: System MUST stream all bot activity (player notifications, API errors, thread creation) to a "Bot Feed" panel in the Hub.
- **FR-013**: System MUST handle Start.gg API rate limits gracefully (max 75 requests per 60 seconds) with retry/backoff strategies.
- **FR-014**: System MUST support bilingual interaction (Arabic and English) based on the player's language preference.
- **FR-015**: System MUST implement a two-stage ready-check timeout: a warning at 3 minutes and an auto-DQ of the non-responding player at 5 minutes, with admin notification upon auto-DQ.
- **FR-016**: System MUST protect the Admin Hub behind a single shared password configured in the application settings; unauthenticated users MUST NOT access any Hub functionality.
- **FR-017**: System MUST support multiple concurrent tournaments; the Admin Hub MUST provide a tournament selector so each tab/instance can manage a different active event independently.
- **FR-018**: System MUST save partial registration progress so players can resume later; incomplete registrations MUST be automatically purged after the event's registration deadline has passed.
- **FR-019**: System MUST handle double-forfeits by auto-DQ'ing both players after the ready-check timeout expires for both, reporting the result to Start.gg, and advancing the bracket.

### Key Entities

- **Player**: Registered user. Attributes: Discord ID, Start.gg ID, Start.gg Tag, CFN ID, preferred language (Arabic/English), avatar image, registration status (pending/complete). Pending registrations are purged after the event registration deadline.
- **Match (Set)**: A tournament bout. Attributes: Set ID, Player 1 ID, Player 2 ID, State (waiting, called, in-progress, completed, conflict, DQ), Thread ID, Score, Winner ID.
- **Event/Tournament**: The Start.gg tournament instance being managed. Attributes: Tournament slug, Event ID, active state. The system supports multiple concurrent events; each Hub tab scopes to one selected tournament.
- **Overlay**: Visual configuration for OBS. Attributes: Element positions, sizes, styles, data bindings.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 80% of tournament matches are fully automated without any admin intervention required.
- **SC-002**: Match results are reflected on the Start.gg bracket within 5 seconds of the players agreeing in the Discord thread.
- **SC-003**: The Admin Hub loads and reflects the latest state within 1 second.
- **SC-004**: The AI referee accurately extracts the correct score from standard player reports (e.g., "I won 2-1", "ggs 0-2") with >95% accuracy.
- **SC-005**: Players complete the full registration flow in under 3 minutes.
- **SC-006**: Admins can resolve a conflict (review + override) in under 30 seconds using the Hub controls.

## Phased Delivery Plan

The platform is delivered in 6 sequential phases, each a self-contained Spec Kit cycle:

| Phase | Name                            | Priority | Depends On    |
| ----- | ------------------------------- | -------- | ------------- |
| 1     | Setup & Scaffolding             | Prereq   | —             |
| 2     | Foundational Infrastructure     | Prereq   | Phase 1       |
| 3     | Player Registration Bot (US1)   | P1       | Phase 2       |
| 4     | Match Coordination & AI Ref (US2)| P1       | Phase 3       |
| 5     | Admin Web Dashboard (US3)       | P2       | Phase 4       |
| 6     | AI Admin Assistant (US4)        | P3       | Phase 5       |
| 7     | OBS Stream Overlay (US5)        | P3       | Phase 4       |
| 8     | Polish & Validation             | P3       | Phase 4-7     |

**Dependency Graph**:
- Phase 0 → Phase 1 → Phase 2 → Phase 3
- Phase 2 → Phase 4 → Phase 5
- Phases 3 and 4 can be developed in parallel after Phase 2.

## Assumptions

- Users have basic familiarity with Discord and Start.gg.
- Start.gg API will remain largely stable and online during tournament execution.
- The hosting environment supports concurrent asynchronous services (Python backend, Node.js frontend, Discord bot).
- The tournament game is Street Fighter 6 (CFN IDs are specific to Capcom Fighters Network).
- Language support is limited to Arabic and English for v1.
- OBS integration assumes the streamer can add browser sources.
- Avatar quality/safety checks use standard image dimension validation and an AI content moderation service.
- Multiple tournaments can run concurrently; each Admin Hub tab/instance manages one tournament at a time via a selector.
