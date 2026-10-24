"""Approved HTTP envelopes; business records remain unchanged."""

from .errors import PipelineError


def paginate(items, page=1, page_size=20):
    if type(page) is not int or type(page_size) is not int or min(page, page_size) < 1:
        raise PipelineError("VALIDATION_ERROR", "page 与 page_size 必须为正整数。")
    page_size = min(page_size, 100)
    total = len(items)
    pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    return {"items": items[start:start + page_size], "page": page,
            "page_size": page_size, "total": total, "total_pages": pages,
            "has_next": page < pages}
