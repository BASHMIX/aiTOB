# US1 provider import evidence

The provider-neutral resolver and exact scope adapters were verified with fake
Start.gg and Challonge clients:

```text
python -m pytest -p no:cacheprovider backend/tests/test_provider_discovery.py -q
```

Result: **8 passed**. Coverage includes full Start.gg Event path preservation,
single and multi-Event behavior, safe locator rejection, exact Challonge
bracket selection, freshness, and capability safety. Draft resolution and
scope-selection endpoints require `If-Match`/revision and retain the existing
draft when provider resolution fails.
