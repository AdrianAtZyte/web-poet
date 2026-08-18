from importlib.util import find_spec

import pytest


@pytest.mark.skipif(
    find_spec("niquests") is not None, reason="the framework extra is installed"
)
def test_framework():
    with pytest.raises(ImportError, match="web-poet\\[framework\\]"):
        import web_poet.framework  # noqa: F401,PLC0415
