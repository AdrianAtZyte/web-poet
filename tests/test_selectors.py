from __future__ import annotations

import asyncio

import attrs
import parsel
import pytest

from web_poet import (
    BrowserPage,
    BrowserResponse,
    HttpClient,
    HttpResponse,
    ItemPage,
    Returns,
    SelectorExtractor,
    WebPage,
    field,
    selector,
)
from web_poet._selectors import _get_selectors_dict
from web_poet.testing import Fixture

HTML = """
<html>
  <head><meta itemprop="brand" content="Acme"></head>
  <body>
    <h1> Foo </h1>
    <p class="price">10.00</p>
    <img src="a.png"><img src="b.png">
    <div class="sku">SKU-1</div>
    <div class="desc">A description</div>
  </body>
</html>
"""


@pytest.fixture
def response():
    return HttpResponse("http://example.com", HTML.encode("utf-8"), encoding="utf-8")


@attrs.define
class Page(WebPage):
    name = field("h1::text")
    images = field(selector("img::attr(src)", all=True))
    brand = field("//meta[@itemprop='brand']/@content")
    missing = field(".missing::text")
    missing_all = field(selector(".missing::text", all=True))

    _sku_a = selector(".sku::text")
    _sku_b = selector("//meta[@name='sku']/@content")

    @field
    def sku(self) -> str | None:
        return self._sku_a or self._sku_b

    @field
    def description(self) -> str | None:
        return self.css(".desc::text").get()


def test_values(response) -> None:
    page = Page(response=response)
    assert page.name == " Foo "
    assert page.images == ["a.png", "b.png"]
    assert page.brand == "Acme"
    assert page.missing is None
    assert page.missing_all == []
    assert page.sku == "SKU-1"
    assert page.description == "A description"


def test_to_item(response) -> None:
    assert asyncio.run(Page(response=response).to_item()) == {
        "name": " Foo ",
        "images": ["a.png", "b.png"],
        "brand": "Acme",
        "missing": None,
        "missing_all": [],
        "sku": "SKU-1",
        "description": "A description",
    }


def test_declaration_not_a_field(response) -> None:
    """A bare selector() attribute is readable, but is not an item field."""
    assert "_sku_a" not in asyncio.run(Page(response=response).to_item())


def test_get_selectors_dict_before_instantiation() -> None:
    declarations = _get_selectors_dict(Page)
    assert set(declarations) == {
        "name",
        "images",
        "brand",
        "missing",
        "missing_all",
        "_sku_a",
        "_sku_b",
    }
    assert declarations["name"].expression == "h1::text"
    assert declarations["name"].name == "name"
    assert declarations["images"].all is True
    assert declarations["name"].all is False


def test_get_selectors_dict_instance(response) -> None:
    assert _get_selectors_dict(Page(response=response)) == _get_selectors_dict(Page)


def test_class_access() -> None:
    """Accessing a declaration on the class returns the declaration."""
    assert _get_selectors_dict(Page)["_sku_a"] is Page._sku_a


@pytest.mark.parametrize(
    ("expression", "syntax"),
    [
        ("h1::text", "css"),
        ("  h1::text  ", "css"),
        ("//h1/text()", "xpath"),
        ("/html/body/h1/text()", "xpath"),
        ("  //h1/text()", "xpath"),
        ("./h1/text()", "xpath"),
        ("../h1/text()", "xpath"),
        ("(//h1)[1]/text()", "xpath"),
        ("*/h1/text()", "xpath"),
    ],
)
def test_sniffing(expression, syntax) -> None:
    assert selector(expression).syntax == syntax


def test_syntax_override(response) -> None:
    @attrs.define
    class SyntaxPage(WebPage):
        # Sniffed as CSS, forced to XPath.
        name = field(selector("descendant::h1/text()", syntax="xpath"))

    assert _get_selectors_dict(SyntaxPage)["name"].syntax == "xpath"
    assert SyntaxPage(response=response).name == " Foo "
    # The opposite direction, which sniffing cannot get wrong on its own.
    assert selector("//h1", syntax="css").syntax == "css"


@pytest.mark.skipif(
    not hasattr(parsel.Selector, "jmespath"),
    reason="parsel < 1.8 doesn't support jmespath",
)
def test_jmespath() -> None:
    @attrs.define
    class JsonPage(WebPage):
        name = field(selector("website.name", syntax="jmespath"))
        price = field(selector("price", syntax="jmespath"))
        tags = field(selector("tags", syntax="jmespath", all=True))
        missing = field(selector("missing", syntax="jmespath"))

    response = HttpResponse(
        "http://example.com",
        b'{"website": {"name": "homepage"}, "price": 10, "tags": ["a", "b"]}',
        encoding="utf-8",
    )
    assert asyncio.run(JsonPage(response=response).to_item()) == {
        "name": "homepage",
        "price": 10,
        "tags": ["a", "b"],
        "missing": None,
    }


def test_field_not_callable() -> None:
    with pytest.raises(TypeError, match="must be used on methods"):
        field(1)  # type: ignore[call-overload]


def test_out(response) -> None:
    @attrs.define
    class OutPage(WebPage):
        name = field("h1::text", out=[str.strip])
        images = field(selector("img::attr(src)", all=True), out=[len])

    page = OutPage(response=response)
    assert page.name == "Foo"
    assert page.images == 2


def test_processors(response) -> None:
    @attrs.define
    class ProcessorsPage(WebPage):
        name = field("h1::text")

        class Processors:
            name = [str.strip]

    assert ProcessorsPage(response=response).name == "Foo"


def test_meta() -> None:
    from web_poet.fields import get_fields_dict  # noqa: PLC0415

    @attrs.define
    class MetaPage(WebPage):
        name = field("h1::text", meta={"expensive": False})

    assert get_fields_dict(MetaPage)["name"].meta == {"expensive": False}


def test_extra_dependency(response) -> None:
    """Attrs recreates the class, dropping the temporary markers that
    ``__init_subclass__`` relies on. Declarations must survive that, including
    when the subclass adds a dependency.

    See https://github.com/scrapinghub/web-poet/issues/141
    """

    @attrs.define
    class SubPage(Page):
        http: HttpClient

    page = SubPage(response=response, http=HttpClient())
    assert set(_get_selectors_dict(SubPage)) == set(_get_selectors_dict(Page))
    assert page.name == " Foo "


class TestInheritance:
    def test_add(self, response) -> None:
        @attrs.define
        class SubPage(Page, Returns[dict]):
            price = field(".price::text")

        assert _get_selectors_dict(SubPage)["price"].expression == ".price::text"
        assert SubPage(response=response).price == "10.00"
        assert SubPage(response=response).name == " Foo "

    def test_override(self, response) -> None:
        @attrs.define
        class SubPage(Page):
            name = field(".price::text")

        assert SubPage(response=response).name == "10.00"
        assert Page(response=response).name == " Foo "

    def test_shadow_with_a_method(self, response) -> None:
        @attrs.define
        class SubPage(Page):
            @field
            def name(self) -> str:
                return "hardcoded"

        assert "name" not in _get_selectors_dict(SubPage)
        assert "name" in _get_selectors_dict(Page)
        assert SubPage(response=response).name == "hardcoded"

    def test_remove(self, response) -> None:
        @attrs.define
        class SubPage(Page):
            _sku_a = None

            @field
            def sku(self) -> str | None:
                return self._sku_b

        assert "_sku_a" not in _get_selectors_dict(SubPage)
        assert SubPage(response=response).sku is None


def test_selector_extractor() -> None:
    @attrs.define
    class Extractor(SelectorExtractor):
        name = field("h1::text", out=[str.strip])

    sel = parsel.Selector(HTML)
    assert asyncio.run(Extractor(sel).to_item()) == {"name": "Foo"}


def test_browser_page() -> None:
    @attrs.define
    class Page(BrowserPage):
        name = field("h1::text", out=[str.strip])

    response = BrowserResponse(url="http://example.com", html=HTML)
    assert asyncio.run(Page(response=response).to_item()) == {"name": "Foo"}


def test_single_extraction_pass(response) -> None:
    calls = []

    @attrs.define
    class CountingPage(Page):
        def _extract_selectors(self, declarations):
            calls.append(declarations)
            return super()._extract_selectors(declarations)

    page = CountingPage(response=response)
    asyncio.run(page.to_item())
    assert len(calls) == 1
    assert set(calls[0]) == set(_get_selectors_dict(CountingPage))
    # Repeated access does not extract again.
    assert page.name == " Foo "
    assert len(calls) == 1


def test_no_selector() -> None:
    @attrs.define
    class NoSelectorPage(ItemPage):
        name = field("h1::text")

    with pytest.raises(TypeError, match="provides no parsel selector"):
        NoSelectorPage().name


def test_fixture(response, tmp_path) -> None:
    base_dir = tmp_path / "fixtures" / "tests.test_selectors.Page"
    item = asyncio.run(Page(response=response).to_item())
    Fixture.save(base_dir, inputs=[response], item=item)
    fixture = Fixture(base_dir / "test-1")
    fixture.assert_full_item_correct(Page)
    fixture.assert_field_correct("name", Page)
    fixture.assert_no_extra_fields(Page)
    fixture.assert_no_toitem_exceptions(Page)
