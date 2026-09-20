"""Shared safe error classification for customer-owned AI adapters."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


FAILURE_CATEGORIES = frozenset({
    "invalid_key",
    "model_unavailable",
    "quota_or_billing",
    "rate_limited",
    "region_restricted",
    "timeout",
    "provider_unavailable",
    "unknown",
})


@dataclass(frozen=True)
class ProviderFailureInfo:
    """Public-safe category for an upstream failure.

    ``detail`` is intentionally absent.  Provider exception text can contain
    request IDs, account identifiers, or credential fragments and therefore
    must not cross this boundary.
    """

    category: str
    safe_message_code: str
    retryable: bool


class AIProviderFailure(RuntimeError):
    """Classified AI failure whose text is safe for logs and API responses."""

    def __init__(self, info: ProviderFailureInfo, *, provider_type: str):
        self.category = info.category
        self.safe_message_code = info.safe_message_code
        self.retryable = info.retryable
        self.provider_type = provider_type
        super().__init__(info.safe_message_code)

    @property
    def failure_category(self) -> str:
        """Compatibility spelling used by health and usage projections."""

        return self.category

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "failure_category": self.category,
            "safe_message_code": self.safe_message_code,
            "retryable": self.retryable,
        }


def _status_code(exc: BaseException) -> int | None:
    """Read a status without serializing the upstream exception."""

    for name in ("status_code", "status", "code"):
        value = getattr(exc, name, None)
        try:
            if value is not None and 100 <= int(value) <= 599:
                return int(value)
        except (TypeError, ValueError):
            continue
    return None


def classify_provider_error(exc: BaseException) -> ProviderFailureInfo:
    """Classify common Gemini/OpenAI failures into a stable safe category.

    Matching uses exception type, status and a lower-cased local string only;
    the string is never returned or persisted.  Unknown failures intentionally
    become ``unknown`` so upstream bodies do not leak through the API.
    """

    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return ProviderFailureInfo("timeout", "ai_timeout", True)

    status = _status_code(exc)
    kind = type(exc).__name__.lower()
    # This string is used only for classification and never appears in the
    # resulting error.  Provider SDKs often put useful status labels here.
    detail = str(exc).lower()
    combined = f"{kind} {detail}"

    if "timeout" in kind or "deadlineexceeded" in kind:
        return ProviderFailureInfo("timeout", "ai_timeout", True)

    if status in {403} and any(
        token in combined
        for token in ("region", "location is not supported", "country is not supported", "not available in")
    ):
        return ProviderFailureInfo("region_restricted", "ai_region_restricted", False)

    if status in {401, 403} or any(
        token in combined
        for token in (
            "invalid api key", "invalid key", "unauthorized", "unauthenticated",
            "authentication", "permission denied", "permissiondenied", "forbidden",
            "invalidauthentication",
        )
    ):
        return ProviderFailureInfo("invalid_key", "ai_invalid_key", False)

    if any(token in combined for token in ("region", "location is not supported", "country is not supported", "not available in")):
        return ProviderFailureInfo("region_restricted", "ai_region_restricted", False)

    if status == 429 or any(
        token in kind for token in ("resourceexhausted", "toomanyrequests")
    ):
        if any(token in combined for token in ("quota", "billing", "insufficient", "exceeded")):
            return ProviderFailureInfo("quota_or_billing", "ai_quota_or_billing", False)
        return ProviderFailureInfo("rate_limited", "ai_rate_limited", True)

    if any(token in combined for token in ("rate limit", "rate-limit", "too many requests")):
        return ProviderFailureInfo("rate_limited", "ai_rate_limited", True)

    if any(token in combined for token in ("quota", "billing", "insufficient funds", "payment required")):
        return ProviderFailureInfo("quota_or_billing", "ai_quota_or_billing", False)

    if status == 404 or kind in {"notfound", "modelnotfound"} or any(token in combined for token in ("model not found", "model unavailable", "unknown model", "invalid model", "does not exist")):
        return ProviderFailureInfo("model_unavailable", "ai_model_unavailable", False)

    if status in {408, 504} or any(token in combined for token in ("timed out", "timeout", "deadline exceeded")):
        return ProviderFailureInfo("timeout", "ai_timeout", True)

    if status is not None and status >= 500 or any(
        token in combined
        for token in ("connection refused", "connection reset", "network", "dns", "temporarily unavailable", "service unavailable", "transport")
    ):
        return ProviderFailureInfo("provider_unavailable", "ai_provider_unavailable", True)

    return ProviderFailureInfo("unknown", "ai_provider_unknown", False)


def raise_classified(exc: BaseException, *, provider_type: str) -> None:
    """Raise a redacted ``AIProviderFailure`` from an arbitrary exception."""

    if isinstance(exc, AIProviderFailure):
        raise exc
    raise AIProviderFailure(classify_provider_error(exc), provider_type=provider_type) from exc


# Short alias useful for adapter clients and external contract tests.
classify_error = classify_provider_error
