# Foundation verification

Executed with the isolated repository virtualenv and writable pytest temp directory:

```text
python -m pytest -p no:cacheprovider backend/tests/test_tournament_setup_schema.py backend/tests/test_provider_discovery.py backend/tests/test_workspace_ai_credentials.py backend/tests/test_no_automatic_dq.py -q
```

Result: **13 passed, 4 skipped**. PostgreSQL contract cases are skipped when
`AITOB_PG_TEST_URL` is not configured; the local schema migration, provider
locator, workspace AI redaction/isolation, and no-automatic-DQ checks pass.

Additional integration redaction and legacy AI suites pass independently:

```text
backend/tests/test_tournament_setup_redaction.py backend/tests/test_integration_accounts.py
```

Result: **18 passed** (the focused redaction run is 10 passed when provider
discovery fixtures are included).
