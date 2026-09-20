# Tournament setup rollout runbook

1. Keep `TOURNAMENT_SETUP_WIZARD_ENABLED=false` while the feature-003
   PostgreSQL/workspace ownership gate is incomplete.
2. Enable draft creation only after migration receipts, secret-redaction tests,
   and no-automatic-DQ regression tests pass.
3. Reconcile provider snapshots before retrying an unknown external outcome.
   A failed or timed-out provider start is never retried blindly.
4. Rotate a workspace AI key through the write-only connection endpoint. A
   missing or wrong encryption service key fails closed; the tournament remains
   usable in manual mode.
5. Pause activation/registration/provider-start flags to stop new effects,
   drain the durable outbox, inspect readiness, then resume after correction.
6. Rollback local activation by pausing workers and retaining the materialized
   tournament/draft for review. Existing overlay asset URLs are preserved.

Remote Start.gg and Challonge bracket-start mutation is currently unavailable
because no documented write contract has been verified. Organizers start the
bracket in the provider UI and use Recheck in the wizard.
