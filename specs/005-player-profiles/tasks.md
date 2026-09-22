# Tasks: Persistent Player Profiles and Tournament Overrides

**Input**: Design documents in `specs/005-player-profiles/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, and `contracts/player-presentation.md`  
**Tests**: Required by the specification and the repository operating policy. Every database test uses `AITOB_PG_TEST_URL` only.  
**OBS boundary**: No task in this feature may make `broadcast_projection.py`, `/obs/*`, station ownership, `broadcast_state`, or provider commands consume the new hook.

## Phase 1: Setup and Baseline

**Purpose**: Record the current behavior and establish safe boundaries before changing data ownership.

- [X] T001 [P] Capture the current participant/override API response and FNCeSports regression case in `backend/tests/test_participants_overrides_regression.py` using a disposable PostgreSQL database.
- [X] T002 [P] Add the hook non-adoption regression contract to `backend/tests/test_broadcast_projection.py`, asserting existing station/OBS projections do not invoke the new player-presentation domain.
- [X] T003 Document migration inventory, rollback checks, and the exact legacy `player_overrides` ambiguity rule in `specs/005-player-profiles/quickstart.md`.

**Checkpoint**: The current failure modes and the unchanged live-broadcast boundary are executable tests.

---

## Phase 2: Foundational Profile Domain (Blocking Prerequisites)

**Purpose**: Create the scoped PostgreSQL data model and one authoritative, local resolver before any archive or hook consumer is implemented.

**⚠️ CRITICAL**: Complete this phase before starting the scoped override/archive/hook tasks. Do not issue provider calls from a migration or resolver.

- [X] T004 Add PostgreSQL schema/migration definitions for `player_profiles`, `player_provider_identities`, `player_game_profiles`, `player_character_defaults`, and scoped `tournament_entrant_overrides` in `backend/core/database_schema.py`.
- [X] T005 Add transactional backfill, ownership validation, legacy-override review marking, and rollback-safe migration checks in `backend/core/database.py`.
- [X] T006 [P] Define immutable Python request/result models for profile provenance and resolved presentation fields in `backend/core/contracts/player_presentation.py`.
- [X] T007 Implement workspace-scoped repositories for profiles, provider identities, game profiles, character defaults, entrant links, and scoped overrides in `backend/core/player_profiles.py`.
- [X] T008 Implement the pure no-I/O field-precedence resolver (override → confirmed profile/game profile → provider snapshot → placeholder) in `backend/core/player_presentation.py`.
- [X] T009 Add PostgreSQL migration, tenant-isolation, deterministic-backfill, and ambiguous-legacy-review tests in `backend/tests/test_player_profile_migration.py`.
- [X] T010 Add resolver precedence/provenance/no-provider-call tests in `backend/tests/test_player_presentation.py`.

**Checkpoint**: A profile can be read and resolved locally with complete provenance; ambiguous legacy data is never guessed; all migrations and resolver tests pass.

---

## Phase 3: User Story 1 — Reuse a Confirmed Player Profile (Priority: P1) 🎯 MVP

**Goal**: A confirmed entrant link displays the saved profile avatar and identity in Participants without another upload, while unlinked entrants still show the provider fallback.

**Independent Test**: Seed a player with an avatar, link them to an entrant in a new tournament, load the participant projection, and verify profile precedence; repeat with no link and verify provider fallback.

- [X] T011 [P] [US1] Add API-level participant-link/profile-precedence tests in `backend/tests/test_participant_profile_presentation.py`.
- [X] T012 [US1] Extend the existing participant-link read projection to return safe linked-profile presentation fields in `backend/core/database.py`.
- [X] T013 [US1] Return character name, ID, and image in the existing legacy-override compatibility projection in `backend/core/database.py`.
- [X] T014 [US1] Add a server-side participant presentation read service that combines exact entrant snapshot, confirmed link, and legacy/scoped override compatibility in `backend/core/player_presentation.py`.
- [X] T015 [P] [US1] Add typed participant-presentation response shapes and route response models in `backend/api/schemas.py`.
- [X] T016 [US1] Expose the authenticated participant presentation read endpoint without accepting a client workspace ID in `backend/api/routers/players.py`.
- [X] T017 [P] [US1] Add participant presentation types, field-source badges, and profile-avatar fallback helpers in `frontend-react/src/features/players/types.ts` and `frontend-react/src/features/players/presentation.ts`.
- [X] T018 [US1] Update `frontend-react/src/features/hub/components/ParticipantsTable.tsx` to render override → linked profile → provider avatar and show saved character data after reload.
- [X] T019 [US1] Add frontend regression coverage for linked-avatar fallback, character persistence, and unlinked provider fallback in `frontend-react/src/features/hub/components/__tests__/ParticipantsTable.test.tsx`.

**Checkpoint**: User Story 1 is independently complete when the current FNCeSports-style case displays its saved profile image and saved character in Participants, without changing any station or OBS response.

---

## Phase 4: User Story 2 — Keep Tournament Choices Local (Priority: P1)

**Goal**: An organizer can keep a reusable profile but set different event-specific characters or presentation values without cross-tournament leakage.

**Independent Test**: Link one player to entrants in two events, choose different characters, reload both participant views, and verify each choice is isolated while the profile remains unchanged.

- [X] T020 [P] [US2] Add scoped-override isolation, reset, and catalog-validation tests in `backend/tests/test_tournament_entrant_overrides.py`.
- [X] T021 [US2] Implement scoped override create/read/update/delete operations with row-locking and audit metadata in `backend/core/player_profiles.py`.
- [X] T022 [US2] Migrate participant override routes from entrant-global writes to the scoped override service, retaining a read-only legacy compatibility path only until migration completion, in `backend/api/routers/players.py`.
- [X] T023 [US2] Add request validation that binds a character selection to the selected provider tournament/event catalog in `backend/api/routers/players.py`.
- [X] T024 [P] [US2] Implement the tournament-vs-profile choice state and provenance labels in `frontend-react/src/features/players/EntrantPresentationEditor.tsx`.
- [X] T025 [US2] Integrate `EntrantPresentationEditor` into `frontend-react/src/features/hub/components/ParticipantsTable.tsx` with explicit reset-to-profile behavior.
- [X] T026 [US2] Add frontend tests for event isolation, reset behavior, and visible value provenance in `frontend-react/src/features/players/__tests__/EntrantPresentationEditor.test.tsx`.

**Checkpoint**: User Story 2 is independently complete when two event choices for one player do not alter each other, the reusable profile, or any unrelated tournament.

---

## Phase 5: User Story 3 — Player Archive and Future Presentation Hook (Priority: P2)

**Goal**: Organizers can browse a modern player archive and future presentation consumers receive a stable read-only hook, while existing live broadcast consumers remain unchanged.

**Independent Test**: Create a profile with game data, load it through the archive and v1 hook, verify per-field provenance and workspace denial, then compare the existing OBS projection before and after the request.

- [X] T027 [P] [US3] Add v1 hook contract, authorization, provenance, and zero-side-effect tests in `backend/tests/test_player_presentation_hook.py`.
- [X] T028 [US3] Implement the authenticated versioned v1 presentation-hook route and archive-list/detail routes in `backend/api/routers/player_profiles.py`.
- [X] T029 [US3] Register the profile router and permission policy without adding it to any public OBS route in `backend/api/main.py` and `backend/api/auth.py`.
- [X] T030 [P] [US3] Build the archive API client, profile list/card types, and provenance display primitives in `frontend-react/src/features/players/api.ts`, `frontend-react/src/features/players/types.ts`, and `frontend-react/src/features/players/components/FieldSourceBadge.tsx`.
- [X] T031 [P] [US3] Build a compact responsive Player Archive list and player detail/game-preference views in `frontend-react/src/features/players/PlayerArchivePage.tsx` and `frontend-react/src/features/players/components/PlayerProfileDetail.tsx`.
- [X] T032 [US3] Add the authorized archive route/navigation entry in `frontend-react/src/App.tsx` and the relevant Hub navigation component.
- [X] T033 [US3] Add archive and hook frontend tests in `frontend-react/src/features/players/__tests__/PlayerArchivePage.test.tsx` and API integration tests in `backend/tests/test_player_profile_api.py`.

**Checkpoint**: User Story 3 is independently complete when an organizer can inspect a player and game preferences, a secure hook returns versioned provenance data, and OBS remains on its prior projection.

---

## Phase 6: Polish and Cross-Cutting Verification

**Purpose**: Prove migration safety, preserve assets, and prepare an explicit later opt-in path for graphics consumers.

- [X] T034 [P] Add asset-preservation and old-URL/reference regression tests in `backend/tests/test_player_profile_assets.py`.
- [X] T035 [P] Add cross-workspace authorization and concurrent profile/override update tests in `backend/tests/test_player_profile_workspace_security.py`.
- [X] T036 Update implementation and operator notes, including the explicit “hook not connected to OBS yet” boundary, in `README.md` and `specs/005-player-profiles/quickstart.md`.
- [X] T037 Run the focused PostgreSQL suites, `python -m pytest backend/tests -q`, `npm test`, and `npm run build`; record the results in `specs/005-player-profiles/quickstart.md`.
- [X] T038 Review the migration using a disposable copy, verify profile/asset/link counts, and document go/no-go and rollback evidence in `specs/005-player-profiles/quickstart.md`.

**Checkpoint**: Migration, workspace isolation, asset preservation, complete backend suite, frontend tests/build, and unchanged live broadcast behavior are verified.

---

## Dependencies and Execution Order

```text
Phase 1 baseline
    └── Phase 2 profile domain
         ├── US1 participant reuse (MVP)
         ├── US2 scoped overrides (depends on US1 presentation adapter)
         └── US3 archive/hook (depends on Phase 2; may start after T010)
              └── Phase 6 verification
```

- **US1** depends on T004–T010, then T011–T019 run in the listed order where marked.
- **US2** depends on the profile domain and US1's presentation adapter (T014); it must not alter the new hook contract.
- **US3** depends on T004–T010 and can run alongside the latter half of US2 because it owns different API/frontend files. It must never edit `backend/core/broadcast_projection.py`.
- **Phase 6** starts only after the desired user stories are merged into the same branch.

## Multi-Agent Execution Plan

### Foundation ownership

One agent owns T004, T005, T007, and T008 because schema, migration, repository,
and resolver changes share a data contract. A second agent may work in parallel
on T006, T009, and T010 after agreeing the contract fields; they must not edit
the migration files.

### After Phase 2

```text
Agent A — US1 backend: T011–T016
Agent B — US1 frontend: T017–T019 (starts after API response shape is agreed)
Agent C — US3 archive shell: T030–T031 (uses frozen v1 types; no OBS files)
```

### After the US1 presentation adapter

```text
Agent A — US2 backend: T020–T023
Agent B — US2 frontend: T024–T026
Agent C — US3 hook/API: T027–T029, then T032–T033
```

Agents must communicate the final contract shape before a dependent task starts,
run only their focused tests, and avoid editing another agent's owned file. The
integrator owns T034–T038 and resolves migration/API conflicts before the full
suite.

## Implementation Strategy

### MVP first

1. Complete Phases 1 and 2.
2. Complete US1 only.
3. Verify the existing player photo and character are visible in Participants
   without a re-upload and confirm OBS is unchanged.
4. Deploy/demo the MVP before starting archive scope.

### Incremental delivery

1. Add US2 for safe per-tournament/event choices.
2. Add US3 only after the local resolver and precedence rules are stable.
3. Treat a future OBS hook consumer as a separate feature, with an opt-in
   comparison and rollback plan.

## Format Validation

All 38 tasks use the required checkbox, sequential task ID, optional `[P]`
marker only for parallel work, user-story label inside story phases, and an
exact target file path.
