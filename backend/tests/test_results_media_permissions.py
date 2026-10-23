"""Role matrix and permission tests for Tournament Results Media."""

from __future__ import annotations

import pytest
from backend.core.workspace_auth import ROLE_PERMISSIONS, permission_allowed


def test_results_manage_permission_matrix():
    """Verify results.manage is granted to Owner and Tournament Organizer only."""
    assert permission_allowed("owner", "results.manage") is True
    assert permission_allowed("tournament_organizer", "results.manage") is True
    assert permission_allowed("organizer", "results.manage") is True

    # Forbidden for stream operators, moderators, viewers
    assert permission_allowed("stream_operator", "results.manage") is False
    assert permission_allowed("operator", "results.manage") is False
    assert permission_allowed("moderator", "results.manage") is False
    assert permission_allowed("viewer", "results.manage") is False


def test_results_broadcast_permission_matrix():
    """Verify results.broadcast is granted to Owner and Stream Operator only."""
    assert permission_allowed("owner", "results.broadcast") is True
    assert permission_allowed("stream_operator", "results.broadcast") is True
    assert permission_allowed("operator", "results.broadcast") is True

    # Forbidden for tournament organizers, moderators, viewers
    assert permission_allowed("tournament_organizer", "results.broadcast") is False
    assert permission_allowed("organizer", "results.broadcast") is False
    assert permission_allowed("moderator", "results.broadcast") is False
    assert permission_allowed("viewer", "results.broadcast") is False


def test_moderator_and_viewer_access_not_widened():
    """Verify moderator and viewer have no new results permissions."""
    results_permissions = {"results.manage", "results.broadcast"}
    assert not (results_permissions & ROLE_PERMISSIONS["moderator"])
    assert not (results_permissions & ROLE_PERMISSIONS["viewer"])
