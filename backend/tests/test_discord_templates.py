import pytest
from backend.core.tournament_templates import TemplateError, render_message, render_template


def test_template_escapes_and_renders_preview():
    assert "&lt;" in render_template("Hello {player_1}", {"player_1": "<x>"})


def test_template_rejects_unknown_and_too_long():
    with pytest.raises(TemplateError):
        render_template("{secret}", {})
    with pytest.raises(TemplateError):
        render_message("match_call", {"player_1": "x"}, templates={"match_call": "x" * 2001})
