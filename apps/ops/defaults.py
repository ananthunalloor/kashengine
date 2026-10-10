"""The first schedule. The first migration saves it in the database.

After that, an admin edits the schedule on Ops > Schedule. "Reset to default" there uses this
list again. All times are IST. Each entry is (name, task, minute, hour, day of week).
"""

DEFAULT_SCHEDULE: tuple[tuple[str, str, str, str, str], ...] = (
    ("fetch-news-feeds", "news.fetch_feeds", "5", "*/3", "*"),
    # A company is read again only when its data is older than SCREENER_REFRESH_DAYS.
    ("refresh-stale-companies", "companies.refresh_stale", "30", "2", "*"),
    # Also starts after each news fetch.
    ("score-news", "news.score_articles", "20", "*", "*"),
    # Quotes before the prediction. They also check the older predictions.
    ("fetch-market-quotes-morning", "markets.fetch_quotes", "45", "6", "*"),
    ("predict-market", "markets.predict", "0", "7", "*"),
    # The market closes at 15:30. This run gets the final quotes and checks today's prediction.
    ("fetch-market-quotes-evening", "markets.fetch_quotes", "30", "17", "*"),
    # The IPO list (if IPO_FETCH_ENABLED), then the scores. The evening run gets listing results.
    ("collect-ipos-morning", "ipos.collect", "15", "6", "*"),
    ("collect-ipos-evening", "ipos.collect", "45", "18", "*"),
    # GMP and subscription (if IPO_GMP_ENABLED), listing results, and the scores.
    ("refresh-ipo-metrics", "ipos.refresh_metrics", "0", "7-19/2", "*"),
    # After the news scoring, before the report.
    ("score-ipos", "ipos.score", "10", "7", "*"),
    # Deletes old task runs and login events (OPS_RETENTION_DAYS).
    ("prune-ops-history", "ops.prune", "40", "3", "*"),
    # The daily report, then the retry for the chats that did not get it.
    ("send-daily-report", "delivery.send_daily_report", "30", "7", "mon-fri"),
    ("send-daily-report-retry", "delivery.send_daily_report", "50", "7", "mon-fri"),
)
