# Feature Specification: Persistent Player Profiles and Tournament Overrides

**Feature Branch**: `005-player-profiles`

**Created**: 2026-09-22

**Status**: Draft

**Input**: User description: "Create a modern, modular player-profile foundation that preserves reusable player data, keeps tournament-specific overrides separate, and exposes future OBS data hooks without changing live broadcast bindings now."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reuse a confirmed player profile (Priority: P1)

An organizer links a tournament entrant to an existing player once and immediately sees that player's saved presentation identity, including their approved avatar, without uploading it again for every tournament.

**Why this priority**: This removes the immediate duplicate-upload problem while preserving the organizer's authority to confirm the entrant-to-player association.

**Independent Test**: Link a known player to an entrant in a new tournament and verify their approved profile image and identity appear in the participant review without creating a tournament override.

**Acceptance Scenarios**:

1. **Given** a confirmed player with an approved avatar, **When** an organizer links them to a new entrant, **Then** the participant review uses the saved avatar and profile presentation without another upload.
2. **Given** a provider refresh changes its own profile image, **When** the entrant is linked to a confirmed local player, **Then** the approved local avatar remains the preferred presentation image.
3. **Given** no confirmed player link exists, **When** the participant review is opened, **Then** provider data remains visible as a clearly labeled fallback.

---

### User Story 2 - Keep tournament choices local (Priority: P1)

An organizer can choose a character, display name, or image for a specific tournament entrant without accidentally changing that player's reusable profile or another tournament.

**Why this priority**: A character choice and broadcast presentation can vary by event; entrant identifiers are not a stable player identity.

**Independent Test**: Give one linked player different character choices in two events and verify each participant review resolves its own choice while the reusable profile remains unchanged.

**Acceptance Scenarios**:

1. **Given** a linked player with no entrant-specific choice, **When** the organizer selects a character for one event, **Then** only that entrant/event presentation changes.
2. **Given** a saved entrant-specific character, **When** the participant review is reloaded, **Then** the selected character and its image are shown.
3. **Given** an organizer resets a tournament override, **When** the reset completes, **Then** the participant falls back to their reusable profile and then provider data without deleting the player profile.

---

### User Story 3 - Prepare presentation data for future surfaces (Priority: P2)

An organizer can rely on one documented player-presentation projection for participant review and future overlay consumers, while current OBS behavior and live match bindings remain unchanged.

**Why this priority**: It provides a durable integration seam without risking a live broadcast regression during the profile work.

**Independent Test**: Request the player-presentation projection for a linked entrant and verify that it reports the resolved values and provenance, while existing OBS output remains byte-for-byte compatible for an unchanged match.

**Acceptance Scenarios**:

1. **Given** a linked entrant, **When** a presentation consumer requests their profile hook, **Then** it receives a stable, versioned projection with source/provenance for every resolved field.
2. **Given** an existing live station, **When** profile foundations are introduced, **Then** no automatic update changes its active match, broadcast state, overlay URL, or provider command.
3. **Given** another workspace, **When** it requests a profile or hook, **Then** it cannot read or infer profile data from this workspace.

---

### Edge Cases

- A provider entrant has no confirmed player link: display provider snapshot data and offer a safe link action; never infer a persistent identity solely from a similar display name.
- A player participates in more than one game: retain game-specific choices separately, and do not show a character from one game as a choice in another.
- A provider account, Discord account, or entrant is relinked: retain audit history and require an explicit organizer confirmation before the new identity becomes the presentation source.
- A profile image is unavailable or deleted: preserve the existing asset safety rules and fall back to the provider image or placeholder without breaking participant review.
- A legacy entrant override lacks tournament or event scope: migrate it conservatively to the originating scope when known; otherwise retain it as a legacy record requiring organizer review.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST maintain a reusable, workspace-owned player profile separately from provider entrants and tournament-specific presentation choices.
- **FR-002**: The system MUST preserve an explicit, organizer-confirmed relationship between a player profile and each provider entrant in a tournament.
- **FR-003**: The participant review MUST resolve presentation values in this order: entrant/event override, confirmed player profile, provider snapshot, then placeholder.
- **FR-004**: The participant review MUST show a saved avatar from the confirmed player profile without requiring it to be copied or uploaded again for each entrant.
- **FR-005**: The system MUST retain game-specific player preferences separately from reusable identity data and validate tournament character choices against the selected event's game catalog.
- **FR-006**: The system MUST scope entrant/event overrides by workspace, provider, tournament, event or bracket scope, and entrant identity so that one tournament's choice cannot affect another.
- **FR-007**: The system MUST expose a read-only, versioned player-presentation hook containing resolved display data and per-field provenance for future consumers.
- **FR-008**: The first delivery of the hook MUST NOT change live station ownership, broadcast state, current OBS response fields, public overlay links, or provider commands.
- **FR-009**: The system MUST use current provider data for membership and bracket facts, while a confirmed local profile remains authoritative for organizer-approved presentation fields.
- **FR-010**: The system MUST keep all profile, identity-link, override, asset, and hook data isolated to its owning workspace and retain a safe audit trail for organizer link changes.
- **FR-011**: The system MUST return saved character name, identifier, and image data consistently to the participant review.

### Key Entities *(include if feature involves data)*

- **Player Profile**: The reusable, workspace-owned player identity and organizer-approved presentation data.
- **Provider Identity**: A confirmed association between a player profile and a provider account; it supports safe suggested links but never silently replaces an organizer decision.
- **Game Profile**: A player's game-specific data and defaults, such as game account identifiers and preferred characters.
- **Tournament Entrant Link**: The confirmed relationship between one provider entrant in one tournament and one player profile.
- **Tournament Entrant Override**: A presentation decision that applies only to one entrant in one event or bracket.
- **Player Presentation Hook**: A read-only resolved representation for the participant review and future presentation consumers, including the source of each value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An organizer can link a known player to a new entrant and see the saved profile image in participant review in under 30 seconds, without uploading an image.
- **SC-002**: A character selected for one entrant/event remains visible after reload and does not appear for the same player in a different game or event unless explicitly chosen there.
- **SC-003**: All presentation fields returned by the player hook identify whether their value came from an override, player profile, provider snapshot, or placeholder.
- **SC-004**: Existing live station and overlay behavior remains unchanged for 100% of regression scenarios that do not opt into a future hook consumer.
- **SC-005**: A user in one workspace cannot retrieve another workspace's profile, identity link, override, or presentation hook in authorization tests.

## Assumptions

- The existing `players` records are the migration source for reusable player profiles; no provider data is deleted during this work.
- The first release provides the foundation, participant-review integration, and a read-only presentation hook; it does not add a public player directory, social discovery, or a new live OBS binding.
- A Discord or provider identity is reusable only inside its workspace. Cross-workspace sharing requires a future explicit consent and tenancy design.
- Existing validated image storage and session authorization remain the only permitted asset and authentication paths.
- Provider snapshots are refreshed per tournament for provider-owned membership and bracket data; Discord and Start.gg are not scraped as replacements for a confirmed local profile.
