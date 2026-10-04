"""Production settings."""

from .base import *  # noqa: F403
from .base import BASE_DIR, LOGGING, env

DEBUG = False

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

# HTTPS behind Nginx
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_REDIRECT_EXEMPT = [r"^health/$"]  # The Docker health check uses plain HTTP.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Log to a file in prod. The folder is a Docker volume.
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOGGING["handlers"]["file"] = {
    "class": "logging.handlers.RotatingFileHandler",
    "filename": LOG_DIR / "app.log",
    "maxBytes": 10 * 1024 * 1024,
    "backupCount": 5,
    "formatter": "standard",
}
LOGGING["root"]["handlers"] = ["console", "file"]  # ty: ignore[invalid-assignment]
LOGGING["root"]["level"] = "INFO"  # ty: ignore[invalid-assignment]
