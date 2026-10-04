"""Development settings."""

from .base import *  # noqa: F403
from .base import LOGGING

DEBUG = True
ALLOWED_HOSTS = ["*"]

LOGGING["root"]["level"] = "DEBUG"
