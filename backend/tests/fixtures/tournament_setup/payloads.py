"""Loadable, redacted provider payloads used by setup wizard tests."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


FIXTURE_DIR = Path(__file__).parent


def _read(name: str) -> dict[str, Any]:
    """Return an independent copy so one test cannot mutate another fixture."""

    with (FIXTURE_DIR / name).open(encoding="utf-8") as stream:
        return deepcopy(json.load(stream))


def startgg_fixture() -> dict[str, Any]:
    """Return the complete Start.gg GraphQL fixture bundle."""

    return _read("startgg.json")


def challonge_fixture() -> dict[str, Any]:
    """Return the complete Challonge JSON:API fixture bundle."""

    return _read("challonge.json")


def discord_fixture() -> dict[str, Any]:
    """Return safe guild, channel, role, and member projections."""

    return _read("discord.json")


def gemini_fixture() -> dict[str, Any]:
    """Return a synthetic Gemini completion and health response."""

    return _read("gemini.json")


def openai_fixture() -> dict[str, Any]:
    """Return a synthetic OpenAI chat completion and health response."""

    return _read("openai.json")
