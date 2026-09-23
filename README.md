# aiTOB

aiTOB is a tournament operations platform that combines a FastAPI API, a
Discord bot, and a React/Vite organizer interface. It integrates with Start.gg
and Challonge while keeping PostgreSQL as the only operational data store.

## Runtime

The local stack contains three processes managed by `run.py`:

- API: FastAPI on `http://127.0.0.1:8000`
- BOT: Discord bot and durable Hub-command consumer
- VITE: React development server on `http://127.0.0.1:5173`

PostgreSQL is mandatory. Set `DATABASE_URL` before starting any process; there
is no embedded-database fallback.

```powershell
Copy-Item .env.example .env
# Set DATABASE_URL and the required credentials in .env.
pip install -r requirements.txt
Set-Location frontend-react
npm install
Set-Location ..
python run.py
```

Stop the three local processes with:

```powershell
python stop.py
```

For containers, populate `.env.production`, including `POSTGRES_PASSWORD` and
the encryption keys, then run:

```powershell
docker compose --env-file .env.production up --build
```

## Tests

Repository tests create and destroy isolated PostgreSQL databases. Point
`AITOB_PG_TEST_URL` at a disposable local PostgreSQL server; never use a
production or shared application database.

```powershell
$env:AITOB_PG_TEST_URL = 'postgresql://aitob:password@127.0.0.1:5433/aitob_test'
python -m pytest backend/tests -q

Set-Location frontend-react
npm test
npm run build
```

External-provider tests are disabled by default. Enable them only against
explicitly disposable provider resources with `AITOB_ALLOW_LIVE_TESTS=true`.

## Current operating rules

- PostgreSQL owns all runtime, test, backup, restore, and maintenance state.
- One platform-managed Discord application serves every connected server.
  `DISCORD_BOT_TOKEN` is a deployment secret, never a customer credential.
  Runtime effects resolve `guild → workspace` and then the tournament's ready
  channel binding; missing or ambiguous routes fail closed.
- Account authentication uses an HttpOnly session cookie. The old Hub-password
  bridge is disabled unless `AITOB_LEGACY_HUB_PASSWORD_COMPAT=true` is set for a
  reviewed compatibility window.
- A provider is the source of truth for bracket progression. aiTOB requests
  actions and then reconciles the provider state; it does not invent a winner.
- Start.gg attendance is tracked independently per entrant as `present` or
  `withdrawn`. Both present moves the Hub/broadcast state to `live`
  automatically. If neither attends by the provider window, Start.gg owns the
  Double-DQ result. Exactly one attendee may be advanced only through the
  verified single-player DQ path after the deadline.
- Challonge supports organizer-approved single-player DQ only. The UI must not
  offer Double-DQ for a Challonge match.
- `docs/workflows.json` is the executable local match-transition definition.
  Provider state, Hub lifecycle, and broadcast state are separate axes.
- Player Profiles & Presentation: `Player Archive` is the sole reusable player
  record, workspace-scoped in PostgreSQL. Tournament registration creates or
  reuses that record by workspace Discord ID, then stores only a profile reference
  on the enrollment and entrant link. Entrant overrides remain scoped per tournament
  and event. The v1 presentation hook (`/api/player-profiles/presentation/v1`)
  provides field-level provenance (`entrant_override` → `player_profile` → `provider_snapshot` → `placeholder`).
- Strict OBS Boundary: Live broadcast overlays (`/obs/*`), `broadcast_projection.py`,
  station projections, and provider bracket synchronization do NOT consume the
  new player presentation hook in v1; their independent pipelines remain unchanged.

## Source map

- `backend/api/main.py`: API entry point and WebSockets
- `backend/core/database.py`: PostgreSQL repositories and initialization
- `backend/core/database_schema.py`: schema definitions
- `backend/core/match_state.py`: Hub lifecycle rules
- `backend/core/match_attendance.py`: per-entrant attendance commands
- `backend/core/providers/`: Start.gg and Challonge adapters
- `frontend-react/`: organizer UI and OBS views
- `docs/LIVE_TEST_RUNBOOK.md`: manual disposable-environment smoke tests
- `specs/002-challonge-support/phase-11-legacy-removal-plan.md`: remaining
  provider-contract consolidation work

Historical embedded-database migration guides, generated evidence, and obsolete
architecture walkthroughs were intentionally removed. Git history remains the
place to inspect those retired implementation states.
