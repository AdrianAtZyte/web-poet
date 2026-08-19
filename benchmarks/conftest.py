from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from benchmarks.documents import build_page, read_bodies
from web_poet import ItemPage

PageBuilder = Callable[[type[ItemPage], str], Any]


@pytest.fixture(scope="session")
def loop() -> Iterator[asyncio.AbstractEventLoop]:
    """An event loop reused by every benchmark, so that the cost of creating one
    is not measured over and over."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def bodies() -> dict[str, bytes]:
    return read_bodies()


@pytest.fixture(scope="session")
def warm_pages(bodies: dict[str, bytes]) -> PageBuilder:
    pages: dict[tuple[type[ItemPage], str], Any] = {}

    def warm_page(page_cls: type[ItemPage], name: str) -> Any:
        key = (page_cls, name)
        if key not in pages:
            page = build_page(page_cls, name, bodies)
            page.selector
            pages[key] = page
        return pages[key]

    return warm_page


@pytest.fixture(params=["cold", "warm"])
def page(
    request: pytest.FixtureRequest,
    bodies: dict[str, bytes],
    warm_pages: PageBuilder,
) -> PageBuilder:
    """Return a function that builds the named page object.

    A cold page object is a new one over a new response, and so it decodes and
    parses the document again on every call, as it does when a spider downloads
    a page. A warm one is reused, and its selector already exists, which leaves
    only the queries and the field machinery to measure.

    A page object parses the response on its own, rather than sharing the
    selector of the response, so reusing the response is not enough to warm
    one up."""
    if request.param == "warm":
        return warm_pages
    return lambda page_cls, name: build_page(page_cls, name, bodies)
