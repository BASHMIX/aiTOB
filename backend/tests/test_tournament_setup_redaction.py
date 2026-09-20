"""Regression coverage for setup projections and integration audit redaction."""
from backend.core.integrations import _safe_audit_detail, _safe_metadata


def test_setup_metadata_drops_secret_shaped_fields():
    value = _safe_metadata({
        "display_name": "Gemini",
        "token": "sk-live-value",
        "nested": {"authorization": "Bearer secret"},
        "capabilities": {"chat": True},
    })
    assert value == {"display_name": "Gemini", "capabilities": {"chat": True}}
    assert "sk-live-value" not in repr(value)


def test_setup_audit_detail_keeps_safe_context_only():
    value = _safe_audit_detail({
        "provider": "openai",
        "api_key": "sk-live-value",
        "nested": {"safe": "ok", "password": "secret"},
    })
    assert value == {"provider": "openai", "nested": {"safe": "ok"}}
    assert "secret" not in repr(value)
