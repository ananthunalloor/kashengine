"""Common settings for all environments. Dev and prod import from this file."""

from pathlib import Path
from typing import Any

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# Docker Compose sets the variables. Local runs read .env.dev if it exists.
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
    "apps.llm",
    "apps.markets",
    "apps.ops",
    "apps.web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Every page needs a login, unless the view uses @login_not_required (for example /health/).
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
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
                "apps.web.context.web_settings",
                "apps.ops.context.ops_nav",
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

# One login for the whole site. Create it with `createsuperuser`.
LOGIN_URL = "web:login"
LOGIN_REDIRECT_URL = "web:dashboard"
LOGOUT_REDIRECT_URL = "web:login"
# Datastar script URL. To serve it locally, use /static/vendor/datastar.js.
DATASTAR_SRC = env(
    "DATASTAR_SRC",
    default="https://cdn.jsdelivr.net/gh/starfederation/datastar@v1.0.4/bundles/datastar.js",
)
WEB_PAGE_SIZE = env.int("WEB_PAGE_SIZE", default=25)

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery
CELERY_BROKER_URL = env("REDIS_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True

# Local LLM (Ollama).
LLM_BASE_URL = env("LLM_BASE_URL", default="http://ollama:11434")
LLM_MODEL = env("LLM_MODEL", default="llama3.2:3b")
# A small model on a CPU can need a minute for one answer.
LLM_TIMEOUT_SECONDS = env.int("LLM_TIMEOUT_SECONDS", default=180)

# News collection
# The user agent names our bot and gives a contact link. Do not make it look like a browser.
NEWS_USER_AGENT = env(
    "NEWS_USER_AGENT",
    default="Mozilla/5.0 (compatible; KashEngineBot/0.1; +https://github.com/ananthunalloor/kashengine)",
)
NEWS_REQUEST_TIMEOUT = env.int("NEWS_REQUEST_TIMEOUT", default=20)  # Seconds.
NEWS_FETCH_EVERY_HOURS = env.int("NEWS_FETCH_EVERY_HOURS", default=3)
NEWS_SCRAPE_FULL_TEXT = env.bool("NEWS_SCRAPE_FULL_TEXT", default=True)
NEWS_SCRAPE_DELAY_SECONDS = env.float("NEWS_SCRAPE_DELAY_SECONDS", default=3.0)  # Per host.
NEWS_SCRAPE_BATCH_SIZE = env.int("NEWS_SCRAPE_BATCH_SIZE", default=50)
NEWS_SCRAPE_MAX_AGE_HOURS = env.int("NEWS_SCRAPE_MAX_AGE_HOURS", default=48)

# Company data from Screener.in.
SCREENER_ENABLED = env.bool("SCREENER_ENABLED", default=False)
SCREENER_DELAY_SECONDS = env.float("SCREENER_DELAY_SECONDS", default=5.0)
SCREENER_REFRESH_DAYS = env.int("SCREENER_REFRESH_DAYS", default=7)
SCREENER_BATCH_SIZE = env.int("SCREENER_BATCH_SIZE", default=100)

# Sentiment scoring
SENTIMENT_MAX_CHARS = env.int("SENTIMENT_MAX_CHARS", default=2000)  # Article text for the model.
SENTIMENT_BATCH_SIZE = env.int("SENTIMENT_BATCH_SIZE", default=50)  # Articles for each run.
SENTIMENT_MAX_AGE_HOURS = env.int("SENTIMENT_MAX_AGE_HOURS", default=48)
SENTIMENT_MAX_ATTEMPTS = env.int("SENTIMENT_MAX_ATTEMPTS", default=3)

# Market data and the prediction
MARKET_FLAT_BAND_PCT = env.float("MARKET_FLAT_BAND_PCT", default=0.25)  # A day within this is flat.
# The news share of the score. The rest is global cues.
PREDICTION_NEWS_WEIGHT = env.float("PREDICTION_NEWS_WEIGHT", default=0.5)
PREDICTION_THRESHOLD = env.float("PREDICTION_THRESHOLD", default=0.15)  # Score for up or down.
PREDICTION_MIN_ARTICLES = env.int("PREDICTION_MIN_ARTICLES", default=5)

# IPOs. The fetch is OFF by default (see the note in apps/ipos/sources.py).
IPO_FETCH_ENABLED = env.bool("IPO_FETCH_ENABLED", default=False)
# The URL can have {month}, {year}, and {fy}.
IPO_SOURCE_URLS = env.list(
    "IPO_SOURCE_URLS",
    default=[
        "https://webnodejs.chittorgarh.com/cloud/report/data-read/82/1/{month}/{year}/{fy}/0/all/0"
        "?search=&v=1"
    ],
)
# GMP and subscription come from a live table. OFF by default (see the note in apps/ipos/gmp.py).
IPO_GMP_ENABLED = env.bool("IPO_GMP_ENABLED", default=False)
IPO_GMP_URL = env("IPO_GMP_URL", default="https://www.investorgain.com/report/ipo-gmp-live/331/")
# The listing price is the first day open from Yahoo Finance.
IPO_LISTING_ENABLED = env.bool("IPO_LISTING_ENABLED", default=True)
IPO_LISTING_CHECK_DAYS = env.int("IPO_LISTING_CHECK_DAYS", default=14)  # Days to look back.
IPO_KEEP_DAYS = env.int("IPO_KEEP_DAYS", default=60)  # Skip new IPOs that opened earlier (days).
IPO_METRIC_MAX_AGE_HOURS = env.int("IPO_METRIC_MAX_AGE_HOURS", default=72)  # GMP, subscription.
IPO_NEWS_DAYS = env.int("IPO_NEWS_DAYS", default=14)
IPO_GOOD_SCORE = env.float("IPO_GOOD_SCORE", default=0.3)  # A score from this up is "good".
IPO_WEAK_SCORE = env.float("IPO_WEAK_SCORE", default=0.1)  # A score under this is "weak".
IPO_GOOD_GAIN_PCT = env.float("IPO_GOOD_GAIN_PCT", default=10.0)  # A listing gain "did well".

# Telegram. TELEGRAM_CHAT_IDS is a comma-separated list.
# Find your chat ID with `manage.py telegram_check`.
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_CHAT_IDS = env.list("TELEGRAM_CHAT_IDS", default=[])
TELEGRAM_TIMEOUT_SECONDS = env.int("TELEGRAM_TIMEOUT_SECONDS", default=20)

# Report time (IST), on trading days. A retry 20 minutes later sends only to chats that missed it.
REPORT_HOUR = env.int("REPORT_HOUR", default=7)
REPORT_MINUTE = env.int("REPORT_MINUTE", default=30)
REPORT_NEWS_ITEMS = env.int("REPORT_NEWS_ITEMS", default=3)  # For good news, and for bad news.
REPORT_NEWS_MIN_RELEVANCE = env.float("REPORT_NEWS_MIN_RELEVANCE", default=0.4)
REPORT_IPO_ITEMS = env.int("REPORT_IPO_ITEMS", default=6)  # For each IPO list.
REPORT_IPO_DAYS_AHEAD = env.int("REPORT_IPO_DAYS_AHEAD", default=7)

# Ops pages (/ops/, staff only).
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"
OPS_RETENTION_DAYS = env.int("OPS_RETENTION_DAYS", default=90)  # Task runs and login events.
OPS_LOG_TAIL_BYTES = env.int("OPS_LOG_TAIL_BYTES", default=1_000_000)  # How much log to read.
OPS_PAGE_SIZE = env.int("OPS_PAGE_SIZE", default=50)

# All times are IST.
CELERY_BEAT_SCHEDULE = {
    "fetch-news-feeds": {
        "task": "news.fetch_feeds",
        "schedule": crontab(minute=5, hour=f"*/{NEWS_FETCH_EVERY_HOURS}"),
    },
    # A company is read again only when its data is older than SCREENER_REFRESH_DAYS.
    "refresh-stale-companies": {
        "task": "companies.refresh_stale",
        "schedule": crontab(minute=30, hour=2),
    },
    # Also starts after each news fetch.
    "score-news": {
        "task": "news.score_articles",
        "schedule": crontab(minute=20),
    },
    # Quotes before the prediction. Also checks the older predictions.
    "fetch-market-quotes-morning": {
        "task": "markets.fetch_quotes",
        "schedule": crontab(minute=45, hour=6),
    },
    "predict-market": {
        "task": "markets.predict",
        "schedule": crontab(minute=0, hour=7),
    },
    # The market closes at 15:30. Gets the final quotes and checks today's prediction.
    "fetch-market-quotes-evening": {
        "task": "markets.fetch_quotes",
        "schedule": crontab(minute=30, hour=17),
    },
    # IPO list (if IPO_FETCH_ENABLED), then the scores. The evening run gets listing results.
    "collect-ipos-morning": {
        "task": "ipos.collect",
        "schedule": crontab(minute=15, hour=6),
    },
    "collect-ipos-evening": {
        "task": "ipos.collect",
        "schedule": crontab(minute=45, hour=18),
    },
    # GMP and subscription (if IPO_GMP_ENABLED), listing results, and the scores.
    "refresh-ipo-metrics": {
        "task": "ipos.refresh_metrics",
        "schedule": crontab(minute=0, hour="7-19/2"),
    },
    # After the news scoring, before the report.
    "score-ipos": {
        "task": "ipos.score",
        "schedule": crontab(minute=10, hour=7),
    },
    # Deletes old task runs and login events (OPS_RETENTION_DAYS).
    "prune-ops-history": {
        "task": "ops.prune",
        "schedule": crontab(minute=40, hour=3),
    },
    # The daily report, then the retry for the chats that did not get it.
    "send-daily-report": {
        "task": "delivery.send_daily_report",
        "schedule": crontab(minute=REPORT_MINUTE, hour=REPORT_HOUR, day_of_week="mon-fri"),
    },
    "send-daily-report-retry": {
        "task": "delivery.send_daily_report",
        "schedule": crontab(
            minute=(REPORT_HOUR * 60 + REPORT_MINUTE + 20) % 60,
            hour=((REPORT_HOUR * 60 + REPORT_MINUTE + 20) // 60) % 24,
            day_of_week="mon-fri",
        ),
    },
}

LOGGING: dict[str, Any] = {
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
    # httpx logs the full URL of each request. For Telegram the URL contains the bot token.
    "loggers": {
        name: {"level": "WARNING"}
        for name in (
            "trafilatura",
            "htmldate",
            "courlan",
            "httpx",
            "httpcore",
            "charset_normalizer",
        )
    },
}
