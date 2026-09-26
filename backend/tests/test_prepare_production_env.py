from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "prepare_production_env.py"
    spec = spec_from_file_location("prepare_production_env", path)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_prepare_removes_legacy_values_and_generates_distinct_keys(tmp_path):
    module = _module()
    env_file = tmp_path / ".env.production"
    env_file.write_text(
        "\n".join([
            "DB_PATH=legacy.sqlite",
            "AITOB_DISCORD_WORKSPACE_ID=workspace-1",
            "STARTGG_API_TOKEN=retired-shared-token",
            "API_BASE_URL=https://aitob.example",
            "APP_PUBLIC_URL=http://127.0.0.1:5173",
            "DATABASE_URL=postgresql://user:pass@example/legacy",
            "AITOB_RUNTIME_DATABASE_NAME=approved_staging",
            "POSTGRES_PASSWORD=not-a-placeholder",
            "DISCORD_BOT_TOKEN=bot-token",
            "DISCORD_CLIENT_ID=client-id",
            "DISCORD_CLIENT_ID=",
            "DISCORD_CLIENT_SECRET=client-secret",
            "DISCORD_CLIENT_SECRET=",
        ]) + "\n",
        encoding="utf-8",
    )

    result = module.prepare(env_file)
    text = env_file.read_text(encoding="utf-8")
    values = dict(module._assignment(line) for line in text.splitlines() if module._assignment(line))

    assert set(result["removed"]) == {
        "DB_PATH", "AITOB_DISCORD_WORKSPACE_ID", "AITOB_RUNTIME_DATABASE_NAME",
        "STARTGG_API_TOKEN",
    }
    assert "DB_PATH=" not in text and "AITOB_DISCORD_WORKSPACE_ID=" not in text
    assert "AITOB_RUNTIME_DATABASE_NAME=" not in text
    assert "STARTGG_API_TOKEN=" not in text
    assert values["AITOB_POSTGRES_DB"] == "approved_staging"
    assert values["DATABASE_URL"].endswith("/approved_staging")
    assert values["APP_PUBLIC_URL"] == values["FRONTEND_BASE_URL"] == "https://aitob.example"
    assert values["DISCORD_OAUTH_REDIRECT_URI"].endswith("/api/integrations/discord/callback")
    assert values["DISCORD_CLIENT_ID"] == "client-id"
    assert values["DISCORD_CLIENT_SECRET"] == "client-secret"
    assert text.count("DISCORD_CLIENT_ID=") == 1
    assert text.count("DISCORD_CLIENT_SECRET=") == 1
    assert values["AITOB_SESSION_COOKIE_SECURE"] == "true"
    assert values["AITOB_MANAGED_PROVIDER_OAUTH"] == "false"
    assert len({values[key] for key in module.GENERATED_KEYS}) == len(module.GENERATED_KEYS)
    assert module.validate(env_file) == []


def test_validation_fails_closed_for_missing_external_discord_credentials(tmp_path):
    module = _module()
    env_file = tmp_path / ".env.production"
    env_file.write_text(
        "DATABASE_URL=postgresql://example/aitob\nAITOB_POSTGRES_DB=aitob\nPOSTGRES_PASSWORD=value\n",
        encoding="utf-8",
    )
    errors = module.validate(env_file)
    assert "DISCORD_CLIENT_ID is missing" in errors
    assert "DISCORD_CLIENT_SECRET is missing" in errors


def test_validation_rejects_database_name_drift(tmp_path):
    module = _module()
    env_file = tmp_path / ".env.production"
    env_file.write_text(
        "DATABASE_URL=postgresql://example/old\nAITOB_POSTGRES_DB=approved\n",
        encoding="utf-8",
    )

    assert "DATABASE_URL database must match AITOB_POSTGRES_DB" in module.validate(env_file)
