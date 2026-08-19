from __future__ import annotations

import gzip
from pathlib import Path
from typing import Any

from web_poet import HttpResponse, ItemPage

FIXTURES = Path(__file__).parent / "fixtures"

#: Every fixture is served as a real response of its website would be, charset
#: included, so that encoding detection is not part of what is measured.
HEADERS = {"Content-Type": "text/html; charset=utf-8"}

URLS = {
    "product": "https://www.ecommerce.example/dp/B0BENCH001",
    "article": "https://www.news.example/news/articles/b3nchmarkid0",
    "job": "https://www.jobs.example/jobs/view/9000000001",
    "minimal": "https://www.example.com/",
}

MINIMAL_BODY = b"""<html><head><title>Alder Vale</title></head>
<body><h1>Copper Ridge</h1><a href="/aspen">Aspen</a></body></html>"""


def read_bodies() -> dict[str, bytes]:
    """Return the body of every document, keyed by name."""
    bodies = {
        name: gzip.decompress((FIXTURES / f"{name}.html.gz").read_bytes())
        for name in URLS
        if name != "minimal"
    }
    return bodies | {"minimal": MINIMAL_BODY}


def build_page(page_cls: type[ItemPage], name: str, bodies: dict[str, bytes]) -> Any:
    return page_cls(
        response=HttpResponse(URLS[name], body=bodies[name], headers=HEADERS)
    )  # type: ignore[call-arg]
