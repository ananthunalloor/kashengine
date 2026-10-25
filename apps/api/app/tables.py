"""Shared bounds and stable ordering for private application tables."""

from django.db.models import F, Model, QuerySet
from ninja import Field, Schema


class TableFilters(Schema):
    """Optional page size preserves the configured default for older clients."""

    page: int = Field(default=1, description="Requested page; out-of-range values are clamped.")
    page_size: int | None = Field(default=None, ge=1, le=100, description="Rows per page, 1-100.")


def ordered[T: Model](rows: QuerySet[T], sort: str, fields: dict[str, str]) -> QuerySet[T]:
    """Apply a validated display sort with nulls last and a stable primary-key tie breaker.

    The caller must check `sort` first (the schema of the filters has a pattern). A key that is not
    in `fields` raises `KeyError`.

    Args:
        rows: The query set to sort.
        sort: A key of `fields`. A leading minus sign means descending order. An empty text means
            that the caller wants no sort.
        fields: A dict from the display key to the name of the model field.

    Returns:
        The query set unchanged for an empty `sort`. Else the query set ordered by the field, with
        empty values last, and then by `pk` so that the order is stable.
    """
    if not sort:
        return rows
    field = F(fields[sort.removeprefix("-")])
    expression = field.desc(nulls_last=True) if sort.startswith("-") else field.asc(nulls_last=True)
    return rows.order_by(expression, "pk")
