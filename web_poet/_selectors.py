from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar, overload

_SELECTORS_DICT_ATTRIBUTE = "_web_poet_selectors_dict"

_ValueT = TypeVar("_ValueT")

_SelectorSyntax = Literal["css", "xpath", "jmespath"]

# Stripped expression prefixes that make an expression be sniffed as XPath.
_XPATH_PREFIXES = ("/", "./", "..", "(", "*/")


class _SelectorDeclaration(Generic[_ValueT]):
    def __init__(
        self,
        expression: str,
        *,
        all: bool = False,
        syntax: _SelectorSyntax | None = None,
    ):
        self.expression = expression
        self.all = all
        self.syntax: _SelectorSyntax = syntax or (
            "xpath" if expression.strip().startswith(_XPATH_PREFIXES) else "css"
        )
        self.name: str | None = None

    def __repr__(self) -> str:
        return (
            f"selector({self.expression!r}, all={self.all!r}, syntax={self.syntax!r})"
        )

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    @overload
    def __get__(
        self, instance: None, owner: type | None = None
    ) -> _SelectorDeclaration[_ValueT]: ...

    @overload
    def __get__(self, instance: object, owner: type | None = None) -> _ValueT: ...

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return _selector_values(instance)[self.name]


@overload
def selector(
    expression: str,
    *,
    all: Literal[False] = False,
    syntax: Literal["css", "xpath"] | None = None,
) -> _SelectorDeclaration[str | None]: ...


@overload
def selector(
    expression: str,
    *,
    all: Literal[True],
    syntax: Literal["css", "xpath"] | None = None,
) -> _SelectorDeclaration[list[str]]: ...


@overload
def selector(
    expression: str,
    *,
    syntax: Literal["jmespath"],
    all: Literal[False] = False,
) -> _SelectorDeclaration[Any]: ...


@overload
def selector(
    expression: str,
    *,
    syntax: Literal["jmespath"],
    all: Literal[True],
) -> _SelectorDeclaration[list[Any]]: ...


def selector(
    expression: str,
    *,
    all: bool = False,
    syntax: _SelectorSyntax | None = None,
) -> _SelectorDeclaration[Any]:
    """Return a declaration of *expression*, to be used as a class attribute of
    a page object class, either on its own or through
    :func:`~web_poet.field`.

    See :ref:`declarative-selectors`.
    """
    return _SelectorDeclaration(expression, all=all, syntax=syntax)


def _selector_values(instance: Any) -> dict[str, Any]:
    """Return the values of all selector declarations of *instance*, raising
    ``TypeError`` if it has no selector to extract them from."""
    try:
        get_values = instance._selector_values
    except AttributeError:
        raise TypeError(
            f"{type(instance).__name__} does not support selector declarations, "
            f"it provides no parsel selector. Inherit from a class that does, "
            f"e.g. web_poet.WebPage or web_poet.SelectorExtractor."
        ) from None
    return get_values()


def _get_declaration(value: Any) -> _SelectorDeclaration | None:
    if isinstance(value, _SelectorDeclaration):
        return value
    return getattr(value, "selector_declaration", None)


def _get_selectors_dict(cls_or_instance) -> dict[str, _SelectorDeclaration]:
    """Return a dictionary with the :func:`~web_poet.selector` declarations of
    a class or instance: keys are attribute names, and values are declaration
    objects."""
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
