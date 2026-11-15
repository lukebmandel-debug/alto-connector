"""STAMP-bassdocs (independent author): HTML or script pasted into the Documents "Paste text" box, in the text OR the name, renders inert in the
panel (Chromium + WebKit, Python Playwright, the in-page simulator: no network, no key, no proxy). Skips without Playwright."""
import json

import pytest

from bass_support import ROOT  # noqa: F401
from test_bass_documents_browser import PAGE

pw = pytest.importorskip("playwright.sync_api")

EVIL = ['<img src=x onerror="window.__pwn=1">', '</textarea><script>window.__pwn=2</script>', '"><svg onload="window.__pwn=3">',
        "<iframe srcdoc=\"<script>parent.__pwn=4</script>\"></iframe>"]


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_pasted_html_and_script_in_text_or_name_render_inert(tmp_path, engine, monkeypatch):
    monkeypatch.setenv("ALTO_BASS_UI", "1")
    from alto.build import bass_ui
    page = tmp_path / "page.html"
    page.write_text(PAGE.replace("__BUNDLE__", bass_ui.ASSET.replace("</script", "<\\/script")), "utf-8")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, engine).launch()
        except Exception as e:                                                         # noqa: BLE001
            pytest.skip(f"{engine} is not installed here: {e}"[:200])
        pg = b.new_page(viewport={"width": 1180, "height": 760})
        errs, net = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("request", lambda r: None if r.url.startswith(("file:", "data:", "about:")) else net.append(r.url))
        pg.goto(page.as_uri() + "#bass=docs")
        pg.wait_for_function("() => window._altoBass")
        pg.evaluate("() => window._altoBass.dev('docs')")
        pg.wait_for_timeout(250)
        for i, evil in enumerate(EVIL):
            pg.click('[data-a="d-paste"]')
            pg.fill("#bs-dpn", evil)
            pg.fill("#bs-dpt", "Notes " + evil)
            pg.click('[data-a="d-pasteok"]')
            pg.wait_for_timeout(250)
            pg.click('[data-a="d-paste"]')                                            # re-open: the draft box re-renders what was typed
            pg.fill("#bs-dpt", evil)
            pg.fill("#bs-dpn", evil)
            pg.evaluate("() => window._altoBass.dev && 0")
            pg.click('[data-a="d-pastex"]')
            pg.wait_for_timeout(150)
        state = pg.evaluate("""() => { const r = document.getElementById('bass-root');
            return {pwn: window.__pwn || null, inj: r.querySelectorAll('img[src="x"], svg[onload], iframe, script').length,
                    onattrs: [...r.querySelectorAll('*')].filter(e => [...e.attributes].some(a => /^on/i.test(a.name))).length,
                    text: r.innerText}; }""")
        lib = pg.evaluate("() => window._altoBass.call('docs', {op: 'list'})")
        b.close()
    assert state["pwn"] is None and state["inj"] == 0 and state["onattrs"] == 0, state
    names = json.dumps([f["name"] for f in lib["files"]])
    assert all(json.dumps(e)[1:-1][:20] in names for e in EVIL[:1]), names                          # it was saved, as plain text
    assert '<img src=x onerror="window.__pwn=1">' in state["text"], state["text"][:600]             # shown literally, not parsed
    assert not errs and not net, (errs, net)
