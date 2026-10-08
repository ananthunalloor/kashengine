"""Production settings."""

from .base import *
from .base import BASE_DIR, LOGGING, MIDDLEWARE, env

DEBUG = False

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

# Caddy ends TLS and sets X-Forwarded-Proto. The web container is on a private network, so only
# Caddy can send this header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_REDIRECT_EXEMPT = [r"^health/$"]  # The Docker health check uses plain HTTP.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# We do not join the browser HSTS preload list, because it is hard to undo.
SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Serve the static files from the app. WhiteNoise follows SecurityMiddleware.
MIDDLEWARE = [
    MIDDLEWARE[0],
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]

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
LOGGING["root"]["handlers"] = ["console", "file"]
LOGGING["root"]["level"] = "INFO"
