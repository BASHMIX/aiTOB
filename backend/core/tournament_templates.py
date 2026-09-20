"""Allow-listed Discord template registry and renderer shared by preview/delivery."""
from __future__ import annotations

import html
import re
from typing import Any, Mapping

MAX_MESSAGE_LENGTH = 2000
SUPPORTED_VARIABLES = {"player_1", "player_2", "gamertag", "prefix", "destination", "tournament", "round", "match_id"}
DEFAULT_TEMPLATES = {
    "match_call": "{player_1} vs {player_2} — report to {destination}",
    "registration_open": "Registration is open for {tournament}.",
    "registration_closed": "Registration is closed for {tournament}.",
}


class TemplateError(ValueError):
    pass


def validate_template(template: str) -> str:
    text = str(template or "")
    if not text.strip():
        raise TemplateError("empty_template")
    if len(text) > MAX_MESSAGE_LENGTH:
        raise TemplateError("template_too_long")
    unknown = [name for name in re.findall(r"\{\{?\s*([a-zA-Z0-9_]+)\s*\}?\}", text) if name not in SUPPORTED_VARIABLES]
    if unknown:
        raise TemplateError("unsupported_variable:" + unknown[0])
    return text


def render_template(template: str, values: Mapping[str, Any], *, locale: str = "en") -> str:
    text = validate_template(template)
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return html.escape(str(values.get(key, "")).strip(), quote=False)
    rendered = re.sub(r"\{\{?\s*([a-zA-Z0-9_]+)\s*\}?\}", replace, text).strip()
    if not rendered:
        raise TemplateError("empty_rendered_message")
    if len(rendered) > MAX_MESSAGE_LENGTH:
        raise TemplateError("rendered_message_too_long")
    return rendered


def render_message(template_key: str, values: Mapping[str, Any], *, templates: Mapping[str, str] | None = None, locale: str = "en") -> str:
    selected = dict(DEFAULT_TEMPLATES)
    selected.update(dict(templates or {}))
    if template_key not in selected:
        raise TemplateError("template_not_found")
    return render_template(selected[template_key], values, locale=locale)


def safe_template_projection(templates: Mapping[str, str] | None = None) -> dict[str, str]:
    result = {}
    for key, value in (templates or {}).items():
        if key in DEFAULT_TEMPLATES:
            result[key] = validate_template(value)
    return result


TEMPLATE_FORBIDDEN_KEYS = {"id", "workspace_id", "tournament_id", "provider_account_id", "provider_scope", "credential", "api_key", "dates", "players", "test_details"}


def sanitize_template_preferences(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep reusable templates to non-secret, non-identity preferences."""
    if not isinstance(value, Mapping):
        return {}
    safe: dict[str, Any] = {}
    for key, item in value.items():
        key_text = str(key).strip().lower()
        if key_text in TEMPLATE_FORBIDDEN_KEYS or any(part in key_text for part in ("token", "secret", "password", "credential")):
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            safe[str(key)] = item
        elif isinstance(item, Mapping) and len(safe) < 64:
            safe[str(key)] = sanitize_template_preferences(item)
    return safe


def build_setup_template(name: str, preferences: Mapping[str, Any] | None = None) -> dict[str, Any]:
    title = str(name or "").strip()
    if not title or len(title) > 120:
        raise TemplateError("invalid_template_name")
    return {"name": title, "schema_version": 1, "preferences": sanitize_template_preferences(preferences)}


__all__ = ["SUPPORTED_VARIABLES", "DEFAULT_TEMPLATES", "TemplateError", "validate_template", "render_template", "render_message", "safe_template_projection", "sanitize_template_preferences", "build_setup_template"]
