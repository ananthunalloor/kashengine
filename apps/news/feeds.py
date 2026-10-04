"""Free RSS feeds from Indian financial news sources.

To add a source, add one `Feed` line. To stop one, remove it or set `enabled=False`.
A feed that fails is logged and skipped. It does not stop the other feeds.

Test status:
- Business Standard: tested and working.
- Economic Times and Mint: URLs from public feed lists. Not tested here.
- Moneycontrol: URLs from memory. Not tested here. Check them first.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Feed:
    source: str
    name: str
    url: str
    enabled: bool = True


FEEDS = [
    # Business Standard
    Feed("Business Standard", "Markets", "https://www.business-standard.com/rss/markets-106.rss"),
    # Economic Times
    Feed(
        "Economic Times",
        "Markets",
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    ),
    Feed(
        "Economic Times",
        "Stocks",
        "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    ),
    Feed(
        "Economic Times",
        "IPO",
        "https://economictimes.indiatimes.com/markets/ipos/fpos/rssfeeds/14655708.cms",
    ),
    # Mint
    Feed("Mint", "Markets", "https://www.livemint.com/rss/markets"),
    Feed("Mint", "Companies", "https://www.livemint.com/rss/companies"),
    # Moneycontrol
    Feed("Moneycontrol", "Top news", "https://www.moneycontrol.com/rss/MCtopnews.xml"),
    Feed("Moneycontrol", "Market reports", "https://www.moneycontrol.com/rss/marketreports.xml"),
    Feed("Moneycontrol", "Business", "https://www.moneycontrol.com/rss/business.xml"),
]
