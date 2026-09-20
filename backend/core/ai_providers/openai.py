"""OpenAI adapter for workspace-owned BYOK assistant requests."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.request import Request, urlopen

from .base import AIProviderFailure, classify_provider_error, raise_classified


class OpenAIAdapter:
    provider_type = "openai"
    endpoint = "https://api.openai.com/v1/chat/completions"

    @staticmethod
    def _completion(text: str, input_tokens: int | None = None, output_tokens: int | None = None):
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
        payload = json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a read-only tournament organizer assistant."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
            }
        ).encode("utf-8")

        def send() -> dict[str, Any]:
            request = Request(
                self.endpoint,
                data=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310 - fixed endpoint
                return json.loads(response.read().decode("utf-8"))

        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(send), timeout=timeout_seconds + 1
            )
            text = str(raw["choices"][0]["message"]["content"])
            usage = raw.get("usage") or {}
            return self._completion(
                text, usage.get("prompt_tokens"), usage.get("completion_tokens")
            )
        except AIProviderFailure:
            raise
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                raise
            raise_classified(exc, provider_type=self.provider_type)

    async def test_connection(
        self, *, api_key: str, model: str, timeout_seconds: int
    ) -> dict[str, Any]:
        await self.complete(
            api_key=api_key,
            model=model,
            prompt="Reply with OK.",
            timeout_seconds=timeout_seconds,
        )
        return {"category": "success", "safe_message_code": "connection_verified"}


OpenAIProvider = OpenAIAdapter
OpenAIAIProvider = OpenAIAdapter
classify_openai_error = classify_provider_error
