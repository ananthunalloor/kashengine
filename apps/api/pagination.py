"""Paging for list endpoints.

Every list answers with the same shape:

    {"items": [...], "count": 120, "limit": 25, "offset": 0}

`count` is the number of rows that match the filters, not the size of the page. A client reads
the next page with `offset = offset + limit`.
"""

from typing import Any

from django.db.models import QuerySet
from ninja import Field, Schema

from apps.siteconfig import conf

from .errors import ApiError

HARD_LIMIT_MAX = 500
HARD_OFFSET_MAX = 1_000_000


class PageParams(Schema):
    """The paging parameters. List filters extend this class."""

    limit: int | None = Field(
        None,
        ge=1,
        le=HARD_LIMIT_MAX,
        description="The most rows to return. The default and the largest value are server "
        "settings (default 25, largest 100 unless an admin changed them).",
    )
    offset: int = Field(
        0,
        ge=0,
        le=HARD_OFFSET_MAX,
        description="How many rows to skip. Use it to read the next page.",
    )


def stable(queryset: QuerySet) -> QuerySet:
    """Add the primary key to the sort order, so that equal rows never change place between pages.

    Args:
        queryset: A queryset, with or without an `order_by`.

    Returns:
        The same queryset, sorted by its own order and then by `pk`.
    """
    order = list(queryset.query.order_by or queryset.model._meta.ordering)  # noqa: SLF001
    return queryset.order_by(*order, "pk")


def window(params: PageParams) -> tuple[int, int]:
    """Return the `(limit, offset)` to use, after the server limits.

    Args:
        params: The parsed paging parameters.

    Returns:
        The limit (the default if the client sent none) and the offset.

    Raises:
        ApiError: `validation_error` when the limit is larger than `API_PAGE_SIZE_MAX`.
    """
    largest = conf.API_PAGE_SIZE_MAX
    limit = params.limit or min(conf.API_PAGE_SIZE, largest)
    if limit > largest:
        raise ApiError(
            "validation_error",
            f"The limit may not be more than {largest}.",
            errors=[
                {
                    "field": "limit",
                    "message": f"Must be at most {largest}.",
                    "type": "less_than_equal",
                }
            ],
        )
    return limit, params.offset


def paginate(queryset: QuerySet, params: PageParams, convert=None) -> dict[str, Any]:
    """Cut a queryset into one page and return the list answer.

    Args:
        queryset: The rows that match the filters.
        params: The parsed paging parameters.
        convert: An optional function that turns one row into the item for the answer. The
            default keeps the row, and the response schema reads its attributes.

    Returns:
        A dict with `items`, `count`, `limit` and `offset`.

    Raises:
        ApiError: `validation_error` for a limit that is too large.
    """
    limit, offset = window(params)
    rows = list(stable(queryset)[offset : offset + limit])
    return {
        "items": [convert(row) for row in rows] if convert else rows,
        "count": queryset.count(),
        "limit": limit,
        "offset": offset,
    }
