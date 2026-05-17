# Quickstart: AI Tournament Organizer Platform

## Prerequisites

- Python 3.10+
- Node.js 18+ / npm
- Discord Bot Token (from Discord Developer Portal)
- Start.gg API Token (from developer.start.gg)
- Google Gemini API Key (for AI referee + content moderation)

## Setup

### 1. Clone & Install

```bash
# Clone the repository
git clone <repo-url>
cd "AI Tournament Organizer Bot"

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend-react
npm install
cd ..
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
# Discord
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_GUILD_ID=your_server_id

# Start.gg
STARTGG_API_TOKEN=your_startgg_token

# Google Gemini (AI Referee)
GOOGLE_API_KEY=your_gemini_key

# Database
DB_PATH=backend/core/database.sqlite

# Hub
HUB_PASSWORD=your_admin_password
```

### 3. Run

```bash
# Start all services (API + Bot + Vite frontend)
python run.py
```

This starts:
- **FastAPI** on `http://localhost:8000` (API + WebSocket)
- **Discord Bot** connected to your configured server
- **Vite Dev Server** on `http://localhost:5173` (Admin Hub)

### 4. First Tournament

1. Open the Admin Hub at `http://localhost:5173`
2. Enter the shared password
3. Add your Start.gg tournament slug
4. Run `!setup_registration` in your Discord channel
5. Players click "Register" and complete the DM flow
6. Matches are auto-detected from Start.gg and managed via Discord threads

## Key URLs

| Service | URL | Description |
|---------|-----|-------------|
| Admin Hub | http://localhost:5173 | Tournament management dashboard |
| API | http://localhost:8000 | REST API + WebSocket |
| OBS Overlay | http://localhost:8000/obs/{name} | Browser source for OBS |

## Stopping

```bash
python stop.py
```
