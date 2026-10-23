"""Run an optional, TLS-verified Upstox V3 feed worker with persisted observations."""

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
MAX_INSTRUMENTS = 100


class Command(BaseCommand):
    """Keep a dedicated worker alive; normal web and Celery processes never open a feed."""

    help = "Stream Upstox V3 quotes to the database (one observation per company per 5 seconds)."

    def add_arguments(self, parser):
        """Allow a bounded subset of the saved company directory."""
        parser.add_argument(
            "--symbols", nargs="+", help="Saved company symbols; default: all mapped."
        )

    def handle(self, *args, **options):
        """Reconnect with bounded backoff, refresh authorization, and stop cleanly on signals."""
        by_key = self.companies(options["symbols"])
        self.stream(FeedWriter(by_key))

    def companies(self, symbols):
        """Reject unknown symbols and provider subscription-limit overflows explicitly."""
        companies = mapped_companies()
        if symbols:
            companies = companies.filter(symbol__in=symbols)
            if companies.count() != len(set(symbols)):
                raise CommandError("Every symbol must identify a saved, Upstox-mapped company.")
        by_key = {company.upstox_instrument_key: company for company in companies}
        if not by_key or len(by_key) > MAX_INSTRUMENTS:
            raise CommandError("Select between 1 and 100 mapped instruments using --symbols.")
        return by_key

    def stream(self, writer):
        """Own the socket lifecycle and restore process signal handlers on every exit."""
        stop = threading.Event()
        socket = None

        def shutdown(*_args):
            stop.set()
            if socket:
                socket.close()

        old_signals = {sig: signal.signal(sig, shutdown) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            for attempt in range(5):
                if stop.is_set():
                    return
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
                if stop.is_set():
                    return
                if writer.invalid or not conf.UPSTOX_ENABLED:
                    break
                logger.warning("Upstox stream disconnected; reconnect attempt %d/5.", attempt + 1)
                stop.wait(min(2**attempt, 30))
            raise CommandError(
                "Upstox stream stopped after failure; saved quotes remain available."
            )
        finally:
            if socket:
                socket.close()
            for sig, handler in old_signals.items():
                signal.signal(sig, handler)
