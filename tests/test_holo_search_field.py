"""Holo home search is ONE glass field (Luke, 2026-11-12: "see the problem with search bar?  problem in mini version as well, only in holo"): in the big and the
compact desktop search and the phone's, the field is the only element with a border, outline, ring or plate (the input, the hint and the grow/shrink control had
each drawn their own box); the control's name shows inside the field, never as a title bubble over the rim; keyboard focus still lights the field; the Holo desktop
home keeps its top ground mask. Classic and Retro search read the same computed styles as on rel-225-int 8d10d06e (GOLD, taken from that tree)."""
import http.server
import json
import os
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alto.build import backgrounds_import as bi, holo, pages, phone as _phone, retro   # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

HOME = [{"name": "Book", "pid": "p", "courses": [
    {"title": "Terrarium", "href": "t.html", "sub": "5 units", "courseId": "a", "units": ["#4a9eff", "#f43f5e"]},
    {"title": "Terrarium", "href": "t.html", "sub": "5 units", "courseId": "b", "units": ["#4a9eff"]}]}]
SIDES = ("Top", "Right", "Bottom", "Left")
DUMP = """()=>{const root=document.getElementById('search-btn');if(!root)return null;
  const g=e=>{const c=getComputedStyle(e),r=e.getBoundingClientRect(),o={sel:e.tagName.toLowerCase()+(e.id?'#'+e.id:'')+(typeof e.className==='string'&&e.className?'.'+e.className.trim().split(/\\s+/).join('.'):''),
    vis:r.width>0&&r.height>0&&c.display!=='none'&&c.visibility!=='hidden',outline:c.outlineStyle+' '+c.outlineWidth,shadow:c.boxShadow,bg:c.backgroundColor,bgi:c.backgroundImage,title:e.getAttribute('title')};
    ['Top','Right','Bottom','Left'].forEach(s=>o['b'+s]=c['border'+s+'Style']+' '+c['border'+s+'Width']+' '+c['border'+s+'Color']);return o};
  return [root,...root.querySelectorAll('*')].map(g).filter(o=>o.vis)}"""


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("holosearch")
    (d / "t.html").write_text("<html><body>t</body></html>")
    (d / "h.html").write_text(pages.build_home(HOME), encoding="utf-8")
    for mod, sub in ((holo, "holo"), (retro, "retro"), (_phone, "phone")):
        nm, tx = (mod.holo_asset if sub == "holo" else mod.retro_asset if sub == "retro" else mod.phone_asset)()
        (d / sub).mkdir()
        (d / sub / nm).write_text(tx, encoding="utf-8")
    lib, js = bi.site_file()
    (d / lib).write_text(js, encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(scope="module")
def webkit():
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no webkit: {e}")
        yield b
        b.close()


def _open(webkit, site, style, dark, mode, ground=None):
    """The home page in a look, scrolled, with its search open: big, mini (the compact desktop field) or phone (402 wide)."""
    size = (402, 874) if mode == "phone" else (1440, 900)
    ctx = webkit.new_context(viewport={"width": size[0], "height": size[1]})
    pg = ctx.new_page()
    pg.goto(site + "/h.html", wait_until="load")
    pg.evaluate("([s,g])=>{localStorage.clear();localStorage.setItem('alto-bg-home-v1-style',s);if(g)localStorage.setItem('alto-bg-home-v1',JSON.stringify({v:g}))}", [style, ground])
    pg.goto(site + "/h.html", wait_until="load")
    pg.wait_for_timeout(700)
    pg.evaluate("(s)=>window._altoStyle && window._altoStyle.set(s)", style)
    if dark is not None:
        pg.evaluate("(d)=>document.documentElement.classList.toggle('dark',d)", dark)
    pg.evaluate("()=>window.scrollTo(0,200)")
    pg.wait_for_timeout(250)
    pg.click("#search-btn")
    pg.wait_for_timeout(300)
    if mode == "big":
        pg.click("#sx-toggle")
        pg.wait_for_timeout(300)
    pg.mouse.move(4, 450)
    pg.wait_for_timeout(200)
    return ctx, pg


def _boxed(o):
    """Does this element draw an edge or plate of its own?"""
    edge = any(not o["b" + s].startswith(("none", "hidden")) and not o["b" + s].split(" ")[1].startswith("0px") for s in SIDES)
    ring = o["shadow"] != "none"
    line = not o["outline"].startswith("none") and o["outline"].split(" ")[1] != "0px"
    plate = o["bg"] not in ("rgba(0, 0, 0, 0)", "transparent") or o["bgi"] != "none"
    return edge or ring or line or plate


@pytest.mark.parametrize("dark,mode", [(True, "big"), (True, "mini"), (True, "phone"), (False, "phone")])
def test_holo_search_is_one_field(webkit, site, dark, mode):
    ctx, pg = _open(webkit, site, "holo", dark, mode, "h-neon-rain" if dark else None)
    try:
        assert pg.evaluate("document.documentElement.classList.contains('alto-holo')")
        els = pg.evaluate(DUMP)
        assert els and els[0]["sel"].startswith("div#search-btn")
        assert _boxed(els[0]), "the field keeps its rim"
        inner = [o["sel"] for o in els[1:] if _boxed(o)]
        assert inner == [], f"boxes inside the Holo search field: {inner}"
        if mode != "phone":
            tg = [o for o in els if o["sel"].startswith("button#sx-toggle")][0]
            assert tg["title"] is None, "no title bubble over the rim in Holo"
            pg.hover("#sx-toggle")
            pg.wait_for_timeout(250)
            assert pg.evaluate("document.getElementById('sx-toggle').getAttribute('title')") is None
            # its name shows inside the field: the ::before label lies within the field's box (and the viewport)
            lab = pg.evaluate("""()=>{const t=document.getElementById('sx-toggle'),c=getComputedStyle(t,'::before');return {d:c.display,txt:c.content,
              f:document.getElementById('search-btn').getBoundingClientRect().toJSON(),t:t.getBoundingClientRect().toJSON(),pos:c.position,right:c.right,w:innerWidth}}""")
            assert lab["d"] != "none" and "search" in lab["txt"], lab
            assert lab["f"]["right"] <= lab["w"] and lab["t"]["right"] <= lab["f"]["right"] and lab["t"]["left"] >= lab["f"]["left"], lab
        # keyboard focus still shows, on the field itself
        assert pg.evaluate("document.activeElement && document.activeElement.id") == "search-input"
        sh = pg.evaluate("getComputedStyle(document.getElementById('search-btn')).boxShadow")
        assert "0px 0px 14px" in sh, sh
    finally:
        ctx.close()


def test_holo_desktop_home_has_the_top_ground_mask(webkit, site):
    ctx, pg = _open(webkit, site, "holo", True, "mini", "h-neon-rain")
    try:
        m = pg.evaluate("""()=>{const c=getComputedStyle(document.documentElement,'::before');return {p:c.position,h:c.height,z:c.zIndex,bg:c.backgroundImage,
          ground:getComputedStyle(document.documentElement).getPropertyValue('--ho-bgrgb').trim()}}""")
        assert m["p"] == "fixed" and int(m["z"]) >= 101 and float(m["h"][:-2]) >= 50, m
        g = ", ".join(x.strip() for x in m["ground"].split(","))
        assert m["bg"].startswith(f"linear-gradient(rgb({g})") and "rgba(0, 0, 0, 0)" in m["bg"], m   # (the Holo ground, fading out: no flat band)
    finally:
        ctx.close()


GOLD_FILE = Path(__file__).with_name("holo_search_gold.json")
CASES = [("classic", False, "big"), ("classic", False, "mini"), ("classic", False, "phone"), ("retro", None, "big"), ("retro", None, "mini"), ("retro", None, "phone")]


@pytest.mark.parametrize("style,dark,mode", CASES)
def test_classic_and_retro_search_unchanged(webkit, site, style, dark, mode):
    ctx, pg = _open(webkit, site, style, dark, mode)
    try:
        els = pg.evaluate(DUMP)
    finally:
        ctx.close()
    key = f"{style}-{mode}"
    if os.environ.get("ALTO_HOLO_SEARCH_GOLD"):   # (to re-take GOLD on a reference tree: ALTO_HOLO_SEARCH_GOLD=1)
        gold = json.loads(GOLD_FILE.read_text()) if GOLD_FILE.exists() else {}
        gold[key] = els
        GOLD_FILE.write_text(json.dumps(gold, indent=1, sort_keys=True))
        pytest.skip("gold written")
    gold = json.loads(GOLD_FILE.read_text())[key]
    assert els == gold


@pytest.mark.parametrize("mode", ["big", "mini"])
def test_retro_search_hint_and_button_have_no_frame(webkit, site, mode):
    ctx, pg = _open(webkit, site, "retro", None, mode)
    try:
        els = pg.evaluate(DUMP)
        tg = [o for o in els if o["sel"].startswith("button#sx-toggle")][0]
        assert not _boxed(tg), tg
        assert _boxed(els[0]), "the field keeps its one gold rim"
        pg.evaluate("document.activeElement && document.activeElement.blur()")
        pg.wait_for_timeout(200)
        rim0 = pg.evaluate("getComputedStyle(document.getElementById('search-btn')).borderTopColor")
        pg.focus("#search-input")
        pg.wait_for_timeout(200)
        rim1 = pg.evaluate("getComputedStyle(document.getElementById('search-btn')).borderTopColor")
        assert rim1 != rim0, "focus brightens the rim"
    finally:
        ctx.close()
