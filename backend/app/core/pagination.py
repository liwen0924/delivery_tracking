"""Server-side pagination primitives shared by every list endpoint.

Every collection in this API is paginated by default — there is no code path
that loads a whole table. `PageParams` is a FastAPI dependency, `Page[T]` is
the envelope every list response uses.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil

from fastapi import Query
from pydantic import BaseModel, Field

from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class PageParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def page_params(
    page: int = Query(1, ge=1, description="1-based page number."),
    page_size: int | None = Query(
        None,
        ge=1,
        le=get_settings().max_page_size,
        description="Rows per page; capped server-side.",
    ),
) -> PageParams:
    settings = get_settings()
    size = page_size or settings.default_page_size
    return PageParams(page=page, page_size=min(size, settings.max_page_size))


class PageMeta(BaseModel):
    page: int = Field(description="1-based page number.")
    page_size: int
    total_items: int
    total_pages: int
    has_previous: bool
    has_next: bool


class Page[T](BaseModel):
    items: list[T]
    meta: PageMeta

    @classmethod
    def build(cls, items: Sequence[T], total: int, params: PageParams) -> Page[T]:
        total_pages = ceil(total / params.page_size) if total else 0
        return cls(
            items=list(items),
            meta=PageMeta(
                page=params.page,
                page_size=params.page_size,
                total_items=total,
                total_pages=total_pages,
                has_previous=params.page > 1,
                has_next=params.page < total_pages,
            ),
        )
