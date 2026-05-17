# AI Tournament Organizer Platform — Phased Spec Kit Implementation Plan

This project is an AI-powered tournament organizer for fighting game events. 
All backend logic is async Python. The frontend is React with TypeScript. 
Every feature must be independently testable. API-first design. 
Test coverage must exceed 80% for all business logic.

## Phase-by-Phase Breakdown

Each phase below is a **self-contained Spec Kit cycle** with its own feature branch, spec, plan, and tasks. Phases are ordered by dependency — each builds on the artifacts of the previous.

---

### Phase 0: Foundation — Project Scaffold & Shared Infrastructure

**Feature Branch**: `000-tournament-bot-foundation`  
**Priority**: Prerequisite (must be done first)

This phase establishes the monorepo structure, shared database schema, configuration management, and CI/CD pipeline that all subsequent phases depend on.

**What this phase covers:**
- Monorepo scaffolding (Python backend + React/Node frontend + shared packages)
- Database schema design and migration framework (Players, Matches, Events tables per the spec's Key Entities)
- Environment configuration and secrets management (Start.gg API keys, Discord bot token, database URL)
- Docker Compose for local development
- CI/CD pipeline (linting, type-checking, testing)
- Project constitution defining architectural principles (async Python, library-first, test-first)

**Spec Kit Commands:**
/speckit.constitution → Establish immutable principles (API-first, test-first, async where possible)
/speckit.specify → Define the foundation requirements
/speckit.plan → Choose tech stack, monorepo structure, DB technology
/speckit.tasks → Break into scaffold, schema, config, CI tasks
/speckit.implement → Execute

text

**Independent Test:** A developer clones the repo, runs `docker compose up`, and the database is provisioned with all tables, the backend and frontend stubs start without errors, and CI passes on the first PR.

---

### Phase 1: Discord Bot — Player Registration & Profile Linking

**Feature Branch**: `001-player-registration`  
**Priority**: P1 (from the Feature Spec)  
**Maps to**: User Story 1 (first two acceptance scenarios), FR-002, FR-006

This is the entry point for players. The Discord bot handles the `/register` flow, links Discord accounts to Start.gg, stores CFN IDs and language preferences, and validates the linkage.

**What this phase covers:**
- Discord bot framework (connection, command handling, slash commands)
- Registration conversation flow (prompts for language, CFN ID, avatar)
- Start.gg account linking via OAuth or manual entry
- Database write/read operations for the Player entity
- Basic error handling and retry logic

**Spec Kit Commands:**
/speckit.specify → Focus on registration UX, profile storage, linking
/speckit.clarify → Resolve: OAuth vs manual link? Timeout on registration flow?
/speckit.plan → Discord.py or discord.js? Database ORM choice?
/speckit.tasks → Bot scaffolding → slash commands → DB persistence → Start.gg linking
/speckit.implement → Build + test

text

**Independent Test:** As defined in the original spec: create a dummy tournament, have two Discord accounts register, verify their profiles appear in the database with correct Start.gg and CFN linkage.

---

### Phase 2: Start.gg Integration & Match Coordination

**Feature Branch**: `002-match-coordination`  
**Priority**: P1  
**Maps to**: User Story 1 (third acceptance scenario), FR-001, FR-002

This phase connects the bot to Start.gg's live tournament data. It polls bracket state, detects when matches are ready, creates Discord threads, and posts match results back.

**What this phase covers:**
- Start.gg GraphQL API client (authentication, querying, mutation)
- Bracket polling / webhook handler for match state changes
- Discord thread creation (private or public) for each match pair
- Score reporting back to Start.gg upon agreement
- Edge case handling: API rate limits, outages, retry strategies

**Spec Kit Commands:**
/speckit.specify → Match lifecycle, API integration contracts
/speckit.clarify → Polling vs webhooks? Thread visibility rules? Rate limit strategy?
/speckit.plan → GraphQL client library, polling architecture, retry patterns
/speckit.tasks → API client → bracket polling → thread creation → score reporting
/speckit.implement → Build + integration tests against Start.gg sandbox

text

**Independent Test:** Create a mock tournament on Start.gg, advance the bracket to generate a match, verify a Discord thread is created with both players, report a score, and confirm Start.gg reflects the result.

---

### Phase 3: AI Referee Agent

**Feature Branch**: `003-ai-referee`  
**Priority**: P1  
**Maps to**: User Story 1 (score agreement verification), FR-003, SC-004

The AI referee reads match thread chat history, extracts the agreed-upon score, detects conflicts (different scores reported), and determines when a match is genuinely complete vs. still in progress.

**What this phase covers:**
- LangGraph-based agent definition (state machine for match conversation analysis)
- Chat history ingestion from Discord threads
- Score extraction with >95% accuracy (e.g., "I won 2-1", "ggs 0-2")
- Conflict detection (players report different scores)
- Ambiguity handling: jokes vs. genuine reports, disconnected players
- Integration with Phase 2's match coordination pipeline

**Spec Kit Commands:**
/speckit.specify → Referee behavior, score formats, conflict scenarios
/speckit.clarify → LLM provider choice? Fallback on ambiguity? Timeout behavior?
/speckit.plan → LangGraph state machine design, prompt engineering strategy
/speckit.tasks → Agent scaffolding → score extraction → conflict detection → integration
/speckit.implement → Build + evaluate against a labeled dataset of match conversations

text

**Independent Test:** Feed the agent 100 simulated match thread conversations (including edge cases like jokes, partial reports, disconnections) and measure extraction accuracy against SC-004's 95% threshold.

---

### Phase 4: Admin Web Dashboard

**Feature Branch**: `004-admin-hub`  
**Priority**: P2  
**Maps to**: User Story 2, FR-004, FR-005, SC-003

A real-time web dashboard that gives tournament admins full visibility into match statuses, bot health, and player conflicts. It's the manual override layer for when automation isn't enough.

**What this phase covers:**
- React (or similar) frontend with real-time updates (WebSocket or SSE)
- Match status dashboard (pending, in-progress, completed, conflict)
- Bot heartbeat monitoring and offline detection (<10 seconds)
- Manual override controls (force score, disqualify player, reassign match)
- Conflict resolution UI
- Role-based access (admin-only)

**Spec Kit Commands:**
/speckit.specify → Dashboard views, real-time requirements, admin actions
/speckit.clarify → WebSocket vs polling? Auth mechanism? Mobile responsiveness?
/speckit.plan → Frontend framework, real-time transport, API contract
/speckit.tasks → Scaffold → API layer → dashboard views → override controls
/speckit.implement → Build + test with mocked match events

text

**Independent Test:** Open the dashboard, mock match events from the backend, verify the UI updates within 1 second (SC-003), simulate a bot heartbeat failure and confirm "Offline" status appears within 10 seconds.

---

### Phase 5: AI Admin Assistant

**Feature Branch**: `005-ai-admin-assistant`  
**Priority**: P3  
**Maps to**: User Story 3

A natural language interface embedded in the Admin Hub that lets organizers query match statuses, trigger announcements, and perform common actions via typed commands rather than navigating menus.

**What this phase covers:**
- Chat interface in the Admin Hub
- Natural language intent parsing (query matches, find player, announce)
- Integration with Phase 4's dashboard data APIs
- Discord announcement publishing
- Command history and undo capability

**Spec Kit Commands:**
/speckit.specify → Supported commands, NL understanding scope, announcement formats
/speckit.clarify → LLM provider? Command confirmation step? Multi-language support?
/speckit.plan → Intent classification approach, tool-calling architecture
/speckit.tasks → Chat UI → NL parser → action execution → Discord integration
/speckit.implement → Build + test with the acceptance scenarios

text

**Independent Test:** Type "Who is currently playing?" and verify it returns the correct list of active matches. Type "announce next round in 5 minutes" and verify the message posts to the Discord channel.

---

## Dependency Graph
Phase 0 (Foundation)
│
├──► Phase 1 (Registration Bot) ──► Phase 2 (Match Coordination)
│ │
│ ├──► Phase 3 (AI Referee)
│ │
│ └──► Phase 4 (Admin Dashboard)
│ │
│ └──► Phase 5 (AI Admin Assistant)
│
└──► (Shared database schema used by all phases)

text

- **Phase 1 and Phase 2** can start in parallel once Phase 0 is done — but Phase 2 needs the Player entity from Phase 1's registration flow, so they're sequenced here.
- **Phase 3 and Phase 4** both depend on Phase 2 (match coordination) but are independent of each other and can be developed in parallel.
- **Phase 5** requires Phase 4's dashboard to be in place.

---

## Mapping to Success Criteria

| Success Criterion | Phase |
|---|---|
| SC-001: 80% of matches fully automated | Phases 2 + 3 |
| SC-002: Start.gg updates within 5 seconds | Phase 2 |
| SC-003: Admin Hub loads in <1 second | Phase 4 |
| SC-004: AI referee >95% accuracy | Phase 3 |

---

## Getting Started

To kick off Phase 0 with Spec Kit:

```bash
# Install the Spec Kit CLI
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git

# Initialize the project
specify init tournament-bot --ai copilot

# In your AI agent's chat, establish the constitution
/speckit.constitution This project is an AI-powered tournament organizer for fighting game events. 
All backend logic is async Python. The frontend is React with TypeScript. 
Every feature must be independently testable. API-first design. 
Test coverage must exceed 80% for all business logic.
Then proceed through /speckit.specify, /speckit.plan, /speckit.tasks, and /speckit.implement for Phase 0. After Phase 0 is validated, create a new branch (001-player-registration) and repeat the cycle.