from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from frostwork import Page, check
except ImportError:
    Page = None  # type: ignore[assignment,misc]

from web_poet._selectors import _get_selectors_dict

if TYPE_CHECKING:
    from collections.abc import Collection

    from web_poet._selectors import _SelectorDeclaration

_PAGE_ATTRIBUTE = "_web_poet_frostwork_page"

# Selector declaration modes, mapped to the frostwork page method with the same
# cardinality. A declaration whose mode is missing here is left to parsel:
# frostwork extracts values, so it cannot build a selector list.
_METHODS = {"get": "field", "getall": "field_all"}

# frostwork supports neither JMESPath nor every CSS and XPath expression; the
# expressions that it does not support are reported by check().
_SYNTAXES = {"css", "xpath"}


def _build_page(
    declarations: dict[str, _SelectorDeclaration],
) -> tuple[Page, dict[_SelectorDeclaration, str]] | None:
    """Return a frostwork page for the declarations that frostwork can extract,
    mapped to the name that they have on it, or ``None`` if there are none.

    A declaration used by more than one attribute is extracted once, under the
    first of those attribute names."""
    if Page is None:
        return None
    candidates: dict[_SelectorDeclaration, str] = {}
    for name, declaration in declarations.items():
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
    """Return the frostwork page of *cls*, building it on the first call.

    Like the selector declarations that it is built from, it is derived and
    cached on the class where it is derived, so that it survives attrs
    recreating the class."""
    try:
        return cls.__dict__[_PAGE_ATTRIBUTE]
    except KeyError:
        result = _build_page(_get_selectors_dict(cls))
        setattr(cls, _PAGE_ATTRIBUTE, result)
        return result


def _extract(
    instance: Any, declarations: Collection[_SelectorDeclaration]
) -> dict[_SelectorDeclaration, Any]:
    """Return the value of every declaration of *instance* that frostwork can
    extract, provided that at least one of *declarations* is among them.

    Return an empty mapping otherwise, including when frostwork is not
    installed or *instance* provides no raw document to scan."""
    result = _get_page(type(instance))
    if result is None:
        return {}
    page, names = result
    if names.keys().isdisjoint(declarations):
        return {}
    document = instance._selector_document()
    if document is None:
        return {}
    html, encoding = document
    values = page.extract(html, encoding).to_dict()
    return {
        declaration: values[name]
        for declaration, name in names.items()
        if name in values
    }
