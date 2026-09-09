"""Console-safe runtime messages for the Discord process.

The Windows console used by the acceptance runner can be cp1252. Bot startup
must never fail simply because an informational message contains an emoji.
"""


def ready_message() -> str:
    """Return an ASCII-only message safe for every supported console."""
    return "Bot is online and connected to Discord."


def console_message(level: str, message: str) -> str:
    """Render log content without crashing a legacy Windows console."""
    raw = f"[{level.upper()}] {message}"
    return raw.encode("ascii", "backslashreplace").decode("ascii")
