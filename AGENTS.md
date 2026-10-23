# AI Tournament Organizer Bot

Read `README.md` before changing the repository. It is the canonical runtime,
setup, testing, and operating-policy reference.

## Non-negotiable architecture

- Python 3.12+, FastAPI, discord.py, React/Vite, and PostgreSQL 17+.
- `DATABASE_URL` is required. Do not add an embedded database, fallback store,
  dual write, or file-backed test fixture.
- `run.py` starts API, BOT, and VITE; `stop.py` stops their process trees.
- Tests require `AITOB_PG_TEST_URL` pointing to a disposable PostgreSQL server.
- Browser authentication is an HttpOnly account session. Treat Hub-password
  headers as an explicitly enabled compatibility boundary only.
- Provider state is authoritative for bracket progression. Keep provider state,
  Hub match lifecycle, and `broadcast_state` separate.
- Never fabricate a Start.gg winner. Start.gg owns native Double-DQ; Challonge
  offers only organizer-approved single-player DQ.

## Key locations

- API and WebSockets: `backend/api/`
- PostgreSQL repositories/schema: `backend/core/database.py` and
  `backend/core/database_schema.py`
- Provider contracts/adapters: `backend/core/contracts/` and
  `backend/core/providers/`
- Match lifecycle/attendance: `backend/core/match_state.py` and
  `backend/core/match_attendance.py`
- Discord bot: `backend/bot/`
- Frontend: `frontend-react/`
- Executable workflow definition: `docs/workflows.json`
- Provider consolidation record: `specs/002-challonge-support/phase-11-legacy-removal-plan.md`
- Player-profile design: `specs/005-player-profiles/plan.md`

## Commands

```powershell
python run.py
python stop.py

$env:AITOB_PG_TEST_URL = 'postgresql://user:password@127.0.0.1:5433/disposable_db'
python -m pytest backend/tests -q

Set-Location frontend-react
npm test
npm run build
```

Preserve unrelated user changes. Use PostgreSQL-native concurrency and
transactions, keep external calls outside database transactions, and run the
focused tests plus the frontend production build for affected behavior.

<!-- SPECKIT START -->
## Active Spec Kit feature

- Tournament Results Media: `specs/006-results-media/plan.md`
<!-- SPECKIT END -->
