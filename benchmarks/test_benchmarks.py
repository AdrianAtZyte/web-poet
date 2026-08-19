from __future__ import annotations

from typing import TYPE_CHECKING, Any

import attrs
import pytest

from benchmarks.pages import (
    ArticlePage,
    DeclarativeArticlePage,
    DeclarativeProductPage,
    JmesPathArticlePage,
    JobPostingPage,
    JsonLdArticlePage,
    MinimalPage,
    ProductDetailsPage,
    ProductPage,
)
from web_poet import ItemPage

if TYPE_CHECKING:
    import asyncio

    from benchmarks.conftest import PageBuilder

#: Page object class and fixture name of every benchmark, keyed by benchmark
#: name. Results are tracked by name over time, so a name is meant to outlive
#: changes to the page object it measures.
BENCHMARKS: dict[str, tuple[type[ItemPage], str]] = {
    "product_imperative": (ProductPage, "product"),
    "product_declarative": (DeclarativeProductPage, "product"),
    "product_details_nodes": (ProductDetailsPage, "product"),
    "article_imperative": (ArticlePage, "article"),
    "article_declarative": (DeclarativeArticlePage, "article"),
    "article_jsonld": (JsonLdArticlePage, "article"),
    "article_jmespath": (JmesPathArticlePage, "article"),
    "job_imperative": (JobPostingPage, "job"),
    "minimal": (MinimalPage, "minimal"),
}


def _extract(loop: asyncio.AbstractEventLoop, page: PageBuilder, name: str) -> Any:
    page_cls, fixture = BENCHMARKS[name]
    return loop.run_until_complete(page(page_cls, fixture).to_item())


@pytest.mark.parametrize("name", list(BENCHMARKS))
def test_extraction(benchmark, loop, page, name: str) -> None:
    benchmark(_extract, loop, page, name)


#: Every declarative benchmark, paired with the imperative one it mirrors.
TWINS = [
    (name, name.replace("_declarative", "_imperative"))
    for name in BENCHMARKS
    if name.endswith("_declarative")
]


@pytest.mark.parametrize(("declarative", "imperative"), TWINS)
def test_twins_agree(loop, page, declarative: str, imperative: str) -> None:
    """A declarative page object extracts what the imperative one that it
    mirrors extracts, so that their benchmarks compare like with like."""
    assert _extract(loop, page, declarative) == _extract(loop, page, imperative)


@pytest.mark.parametrize("name", list(BENCHMARKS))
def test_every_field_is_extracted(loop, page, name: str) -> None:
    """Guard the benchmarks against measuring extraction that no longer
    extracts anything."""
    item = _extract(loop, page, name)
    empty = [
        field.name
        for field in attrs.fields(type(item))
        if not getattr(item, field.name)
    ]
    assert not empty
