from flask import request

DEFAULT_PER_PAGE = 12
MAX_PER_PAGE = 50


def get_page_args(default_per_page=DEFAULT_PER_PAGE, max_per_page=MAX_PER_PAGE):
    """Read ?page= and ?per_page= safely (bad values fall back to defaults)."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", default_per_page, type=int)
    page = max(page, 1)
    per_page = min(max(per_page, 1), max_per_page)
    return page, per_page


def pagination_meta(p):
    """Turn a Flask-SQLAlchemy Pagination object into JSON-friendly info."""
    return {
        "page": p.page,
        "per_page": p.per_page,
        "total": p.total,
        "pages": p.pages,
        "has_next": p.has_next,
        "has_prev": p.has_prev,
    }