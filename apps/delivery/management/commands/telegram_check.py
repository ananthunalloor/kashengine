"""Management command: check the Telegram bot token and list the chat IDs."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.delivery.service import configured_chat_ids
from apps.delivery.telegram import TelegramClient, TelegramError


class Command(BaseCommand):
    """Check the bot token and show the chats."""

    help = (
        "Check the bot token, and show the chat IDs of the chats that sent a message to the bot. "
        "Put the ID of your chat in TELEGRAM_CHAT_IDS."
    )

    def handle(self, *args, **options):
        """Run the command."""
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("TELEGRAM_BOT_TOKEN is not set. Get a token from @BotFather.")
        try:
            with TelegramClient() as client:
                me = client.get_me()
                self.stdout.write(f"Bot: @{me.get('username')} ({me.get('first_name')})")
                chats = client.get_chats()
        except TelegramError as exc:
            raise CommandError(str(exc)) from exc

        configured = configured_chat_ids()
        self.stdout.write(f"TELEGRAM_CHAT_IDS: {', '.join(configured) or 'empty'}")
        if not chats:
            self.stdout.write(
                "No chat found. Send any message to your bot in Telegram, then run this again. "
                "(Telegram keeps these messages for 24 hours.)"
            )
            return
        self.stdout.write("Chats that wrote to the bot:")
        for chat in chats:
            mark = "  (set)" if str(chat["id"]) in configured else ""
            self.stdout.write(f"  {chat['id']}  {chat['type']}  {chat['name']}{mark}")
