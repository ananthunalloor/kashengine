"""Development settings."""

import sys

from .base import *
from .base import BASE_DIR, LOG_DIR, LOG_FILE, LOGGING, env

DEBUG = True
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

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
