"""Local safety checks for the explicit backup/restore drill."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_script(name: str):
    if name == "restore_database" and "backup_database" not in sys.modules:
        _load_script("backup_database")
    root = Path(__file__).resolve().parents[2] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"aitob_{name}", root)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def backup_tools():
    return _load_script("backup_database")


def _write_manifest(backup: Path, *, digest: str, size: int | None = None) -> Path:
    record: dict[str, object] = {
        "manifest_version": 1,
        "engine": "sqlite-fixture",
        "file": backup.name,
        "sha256": digest,
        "secrets_included": False,
    }
    if size is not None:
        record["size_bytes"] = size
    manifest = backup.with_suffix(backup.suffix + ".manifest.json")
    manifest.write_text(json.dumps(record), encoding="utf-8")
    return manifest


def test_manifest_verification_accepts_exact_artifact(tmp_path: Path, backup_tools):
    backup = tmp_path / "accepted.sqlite"
    backup.write_bytes(b"stable backup bytes")
    manifest = _write_manifest(backup, digest=backup_tools._digest(backup), size=backup.stat().st_size)

    result = backup_tools.verify_manifest(backup, manifest)

    assert result["file"] == backup.name
    assert result["secrets_included"] is False


@pytest.mark.parametrize("tamper", ["bytes", "filename", "size"])
def test_manifest_verification_rejects_tampered_or_mismatched_artifact(
    tmp_path: Path, backup_tools, tamper: str
):
    backup = tmp_path / "checked.sqlite"
    backup.write_bytes(b"stable backup bytes")
    manifest = _write_manifest(backup, digest=backup_tools._digest(backup), size=backup.stat().st_size)

    if tamper == "bytes":
        backup.write_bytes(b"changed after review")
    elif tamper == "filename":
        renamed = tmp_path / "different.sqlite"
        backup.rename(renamed)
        backup = renamed
    else:
        record = json.loads(manifest.read_text(encoding="utf-8"))
        record["size_bytes"] = int(record["size_bytes"]) + 1
        manifest.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="manifest|digest|size"):
        backup_tools.verify_manifest(backup, manifest)


def test_restore_requires_sidecar_manifest(tmp_path: Path, backup_tools):
    backup = tmp_path / "without-manifest.sqlite"
    backup.write_bytes(b"unreviewed backup")

    with pytest.raises(ValueError, match="manifest"):
        backup_tools.verify_manifest(backup)


def test_postgres_restore_is_non_destructive_without_force(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    restore = _load_script("restore_database")
    backup = tmp_path / "reviewed.dump"
    backup.write_bytes(b"reviewed dump")
    manifest = _write_manifest(backup, digest=restore.verify_manifest.__globals__["_digest"](backup), size=backup.stat().st_size)
    calls: list[list[str]] = []

    monkeypatch.setattr(restore.subprocess, "run", lambda command, check=False: calls.append(command) or type("Result", (), {"returncode": 0})())
    monkeypatch.setattr(restore.os, "getenv", lambda key, default="": "postgresql://disposable" if key == "DATABASE_URL" else default)
    monkeypatch.setattr(restore.sys, "argv", ["restore_database.py", str(backup), "--postgres-target", "postgresql://disposable"])

    assert restore.main() == 0
    assert calls and "--clean" not in calls[0] and "--if-exists" not in calls[0]


def test_postgres_restore_cleanup_requires_force(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    restore = _load_script("restore_database")
    backup = tmp_path / "reviewed.dump"
    backup.write_bytes(b"reviewed dump")
    manifest = _write_manifest(backup, digest=restore.verify_manifest.__globals__["_digest"](backup), size=backup.stat().st_size)
    calls: list[list[str]] = []

    monkeypatch.setattr(restore.subprocess, "run", lambda command, check=False: calls.append(command) or type("Result", (), {"returncode": 0})())
    monkeypatch.setattr(restore.sys, "argv", ["restore_database.py", str(backup), "--postgres-target", "postgresql://disposable", "--force"])

    assert restore.main() == 0
    assert calls and "--clean" in calls[0] and "--if-exists" in calls[0]
