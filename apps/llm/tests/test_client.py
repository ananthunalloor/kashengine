"""Tests for LLMClient and the llm_check command. They do not use the network."""

import json

import httpx
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.llm.client import LLMClient, LLMInvalidOutputError, LLMUnavailableError


def chat_reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})


class Server:
    """A fake Ollama server. It gives the replies in order, and repeats the last one."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply


def make_llm(server: Server) -> LLMClient:
    client = httpx.Client(transport=httpx.MockTransport(server))
    return LLMClient(model="test-model", base_url="http://llm.test/", client=client)


def test_chat_json_sends_the_expected_request():
    server = Server(chat_reply('{"a": 1}'))
    llm = make_llm(server)

    assert llm.chat_json("system text", "user text") == {"a": 1}

    request = server.requests[0]
    body = json.loads(request.content)
    assert str(request.url) == "http://llm.test/api/chat"
    assert body["model"] == "test-model"
    assert body["stream"] is False
    assert body["format"] == "json"
    assert body["options"] == {"temperature": 0}
    assert body["messages"] == [
        {"role": "system", "content": "system text"},
        {"role": "user", "content": "user text"},
    ]
    assert llm.last_attempts == 1


def test_chat_json_sends_the_schema_as_the_format():
    schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
    server = Server(chat_reply('{"a": 1}'))

    make_llm(server).chat_json("s", "u", schema=schema)

    assert json.loads(server.requests[0].content)["format"] == schema


def test_invalid_json_gets_one_retry_with_the_error_message():
    server = Server(chat_reply("Sure! Here is the answer"), chat_reply('{"a": 1}'))
    llm = make_llm(server)

    assert llm.chat_json("s", "u") == {"a": 1}

    assert llm.last_attempts == 2
    assert len(server.requests) == 2
    second = json.loads(server.requests[1].content)["messages"]
    assert second[2] == {"role": "assistant", "content": "Sure! Here is the answer"}
    assert second[3]["role"] == "user"
    assert "not valid" in second[3]["content"]


def test_the_validate_function_can_ask_for_a_retry():
    def validate(data):
        if data["a"] > 1:
            raise ValueError('"a" must be 1 or less')
        return {"a": data["a"], "checked": True}

    server = Server(chat_reply('{"a": 5}'), chat_reply('{"a": 1}'))
    llm = make_llm(server)

    assert llm.chat_json("s", "u", validate=validate) == {"a": 1, "checked": True}
    assert llm.last_attempts == 2
    assert (
        '"a" must be 1 or less' in json.loads(server.requests[1].content)["messages"][3]["content"]
    )


def test_an_answer_that_is_not_an_object_is_not_valid():
    server = Server(chat_reply("[1, 2]"), chat_reply('{"a": 1}'))

    assert make_llm(server).chat_json("s", "u") == {"a": 1}
    assert len(server.requests) == 2


def test_two_invalid_answers_raise_an_error_and_there_is_no_third_try():
    server = Server(chat_reply("not json"), chat_reply("still not json"))

    with pytest.raises(LLMInvalidOutputError):
        make_llm(server).chat_json("s", "u")

    assert len(server.requests) == 2


def test_a_missing_model_raises_unavailable_with_the_fix_and_is_not_retried():
    server = Server(httpx.Response(404, json={"error": "model 'test-model' not found"}))

    with pytest.raises(LLMUnavailableError, match="llm_check --pull"):
        make_llm(server).chat_json("s", "u")

    assert len(server.requests) == 1


@pytest.mark.parametrize(
    "reply",
    [
        httpx.ConnectError("connection refused"),
        httpx.ReadTimeout("timeout"),
        httpx.Response(500, text="boom"),
        httpx.Response(200, json={"unexpected": True}),
    ],
)
def test_server_problems_raise_unavailable(reply):
    with pytest.raises(LLMUnavailableError):
        make_llm(Server(reply)).chat_json("s", "u")


def test_list_models_and_has_model():
    tags = {"models": [{"name": "llama3.2:3b"}, {"name": "tiny:latest"}]}
    llm = make_llm(Server(httpx.Response(200, json=tags)))
    assert llm.list_models() == ["llama3.2:3b", "tiny:latest"]

    assert make_llm(Server(httpx.Response(200, json=tags))).has_model() is False  # "test-model"
    tiny = LLMClient(
        model="tiny",
        base_url="http://llm.test",
        client=httpx.Client(transport=httpx.MockTransport(Server(httpx.Response(200, json=tags)))),
    )
    assert tiny.has_model() is True  # "tiny" matches "tiny:latest".


def test_list_models_raises_unavailable_when_the_server_is_down():
    with pytest.raises(LLMUnavailableError):
        make_llm(Server(httpx.ConnectError("down"))).list_models()


def test_pull_model_asks_the_server_and_reports_errors():
    server = Server(httpx.Response(200, json={"status": "success"}))
    make_llm(server).pull_model()
    assert json.loads(server.requests[0].content) == {"model": "test-model", "stream": False}
    assert str(server.requests[0].url) == "http://llm.test/api/pull"

    with pytest.raises(LLMUnavailableError):
        make_llm(Server(httpx.Response(500, text="no space"))).pull_model()


@pytest.fixture
def fake_server(monkeypatch):
    state = {"models": ["llama3.2:3b"], "pulled": []}

    def list_models(self):
        return list(state["models"])

    def pull_model(self):
        state["pulled"].append(self.model)
        state["models"].append(self.model)

    monkeypatch.setattr(LLMClient, "list_models", list_models)
    monkeypatch.setattr(LLMClient, "pull_model", pull_model)
    return state


def test_llm_check_says_ok_when_the_model_is_there(fake_server, capsys):
    call_command("llm_check", "--model", "llama3.2:3b")
    assert "OK" in capsys.readouterr().out


def test_llm_check_fails_with_a_hint_when_the_model_is_missing(fake_server):
    with pytest.raises(CommandError, match="--pull"):
        call_command("llm_check", "--model", "other:1b")
    assert fake_server["pulled"] == []


def test_llm_check_pulls_the_model_with_the_pull_option(fake_server, capsys):
    call_command("llm_check", "--model", "other:1b", "--pull")
    assert fake_server["pulled"] == ["other:1b"]
    assert "ready" in capsys.readouterr().out


def test_llm_check_turns_a_server_error_into_a_command_error(monkeypatch):
    def list_models(self):
        raise LLMUnavailableError("server is down")

    monkeypatch.setattr(LLMClient, "list_models", list_models)
    with pytest.raises(CommandError, match="server is down"):
        call_command("llm_check")
