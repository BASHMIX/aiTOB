<!--
SYNC IMPACT REPORT
Version: 1.0.0 (Initial Draft for AI Tournament Organizer)
Modified Principles: N/A (Initial Template population)
Added Sections:
  - I. Asynchronous Architecture First
  - II. Stateful Event-Driven Agents
  - III. Strict AI Interfaces
  - IV. Resilient API Integrations
  - V. Clear Observability & Real-time UI
Removed Sections: All placeholder principles.
Templates requiring updates:
  - .specify/templates/plan-template.md (✅ updated conceptually / no hardcoded principle links found)
  - .specify/templates/spec-template.md (✅)
  - .specify/templates/tasks-template.md (✅)
Deferred Items: None.
-->
# AI Tournament Organizer Bot Constitution

## Core Principles

### I. Asynchronous Architecture First
All I/O bound operations (Database, API calls, Discord bot events) MUST be asynchronous using frameworks like `discord.py`, `aiosqlite`, `httpx`, and `FastAPI`. Blocking the main event loop is strictly prohibited as it will cause bot latency and missed events.

### II. Stateful Event-Driven Agents
Complex workflows involving human interaction (e.g., match moderation in Discord threads) MUST use stateful agent architectures. specifically LangGraph with `MemorySaver` to persist and resume state accurately when waiting for user inputs.

### III. Strict AI Interfaces
All Large Language Model (LLM) outputs intended for system logic MUST be constrained using strict schemas (e.g., Pydantic models with `structured_output`). Unstructured text parsing for critical logic or state updates is not allowed.

### IV. Resilient API Integrations
All external API calls (especially Start.gg GraphQL API) MUST include proper rate-limit handling, exception catching, and retry mechanisms. The bot must fail gracefully on API timeouts without crashing the agent process.

### V. Clear Observability & Real-time UI
The backend MUST aggregate logs with clear color-coding for different services (via `run.py`). The frontend (React/Vite/Tailwind) MUST provide real-time status feedback (e.g. WebSocket or polling) for all significant events without requiring manual page reloads.

## Development Constraints

- **Python Environment**: Python 3.10+ required.
- **Frontend Stack**: React, TypeScript, Vite, Tailwind CSS.
- **Data Persistence**: `aiosqlite` for fast, async, non-blocking local storage. No heavy databases (like Postgres) unless explicitly required for future scaling.

## Governance

- All pull requests and feature additions must adhere to the asynchronous and stateful principles outlined above.
- Amendments require documentation and approval before implementation.
- Breaking changes to the database schema require a documented migration plan.

**Version**: 1.0.0 | **Ratified**: 2026-05-16 | **Last Amended**: 2026-05-16
