"""Workspace-owned AI provider adapters.

Provider modules keep network and SDK details behind one small interface.  The
adapters return the existing ``AICompletion`` shape and raise a classified,
redacted error for failures.  They never select another provider and never
persist or echo credential material.
"""

from .base import (
    AIProviderFailure,
    FAILURE_CATEGORIES,
    ProviderFailureInfo,
    classify_provider_error,
)
from .gemini import GeminiAdapter
from .openai import OpenAIAdapter

__all__ = [
    "AIProviderFailure",
    "FAILURE_CATEGORIES",
    "ProviderFailureInfo",
    "GeminiAdapter",
    "OpenAIAdapter",
    "classify_provider_error",
]
