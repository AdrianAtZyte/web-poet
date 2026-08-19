from __future__ import annotations

import argparse
import asyncio
import re
import statistics
import textwrap
import timeit
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import frostwork

from benchmarks.documents import build_page, read_bodies
from benchmarks.pages import DeclarativeArticlePage, DeclarativeProductPage
from web_poet import mixins
from web_poet._frostwork import _get_page
from web_poet._selectors import _get_selectors_dict

if TYPE_CHECKING:
    from web_poet import ItemPage

DOCS = Path(__file__).parent.parent / "docs" / "page-objects" / "fields.rst"
START = ".. frostwork-benchmark-start"
END = ".. frostwork-benchmark-end"

# Documents to measure: the name of a benchmark document, the page object class
# to extract it with, and how the documentation refers to it.
DOCUMENTS = (
    ("article", DeclarativeArticlePage, "article page"),
    ("product", DeclarativeProductPage, "product page"),
)


@contextmanager
def _parsel_only():
    original = mixins._frostwork_extract
    mixins._frostwork_extract = lambda instance, declarations: {}
    try:
        yield
    finally:
        mixins._frostwork_extract = original


def _item(page_cls: type[ItemPage], name: str, bodies: dict[str, bytes], loop) -> Any:
    # A new page object over a new response on every call, as a spider builds
    # one per downloaded page, so that parsing the document is measured, the way
    # the cold benchmarks of test_benchmarks.py measure it.
    page = build_page(page_cls, name, bodies)
    return loop.run_until_complete(page.to_item())


def _seconds(page_cls: type[ItemPage], name: str, bodies, loop) -> float:
    timer = timeit.Timer(lambda: _item(page_cls, name, bodies, loop))
    number, _ = timer.autorange()
    return min(timer.repeat(repeat=5, number=number)) / number


def _speedup(page_cls: type[ItemPage], name: str, bodies, loop) -> float:
    """Return how many times faster than parsel frostwork extracts *name*.

    Each backend is measured once per round, so that a machine that speeds up or
    slows down during the run moves both of them, and the median round is the
    result."""
    ratios = []
    for _ in range(5):
        with _parsel_only():
            parsel_seconds = _seconds(page_cls, name, bodies, loop)
        ratios.append(parsel_seconds / _seconds(page_cls, name, bodies, loop))
    return statistics.median(ratios)


def _check(page_cls: type[ItemPage], name: str, bodies, loop) -> None:
    """Raise ``ValueError`` unless frostwork extracts every declaration of
    *page_cls*, with the values that parsel extracts."""
    result = _get_page(page_cls)
    declarations = _get_selectors_dict(page_cls)
    if result is None or len(result[1]) != len(declarations):
        raise ValueError(f"frostwork does not extract every declaration of {page_cls}")
    item = _item(page_cls, name, bodies, loop)
    with _parsel_only():
        if _item(page_cls, name, bodies, loop) != item:
            raise ValueError(f"frostwork and parsel disagree on {page_cls}")


def _size(body: bytes) -> str:
    """Return the size of *body*, in the unit that reads best for it."""
    kb = len(body) / 1024
    return f"{kb / 1024:.1f} MB" if kb >= 1024 else f"{kb:.0f} KB"


def _ratio(speedup: float) -> str:
    """Return *speedup* as a factor, coarse enough to survive the noise of a
    measurement and the hardware that it runs on."""
    return f"about {speedup:.0f} times"


def _sentence() -> str:
    bodies = read_bodies()
    loop = asyncio.new_event_loop()
    try:
        measurements = []
        for name, page_cls, label in DOCUMENTS:
            _check(page_cls, name, bodies, loop)
            ratio = _ratio(_speedup(page_cls, name, bodies, loop))
            measurements.append(f"{ratio} faster for a {_size(bodies[name])} {label}")
    finally:
        loop.close()
    return textwrap.fill(
        f"Measured with frostwork {frostwork.__version__}, extraction is "
        f"{' and '.join(measurements)}, with every field of both page objects "
        f"declared.",
        width=79,
    )


def _write(sentence: str) -> None:
    text, count = re.subn(
        rf"{re.escape(START)}\n.*?{re.escape(END)}",
        f"{START}\n\n{sentence}\n\n{END}",
        DOCS.read_text(encoding="utf-8"),
        flags=re.DOTALL,
    )
    if not count:
        raise ValueError(f"Found no {START} block in {DOCS}")
    DOCS.write_text(text, encoding="utf-8")


def main() -> None:
    """Measure how much faster frostwork extracts selector declarations than
    parsel, over the same documents and page objects as the benchmarks, and
    print or write the sentence that says so in the documentation.

    Run this whenever the minimum supported frostwork version changes;
    ``test_documented_benchmark`` fails until the documented measurement is that
    of a version at least as new."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument(
        "--write", action="store_true", help=f"update the {DOCS.name} block in place"
    )
    sentence = _sentence()
    if parser.parse_args().write:
        _write(sentence)
    print(sentence)


if __name__ == "__main__":
    main()
