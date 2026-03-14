"""Structured logging and secret sanitization for preset-toolkit."""
import logging
import re
import sys

_ROOT_NAME = "preset_toolkit"
_root = logging.getLogger(_ROOT_NAME)
_configured = False

# Shared secret patterns — used by telemetry, sync, and any outbound data
SECRET_PATTERNS = re.compile(
    r'(token|secret|password|authorization|bearer|jwt|api[_-]?key)\s*[=:]\s*\S+',
    re.IGNORECASE,
)


def sanitize(text: str, max_length: int = 500) -> str:
    """Remove potential secrets from text before logging or sending externally."""
    return SECRET_PATTERNS.sub("[REDACTED]", text)[:max_length]


def _configure():
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    _root.addHandler(handler)
    _root.setLevel(logging.INFO)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a namespaced logger: preset_toolkit.<name>."""
    _configure()
    return _root.getChild(name)


def set_debug(enabled: bool = True) -> None:
    """Toggle debug level on all preset-toolkit loggers."""
    _configure()
    level = logging.DEBUG if enabled else logging.INFO
    _root.setLevel(level)
    for handler in _root.handlers:
        handler.setLevel(level)
    for name in logging.Logger.manager.loggerDict:
        if name.startswith(_ROOT_NAME):
            logging.getLogger(name).setLevel(level)
