# Research: AI Tournament Organizer Platform

## Key Decisions

### 1. Service Architecture (3-service monorepo)
- **Decision**: `run.py` launches API, Bot, and Vite concurrently with color-coded logs
- **Rationale**: Fast iteration during development; each service hot-reloads independently. `stop.py` kills process trees via psutil.
- **Alternatives considered**: Docker Compose in dev (too slow for hot-reload), single monolithic service (too coupled)
- **Reference**: `run.py` at repo root, `stop.py` at repo root

### 2. Database: SQLite via aiosqlite
- **Decision**: Single `backend/core/database.sqlite` file, all queries centralized in `database.py` (675 lines)
- **Rationale**: Zero configuration, async-native, sufficient for tournament-scale data (hundreds of matches per event)
- **Alternatives considered**: PostgreSQL (overkill for local tournament), Redis (doesn't replace relational storage)
- **Key tables**: players, active_matches, match_results, tournaments, stations, overlays, conflicts, bot_feed, hub_commands, global_settings, connections, player_overrides

### 3. Start.gg Integration: Singleton with Rate Limiting
- **Decision**: `StartGGClient` singleton with 75 req/min lock, centralized in `backend/core/startgg_client.py`
- **Rationale**: Start.gg enforces 80 req/60s; shared lock prevents bursts from multiple callers
- **Constraints**: Per-instance threading.Lock, all mutations funneled through client methods
- **Edge case**: `fetch_set_entrant_order` falls back to default ordering on API failure

### 4. Pydantic v2 Schema Validation
- **Decision**: All API request bodies validated by Pydantic v2 models in `backend/api/schemas.py`
- **Rationale**: Strict input validation, auto-generated OpenAPI docs, field coercion for numeric IDs
- **Key finding**: `str` fields with `mode="before"` field validators needed for Start.gg numeric IDs (set_id, entrant_ids arrive as ints from frontend)

### 5. Per-Game Score Reporting to Start.gg
- **Decision**: `report_set_score_normal` sends per-game `gameData` entries (winner=1, loser=0 per game)
- **Rationale**: Fighting game format; a 2-0 set sends `[{1-0, gameNum:1}, {1-0, gameNum:2}]`
- **Consolidation**: Method internally handles entrant order lookup, `mark_in_progress` call, and score swapping — reduced API call chain from 3 to 2 sequential calls

### 6. WebSocket Hub Protocol
- **Decision**: `/ws/hub` for tournament slug subscription, `/ws/overlay/{slot}` for per-slot overlay broadcast
- **Rationale**: Push-based updates eliminate polling; overlay slots allow per-station isolation
- **Implementation**: `ws_manager.py` with per-connection subscription registry; periodic pings for keepalive

### 7. Hub Auth: Bearer + X-Hub-Password
- **Decision**: Shared password stored in `global_settings` table, fallback to `HUB_PASSWORD` env var
- **Rationale**: Simple shared secret suitable for local/admin use; Axios interceptor injects into all requests
- **Implementation**: `backend/api/auth.py` middleware checks Bearer token or X-Hub-Password header

### 8. Frontend State Management: Zustand
- **Decision**: Two stores: `useHubStore` (matches, tournaments, stations, WebSocket, auth) and `useEditorStore` (overlay config)
- **Rationale**: Lightweight, TypeScript-native, no boilerplate vs Redux
- **Reference**: `frontend-react/src/store/useHubStore.ts`, `useEditorStore.ts`

## Unresolved Considerations (future phases)

- **AI Referee accuracy**: Phase 3 will validate >95% score extraction accuracy
- **Bilingual support (Arabic/English)**: Registration flow handles language selection, but Discord message i18n not yet implemented
- **Start.gg webhook fallback**: Currently polling-based; webhooks would reduce latency to near-instant
- **Registration deadline purge**: Logic for purging incomplete registrations after event deadline not yet implemented
