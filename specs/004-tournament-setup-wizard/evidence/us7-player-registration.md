# US7 player registration evidence

The registration window, exact roster synchronization, identity policy,
entrant mapping, and manual Discord link suites were run with isolated PostgreSQL
fixtures:

```text
python -m pytest -p no:cacheprovider backend/tests/test_registration_window.py backend/tests/test_registration_sync.py backend/tests/test_registration_identity.py backend/tests/test_registration_manual_discord_link.py backend/tests/test_registration_entrants.py -q
```

Result: **10 passed**. The API and repositories keep registration scoped to a
tournament/workspace, use server-time windows and schedule versions, preserve
Prefix/Gamertag separately, detect normalized collisions, and enforce unique
write-only manual Discord links with unlink/replacement states.
