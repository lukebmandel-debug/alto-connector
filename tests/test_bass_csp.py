"""The published page's CSP connect-src lets the browser reach the Bass beta proxy, and ONLY then (ALTO_BASS_UI on AND ALTO_BASS_BASE set)."""
import pytest

from alto import publish_static as ps

RUN = "https://bass-proxy-abc123-uc.a.run.app"
NEW = "https://bass-proxy-123456789012.us-central1.run.app"
FN = "https://us-central1-example-project.cloudfunctions.net/bass"


def _connect(monkeypatch, ui, base):
    for k, v in (("ALTO_BASS_UI", ui), ("ALTO_BASS_BASE", base)):
        monkeypatch.delenv(k, raising=False) if v is None else monkeypatch.setenv(k, v)
    return next(p for p in ps._csp("'none'").split("; ") if p.startswith("connect-src"))


def test_flag_off_the_csp_is_unchanged_even_with_a_base_set(monkeypatch):
    off = _connect(monkeypatch, None, None)
    assert _connect(monkeypatch, None, RUN) == off                      # no UI flag: nothing added
    assert _connect(monkeypatch, "0", RUN) == off
    assert "run.app" not in off and "cloudfunctions" not in off


def test_flag_on_without_a_base_adds_nothing(monkeypatch):
    assert _connect(monkeypatch, "1", None) == _connect(monkeypatch, None, None)
    assert _connect(monkeypatch, "1", "") == _connect(monkeypatch, None, None)


@pytest.mark.parametrize("base,origin", [(RUN, RUN), (NEW, NEW), (NEW + "/bass", NEW), (FN, "https://us-central1-example-project.cloudfunctions.net"), (RUN + "/x/y", RUN)])
def test_flag_on_with_a_proxy_base_allows_exactly_that_origin(monkeypatch, base, origin):
    c = _connect(monkeypatch, "1", base)
    assert c.endswith(" " + origin) and c.count(origin) == 1
    assert "*" not in c.replace("https://*.googleapis.com", "").replace("https://*.firebaseio.com", "").replace("wss://*.firebaseio.com", "").replace("https://*.firebaseapp.com", "")


@pytest.mark.parametrize("base", ["http://bass-x-uc.a.run.app", "https://evil.example.com", "https://x.a.run.app.evil.com", "https://Bass-X-uc.a.run.app", "https://x-uc.a.run.app:8443", "https://run.app", "https://x.run.app.evil.com",
                                  "javascript:1", "https://x.a.run.app; script-src *", "//x-uc.a.run.app", "/bass"])
def test_anything_that_is_not_a_run_or_functions_https_origin_adds_nothing(monkeypatch, base):
    assert _connect(monkeypatch, "1", base) == _connect(monkeypatch, None, None)


# --- the beta build must still be PUBLISHABLE: single_file counts every `location.hash` in a page (a srcdoc page has no real hash) ----------
def test_a_private_and_an_offline_page_build_with_the_bass_ui_on(monkeypatch):
    import json
    from pathlib import Path
    from alto.build.builder import build_timeline, load_brief
    from alto.build.single_file import bundle, private_page
    d = json.loads((Path(__file__).resolve().parent.parent / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
    monkeypatch.delenv("ALTO_BASS_UI", raising=False)
    monkeypatch.delenv("ALTO_BASS_BASE", raising=False)
    b, nodes, conns = load_brief(d)
    html0 = build_timeline(b, nodes, conns)[0]
    off = (private_page(b, html0), bundle(b, html0))
    monkeypatch.setenv("ALTO_BASS_UI", "1")
    monkeypatch.setenv("ALTO_BASS_BASE", RUN)
    b, nodes, conns = load_brief(d)
    html, _ = build_timeline(b, nodes, conns)
    assert "_altoBassOpen" in html                                      # the Bass loader really is in this build
    on_private = private_page(b, html)
    for page, page_off in zip((on_private, bundle(b, html)), off):   # BundleError ("found 5 != 4") before the fix
        assert "_altoBassOpen" in page
        # none left over from the TIMELINE loader (swapped like the others); the offline bundle also embeds the home page, whose Bass switch has
        # one deep-link read (`#bass=`) of its own that no build step touches: at most that one extra
        assert page.count("location.hash") <= page_off.count("location.hash") + (1 if page is not on_private else 0)
        assert "/[#&]bass=/.test(__altoHash())" in page                  # the Bass auto-open reads the shell's hash, not the srcdoc's empty one
