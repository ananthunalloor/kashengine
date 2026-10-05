"""A stand-in for LLMClient, for tests."""


class FakeLLM:
    """It answers like LLMClient.chat_json, without a server.

    answers:  a list. Each item is a dict (the answer of the model), or an exception to raise.
              When the list is empty, `default` is used.
    on_call:  a function that is called with the number of the call, before each answer.
    """

    def __init__(self, answers=None, model="fake-model", default=None, on_call=None):
        self.model = model
        self.answers = list(answers or [])
        self.default = default
        self.on_call = on_call
        self.prompts: list[str] = []
        self.last_seconds = 1.0
        self.last_attempts = 1

    def chat_json(self, system, user, schema=None, validate=None):
        self.prompts.append(user)
        if self.on_call:
            self.on_call(len(self.prompts))
        answer = self.answers.pop(0) if self.answers else self.default
        if isinstance(answer, Exception):
            raise answer
        return validate(answer) if validate else answer

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
