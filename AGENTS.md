# AI Tournament Organizer Bot

## Architecture

**3 services** managed by `run.py` (color-coded, parallel logs):
- **API** — FastAPI on `:8000` (`uvicorn backend.api.main:app --reload`)
- **BOT** — Discord bot (`backend/bot/main.py`)
- **VITE** — React dev server on `:5173` (proxies `/api`, `/static`, `/assets`, `/ws` to `:8000`)

Stop all with `python stop.py` (reads `.pids.json`, kills process trees via psutil).

Docker: `docker compose up --build` — multi-stage builds (api / bot targets).

## Stack

| Layer | Tech | Key files |
|-------|------|-----------|
| Backend | Python 3.12+, FastAPI, aiosqlite, psutil | `backend/api/main.py` — entrypoint & WS |
| Database | SQLite via aiosqlite | `backend/core/database.py` — schema + all queries |
| Models | Pydantic v2 | `backend/core/models.py` |
| Discord | discord.py 2.x | `backend/bot/main.py` — commands, threads, hub-agent |
| AI | LangGraph + langchain-google-genai | `backend/bot/agent/` — match referee graph |
| Brackets | Start.gg API | `backend/core/startgg_client.py`, `backend/bot/bracket_sync.py` |
| Frontend | React 19 + TypeScript 6 + Vite 8 + Tailwind 3 | `frontend-react/` — `@/` alias to `src/` |
| State | Zustand | `frontend-react/src/store/useHubStore.ts`, `useEditorStore.ts` |
| Auth | Hub password via Bearer / X-Hub-Password | `backend/api/auth.py` |

## Dev commands

```powershell
# Start all 3 services
python run.py

# Stop all services
python stop.py

# Python deps — installed via pip; dev deps via uv
pip install -r requirements.txt
uv sync --dev          # includes pytest, pytest-asyncio

# Frontend
cd frontend-react
npm install
npm run dev            # Vite :5173
npm run build          # tsc && vite build
```

## Frontend routes

- `/login` — enter hub password
- `/admin/hub` — dashboard (guarded by AuthGuard)
- `/admin/editor` — overlay editor (guarded by AuthGuard)
- `/obs` — OBS browser source (no auth, reads overlay config)

## Key conventions

- Frontend proxies ALL `/api`, `/static`, `/assets`, `/ws` to backend in dev
- Axios interceptor in `src/main.tsx` injects hub password as Bearer + X-Hub-Password
- Hub password stored in DB (`global_settings` table), fallback `HUB_PASSWORD` env var
- `.env` is real secrets (in .gitignore), `.env.example` is template
- Database auto-creates + migrates on startup (`init_db()`)
- Frontend uses `verbatimModuleSyntax` + `erasableSyntaxOnly` (TS 6.0 strict)
- LangGraph agent at `backend/bot/agent/graph.py` — match referee with tool calling
- Hub agent polls every 3s for pending commands (`backend/bot/main.py:poll_hub_commands`)
- WebSocket at `/ws/hub` — subscribe to tournament_slug for live updates
- WebSocket at `/ws/overlay/{slot}` — per-slot overlay broadcast

## Testing

```powershell
# Run all tests
pytest

# Run with asyncio support
pytest -p pytest_asyncio
```

## Spec Kit workflow

Project uses [Spec Kit](https://opencode.ai) with git extension:
- `speckit.specify` → `speckit.plan` → `speckit.tasks` → `speckit.implement`
- Feature branches: numbered (`001-feature-name`)
- Auto-commit hooks enabled for most steps
- Config at `.specify/extensions/git/git-config.yml`
