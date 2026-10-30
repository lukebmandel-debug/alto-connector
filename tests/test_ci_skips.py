"""The CI-only skip hook in tests/conftest.py: inert unless ALTO_CI=1, and every entry names a test that exists."""
import importlib.util
import re
from pathlib import Path
from types import SimpleNamespace

TESTS = Path(__file__).resolve().parent


def _conftest():
    spec = importlib.util.spec_from_file_location("alto_conftest_under_test", TESTS / "conftest.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Item:
    def __init__(self, nodeid):
        self.nodeid, self.markers = nodeid, []

    def add_marker(self, m):
        self.markers.append(m)


def _items(c):
    listed = [_Item(prefix + "[chromium-a]") for prefix, _ in c.CI_SKIPS]
    other = _Item("tests/test_homepage.py::test_something_else")
    return listed, other


def test_the_hook_does_nothing_without_alto_ci(monkeypatch):
    c = _conftest()
    monkeypatch.delenv("ALTO_CI", raising=False)
    listed, other = _items(c)
    c.pytest_collection_modifyitems(SimpleNamespace(), listed + [other])
    assert all(not i.markers for i in listed + [other])
    monkeypatch.setenv("ALTO_CI", "0")
    c.pytest_collection_modifyitems(SimpleNamespace(), listed + [other])
    assert all(not i.markers for i in listed + [other])


def test_with_alto_ci_only_the_listed_tests_are_skipped_with_their_reason(monkeypatch):
    c = _conftest()
    monkeypatch.setenv("ALTO_CI", "1")
    listed, other = _items(c)
    c.pytest_collection_modifyitems(SimpleNamespace(), listed + [other])
    assert other.markers == []
    for i in listed:
        assert len(i.markers) == 1 and i.markers[0].name == "skip" and i.markers[0].kwargs["reason"].startswith("CI: ")


def test_every_entry_has_a_reason_and_names_a_test_that_exists():
    c = _conftest()
    assert c.CI_SKIPS
    for prefix, why in c.CI_SKIPS:
        path, name = prefix.split("::")
        assert len(why) > 20
        assert re.search(r"^def " + re.escape(name) + r"\b", (TESTS.parent / path).read_text("utf-8"), re.M), prefix
