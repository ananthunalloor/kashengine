"""Development settings."""

import sys

from .base import *
from .base import BASE_DIR, LOG_DIR, LOG_FILE, LOGGING, env

DEBUG = True
ALLOWED_HOSTS = ["*"]
DJANGO_VITE["default"]["dev_mode"] = env.bool("DJANGO_VITE_DEV_MODE", default=True)

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

# Web, realtime, the streamer and several Celery workers write to the same SQLite file in dev.
# WAL lets readers run beside a writer, IMMEDIATE takes the write lock at the start of a
# transaction (no deadlocked upgrades), and the timeout waits for the lock instead of failing.
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"].setdefault("OPTIONS", {}).update(
        {
            "timeout": 20,
            "transaction_mode": "IMMEDIATE",
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
        }
    )

# Caddy (https://localhost/) ends TLS and sets X-Forwarded-Proto. Django then sees HTTPS, and the
# CSRF check accepts the https origin.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING["root"]["level"] = "DEBUG"

# Write the log file, so the Ops log viewer works in dev. Tests do not write it.
if env.bool("DJANGO_LOG_TO_FILE", default="pytest" not in sys.modules):
    LOG_DIR.mkdir(exist_ok=True)
    LOGGING["handlers"]["file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": LOG_FILE,
        "maxBytes": 5 * 1024 * 1024,
        "backupCount": 2,
        "formatter": "standard",
    }
    LOGGING["root"]["handlers"] = ["console", "file"]
