"""Regression coverage for tenant-qualified station overlay repositories.

Stations keep a stable, human-facing id for Browser Source URLs.  When two
workspaces choose the same id, the repository stores the second row under a
tenant-qualified storage id.  Overlay helpers must resolve that storage id
before every read or write; otherwise a direct repository caller either sees
the other workspace's data or cannot manage its own overlays.
"""
from __future__ import annotations

import asyncio
import os

import pytest

from backend.core import database


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    original_path = database.DB_PATH
    database.DB_PATH = str(tmp_path / "station-overlay-scope.sqlite")
    monkeypatch.setenv("AITOB_TESTING", "1")
    monkeypatch.setenv("DB_PATH", database.DB_PATH)
    run(database.init_db())
    yield
    database.DB_PATH = original_path


def test_public_station_id_resolves_to_its_workspace_storage_row():
    """Same public id may carry independent overlays and active presets."""
    run(database.create_station("broadcast", "Workspace A", "workspace-a"))
    run(database.create_station("broadcast", "Workspace B", "workspace-b"))

    # Repository callers use the public station id, not an internal storage id.
    run(database.add_station_overlay("broadcast", "a-layout", "workspace-a"))
    run(database.add_station_overlay("broadcast", "b-layout", "workspace-b"))
    run(database.update_station_active_overlay("broadcast", "a-layout", "workspace-a"))
    run(database.update_station_active_overlay("broadcast", "b-layout", "workspace-b"))

    assert [row["overlay_name"] for row in run(database.get_station_overlays("broadcast", "workspace-a"))] == ["a-layout"]
    assert [row["overlay_name"] for row in run(database.get_station_overlays("broadcast", "workspace-b"))] == ["b-layout"]
    assert run(database.get_station_active_overlay("broadcast", "workspace-a")) == "a-layout"
    assert run(database.get_station_active_overlay("broadcast", "workspace-b")) == "b-layout"


def test_overlay_removal_with_public_id_never_touches_another_workspace():
    run(database.create_station("broadcast", "Workspace A", "workspace-a"))
    run(database.create_station("broadcast", "Workspace B", "workspace-b"))
    run(database.add_station_overlay("broadcast", "a-layout", "workspace-a"))
    run(database.add_station_overlay("broadcast", "b-layout", "workspace-b"))

    run(database.remove_station_overlay("broadcast", "b-layout", "workspace-b"))

    assert [row["overlay_name"] for row in run(database.get_station_overlays("broadcast", "workspace-a"))] == ["a-layout"]
    assert run(database.get_station_overlays("broadcast", "workspace-b")) == []
