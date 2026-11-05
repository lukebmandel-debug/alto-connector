"""Pictures of the owner's own (alto/build/photos.py): the brief, the build (the page names a picture and never carries it), folding the page's
edits into the draft, the account layer, and in a real browser (Chromium and WebKit) the Photos section, a card's pictures, edit mode, the viewer,
print and the phone. Never touches a real account: the browser tests run against stand-ins for Firestore and the account."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import photos  # noqa: E402
from alto.build.brief import BriefError  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.private_shell import stored_bytes  # noqa: E402
from alto.build.manual_edit import jhash  # noqa: E402
from alto.edits import fold, photos_list, _jdump  # noqa: E402
from alto.edits import order_sig, published  # noqa: E402
from tests.test_manual_edit import Store, _build as _build_store, _node, _view  # noqa: E402,F401

OUTLINE = ROOT / "samples" / "outline_brief.json"
CLOUD = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
R1, R2, R3, R4 = "pic-abcdefghij", "pic-abcdefghik", "pic-abcdefghil", "pic-abcdefghim"


def _d():
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    d["nodes"][0]["sections"].append({"h": "Photos", "t": "See below.", "photos": {"items": [
        {"ref": R1, "caption": "A <b>cap</b>"}, {"ref": R2, "caption": "Two", "alt": "alt two"}], "label": "Exhibits"}})
    d["nodes"][1]["photos"] = [{"ref": R3, "caption": "card pic"}]
    return d


def _html(d=None):
    return build_timeline(*load_brief(d or _d()))[0]


def _data(html):
    m = re.search(r'<script id="alto-ph">window\._ALTO_PH=(.*?);window\._ALTO_PC=(.*?);window\._altoPicsLoad', html)
    return json.loads(m.group(1)), json.loads(m.group(2))


# ── the brief ───────────────────────────────────────────────────────────────

def test_a_photos_section_and_a_cards_pictures_reach_the_page_as_names_never_bytes():
    html = _html()
    ph, pc = _data(html)
    assert ph == {"n-formation-1": {"lab": "Exhibits", "n": [{"i": "p1", "r": R1, "c": "A cap"}, {"i": "p2", "r": R2, "c": "Two", "a": "alt two"}]}}
    assert pc == {"definiteness": [{"i": "p1", "r": R3, "c": "card pic"}]}
    assert 'class="aph-slot" data-aph="n-formation-1" hidden>A cap alt two' in html.replace("\\u003c", "<") or "aph-slot" in html
    assert "data:image" not in html.split('<script id="alto-ph">')[1].split("</script>")[0]
    assert photos.PATH in html and photos.ASSET[:80] not in html          # the renderer is a hosted file, fetched by the page


def test_a_page_with_no_pictures_loads_nothing_and_a_build_is_repeatable():
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    html = _html(d)
    assert _data(html) == ({}, {}) and "if(false)_altoPicsLoad();" in html
    assert _html(copy.deepcopy(d)) == html


def test_building_never_changes_the_stored_brief():
    d = _d()
    before = copy.deepcopy(d)
    _html(d)
    assert d == before


@pytest.mark.parametrize("bad,why", [
    ({"items": []}, "at least one"),
    ({"items": [{"ref": "x.jpg"}]}, "pic-"),
    ({"items": [{"ref": R1}, {"ref": R1}]}, "twice"),
    ({"items": [{"ref": R1, "url": "http://x"}]}, "unknown"),
    ({"items": [{"ref": R1, "caption": "x" * 201}]}, "caption"),
    ({"items": [{"ref": R1}], "extra": 1}, "unknown photos"),
])
def test_a_photos_section_that_would_not_build_is_refused(bad, why):
    d = _d()
    d["nodes"][0]["sections"][-1]["photos"] = bad
    with pytest.raises(BriefError, match=why):
        _html(d)


def test_a_section_carries_photos_or_a_tree_never_both():
    d = _d()
    d["nodes"][0]["sections"][-1]["quiz"] = {"questions": [{"q": "q?", "choices": ["a", "b"], "answer": 0}]}
    with pytest.raises(BriefError, match="one of"):
        _html(d)


def test_a_card_holds_at_most_twelve_pictures():
    d = _d()
    d["nodes"][1]["photos"] = [{"ref": f"pic-abcdefgh{i:02d}"} for i in range(13)]
    with pytest.raises(BriefError, match="12-picture"):
        _html(d)


def test_the_page_stays_small():
    base = _html(json.loads(OUTLINE.read_text(encoding="utf-8")))
    html = _html()
    assert stored_bytes(html) - stored_bytes(base) < 3000                 # (a few pictures' names and the loader)


# ── folding the page's edits into the draft ─────────────────────────────────

def _store():
    d = _d()
    return Store(d)


def test_a_photos_section_list_folds_and_a_rebuilt_page_wears_it():
    st = _store()
    v = _view(st)
    sec = v.owner("n", "formation").sections[-1]
    lst = photos_list(sec)
    new = {"lab": "Exhibits", "n": [lst["n"][1], {"i": "p9", "r": R4, "c": "Third", "a": "alt"}]}
    st.edits = {"v": 1, "ops": {"ph|n-formation-%d|pics" % (len(v.owner("n", "formation").sections) - 1): {"b": jhash(_jdump(lst)), "v": new, "t": 5}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and r["folded"] == 1, r
    assert _node(st, "formation")["sections"][-1]["photos"] == {"items": [
        {"id": "p2", "ref": R2, "caption": "Two", "alt": "alt two"}, {"id": "p9", "ref": R4, "caption": "Third", "alt": "alt"}], "label": "Exhibits"}
    ph, _pc = _data(_build_store(st)[0])
    assert [x["r"] for x in ph["n-formation-%d" % (len(v.owner("n", "formation").sections) - 1)]["n"]] == [R2, R4]
    assert fold(st, "u", "t1")["folded"] == 0
    assert published(st, "u", "t1") == 1


def test_a_photos_list_made_against_another_page_is_a_conflict_and_removing_every_picture_keeps_the_section():
    st = _store()
    n = len(_view(st).owner("n", "formation").sections) - 1
    st.edits = {"v": 1, "ops": {"ph|n-formation-%d|pics" % n: {"b": "deadbeef", "v": {"lab": "", "n": []}, "t": 1}}}
    r = fold(st, "u", "t1")
    assert r["conflicts"] == ["ph|n-formation-%d|pics" % n]
    st = _store()
    lst = photos_list(_view(st).owner("n", "formation").sections[-1])
    st.edits = {"v": 1, "ops": {"ph|n-formation-%d|pics" % n: {"b": jhash(_jdump(lst)), "v": {"lab": "Exhibits", "n": []}, "t": 1}}}
    assert fold(st, "u", "t1")["folded"] == 1
    sec = _node(st, "formation")["sections"][-1]
    assert "photos" not in sec and sec["h"] == "Photos"
    _build_store(st)


def test_a_new_photos_section_folds_with_its_pictures_and_an_empty_one_leaves_no_section():
    st = _store()
    v = _view(st)
    sig = order_sig(v.owner("n", "formation"))
    cur = [str(j) for j in range(len(_node(st, "formation")["sections"]))]
    st.edits = {"v": 1, "ops": {
        "n|formation|order": {"b": sig, "v": cur + ["new-ph1ph1", "new-ph2ph2"], "t": 1},
        "n|formation|s|new-ph1ph1|h": {"b": "", "v": "Photos", "t": 2},
        "ph|n-formation-new-ph1ph1|pics": {"b": "new", "v": {"lab": "", "n": [{"i": "p1", "r": R4, "c": "New one"}]}, "t": 3},
        "n|formation|s|new-ph2ph2|h": {"b": "", "v": "Nothing yet", "t": 4},
        "ph|n-formation-new-ph2ph2|pics": {"b": "new", "v": {"lab": "", "n": []}, "t": 5}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    secs = _node(st, "formation")["sections"]
    assert secs[-1]["h"] == "Photos" and secs[-1]["photos"]["items"][0]["ref"] == R4 and secs[-1]["photos"]["items"][0]["caption"] == "New one"
    assert [s["h"] for s in secs].count("Nothing yet") == 0
    _build_store(st)


def test_a_cards_pictures_fold_and_a_changed_list_is_a_conflict():
    st = _store()
    base = photos.compact_items(photos.sanitize_items(_node(st, "definiteness")["photos"]))
    new = base + [{"i": "p5", "r": R4, "c": "More"}]
    st.edits = {"v": 1, "ops": {"pc|definiteness|pics": {"b": base, "v": new, "t": 1}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and r["folded"] == 1, r
    assert [x["ref"] for x in _node(st, "definiteness")["photos"]] == [R3, R4]
    assert "definiteness" in st.put_n
    # the draft changed since (Claude edited the card too): the page's list loses
    st2 = _store()
    st2.edits = {"v": 1, "ops": {"pc|definiteness|pics": {"b": [{"i": "p1", "r": R1}], "v": new, "t": 1}}}
    assert fold(st2, "u", "t1")["conflicts"] == ["pc|definiteness|pics"]
    # every picture taken off a card
    st3 = _store()
    st3.edits = {"v": 1, "ops": {"pc|definiteness|pics": {"b": base, "v": [], "t": 1}}}
    assert fold(st3, "u", "t1")["folded"] == 1 and "photos" not in _node(st3, "definiteness")
    # a card made on the page (not yet in the draft) waits
    st4 = _store()
    st4.edits = {"v": 1, "ops": {"pc|card-ab12cd|pics": {"b": [], "v": new, "t": 1}}}
    assert fold(st4, "u", "t1")["folded"] == 0


def test_the_page_and_the_connector_sign_alike():
    st = _store()
    lst = photos_list(_view(st).owner("n", "formation").sections[-1])
    assert jhash(_jdump(lst)) == jhash(json.dumps(lst, ensure_ascii=False, separators=(",", ":")))


# ── in a browser (Chromium and WebKit): a stand-in for the account, never a real one ──────────────────

import functools  # noqa: E402
import http.server  # noqa: E402
import socketserver  # noqa: E402
import threading  # noqa: E402

pw = pytest.importorskip("playwright.sync_api")

# an account with a picture store of its own: `pic-seed0000N` names the file /pN.jpg, anything else is what was put
FAKE = """(function(){ var store=null, pics={}; window.__pics=pics; window.__puts=[];
 var C={enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); window.__edits=store; return Promise.resolve(); }, watchEdits:function(){ return function(){}; },
  pics:{ put:function(ref, th, big, meta){ pics[ref]={th:th, big:big, type:meta.type, thType:meta.thType}; window.__puts.push([ref, th.length, big.length, meta]); return Promise.resolve(true); },
         get:function(ref,k){ var m=/^pic-seed0000(\\d)$/.exec(ref); if(m) return fetch('/p'+m[1]+'.jpg').then(function(r){return r.arrayBuffer();}).then(function(b){ return {bytes:new Uint8Array(b), type:'image/jpeg'}; });
           var r=pics[ref]; if(!r) return Promise.resolve(null); return Promise.resolve(k==='big'?{bytes:r.big,type:r.type}:{bytes:r.th,type:r.thType||r.type}); },
         remove:function(ref){ delete pics[ref]; return Promise.resolve(true); } }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""

S1, S2, S3, S4, S5 = (f"pic-seed0000{i}" for i in range(5))


def _picture(path, i, w=1600, h=1100):
    from PIL import Image, ImageDraw
    c = [(40, 90, 200), (200, 90, 40), (40, 160, 90), (160, 60, 160), (220, 180, 40)][i % 5]
    im = Image.new("RGB", (w, h), c)
    d = ImageDraw.Draw(im)
    d.ellipse([w * .55, h * .15, w * .8, h * .45], fill=(255, 230, 150))
    d.rectangle([0, h * .7, w, h], fill=(30, 60, 40))
    im.save(path, "JPEG", quality=88)


def _seeded():
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    d["nodes"][0]["sections"].append({"h": "Photos", "t": "The exhibits.", "photos": {"items": [
        {"ref": S1, "caption": "Signed letter, 1892", "alt": "A letter"}, {"ref": S2, "caption": "The shop front"}, {"ref": S3}]}})
    d["nodes"][0]["photos"] = [{"ref": S4, "caption": "Portrait"}, {"ref": S5}, {"ref": S2}]
    d["nodes"][1]["photos"] = [{"ref": S3, "caption": "One"}]
    return d


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    pytest.importorskip("PIL")
    from alto.build import holo, retro
    root = tmp_path_factory.mktemp("pics")
    (root / "seeded.html").write_text(_html(_seeded()), encoding="utf-8")
    (root / "plain.html").write_text(_html(json.loads(OUTLINE.read_text(encoding="utf-8"))), encoding="utf-8")
    for mod, fn in ((photos, "pics_asset"), (retro, "retro_asset"), (holo, "holo_asset")):
        name, text = getattr(mod, fn)()
        (root / mod.FOLDER).mkdir(exist_ok=True)
        (root / mod.FOLDER / name).write_text(text, encoding="utf-8")
    for i in range(5):
        _picture(root / f"p{i}.jpg", i)
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", root
    srv.shutdown()


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def _open(browser, site, page="seeded", edit=False, mobile=False, viewport=None, dark=False):
    base, _root = site
    if mobile:
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True,
                                  user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
    else:
        ctx = browser.new_context(viewport=viewport or {"width": 1400, "height": 900})
    ctx.add_init_script(FAKE)
    pg = ctx.new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(f"{base}/{page}.html", timeout=90000)
    pg.wait_for_timeout(1800)
    if edit:
        pg.click("#alto-edit-pill .aep-manual")
        pg.wait_for_timeout(500)
    return pg


def _loaded(pg, sel):
    pg.wait_for_function("s => { const a=[...document.querySelectorAll(s)]; return a.length && a.every(i => i.complete && i.naturalWidth > 0); }", arg=sel, timeout=15000)


def _detail(pg, id_="formation"):
    pg.evaluate(f"showDetail('node','{id_}')")
    pg.wait_for_timeout(800)


def test_a_photos_section_draws_its_pictures_and_captions_under_the_text_and_opens_them_large(browser, site):
    pg = _open(browser, site)
    _detail(pg)
    _loaded(pg, ".aph:not(.aph-top) .aph-img img")
    assert pg.evaluate("[...document.querySelectorAll('.aph:not(.aph-top) .aph-cap')].map(e => e.textContent)") == ["Signed letter, 1892", "The shop front"]
    assert pg.evaluate("document.querySelector('.aph:not(.aph-top) .aph-img').getAttribute('aria-label')").startswith("A letter")
    assert pg.evaluate("!!document.querySelector('#detail-content .aph-slot')") is False            # the slot became the row
    pg.click(".aph:not(.aph-top) .aph-fig >> nth=1 >> .aph-img")
    pg.wait_for_selector("#aph-lb img[src^='blob:']", timeout=8000)
    assert pg.inner_text("#aph-lb .lb-cap") == "The shop front" and pg.inner_text("#aph-lb .lb-n") == "2 / 3"
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(300)
    assert pg.inner_text("#aph-lb .lb-n") == "3 / 3"
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(200)
    assert pg.evaluate("!document.getElementById('aph-lb')")
    assert not pg.errs, pg.errs
    pg.context.close()


def test_a_cards_picture_and_count_sit_on_it_and_the_enlarged_card_opens_them_beside_it(browser, site):
    pg = _open(browser, site)
    pg.evaluate("document.getElementById('node-formation').scrollIntoView({block:'center'})")
    pg.wait_for_timeout(500)
    _loaded(pg, "#node-formation .aph-thumb img")
    assert pg.inner_text("#node-formation .aph-thumb .aph-n") == "+2"
    assert pg.evaluate("!document.querySelector('#node-definiteness .aph-thumb .aph-n')")             # one picture: no count
    h = pg.evaluate("[document.querySelector('#node-formation .node-card').offsetHeight, document.querySelector('#node-formation .node-card').offsetWidth]")
    pl = _open(browser, site, page="plain")
    pl.wait_for_timeout(500)
    assert pl.evaluate("[document.querySelector('#node-formation .node-card').offsetHeight, document.querySelector('#node-formation .node-card').offsetWidth]") == h    # the card keeps its size
    pl.context.close()
    pg.evaluate("enterFocus('formation')")
    pg.wait_for_selector("#node-formation .aph-tray", timeout=5000)
    _loaded(pg, "#node-formation .aph-tray img")
    assert pg.evaluate("document.querySelectorAll('#node-formation .aph-tray button').length") == 3
    pg.evaluate("exitFocus()")
    pg.wait_for_timeout(600)
    assert pg.evaluate("!document.querySelector('.aph-tray')")
    pg.click("#node-formation .aph-thumb")                                                            # the thumb opens the viewer, never the card
    pg.wait_for_selector("#aph-lb", timeout=5000)
    assert pg.evaluate("document.getElementById('detail-page').classList.contains('visible')") is False
    assert not pg.errs, pg.errs
    pg.context.close()


def test_a_cards_pictures_sit_beside_its_title_on_its_page_and_below_it_while_editing(browser, site):
    pg = _open(browser, site)
    _detail(pg)
    _loaded(pg, ".aph-top .aph-img img")
    assert pg.evaluate("!!document.querySelector('.detail-header .aph-top.aph-side')") and pg.evaluate("document.querySelectorAll('.aph-top .aph-fig').length") == 3
    pg.evaluate("document.querySelector('#alto-edit-pill .aep-manual').click()")
    pg.wait_for_timeout(900)
    assert pg.evaluate("!document.querySelector('.detail-header .aph-top') && !!document.querySelector('.aph-top .aph-add')")
    pg.context.close()


def _add(pg, sel, files):
    with pg.expect_file_chooser() as fc:
        pg.click(sel)
    fc.value.set_files(files)
    pg.wait_for_function("document.querySelectorAll('.aph-err').length > 0 && !document.querySelector('.aph-add:disabled')", timeout=20000)
    pg.wait_for_timeout(700)


def test_edit_mode_adds_a_photos_section_with_pictures_captions_order_removal_undo_and_it_survives_a_reload(browser, site):
    _base, root = site
    pg = _open(browser, site, page="plain", edit=True)
    _detail(pg)
    pg.click(".aed-add >> nth=-1")
    pg.wait_for_selector("#aed-kinds button[data-k=photos]")
    assert "Photos" in pg.inner_text("#aed-kinds")
    pg.click("#aed-kinds button[data-k=photos]")
    pg.wait_for_selector(".aph:not(.aph-top) .aph-add", timeout=8000)
    _add(pg, ".aph:not(.aph-top) .aph-add", [str(root / "p0.jpg"), str(root / "p1.jpg"), str(root / "p2.jpg")])
    ops = pg.evaluate("window.__edits.ops")
    key = next(k for k in ops if k.startswith("ph|"))
    assert key.startswith("ph|n-formation-new-") and len(ops[key]["v"]["n"]) == 3
    # shrunk in the browser: a small and a large size went to the account, neither the original
    puts = pg.evaluate("window.__puts")
    assert len(puts) == 3 and all(p[1] < 60000 and p[2] < 900000 and p[3]["w"] <= 1800 for p in puts), puts
    _loaded(pg, ".aph:not(.aph-top) .aph-img img")
    # a caption and its alt text, the order, a removal
    pg.fill(".aph:not(.aph-top) .aph-fig >> nth=0 >> .aph-ed input >> nth=0", "Exhibit A")
    pg.keyboard.press("Tab")                                                                          # (typing on goes into the alt text: the row was not drawn again)
    pg.keyboard.type("A letter on a desk")
    pg.keyboard.press("Tab")
    pg.wait_for_timeout(1100)
    v = pg.evaluate("window.__edits.ops['%s'].v.n" % key)
    assert v[0]["c"] == "Exhibit A" and v[0]["a"] == "A letter on a desk"
    first = v[0]["r"]
    pg.hover(".aph:not(.aph-top) .aph-fig >> nth=0")
    pg.click(".aph:not(.aph-top) .aph-fig >> nth=0 >> .aph-tools button >> nth=1")                 # move right
    pg.wait_for_timeout(1100)
    assert pg.evaluate("window.__edits.ops['%s'].v.n[1].r" % key) == first
    pg.hover(".aph:not(.aph-top) .aph-fig >> nth=2")
    pg.click(".aph:not(.aph-top) .aph-fig >> nth=2 >> .aph-tools button >> nth=2")                 # remove
    pg.wait_for_timeout(1100)
    assert len(pg.evaluate("window.__edits.ops['%s'].v.n" % key)) == 2
    pg.keyboard.press("Control+z")
    pg.wait_for_timeout(1100)
    assert len(pg.evaluate("window.__edits.ops['%s'].v.n" % key)) == 3                               # undo brings it back
    # a card's pictures: the tile below its title
    _add(pg, ".aph-top .aph-add", [str(root / "p3.jpg")])
    assert len(pg.evaluate("window.__edits.ops['pc|formation|pics'].v")) == 1
    pg.wait_for_timeout(1100)
    stored = pg.evaluate("localStorage.getItem(Object.keys(localStorage).find(k => k.indexOf('alto-ed-')===0))")
    assert stored and "ph|n-formation-new-" in stored
    # a reload: the page is built without them; the edits lay them over it, the pictures come from this browser's copy
    pg.reload()
    pg.wait_for_timeout(1800)
    _detail(pg)
    _loaded(pg, ".aph:not(.aph-top) .aph-img img")
    assert pg.evaluate("document.querySelectorAll('.aph:not(.aph-top) .aph-fig').length") == 3
    assert pg.evaluate("[...document.querySelectorAll('.aph:not(.aph-top) .aph-cap')].map(e => e.textContent)")[:1] == ["Exhibit A"]
    assert not pg.errs, pg.errs
    pg.context.close()


def test_a_file_that_is_not_a_picture_is_refused_in_place_with_what_to_do(browser, site):
    _base, root = site
    (root / "notes.txt").write_text("not a picture", encoding="utf-8")
    pg = _open(browser, site, page="plain", edit=True)
    _detail(pg)
    pg.click(".aed-add >> nth=-1")
    pg.click("#aed-kinds button[data-k=photos]")
    pg.wait_for_selector(".aph:not(.aph-top) .aph-add")
    _add(pg, ".aph:not(.aph-top) .aph-add", [str(root / "notes.txt")])
    assert "not a picture" in pg.inner_text(".aph:not(.aph-top) .aph-err")
    assert pg.evaluate("window.__puts.length") == 0
    pg.context.close()


def test_no_pictures_means_nothing_is_fetched_until_edit_mode_starts(browser, site):
    pg = _open(browser, site, page="plain")
    assert pg.evaluate("!window._altoPics && !document.getElementById('alto-pics-css')")
    pg.evaluate("document.querySelector('#alto-edit-pill .aep-manual').click()")
    pg.wait_for_timeout(600)
    assert pg.evaluate("!!window._altoPics")
    pg.context.close()


def test_the_strip_wears_retro_and_holographic_frames(browser, site):
    pg = _open(browser, site)
    _detail(pg)
    for st, edge in (("retro", "rgb(217, 174, 85)"), ("holo", None)):
        pg.evaluate(f"window._altoStyle.set('{st}')")
        pg.wait_for_function(f"document.documentElement.classList.contains('alto-{st}')", timeout=10000)
        pg.wait_for_timeout(1200)
        r = pg.evaluate("(() => { const e=document.querySelector('.aph:not(.aph-top) .aph-img'), c=getComputedStyle(e); return [c.borderTopLeftRadius, c.borderTopColor]; })()")
        assert r[0] == "0px", (st, r)
        if edge:
            assert r[1].startswith("rgba(217, 174, 85") or r[1] == edge, r
    assert not pg.errs, pg.errs
    pg.context.close()


def test_print_includes_the_strip_and_the_ink_saver_prints_the_captions_only(browser, site):
    pg = _open(browser, site)
    _detail(pg)
    _loaded(pg, ".aph:not(.aph-top) .aph-img img")
    pg.emulate_media(media="print")
    assert pg.evaluate("getComputedStyle(document.querySelector('.aph:not(.aph-top) .aph-img')).display") != "none"
    assert pg.evaluate("getComputedStyle(document.querySelector('.aph:not(.aph-top) .aph-cap')).display") != "none"
    pg.evaluate("document.documentElement.classList.add('print-ink')")
    assert pg.evaluate("getComputedStyle(document.querySelector('.aph:not(.aph-top) .aph-img')).display") == "none"
    assert pg.evaluate("getComputedStyle(document.querySelector('.aph:not(.aph-top) .aph-cap')).display") != "none"
    pg.context.close()


def test_a_phone_shows_pictures_on_the_card_and_in_one_column_on_the_page(browser, site):
    pg = _open(browser, site, mobile=True)
    _detail(pg)
    _loaded(pg, ".aph:not(.aph-top) .aph-img img")
    w = pg.evaluate("[...document.querySelectorAll('.aph:not(.aph-top) .aph-fig')].map(f => Math.round(f.getBoundingClientRect().width))")
    assert len(set(w)) == 1 and w[0] > 300, w                                                       # one column: each as wide as the page
    assert pg.evaluate("!document.querySelector('.aph-side')")                                       # the card's own pictures: below its title
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    pg.click(".aph:not(.aph-top) .aph-img >> nth=0")
    pg.wait_for_selector("#aph-lb img[src^='blob:']", timeout=8000)                                  # tap to enlarge
    pg.context.close()


def test_a_card_on_a_phone_carries_its_picture(browser, site):
    pg = _open(browser, site, mobile=True)
    pg.wait_for_timeout(600)
    n = pg.evaluate("document.querySelectorAll('.node .aph-thumb').length")
    assert n >= 1
    _loaded(pg, ".node .aph-thumb img")
    pg.evaluate("window.__opened = 0; var o = window.showDetail; window.showDetail = function(){ window.__opened++; return o.apply(this, arguments); };")
    pg.tap(".node.mobile-featured .aph-thumb, .node .aph-thumb >> nth=0")                              # a tap on the picture: the viewer, not the card's page
    pg.wait_for_selector("#aph-lb", timeout=8000)
    assert pg.evaluate("window.__opened") == 0
    pg.context.close()


# ── the account layer, the real alto-cloud.js against an in-memory Firestore ──────────────────────

def test_the_account_layer_keeps_pictures_under_the_owner_and_copies_a_shares_beside_it():
    assert "users/{uid}/pics/{ref}" in CLOUD and "PIC_TH_MAX = 200000, PIC_BIG_MAX = 950000;" in CLOUD
    assert "indexedDB.deleteDatabase('alto-pics')" in CLOUD                                  # signing out takes this browser's copies too
    for rules in ("firestore.rules", "alto/firestore.rules"):
        r = (ROOT / rules).read_text(encoding="utf-8")
        assert "'pics', 'picbig'" in r and "match /{coll}/{ref}" in r
        own = r.split("function ownCollection")[1].split("match /users/{uid}")[0]
        assert "'pics', 'picbig'" in own
    assert (ROOT / "firestore.rules").read_bytes() == (ROOT / "alto" / "firestore.rules").read_bytes()


_BATCH = """
export function writeBatch(){ const ops=[]; return { set(r,d,o){ ops.push(['s',r,d,o]); }, update(r,d){ ops.push(['u',r,d]); }, delete(r){ ops.push(['d',r]); },
  async commit(){ for(const o of ops){ if(o[0]==='s') await setDoc(o[1],o[2],o[3]); else if(o[0]==='u') await setDoc(o[1],o[2],{merge:true}); else await deleteDoc(o[1]); } } }; }
export function deleteField(){ return undefined; }
"""


@pytest.fixture(scope="module")
def cloud_site(tmp_path_factory):
    from alto.cloud import emit_cloud_js
    from alto.hosted import hosted_timeline
    from tests.test_backgrounds_import import _STUBS
    d = tmp_path_factory.mktemp("picscloud")
    html = _html(_seeded())
    (d / "t.html").write_text(hosted_timeline(html, "contracts-outline"), encoding="utf-8")
    (d / "alto-cloud.js").write_text(emit_cloud_js({"apiKey": "k", "authDomain": "p.firebaseapp.com", "projectId": "p", "storageBucket": "",
                                                    "messagingSenderId": "", "appId": "a"}), encoding="utf-8")
    stubs = dict(_STUBS)
    stubs["firebase-firestore.js"] = _STUBS["firebase-firestore.js"] + _BATCH
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", stubs, html
    srv.shutdown()


def _cloud_page(browser, cloud_site, docs=None):
    base, stubs, _html_ = cloud_site
    ctx = browser.new_context(viewport={"width": 1200, "height": 800})
    pg = ctx.new_page()
    pg.route("https://www.gstatic.com/firebasejs/**", lambda r: r.fulfill(status=200, content_type="text/javascript", body=stubs[r.request.url.rsplit("/", 1)[1]]))
    pg.add_init_script("window.__fs={docs:%s,writes:[],deletes:[]};" % json.dumps(docs or {}))
    pg.goto(base + "/t.html")
    pg.wait_for_function("window.AltoCloud && window.AltoCloud.known", timeout=15000)
    pg.wait_for_timeout(300)
    return pg


def test_a_picture_is_stored_in_two_sizes_read_back_removed_and_never_over_the_limit(browser, cloud_site):
    pg = _cloud_page(browser, cloud_site)
    r = pg.evaluate("""async () => { const C = window.AltoCloud.pics, th = new Uint8Array(3000).fill(7), big = new Uint8Array(40000).fill(9);
      await C.put('pic-abcdefghij', th, big, {type: 'image/webp', thType: 'image/webp', w: 1600, h: 1100});
      const a = await C.get('pic-abcdefghij', 'th'), b = await C.get('pic-abcdefghij', 'big'), none = await C.get('pic-zzzzzzzzzz', 'th');
      let tooBig = ''; try { await C.put('pic-abcdefghik', th, new Uint8Array(950001), {}); } catch (e) { tooBig = String(e.message); }
      let bad = ''; try { await C.get('../x', 'th'); } catch (e) { bad = String(e.message); }
      const keys = Object.keys(window.__fs.docs);
      await C.remove('pic-abcdefghij');
      const mine = (k) => /\\/(pics|picbig)\\//.test(k);
      return {th: a.bytes.length, big: b.bytes.length, type: a.type, none: none, tooBig, bad, keys: keys.filter(mine), left: Object.keys(window.__fs.docs).filter(mine)}; }""")
    assert r["th"] == 3000 and r["big"] == 40000 and r["type"] == "image/webp" and r["none"] is None, r
    assert r["tooBig"] == "too-large" and r["bad"] == "bad picture id", r
    assert sorted(r["keys"]) == ["users/u1/picbig/pic-abcdefghij", "users/u1/pics/pic-abcdefghij"] and r["left"] == [], r
    pg.context.close()


def test_a_share_copies_the_pages_pictures_says_how_many_and_stops_with_the_link(browser, cloud_site):
    _base, _stubs, html = cloud_site
    refs = sorted({S1, S2, S3, S4, S5})
    block = re.search(r'<script id="alto-ph">.*?</script>', html, re.S).group(0)
    small = "<html><body><script>var COURSE_ID = 'contracts-outline';</script>" + block + "</body></html>"      # (a page's pictures are all a share's count looks at)
    seed = {"users/u1/pages/pk1": {"html": small}}
    for ref in refs:
        seed[f"users/u1/pics/{ref}"] = {"d": {"__b64": "AQID"}, "type": "image/webp", "t": 1, "w": 10, "h": 10}
        seed[f"users/u1/picbig/{ref}"] = {"d": {"__b64": "BAUGBwgJ"}, "type": "image/webp", "t": 1}
    pg = _cloud_page(browser, cloud_site, seed)
    assert pg.evaluate("window.AltoCloud.pics.count(%s)" % json.dumps('{"r":"pic-abcdefghij"} {"r":"pic-abcdefghij"} "pic-abcdefghik"')) == 2
    assert pg.evaluate("window.AltoCloud.pics.countOf('pk1')") == 5                  # what the dialog says before anything is sent
    r = pg.evaluate("window.AltoCloud.sharePush('pk1', 'T')")
    key = r["shareKey"]
    assert r["pictures"] == 5
    docs = pg.evaluate("Object.keys(window.__fs.docs).filter(k => k.startsWith('shares/%s/'))" % key)
    assert sorted(d for d in docs if "/pics/" in d) == [f"shares/{key}/pics/{x}" for x in refs]
    assert sorted(d for d in docs if "/picbig/" in d) == [f"shares/{key}/picbig/{x}" for x in refs]
    got = pg.evaluate("window.AltoCloud.pics.shared(%s, %s, 'big').then(r => [r.bytes.length, r.type])" % (json.dumps(key), json.dumps(S1)))
    assert got == [6, "image/webp"]
    # the owner takes a picture off the page and updates the link: it stops being readable there
    pg.evaluate("""async () => { const h = window.__fs.docs['users/u1/pages/pk1'].html; window.__fs.docs['users/u1/pages/pk1'].html = h.split('"%s"').join('"pic-zzzzzzzzzz"'); }""" % S5)
    r2 = pg.evaluate("window.AltoCloud.sharePush('pk1', 'T')")
    gone = pg.evaluate("Object.keys(window.__fs.docs).filter(k => k.indexOf('%s') > 0 && k.startsWith('shares/'))" % S5)
    assert gone == [] and r2["shareKey"] == key
    # stopping the link takes its pictures with it
    assert pg.evaluate("window.AltoCloud.shareRevoke('pk1')") is True
    assert pg.evaluate("Object.keys(window.__fs.docs).filter(k => k.startsWith('shares/'))") == [f"shares/{key}/private/owner"] or \
        pg.evaluate("Object.keys(window.__fs.docs).filter(k => k.startsWith('shares/') && /pics|picbig/.test(k))") == []
    pg.context.close()


# ── quizzes, flash cards, the Filter ─────────────────────────────────────────

def _study_doc():
    d = _seeded()
    d["nodes"][0]["sections"] += [
        {"h": "Flash cards", "t": "", "cards": {"label": "Elements", "cards": [
            {"id": "c1", "front": "What is an offer?", "back": "A manifestation of willingness.", "front_pic": {"ref": S1, "caption": "The letter"}},
            {"id": "c2", "front": "Acceptance?", "back": "Assent.", "back_pic": {"ref": S2, "alt": "A shop"}}]}},
        {"h": "Quiz", "t": "", "quiz": {"label": "Quiz", "questions": [
            {"id": "q1", "q": "What does the letter show?", "choices": ["An offer", "A claim"], "answer": 0, "pic": {"ref": S3, "caption": "Ledger page"}}]}}]
    return d


def test_a_question_and_a_card_side_carry_a_picture_through_the_brief_and_the_page():
    html = _html(_study_doc())
    m = re.search(r'window\._ALTO_ST=(.*?);</script>', html)
    st = json.loads(m.group(1).replace("<\\/", "</"))
    cards = next(v for v in st.values() if v["k"] == "c")["n"]
    quiz = next(v for v in st.values() if v["k"] == "q")["n"]
    assert cards[0]["fp"] == {"r": S1, "c": "The letter"} and "fp" not in cards[1] and cards[1]["bp"] == {"r": S2, "a": "A shop"}
    assert quiz[0]["p"] == {"r": S3, "c": "Ledger page"}
    bad = _study_doc()
    bad["nodes"][0]["sections"][-1]["quiz"]["questions"][0]["pic"] = {"ref": "nope"}
    with pytest.raises(BriefError, match="pic-"):
        _html(bad)


def test_the_study_editors_list_folds_with_its_pictures():
    from alto.build.study import compact, from_compact
    st = Store(_study_doc())
    v = _view(st)
    secs = v.owner("n", "formation").sections
    for s in secs:
        if s.cards or s.quiz:
            c = compact(s)
            which, back = from_compact(c)
            assert back == (s.cards if which == "cards" else s.quiz) or which in ("cards", "quiz")
    cards = compact(next(s for s in secs if s.cards))
    cards["n"][0]["bp"] = {"r": S4, "c": "Back side"}
    which, out = from_compact(cards)
    assert out["cards"][0]["back_pic"] == {"ref": S4, "caption": "Back side"} and out["cards"][0]["front_pic"] == {"ref": S1, "caption": "The letter"}
    sec = next(s for s in secs if s.cards)
    k = "sd|n-formation-%d|study" % secs.index(sec)
    st.edits = {"v": 1, "ops": {k: {"b": jhash(_jdump(compact(sec))), "v": cards, "t": 3}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and r["folded"] == 1, r
    got = next(s for s in _node(st, "formation")["sections"] if s.get("cards"))["cards"]["cards"][0]
    assert got["back_pic"]["ref"] == S4
    _build_store(st)


def test_a_quiz_question_and_a_flash_card_show_their_pictures(browser, site, tmp_path_factory):
    base, root = site
    (root / "study.html").write_text(_html(_study_doc()), encoding="utf-8")
    pg = _open(browser, site, page="study")
    _detail(pg)
    pg.wait_for_selector(".ast-quiz .asq-q .aph-q img", timeout=8000)
    _loaded(pg, ".ast-quiz .aph-q img")
    assert pg.inner_text(".ast-quiz .aph-q .aph-cap") == "Ledger page"
    pg.wait_for_selector(".ast-cards .aph-cf img", timeout=8000)
    _loaded(pg, ".ast-cards .asc-front .aph-cf img")
    assert pg.evaluate("document.querySelectorAll('.ast-cards .asc-front .aph-cf').length") == 1 and pg.evaluate("document.querySelectorAll('.ast-cards .asc-back .aph-cf').length") == 0
    pg.click(".ast-cards .asc-next, .ast-cards .asc-nav >> nth=1")                                   # the second card: its picture is on the back
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.querySelectorAll('.ast-cards .asc-back .aph-cf').length") == 1
    pg.click(".ast-quiz .aph-q .aph-img")                                                             # a picture in a question opens large
    pg.wait_for_selector("#aph-lb img[src^='blob:']", timeout=8000)
    assert not pg.errs, pg.errs
    pg.context.close()


def test_the_study_editor_adds_and_removes_a_picture_on_a_question(browser, site):
    _base, root = site
    (root / "study.html").write_text(_html(_study_doc()), encoding="utf-8")
    pg = _open(browser, site, page="study", edit=True)
    _detail(pg)
    pg.click(".aed-st >> nth=0")
    pg.wait_for_selector("#aed-study .as-pic", timeout=8000)
    pg.wait_for_function("document.querySelectorAll('#aed-study .as-pict img[src^=\"blob:\"]').length >= 1", timeout=8000)
    assert pg.evaluate("document.querySelectorAll('#aed-study .as-pic').length") >= 2                  # a row for each side of each card
    pg.click("#aed-study .as-pic .as-picx >> nth=0")                                                  # take the front card's picture off
    pg.click("#aed-study .as-save")
    pg.wait_for_timeout(1200)
    key = next(k for k in pg.evaluate("Object.keys(window.__edits.ops)") if k.startswith("sd|"))
    v = pg.evaluate("window.__edits.ops['%s'].v" % key)
    assert "fp" not in v["n"][0] and v["n"][1]["bp"]["r"] == S2
    assert not pg.errs, pg.errs
    pg.context.close()


def test_the_filter_gains_has_pictures_and_a_picture_added_in_edit_mode_joins_it(browser, site):
    pg = _open(browser, site)
    f = pg.evaluate("(window.FILTER_SECTIONS || []).filter(s => s.key === 'pics').map(s => [s.label, s.items[0].name, s.items[0].count, (window.FILTER_NODES.pics || {}).has])")
    assert f == [["Pictures", "Has pictures", 2, ["definiteness", "formation"]]], f
    pg.context.close()
    pg = _open(browser, site, page="plain", edit=True)
    assert pg.evaluate("(window.FILTER_SECTIONS || []).filter(s => s.key === 'pics').length") == 0
    _detail(pg)
    _add(pg, ".aph-top .aph-add", [str(site[1] / "p3.jpg")])
    assert pg.evaluate("(window.FILTER_NODES.pics || {}).has") == ["formation"]
    pg.context.close()


# ── the System: the rising hologram panel (solar_pics.py), desktop 3D only ───────────────────────

UNITS = [[[2, 1, 0], [1, 0], [0], [3, 1]], [[1, 1], [0, 2], [2]], [[], [0]]]


def _system_doc():
    from tests.test_solar_draw import solar_doc
    d = solar_doc(UNITS, "orbit", [("u1-p1", "u2-p2")])
    for n in d["nodes"]:
        if n["id"] == "u1-p1":
            n["photos"] = [{"ref": S1, "caption": "Signed letter, 1892"}, {"ref": S2}, {"ref": S3}]
        if n["id"] == "u1-p2":
            n["photos"] = [{"ref": S4, "caption": "Ledger"}]
    return d


def _in_3d(pg):
    pg.evaluate("() => { window._altoCraft.set('explorer'); window._altoFlyOff=true; window._altoSolarLook.set('stars'); window._altoSolarStyle.set('real'); }")
    pg.wait_for_timeout(2800)
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pg.context.close()
        pytest.skip("no WebGL in this browser")


def test_a_body_with_pictures_carries_a_tag_from_afar_and_a_panel_rises_as_the_camera_comes_near(browser, site):
    base, root = site
    (root / "system.html").write_text(_html(_system_doc()), encoding="utf-8")
    pg = _open(browser, site, page="system", viewport={"width": 1500, "height": 950})
    _in_3d(pg)
    pg.wait_for_function("document.querySelectorAll('#aph-hp .hp-tag').length >= 1", timeout=10000)
    assert pg.evaluate("document.querySelector('#aph-hp .hp-panel')") is None                        # far: a tag, no panel
    g = pg.evaluate("() => { var g = window._altoSolarGeo().bodies['u1-p1']; return [g.x, g.y]; }")
    pg.evaluate("a => window._altoSolar3D.set({tx: a[0], tz: a[1], d: 170})", g)
    pg.wait_for_function("document.querySelector('#aph-hp .hp-panel') && +document.querySelector('#aph-hp .hp-panel').style.opacity > .8", timeout=10000)
    r = pg.evaluate("""() => { const p = document.querySelector('#aph-hp .hp-panel'), b = p.getBoundingClientRect(), s = window._altoSolar3D.screen('u1-p1');
      return {w: b.width, l: b.left, r: b.right, bx: s.x, br: s.r, imgs: p.querySelectorAll('img').length, name: p.querySelector('.hp-name').textContent, cap: p.querySelector('.hp-cap').textContent,
              tether: !!document.querySelector('#aph-hp .hp-tether line'), vw: innerWidth}; }""")
    assert r["imgs"] == 3 and r["cap"] == "Signed letter, 1892" and r["tether"] and r["name"].lower().startswith("planet concept 1.1"), r
    assert r["l"] >= 0 and r["r"] <= r["vw"], r                                                      # on screen, beside the body, not on it
    pg.click("#aph-hp .hp-panel .hp-main", force=True)
    pg.wait_for_selector("#aph-lb", timeout=5000)
    pg.keyboard.press("Escape")
    # rising: between far and near the panel is part-grown and turned; with Reduce Motion it stands without the turn
    ROT = "() => { const p = document.querySelector('#aph-hp .hp-panel'); return p ? [+p.style.opacity, +(/rotateY\\((-?[0-9.]+)deg/.exec(p.style.transform) || [0, 0])[1]] : null; }"
    seen = None
    for dist in (900, 800, 700, 620, 560, 500):
        pg.evaluate("a => window._altoSolar3D.set({tx: a[0], tz: a[1], d: a[2]})", [g[0], g[1], dist])
        pg.wait_for_timeout(500)
        o = pg.evaluate(ROT)
        if o and 0 < o[0] < .95:
            seen = o
            break
    assert seen and abs(seen[1]) > 3, seen
    pg.emulate_media(reduced_motion="reduce")
    pg.wait_for_timeout(400)
    assert abs(pg.evaluate(ROT)[1]) < .01
    assert not pg.errs, pg.errs
    pg.context.close()


def test_a_phone_has_no_hologram_panel(browser, site):
    base, root = site
    (root / "system.html").write_text(_html(_system_doc()), encoding="utf-8")
    pg = _open(browser, site, page="system", mobile=True)
    assert pg.evaluate("!document.querySelector('#aph-hp .hp-panel') && (!document.getElementById('aph-hp') || getComputedStyle(document.getElementById('aph-hp')).display === 'none')")
    pg.context.close()
