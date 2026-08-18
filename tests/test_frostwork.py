from __future__ import annotations

import asyncio

import attrs
import parsel
import pytest

from web_poet import (
    BrowserPage,
    BrowserResponse,
    HttpResponse,
    SelectorExtractor,
    WebPage,
    css,
    field,
    jmespath,
    xpath,
)
from web_poet import mixins as _mixins
from web_poet._frostwork import _get_page

pytest.importorskip("frostwork")

HTML = """
<html>
  <head>
    <meta itemprop="brand" content="Acme">
    <script type="application/ld+json">{"sku": "SKU-1"}</script>
  </head>
  <body>
    <h1> Foo </h1>
    <p class="price">10.00</p>
    <img src="a.png"><img src="b.png">
    <div class="desc">A description</div>
  </body>
</html>
"""


@pytest.fixture
def response():
    return HttpResponse("http://example.com", HTML.encode("utf-8"), encoding="utf-8")


@pytest.fixture
def parsel_only(monkeypatch):
    """Disable frostwork, so that parsel extracts every declaration."""
    monkeypatch.setattr(_mixins, "_frostwork_extract", lambda instance, names: {})


@attrs.define
class Page(WebPage):
    name = field(css("h1::text").get())
    images = field(css("img::attr(src)").getall())
    brand = field(xpath("//meta[@itemprop='brand']/@content").get())
    sources = field(xpath("//img/@src").getall())
    missing = field(css(".missing::text").get())

    # Neither a selector list nor JMESPath is something that frostwork can
    # extract, and :contains() is beyond its selector support.
    price = field(css(".price::text"), out=[lambda value: value.get()])
    sku = field(jmespath("sku").get())
    description = field(css(".desc:contains('description')::text").get())


EXPECTED = {
    "name": " Foo ",
    "images": ["a.png", "b.png"],
    "brand": "Acme",
    "sources": ["a.png", "b.png"],
    "missing": None,
    "price": "10.00",
    "sku": None,
    "description": "A description",
}


def test_extractable_declarations() -> None:
    page = _get_page(Page)
    assert page is not None
    assert page[1] == {"name", "images", "brand", "sources", "missing"}


def test_values(response) -> None:
    assert asyncio.run(Page(response=response).to_item()) == EXPECTED


def test_parsel_agreement(response, parsel_only) -> None:
    """Every declaration has the same value with either backend."""
    assert asyncio.run(Page(response=response).to_item()) == EXPECTED


def test_fallback_is_lazy(response) -> None:
    """A declaration that frostwork cannot extract does not trigger a scan."""
    page = Page(response=response)
    assert page.sku is None
    assert set(page._selector_value_cache()) == {"sku"}


def test_browser_page() -> None:
    """A browser response provides no bytes to scan, but its HTML can be
    scanned as it is."""

    @attrs.define
    class BrowserPageSubclass(BrowserPage):
        name = field(css("h1::text").get())

    response = BrowserResponse(url="http://example.com", html=HTML)
    assert asyncio.run(BrowserPageSubclass(response=response).to_item()) == {
        "name": " Foo "
    }


def test_selector_extractor() -> None:
    """An extractor built on a selector provides no document to scan, so parsel
    extracts its declarations."""

    @attrs.define
    class Extractor(SelectorExtractor):
        name = field(css("h1::text").get())

    extractor = Extractor(parsel.Selector(HTML))
    assert asyncio.run(extractor.to_item()) == {"name": " Foo "}
    assert _get_page(Extractor) is not None
