"""Minimal current Challonge v2.1 JSON:API client.

The legacy FNC integration placed a key in a URL. This client deliberately
uses the documented v1-key headers and never exposes/prints the credential.
"""
from __future__ import annotations
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo
import httpx
import re

BASE_URL = "https://api.challonge.com/v2.1"

class ChallongeError(Exception):
    pass


class ChallongeRateLimitError(ChallongeError):
    def __init__(self, pause_seconds: int):
        self.pause_seconds = pause_seconds
        super().__init__(f"Challonge rate limit reached. Try again in about {pause_seconds} seconds.")


def _retry_at_message(pause_seconds: int) -> str:
    """Format a long provider pause for the Hub without exposing raw seconds."""
    retry_at = datetime.now(timezone.utc) + timedelta(seconds=pause_seconds)
    try:
        retry_at = retry_at.astimezone(ZoneInfo("Asia/Baghdad"))
    except Exception:
        # Baghdad is UTC+03:00 and does not observe daylight saving time.
        retry_at = retry_at.astimezone(timezone(timedelta(hours=3)))
    timezone_label = "Baghdad time"
    hour = retry_at.hour % 12 or 12
    am_pm = "AM" if retry_at.hour < 12 else "PM"
    formatted = (
        f"{retry_at.strftime('%B')} {retry_at.day}, {retry_at.year} "
        f"at {hour}:{retry_at.minute:02d} {am_pm}"
    )
    return (
        "Challonge API quota is exhausted. No action was sent; requests are "
        f"paused until {formatted} ({timezone_label})."
    )


class ChallongeClient:
    def __init__(self, api_key: str | None = None, *, account_id: str | None = None):
        self.api_key = api_key
        self.account_id = account_id
        self._http: httpx.AsyncClient | None = None
        self._rate_limited_until = 0.0

    @property
    def rate_limited_until(self) -> float:
        return self._rate_limited_until

    async def _key(self) -> str:
        if self.api_key:
            return self.api_key
        if not self.account_id:
            raise ChallongeError("Challonge account binding is required.")
        from backend.core.integrations import IntegrationSecretUnavailable, get_challonge_credential
        try:
            self.api_key = await get_challonge_credential(self.account_id, "api_key")
        except IntegrationSecretUnavailable as exc:
            raise ChallongeError("Challonge account credentials are unavailable.") from exc
        if not self.api_key:
            raise ChallongeError("Challonge API key is not configured. Add it in Settings → Connections.")
        return self.api_key

    async def _headers(self) -> dict[str, str]:
        """Prefer a current OAuth token while retaining the v1-key fallback."""
        from .oauth import valid_access_token

        access_token = await valid_access_token(self.account_id)
        if access_token:
            return {
                "Accept": "application/json",
                "Content-Type": "application/vnd.api+json",
                "Authorization-Type": "v2",
                "Authorization": f"Bearer {access_token}",
            }
        key = await self._key()
        return {
            "Accept": "application/json",
            "Content-Type": "application/vnd.api+json",
            "Authorization-Type": "v1",
            "Authorization": key,
        }

    async def _client(self) -> httpx.AsyncClient:
        if not self._http or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def _record_usage(self, method: str, path: str, status_code: int | None) -> None:
        try:
            from backend.core.database import record_provider_api_usage
            workspace_id = None
            if self.account_id:
                from backend.core.integrations import get_integration_workspace_id
                workspace_id = await get_integration_workspace_id(self.account_id)
            await record_provider_api_usage(
                "challonge", method, path, status_code,
                workspace_id=workspace_id,
                provider_account_id=self.account_id,
            )
        except Exception:
            # Usage telemetry must never turn a successful provider call into a
            # failure (e.g. during first-run schema initialization).
            pass

    @staticmethod
    def _safe_resource(value: str, label: str) -> str:
        cleaned = str(value or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", cleaned):
            raise ChallongeError(f"Invalid Challonge {label}.")
        return cleaned

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        payload: dict | None = None,
        if_none_match: str | None = None,
    ) -> dict:
        now = time.monotonic()
        if now < self._rate_limited_until:
            wait_seconds = int(self._rate_limited_until - now) + 1
            if wait_seconds > 3600:
                raise ChallongeError(_retry_at_message(wait_seconds))
            raise ChallongeError(f"Challonge rate limit is active. Try again in about {wait_seconds} seconds.")
        headers = await self._headers()
        if if_none_match:
            headers = {**headers, "If-None-Match": if_none_match}
        try:
            response = await (await self._client()).request(method, f"{BASE_URL}{path}", params=params, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            await self._record_usage(method, path, None)
            raise ChallongeError("Challonge network request failed.") from exc
        await self._record_usage(method, path, response.status_code)
        if response.status_code == 304:
            return {"_not_modified": True}
        if response.status_code == 429:
            # Do not let the background reconciler turn one 429 into dozens of
            # failed requests. Challonge may omit Retry-After for quota limits.
            retry_after = response.headers.get("Retry-After")
            try:
                pause_seconds = max(60, int(retry_after or 900))
            except ValueError:
                pause_seconds = 900
            self._rate_limited_until = time.monotonic() + pause_seconds
            raise ChallongeRateLimitError(pause_seconds)
        if response.status_code in (401, 403):
            raise ChallongeError("Challonge authorization failed or this tournament is inaccessible.")
        if response.status_code == 404:
            # Community-scoped tokens deliberately hide an ungranted community
            # behind a 404. Surface the actionable recovery instead of making
            # organizers hunt for an otherwise valid tournament URL.
            try:
                detail = (response.json().get("errors") or {}).get("detail") or ""
            except Exception:
                detail = ""
            if "Community with the given identifier was not found" in detail:
                raise ChallongeError(
                    "Challonge community access is not granted for this account. "
                    "Reconnect Challonge, select the community checkbox, then authorize again."
                )
            raise ChallongeError("Challonge tournament or match was not found.")
        if response.is_error:
            # Provider error bodies are not a safe user-facing/log-facing contract:
            # a proxy can echo authorization data or an arbitrary user-supplied
            # reference. Keep the adapter boundary deliberately redacted.
            raise ChallongeError("Challonge rejected the request.")
        return response.json() if response.content else {}

    async def list_all(
        self, path: str, *, params: dict | None = None, if_none_match: str | None = None
    ) -> list[dict]:
        output, page = [], 1
        while True:
            query = {**(params or {}), "page": page, "per_page": 100}
            data = await self.request("GET", path, params=query, if_none_match=if_none_match)
            if data.get("_not_modified"):
                return []
            rows = data.get("data") if isinstance(data, dict) else data
            if not isinstance(rows, list): rows = []
            output.extend(rows)
            if len(rows) < 100: break
            page += 1
        return output

    async def get_tournament(
        self, tournament_id: str, community_id: str | None = None, *, if_none_match: str | None = None
    ) -> dict:
        tournament_id = self._safe_resource(tournament_id, "tournament identifier")
        if community_id:
            community_id = self._safe_resource(community_id, "community")
        params = {"community_id": community_id} if community_id else None
        data = await self.request(
            "GET", f"/tournaments/{tournament_id}.json", params=params, if_none_match=if_none_match
        )
        return data if data.get("_not_modified") else (data.get("data") or {})

    async def find_tournament(self, slug: str, subdomain: str | None = None) -> dict | None:
        # v2.1 calls the formerly named subdomain a community_id.
        slug = self._safe_resource(slug, "tournament slug")
        if subdomain:
            subdomain = self._safe_resource(subdomain, "community")
        params = {"community_id": subdomain} if subdomain else None
        rows = await self.list_all("/tournaments.json", params=params)
        wanted = slug.lower()
        for item in rows:
            attrs = item.get("attributes") or {}
            if str(item.get("id")) == slug or str(attrs.get("url") or attrs.get("url_slug") or "").lower() == wanted:
                return item
        return None

    async def participants(self, tournament_id: str, community_id: str | None = None) -> list[dict]:
        return await self.list_all(f"/tournaments/{tournament_id}/participants.json", params={"community_id": community_id} if community_id else None)

    async def matches(self, tournament_id: str, community_id: str | None = None) -> list[dict]:
        return await self.list_all(f"/tournaments/{tournament_id}/matches.json", params={"community_id": community_id} if community_id else None)

    async def update_match(self, tournament_id: str, match_id: str, attributes: dict, community_id: str | None = None) -> dict:
        return (await self.request("PUT", f"/tournaments/{tournament_id}/matches/{match_id}.json", params={"community_id": community_id} if community_id else None, payload={"data": {"type": "Match", "id": str(match_id), "attributes": attributes}})).get("data") or {}

    async def change_tournament_state(self, tournament_id: str, state: str, community_id: str | None = None) -> dict:
        payload = {"data": {"type": "TournamentState", "attributes": {"state": state}}}
        params = {"community_id": community_id} if community_id else None
        return (await self.request("PUT", f"/tournaments/{tournament_id}/change_state.json", params=params, payload=payload)).get("data") or {}
