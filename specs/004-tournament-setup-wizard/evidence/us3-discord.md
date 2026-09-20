# US3 Discord evidence

The routing and template boundaries are covered by
`backend/tests/test_discord_routing_wizard.py` and
`backend/tests/test_discord_templates.py` (3 tests). OAuth state is stored as a
short-lived SHA-256 hash bound to workspace, actor, draft and return step; the
callback consumes it once and exposes only an enumerated redirect outcome.
Resource and permission projections contain IDs/labels and safe permission
states only. Message previews and delivery share the same allow-listed renderer.
