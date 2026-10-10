"""Client for the local LLM server (Ollama).

All code that needs the LLM uses `LLMClient`. The server URL and the model come from the
settings `LLM_BASE_URL` and `LLM_MODEL`. You can give another model to one client, to compare
models.
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
    """Base class for LLM errors."""


class LLMUnavailableError(LLMError):
    """The server cannot be reached, or it has no such model. Do not try more requests now."""


class LLMInvalidOutputError(LLMError):
    """The model answered, but not with valid JSON in the right format (even after a retry)."""


def _parse_object(content: str) -> dict:
    """Parse `content` as JSON and check that it is an object.

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
    """Client for one model on the LLM server."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ):
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
        return self

    def __exit__(self, *exc_info):
        self.close()

    def chat_json(self, system: str, user: str, schema: dict | None = None, validate=None) -> dict:
        """Ask the model a question and get a JSON object back.

        If the answer is not valid, ask one more time and tell the model what was wrong.

        Args:
            system: The system prompt.
            user: The user prompt.
            schema: A JSON schema. Ollama forces the output to follow it. Without it, we ask
                for "json".
            validate: A function that takes the parsed data and returns the clean data. It
                raises ValueError if the data is not good.

        Returns:
            The parsed (and validated) JSON object.

        Raises:
            LLMInvalidOutputError: The second answer is also not valid.
            LLMUnavailableError: The server cannot be reached or has no such model.
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

        A name without a tag, such as "llama3.2", also matches "llama3.2:latest".
        """
        wanted = self.model if ":" in self.model else f"{self.model}:latest"
        return wanted in self.list_models()

    def pull_model(self) -> None:
        """Download our model to the server. This can take many minutes."""
        try:
            response = self._http.post(
                f"{self.base_url}/api/pull",
                json={"model": self.model, "stream": False},
                timeout=None,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"Cannot pull '{self.model}': {exc}") from exc
