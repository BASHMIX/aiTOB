# Quickstart: AI Tournament Organizer

## Prerequisites

- Python 3.12+
- Node.js 20+
- Discord Bot Token (from Discord Developer Portal)
- Start.gg API Token

## Setup

```powershell
# Clone & install Python deps
pip install -r requirements.txt
uv sync --dev

# Install frontend deps
cd frontend-react
npm install
cd ..

# Configure environment
copy .env.example .env
# Edit .env: set DISCORD_TOKEN, STARTGG_TOKEN, HUB_PASSWORD
```

## Run

```powershell
# Start all 3 services (API :8000, Bot, Vite :5173)
python run.py

# Stop all
python stop.py
```

## Frontend

| Route | Description |
|-------|-------------|
| `/login` | Hub password entry |
| `/admin/hub` | Match dashboard (guarded) |
| `/admin/editor` | Overlay editor (guarded) |
| `/obs` | OBS browser source (no auth) |

## Key Commands (Discord)

- `!register` — Start registration flow
- `!report <p1_score>-<p2_score>` — Report match score (in match thread)

## API Reference

OpenAPI docs at `http://localhost:8000/docs` — 46 endpoints with 15 Pydantic schemas.
