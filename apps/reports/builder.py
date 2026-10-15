"""Build the daily report from the data in the database.

The report has four parts: the Nifty 50 outlook, the news, the IPOs, and a short warning that
this is not advice.

The builder reads the data that other apps already saved: the prediction, the news scores and
the IPO rows. It does not call the LLM and it does not use the network, so it works when the LLM
server or Yahoo is down. When data is missing, the text says what is missing.

The builder writes to the database in three places. It updates the status and the score of the
IPO rows, it can create the `Prediction` row for the day, and it saves the `Report` row.

The text is plain text, so Telegram cannot refuse it because of bad mark-up. `Report.data`
keeps the numbers and the lists for the web page.

Callers:
- `apps.delivery.tasks.send_daily_report` and the `send_report` command call `build_report`.
- The `build_report` command of this app calls it too.
- `apps.web.queries` calls `gather_ipos`, `gather_news` and `_strength` for the dashboard.
- `apps.api.v1.schemas` reads `STORY_MIN_SCORE`.

The limits for the lists come from the site settings `REPORT_NEWS_ITEMS`,
`REPORT_NEWS_MIN_RELEVANCE`, `REPORT_IPO_ITEMS` and `REPORT_IPO_DAYS_AHEAD`.
"""

import logging
from datetime import date, datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from apps.ipos.collect import refresh_statuses
from apps.ipos.models import Ipo
from apps.ipos.scoring import likely_good_ipos, score_ipos
from apps.markets.evaluation import MIN_RESULTS_TO_TRUST, accuracy_stats
from apps.markets.models import Prediction
from apps.markets.prediction import make_prediction, news_window_start
from apps.markets.trading import next_trading_day, today_ist
from apps.news.models import NewsArticle
from apps.siteconfig import conf

from .models import Report

logger = logging.getLogger(__name__)

ARROWS = {"up": "▲", "down": "▼", "flat": "▬"}
VERDICTS = {
    "good": "likely to do well",
    "mixed": "mixed",
    "weak": "unlikely to do well",
    "unknown": "no verdict (not enough data)",
}
STORY_MIN_SCORE = 0.2  # A story with a smaller score is neutral. We do not show it.
LAST_RESULT_MAX_AGE_DAYS = 7
WEAK_BELOW = 0.4  # Confidence below this is a weak signal.
MODERATE_BELOW = 0.6  # Confidence below this (and not weak) is a moderate signal.
TITLE_CHARS = 110
REASON_CHARS = 140


def _cut(text: str, limit: int) -> str:
    """Return the text on one line, cut to at most `limit` characters.

    Args:
        text: The text to shorten. `None` counts as an empty text. All runs of white space,
            including new lines, become one space.
        limit: The maximum length of the result, with the ellipsis.

    Returns:
        The text as it is when it is short enough. If not, the text is cut and ends with the
        ellipsis character.
    """
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _day(value: date) -> str:
    """Return a date as a short English label, for example `Tue 6 Oct`.

    Args:
        value: The date to format.

    Returns:
        The short weekday name, the day number without a leading zero, and the short month
        name. The names follow the locale of the process. In the default C locale they are
        in English.
    """
    return f"{value:%a} {value.day} {value:%b}"


def _strength(confidence: float) -> str:
    """Return the word for the strength of a prediction.

    The web app also calls this function.

    Args:
        confidence: The confidence of the prediction, from 0 to 1.

    Returns:
        `weak` below `WEAK_BELOW`, `moderate` below `MODERATE_BELOW`, and `strong` if not.
    """
    if confidence < WEAK_BELOW:
        return "weak"
    if confidence < MODERATE_BELOW:
        return "moderate"
    return "strong"


def gather_prediction(prediction: Prediction) -> dict:
    """Return the numbers of a prediction for the report, with the four strongest cues.

    The function sorts the cues by the size of `weight * signal`. This is the part that each cue
    adds to the score. The biggest part comes first. Only the first four cues stay.

    Args:
        prediction: The saved prediction. Its `inputs` field can have a `cues` list (each cue
            has `name`, `change_pct`, `as_of`, `weight` and `signal`) and a `notes` list.

    Returns:
        A dict with these keys. `target_date` is an ISO date text. `direction`, `confidence`,
        `score`, `news_score`, `news_articles` and `global_score` come from the prediction.
        `news_score` and `global_score` are `None` when that part has no data. `cues` is a list
        of up to four dicts with `name`, `change_pct` and `as_of`. `notes` is the list of notes
        from the prediction, or an empty list.

    Raises:
        KeyError: If a cue in `inputs` has no `name`, `change_pct`, `as_of`, `weight` or
            `signal` key. The function does not catch it.
    """
    cues = prediction.inputs.get("cues", [])
    # The cues that moved the score most come first.
    cues = sorted(cues, key=lambda c: abs(c["weight"] * c["signal"]), reverse=True)
    return {
        "target_date": prediction.target_date.isoformat(),
        "direction": prediction.direction,
        "confidence": prediction.confidence,
        "score": prediction.score,
        "news_score": prediction.news_score,
        "news_articles": prediction.news_articles,
        "global_score": prediction.global_score,
        "cues": [
            {"name": c["name"], "change_pct": c["change_pct"], "as_of": c["as_of"]}
            for c in cues[:4]
        ],
        "notes": prediction.inputs.get("notes", []),
    }


def gather_last_result(today: date) -> dict | None:
    """Return the newest prediction that has a result, if it is not too old.

    A prediction has a result when `correct` is not empty. A void prediction has no result, so
    the function skips it. The prediction must have a target date of at most
    `LAST_RESULT_MAX_AGE_DAYS` days before `today`.

    Args:
        today: The date of the report. The age limit counts back from this date.

    Returns:
        A dict with `target_date` (ISO date text), `direction`, `actual_direction`,
        `actual_change_pct` and `correct`. The value is `None` when no prediction fits.
    """
    last = (
        Prediction.objects.filter(correct__isnull=False)
        .filter(target_date__gte=today - timedelta(days=LAST_RESULT_MAX_AGE_DAYS))
        .order_by("-target_date")
        .first()
    )
    if last is None:
        return None
    return {
        "target_date": last.target_date.isoformat(),
        "direction": last.direction,
        "actual_direction": last.actual_direction,
        "actual_change_pct": last.actual_change_pct,
        "correct": last.correct,
    }


def gather_track_record() -> dict:
    """Return the accuracy numbers of the past predictions for the report.

    The function calls `accuracy_stats` and keeps five of its keys.

    Returns:
        A dict with `total` (the predictions that have a result), `correct`, `accuracy` and
        `baseline_accuracy` (both from 0 to 1), and `enough_results`. `enough_results` is True
        when `total` is at least `MIN_RESULTS_TO_TRUST`. `accuracy` and `baseline_accuracy` are
        `None` when `total` is 0.
    """
    stats = accuracy_stats()
    return {
        "total": stats["total"],
        "correct": stats["correct"],
        "accuracy": stats["accuracy"],
        "baseline_accuracy": stats["baseline_accuracy"],
        "enough_results": stats["enough_results"],
    }


def gather_news(since: datetime, limit: int | None = None) -> dict:
    """Return the counts and the strongest good and bad stories since a time.

    The function takes the scored articles that have a relevance of at least the site setting
    `REPORT_NEWS_MIN_RELEVANCE`. The time of an article is `published_at`. If it is empty, the
    function uses `fetched_at`. The function sorts the articles by the size of the sentiment score
    multiplied by the relevance. The biggest comes first.

    Then it fills two lists. A story with a score of `STORY_MIN_SCORE` or more goes in the good
    list. A story with a score of minus `STORY_MIN_SCORE` or less goes in the bad list. A story
    with a score between them is neutral and goes in no list. A story whose title is the same as
    an earlier story (case and extra spaces do not count) is skipped in both lists. Each list
    stops when it has `limit` stories.

    Args:
        since: The start of the window. It must be timezone-aware.
        limit: The maximum number of stories in each list. The default (`None`) is the site
            setting `REPORT_NEWS_ITEMS`.

    Returns:
        A dict with these keys. `since` is the ISO text of the start. `articles` is the number
        of articles in the window. `positive` and `negative` count the articles with a score of
        `STORY_MIN_SCORE` or more, and of minus `STORY_MIN_SCORE` or less. `good` and `bad` are
        the lists. Each story is a dict with `title`, `source`, `score`, `reason`, `companies`
        (up to three names) and `url`.

    Note:
        The counts `articles`, `positive` and `negative` include articles with a double title
        and articles that did not fit in the lists. Only the lists remove them.
        An article with no relevance value never matches the filter.
    """
    limit = conf.REPORT_NEWS_ITEMS if limit is None else limit
    articles = (
        NewsArticle.objects.filter(
            scored_at__isnull=False,
            sentiment_score__isnull=False,
            relevance__gte=conf.REPORT_NEWS_MIN_RELEVANCE,
        )
        .filter(Q(published_at__gte=since) | Q(published_at__isnull=True, fetched_at__gte=since))
        .prefetch_related("companies")
    )
    ranked = sorted(
        articles, key=lambda a: abs(a.sentiment_score) * (a.relevance or 0), reverse=True
    )

    seen: set[str] = set()
    good: list[dict] = []
    bad: list[dict] = []
    for article in ranked:
        key = " ".join(article.title.lower().split())
        if key in seen:
            continue
        seen.add(key)
        item = {
            "title": _cut(article.title, TITLE_CHARS),
            "source": article.source,
            "score": round(article.sentiment_score, 2),
            "reason": _cut(article.sentiment_reason, REASON_CHARS),
            "companies": [c.name for c in list(article.companies.all())[:3]],
            "url": article.url,
        }
        if article.sentiment_score >= STORY_MIN_SCORE and len(good) < limit:
            good.append(item)
        elif article.sentiment_score <= -STORY_MIN_SCORE and len(bad) < limit:
            bad.append(item)
    return {
        "since": since.isoformat(),
        "articles": len(ranked),
        "positive": sum(a.sentiment_score >= STORY_MIN_SCORE for a in ranked),
        "negative": sum(a.sentiment_score <= -STORY_MIN_SCORE for a in ranked),
        "good": good,
        "bad": bad,
    }


def _ipo_item(ipo: Ipo) -> dict:
    """Convert an IPO row to a dict that the report and the web page can use.

    Args:
        ipo: The IPO row.

    Returns:
        A dict with `name`, `category`, `status`, `open_date`, `close_date`, `listing_date`
        (ISO date text or `None`), `price_band_low` and `price_band_high` (numbers or `None`),
        `gmp_pct` (rounded to one decimal, or `None`), `subscription_times` (a number or `None`),
        `verdict` and `score`. An empty verdict becomes `unknown`. A price or a subscription of 0
        becomes `None`.
    """
    gmp_pct = ipo.gmp_pct
    return {
        "name": ipo.name,
        "category": ipo.category,
        "status": ipo.status,
        "open_date": ipo.open_date.isoformat() if ipo.open_date else None,
        "close_date": ipo.close_date.isoformat() if ipo.close_date else None,
        "listing_date": ipo.listing_date.isoformat() if ipo.listing_date else None,
        "price_band_low": float(ipo.price_band_low) if ipo.price_band_low else None,
        "price_band_high": float(ipo.price_band_high) if ipo.price_band_high else None,
        "gmp_pct": None if gmp_pct is None else round(gmp_pct, 1),
        "subscription_times": float(ipo.subscription_times) if ipo.subscription_times else None,
        "verdict": ipo.verdict or "unknown",
        "score": ipo.score,
    }


def gather_ipos(today: date, limit: int | None = None, days_ahead: int | None = None) -> dict:
    """Return the IPO groups that matter on a day.

    The function makes these groups.

    - `open_now`: the IPOs that open on or before `today` and close on or after it. It orders
      them by the close date, then by name.
    - `listing_today`: the IPOs with the listing date `today`.
    - `upcoming`: the IPOs that open after `today` and not later than `days_ahead` days from it.
    - `likely_good`: the open or coming IPOs with the verdict good, from `likely_good_ipos`.
      The best score comes first.

    Each group has at most `limit` items.

    Args:
        today: The date of the report.
        limit: The maximum number of items in each group. The default (`None`) is the site
            setting `REPORT_IPO_ITEMS`.
        days_ahead: How many days to look ahead for the upcoming IPOs. The default (`None`) is
            the site setting `REPORT_IPO_DAYS_AHEAD`.

    Returns:
        A dict with the four groups as lists of `_ipo_item` dicts. It also has `without_verdict`
        and `days_ahead`. `without_verdict` is the number of IPOs in `open_now` and `upcoming`
        that have no verdict or the verdict unknown. The `limit` does not change this number.
        `days_ahead` is the value that the function used.

    Note:
        An IPO can be in more than one group, for example in `open_now` and `likely_good`.
        An IPO that has the same date for the opening and for the listing can be in two groups.
    """
    limit = conf.REPORT_IPO_ITEMS if limit is None else limit
    days_ahead = conf.REPORT_IPO_DAYS_AHEAD if days_ahead is None else days_ahead
    ordering = ("close_date", "name")

    open_now = Ipo.objects.filter(open_date__lte=today, close_date__gte=today).order_by(*ordering)
    listing_today = Ipo.objects.filter(listing_date=today).order_by("name")
    upcoming = Ipo.objects.filter(
        open_date__gt=today, open_date__lte=today + timedelta(days=days_ahead)
    ).order_by("open_date", "name")
    good = likely_good_ipos(today)

    watched = [*open_now, *upcoming]
    return {
        "open_now": [_ipo_item(i) for i in open_now[:limit]],
        "listing_today": [_ipo_item(i) for i in listing_today[:limit]],
        "upcoming": [_ipo_item(i) for i in upcoming[:limit]],
        "likely_good": [_ipo_item(i) for i in good[:limit]],
        "without_verdict": sum(1 for i in watched if (i.verdict or "unknown") == "unknown"),
        "days_ahead": days_ahead,
    }


def gather(day: date, prediction: Prediction) -> dict:
    """Collect all the data for the report of one day.

    The news window starts at the close of the trading day before the target day of the
    prediction. This is the same window that the prediction used.

    Args:
        day: The date of the report (the IST date of the build).
        prediction: The prediction for the report. Its target date is the day that the report
            talks about. It can be later than `day`, for example on a weekend.

    Returns:
        A dict with `date` (ISO text), `prediction`, `last_result`, `track_record`, `news` and
        `ipos`. Each value comes from the `gather_*` function with that name.
        `last_result` can be `None`. This dict is saved in `Report.data`.
    """
    return {
        "date": day.isoformat(),
        "prediction": gather_prediction(prediction),
        "last_result": gather_last_result(day),
        "track_record": gather_track_record(),
        "news": gather_news(news_window_start(prediction.target_date)),
        "ipos": gather_ipos(day),
    }


def _price(item: dict) -> str:
    """Return the price band of an IPO item as text.

    Args:
        item: An IPO dict from `_ipo_item`.

    Returns:
        `price band not known` when the high price is empty. One price (for example `₹100`)
        when the low price is empty or the same as the high price. Else a range such as
        `₹95-100`.
    """
    low, high = item["price_band_low"], item["price_band_high"]
    if high is None:
        return "price band not known"
    if low is None or low == high:
        return f"₹{high:g}"
    return f"₹{low:g}-{high:g}"


def _ipo_line(item: dict, show_verdict: bool = True) -> str:
    """Return one text line for an IPO item.

    The line has a bullet, the name, `SME` or `mainboard`, and a list of facts. The facts are the
    price, the close date (open IPO) or the open date (coming IPO), the GMP, the subscription
    and the verdict. A fact is left out when its value is empty.

    Args:
        item: An IPO dict from `_ipo_item`.
        show_verdict: False leaves the verdict out. The listing list does this, because the
            verdict is not useful on the day of the listing.

    Returns:
        The line as text, without a new line character.
    """
    parts = [_price(item)]
    if item["status"] == "open" and item["close_date"]:
        parts.append(f"closes {_day(date.fromisoformat(item['close_date']))}")
    elif item["status"] == "upcoming" and item["open_date"]:
        parts.append(f"opens {_day(date.fromisoformat(item['open_date']))}")
    if item["gmp_pct"] is not None:
        parts.append(f"GMP {item['gmp_pct']:+.0f}%")
    if item["subscription_times"] is not None:
        parts.append(f"subscribed {item['subscription_times']:g}x")
    if show_verdict:
        parts.append(VERDICTS[item["verdict"]])
    kind = "SME" if item["category"] == "sme" else "mainboard"
    return f"• {item['name']} ({kind}): " + ", ".join(parts)


def _render_outlook(data: dict) -> list[str]:
    """Return the lines of the Nifty 50 outlook section.

    The section has the title, the direction with its strength and score, the news and global
    parts, the strongest cues, the notes, the last result, and the track record. It says that
    the strength is not a probability. If the track record has fewer than
    `MIN_RESULTS_TO_TRUST` results, it adds a warning.

    Args:
        data: The dict from `gather`.

    Returns:
        A list of text lines.
    """
    p = data["prediction"]
    target = date.fromisoformat(p["target_date"])
    lines = [
        f"NIFTY 50 OUTLOOK, {_day(target)}",
        f"{ARROWS[p['direction']]} {p['direction'].upper()}: {_strength(p['confidence'])} signal "
        f"(strength {p['confidence']:.2f}, score {p['score']:+.2f}).",
        "The strength is not a probability.",
    ]
    news = (
        "no scored news"
        if p["news_score"] is None
        else f"{p['news_score']:+.2f} from {p['news_articles']} articles"
    )
    glob = "no data" if p["global_score"] is None else f"{p['global_score']:+.2f}"
    lines.append(f"News: {news}. Global markets: {glob}.")
    if p["cues"]:
        lines.append(
            "Cues: " + ", ".join(f"{c['name']} {c['change_pct']:+.1f}%" for c in p["cues"])
        )
    lines.extend(f"Note: {note}" for note in p["notes"])

    last = data["last_result"]
    if last:
        verdict = "right" if last["correct"] else "wrong"
        lines.append(
            f"Last result ({_day(date.fromisoformat(last['target_date']))}): we said "
            f"{last['direction']}, the market was {last['actual_direction']} "
            f"({last['actual_change_pct']:+.2f}%). We were {verdict}."
        )
    record = data["track_record"]
    if record["total"]:
        line = (
            f"Track record: {record['correct']} of {record['total']} right "
            f"({record['accuracy'] * 100:.0f}%). Simple baseline: "
            f"{record['baseline_accuracy'] * 100:.0f}%."
        )
        if not record["enough_results"]:
            line += f" Only {record['total']} results. Wait for {MIN_RESULTS_TO_TRUST}."
        lines.append(line)
    else:
        lines.append("Track record: no results yet.")
    return lines


def _render_story(item: dict) -> list[str]:
    """Return the lines of one news story.

    Args:
        item: A story dict from `gather_news`.

    Returns:
        The title line with the source and the score, then optional lines for the reason and
        the companies, then the link.
    """
    head = f"• {item['title']} ({item['source']}, {item['score']:+.1f})"
    lines = [head]
    if item["reason"]:
        lines.append(f"  {item['reason']}")
    if item["companies"]:
        lines.append("  Companies: " + ", ".join(item["companies"]))
    lines.append(f"  {item['url']}")
    return lines


def _render_news(news: dict) -> list[str]:
    """Return the lines of the news section.

    Args:
        news: The dict from `gather_news`.

    Returns:
        The title line, the counts of good, bad and neutral articles, and the good and bad
        stories. If there is no scored article, the function returns the title and a line that
        says the news service or the LLM service can be down.
    """
    lines = ["NEWS SINCE THE LAST CLOSE"]
    if not news["articles"]:
        lines.append("No scored news. The news or the LLM service may be down.")
        return lines
    neutral = news["articles"] - news["positive"] - news["negative"]
    lines.append(
        f"{news['articles']} important articles: {news['positive']} good, "
        f"{news['negative']} bad, {neutral} neutral."
    )
    if news["good"]:
        lines.append("Good:")
        for item in news["good"]:
            lines.extend(_render_story(item))
    if news["bad"]:
        lines.append("Bad:")
        for item in news["bad"]:
            lines.extend(_render_story(item))
    return lines


def _render_ipos(ipos: dict) -> list[str]:
    """Return the lines of the IPO section.

    The section lists the IPOs that list today, that are open, and that come soon, and then the
    IPOs that are likely to do well. If the first three lists are empty, it says so. It adds a
    warning for the IPOs that have no verdict. The warning says that the GMP is not official
    data.

    Args:
        ipos: The dict from `gather_ipos`.

    Returns:
        A list of text lines.
    """
    lines = ["IPOS"]
    empty = True
    if ipos["listing_today"]:
        empty = False
        lines.append("Listing today:")
        lines.extend(_ipo_line(i, show_verdict=False) for i in ipos["listing_today"])
    if ipos["open_now"]:
        empty = False
        lines.append("Open now:")
        lines.extend(_ipo_line(i) for i in ipos["open_now"])
    if ipos["upcoming"]:
        empty = False
        lines.append(f"Coming in the next {ipos['days_ahead']} days:")
        lines.extend(_ipo_line(i) for i in ipos["upcoming"])
    if empty:
        lines.append(f"No IPO is open, listing, or coming in the next {ipos['days_ahead']} days.")
    if ipos["likely_good"]:
        lines.append("Likely to do well (our rule, not a promise):")
        lines.extend(f"• {i['name']} (score {i['score']:+.2f})" for i in ipos["likely_good"])
    if ipos["without_verdict"]:
        count = ipos["without_verdict"]
        subject = "1 IPO has" if count == 1 else f"{count} IPOs have"
        lines.append(
            f"{subject} no verdict: the GMP or the subscription is not entered. "
            "The GMP is not official data."
        )
    return lines


def render_text(data: dict) -> str:
    """Make the plain text of the report from the data.

    The text has a title, the outlook, the news, the IPOs, and a line that says the report is not
    investment advice. A blank line separates the sections. The function makes no database query
    and no network call.

    Args:
        data: The dict from `gather`, or the `Report.data` of a saved report.

    Returns:
        The report as plain text.
    """
    day = date.fromisoformat(data["date"])
    sections = [
        [f"KASH ENGINE: DAILY REPORT, {_day(day)} {day.year}"],
        _render_outlook(data),
        _render_news(data["news"]),
        _render_ipos(data["ipos"]),
        ["This is an automated summary for information. It is not investment advice."],
    ]
    return "\n\n".join("\n".join(section) for section in sections)


def _refresh_ipos(day: date, now: datetime) -> None:
    """Update the IPO status and scores, so the report shows the newest GMP and subscription.

    The function calls `refresh_statuses` and then `score_ipos`. It uses no network. If any
    exception happens, the function logs it and returns. The report is then built with the
    scores that the database already has.

    Args:
        day: The date of the report. `refresh_statuses` uses it to set the IPO status.
        now: The current time. `score_ipos` uses it as the time of the scoring.

    Side effects:
        Updates the status and the listing gain of IPO rows, and the score, the verdict and the
        score time of the IPO rows that are not listed.
    """
    try:
        refresh_statuses(day)
        score_ipos(now)
    except Exception:
        logger.exception("The IPO scores could not be updated. The report uses the saved scores.")


def build_report(
    day: date | None = None, now: datetime | None = None, force: bool = False
) -> tuple[Report, bool]:
    """Build and save the report for a day. Return (report, created).

    The prediction is for the first trading day that is `day` or later. On a Monday to Friday, this
    is `day` itself. On a Saturday or Sunday, it is the next Monday.

    If a report for the day exists, the function returns it and does not change it. A second run
    or a retry then sends the same text. With `force`, the function builds the report again.

    The steps are: update the IPO status and scores, get the prediction (`make_prediction` makes
    it when none exists), collect the data, make the text, and save the report.

    Args:
        day: The date of the report. The default (`None`) is the IST date of `now`.
        now: The current time. It must be timezone-aware. The default (`None`) is the current
            time.
        force: True builds the report again when one exists for the day.

    Returns:
        A tuple of the `Report` and a flag. The flag is False when the function returned an
        existing report. It is True when the function built and saved the report in this call,
        also when `force` replaced an old report.

    Side effects:
        Creates or updates the `Report` row for `day`. Can create the `Prediction` row. Updates
        the IPO rows (see `_refresh_ipos`). Writes a log line.

    Note:
        `force` does not make the prediction again. If a prediction exists for the target day,
        the new report uses it. Use `predict_market --force` to change the prediction first.
    """
    now = now or timezone.now()
    day = day or today_ist(now)
    existing = Report.objects.filter(date=day).first()
    if existing and not force:
        return existing, False

    _refresh_ipos(day, now)
    prediction, _ = make_prediction(next_trading_day(day), now=now)
    data = gather(day, prediction)
    report, _ = Report.objects.update_or_create(
        date=day,
        defaults={
            "text": render_text(data),
            "prediction": prediction.direction,
            "confidence": prediction.confidence,
            "data": data,
        },
    )
    logger.info("Report for %s built (%d characters)", day, len(report.text))
    return report, True
