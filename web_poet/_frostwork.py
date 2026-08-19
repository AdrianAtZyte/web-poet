from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from frostwork import Page, check
except ImportError:
    Page = None  # type: ignore[assignment,misc]

from web_poet._selectors import _class_cached, _get_selectors_dict

if TYPE_CHECKING:
    from web_poet._selectors import _SelectorDeclaration

_PAGE_ATTRIBUTE = "_web_poet_frostwork_page"

# Selector declaration modes, mapped to the frostwork page method with the same
# cardinality. A declaration whose mode is missing here is left to parsel:
# frostwork extracts values, so it cannot build a selector list.
_METHODS = {"get": "field", "getall": "field_all"}

# frostwork supports neither JMESPath nor every CSS and XPath expression; the
# expressions that it does not support are reported by check().
_SYNTAXES = {"css", "xpath"}


def _build_page(cls: type) -> tuple[Page, dict[_SelectorDeclaration, str]] | None:
    """Return a frostwork page for the declarations of *cls* that frostwork can
    extract, mapped to the name that they have on it, or ``None`` if there are
    none.

    Declarations that are equal are extracted once, under the first attribute
    name that uses one."""
    if Page is None:
        return None
    candidates: dict[_SelectorDeclaration, str] = {}
    for name, declaration in _get_selectors_dict(cls).items():
        if (
            declaration.mode in _METHODS
            and declaration.syntax in _SYNTAXES
            and declaration not in candidates
        ):
            candidates[declaration] = name
    if not candidates:
        return None
    report = check(
        [(name, declaration.expression) for declaration, name in candidates.items()]
    )
    if report.over_budget:
        # The budget covers a whole schema at once, and leaving out enough
        # declarations to fit could leave out any of them, so parsel extracts
        # them all instead.
        return None
    supported = frozenset(field.name for field in report.fields if field.supported)
    names = {
        declaration: name
        for declaration, name in candidates.items()
        if name in supported
    }
    if not names:
        return None
    page = Page()
    for declaration, name in names.items():
        getattr(page, _METHODS[declaration.mode])(name, declaration.expression)
    return page, names


def _get_page(cls: type) -> tuple[Page, dict[_SelectorDeclaration, str]] | None:
    """Return the frostwork page of *cls*, building it on the first call."""
    return _class_cached(cls, _PAGE_ATTRIBUTE, _build_page)


def _extract(
    cls: type,
    declaration: _SelectorDeclaration,
    document: tuple[bytes | str, str | None],
) -> dict[_SelectorDeclaration, Any]:
    """Return the value of every declaration of *cls* that frostwork can
    extract out of *document*, provided that *declaration* is among them.

    Return an empty mapping otherwise, including when frostwork is not
    installed."""
    result = _get_page(cls)
    if result is None:
        return {}
    page, names = result
    if declaration not in names:
        return {}
    html, encoding = document
    values = page.extract(html, encoding).to_dict()
    return {
        declaration: values[name]
        for declaration, name in names.items()
        if name in values
    }
