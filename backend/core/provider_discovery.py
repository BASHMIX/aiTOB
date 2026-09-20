"""Provider-neutral tournament/event discovery for the setup wizard.

Discovery is deliberately a read-only boundary.  It parses a user supplied
locator, asks the selected workspace-owned adapter for a provider snapshot and
returns a safe projection suitable for a draft.  No tournament, account, raw
provider response or credential is persisted here.

The module keeps the provider-specific HTTP shape in ``providers/*/discovery``
and exposes small dataclasses so API and frontend code do not need to know how
Start.gg GraphQL or Challonge JSON:API represents an event/bracket.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
import re
from typing import Any, Mapping, Protocol


SUPPORTED_PROVIDER_TYPES = frozenset({"startgg", "challonge"})
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@-]{0,399}$")
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,199}$")


class LocatorKind(str, Enum):
    TOURNAMENT = "tournament"
    EVENT = "event"
    BRACKET = "bracket"


class ResolutionKind(str, Enum):
    SELECTED_SCOPE = "selected_scope"
    SCOPE_SELECTION_REQUIRED = "scope_selection_required"


class CapabilityState(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class StartInWaveState(str, Enum):
    VERIFIED_ENABLED = "verified_enabled"
    VERIFIED_DISABLED = "verified_disabled"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProviderLocator:
    """Validated, normalized locator with no credential-bearing URL parts."""

    provider: str
    raw: str
    kind: LocatorKind
    tournament_slug: str
    scope_slug: str | None = None
    community: str | None = None

    @property
    def canonical(self) -> str:
        """Canonical provider slug passed to an adapter, preserving event path."""

        if self.provider == "challonge":
            return self.scope_slug or self.tournament_slug
        return self.scope_slug or self.tournament_slug

    @property
    def coordination_key(self) -> str:
        scope = self.scope_slug or self.tournament_slug
        community = self.community or "global"
        return f"{self.provider}:{self.kind.value}:{community}:{scope.lower()}"


@dataclass(frozen=True)
class ProviderFact:
    value: Any = None
    source: str = "unavailable"
    observed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderScope:
    kind: str
    external_id: str
    canonical_slug: str | None = None
    name: ProviderFact = field(default_factory=ProviderFact)
    game: ProviderFact = field(default_factory=ProviderFact)
    format: ProviderFact = field(default_factory=ProviderFact)
    state: ProviderFact = field(default_factory=ProviderFact)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "external_id": self.external_id,
            "canonical_slug": self.canonical_slug,
            "name": self.name.to_dict(),
            "game": self.game.to_dict(),
            "format": self.format.to_dict(),
            "state": self.state.to_dict(),
        }


@dataclass(frozen=True)
class ProviderObject:
    external_id: str
    canonical_slug: str | None = None
    name: ProviderFact = field(default_factory=ProviderFact)
    starts_at: ProviderFact = field(default_factory=ProviderFact)
    timezone: ProviderFact = field(default_factory=ProviderFact)
    state: ProviderFact = field(default_factory=ProviderFact)
    logo_url: ProviderFact = field(default_factory=ProviderFact)

    def to_dict(self) -> dict[str, Any]:
        return {
            "external_id": self.external_id,
            "canonical_slug": self.canonical_slug,
            "name": self.name.to_dict(),
            "starts_at": self.starts_at.to_dict(),
            "timezone": self.timezone.to_dict(),
            "state": self.state.to_dict(),
            "logo_url": self.logo_url.to_dict(),
        }


@dataclass(frozen=True)
class Capability:
    state: CapabilityState
    reason_code: str

    def to_dict(self) -> dict[str, str]:
        return {"state": self.state.value, "reason_code": self.reason_code}


@dataclass(frozen=True)
class StartInWaveProjection:
    state: StartInWaveState = StartInWaveState.UNKNOWN
    observed_at: str = ""
    monitoring_mode: str = "off"
    confirmed: bool = False
    confirmed_at: str | None = None
    monitoring_state: str = "not_applicable"

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "observed_at": self.observed_at,
            "monitoring_mode": self.monitoring_mode,
            "organizer_confirmation": {
                "confirmed": self.confirmed,
                "confirmed_at": self.confirmed_at,
            },
            "monitoring_state": self.monitoring_state,
        }


@dataclass(frozen=True)
class ProviderResolution:
    resolution: ResolutionKind
    provider: str
    account_id: str
    tournament: ProviderObject
    scopes: tuple[ProviderScope, ...]
    selected_scope: ProviderScope | None
    capabilities: Mapping[str, Capability]
    start_in_wave: StartInWaveProjection
    observed_at: str
    freshness_seconds: int
    locator: ProviderLocator | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution": self.resolution.value,
            "provider": self.provider,
            "account_id": self.account_id,
            "tournament": self.tournament.to_dict(),
            "scopes": [scope.to_dict() for scope in self.scopes],
            "selected_scope": self.selected_scope.to_dict() if self.selected_scope else None,
            "capabilities": {name: value.to_dict() for name, value in self.capabilities.items()},
            "start_in_wave": self.start_in_wave.to_dict(),
            "observed_at": self.observed_at,
            "freshness_seconds": self.freshness_seconds,
            "locator": {
                "provider": self.locator.provider,
                "kind": self.locator.kind.value,
                "canonical": self.locator.canonical,
                "coordination_key": self.locator.coordination_key,
            } if self.locator else None,
        }


class ProviderDiscoveryError(RuntimeError):
    """Safe, stable error suitable for a browser response."""

    def __init__(self, code: str, message: str, *, retryable: bool = False, status_code: int = 422):
        self.code = code
        self.retryable = retryable
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "retryable": self.retryable}


class DiscoveryAdapter(Protocol):
    async def discover(self, locator: ProviderLocator, *, account_id: str) -> Mapping[str, Any]: ...


def _normalize_provider(provider: str) -> str:
    value = str(provider or "").strip().lower()
    if value not in SUPPORTED_PROVIDER_TYPES:
        raise ProviderDiscoveryError("unsupported_provider", "This bracket provider is not supported.")
    return value


def _clean_path(parts: list[str]) -> list[str]:
    cleaned = [part.strip() for part in parts if part.strip()]
    if any(part in {".", ".."} or "\\" in part for part in cleaned):
        raise ProviderDiscoveryError("invalid_locator", "The provider locator contains an invalid path.")
    return cleaned


def parse_startgg_locator(value: str) -> ProviderLocator:
    """Parse a Start.gg tournament or Event slug/URL without truncating it."""

    from urllib.parse import unquote, urlparse

    raw = str(value or "").strip()
    if not raw:
        raise ProviderDiscoveryError("invalid_locator", "Enter a Start.gg tournament or Event link/slug.")
    has_scheme = "://" in raw
    if has_scheme:
        parse_value = raw
    elif raw.lower().startswith(("tournament/", "event/")):
        # The documented slug form is entered without a hostname.
        parse_value = f"https://start.gg/{raw}"
    elif "/" in raw or "." in raw:
        # A host-looking value must prove that it is a Start.gg host below;
        # this prevents ``evil.example/tournament/foo`` being treated as a
        # bare opaque slug.
        parse_value = f"https://{raw}"
    else:
        # Keep accepting a bare tournament slug while making its scope explicit.
        parse_value = f"https://start.gg/tournament/{raw}"
    parsed = urlparse(parse_value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProviderDiscoveryError("invalid_locator", "Start.gg locators cannot contain credentials, queries, or fragments.")
    if has_scheme and parsed.scheme.lower() not in {"http", "https"}:
        raise ProviderDiscoveryError("invalid_locator", "Start.gg links must use HTTP or HTTPS.")
    if parsed.port not in (None, 80, 443):
        raise ProviderDiscoveryError("invalid_locator", "Start.gg links must use a standard HTTP(S) port.")
    if (parsed.hostname or "").lower().rstrip(".") not in {"start.gg", "www.start.gg"}:
        raise ProviderDiscoveryError("invalid_locator", "Enter a link hosted by Start.gg.")
    parts = _clean_path([unquote(part) for part in parsed.path.split("/")])
    if not parts:
        raise ProviderDiscoveryError("invalid_locator", "Enter a Start.gg tournament or Event link/slug.")
    if any(not _SAFE_SEGMENT.fullmatch(part) for part in parts):
        raise ProviderDiscoveryError("invalid_locator", "The Start.gg locator contains unsupported characters.")
    if parts[0].lower() == "tournament":
        if len(parts) < 2 or len(parts) > 4 or (len(parts) == 4 and parts[2].lower() != "event"):
            raise ProviderDiscoveryError("invalid_locator", "Start.gg link must identify a tournament or Event.")
        tournament_slug = f"tournament/{parts[1]}"
        if len(parts) == 4:
            scope_slug = f"{tournament_slug}/event/{parts[3]}"
            kind = LocatorKind.EVENT
        else:
            scope_slug, kind = None, LocatorKind.TOURNAMENT
    elif parts[0].lower() == "event" and len(parts) == 2:
        # The short event form is accepted, but remains an Event locator.  The
        # adapter will resolve the parent tournament from the provider response.
        tournament_slug = f"event/{parts[1]}"
        scope_slug, kind = tournament_slug, LocatorKind.EVENT
    else:
        # GraphQL accepts canonical ``tournament/foo`` slugs.  Treat an opaque
        # single slug as a tournament locator to avoid guessing an Event.
        if len(parts) != 1:
            raise ProviderDiscoveryError("invalid_locator", "Use a Start.gg tournament slug or full Event slug.")
        tournament_slug, scope_slug, kind = parts[0], None, LocatorKind.TOURNAMENT
    for candidate in (tournament_slug, scope_slug):
        if candidate and not _SAFE_ID.fullmatch(candidate):
            raise ProviderDiscoveryError("invalid_locator", "The Start.gg locator contains unsupported characters.")
    return ProviderLocator("startgg", raw, kind, tournament_slug, scope_slug)


def parse_challonge_locator(value: str, *, subdomain: str | None = None) -> ProviderLocator:
    from backend.core.providers.challonge.locator import parse_locator

    try:
        parsed = parse_locator(value, subdomain)
    except ValueError as exc:
        # The provider parser is currently using fixed messages, but the
        # discovery boundary must remain safe if that implementation changes.
        # Never reflect a provider exception or user supplied locator.
        raise ProviderDiscoveryError(
            "invalid_locator", "Enter a valid Challonge tournament or bracket link/slug."
        ) from exc
    return ProviderLocator(
        "challonge",
        parsed.identifier,
        LocatorKind.BRACKET,
        parsed.resource,
        parsed.resource,
        parsed.subdomain,
    )


def parse_locator(provider: str, value: str, *, challonge_subdomain: str | None = None) -> ProviderLocator:
    provider = _normalize_provider(provider)
    if provider == "startgg":
        return parse_startgg_locator(value)
    return parse_challonge_locator(value, subdomain=challonge_subdomain)


def freshness_seconds(observed_at: str | datetime, *, now: datetime | None = None) -> int:
    """Return non-negative age in seconds; malformed timestamps are stale."""

    if isinstance(observed_at, str):
        try:
            parsed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        except ValueError:
            return 2**31 - 1
    else:
        parsed = observed_at
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    reference = now or datetime.now(UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    return max(0, int((reference - parsed.astimezone(UTC)).total_seconds()))


def project_capabilities(provider: str, adapter: Any = None) -> dict[str, Capability]:
    """Project only capabilities explicitly declared by the adapter.

    Remote bracket start and Start-in-wave setting reads/writes remain unknown
    or unsupported until a provider-specific verified contract exists.  A
    successful ``mark_called`` method is intentionally not treated as proof of
    tournament-start or wave-setting support.
    """

    provider = _normalize_provider(provider)
    result: dict[str, Capability] = {
        "remote_start": Capability(CapabilityState.UNKNOWN, "remote_start_contract_unverified"),
        "start_in_wave_read": Capability(CapabilityState.UNKNOWN, "start_in_wave_read_unverified"),
        "start_in_wave_write": Capability(CapabilityState.UNSUPPORTED, "start_in_wave_write_undocumented"),
        "result_reporting": Capability(CapabilityState.UNKNOWN, "result_reporting_unverified"),
    }
    if adapter is not None:
        declared = getattr(adapter, "capabilities_v2", None)
        if declared is not None:
            actions = getattr(declared, "actions", {}) or {}
            aliases = {
                "remote_start": ("remote_start", "start_tournament", "start_bracket"),
                "start_in_wave_read": ("start_in_wave_read", "read_start_in_wave", "start_in_wave_state"),
                "start_in_wave_write": ("start_in_wave_write", "write_start_in_wave", "set_start_in_wave"),
                "result_reporting": ("result_reporting", "report_score", "report_result", "report_winner"),
            }
            for name, names in aliases.items():
                declared_action = next((actions.get(action) for action in names if action in actions), None)
                if declared_action is None:
                    continue
                kind = getattr(declared_action, "kind", None)
                if kind is None and isinstance(declared_action, Mapping):
                    kind = declared_action.get("kind") or declared_action.get("availability") or declared_action.get("state")
                value = getattr(kind, "value", kind)
                if value in {"remote", "local"}:
                    result[name] = Capability(CapabilityState.SUPPORTED, "provider_contract")
                elif value in {"unavailable", "unsupported"}:
                    reason = getattr(declared_action, "reason", None)
                    if reason is None and isinstance(declared_action, Mapping):
                        reason = declared_action.get("reason") or declared_action.get("reason_code")
                    result[name] = Capability(CapabilityState.UNSUPPORTED, str(reason or "provider_contract"))
                else:
                    result[name] = Capability(CapabilityState.UNKNOWN, "provider_capability_state_unknown")
    return result


def classify_provider_error(error: BaseException) -> ProviderDiscoveryError:
    """Map provider failures to stable, non-secret user-facing categories."""

    name = type(error).__name__.lower()
    text = str(error).lower()
    if "rate" in name or "rate limit" in text or "quota" in text:
        return ProviderDiscoveryError("rate_limited", "The provider rate limit was reached. Try again later.", retryable=True, status_code=429)
    if "auth" in name or "unauthor" in text or "forbidden" in text or "credential" in text or "token" in text:
        return ProviderDiscoveryError("connection_invalid", "The selected provider connection is unavailable or expired.", status_code=409)
    if "timeout" in name or "network" in text or "connection" in text:
        return ProviderDiscoveryError("provider_unavailable", "The provider could not be reached. Retry without losing the draft.", retryable=True, status_code=502)
    if "not found" in text or "inaccessible" in text:
        return ProviderDiscoveryError("scope_not_found", "The selected provider scope was not found or is not accessible.", status_code=404)
    return ProviderDiscoveryError("provider_error", "The provider could not resolve this scope.", retryable=True, status_code=502)


async def discover(
    provider: str,
    account_id: str,
    locator: str,
    *,
    adapter: DiscoveryAdapter | None = None,
    challonge_subdomain: str | None = None,
    now: datetime | None = None,
) -> ProviderResolution:
    """Resolve a locator through an injected provider adapter.

    ``adapter`` is injectable for tests and for workspace-account binding.  If
    omitted, the provider-specific discovery adapter is constructed using the
    exact account ID; no global credential fallback is permitted.
    """

    provider = _normalize_provider(provider)
    account_id = str(account_id or "").strip()
    if not account_id or not _SAFE_ID.fullmatch(account_id):
        raise ProviderDiscoveryError("invalid_account", "A valid provider connection must be selected.")
    parsed = parse_locator(provider, locator, challonge_subdomain=challonge_subdomain)
    if adapter is None:
        if provider == "startgg":
            from backend.core.providers.startgg.discovery import StartGGDiscovery
            adapter = StartGGDiscovery()
        else:
            from backend.core.providers.challonge.discovery import ChallongeDiscovery
            adapter = ChallongeDiscovery()
    try:
        payload = await adapter.discover(parsed, account_id=account_id)
    except ProviderDiscoveryError:
        raise
    except Exception as exc:
        raise classify_provider_error(exc) from exc
    if not isinstance(payload, Mapping):
        raise ProviderDiscoveryError("provider_error", "The provider returned an invalid scope preview.", retryable=True, status_code=502)
    return _resolution_from_payload(provider, account_id, parsed, payload, now=now)


def _fact(value: Any, observed_at: str, *, source: str = "provider") -> ProviderFact:
    return ProviderFact(value=value, source=source if value not in (None, "") else "unavailable", observed_at=observed_at)


def _resolution_from_payload(
    provider: str,
    account_id: str,
    locator: ProviderLocator,
    payload: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> ProviderResolution:
    observed = str(payload.get("observed_at") or datetime.now(UTC).isoformat())
    tournament = payload.get("tournament") if isinstance(payload.get("tournament"), Mapping) else payload
    external_id = str(tournament.get("external_id") or tournament.get("id") or "")
    if not external_id:
        raise ProviderDiscoveryError("scope_not_found", "The provider did not return a tournament identity.", status_code=404)
    tournament_obj = ProviderObject(
        external_id=external_id,
        canonical_slug=tournament.get("canonical_slug") or tournament.get("slug") or locator.tournament_slug,
        name=_fact(tournament.get("name"), observed),
        starts_at=_fact(tournament.get("starts_at"), observed),
        timezone=_fact(tournament.get("timezone"), observed),
        state=_fact(tournament.get("state"), observed),
        logo_url=_fact(tournament.get("logo_url"), observed),
    )
    raw_scopes = payload.get("scopes")
    if raw_scopes is None and isinstance(tournament.get("scopes"), list):
        raw_scopes = tournament.get("scopes")
    scopes: list[ProviderScope] = []
    for raw_scope in raw_scopes or []:
        if not isinstance(raw_scope, Mapping):
            continue
        scope_id = str(raw_scope.get("external_id") or raw_scope.get("id") or "")
        if not scope_id:
            continue
        scopes.append(ProviderScope(
            kind=str(raw_scope.get("kind") or ("bracket" if provider == "challonge" else "event")),
            external_id=scope_id,
            canonical_slug=raw_scope.get("canonical_slug") or raw_scope.get("slug"),
            name=_fact(raw_scope.get("name"), observed),
            game=_fact(raw_scope.get("game"), observed),
            format=_fact(raw_scope.get("format"), observed),
            state=_fact(raw_scope.get("state"), observed),
        ))
    selected: ProviderScope | None = None
    if locator.kind in {LocatorKind.EVENT, LocatorKind.BRACKET}:
        wanted = str(payload.get("selected_scope_id") or "")
        if wanted:
            selected = next((scope for scope in scopes if scope.external_id == wanted), None)
        if selected is None and len(scopes) == 1:
            selected = scopes[0]
        if selected is None:
            # Direct locators must never silently bind a different scope.
            raise ProviderDiscoveryError("scope_not_found", "The exact provider Event or bracket could not be confirmed.", status_code=404)
    elif len(scopes) == 1:
        selected = scopes[0]
    resolution = ResolutionKind.SELECTED_SCOPE if selected else ResolutionKind.SCOPE_SELECTION_REQUIRED
    current = now or datetime.now(UTC)
    raw_wave_state = payload.get("start_in_wave_state")
    if isinstance(raw_wave_state, StartInWaveState):
        wave_state = raw_wave_state
    else:
        try:
            wave_state = StartInWaveState(str(raw_wave_state or "unknown").lower())
        except ValueError:
            wave_state = StartInWaveState.UNKNOWN
    return ProviderResolution(
        resolution=resolution,
        provider=provider,
        account_id=account_id,
        tournament=tournament_obj,
        scopes=tuple(scopes),
        selected_scope=selected,
        capabilities=project_capabilities(provider, payload.get("adapter")),
        start_in_wave=StartInWaveProjection(
            state=wave_state,
            observed_at=observed,
        ),
        observed_at=observed,
        freshness_seconds=freshness_seconds(observed, now=current),
        locator=locator,
    )


# Names used by API callers and earlier planning artifacts.
parse_provider_locator = parse_locator
resolve_provider_scope = discover

__all__ = [
    "Capability", "CapabilityState", "ProviderDiscoveryError", "ProviderFact",
    "ProviderLocator", "ProviderObject", "ProviderResolution", "ProviderScope",
    "ResolutionKind", "StartInWaveProjection", "StartInWaveState", "discover",
    "freshness_seconds", "parse_challonge_locator", "parse_locator",
    "parse_provider_locator", "parse_startgg_locator", "project_capabilities",
    "resolve_provider_scope",
]
