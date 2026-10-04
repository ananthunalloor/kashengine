"""Common settings for all environments. Dev and prod import from this file."""

from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# In Docker, Compose sets the variables. For local runs, read .env.dev if it exists.
environ.Env.read_env(BASE_DIR / ".env.dev", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.news",
    "apps.companies",
    "apps.ipos",
    "apps.reports",
    "apps.delivery",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery
CELERY_BROKER_URL = env("REDIS_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True

# Local LLM (Ollama). All code reads these values through LLMClient.
LLM_BASE_URL = env("LLM_BASE_URL", default="http://ollama:11434")
LLM_MODEL = env("LLM_MODEL", default="llama3.2:3b")

# News collection
# Standard bot format (like Googlebot). It names our bot and gives a contact link.
# Do not make it look like a browser. Change the link to your own site or repository.
NEWS_USER_AGENT = env(
    "NEWS_USER_AGENT",
    default="Mozilla/5.0 (compatible; KashEngineBot/0.1; +https://github.com/ananthunalloor/kashengine)",
)
NEWS_REQUEST_TIMEOUT = env.int("NEWS_REQUEST_TIMEOUT", default=20)  # seconds
NEWS_FETCH_EVERY_HOURS = env.int("NEWS_FETCH_EVERY_HOURS", default=3)
NEWS_SCRAPE_FULL_TEXT = env.bool("NEWS_SCRAPE_FULL_TEXT", default=True)
NEWS_SCRAPE_DELAY_SECONDS = env.float("NEWS_SCRAPE_DELAY_SECONDS", default=3.0)  # per host
NEWS_SCRAPE_BATCH_SIZE = env.int("NEWS_SCRAPE_BATCH_SIZE", default=50)
NEWS_SCRAPE_MAX_AGE_HOURS = env.int("NEWS_SCRAPE_MAX_AGE_HOURS", default=48)

CELERY_BEAT_SCHEDULE = {
    "fetch-news-feeds": {
        "task": "news.fetch_feeds",
        "schedule": crontab(minute=5, hour=f"*/{NEWS_FETCH_EVERY_HOURS}"),
    },
}

# Telegram
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")

# Report time (IST)
REPORT_HOUR = env.int("REPORT_HOUR", default=7)
REPORT_MINUTE = env.int("REPORT_MINUTE", default=30)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    # These libraries write many debug lines. Dev sets the root level to DEBUG.
    "loggers": {
        name: {"level": "WARNING"}
        for name in ("trafilatura", "htmldate", "courlan", "httpcore", "charset_normalizer")
    },
}
