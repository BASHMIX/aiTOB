"""Reusable hermetic provider fixtures for V2 contract tests.

They are deliberately transport-only and never contain a credential or live URL.
"""
import pytest


@pytest.fixture
def provider_snapshot_fixture() -> dict:
    return {
        "tournament_id": "fixture-tournament",
        "revision": "fixture-revision-1",
        "matches": [
            {
                "id": "fixture-match-1",
                "state": "open",
                "entrant_ids": ["entrant-1", "entrant-2"],
            }
        ],
    }
