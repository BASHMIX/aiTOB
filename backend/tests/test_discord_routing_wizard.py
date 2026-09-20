from backend.core.discord_resources import effective_permissions, permission_checks


def test_effective_permissions_apply_overwrites():
    assert effective_permissions({"view_channel": True}, member_overwrites={"send_messages": True})["send_messages"] is True
    checks = permission_checks({"view_channel": False})
    assert any(item["reason_code"] == "missing_permission" for item in checks)
