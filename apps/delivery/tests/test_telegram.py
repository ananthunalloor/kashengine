"""Tests for the Telegram client. They do not use the network."""

import json

import httpx
import pytest

from apps.delivery.telegram import (
    MAX_MESSAGE_CHARS,
    SAFE_MESSAGE_CHARS,
    TelegramClient,
    TelegramError,
    redact,
    split_message,
)

TOKEN = "123456:SECRET-token"


class Server:
    """A fake Telegram server. It gives the replies in order, and repeats the last one."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply

    def bodies(self):
        return [json.loads(r.content) for r in self.requests]


def ok(result=True) -> httpx.Response:
    return httpx.Response(200, json={"ok": True, "result": result})


def error(code: int, description: str, **extra) -> httpx.Response:
    return httpx.Response(
        code, json={"ok": False, "error_code": code, "description": description, **extra}
    )


def make_client(server: Server, sleeps=None) -> TelegramClient:
    http = httpx.Client(transport=httpx.MockTransport(server))
    return TelegramClient(
        token=TOKEN, client=http, sleep=(sleeps.append if sleeps is not None else lambda s: None)
    )


# --- split_message and redact --------------------------------------------------------------


def test_a_short_text_is_one_part_and_an_empty_text_is_none():
    assert split_message("hello") == ["hello"]
    assert split_message("  \n ") == []


def test_a_long_text_is_split_at_blank_lines():
    blocks = [f"Block {n}\n" + "x" * 900 for n in range(10)]

    parts = split_message("\n\n".join(blocks), limit=2000)

    assert len(parts) > 1
    assert all(len(part) <= 2000 for part in parts)
    assert "\n\n".join(parts) == "\n\n".join(blocks)  # Nothing was lost or cut in a block.


def test_a_block_that_is_too_long_is_split_at_lines_then_spaces_then_anywhere():
    lines_block = "\n".join(f"line {n} " + "y" * 40 for n in range(100))
    spaces_block = " ".join(["word"] * 1000)
    solid_block = "z" * 5000

    parts = split_message("\n\n".join([lines_block, spaces_block, solid_block]), limit=1000)

    assert all(len(part) <= 1000 for part in parts)
    joined = "".join(parts)
    assert joined.count("z") == 5000
    assert joined.count("word") == 1000
    assert joined.count("line ") == 100


def test_the_safe_limit_is_under_the_telegram_limit():
    assert SAFE_MESSAGE_CHARS < MAX_MESSAGE_CHARS


def test_redact_removes_the_token():
    assert redact(f"error at /bot{TOKEN}/send", TOKEN) == "error at /bot<token>/send"
    assert redact("text", "") == "text"


# --- Requests ------------------------------------------------------------------------------


def test_send_message_sends_plain_text_to_the_chat():
    server = Server(ok())

    count = make_client(server).send_message("42", "Hello <b>& co</b>")

    assert count == 1
    assert str(server.requests[0].url) == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    body = server.bodies()[0]
    assert body == {"chat_id": "42", "text": "Hello <b>& co</b>", "disable_web_page_preview": True}
    assert "parse_mode" not in body


def test_a_long_text_goes_in_more_than_one_message():
    server = Server(ok())
    text = "\n\n".join("p" * 1500 for _ in range(6))

    count = make_client(server).send_message("42", text)

    assert count == len(server.requests) > 1
    assert all(len(body["text"]) <= MAX_MESSAGE_CHARS for body in server.bodies())


def test_too_many_requests_waits_once_and_tries_again():
    sleeps = []
    server = Server(error(429, "Too Many Requests", parameters={"retry_after": 3}), ok())

    make_client(server, sleeps).send_message("42", "hi")

    assert sleeps == [3]
    assert len(server.requests) == 2


def test_too_many_requests_twice_or_with_a_long_wait_is_a_retryable_error():
    sleeps = []
    twice = Server(error(429, "x", parameters={"retry_after": 1}))
    with pytest.raises(TelegramError) as info:
        make_client(twice, sleeps).send_message("42", "hi")
    assert info.value.retryable
    assert len(twice.requests) == 2

    long_wait = Server(error(429, "x", parameters={"retry_after": 600}))
    sleeps.clear()
    with pytest.raises(TelegramError) as info:
        make_client(long_wait, sleeps).send_message("42", "hi")
    assert info.value.retryable
    assert sleeps == []


@pytest.mark.parametrize(
    ("code", "description"),
    [(400, "Bad Request: chat not found"), (403, "Forbidden: bot was blocked by the user")],
)
def test_client_errors_are_not_retryable(code, description):
    with pytest.raises(TelegramError, match=description) as info:
        make_client(Server(error(code, description))).send_message("42", "hi")

    assert not info.value.retryable


def test_server_errors_and_network_errors_are_retryable():
    with pytest.raises(TelegramError) as info:
        make_client(Server(error(502, "Bad Gateway"))).send_message("42", "hi")
    assert info.value.retryable

    with pytest.raises(TelegramError) as info:
        make_client(Server(httpx.ConnectError("refused"))).send_message("42", "hi")
    assert info.value.retryable


def test_the_token_is_never_in_an_error_text():
    request_error = httpx.ConnectError(
        f"cannot connect to https://api.telegram.org/bot{TOKEN}/sendMessage"
    )
    with pytest.raises(TelegramError) as info:
        make_client(Server(request_error)).send_message("42", "hi")
    assert TOKEN not in str(info.value)
    assert info.value.__cause__ is None
    assert info.value.__suppress_context__

    with pytest.raises(TelegramError) as info:
        make_client(Server(error(400, f"bad request for bot{TOKEN}"))).send_message("42", "hi")
    assert TOKEN not in str(info.value)


def test_an_answer_that_is_not_json_is_an_error():
    with pytest.raises(TelegramError, match="502"):
        make_client(Server(httpx.Response(502, text="<html>bad gateway</html>"))).get_me()


def test_a_missing_token_is_an_error(settings):
    settings.TELEGRAM_BOT_TOKEN = ""

    with pytest.raises(TelegramError, match="TELEGRAM_BOT_TOKEN"):
        TelegramClient()


def test_get_me():
    server = Server(ok({"username": "kash_bot", "first_name": "Kash"}))

    assert make_client(server).get_me()["username"] == "kash_bot"


def test_get_chats_lists_each_chat_once():
    updates = [
        {
            "update_id": 1,
            "message": {
                "chat": {"id": 11, "type": "private", "first_name": "Ann", "last_name": "Lee"}
            },
        },
        {
            "update_id": 2,
            "message": {
                "chat": {"id": 11, "type": "private", "first_name": "Ann", "last_name": "Lee"}
            },
        },
        {"update_id": 3, "message": {"chat": {"id": -100, "type": "group", "title": "Traders"}}},
        {
            "update_id": 4,
            "channel_post": {
                "chat": {"id": -200, "type": "channel", "title": "News", "username": "news"}
            },
        },
        {"update_id": 5, "my_chat_member": {"nothing": "here"}},
    ]

    chats = make_client(Server(ok(updates))).get_chats()

    assert chats == [
        {"id": 11, "type": "private", "name": "Ann Lee"},
        {"id": -100, "type": "group", "name": "Traders"},
        {"id": -200, "type": "channel", "name": "News"},
    ]
