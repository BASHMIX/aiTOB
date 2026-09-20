"""Validation and provenance helpers for tournament identity and branding.

Provider facts are immutable observations.  Organizers can add local
presentation overrides without changing the provider snapshot; the projection
records where every value came from so Hub, Editor and overlays agree.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class BrandValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BrandProjection:
    display_name: str
    short_name: str | None
    accent_color: str | None
    logo_url: str | None
    provenance: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "display_name": self.display_name,
            "short_name": self.short_name,
            "accent_color": self.accent_color,
            "logo_url": self.logo_url,
            "provenance": dict(self.provenance),
        }


def validate_brand_patch(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate local branding and return a bounded safe projection."""
    value = dict(value or {})
    display = value.get("display_name")
    short = value.get("short_name")
    accent = value.get("accent_color")
    logo = value.get("logo_url") or value.get("logo_asset_id")
    if display is not None:
        display = str(display).strip()
        if not display or len(display) > 200:
            raise BrandValidationError("display_name must contain 1-200 characters")
    if short is not None:
        short = str(short).strip()
        if len(short) > 80:
            raise BrandValidationError("short_name must contain at most 80 characters")
    if accent is not None:
        accent = str(accent).strip()
        if not _HEX.fullmatch(accent):
            raise BrandValidationError("accent_color must be a six digit hex color")
        accent = accent.upper()
    if logo is not None:
        logo = str(logo).strip()
        if len(logo) > 500 or any(ch in logo for ch in ("\r", "\n")):
            raise BrandValidationError("logo reference is invalid")
    return {"display_name": display, "short_name": short, "accent_color": accent, "logo_asset_id": logo}


def project_tournament_brand(
    provider_facts: Mapping[str, Any] | None,
    local_brand: Mapping[str, Any] | None = None,
    *,
    logo_url: str | None = None,
) -> BrandProjection:
    """Resolve local overrides first, then provider facts, then safe defaults."""
    provider = dict(provider_facts or {})
    local = validate_brand_patch(local_brand)

    def fact(name: str) -> Any:
        value = provider.get(name)
        if isinstance(value, Mapping) and "value" in value:
            return value.get("value")
        return value

    display = local.get("display_name") or fact("name") or "Untitled tournament"
    short = local.get("short_name") or fact("short_name")
    accent = local.get("accent_color") or fact("accent_color")
    if accent is not None:
        try:
            accent = validate_brand_patch({"accent_color": accent})["accent_color"]
        except BrandValidationError:
            accent = None
    local_logo = local.get("logo_asset_id")
    resolved_logo = logo_url or (fact("logo_url") if not local_logo else local_logo)
    provenance = {
        "display_name": "local" if local.get("display_name") else ("provider" if fact("name") else "default"),
        "short_name": "local" if local.get("short_name") else ("provider" if fact("short_name") else "unavailable"),
        "accent_color": "local" if local.get("accent_color") else ("provider" if fact("accent_color") else "default"),
        "logo_url": "local" if local_logo or logo_url else ("provider" if fact("logo_url") else "unavailable"),
    }
    return BrandProjection(str(display), str(short) if short else None, accent, str(resolved_logo) if resolved_logo else None, provenance)


resolve_brand = project_tournament_brand

__all__ = ["BrandValidationError", "BrandProjection", "validate_brand_patch", "project_tournament_brand", "resolve_brand"]
