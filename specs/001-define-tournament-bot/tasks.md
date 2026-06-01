# Tasks: AI Tournament Organizer Platform

**Input**: Design documents from `specs/001-define-tournament-bot/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding, dependency validation, and environment configuration

- [x] T001 Validate Python 3.10+ and Node.js 18+ are available and all dependencies install cleanly via `pip install -r requirements.txt` and `cd frontend-react && npm install`
- [x] T002 [P] Create `.env.example` template with all required environment variables (DISCORD_BOT_TOKEN, STARTGG_API_TOKEN, GOOGLE_API_KEY, DB_PATH, HUB_PASSWORD) in project root
- [x] T003 [P] Create `docker-compose.yml` with backend, bot, and frontend services in project root
- [x] T004 [P] Create `Dockerfile` for the Python backend (API + Bot) in project root


---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Extend database schema in `backend/core/database.py` — add `registration_step` column to `players` table (tracks pending registration progress: startgg_linked, language_set, cfn_provided, avatar_uploaded, complete) and `registration_deadline` column to `tournaments` table
- [x] T006 [P] Create Start.gg GraphQL client module at `backend/core/startgg_client.py` — implement async functions: `fetch_tournament_sets(slug)`, `report_set_score(set_id, winner_id, scores)`, `mark_set_dq(set_id, entrant_id)`, `reset_set(set_id)` with rate-limit handling (80 req/60s), retry/backoff, and exception catching per Constitution Principle IV
- [x] T007 [P] Create WebSocket manager at `backend/api/ws_manager.py` — implement `ConnectionManager` class that handles client connections, tournament-scoped subscriptions (`subscribe` event), and broadcast methods for all event types defined in `contracts/websocket-events.md` (match_update, bot_feed, heartbeat, conflict_created, etc.)
- [x] T008 [P] Create shared Pydantic models at `backend/core/models.py` — define `Player`, `ActiveMatch`, `MatchResult`, `Tournament`, `Conflict`, `BotFeedEntry`, `Overlay` response/request schemas per data-model.md validation rules
- [x] T009 [P] Create Hub authentication middleware at `backend/api/auth.py` — implement shared password gate using `global_settings` table (`hub_password` key) per FR-016; exempt OBS overlay routes (`/obs/*`) from auth
- [x] T010 Refactor `backend/api/main.py` — extract route groups into separate router modules: `backend/api/routers/players.py`, `backend/api/routers/matches.py`, `backend/api/routers/tournaments.py`, `backend/api/routers/overlays.py`, `backend/api/routers/settings.py`, `backend/api/routers/hub.py`; integrate WebSocket manager from T007 and auth middleware from T009


**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Player Registration via Discord (Priority: P1) 🎯 MVP

**Goal**: Players register for tournaments through Discord by linking Start.gg, providing CFN ID, choosing language, uploading avatar

**Independent Test**: Create a dummy tournament, have two Discord accounts register via the bot's DM prompts, verify profiles (Start.gg link, CFN ID, language, avatar) appear correctly in the database

### Implementation for User Story 1

- [x] T011 [US1] Implement registration button and DM flow in `backend/bot/main.py` — add `!setup_registration` command that posts an embed with a "Register" button; on click, bot sends DM to initiate multi-step flow
- [x] T012 [US1] Implement multi-step DM registration state machine in `backend/bot/registration.py` — steps: Start.gg linking → language selection (AR/EN) → CFN ID input → avatar upload; track progress via `registration_step` column; save partial progress at each step per FR-018
- [x] T013 [US1] Implement avatar validation in `backend/core/image_utils.py` — add quality check (min 100x100px dimensions, file size <5MB) and AI safety check using Google Gemini vision for prohibited content per FR-004
- [x] T014 [US1] Implement Start.gg account linking in `backend/bot/registration.py` — verify player's Start.gg ID via GraphQL query using `backend/core/startgg_client.py`, store `startgg_id` and `gamer_tag` in players table
- [x] T015 [US1] Implement duplicate registration handling in `backend/bot/registration.py` — detect already-registered players (`is_verified = TRUE`), offer profile update flow instead of new registration per acceptance scenario 3
- [x] T016 [US1] Implement registration deadline purge in `backend/core/database.py` — add async function `purge_incomplete_registrations(tournament_slug)` that deletes players with `is_verified = FALSE` when the tournament's `registration_deadline` has passed per FR-018
- [x] T017 [US1] Create registration API endpoints in `backend/api/routers/players.py` — GET `/api/players` (list all), GET `/api/players/{discord_id}` (get one), POST `/api/players` (create/update) per contracts/api-endpoints.md
- [x] T018 [US1] Add bilingual message templates at `backend/bot/messages.py` — create Arabic and English string templates for all registration prompts, confirmations, and error messages per FR-014


**Checkpoint**: User Story 1 complete — players can register via Discord, profiles are persisted and viewable via API

---

## Phase 4: User Story 2 — Automated Match Coordination & AI Refereeing (Priority: P1)

**Goal**: System auto-creates Discord threads for matches, prompts ready checks, AI referee verifies scores, results reported to Start.gg

**Independent Test**: Create mock tournament on Start.gg, advance bracket to generate a match, verify Discord thread created, complete ready check, report agreeing scores, confirm Start.gg reflects result within 5 seconds

**Depends on**: Phase 3 (US1) — players must be registered to be matched

### Implementation for User Story 2

- [x] T019 [US2] Implement Start.gg bracket polling loop in `backend/bot/bracket_sync.py` — async task that polls `fetch_tournament_sets()` every 15 seconds, detects new ready matches, triggers thread creation; respect 80 req/60s rate limit per FR-001/FR-0013
- [x] T020 [US2] Implement Discord thread creation in `backend/bot/match_threads.py` — when a match is detected, create a Discord thread for the two players, post match info embed (round name, player names, CFN IDs), add both players to thread per FR-003
- [x] T021 [US2] Implement ready-check system in `backend/bot/match_threads.py` — prompt both players with reaction-based ready check; implement two-stage timeout: warning at 3 min, auto-DQ at 5 min per FR-015
- [x] T022 [US2] Implement double-forfeit handling in `backend/bot/match_threads.py` — when both players fail ready check timeout, auto-DQ both, report double-DQ to Start.gg via `mark_set_dq()`, advance bracket per FR-019
- [x] T023 [US2] Implement AI referee agent at `backend/bot/agent/referee.py` — LangGraph stateful agent with `MemorySaver` that monitors thread messages, extracts scores using Pydantic `MatchResultExtraction` model with `structured_output`, detects agreement/conflict per FR-005 and Constitution Principles II & III
- [x] T024 [US2] Implement score agreement flow in `backend/bot/match_threads.py` — when AI referee detects agreed scores, report to Start.gg via `report_set_score()`, lock thread, post completion message, archive to `match_results` table per FR-002
- [x] T025 [US2] Implement conflict detection flow in `backend/bot/match_threads.py` — when AI referee detects mismatched scores, create conflict record in `conflicts` table, flag match as "conflict" status, ping admin in thread, broadcast `conflict_created` WebSocket event
- [x] T026 [US2] Implement match coordination API endpoints in `backend/api/routers/matches.py` — GET `/api/matches`, GET `/api/matches/{set_id}`, POST `/api/matches/{set_id}/call`, POST `/api/matches/{set_id}/score`, POST `/api/matches/{set_id}/dq`, POST `/api/matches/{set_id}/reopen`, DELETE `/api/matches/{set_id}` per contracts/api-endpoints.md
- [x] T027 [US2] Implement conflict resolution API endpoints in `backend/api/routers/matches.py` — GET `/api/conflicts`, POST `/api/conflicts/{id}/resolve` per contracts/api-endpoints.md
- [x] T028 [US2] Wire WebSocket broadcast for match events in `backend/api/routers/matches.py` — broadcast `match_update`, `match_deleted`, `conflict_created`, `conflict_resolved` events via WebSocket manager from T007

**Checkpoint**: User Story 2 complete — matches are auto-coordinated via Discord threads with AI refereeing and Start.gg sync

---

## Phase 5: User Story 3 — Admin Hub Real-Time Monitoring (Priority: P2)

**Goal**: Web dashboard showing real-time match statuses, bot health, player conflicts, manual override controls, tournament selector

**Independent Test**: Open Hub, mock match events, verify UI updates within 1 second, simulate bot heartbeat failure and confirm "Offline" within 10 seconds

**Depends on**: Phase 4 (US2) — match data must exist to display

### Implementation for User Story 3

- [x] T029 [US3] Implement Hub password login page at `frontend-react/src/features/auth/LoginPage.tsx` — shared password form, session persistence, redirect to dashboard on success per FR-016
- [x] T030 [US3] Implement auth guard HOC at `frontend-react/src/components/AuthGuard.tsx` — wrap all Hub routes, redirect to login if unauthenticated
- [x] T031 [US3] Implement tournament selector component at `frontend-react/src/features/hub/TournamentSelector.tsx` — dropdown of all tournaments from API, persists selection per tab, scopes all dashboard data per FR-017
- [x] T032 [US3] Implement WebSocket hook at `frontend-react/src/hooks/useHubSocket.ts` — connect to `ws://localhost:8000/ws/hub`, auto-reconnect gracefully handling React dev server reloads
- [x] T033 [P] [US3] Implement match dashboard store at `frontend-react/src/store/useHubStore.ts` — Zustand store for active matches, updated via WebSocket `match_update` events
- [x] T034 [P] [US3] Implement bot status store at `frontend-react/src/store/botStatusStore.ts` — Zustand store tracking Discord bot online/offline state from WebSocket `heartbeat` events, display "Offline" if heartbeat missed >10s per FR-011
- [x] T035 [US3] Implement match dashboard page at `frontend-react/src/features/hub/MatchDashboard.tsx` — real-time match list with status badges, player names, and scores
- [x] T036 [US3] Implement conflict resolution panel at `frontend-react/src/features/hub/ConflictPanel.tsx` — display unresolved conflicts with P1/P2 claims, provide force-score, DQ, and reassign buttons per FR-007
- [x] T037 [US3] Implement match admin controls at `frontend-react/src/features/hub/MatchCard.tsx` — call match, force score, DQ player, reopen match buttons; each calls corresponding API endpoint
- [x] T038 [US3] Implement bot feed panel at `frontend-react/src/features/hub/BotFeedPanel.tsx` — scrollable list of bot activity from WebSocket `bot_feed` events with level-based color coding
- [x] T039 [US3] Implement bot feed and heartbeat API endpoints in `backend/api/routers/hub.py` — GET `/api/bot-feed`, DELETE `/api/bot-feed`; implement heartbeat broadcast logic
- [x] T040 [US3] Implement Discord bot heartbeat sender in `backend/bot/main.py` — send heartbeat to database every 10 seconds; API broadcasts to WebSocket clients per FR-011

**Checkpoint**: User Story 3 complete — admins can monitor and manage tournaments from the web dashboard in real-time

---

## Phase 6: User Story 4 — AI Admin Assistant (Priority: P3)

**Goal**: Natural language and structured command interface in the Hub for quick admin actions

**Independent Test**: Type "Who is currently playing?" in agent chat, verify correct list of active matches returned. Type "announce next round in 5 minutes", verify message posts to Discord.

**Depends on**: Phase 5 (US3) — Hub must exist to host the agent chat

### Implementation for User Story 4

- [x] T041 [US4] Implement admin agent at `backend/bot/agent/admin_agent.py` — LangGraph agent with tools: `get_active_matches`, `get_players`, `create_discord_thread`, `post_announcement`; use Pydantic structured output per Constitution Principles II & III
- [x] T042 [US4] Implement structured command parser in `backend/api/routers/hub.py` — parse `msg <P1> vs <P2>`, `announce <msg>`, `call_match <id>` commands; route to bot actions per FR-009
- [x] T043 [US4] Implement hub command API endpoint in `backend/api/routers/hub.py` — POST `/api/hub/command` that routes to either the NL agent (T041) or structured command parser (T042) and returns response per FR-008
- [x] T044 [US4] Implement agent chat UI at `frontend-react/src/features/hub/AgentChat.tsx` — chat input, response display, command history, loading states; submit to `/api/hub/command` endpoint

**Checkpoint**: User Story 4 complete — admins can issue NL and structured commands from the Hub

---

## Phase 7: User Story 5 — OBS Stream Overlay System (Priority: P3)

**Goal**: Customizable OBS-compatible overlays with live match data and a visual editor

**Independent Test**: Open OBS overlay URL in browser, start a match, verify overlay displays both players' names, avatars, and scores with live updates

**Depends on**: Phase 4 (US2) — match data must exist to populate overlays. Can run in parallel with Phase 5/6.

### Implementation for User Story 5

- [x] T045 [P] [US5] Implement OBS overlay data endpoint at `backend/api/routers/overlays.py` — GET `/obs/{overlay_name}/data` returns current match data as JSON; GET `/obs/{overlay_name}` returns rendered HTML page per contracts/api-endpoints.md (no auth required)
- [x] T046 [P] [US5] Create OBS overlay HTML template at `backend/api/templates/overlay.html` — Jinja2 template with player names, avatars, scores, team/country info; auto-refreshes via JS polling or WebSocket
- [x] T047 [US5] Implement overlay CRUD API endpoints in `backend/api/routers/overlays.py` — GET `/api/overlays`, POST `/api/overlays`, DELETE `/api/overlays/{name}` per contracts/api-endpoints.md
- [x] T048 [US5] Implement overlay editor page at `frontend-react/src/features/editor/OverlayEditor.tsx` — visual drag/resize editor using `react-rnd` for overlay element positioning; save config to API per FR-010
- [x] T049 [US5] Implement station management in `backend/api/routers/overlays.py` — GET `/api/stations`, POST `/api/stations`, DELETE `/api/stations/{id}`; link overlays to stations per contracts/api-endpoints.md

**Checkpoint**: User Story 5 complete — streamers have customizable live overlays for OBS

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T050 [P] Add comprehensive error handling across all API routers — consistent error response format, proper HTTP status codes, meaningful error messages
- [x] T051 [P] Add structured logging across backend services — use Python `logging` module with color-coded output per Constitution Principle V
- [x] T052 Implement WebSocket reconnection logic in Hub — graceful reconnection avoiding `ECONNABORTED` states
- [x] T053 [P] Add tournament settings API endpoint at `backend/api/routers/tournaments.py` — PATCH `/api/tournaments/{slug}/settings`
- [x] T054 [P] Add connections and global settings API endpoints — Settings UI fully implemented; Start.gg token dynamically loaded
- [x] T055 [Fix] Consolidate router topology and data schemas — Relocated Player Overrides to Tournament router for reliability, fixed GraphQL flattening 500 errors, and fixed avatar form field mappings.
- [x] T056 [US2] Create AI referee accuracy evaluation harness — add a test suite that feeds 100+ mock chat scenarios (including edge cases like player jokes, conflicts, and malformed scores) to the LangGraph referee and validates extraction against expected results to verify >95% accuracy (SC-004)
- [x] T057 Run quickstart.md validation — execute full setup flow, verify all services start, create a test tournament, register two players, complete a match end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 Registration (Phase 3)**: Depends on Phase 2
- **US2 Match Coordination (Phase 4)**: Depends on Phase 3 (needs registered players)
- **US3 Admin Hub (Phase 5)**: Depends on Phase 4 (needs match data to display)
- **US4 AI Assistant (Phase 6)**: Depends on Phase 5 (needs Hub UI to host chat)
- **US5 OBS Overlays (Phase 7)**: Depends on Phase 4 (needs match data); can run in **parallel** with Phases 5 & 6
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### Dependency Graph

```
Phase 1 → Phase 2 → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3) → Phase 6 (US4)
                                           ↓
                                      Phase 7 (US5) [parallel with 5 & 6]
                                           ↓
                                      Phase 8 (Polish)
```

### Within Each User Story

- Models/schema before services
- Services before API endpoints
- Backend before frontend
- Core implementation before integration

### Parallel Opportunities

- **Phase 2**: T006, T007, T008, T009 can all run in parallel (different files)
- **Phase 5**: T033, T034 can run in parallel (different stores)
- **Phase 7**: T045, T046 can run in parallel (different files)
- **Phase 7 overall**: Can run in parallel with Phases 5 & 6 (independent feature)
- **Phase 8**: T050, T051, T053, T054 can all run in parallel

---

## Parallel Example: User Story 2

```text
# After Phase 3 complete, launch these in parallel:
Task T019: "Bracket polling loop in backend/bot/bracket_sync.py"
Task T023: "AI referee agent in backend/bot/agent/referee.py"
Task T026: "Match coordination API endpoints in backend/api/routers/matches.py"

# Then sequentially:
Task T020: "Discord thread creation" (needs T019)
Task T021: "Ready-check system" (needs T020)
Task T024: "Score agreement flow" (needs T023 + T020)
Task T025: "Conflict detection flow" (needs T023 + T020)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (Player Registration)
4. **STOP and VALIDATE**: Test registration flow independently
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (Registration) → Test → **MVP!**
3. Add US2 (Match Coordination + AI Referee) → Test → **Core automation!**
4. Add US3 (Admin Hub) → Test → **Full monitoring!**
5. Add US4 (AI Assistant) → Test → **Enhanced admin!**
6. Add US5 (OBS Overlays) → Test → **Stream ready!**
7. Polish → **Production ready!**

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
