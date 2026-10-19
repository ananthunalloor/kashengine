"""Shared bounds and stable ordering for private application tables."""

from django.db.models import F, Model, QuerySet
from ninja import Field, Schema


class TableFilters(Schema):
    """Optional page size preserves the configured default for older clients."""

    page: int = Field(default=1, description="Requested page; out-of-range values are clamped.")
    page_size: int | None = Field(default=None, ge=1, le=100, description="Rows per page, 1-100.")


def ordered[T: Model](rows: QuerySet[T], sort: str, fields: dict[str, str]) -> QuerySet[T]:
    """Apply a validated display sort with nulls last and a stable primary-key tie breaker."""
    if not sort:
        return rows
    field = F(fields[sort.removeprefix("-")])
    expression = field.desc(nulls_last=True) if sort.startswith("-") else field.asc(nulls_last=True)
    return rows.order_by(expression, "pk")
