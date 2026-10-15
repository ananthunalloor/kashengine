"""Client for the local LLM server (Ollama).

All code that needs the LLM uses `LLMClient`. The server URL and the model come from the
settings `LLM_BASE_URL` and `LLM_MODEL`. You can give another model to one client, to compare
models.

Callers: `apps.news.sentiment` (scores articles), `apps.news.compare` (compares models),
`apps.ops.health` (the LLM health check) and the commands `llm_check`, `score_news` and
`compare_models`. The client reads the settings `LLM_BASE_URL`, `LLM_MODEL` and
`LLM_TIMEOUT_SECONDS` through `apps.siteconfig.conf`. A value that an admin saved on the
dashboard replaces the environment value.

The client talks to the Ollama HTTP API only: `/api/chat`, `/api/tags` and `/api/pull`. It is
not thread-safe, because it keeps the details of the last call in `last_seconds` and
`last_attempts`. Make one client for each task run.
"""

import json
import logging
import time

import httpx

from apps.siteconfig import conf

logger = logging.getLogger(__name__)

HTTP_NOT_FOUND = 404
HTTP_CLIENT_ERROR = 400  # First status code of the 4xx and 5xx error range.
MAX_ATTEMPTS = 2  # The first try and one retry.
ERROR_TEXT_LIMIT = 200  # Characters of a server error body that we put in a message.


class LLMError(Exception):
    """Base class for all errors of the LLM client.

    Catch this class to handle every LLM failure in one place.
    """


class LLMUnavailableError(LLMError):
    """The server cannot be reached, or it has no such model. Do not try more requests now.

    The client also raises this error for an HTTP error status and for a reply that does not have
    the expected shape. The fault is not in one article, so callers stop the whole run and do not
    count a failed try for the article.
    """


class LLMInvalidOutputError(LLMError):
    """The model answered, but not with valid JSON in the right format (even after a retry).

    The text of the error is the reason that the last answer was not valid. Callers count this as
    a failed try for the item that they were scoring.
    """


def _parse_object(content: str) -> dict:
    """Parse `content` as JSON and check that it is an object.

    `json.JSONDecodeError` is a subclass of `ValueError`, so `chat_json` catches both errors
    together.

    Args:
        content: The text that the model sent back.

    Returns:
        The parsed JSON object.

    Raises:
        ValueError: The text is not valid JSON.
        TypeError: The JSON is not an object.
    """
    data = json.loads(content)
    if not isinstance(data, dict):
        msg = "The answer must be a JSON object."
        raise TypeError(msg)
    return data


class LLMClient:
    """Client for one model on the LLM server.

    One object is bound to one model and one server address. It can be used as a context manager.
    The `with` block closes the HTTP client at the end, but only when this object created it.
    Each `chat_json` call sets `last_attempts` (the number of requests sent) and `last_seconds`
    (the time of the call). The model comparison reads `last_seconds`.
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ):
        """Set up the client. Each argument that is empty falls back to a setting.

        Args:
            model: The model name. If empty, the client uses the setting `LLM_MODEL`.
            base_url: The server address. If empty, the client uses `LLM_BASE_URL`. A slash at
                the end is removed.
            timeout: The time limit, in seconds, for one HTTP request. If empty or zero, the
                client uses `LLM_TIMEOUT_SECONDS`. It is not used when `client` is given.
            client: An HTTP client to use, for example a test client. If given, the caller owns
                it and `close` does not close it.
        """
        self.model = model or conf.LLM_MODEL
        self.base_url = (base_url or conf.LLM_BASE_URL).rstrip("/")
        self.timeout = timeout or conf.LLM_TIMEOUT_SECONDS
        self._own_client = client is None
        self._http = client or httpx.Client(timeout=self.timeout)
        # Details of the last chat_json call. The model comparison uses these.
        self.last_seconds = 0.0
        self.last_attempts = 0

    def close(self) -> None:
        """Close the HTTP client, if this object created it."""
        if self._own_client:
            self._http.close()

    def __enter__(self):
        """Return this client, so it can be used in a `with` block."""
        return self

    def __exit__(self, *exc_info):
        """Close the client when the `with` block ends. Errors are not hidden."""
        self.close()

    def chat_json(self, system: str, user: str, schema: dict | None = None, validate=None) -> dict:
        """Ask the model a question and get a JSON object back.

        If the answer is not valid, ask one more time and tell the model what was wrong. The
        client sends at most two requests (`MAX_ATTEMPTS`). An answer is not valid when it is not
        JSON, when the JSON is not an object, or when `validate` raises `ValueError` or
        `TypeError`. The temperature is 0, so the same input gives nearly the same answer.

        Args:
            system: The system prompt.
            user: The user prompt.
            schema: A JSON schema. Ollama forces the output to follow it. Without it, we ask
                for "json".
            validate: A function that takes the parsed data and returns the clean data. It
                raises ValueError if the data is not good.

        Returns:
            The parsed JSON object. If `validate` is given, the return value of `validate`.

        Raises:
            LLMInvalidOutputError: The second answer is also not valid.
            LLMUnavailableError: The server cannot be reached or has no such model.

        Side effects:
            Sends one or two HTTP requests. Sets `last_attempts` on each try. Sets
            `last_seconds` to the total time, also when the call fails because the answer is not
            valid. When the server is not available, `last_seconds` keeps its old value.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        started = time.monotonic()
        error = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self.last_attempts = attempt
            content = self._chat(messages, schema)
            try:
                data = _parse_object(content)
                result = validate(data) if validate else data
            except (ValueError, TypeError) as exc:  # json.JSONDecodeError is a ValueError.
                error = str(exc)
                logger.warning("LLM answer not valid (try %d): %s", attempt, error)
                messages += [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": f"That answer is not valid: {error}. "
                        "Answer again with only the JSON object, in the format that was asked.",
                    },
                ]
                continue
            self.last_seconds = time.monotonic() - started
            return result
        self.last_seconds = time.monotonic() - started
        raise LLMInvalidOutputError(error)

    def _chat(self, messages: list[dict], schema: dict | None) -> str:
        """Send one chat request and return the text of the answer.

        Args:
            messages: The chat messages, each one a dict with `role` and `content`.
            schema: A JSON schema for the answer. If empty, the request asks for "json".

        Returns:
            The `message.content` text of the server reply.

        Raises:
            LLMUnavailableError: The server cannot be reached, the model is not on the server
                (HTTP 404), the status is 400 or more, or the reply has an unexpected shape.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": schema or "json",
            "options": {"temperature": 0},
        }
        try:
            response = self._http.post(f"{self.base_url}/api/chat", json=payload)
        except httpx.HTTPError as exc:
            msg = f"Cannot reach the LLM server at {self.base_url}: {exc}"
            raise LLMUnavailableError(msg) from exc
        if response.status_code == HTTP_NOT_FOUND:
            raise LLMUnavailableError(
                f"The model '{self.model}' is not on the server. "
                f"Run: python manage.py llm_check --pull (or: ollama pull {self.model})"
            )
        if response.status_code >= HTTP_CLIENT_ERROR:
            msg = f"LLM server error {response.status_code}: {response.text[:ERROR_TEXT_LIMIT]}"
            raise LLMUnavailableError(msg)
        try:
            return response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMUnavailableError(f"Unexpected answer from the LLM server: {exc}") from exc

    def list_models(self) -> list[str]:
        """Return the names of the models on the server.

        Returns:
            The model names, each with its tag, for example `llama3.2:latest`. The list is empty
            when the server has no models.

        Raises:
            LLMUnavailableError: The server is down or gives a bad answer.
        """
        try:
            response = self._http.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            return [item["name"] for item in response.json().get("models", [])]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            msg = f"Cannot read the model list from {self.base_url}: {exc}"
            raise LLMUnavailableError(msg) from exc

    def has_model(self) -> bool:
        """Return True if our model is on the server.

        A name without a tag, such as "llama3.2", also matches "llama3.2:latest". The check
        calls `list_models`, so it sends one HTTP request.

        Returns:
            True if the model is on the server. False if it is not.

        Raises:
            LLMUnavailableError: The server is down or gives a bad answer.
        """
        wanted = self.model if ":" in self.model else f"{self.model}:latest"
        return wanted in self.list_models()

    def pull_model(self) -> None:
        """Download our model to the server. This can take many minutes.

        The request has no time limit, because a pull of a large model is slow. The server
        sends the reply when the download is complete.

        Raises:
            LLMUnavailableError: The request fails or the server sends an error status.

        Side effects:
            The server stores the model files on its disk.
        """
        try:
            response = self._http.post(
                f"{self.base_url}/api/pull",
                json={"model": self.model, "stream": False},
                timeout=None,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"Cannot pull '{self.model}': {exc}") from exc
