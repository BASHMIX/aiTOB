"""Verify workspace-owned tournament-provider credentials.

Provider credentials are BYOC: the workspace owner supplies a credential issued
by the provider, and aiTOB derives the provider identity from that credential.
Callers must complete this network verification before opening a database
transaction or persisting any secret.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


STARTGG_API_URL = "https://api.start.gg/gql/alpha"
CHALLONGE_ME_URL = "https://api.challonge.com/v2.1/me.json"


class ProviderCredentialError(RuntimeError):
    """A credential could not be verified without exposing provider details."""


@dataclass(frozen=True)
class VerifiedProviderCredential:
    provider_type: str
    external_account_id: str
    display_name: str
    secret_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


async def verify_provider_credential(
    provider_type: str,
    credential: str,
    *,
    http: httpx.AsyncClient | None = None,
) -> VerifiedProviderCredential:
    """Return the provider-owned identity proven by ``credential``.

    The credential is used only in the outbound authorization header and is
    never included in errors, metadata, or the returned identity projection.
    """

    provider = str(provider_type or "").strip().lower()
    secret = str(credential or "").strip()
    if provider not in {"startgg", "challonge"}:
        raise ProviderCredentialError("Unsupported tournament provider.")
    if not secret:
        raise ProviderCredentialError("A provider credential is required.")

    owns_http = http is None
    client = http or httpx.AsyncClient(timeout=20.0)
    try:
        if provider == "startgg":
            response = await client.post(
                STARTGG_API_URL,
                json={
                    "query": (
                        "query AitobVerifyCredential { currentUser { id name slug "
                        "player { gamerTag } } }"
                    )
                },
                headers={
                    "Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json",
                },
            )
            if response.is_error:
                raise ProviderCredentialError(
                    "Start.gg rejected this API token. Generate a token from the account that manages the tournament."
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise ProviderCredentialError("Start.gg returned an invalid credential response.") from exc
            if payload.get("errors"):
                raise ProviderCredentialError(
                    "Start.gg rejected this API token or it cannot read the account identity."
                )
            identity = (payload.get("data") or {}).get("currentUser") or {}
            external_id = str(identity.get("id") or "").strip()
            player = identity.get("player") or {}
            display_name = str(
                player.get("gamerTag") or identity.get("name") or identity.get("slug") or ""
            ).strip()
            if not external_id or not display_name:
                raise ProviderCredentialError("Start.gg returned no account identity for this token.")
            metadata = {
                "identity_verified": True,
                "identity_source": "provider_credential",
            }
            if identity.get("slug"):
                metadata["provider_slug"] = str(identity["slug"])
            return VerifiedProviderCredential(
                provider_type=provider,
                external_account_id=external_id,
                display_name=display_name,
                secret_type="access_token",
                metadata=metadata,
            )

        response = await client.get(
            CHALLONGE_ME_URL,
            headers={
                "Authorization": secret,
                "Authorization-Type": "v1",
                "Accept": "application/json",
                "Content-Type": "application/vnd.api+json",
            },
        )
        if response.is_error:
            raise ProviderCredentialError(
                "Challonge rejected this API key. Generate a key from the account that manages the tournament."
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderCredentialError("Challonge returned an invalid credential response.") from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        attrs = (data or {}).get("attributes") if isinstance(data, dict) else {}
        external_id = str((data or {}).get("id") or "").strip()
        display_name = str(
            (attrs or {}).get("username")
            or (attrs or {}).get("name")
            or (attrs or {}).get("email")
            or ""
        ).strip()
        if not external_id or not display_name:
            raise ProviderCredentialError("Challonge returned no account identity for this API key.")
        return VerifiedProviderCredential(
            provider_type=provider,
            external_account_id=external_id,
            display_name=display_name,
            secret_type="api_key",
            metadata={
                "identity_verified": True,
                "identity_source": "provider_credential",
            },
        )
    except httpx.HTTPError as exc:
        raise ProviderCredentialError(
            f"{provider_type_label(provider)} could not be reached to verify this credential."
        ) from exc
    finally:
        if owns_http:
            await client.aclose()


def provider_type_label(provider_type: str) -> str:
    return "Start.gg" if provider_type == "startgg" else "Challonge"
