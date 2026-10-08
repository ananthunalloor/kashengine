"""Development settings."""

from .base import *
from .base import BASE_DIR, LOGGING, env

DEBUG = True
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

LOGGING["root"]["level"] = "DEBUG"
