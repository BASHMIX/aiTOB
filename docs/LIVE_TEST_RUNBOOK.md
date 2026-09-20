# Disposable live-provider test runbook

Use this runbook only with a disposable PostgreSQL database, test Discord guild,
and test provider brackets. Default CI must not contact an external provider.

## Safety gates

- Set `DATABASE_URL` to the disposable acceptance database.
- Set `AITOB_ALLOW_LIVE_TESTS=true` only for the live run.
- Store provider and Discord credentials through the Workspace integration UI;
  do not commit them or paste them into this document.
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
