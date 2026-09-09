from __future__ import annotations

import pytest

from backend.core.providers.challonge.client import ChallongeClient, ChallongeError, ChallongeRateLimitError


class _Response:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.content = b"{}"
        self.is_error = status_code >= 400

    def json(self):
        return self._payload


class _Http:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return next(self.responses)


@pytest.mark.asyncio
async def test_client_uses_header_auth_and_never_places_key_in_url(monkeypatch):
    client = ChallongeClient(api_key="secret-key")
    http = _Http([_Response(payload={"data": {"id": "1"}})])
    monkeypatch.setattr(client, "_client", lambda: _resolved(http))
    monkeypatch.setattr(client, "_record_usage", _noop)
    monkeypatch.setattr(client, "_headers", _headers)

    await client.get_tournament("18449397", "fnc-jo")
    _, url, kwargs = http.calls[0]

    assert url.endswith("/tournaments/18449397.json")
    assert "secret-key" not in url
    assert kwargs["params"] == {"community_id": "fnc-jo"}
    assert kwargs["headers"]["Authorization"] == "secret-key"


@pytest.mark.asyncio
async def test_client_paginates_and_sends_conditional_headers(monkeypatch):
    client = ChallongeClient(api_key="secret")
    http = _Http([
        _Response(payload={"data": [{"id": str(i)} for i in range(100)]}),
        _Response(payload={"data": [{"id": "100"}]}),
    ])
    monkeypatch.setattr(client, "_client", lambda: _resolved(http))
    monkeypatch.setattr(client, "_record_usage", _noop)
    monkeypatch.setattr(client, "_headers", _headers)

    rows = await client.list_all("/tournaments.json", params={"community_id": "fnc-jo"}, if_none_match="etag-1")

    assert len(rows) == 101
    assert [call[2]["params"]["page"] for call in http.calls] == [1, 2]
    assert http.calls[0][2]["headers"]["If-None-Match"] == "etag-1"


@pytest.mark.asyncio
async def test_429_is_safe_redacted_and_does_not_leak_token(monkeypatch):
    secret = "secret-token"
    client = ChallongeClient(api_key=secret)
    http = _Http([_Response(status_code=429, headers={"Retry-After": "60"})])
    monkeypatch.setattr(client, "_client", lambda: _resolved(http))
    monkeypatch.setattr(client, "_record_usage", _noop)
    monkeypatch.setattr(client, "_headers", _headers)

    with pytest.raises(ChallongeRateLimitError) as exc:
        await client.get_tournament("18449397")

    assert secret not in str(exc.value)
    assert client.rate_limited_until > 0


@pytest.mark.asyncio
async def test_error_body_is_not_reflected_into_an_exception(monkeypatch):
    secret = "secret-token"
    client = ChallongeClient(api_key=secret)
    http = _Http([_Response(status_code=500, payload={"errors": [{"detail": f"Bearer {secret}"}]})])
    monkeypatch.setattr(client, "_client", lambda: _resolved(http))
    monkeypatch.setattr(client, "_record_usage", _noop)
    monkeypatch.setattr(client, "_headers", _headers)

    with pytest.raises(ChallongeError) as exc:
        await client.get_tournament("18449397")

    assert str(exc.value) == "Challonge rejected the request."
    assert secret not in str(exc.value)


async def _resolved(value):
    return value


async def _noop(*_args, **_kwargs):
    return None


async def _headers():
    return {"Authorization": "secret-key", "Accept": "application/json"}
