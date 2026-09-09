"""Parse only known Challonge references into safe adapter resource identifiers."""
from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import unquote, urlparse

_SAFE_PART = re.compile(r"[a-z0-9][a-z0-9_-]*\Z", re.IGNORECASE)
_KNOWN_ROOT = "challonge.com"


@dataclass(frozen=True)
class ChallongeLocator:
    """A local parse result, never a URL to pass to the HTTP client."""

    identifier: str
    tournament_id: str | None = None
    slug: str | None = None
    subdomain: str | None = None

    @property
    def resource(self) -> str:
        return self.tournament_id or self.slug or ""

    @property
    def coordination_key(self) -> str:
        return f"{'id' if self.tournament_id else 'slug'}:{self.subdomain or 'global'}:{self.resource.lower()}"


def _safe_part(value: str | None, label: str) -> str | None:
    cleaned = (value or "").strip().lower()
    if not cleaned:
        return None
    if not _SAFE_PART.fullmatch(cleaned):
        raise ValueError(f"Invalid Challonge {label}.")
    return cleaned


def _parse_legacy_reference(raw: str, supplied_subdomain: str | None) -> ChallongeLocator | None:
    if raw.count("@") != 1 or "://" in raw:
        return None
    resource, community = raw.split("@", 1)
    resource = resource.removeprefix("challonge:")
    community = _safe_part(community, "community")
    if supplied_subdomain and supplied_subdomain != community:
        raise ValueError("The supplied community does not match the Challonge reference.")
    if resource.isdigit():
        return ChallongeLocator(raw, tournament_id=resource, subdomain=community)
    return ChallongeLocator(raw, slug=_safe_part(resource, "tournament slug"), subdomain=community)


def parse_locator(value: str, subdomain: str | None = None) -> ChallongeLocator:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Challonge tournament ID or URL is required.")
    supplied_subdomain = _safe_part(subdomain, "community")
    legacy = _parse_legacy_reference(raw, supplied_subdomain)
    if legacy:
        return legacy
    if raw.isdigit():
        return ChallongeLocator(raw, tournament_id=raw, subdomain=supplied_subdomain)

    has_scheme = "://" in raw
    parsed = urlparse(raw if has_scheme else f"https://{raw}")
    if has_scheme and parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Challonge URLs must use HTTP or HTTPS.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not accepted.")
    if parsed.query or parsed.fragment:
        raise ValueError("Challonge URLs must not contain query parameters or fragments.")

    host = (parsed.hostname or "").lower().rstrip(".")
    if host == _KNOWN_ROOT or host.endswith(f".{_KNOWN_ROOT}"):
        if parsed.port not in (None, 80, 443):
            raise ValueError("Challonge URLs must use a standard HTTP(S) port.")
        parts = [unquote(part).strip() for part in parsed.path.split("/") if part]
        if len(parts) != 1:
            raise ValueError("Challonge URL must include exactly one tournament slug.")
        slug = _safe_part(parts[0], "tournament slug")
        host_parts = host.split(".")
        derived_subdomain = host_parts[0] if len(host_parts) > 2 else None
        if supplied_subdomain and derived_subdomain and supplied_subdomain != derived_subdomain:
            raise ValueError("The supplied community does not match the Challonge URL.")
        return ChallongeLocator(raw, slug=slug, subdomain=supplied_subdomain or derived_subdomain)

    if not has_scheme and "/" not in raw and "." not in raw:
        return ChallongeLocator(raw, slug=_safe_part(raw, "tournament slug"), subdomain=supplied_subdomain)
    raise ValueError("Enter a numeric ID, a known Challonge URL, or a tournament slug.")
