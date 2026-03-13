import pytest
from scripts.push_dashboard import compare_css, CssComparison


def test_compare_css_identical():
    result = compare_css("body { color: red; }", "body { color: red; }")
    assert result.changed is False


def test_compare_css_different():
    result = compare_css("body { color: red; }", "body { color: blue; }")
    assert result.changed is True
    assert result.local_length > 0
    assert result.remote_length > 0


def test_compare_css_length_warning():
    long_css = "x" * 31000
    result = compare_css(long_css, "short")
    assert result.length_warning is True


def test_compare_css_no_warning():
    short_css = "body { color: red; }"
    result = compare_css(short_css, "body { color: blue; }")
    assert result.length_warning is False
