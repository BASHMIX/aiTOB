"""Immutable models for the versioned v1 player presentation hook and provenance contract."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

ProvenanceSource = Literal["entrant_override", "player_profile", "provider_snapshot", "placeholder"]


class EntrantScope(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str = Field(default="startgg", description="Tournament bracket provider (e.g. startgg, challonge)")
    tournament_slug: str = Field(description="Unique tournament identifier/slug")
    event_id: str = Field(description="Event or bracket scope identifier")
    entrant_id: str = Field(description="Entrant identifier in the provider bracket")


class CharacterValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = ""
    id: str = ""
    image_url: str = ""


class PresentationField(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True)

    value: T | None = None
    source: ProvenanceSource = "placeholder"


class ResolvedPresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    display_name: PresentationField[str] = Field(default_factory=PresentationField[str])
    prefix: PresentationField[str] = Field(default_factory=PresentationField[str])
    country: PresentationField[str] = Field(default_factory=PresentationField[str])
    avatar_url: PresentationField[str] = Field(default_factory=PresentationField[str])
    character: PresentationField[CharacterValue] = Field(default_factory=PresentationField[CharacterValue])


class PlayerPresentationV1(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: Literal["v1"] = "v1"
    entrant: EntrantScope
    player_profile_id: str | None = None
    linked: bool = False
    presentation: ResolvedPresentation


class EntrantPresentationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str = "startgg"
    tournament_slug: str
    event_id: str
    entrant_id: str
