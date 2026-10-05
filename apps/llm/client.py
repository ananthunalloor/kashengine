"""One client for the local LLM (Ollama). All code that needs the LLM uses this class.

The server URL and the model come from the settings LLM_BASE_URL and LLM_MODEL.
You can give another model for one client, to compare models.
"""

import json
import logging
import time

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base class for LLM errors."""


class LLMUnavailable(LLMError):
    """The server cannot be reached, or it has no such model. Do not try more requests now."""


class LLMInvalidOutput(LLMError):
    """The model answered, but not with valid JSON in the right format (even after a retry)."""


class LLMClient:
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ):
        self.model = model or settings.LLM_MODEL
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.LLM_TIMEOUT_SECONDS
        self._own_client = client is None
        self._http = client or httpx.Client(timeout=self.timeout)
        # Details of the last chat_json call. The model comparison uses these.
        self.last_seconds = 0.0
        self.last_attempts = 0

    def close(self) -> None:
        if self._own_client:
            self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    # --- Chat ---------------------------------------------------------------------------

    def chat_json(self, system: str, user: str, schema: dict | None = None, validate=None) -> dict:
        """Ask the model a question and get a JSON object back.

        schema:   a JSON schema. Ollama forces the output to follow it.
                  Without it, we ask for "json".
        validate: a function that takes the parsed data and returns the clean data. It raises
                  ValueError if the data is not good.
        If the answer is not valid, we ask one more time and tell the model what was wrong.
        Raise LLMInvalidOutput if the second answer is also not valid.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        started = time.monotonic()
        error = ""
        for attempt in (1, 2):
            self.last_attempts = attempt
            content = self._chat(messages, schema)
            try:
                data = json.loads(content)
                if not isinstance(data, dict):
                    raise ValueError("The answer must be a JSON object.")
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
        raise LLMInvalidOutput(error)

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
            raise LLMUnavailable(f"Cannot reach the LLM server at {self.base_url}: {exc}") from exc
        if response.status_code == 404:
            raise LLMUnavailable(
                f"The model '{self.model}' is not on the server. "
                f"Run: python manage.py llm_check --pull (or: ollama pull {self.model})"
            )
        if response.status_code >= 400:
            raise LLMUnavailable(f"LLM server error {response.status_code}: {response.text[:200]}")
        try:
            return response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMUnavailable(f"Unexpected answer from the LLM server: {exc}") from exc

    # --- Server checks ------------------------------------------------------------------

    def list_models(self) -> list[str]:
        """Return the names of the models on the server. Raise LLMUnavailable if it is down."""
        try:
            response = self._http.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            return [item["name"] for item in response.json().get("models", [])]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise LLMUnavailable(f"Cannot read the model list from {self.base_url}: {exc}") from exc

    def has_model(self) -> bool:
        """True if our model is on the server. "llama3.2" also matches "llama3.2:latest"."""
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
            raise LLMUnavailable(f"Cannot pull '{self.model}': {exc}") from exc
