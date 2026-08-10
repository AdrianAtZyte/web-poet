from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar, overload

_SELECTORS_DICT_ATTRIBUTE = "_web_poet_selectors_dict"

_ValueT = TypeVar("_ValueT")

_SelectorSyntax = Literal["css", "xpath", "jmespath"]


class _SelectorDeclaration(Generic[_ValueT]):
    def __init__(
        self,
        expression: str,
        syntax: _SelectorSyntax,
        *,
        all: bool = False,
    ):
        self.expression = expression
        self.syntax = syntax
        self.all = all

    def __repr__(self) -> str:
        return f"{self.syntax}({self.expression!r}, all={self.all!r})"

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


@overload
def css(
    expression: str, *, all: Literal[False] = False
) -> _SelectorDeclaration[str | None]: ...


@overload
def css(expression: str, *, all: Literal[True]) -> _SelectorDeclaration[list[str]]: ...


@overload
def css(expression: str, *, all: bool) -> _SelectorDeclaration[Any]: ...


def css(expression: str, *, all: bool = False) -> _SelectorDeclaration[Any]:
    """Return a declaration of the CSS *expression*, to be used as a class
    attribute of a page object class, either on its own or through
    :func:`~web_poet.field`.

    Set *all* to ``True`` to get the values of all matches instead of the value
    of the first match.

    See :ref:`declarative-selectors`.
    """
    return _SelectorDeclaration(expression, "css", all=all)


@overload
def xpath(
    expression: str, *, all: Literal[False] = False
) -> _SelectorDeclaration[str | None]: ...


@overload
def xpath(
    expression: str, *, all: Literal[True]
) -> _SelectorDeclaration[list[str]]: ...


@overload
def xpath(expression: str, *, all: bool) -> _SelectorDeclaration[Any]: ...


def xpath(expression: str, *, all: bool = False) -> _SelectorDeclaration[Any]:
    """Return a declaration of the XPath *expression*.

    See :func:`~web_poet.css`.
    """
    return _SelectorDeclaration(expression, "xpath", all=all)


@overload
def jmespath(
    expression: str, *, all: Literal[False] = False
) -> _SelectorDeclaration[Any]: ...


@overload
def jmespath(
    expression: str, *, all: Literal[True]
) -> _SelectorDeclaration[list[Any]]: ...


@overload
def jmespath(expression: str, *, all: bool) -> _SelectorDeclaration[Any]: ...


def jmespath(expression: str, *, all: bool = False) -> _SelectorDeclaration[Any]:
    """Return a declaration of the JMESPath *expression*.

    See :func:`~web_poet.css`.
    """
    return _SelectorDeclaration(expression, "jmespath", all=all)


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
