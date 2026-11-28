"""Chip labels (Luke 2026-11-28, B-1128): a 1-2 letter badge on any chip, a legend of what each letter means, a tooltip on hover and long-press.
Data/validation/tools run anywhere; the page checks run in WebKit (desktop and iPhone size), offline, and skip without Playwright."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LEGEND = [{"label": "H", "meaning": "history"}, {"label": "R", "meaning": "explains the modern rule"}, {"label": "O", "meaning": "overruled"}]


def _brief(name, labelled=True):
    d = json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8"))
    b = d["brief"]
    if labelled:
        b["chip_legend"] = copy.deepcopy(LEGEND)
        for ax in b.get("axes", []):
            for i, v in enumerate(ax["values"]):
                v["label"] = "HRO"[i % 3]
                if i == 0:
                    v["labels"] = ["\u2605"]
        if b.get("entities"):
            b["entities"][0]["label"] = "R"
    return d


def _html(d):
    from alto.build.builder import build_timeline, load_brief
    out = build_timeline(*load_brief(copy.deepcopy(d)))
    return out if isinstance(out, str) else out[0]


# ── data ──
def test_a_label_is_one_or_two_letters_and_the_legend_is_checked():
    from alto.build.brief import BriefError, clean_label, validate_brief
    from alto.build.builder import load_brief
    from alto.build.brief import tags_of
    assert clean_label(" h! ") == "H" and clean_label("abc") == "AB" and clean_label(None) == "" and clean_label("\u2605") == "\u2605"
    assert tags_of("o", ["\u2605", "O", "x"]) == ["O", "\u2605"]          # `label` is shorthand; two tags at most, no repeats
    d = _brief("outline")
    validate_brief(load_brief(copy.deepcopy(d))[0])
    bad = copy.deepcopy(d)
    bad["brief"]["axes"][0]["values"][0]["labels"] = ["A", "B", "C"]
    with pytest.raises(BriefError):
        validate_brief(load_brief(bad)[0])
    bad = copy.deepcopy(d)
    bad["brief"]["chip_legend"] = LEGEND + [{"label": "H", "meaning": "again"}]
    with pytest.raises(BriefError):
        validate_brief(load_brief(bad)[0])


def test_an_unlabelled_timeline_carries_no_badges_and_the_label_survives_a_rebuild():
    assert 'class="alto-lbl"' not in _html(_brief("outline", labelled=False))
    h = _html(_brief("outline"))
    assert '"legend":[{"label":"H"' in h.replace(" ", "") or '"H"' in h


def test_the_tools_take_a_label_and_a_legend():
    pytest.importorskip("mcp")
    from alto import mcp_server
    assert "label?" in mcp_server.set_entities.__doc__ and "label?" in mcp_server.set_axis_values.__doc__
    assert hasattr(mcp_server, "set_chip_legend")


def test_a_manual_edit_of_a_label_and_the_legend_folds_into_the_draft():
    from alto import edits
    brief = _brief("outline")["brief"]
    brief["chip_legend"] = []
    vid = brief["axes"][0]["values"][0]["id"]
    t = edits._target(f"env|{vid}|label", brief, {}, [])
    assert t and t[1] == "label" and t[2] == "plain"
    t = edits._target("cl|legend", brief, {}, [])
    assert t and t[1] == "chip_legend" and t[2] == "legend"
    assert edits._legend_list([{"label": "h", "meaning": " x "}, {"label": "!!"}]) == [{"label": "H", "meaning": "x"}]


# ── the page, in WebKit ──
@pytest.fixture(scope="module")
def browser(tmp_path_factory):
    pw = pytest.importorskip("playwright.sync_api")
    d = tmp_path_factory.mktemp("lbl")
    for n in ("outline", "lanes", "contracts"):
        (d / f"{n}.html").write_text(_html(_brief(n)), encoding="utf-8")
    import functools
    import http.server
    import socketserver
    import threading
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    h.log_message = lambda *a: None
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no WebKit: {e}")
        yield b, base
        b.close()
    srv.shutdown()


def _open(browser, name, phone=False):
    b, d = browser
    kw = dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2) if phone else dict(viewport={"width": 1440, "height": 900})
    pg = b.new_context(**kw).new_page()
    pg.goto(f"{d}/{name}.html", wait_until="load")
    pg.wait_for_timeout(1200)
    return pg


@pytest.mark.parametrize("name", ["outline", "contracts", "lanes"])
@pytest.mark.parametrize("phone", [False, True])
def test_every_labelled_chip_wears_its_badge_where_it_shows(browser, name, phone):
    pg = _open(browser, name, phone)
    pg.evaluate("document.querySelector('.node')&&1")
    n = pg.evaluate("document.querySelectorAll('.node-footer [data-lbl]').length + document.querySelectorAll('#nav [data-lbl], #nav-drawer-body [data-lbl]').length")
    assert n > 0, "no badge on a card footer or the nav"
    # no text on text: a badge is a sibling of the chip's own text inside it, never positioned over it
    over = pg.evaluate("[...document.querySelectorAll('.alto-lbl')].filter(e=>getComputedStyle(e).position==='absolute').length")
    assert over == 0
    # the whole chip stays one target: the badge is a plain child of its chip, not a control of its own
    assert pg.evaluate("[...document.querySelectorAll('.alto-lbl')].every(e=>e.parentElement.hasAttribute('data-lbl')&&e.tabIndex<0&&!e.onclick)")


def test_a_chip_page_and_its_chip_row_carry_the_label(browser):
    pg = _open(browser, "outline")
    vid = pg.evaluate("Object.keys(window._ALTO_CHIPLBL.byId.env)[0]")
    pg.evaluate(f"showDetail('env','{vid}')")
    pg.wait_for_timeout(500)
    assert pg.evaluate("!!document.querySelector('#detail-page .detail-name .alto-lbl')")
    pg.evaluate("showDetail('node','formation')")
    pg.wait_for_timeout(500)
    assert pg.evaluate("!!document.querySelector('#detail-page .char-chip .alto-lbl')")


def test_hovering_a_badge_shows_the_whole_legend_with_its_letter_marked(browser):
    pg = _open(browser, "outline")
    pg.evaluate("window.scrollTo(0,0)")
    box = pg.evaluate("(()=>{const e=document.querySelector('#nav [data-lbl], .node-footer [data-lbl]');const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]})()")
    pg.mouse.move(*box)
    pg.wait_for_timeout(300)
    t = pg.evaluate("(()=>{const e=document.getElementById('alto-lbl-tip');return e&&getComputedStyle(e).display==='block'?e.innerText:null})()")
    assert t and "history" in t and "overruled" in t, t
    assert pg.evaluate("document.querySelectorAll('#alto-lbl-tip div.on').length") == 1


def test_a_long_press_shows_the_meaning_on_a_phone_and_does_not_open_the_chip(browser):
    pg = _open(browser, "outline", phone=True)
    pg.evaluate("showDetail('node','formation')")
    pg.wait_for_timeout(500)
    got = pg.evaluate("""() => new Promise(res => { const c=document.querySelector('#detail-page .char-chip[data-lbl]'); const r=c.getBoundingClientRect();
      const t={identifier:1,target:c,clientX:r.x+8,clientY:r.y+8}, ev=(n,l)=>{ const e=new Event(n,{bubbles:true,cancelable:true}); e.touches=l; e.changedTouches=[t]; return e; };
      c.dispatchEvent(ev('touchstart',[t]));
      setTimeout(()=>{ const tip=document.getElementById('alto-lbl-tip'); const shown=tip&&getComputedStyle(tip).display==='block';
        c.dispatchEvent(ev('touchend',[])); c.click();
        setTimeout(()=>res({shown, stayed: document.querySelector('#detail-page .detail-name').textContent.includes('Formation')}),100); },700); })""")
    assert got["shown"], got
    assert got["stayed"], "the long press also opened the chip"


def test_the_legend_heads_the_filter_panel(browser):
    pg = _open(browser, "outline")
    pg.evaluate("document.getElementById('filter-toggle').click()")
    pg.wait_for_timeout(500)
    assert "modern rule" in pg.evaluate("document.querySelector('#ef-panel .alto-lbl-legend')?.innerText||''")


def test_the_edit_api_relabels_every_chip_and_undo_restores(browser):
    pg = _open(browser, "outline")
    vid = pg.evaluate("Object.keys(window._ALTO_CHIPLBL.byId.env)[0]")
    pg.evaluate(f"window._altoChipLbl.set('env','{vid}',['Z'], document.querySelector('.esym-btn[data-lbl]').getAttribute('data-tn'))")
    pg.wait_for_timeout(300)
    assert pg.evaluate("[...document.querySelectorAll('.esym-btn .alto-lbl')].some(e=>e.textContent==='Z')")
    pg.evaluate(f"window._altoChipLbl.set('env','{vid}',[], document.querySelector('.esym-btn[data-lbl]').getAttribute('data-tn'))")
    assert not pg.evaluate("[...document.querySelectorAll('.esym-btn .alto-lbl')].some(e=>e.textContent==='Z')")


FAKE = """(function(){ var store=null;
 var C={enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); window.__edits=store; return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""


def test_in_edit_mode_a_chip_page_offers_a_label_button_that_labels_and_undoes(browser):
    b, d = browser
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(FAKE)
    pg = ctx.new_page()
    pg.goto(f"{d}/outline.html", wait_until="load")
    pg.wait_for_timeout(1200)
    pg.click("#alto-edit-pill .aep-manual")
    pg.wait_for_timeout(500)
    ids = pg.evaluate("Object.keys(window._ALTO_CHIPLBL.byId.env)")
    plain = pg.evaluate("[...document.querySelectorAll('.esym-btn')].map(e=>e.getAttribute('data-tn')||e.title).length")
    assert ids and plain
    vid = ids[0]
    pg.evaluate(f"showDetail('env','{vid}')")
    pg.wait_for_timeout(600)
    btn = pg.locator(".aed-lblbtn")
    btn.wait_for(timeout=5000)
    assert btn.count() == 1 and btn.evaluate("e => e.offsetHeight") >= 44
    btn.click()
    pg.fill("#aed-form [data-f=label]", "x \u2605 q")
    pg.fill("#aed-form [data-f=legend]", "H = history\nX = my own letter")
    pg.click("#aed-form [data-a=ok]")
    pg.wait_for_timeout(500)
    assert pg.evaluate(f"window._altoChipLbl.get('env','{vid}').join(' ')") == "X \u2605"
    assert pg.evaluate("window._altoChipLbl.legend().map(r=>r.label).join('')") == "HX"
    assert pg.evaluate("document.querySelector('#detail-page .detail-name .alto-lbl')?.textContent") == "X"
    pg.wait_for_timeout(2500)
    folded = pg.evaluate("JSON.stringify(window.__edits||{}) + JSON.stringify(Object.assign({}, localStorage))")
    assert f"env|{vid}|label" in folded and "cl|legend" in folded
    pg.click("#alto-edit-exit .ee-undo")        # the label and the legend were one change: one undo
    pg.wait_for_timeout(400)
    assert pg.evaluate(f"window._altoChipLbl.get('env','{vid}').length") == 2
    assert pg.evaluate("window._altoChipLbl.legend().length") == 3


def test_a_chip_can_wear_a_letter_and_a_gold_star_and_the_index_page_keys_only_the_tags_it_uses(browser):
    pg = _open(browser, "outline", phone=True)
    pg.evaluate("showDetail('index','env')")
    pg.wait_for_timeout(600)
    k = pg.evaluate("""() => { const e=document.querySelector('#detail-content .alto-lbl-key'); if(!e) return null; const r=e.getBoundingClientRect();
      return {t:e.innerText, l:r.left, rt:window.innerWidth-r.right, n:e.querySelectorAll('.alto-lbl').length, star:!!e.querySelector('.alto-lbl.star')}; }""")
    assert k, "no key on the page that lists the values"
    assert k["n"] == 4 and k["star"] and "history" in k["t"] and "overruled" in k["t"], k       # the 3 letters + the star, nothing else
    assert k["l"] >= 20 and k["rt"] >= 20, k
    pg.evaluate("showDetail('node','formation')")
    pg.wait_for_timeout(400)
    assert pg.evaluate("document.querySelectorAll('#detail-content .alto-lbl-key').length") == 0
    pg.evaluate("showDetail('index','env')")
    pg.wait_for_timeout(400)
    two = pg.evaluate("[...document.querySelectorAll('#detail-content [data-lbl]')].filter(e=>e.querySelectorAll(':scope>.alto-lbl').length===2).length")
    assert two >= 1, "a chip with a letter and a star shows two badges"
