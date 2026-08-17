from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar, overload

from lxml.etree import XPath  # type: ignore[import-untyped]
from parsel.csstranslator import HTMLTranslator

if TYPE_CHECKING:
    import parsel

try:
    from jmespath import compile as _compile_jmespath  # type: ignore[import-untyped]
except ImportError:
    # parsel only requires jmespath since 1.8, the version that added JMESPath
    # support.
    _compile_jmespath = None  # type: ignore[assignment]

_SELECTORS_DICT_ATTRIBUTE = "_web_poet_selectors_dict"

_ValueT = TypeVar("_ValueT")

_SelectorSyntax = Literal["css", "xpath", "jmespath"]

# How the value of a selector declaration is built out of its matches: the
# parsel selector list, the value of its first match, or the values of all its
# matches.
_SelectorMode = Literal["selector", "get", "getall"]

# HTML is the CSS dialect with the largest set of valid expressions, so it is
# also the one that never rejects an expression that some parsel selector could
# have translated.
_css_translator = HTMLTranslator()


def _validate(expression: str, syntax: _SelectorSyntax) -> None:
    """Raise the underlying syntax error of *syntax* if *expression* cannot be
    parsed."""
    if syntax == "css":
        _css_translator.css_to_xpath(expression)
    elif syntax == "xpath":
        XPath(expression)
    elif _compile_jmespath is not None:
        _compile_jmespath(expression)


class _SelectorDeclaration(Generic[_ValueT]):
    def __init__(
        self,
        expression: str,
        syntax: _SelectorSyntax,
        mode: _SelectorMode,
    ):
        _validate(expression, syntax)
        self.expression = expression
        self.syntax = syntax
        self.mode = mode

    def __repr__(self) -> str:
        suffix = "" if self.mode == "selector" else f"_{self.mode}"
        return f"{self.syntax}{suffix}({self.expression!r})"

    @overload
    def __get__(
        self, instance: None, owner: type | None = None
    ) -> _SelectorDeclaration[_ValueT]: ...

    @overload
    def __get__(self, instance: object, owner: type | None = None) -> _ValueT: ...

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return _declaration_value(instance, self)


def css(expression: str) -> _SelectorDeclaration[parsel.SelectorList[parsel.Selector]]:
    """Return a declaration of the CSS *expression*, to be used as a class
    attribute of a page object class, either on its own or through
    :func:`~web_poet.field`.

    Its value is a :class:`~parsel.selector.SelectorList`. See
    :func:`~web_poet.css_get` and :func:`~web_poet.css_getall` to get extracted
    values instead.

    See :ref:`declarative-selectors`.
    """
    return _SelectorDeclaration(expression, "css", "selector")


def css_get(expression: str) -> _SelectorDeclaration[str | None]:
    """Return a declaration of the CSS *expression* whose value is that of its
    first match, or ``None``.

    See :func:`~web_poet.css`.
    """
    return _SelectorDeclaration(expression, "css", "get")


def css_getall(expression: str) -> _SelectorDeclaration[list[str]]:
    """Return a declaration of the CSS *expression* whose value is the list of
    the values of all its matches.

    See :func:`~web_poet.css`.
    """
    return _SelectorDeclaration(expression, "css", "getall")


def xpath(
    expression: str,
) -> _SelectorDeclaration[parsel.SelectorList[parsel.Selector]]:
    """Return a declaration of the XPath *expression*.

    See :func:`~web_poet.css`.
    """
    return _SelectorDeclaration(expression, "xpath", "selector")


def xpath_get(expression: str) -> _SelectorDeclaration[str | None]:
    """Return a declaration of the XPath *expression* whose value is that of
    its first match, or ``None``.

    See :func:`~web_poet.css`.
    """
    return _SelectorDeclaration(expression, "xpath", "get")


def xpath_getall(expression: str) -> _SelectorDeclaration[list[str]]:
    """Return a declaration of the XPath *expression* whose value is the list
    of the values of all its matches.

    See :func:`~web_poet.css`.
    """
    return _SelectorDeclaration(expression, "xpath", "getall")


def jmespath(
    expression: str,
) -> _SelectorDeclaration[parsel.SelectorList[parsel.Selector]]:
    """Return a declaration of the JMESPath *expression*.

    See :func:`~web_poet.css`.
    """
    return _SelectorDeclaration(expression, "jmespath", "selector")


def jmespath_get(expression: str) -> _SelectorDeclaration[Any]:
    """Return a declaration of the JMESPath *expression* whose value is the
    JSON value of its first match, or ``None``.

    See :func:`~web_poet.css`.
    """
    return _SelectorDeclaration(expression, "jmespath", "get")


def jmespath_getall(expression: str) -> _SelectorDeclaration[list[Any]]:
    """Return a declaration of the JMESPath *expression* whose value is the
    list of the JSON values of all its matches.

    See :func:`~web_poet.css`.
    """
    return _SelectorDeclaration(expression, "jmespath", "getall")


def _declaration_value(instance: Any, declaration: _SelectorDeclaration) -> Any:
    """Return the value of *declaration* for *instance*, raising ``TypeError``
    if *instance* has no selector to extract it from."""
    try:
        get_value = instance._selector_value
    except AttributeError:
        raise TypeError(
            f"{type(instance).__name__} does not support selector declarations, "
            f"it provides no parsel selector. Inherit from a class that does, "
            f"e.g. web_poet.WebPage or web_poet.SelectorExtractor."
        ) from None
    return get_value(_declaration_name(instance, declaration))


def _declaration_name(instance: Any, declaration: _SelectorDeclaration) -> str:
    """Return the attribute name that *declaration* has on *instance*.

    A declaration object can be shared by any number of attributes and classes,
    so its name depends on where it is looked up."""
    for name, candidate in _get_selectors_dict(instance).items():
        if candidate is declaration:
            return name
    raise ValueError(
        f"{declaration!r} is not among the selector declarations of "
        f"{type(instance).__name__}. Selector declarations must be set as class "
        f"attributes in the class definition."
    )


def _get_declaration(value: Any) -> _SelectorDeclaration | None:
    if isinstance(value, _SelectorDeclaration):
        return value
    return getattr(value, "selector_declaration", None)


def _get_selectors_dict(cls_or_instance) -> dict[str, _SelectorDeclaration]:
    """Return a dictionary with the selector declarations of a class or
    instance: keys are attribute names, and values are declaration objects."""
    cls = (
        cls_or_instance if isinstance(cls_or_instance, type) else type(cls_or_instance)
    )
    # The result is derived from the descriptors themselves, and cached on the
    # class where it is derived, rather than filled in on class creation. That
    # way it survives attrs recreating the class (see issue #141).
    cached = cls.__dict__.get(_SELECTORS_DICT_ATTRIBUTE)
    if cached is not None:
        return cached
    result: dict[str, _SelectorDeclaration] = {}
    for klass in reversed(cls.__mro__):
        for name, value in vars(klass).items():
            declaration = _get_declaration(value)
            if declaration is None:
                # A subclass shadowing a declaration with something else, e.g.
                # a regular @field method, drops it from the schema.
                result.pop(name, None)
            else:
                result[name] = declaration
    setattr(cls, _SELECTORS_DICT_ATTRIBUTE, result)
    return result
