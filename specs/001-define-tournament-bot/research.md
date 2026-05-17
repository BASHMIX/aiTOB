# Research: AI Tournament Organizer Platform

**Date**: 2026-05-16
**Feature**: `001-define-tournament-bot`

## Technology Decisions

### 1. Start.gg API Integration Strategy

- **Decision**: Polling with configurable interval (default 15s)
- **Rationale**: Start.gg does not provide reliable webhooks for tournament state changes. Polling the GraphQL API at intervals is the standard community approach. A 15-second interval stays well within the 80 req/60s rate limit while providing near-real-time bracket awareness.
- **Alternatives considered**:
  - Webhooks: Start.gg webhook support is limited and unreliable for set state changes
  - Long-polling: Not supported by Start.gg API

### 2. Real-Time Frontend Updates

- **Decision**: WebSocket (native `websockets` library via FastAPI)
- **Rationale**: Already implemented in the codebase. WebSocket provides true push-based updates for match state changes, bot feed, and heartbeat status. Lower latency than SSE for bidirectional communication needs (admin commands).
- **Alternatives considered**:
  - Server-Sent Events (SSE): Simpler but unidirectional; doesn't support admin command acknowledgments
  - HTTP polling: Higher latency, more bandwidth

### 3. AI Referee LLM Provider

- **Decision**: Google Gemini via `langchain-google-genai`
- **Rationale**: Already integrated via `langchain-google-genai` in requirements. Gemini provides good structured output support via Pydantic models, which aligns with Constitution Principle III (Strict AI Interfaces).
- **Alternatives considered**:
  - OpenAI: Higher cost, similar capabilities
  - Groq: Faster inference but less stable for structured output

### 4. State Management (Frontend)

- **Decision**: Zustand
- **Rationale**: Already adopted in `frontend-react/src/store/`. Lightweight, minimal boilerplate, excellent TypeScript support. Ideal for managing tournament state, match lists, and bot status.
- **Alternatives considered**:
  - Redux Toolkit: More boilerplate than needed for this scope
  - React Context: Insufficient for cross-component state sharing at this scale

### 5. Avatar Safety & Quality Checks

- **Decision**: Pillow for dimension/quality validation + Google Gemini for content moderation
- **Rationale**: Pillow (`image_utils.py`) already handles image processing. Gemini's vision capabilities can be used for content safety screening without adding a separate moderation API dependency.
- **Alternatives considered**:
  - AWS Rekognition: External dependency, cost
  - OpenAI Vision: Higher cost per image
  - Manual-only review: Doesn't scale, blocks registration flow

### 6. Admin Hub Authentication

- **Decision**: Single shared password (from `global_settings` table)
- **Rationale**: Per clarification Q2. The system is a local tournament tool, not a multi-tenant SaaS. A simple password gate stored in the database keeps it lightweight while preventing unauthorized access during events.
- **Alternatives considered**:
  - Discord OAuth: Adds complexity for a single-admin use case
  - No auth: Security risk on shared networks

### 7. Database Migration Strategy

- **Decision**: Inline ALTER TABLE with try/except (idempotent migrations)
- **Rationale**: Already implemented in `database.py`. Each migration is a single ALTER TABLE wrapped in a try/except that silently skips if the column already exists. Simple, no external migration framework needed for this project scale.
- **Alternatives considered**:
  - Alembic: Overkill for SQLite with a single developer
  - Manual schema versioning: Error-prone

## Resolved Unknowns

All NEEDS CLARIFICATION items from Technical Context have been resolved through existing codebase analysis. No external research was required — the project already has a mature implementation for all core subsystems.
