from backend.bot.runtime_logging import console_message, ready_message


def test_ready_message_is_console_safe_ascii():
    """Regression: on_ready must not crash on a Windows cp1252 console."""
    assert ready_message().isascii()


def test_console_message_escapes_non_ascii_before_windows_console_output():
    assert console_message("info", "Bot \U0001f916 ready").isascii()
