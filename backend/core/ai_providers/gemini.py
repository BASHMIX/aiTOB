"""Gemini adapter for workspace-owned BYOK assistant requests."""

from __future__ import annotations

import asyncio
from typing import Any

from .base import AIProviderFailure, classify_provider_error, raise_classified


class GeminiAdapter:
    provider_type = "gemini"

    @staticmethod
    def _completion(text: str, input_tokens: int | None = None, output_tokens: int | None = None):
        # Importing the service at call time avoids a module cycle while still
        # preserving the existing AICompletion contract.
        from backend.core.ai_service import _completion_from_text

        return _completion_from_text(text, input_tokens, output_tokens)

    async def complete(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str,
        timeout_seconds: int,
    ):
        """Run one completion with a bounded timeout and classified errors."""

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            client = ChatGoogleGenerativeAI(
                model=model,
                temperature=0,
                api_key=api_key,
                request_timeout=timeout_seconds,
            )
            message = await asyncio.wait_for(
                client.ainvoke(prompt), timeout=timeout_seconds
            )
            content = getattr(message, "content", "")
            if isinstance(content, list):
                content = "\n".join(
                    str(item.get("text", "")) if isinstance(item, dict) else str(item)
                    for item in content
                )
            usage = getattr(message, "usage_metadata", {}) or {}
            return self._completion(
                str(content or ""), usage.get("input_tokens"), usage.get("output_tokens")
            )
        except AIProviderFailure:
            raise
        except BaseException as exc:
            # Do not let cancellation be converted into a provider failure.
            if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                raise
            raise_classified(exc, provider_type=self.provider_type)

    async def test_connection(
        self, *, api_key: str, model: str, timeout_seconds: int
    ) -> dict[str, Any]:
        """Make the smallest explicit provider request used by the UI test."""

        await self.complete(
            api_key=api_key,
            model=model,
            prompt="Reply with OK.",
            timeout_seconds=timeout_seconds,
        )
        return {"category": "success", "safe_message_code": "connection_verified"}


# Naming used by a few provider contract clients.
GeminiProvider = GeminiAdapter
GeminiAIProvider = GeminiAdapter
classify_gemini_error = classify_provider_error
