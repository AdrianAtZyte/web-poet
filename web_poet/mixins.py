from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar
from urllib.parse import urljoin

import parsel
from w3lib.html import get_base_url

from web_poet._frostwork import _extract as _frostwork_extract
from web_poet.utils import cached_method

if TYPE_CHECKING:
    from collections.abc import Collection

    from web_poet._selectors import _SelectorDeclaration
    from web_poet.page_inputs.url import RequestUrl, ResponseUrl


class _ResponseLike(Protocol):
    """Protocol for response objects."""

    url: ResponseUrl | str
    text: str


ResponseT = TypeVar("ResponseT", bound=_ResponseLike)


class SelectorShortcutsMixin:
    def xpath(self, query, **kwargs) -> parsel.SelectorList:
        """A shortcut to ``.selector.xpath()``."""
        return self.selector.xpath(query, **kwargs)  # type: ignore[attr-defined]

    def css(self, query) -> parsel.SelectorList:
        """A shortcut to ``.selector.css()``."""
        return self.selector.css(query)  # type: ignore[attr-defined]

    def jmespath(self, query: str, **kwargs) -> parsel.SelectorList:
        """A shortcut to ``.selector.jmespath()``."""
        if not hasattr(self.selector, "jmespath"):  # type: ignore[attr-defined]
            raise AttributeError(
                "Please install parsel >= 1.8.1 to get jmespath support"
            )
        return self.selector.jmespath(query, **kwargs)  # type: ignore[attr-defined]

    def _selector_document(self) -> tuple[bytes | str, str | None] | None:
        """Return the raw document of this object and its encoding, for
        extraction backends that scan it directly instead of using
        ``self.selector``, or ``None`` if there is no such document."""
        return None

    @cached_method
    def _selector_value_cache(self) -> dict[_SelectorDeclaration, Any]:
        return {}

    def _selector_value(self, declaration: _SelectorDeclaration) -> Any:
        """Return the value of *declaration* for this object, extracting it on
        the first call."""
        values = self._selector_value_cache()
        if declaration not in values:
            values.update(self._extract_selectors([declaration]))
        return values[declaration]

    def _extract_selectors(
        self, declarations: Collection[_SelectorDeclaration]
    ) -> dict[_SelectorDeclaration, Any]:
        """Return a value for every declaration in *declarations*.

        frostwork extracts every declaration of the object that it supports in
        a single pass, and parsel extracts the rest, one query per declaration.
        Values for declarations beyond those requested may be included in the
        returned mapping; they are cached and reused, so that a single pass
        happens only once."""
        values = _frostwork_extract(self, declarations)
        for declaration in declarations:
            if declaration in values:
                continue
            # Going through the mixin, and not through self, keeps a field
            # named css, xpath or jmespath from shadowing the query method.
            query = getattr(SelectorShortcutsMixin, declaration.syntax)
            selector_list = query(self, declaration.expression)
            # Modes other than selector are named after the parsel selector
            # list method that implements them.
            values[declaration] = (
                selector_list
                if declaration.mode == "selector"
                else getattr(selector_list, declaration.mode)()
            )
        return values


class SelectableMixin(abc.ABC, SelectorShortcutsMixin):
    """
    Inherit from this mixin, implement ``._selector_input`` method,
    get ``.selector`` property and ``.xpath`` / ``.css`` / ``.jmespath``
    methods.
    """

    __cached_selector = None

    @abc.abstractmethod
    def _selector_input(self) -> str:
        raise NotImplementedError  # pragma: nocover

    @property
    def selector(self) -> parsel.Selector:
        """Cached instance of :external:class:`parsel.selector.Selector`."""
        # caching is implemented in a manual way to avoid issues with
        # non-hashable classes, where memoizemethod_noargs doesn't work
        if self.__cached_selector is not None:
            return self.__cached_selector
        base_url = str(self.url) if hasattr(self, "url") else None
        sel = parsel.Selector(text=self._selector_input(), base_url=base_url)
        self.__cached_selector = sel
        return sel


class UrlShortcutsMixin:
    _cached_base_url = None

    def _url_shortcuts_input(self) -> str:
        return self._selector_input()  # type: ignore[attr-defined]

    @property
    def _base_url(self) -> str:
        if self._cached_base_url is None:
            text = self._url_shortcuts_input()[:4096]
            self._cached_base_url = get_base_url(text, str(self.url))  # type: ignore[attr-defined]
        return self._cached_base_url

    def urljoin(self, url: str | RequestUrl | ResponseUrl) -> RequestUrl:
        """Return *url* as an absolute URL.

        If *url* is relative, it is made absolute relative to the base URL of
        *self*."""
        from web_poet.page_inputs.url import RequestUrl  # noqa: PLC0415

        return RequestUrl(urljoin(self._base_url, str(url)))


class ResponseShortcutsMixin(Generic[ResponseT], SelectableMixin, UrlShortcutsMixin):  # noqa: PYI059
    """Common shortcut methods for working with HTML responses.
    This mixin could be used with Page Object base classes.

    It requires "response" attribute to be present.
    """

    response: ResponseT

    _cached_base_url = None

    @property
    def url(self) -> str:
        """Shortcut to HTML Response's URL, as a string."""
        return str(self.response.url)

    @property
    def html(self) -> str:
        """Shortcut to HTML Response's content."""
        return self.response.text

    def _selector_input(self) -> str:
        return self.html

    def _selector_document(self) -> tuple[bytes | str, str | None]:
        response: Any = self.response
        try:
            body = response.body
        except AttributeError:
            # A browser response is HTML that has already been decoded.
            return self.html, None
        return body, response.encoding

    @property
    def base_url(self) -> str:
        """Return the base url of the given response"""
        return self._base_url

    def urljoin(self, url: str) -> str:  # type: ignore[override]
        """Convert url to absolute, taking in account
        url and baseurl of the response"""
        return str(super().urljoin(url))
