# Disposable live-provider test runbook

Use this runbook only with a disposable PostgreSQL database, test Discord guild,
and test provider brackets. Default CI must not contact an external provider.

## Safety gates

- Set `DATABASE_URL` to the disposable acceptance database.
- Set `AITOB_ALLOW_LIVE_TESTS=true` only for the live run.
- Store provider credentials through the Workspace integration UI. Discord uses
  the one platform-managed application: keep its bot token, client ID, and OAuth
  client secret in the deployment secret store, never in a customer Workspace.
- Confirm the Start.gg or Challonge bracket can be reset without affecting a
  real event.
- Keep automatic and AI-selected DQ disabled.

Start the stack with `python run.py` and stop it with `python stop.py`. API
readiness is available at `/readiness`.

## Start.gg acceptance matrix

Use a bracket with fresh, identifiable sets. Start the wave in Start.gg, then
verify each case independently.

### Both entrants attend

1. Call the set and verify aiTOB records the provider call/deadline projection.
2. Mark entrant 1 present. The match may be protected remotely, but the
   platform `broadcast_state` must not become `live` yet.
3. Mark entrant 2 present. The platform must move `broadcast_state` to `live`
   automatically.
4. Submit a valid score through the authorized result flow.
5. Re-read Start.gg and verify the provider-completed set, winner, score, and
   local reconciliation agree.

### Exactly one entrant attends or the other withdraws

1. Mark only the attendee `present`; optionally mark the other entrant
   `withdrawn` from Discord or the organizer match card.
2. Verify withdrawal alone does not fabricate a winner or complete the set.
3. Wait for the provider deadline. Run the verified single-player DQ resolution
   path only after that deadline.
4. Re-read Start.gg and verify the attendee advanced and the local projection
   reflects the provider result.

### Neither entrant attends

1. Call the set with neither entrant present. Do not send a winner or a local
   Double-DQ mutation.
2. Wait through the Start.gg DQ window plus the configured reconciliation grace.
3. Re-read the set. Start.gg must own the DQ result and bracket progression.
4. If the state is unchanged, schedule another read after the additional grace
   interval. Escalate after the bounded retries; do not invent progression.

## Challonge acceptance matrix

- Submit one normal score and verify the provider result after reconciliation.
- DQ entrant 1 and entrant 2 in separate resettable sets. The loser score is
  `-1` and the advancing entrant score is `0`.
- Confirm the match card never offers Double-DQ for Challonge.

## Outage and unknown-outcome recovery

1. Interrupt provider connectivity after a durable command is recorded.
2. Verify an unknown mutation outcome is not blindly resent.
3. Restore connectivity and run reconciliation.
4. Confirm the command reaches acknowledged/completed or `needs_review`, with no
   duplicate external effect.

## Diagnostics

Inspect recent Hub commands against the configured PostgreSQL database:

```powershell
python -c "import os,psycopg; c=psycopg.connect(os.environ['DATABASE_URL']); print(c.execute('SELECT id,status,command_text FROM hub_commands ORDER BY id DESC LIMIT 10').fetchall()); c.close()"
```

Record only timestamps, provider IDs safe for the test environment, state
transitions, and redacted response categories. Never record access tokens,
session cookies, player private data, or full upstream error bodies.

## Two-tenant Discord isolation acceptance

Use two test accounts, two Workspaces, and two Discord guilds. The same managed
aiTOB application must be installed in both guilds.

1. Account A installs guild A, selects channel A, sends a test message, and
   materializes tournament A. Repeat independently for account/guild/channel B.
2. Verify each Connections page lists only its own installation and named
   channels. Cross-Workspace account and destination IDs must return not found.
3. Call one match in each tournament. Each message and thread must appear only
   in its bound guild/channel and use that tournament's players.
4. From guild A, try an organizer command in channel B and an unbound channel.
   Both attempts must fail closed. Repeat in the opposite direction.
5. Verify a user without Manage Server cannot install/rebind the bot and a user
   without the aiTOB organizer permission cannot execute organizer commands.
6. Record redacted guild/channel IDs and delivery occurrence IDs as evidence;
   never record OAuth codes, tokens, session cookies, or message contents with
   private player data.

## Production backup and restore gate

Before deployment, normalize the ignored environment and require a clean check:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_production_env.py
.\.venv\Scripts\python.exe scripts\prepare_production_env.py --check
docker compose --env-file .env.production config --quiet
```

Create a PostgreSQL custom-format backup and its SHA-256 manifest:

```powershell
.\.venv\Scripts\python.exe scripts\backup_database.py --output-dir .backups
```

Restore that exact artifact to an explicitly named disposable database, run the
normal application migrations there, and execute smoke queries before cutover:

```powershell
.\.venv\Scripts\python.exe scripts\restore_database.py .backups\<backup>.dump `
  --manifest .backups\<backup>.dump.manifest.json `
  --postgres-target postgresql://.../aitob_restore_drill
```

Never pass the production database as the restore target. Delete the disposable
restore database only after confirming its resolved name is the intended drill
database.

## Results Media and OBS Overlay acceptance matrix

Verify static exports, live broadcast sequences, and presentation isolation in a disposable environment.

### Final Standings & Immutable Versioning
1. Complete a test tournament in Start.gg or Challonge with at least 8 entrants.
2. In aiTOB, open **Results Studio** (`/admin/results`).
3. Click **Refresh Results**. Confirm `Provider Final` badge appears and entrant standings are frozen with observation hash.
4. Verify preflight warnings identify any missing avatar or character media.

### Static 1080p Media Export & Audit Receipts
1. In **Results Studio**, select the **Champion Focus** template.
2. Click **Export PNG**.
3. Confirm unscaled 1920x1080 PNG is generated and downloaded with a valid filename (e.g., `<slug>-<event>-top8-standings.png`).
4. Inspect PostgreSQL `results_media_outputs` table: verify output kind is `static`, `export_sha256` is recorded, and byte size matches downloaded asset.

### Live Results Overlay & Broadcast Sequence Controls
1. Bind the media output to an active station: in Station Settings or Results Studio, bind the generated output.
2. Open the station OBS browser source at `/obs/{station_id}/view` in an external browser window.
3. Open **Results Overlay Controls** in the operator panel.
4. Click **Take Live**: verify the browser source transitions from blank/match to the frozen results scene at cue 0.
5. Click **Next** / **Previous**: verify card highlight and reveal advance smoothly through placements.
6. Click **Hold**: verify sequence pause. Click **Restart**: verify sequence rewinds to first placement.
7. Click **Clear**: verify scene clears cleanly without tearing or leaking state into active match overlays.

### Operator Recovery & Service Restart
1. While an overlay sequence is `live` at cue 4, restart the backend API service (`python stop.py`, `python run.py`).
2. Refresh the OBS browser page: verify it queries `GET /obs/{station_id}/data` and reconstructs `projection_kind: tournament_results` at cue 4 without losing place.
3. Re-open operator controls: verify current revision is fetched and subsequent commands execute without revision conflict.

### Entrant Presentation Correction & Profile Promotion
1. In Participants & Overrides, edit a top entrant's featured character for the current event. Select `Event-only override` and save.
2. Verify only the current tournament's results preview reflects the new character; Player Archive profile default character remains unchanged.
3. Edit the entrant again, select `Update Player Profile (Promote to Player Archive)`, and save.
4. Confirm Player Archive is updated and an audit event with action `player_profile.promote_override` is recorded.
5. In Results Studio, verify the previously frozen Result Version remains unchanged until **Refresh Results** is clicked.
