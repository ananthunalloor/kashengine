"""Pieces that the routers of API v1 share."""

from .schemas import Problem

#: The error answers that every protected endpoint can give. They go in the OpenAPI file.
ERRORS = {401: Problem, 403: Problem, 429: Problem}
#: The same, for an endpoint with parameters.
ERRORS_WITH_VALIDATION = {**ERRORS, 422: Problem}

MAX_SEARCH_CHARS = 100
#: The same, for an endpoint that reads one item by its key. The item may not exist.
ERRORS_WITH_NOT_FOUND = {**ERRORS_WITH_VALIDATION, 404: Problem}
