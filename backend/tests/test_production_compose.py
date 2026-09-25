from pathlib import Path


def test_compose_keeps_frontend_dist_image_owned_and_persists_only_avatars():
    compose = (Path(__file__).resolve().parents[2] / "docker-compose.yml").read_text(encoding="utf-8")

    assert "avatars_data:/app/backend/api/static/avatars" in compose
    assert "static_data:/app/backend/api/static" not in compose
    assert "overlay_configs:" not in compose
    assert "AITOB_POSTGRES_DB" in compose
    assert "urllib.request.urlopen('http://localhost:8000/readiness'" in compose
    assert '["CMD", "curl"' not in compose
