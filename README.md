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

`run.py` terminates only stale processes that belong to this checkout. It
refuses to kill Docker, WSL relays, or unrelated applications that own a
requested port. To run the source stack beside a Compose API already using
port 8000, select an alternate API port; Vite and the bot inherit it:

```powershell
$env:AITOB_API_PORT = '8001'
python run.py
```

Stop the three local processes with:

```powershell
python stop.py
```

For containers, populate `.env.production`, including the explicit
`AITOB_POSTGRES_DB`, `POSTGRES_PASSWORD`, and the Discord application
credentials, then normalize and validate it without
printing generated encryption keys:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_production_env.py
.\.venv\Scripts\python.exe scripts\prepare_production_env.py --check
```

Register the exact `DISCORD_OAUTH_REDIRECT_URI` in the Discord Developer Portal.
The platform owns `DISCORD_BOT_TOKEN`, `DISCORD_CLIENT_ID`, and
`DISCORD_CLIENT_SECRET`; customers never enter any of them. Then run:

```powershell
docker compose --env-file .env.production up --build
```

### Closed staging onboarding

Keep `ALLOW_PUBLIC_REGISTRATION=false`. A platform administrator opens
**Settings → Account → Closed staging invitations**, enters the company Owner
email and workspace name, then sends the generated one-time link. Accepting the
link creates a separate workspace, Owner membership, and free entitlement in a
single PostgreSQL transaction. It does not add the company to the administrator's
workspace. After sign-in, the company Owner connects its Discord server from
**Connections** and may invite its own staff from **Workspace members**.

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
- Tournament and Organizer Assistant providers are BYOC. A Workspace supplies
  its own Start.gg token, Challonge API key, Gemini key, or OpenAI key through
  **Settings -> Connections**. Tournament-provider identities are read from the
  provider credential instead of being typed by an organizer; credentials are
  encrypted, account-scoped, and never shared across Workspaces. Platform
  deployment variables must not subsidize customer provider usage.
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
- Results Media & Results Studio: Author and publish verified tournament results
  graphics and live OBS sequences at `/admin/results`. Results versions freeze provider
  standings, resolved player presentation, observation hashes, and verification state into
  immutable versions. Static media exports produce unscaled 1080p PNG graphics with
  cryptographic SHA-256 audit receipts. Live broadcast overlays (`/obs/{station_id}/view`)
  project results sessions without an active match, driven by operator sequence controls
  (Take Live, Play All, Next, Previous, Hold, Restart, Clear) with revision monotonicity.
  The overlay editor offers two intentionally separate authoring paths that share
  one Result Card design and renderer:
  - **Add Result Card** creates one freely positioned atomic card inside a
    layout-neutral Results Cards scheduler. Use **Edit Card Design** to arrange
    the bound player layers, then animate the atomic card through the editor's
    standard **Animation** panel used by text, images, and shapes. The Results
    Cards parent owns only Top 8/Top 16/All selection, order, preview transport,
    and **Delay Between Starts**; that delay is a stagger and may overlap cards.
  - **Add Results Group** keeps the preset Board/image-export workflow and the
    established group sequence. It uses the same Result Card design. **Create
    Editable Linked Cards** deliberately converts the current template layout
    into movable cards without copying the shared design.
  Preview-generated cards are runtime-only. Only explicitly inserted or
  materialized linked cards are saved as scene nodes.
- Provider Finality & Featured Characters: Provider state is strictly authoritative;
  Start.gg requires completed event standings, while Challonge requires completed
  tournaments with final ranks. Standings characters represent organizer-selected or profile
  featured artwork and are labeled as such without falsely asserting in-match usage.
  Event-scoped character corrections preserve immutable past versions and require explicit
  promotion to update the Player Archive game profile.

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
