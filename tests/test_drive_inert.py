"""It ships INERT: with ALTO_DRIVE_CLIENT_ID / ALTO_DRIVE_API_KEY / ALTO_DRIVE_APP_ID absent (or only some set) nothing about a built page, the headers or
the hosted files changes. With all three set the Picker page and its own CSP rule appear, and only those. Plain venv, no SDK, nothing skipped."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import drive_common as DC  # noqa: E402
from alto import publish_static as ps  # noqa: E402
from alto.build import drive_picker_page as PK  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.pages import build_home  # noqa: E402

MARKERS = ("gdChip", "alto-drive-cfg", "data-gdrive", "/drive-picker/", "Choose from Drive", "_ALTO_DRIVE", "drive_common")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for n in DC.DriveConfig.ENV + ("ALTO_BASS_UI", "ALTO_BASS_BASE"):
        monkeypatch.delenv(n, raising=False)


def _set(monkeypatch, k):
    for n, v in list(zip(DC.DriveConfig.ENV, ("c.apps.googleusercontent.com", "key-1", "12345")))[:k]:
        monkeypatch.setenv(n, v)


def _pages():
    out = {}
    for name in ("outline", "contracts", "lanes"):
        d = json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8"))
        out[name] = build_timeline(*load_brief(d))[0]
    out["home"] = build_home([{"name": "Law", "pid": "p", "courses": []}])
    return out


def test_default_build_carries_no_trace():
    for name, page in _pages().items():
        assert [m for m in MARKERS if m in page] == [], name
    assert ps._picker_csp() is None
    assert "/drive-picker/**" not in json.dumps(ps._security_headers(None))


@pytest.mark.parametrize("k", [1, 2])
def test_a_half_finished_deploy_is_still_inert_and_byte_identical(monkeypatch, k):
    base = _pages()
    base_headers = json.dumps(ps._security_headers(None), sort_keys=True)
    _set(monkeypatch, k)
    assert DC.DriveConfig.from_env().partial is True
    assert _pages() == base
    assert json.dumps(ps._security_headers(None), sort_keys=True) == base_headers and ps._picker_csp() is None


def test_all_three_set_turns_on_only_the_picker_rule_and_the_timeline_chip(monkeypatch):
    base_pages, base_headers = _pages(), ps._security_headers(None)
    _set(monkeypatch, 3)
    assert ps._picker_csp() == PK.PICKER_CSP
    on = ps._security_headers(None)
    extra = [h for h in on if h not in base_headers]
    assert [h["source"] for h in extra] == ["/drive-picker/**"]
    assert [h for h in base_headers if h not in on] == []                              # nothing else moved: not the site-wide CSP, not /connect/
    pages = _pages()
    assert pages["home"] == base_pages["home"]                                          # the homepage is untouched
    for name in ("outline", "contracts", "lanes"):
        assert "gdChip" in pages[name] and "gdChip" not in base_pages[name]
        # the link panel is placed by the enlarge safe box (one copy of the measured-chrome code), handed over only in a Drive build
        assert "function _safeBox(x0,x1,win){" in pages[name] and "function _safeBox(x0,x1){" in base_pages[name] and "window._altoSafeBox={box:_safeBox," in pages[name] and "window._altoSafeBox=_safeBox;" not in pages[name]
        assert pages[name].count("function _safeBox(") == 1 and pages[name].count("function _chromeRects(") == 1
        assert "window._altoSafeBox.box(x - PAD, x + w + PAD, true)" in pages[name] and "querySelectorAll('*')" not in pages[name].split("function gdPlace(")[1].split("var GD_KEY")[0]


def test_the_picker_page_is_written_only_when_on(monkeypatch):
    sp = (ROOT / "alto" / "publish_static.py").read_text(encoding="utf-8")
    assert "if _picker_csp():" in sp and "drive_on()" in sp                          # one gate decides both the page and its header
