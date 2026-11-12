"""SECURITY I-1: alto-cloud.js pushes and pulls the chip-bar choice (chips, chipsAt) only in its expected shape:
'on' | 'off' and a time no more than a day ahead. Anything else (a long string, a wrong type, a pinned future time) is dropped,
never written to the account and never stored locally. Runs the real alto-cloud.js against the Firestore stand-in of test_backgrounds."""
import http.server
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_backgrounds import _STUBS  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

KEY, TL = "alto-hl-civ-chips", "users/u1/tl/civ"
FUTURE = 4102444800000  # 2100


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    from alto.cloud import emit_cloud_js
    d = tmp_path_factory.mktemp("site")
    (d / "alto-cloud.js").write_text(emit_cloud_js({"apiKey": "k", "authDomain": "p.firebaseapp.com", "projectId": "p",
                                                    "storageBucket": "", "messagingSenderId": "", "appId": "a"}), encoding="utf-8")
    (d / "sync.html").write_text('<!doctype html><html><head><meta charset="utf-8"></head><body>'
                                 '<script type="module" src="/alto-cloud.js" data-tid="civ"></script></body></html>', encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}"
    s.shutdown()


@pytest.fixture(params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def _run(browser, base, docs=None, local=None):
    pg = browser.new_page()
    pg.route("https://www.gstatic.com/firebasejs/**", lambda r: r.fulfill(
        status=200, content_type="text/javascript", body=_STUBS[r.request.url.rsplit("/", 1)[1]]))
    pg.add_init_script("window.__fs={docs:%s,writes:[]};" % json.dumps(docs or {}))
    if local is not None:
        pg.add_init_script("try{localStorage.getItem(%r)===null&&localStorage.setItem(%r,%r)}catch(e){}" % (KEY, KEY, local))
    pg.goto(base + "/sync.html"); pg.wait_for_timeout(2500)
    out = (pg.evaluate("window.__fs.docs[%r]||{}" % TL), pg.evaluate("localStorage.getItem(%r)" % KEY))
    pg.close()
    return out


def test_good_choice_still_syncs_both_ways(browser, base):
    d, _ = _run(browser, base, local=json.dumps({"v": "off", "t": 100}))
    assert d["chips"] == "off" and d["chipsAt"] == 100
    _, ls = _run(browser, base, docs={TL: {"chips": "off", "chipsAt": 500}})
    assert json.loads(ls) == {"v": "off", "t": 500}


@pytest.mark.parametrize("bad", [
    {"v": "x" * 5000, "t": 100}, {"v": "ON", "t": 100}, {"v": 7, "t": 100}, {"v": "off", "t": FUTURE}, {"v": "off", "t": -5}])
def test_bad_local_value_is_never_pushed(browser, base, bad):
    d, _ = _run(browser, base, local=json.dumps(bad))
    assert "chips" not in d and "chipsAt" not in d


@pytest.mark.parametrize("bad", [{"chips": "y" * 5000, "chipsAt": 500}, {"chips": "off", "chipsAt": FUTURE}])
def test_bad_remote_value_is_never_stored(browser, base, bad):
    _, ls = _run(browser, base, docs={TL: bad})
    assert ls is None
