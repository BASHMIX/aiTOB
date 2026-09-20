"""Hermetic fixtures for the tournament setup wizard.

The fixtures in this package are deliberately provider shaped, but contain no
credential, member, message, or production identifier.  Tests should build
adapters through the ``make_*_adapter`` helpers instead of importing concrete
HTTP clients and monkeypatching their network methods.
"""

from .adapters import (
    FakeChallongeClient,
    FakeDiscordAdapter,
    FakeAICompletion,
    FakeStartGGClient,
    FakeWorkspaceAIAdapter,
    make_challonge_adapter,
    make_discord_adapter,
    make_gemini_adapter,
    make_openai_adapter,
    make_startgg_adapter,
)
from .payloads import (
    challonge_fixture,
    discord_fixture,
    gemini_fixture,
    openai_fixture,
    startgg_fixture,
)

__all__ = [
    "FakeChallongeClient",
    "FakeDiscordAdapter",
    "FakeAICompletion",
    "FakeStartGGClient",
    "FakeWorkspaceAIAdapter",
    "make_challonge_adapter",
    "make_discord_adapter",
    "make_gemini_adapter",
    "make_openai_adapter",
    "make_startgg_adapter",
    "challonge_fixture",
    "discord_fixture",
    "gemini_fixture",
    "openai_fixture",
    "startgg_fixture",
]
