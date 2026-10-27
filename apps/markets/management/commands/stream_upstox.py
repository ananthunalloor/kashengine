"""Run the optional, TLS-verified Upstox V3 feed worker that powers live browser quotes."""

import logging
import signal
import ssl
import threading

import websocket
from django.core.management.base import BaseCommand, CommandError

from apps.markets.streaming import FeedWriter, authorized_uri
from apps.markets.upstox import mapped_companies
from apps.markets.upstox_client import UpstoxError
from apps.siteconfig import conf

logger = logging.getLogger(__name__)
# Upstox V3 allows up to 2000 instrument keys in `full` mode on one connection.
MAX_INSTRUMENTS = 2000
MAX_BACKOFF_SECONDS = 60


class Command(BaseCommand):
    """Keep a dedicated worker alive; normal web and Celery processes never open a feed."""

    help = (
        "Stream Upstox V3 full-mode quotes for mapped companies and indices: broadcast them to "
        "browser WebSockets about once a second and save one observation per company per 5 "
        "seconds."
    )

    def add_arguments(self, parser):
        """Add `--symbols`, `--no-indices` and `--max-attempts`.

        Args:
            parser: The argument parser of the command.
        """
        parser.add_argument(
            "--symbols", nargs="+", help="Saved company symbols; default: all mapped."
        )
        parser.add_argument(
            "--no-indices",
            action="store_true",
            help="Do not follow the indices of the UPSTOX_STREAM_INDICES setting.",
        )
        parser.add_argument(
            "--max-attempts",
            type=int,
            default=0,
            help="Stop after this many failed connections in a row (default 0: never stop).",
        )

    def handle(self, *args, **options):
        """Run the feed worker until it gets a stop signal or gives up.

        Args:
            *args: Positional arguments of Django. The command ignores them.
            **options: The command options.
        """
        self.symbols = options["symbols"]
        self.indices = not options["no_indices"]
        self.writer()
        self.stream(options["max_attempts"])

    def companies(self, symbols):
        """Find the companies to follow, as a dict from the instrument key to the company.

        Args:
            symbols: The symbols from `--symbols`, or None for all companies that have a key.

        Returns:
            A dict from the Upstox instrument key to the `Company`. Without `--symbols` only the
            first companies (by id) that fit the instrument limit are kept, with a warning.

        Raises:
            CommandError: If a symbol is unknown or has no key, or too many symbols are given.
        """
        companies = mapped_companies()
        if symbols:
            companies = companies.filter(symbol__in=symbols)
            if companies.count() != len(set(symbols)):
                raise CommandError("Every symbol must identify a saved, Upstox-mapped company.")
            if len(set(symbols)) > MAX_INSTRUMENTS:
                raise CommandError(f"Select at most {MAX_INSTRUMENTS} instruments.")
        by_key = {company.upstox_instrument_key: company for company in companies}
        if len(by_key) > MAX_INSTRUMENTS:
            logger.warning(
                "%d mapped companies; streaming only the first %d.", len(by_key), MAX_INSTRUMENTS
            )
            by_key = dict(list(by_key.items())[:MAX_INSTRUMENTS])
        return by_key

    def writer(self) -> FeedWriter:
        """Build a `FeedWriter` with the current companies and indices.

        The command calls it before each connection, so new mappings and index settings apply
        after a reconnect.

        Returns:
            The new writer.

        Raises:
            CommandError: If there is nothing to stream.
        """
        by_key = self.companies(self.symbols)
        indices = list(conf.UPSTOX_STREAM_INDICES or []) if self.indices else []
        indices = indices[: max(0, MAX_INSTRUMENTS - len(by_key))]
        if not by_key and not indices:
            raise CommandError("Map at least one company to Upstox, or configure stream indices.")
        return FeedWriter(by_key, indices)

    def stream(self, max_attempts: int = 0):
        """Connect to the feed and reconnect after each disconnect.

        The wait before a new try grows by powers of 2 seconds, up to 60. A connection that
        received data resets the count. A stop signal (`SIGINT` or `SIGTERM`) closes the socket.
        The old signal handlers are restored at the end.

        Args:
            max_attempts: Give up after this many failed connections in a row. 0 never gives up.

        Raises:
            CommandError: If the stream gives up after `max_attempts` failures.
        """
        stop = threading.Event()
        socket = None
        writer = None

        def shutdown(*_args):
            """Set the stop flag and close the socket. Signal handlers call it."""
            stop.set()
            if socket:
                socket.close()

        old_signals = {sig: signal.signal(sig, shutdown) for sig in (signal.SIGINT, signal.SIGTERM)}
        failures = 0
        try:
            while not stop.is_set():
                writer = self.writer()
                writer.start()
                try:
                    socket = websocket.WebSocketApp(
                        authorized_uri(),
                        on_open=writer.on_open,
                        on_message=writer.on_message,
                        on_error=writer.on_error,
                    )
                    socket.run_forever(
                        sslopt={"cert_reqs": ssl.CERT_REQUIRED, "check_hostname": True},
                        ping_interval=20,
                        ping_timeout=10,
                    )
                except UpstoxError as exc:
                    logger.warning("%s", exc)
                finally:
                    writer.stop()
                if stop.is_set():
                    return
                failures = 0 if writer.received and not writer.invalid else failures + 1
                if max_attempts and failures >= max_attempts:
                    raise CommandError(
                        "Upstox stream stopped after failure; saved quotes remain available."
                    )
                delay = min(2 ** max(failures - 1, 0), MAX_BACKOFF_SECONDS)
                logger.warning("Upstox stream disconnected; reconnecting in %d seconds.", delay)
                stop.wait(delay)
        finally:
            if socket:
                socket.close()
            for sig, handler in old_signals.items():
                signal.signal(sig, handler)
