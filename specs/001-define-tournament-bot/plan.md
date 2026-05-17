# Implementation Plan: AI Tournament Organizer Platform

**Branch**: `master` | **Date**: 2026-05-17 | **Spec**: `specs/001-define-tournament-bot/spec.md`

**Input**: Feature specification from `specs/001-define-tournament-bot/spec.md`

## Summary

Full-stack tournament management platform integrating Discord bot, Start.gg bracket API, and a React admin dashboard with OBS overlays. AI-powered match referee via LangGraph automates score verification and conflict resolution. 6-phase delivery starting from Foundation & Scaffold.

## Technical Context

**Language/Version**: Python 3.12+, Node.js 20+, TypeScript 6.0 (verbatimModuleSyntax)

**Primary Dependencies**:
- Backend: FastAPI, uvicorn, aiosqlite, discord.py 2.x, langgraph, langchain-google-genai, psutil, httpx
- Frontend: React 19, Vite 8, Tailwind 3, Zustand, Axios
- Dev: pytest, pytest-asyncio, mypy, ruff

**Storage**: SQLite via aiosqlite (`backend/core/database.sqlite`). Tables: players, overlays, tournaments, active_matches, match_results, stations, conflicts, bot_feed, hub_commands, global_settings, connections, player_overrides.

**Testing**: pytest + pytest-asyncio. Run `pytest` from repo root.

**Target Platform**: Windows (dev) / Linux (production, Docker). Docker multi-stage builds targeting API and bot service images.

**Project Type**: Monorepo — 3-service architecture: FastAPI REST API (`:8000`), Discord bot, React Vite dev server (`:5173`). Managed by `run.py` (color-coded parallel logs). Stop via `python stop.py`.

**Performance Goals**: Match results reported to Start.gg within 5s of verification. Hub UI updates <1s via WebSocket push. Bot heartbeat every 10s.

**Constraints**: Start.gg API rate limit: 75 req/min (handled by singleton rate limiter with per-instance lock). WebSocket reconnection with exponential backoff. OBS browser sources must work without auth.

**Scale/Scope**: 6 sequential phases (Foundation → Registration → Match Coordination → AI Referee → Admin Dashboard → AI Assistant). Supports multiple concurrent tournaments via Hub tournament selector.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Async Architecture First | ✅ PASS | All I/O async: FastAPI, aiosqlite, discord.py, httpx. No blocking calls in event loop. |
| II. Stateful Event-Driven Agents | ✅ PASS | LangGraph with MemorySaver for match referee graph (`backend/bot/agent/graph.py`). State persisted per-thread. |
| III. Strict AI Interfaces | ✅ PASS | Pydantic v2 models with `structured_output` for all LLM responses. Validators enforce schemas. |
| IV. Resilient API Integrations | ✅ PASS | `StartGGClient` singleton with 75 req/min rate limiter, exception handling, retry. Fallback to default ordering on fetch failure. |
| V. Clear Observability & Real-time UI | ✅ PASS | WebSocket at `/ws/hub` and `/ws/overlay/{slot}`. `run.py` color-coded logs. Bot feed panel in Hub. |

**Gate verdict**: ✅ ALL CONSTITUTION CHECKS PASS — Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-define-tournament-bot/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
backend/
├── api/                 # FastAPI entrypoint + routers
│   ├── main.py          # App factory, CORS, WS, startup
│   ├── auth.py          # Hub password auth (Bearer + X-Hub-Password)
│   ├── schemas.py       # Pydantic v2 request/response models
│   ├── ws_manager.py    # WebSocket connection manager
│   └── routers/         # 8 routers: matches, tournaments, hub, settings, stations, overlays, assets, players
├── bot/                 # Discord bot
│   ├── main.py          # Bot client, commands, hub command poller
│   ├── match_threads.py # Match thread lifecycle
│   ├── messages.py      # Message formatting
│   ├── registration.py  # Player registration flow
│   └── agent/           # LangGraph match referee
│       └── graph.py     # Referee state graph with tool calling
├── core/                # Shared business logic
│   ├── database.py      # SQLite schema + all queries (675 lines)
│   ├── models.py        # Pydantic domain models
│   ├── startgg_client.py# Start.gg GraphQL client with rate limiting
│   ├── match_state.py   # Match state machine
│   └── image_utils.py   # Image processing utilities

frontend-react/          # React 19 + Vite 8 + Tailwind 3
└── src/
    ├── main.tsx         # Entry, Axios interceptor (Bearer + X-Hub-Password)
    ├── App.tsx          # Router: /login, /admin/hub, /admin/editor, /obs
    ├── store/           # Zustand: useHubStore, useEditorStore
    ├── hooks/           # useHubSocket
    ├── features/
    │   ├── auth/        # LoginPage
    │   ├── hub/         # HubDashboard, MatchDashboard, MatchesList, MatchCard, ActiveMatchCard
    │   ├── editor/      # Overlay editor with drag/resize elements
    │   └── obs/         # OBS viewer (no auth)
    └── components/      # Shared: layout, AuthGuard
```

## Complexity Tracking

No violations — constitution gates pass without complexity concerns.

