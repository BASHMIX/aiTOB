# US4 workspace AI BYOK evidence

Focused credential, config, and adapter suites:

```text
python -m pytest -p no:cacheprovider backend/tests/test_workspace_ai_credentials.py backend/tests/test_workspace_ai_config.py backend/tests/test_workspace_ai_adapters.py -q
```

Result: **20 passed**. Gemini and OpenAI keys are encrypted through the
workspace integration account store, projections are write-only, provider
selection and usage reservations are workspace-scoped, and adapter failures
are classified without retaining upstream response text. Assistant requests
require `assistant.use` and do not use the legacy service/global key path.
