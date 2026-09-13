# Quickstart: Tournament Setup Wizard

This guide describes the intended development and acceptance workflow after the
plan is decomposed with `/speckit-tasks`. It does not authorize live provider,
Discord, or AI mutations.

## 1. Prerequisite gates

Before implementing or enabling activation, verify feature 003 has completed the
PostgreSQL/workspace identity gates:

- API, bot, and workers require `DATABASE_URL` and use PostgreSQL only.
- `AITOB_ENFORCE_WORKSPACE_NOT_NULL=true` passes startup checks.
- Tournaments have stable UUID identity and workspace-scoped slug lookup.
- Integration accounts, assets, commands, usage, workers, and WebSockets are
  non-null workspace owned.
- No runtime provider, Discord, or AI path silently falls back to global settings.

Use an ignored local environment file or secret manager. Required service keys
include `AITOB_INTEGRATION_MASTER_KEY`; the legacy
`AITOB_AI_SERVICE_MASTER_KEY` is needed only while performing an explicit legacy
AI assignment. Do not place real API keys in fixtures, shell history, docs, or
committed files.

## 2. Install and initialize

```powershell
uv sync --dev
Set-Location frontend-react
npm install
Set-Location ..
docker compose --env-file .env.production up -d postgres
.\.venv\Scripts\python.exe -c "import asyncio; from backend.core.database import init_db; asyncio.run(init_db())"
```

`DATABASE_URL` must select a disposable/local PostgreSQL database. Runtime
startup must fail instead of falling back to SQLite when it is missing or invalid.

## 3. Implement in dependency order

1. Remove automatic-DQ behavior/defaults/UI and establish the tournament UUID
   prerequisite.
2. Add PostgreSQL schema/repositories and migration receipts.
3. Add workspace Gemini/OpenAI connections and assistant config/usage scoping.
4. Add exact provider resolution and preview.
5. Add versioned drafts, readiness, materialization, and activation/outbox.
6. Add managed Discord onboarding, discovery, permissions, templates, and
   multi-workspace routing.
7. Replace the global bot registration flow with tournament-scoped windows,
   exact-scope roster sync, canonical Prefix/Gamertag fields, configurable exact
   Gamertag/nickname verification, optional Start.gg bio proof, manual Discord ID
   linking from entrant rows, enrollment state, and image policy.
8. Add brand projection to Hub, Editor, and overlay.
9. Add the five-step React wizard behind a disabled-by-default feature flag.

Do not let route order define security. Every service/repository method accepts
or derives the trusted workspace and constrains every referenced child resource
to it.

## 4. Backend tests

Fast local suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Required PostgreSQL suite uses a disposable administrator DSN; it must never
target the application database:

```powershell
$env:AITOB_PG_TEST_URL = 'postgresql://…/aitob_wizard_test'
.\.venv\Scripts\python.exe -m pytest backend/tests --postgres -q
```

The feature-specific acceptance suite must cover:

- Start.gg Event URL/slug preserves the exact Event; multi-Event tournament input
  requires a choice and never uses `events[0]`.
- Challonge resolution previews one bracket without persisting it.
- Draft reload, OAuth return, stale revision `409`, permission revocation, and
  idempotent materialization/activation.
- Two workspaces may reference the same remote Event but cannot read/use each
  other’s draft, account, key, configuration, usage, asset, or Discord binding.
- Key add/replace/test/disable/remove and classified Gemini/OpenAI failures use
  fake adapters by default. CI makes no paid completion.
- Parallel usage reservations stay within each workspace’s current limits.
- Missing/wrong master key exposes no plaintext and fails only credential/AI
  actions; draft/manual operation remains available.
- A crash after activation commit but before initial sync is recovered by one
  idempotent outbox effect.
- Provider-verified or explicitly organizer-confirmed Start-in-wave waits through
  prestart, then sends one Discord call for every real provider-owned `CALLED`
  transition, including the first wave; Dashboard/provider concurrency, duplicate
  snapshots, and worker restart produce no duplicate call.
- Player registration start/confirmation/upload obey server-side opening and
  closing instants, including a challenge that reaches registration close;
  organizer corrections remain audited and available after close.
- When enabled, optional Start.gg bio proof stores no plaintext code or profile
  bio, is bound to the exact Workspace/tournament/Event/player/profile, and cannot
  be replayed.
- Exact Event/bracket membership uses provider entrants plus the configured exact
  Gamertag/Discord-name or bot-managed server-nickname rule. Normalized collisions
  become review cases; optional provider registration stays visibly unmatched.
- Challonge keeps the exact Gamertag/nickname rule and never renders a bio option.
- Manual Discord ID add/edit/unlink resolves a non-bot user in the selected guild,
  rejects malformed/wrong-guild/duplicate IDs, and reconciles future routing.
- Canonical player projections use `prefix` and `gamertag`; legacy player `team`
  and `name` exist only at the documented compatibility boundary.
- Player images satisfy disabled/optional/required policy through deterministic
  validation without a global or hidden Gemini/OpenAI request.
- Duplicate roster snapshots, bot interactions, scheduled open/close jobs, and
  role grants remain idempotent across restart and two simultaneous tournaments.
- Attendance timeout/restart/Discord/AI paths never call automatic DQ; reminders
  and human escalation still occur.

Search test output, captured logs, safe database columns, API responses, audit,
error telemetry, exports, drafts, and templates for the submitted synthetic
secret; the count must be zero.

## 5. Frontend tests and build

```powershell
Set-Location frontend-react
npm run test
npm run build
Set-Location ..
```

Frontend tests cover keyboard completion, error focus, Arabic RTL, supported
mobile width, autosave/retry/conflict, reload/OAuth restore, secret input clearing,
provider Event choice, optional Discord/AI skip, and distinct Save draft / Save
tournament / Activate aiTOB labels.

## 6. Local manual smoke with fakes

Start the three services only after schema initialization:

```powershell
python run.py
```

Use local fake adapters or recorded redacted fixtures. Then:

1. Sign in as Workspace A owner and create a draft.
2. Resolve a Start.gg Event slug and verify its exact Event is selected.
3. Resolve a multi-Event tournament and verify Next remains blocked until choice.
4. Add local name/logo/color and confirm the Editor/overlay preview projection.
5. Configure assisted operation and confirm the summary contains reminders and
   human escalation, with no automatic DQ.
6. Skip Discord and AI, save the tournament, and activate local management.
7. Create another draft, attach fake Discord resources and a fake Gemini/OpenAI
   connection, preview templates, test the connection, and activate.
8. Configure a registration channel, window, required provider membership, and
   optional image. Verify before/after-window rejection and one opening message.
9. Register fake Start.gg entrants through an exact Gamertag match and a simulated
   server nickname change; optionally enable a bio code, confirm exact Event
   membership, keep/replace an image, and inspect Ready in the organizer view.
10. Repeat with bio disabled, provider registration optional, and a Challonge
    entrant using the same Gamertag/nickname rule; simulate a duplicate Gamertag
    and confirm it moves to organizer review.
11. From a participant row, add a valid sample Discord ID, replace it, and unlink
    it; verify malformed, bot, wrong-guild, and already-linked IDs never become
    Ready and each accepted change has one audit event.
12. Sign in as Workspace B and verify Workspace A IDs behave as not found.
13. Reload and resume a partial draft; simulate OAuth return and a two-tab revision
   conflict.
14. Confirm Start-in-wave displays Unknown/Unsupported and offers no remote
    toggle; explicitly confirm it and verify the UI labels the source Organizer.
15. With a verified-enabled or organizer-confirmed fake, move from prestart to the
    first `CALLED` snapshot and confirm those players are called once. Repeat the
    same transition through Dashboard/provider concurrency and confirm no second
    delivery.

Stop services with:

```powershell
python stop.py
```

## 7. Optional live connection smoke

Live smoke is manual and opt-in, using disposable test accounts/guild/brackets.
It must remain outside default CI. Record safe outcome categories only.

- Start.gg: authorize, resolve a test Event, read its entrants, complete a fresh
  bio challenge, and run remote-start preflight/start only against a disposable
  bracket through the authorized adapter. Do not infer Start-in-wave through a
  match mutation.
- Challonge: authorize, refresh an expiring token, list/resolve entrants, and run
  remote-start preflight/start only against a disposable bracket through the
  authorized adapter.
- Discord: install in a test guild, enumerate channels/roles, and verify effective
  permissions. Send only to an explicitly approved test channel.
- Gemini/OpenAI: add a disposable restricted key and run the explicit minimal
  connection test. Confirm the external provider account owns all usage/cost.

Both remote-start adapters require separate documented or provider-authorized
capability, preflight, confirmation, idempotency, resulting-state verification,
and reconciliation acceptance. Missing either contract blocks Epic completion.

## 8. Cutover evidence

Before enabling the wizard activation flag, attach:

- PostgreSQL migration/constraint report and backup/restore rehearsal;
- two-workspace isolation and bot-routing results;
- secret redaction/encryption failure results;
- provider resolver and AI failure-classification results;
- activation/outbox crash recovery evidence;
- image/overlay before-and-after comparison;
- keyboard/RTL/mobile acceptance;
- no-automatic-DQ and human result-approval evidence;
- registration-window, exact entrant-link, hashed challenge, image validation,
  two-tournament routing, and idempotent schedule/role evidence;
- explicit status of any legacy AI/Discord records: assigned, quarantined, or
  purged, never an undisclosed fallback.

Review unresolved/unknown external effects before worker resume. A database
rollback cannot undo an accepted provider change or Discord delivery.
