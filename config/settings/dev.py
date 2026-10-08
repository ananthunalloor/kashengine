"""Development settings."""

from .base import *
from .base import BASE_DIR, LOGGING, env

DEBUG = True
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

# Caddy (https://localhost/) ends TLS and sets X-Forwarded-Proto. Django then sees HTTPS, and the
# CSRF check accepts the https origin.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING["root"]["level"] = "DEBUG"
