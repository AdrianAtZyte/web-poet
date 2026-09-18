from __future__ import annotations

from pathlib import Path

import pytest

from web_poet.page_inputs import HttpResponse, HttpResponseBody
from web_poet.rules import RulesRegistry
from web_poet.serialization import register_encoding_backend
from web_poet.serialization.api import _ENCODING_BACKENDS

pytest_plugins = ["pytester"]


@pytest.fixture(name="pytester")
def _pytester(pytester):
    # Nested pytest runs start in an empty directory, so they need their own
    # configuration.
    pytester.makeini("[pytest]\nasyncio_default_fixture_loop_scope = function\n")
    return pytester


def read_fixture(path: str) -> str:
    return (Path(__file__).parent / path).read_text(encoding="utf-8")


@pytest.fixture
def book_list_html():
    return read_fixture("fixtures/book_list.html")


@pytest.fixture
def some_json_response():
    body = """
    {
      "description": "paragraph",
      "website": {
        "url": "http://www.scrapy.org",
        "name": "homepage"
      },
      "logo": "/images/logo.png"
    }
    """
    return HttpResponse(
        url="http://books.toscrape.com/result.json",
        body=body.encode("utf-8"),
        encoding="utf-8",
    )


@pytest.fixture
def book_list_html_response(book_list_html):
    body = HttpResponseBody(bytes(book_list_html, "utf-8"))
    return HttpResponse(
        url="http://books.toscrape.com/index.html", body=body, encoding="utf-8"
    )


@pytest.fixture
def registry():
    return RulesRegistry()


class _Latin1Decision:
    name = "latin-1"
    ascii_compatible = True

    def decode(self, body: bytes) -> str:
        return body.decode("latin-1")


class Latin1EncodingBackend:
    """Encoding backend that decodes every document as latin-1."""

    policy_id = "test-latin1"

    def resolve(
        self, body: bytes, content_type: str = "", encoding: str | None = None
    ) -> _Latin1Decision:
        return _Latin1Decision()


@pytest.fixture
def encoding_backend():
    return Latin1EncodingBackend()


@pytest.fixture
def registered_encoding_backend(encoding_backend):
    register_encoding_backend(encoding_backend)
    yield encoding_backend
    del _ENCODING_BACKENDS[encoding_backend.policy_id]
