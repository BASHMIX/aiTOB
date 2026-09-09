import secrets

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.database import consume_oauth_state, create_oauth_state, init_db
from backend.core.providers.challonge.client import ChallongeClient
from backend.core.providers.challonge import oauth
from backend.core.providers.challonge.provider import ChallongeProvider
from backend.core.contracts import ProviderEntrant, ProviderSetState
from backend.core.providers.challonge.mapper import map_match


@pytest.fixture(autouse=True)
async def initialized_oauth_store():
    """This contract owns its schema instead of relying on test-file order."""
    await init_db()


@pytest.mark.asyncio
async def test_oauth_state_is_single_use_and_provider_scoped():
    state = secrets.token_urlsafe(24)
    await create_oauth_state("challonge", state, 60, account_id="account-fnc")

    assert await consume_oauth_state("challonge", state) == "account-fnc"
    assert await consume_oauth_state("challonge", state) is None


@pytest.mark.asyncio
async def test_oauth_headers_precede_legacy_v1_key(monkeypatch):
    async def token(account_id=None):
        return "oauth-access-token"

    monkeypatch.setattr(oauth, "valid_access_token", token)
    headers = await ChallongeClient("legacy-key")._headers()

    assert headers["Authorization-Type"] == "v2"
    assert headers["Authorization"] == "Bearer oauth-access-token"


@pytest.mark.asyncio
async def test_v1_key_remains_a_fallback_when_oauth_is_not_connected(monkeypatch):
    async def no_token(account_id=None):
        return None

    monkeypatch.setattr(oauth, "valid_access_token", no_token)
    headers = await ChallongeClient("legacy-key")._headers()

    assert headers["Authorization-Type"] == "v1"
    assert headers["Authorization"] == "legacy-key"


def test_oauth_requests_the_community_scope_needed_for_hosted_brackets():
    assert "communities:manage" in oauth.OAUTH_SCOPES.split()


def test_callback_accepts_provider_form_posts_without_a_405():
    response = TestClient(app).post("/api/auth/challonge/callback", data={})

    assert response.status_code == 200
    assert "invalid or has expired" in response.text


@pytest.mark.asyncio
async def test_url_slug_resolves_directly_without_listing_the_community():
    class Client:
        def __init__(self):
            self.requested = None

        async def get_tournament(self, tournament_id, community_id):
            self.requested = (tournament_id, community_id)
            return {"id": "18449397", "attributes": {"name": "FNCTest2026", "url": "ap6fj0k1"}}

        async def find_tournament(self, *_args):
            raise AssertionError("URL resolution must not enumerate community tournaments")

    client = Client()
    result = await ChallongeProvider(client).resolve("https://fnc-jo.challonge.com/ap6fj0k1")

    assert client.requested == ("ap6fj0k1", "fnc-jo")
    assert result["provider_tournament_id"] == "18449397"


@pytest.mark.asyncio
async def test_hidden_community_404_explains_how_to_restore_access(monkeypatch):
    class Response:
        status_code = 404
        is_error = True
        headers = {}
        content = b'{}'

        def json(self):
            return {"errors": {"detail": "Community with the given identifier was not found. Identifier passed was `fnc-jo`"}}

    class Http:
        async def request(self, *_args, **_kwargs):
            return Response()

    async def no_token(account_id=None):
        return "access-token"

    client = ChallongeClient()
    monkeypatch.setattr(oauth, "valid_access_token", no_token)
    monkeypatch.setattr(client, "_client", lambda: _resolved(Http()))

    with pytest.raises(Exception, match="Reconnect Challonge, select the community checkbox"):
        await client.get_tournament("18449397", "fnc-jo")


async def _resolved(value):
    return value


def test_open_challonge_match_is_ready_not_live():
    from backend.core.providers.challonge.state_map import map_state

    assert map_state("open") is ProviderSetState.NOT_STARTED
    assert map_state("complete") is ProviderSetState.COMPLETE


def test_match_mapper_reads_v21_points_by_participant_when_relationships_are_absent():
    entrants = {
        "303608376": ProviderEntrant(id="303608376", name="Snapboom"),
        "303608372": ProviderEntrant(id="303608372", name="LordAhmad"),
    }
    match = map_match(
        {
            "id": "471045156",
            "attributes": {
                "state": "open", "round": 1, "identifier": "A",
                "points_by_participant": [
                    {"participant_id": 303608376, "scores": []},
                    {"participant_id": 303608372, "scores": []},
                ],
            },
        },
        "18449397", entrants, "fnc-jo",
    )

    assert match.entrant1 and match.entrant1.name == "Snapboom"
    assert match.entrant2 and match.entrant2.name == "LordAhmad"
