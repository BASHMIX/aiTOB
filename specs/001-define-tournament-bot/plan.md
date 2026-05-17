# Implementation Plan: AI Tournament Organizer Platform

**Branch**: `001-define-tournament-bot` | **Date**: 2026-05-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-define-tournament-bot/spec.md`

## Summary

An AI-powered tournament organizer for Street Fighter 6 events that automates player registration, match coordination, and score verification through a Discord bot with an AI referee (LangGraph), backed by a FastAPI API, aiosqlite database, and a React/TypeScript Admin Hub with real-time updates. The system integrates with the Start.gg GraphQL API for bracket management and provides OBS-compatible stream overlays.

## Technical Context

**Language/Version**: Python 3.10+ (backend, bot, agent), TypeScript 5+ (frontend)

**Primary Dependencies**:
- **Backend**: FastAPI, uvicorn, aiosqlite, httpx, python-dotenv, Pillow, websockets, jinja2
- **Bot**: discord.py (async)
- **AI Agent**: langgraph, langchain-core, langchain-google-genai, pydantic
- **Frontend**: React 19, Vite 8, Tailwind CSS 3, Zustand (state), React Router 7, Axios, Lucide React (icons), react-rnd (drag/resize)

**Storage**: aiosqlite (SQLite) — async, non-blocking local storage. Tables: `players`, `tournaments`, `active_matches`, `match_results`, `conflicts`, `bot_feed`, `hub_commands`, `overlays`, `stations`, `station_overlays`, `connections` (legacy), `global_settings` (primary config store), `player_overrides`

**Testing**: pytest (backend), manual testing via the Hub UI (frontend)

**Target Platform**: Windows local development, Docker Compose for deployment

**Project Type**: Multi-service web application (API + Discord Bot + React SPA)

**Performance Goals**: Hub loads <1s (SC-003), Start.gg updates <5s (SC-002), AI referee >95% accuracy (SC-004)

**Constraints**: Start.gg API rate limit 80 req/60s, async-only I/O, single shared password auth

**Scale/Scope**: Single organizer, ~64-128 players per tournament, multiple concurrent events

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Asynchronous Architecture First | ✅ PASS | All DB ops via `aiosqlite`, API via `FastAPI` (async), bot via `discord.py` (async), HTTP via `httpx` (async) |
| II. Stateful Event-Driven Agents | ✅ PASS | Match referee uses LangGraph with `MemorySaver` for checkpointed state machine |
| III. Strict AI Interfaces | ✅ PASS | `MatchResultExtraction` Pydantic model constrains LLM output for score extraction |
| IV. Resilient API Integrations | ✅ PASS | Start.gg client implements rate-limit handling (80/60s), retry, exception catching per FR-013 |
| V. Clear Observability & Real-time UI | ✅ PASS | `run.py` color-coded log aggregation, `bot_feed` table, WebSocket real-time updates, heartbeat system |

All gates pass. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/001-define-tournament-bot/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── api-endpoints.md
│   └── websocket-events.md
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── api/
│   ├── main.py              # FastAPI app (routes, WebSocket, static)
│   ├── overlay_config.json  # Default overlay configuration
│   ├── overlay_configs/     # Per-overlay config storage
│   ├── static/              # Static assets (avatars, images)
│   └── templates/           # Jinja2 templates (OBS overlays)
├── bot/
│   ├── main.py              # Discord bot entry point
│   └── agent/               # LangGraph AI referee + admin agent
├── core/
│   ├── database.py          # aiosqlite schema + CRUD operations
│   ├── database.sqlite      # SQLite database file
│   └── image_utils.py       # Avatar image processing
└── assets/                  # Shared assets

frontend-react/
├── src/
│   ├── App.tsx              # Root component + routing
│   ├── main.tsx             # Entry point
│   ├── index.css            # Tailwind + global styles
│   ├── components/          # Shared UI components
│   ├── features/            # Feature-specific components (Hub, Editor, OBS)
│   ├── hooks/               # Custom React hooks
│   ├── services/            # API client services
│   └── store/               # Zustand state stores
├── tailwind.config.js
├── vite.config.ts
└── package.json

run.py                       # Master startup (API + Bot + Vite)
stop.py                      # Graceful shutdown
requirements.txt             # Python dependencies
docker-compose.yml           # Container orchestration
Dockerfile                   # Backend container
```

**Structure Decision**: Web application structure (Option 2) — `backend/` (Python) + `frontend-react/` (React/TS). This matches the existing repository layout. The backend further splits into `api/` (FastAPI), `bot/` (Discord), `core/` (shared DB/utils), and `bot/agent/` (LangGraph). Note: Player override routes are consolidated into `tournaments.py` to ensure reliable prefix resolution.

## Complexity Tracking

No constitution violations. No complexity justifications needed.
