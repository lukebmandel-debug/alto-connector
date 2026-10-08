"""Backgrounds: a choice of photographs behind a timeline and behind the homepage
(alto/build/backgrounds.py). A choice is per timeline, kept in the browser and,
for the account that owns the timeline, in its Firestore record; the homepage and
the reports page share one of their own. Nothing is baked into a page, and a page
whose owner never chooses is the page it always was. The browser parts are skipped
when Playwright is not installed."""
import http.server
import json
import re
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import backgrounds as bg                       # noqa: E402
from alto.build.backgrounds_catalog import COLOURS, PATTERNS, SCENES   # noqa: E402
from alto.build.blocks import ID_PATTERNS                      # noqa: E402
from alto.build.builder import build_timeline, load_brief      # noqa: E402
from alto.build.pages import build_home, build_reports         # noqa: E402

ASSETS = ROOT / "alto" / "assets" / "backgrounds"
OUTLINE = ROOT / "samples" / "outline_brief.json"


@pytest.fixture(scope="module")
def timeline():
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)[0], brief.timeline_id


# ── the photographs ─────────────────────────────────────────────────────────

def _variants():
    for sc in SCENES:
        for m in ("l", "d"):
            yield sc["id"], m, sc[m]


def test_a_combination_of_space_nature_and_city_each_with_a_light_and_a_dark_picture():
    groups = {}
    for sc in SCENES:
        groups.setdefault(sc["group"], []).append(sc["id"])
        assert set(sc) >= {"l", "d"}, sc["id"]
    assert set(groups) == {"Space", "Nature", "City"}
    assert all(len(v) >= 5 for v in groups.values()), groups


def test_every_photo_is_on_disk_and_light_enough():
    for sid, m, v in _variants():
        full, thumb = ASSETS / f"{sid}-{m}.jpg", ASSETS / "t" / f"{sid}-{m}.jpg"
        assert full.is_file() and thumb.is_file(), (sid, m)
        assert full.stat().st_size <= 470 * 1024, f"{sid}-{m} is {full.stat().st_size} bytes"
        assert thumb.stat().st_size <= 40 * 1024, (sid, m)
        assert full.read_bytes()[:3] == b"\xff\xd8\xff"            # a JPEG
    want = {f"{sid}-{m}" for sid, m, _ in _variants()}
    assert {f.stem for f in ASSETS.glob("*.jpg")} == want, "a file with no catalogue entry, or an entry with no file"


def test_the_light_pictures_are_bright_and_the_dark_ones_are_dim_enough():
    """The point of two pictures: the light theme gets a bright photograph and the dark theme a dim one."""
    for sid, m, v in _variants():
        if m == "l":
            assert v["L50"] >= 0.40 and v["L10"] >= 0.05, (sid, v["L10"], v["L50"])
        else:
            assert v["L50"] <= 0.52, (sid, v["L50"])


def test_only_licences_that_allow_this_use_and_every_photo_is_credited():
    for sid, m, v in _variants():
        assert re.fullmatch(r"Public domain|CC0|CC BY \d\.\d", v["lic"]), (sid, m, v["lic"])
        assert v["by"].strip() and v["name"].strip()
        assert v["url"].startswith("https://commons.wikimedia.org/wiki/File:"), (sid, m)
        assert 0 < v["fx"] < 1 and 0 < v["fy"] < 1
    ids = [sc["id"] for sc in SCENES]
    assert len(set(ids)) == len(ids) and all(re.fullmatch(r"[a-z][a-z0-9-]{1,40}", i) for i in ids)


def test_the_veil_and_lift_keep_the_engines_contrast_assumptions():
    """Light mode wants a pale ground and dark mode a deep one whatever the photo."""
    lum = lambda hx: sum(int(hx[i:i + 2], 16) * w for i, w in ((1, .2126), (3, .7152), (5, .0722))) / 255
    for sid, m, v in _variants():
        t = bg.tune(v, m)
        if m == "l":
            assert 0.10 <= t["v"] <= 0.70 and 1.0 <= t["b"] <= 2.0, (sid, t)
            assert lum(t["q"]) > 0.45, (sid, t["q"])
        else:
            assert 0.20 <= t["v"] <= 0.70 and 0.55 <= t["b"] <= 1.0, (sid, t)
            assert lum(t["q"]) < 0.40, (sid, t["q"])
        for k in ("q", "s", "a"):
            assert re.fullmatch(r"#[0-9a-f]{6}", t[k]), (sid, k)


def test_colours_and_patterns_are_pale_in_light_and_deep_in_dark():
    lum = lambda hx: sum(int(hx[i:i + 2], 16) * w for i, w in ((1, .2126), (3, .7152), (5, .0722))) / 255
    assert len(COLOURS) >= 10 and len(PATTERNS) >= 6
    for c in COLOURS + PATTERNS:
        assert re.fullmatch(r"[cp]-[a-z]+", c["id"]) and c["name"].strip()
        assert all(lum(h) > 0.70 for h in c["l"][:2]), (c["id"], c["l"])
        assert all(lum(h) < 0.30 for h in c["d"][:2]), (c["id"], c["d"])
    for c in PATTERNS:
        assert c["kind"] in ("dots", "grid", "lines", "waves", "hex", "chevron", "diamond", "paper")
        assert 0 < c["l"][3] < 0.5 and 0 < c["d"][3] < 0.5
    ids = [c["id"] for c in COLOURS + PATTERNS] + [sc["id"] for sc in SCENES]
    assert len(set(ids)) == len(ids)


def test_the_client_catalogue_has_everything_a_page_needs():
    C = bg.client_catalog()
    assert len(C) == len(SCENES) + len(COLOURS) + len(PATTERNS)
    for sc in SCENES:
        e = C[sc["id"]]
        assert e["k"] == "p" and e["g"] == sc["group"]
        for m in ("l", "d"):
            assert e[m]["f"] == f"{sc['id']}-{m}.jpg" and 0 < e[m]["x"] < 1 and 0 < e[m]["y"] < 1
    assert C["c-ocean"]["k"] == "c" and C["p-dots"]["k"] == "x" and C["p-dots"]["p"] == "dots"
    assert "</" not in bg.catalog_json()


# ── what a page carries ─────────────────────────────────────────────────────

def test_a_timeline_applies_its_choice_before_first_paint_and_carries_the_picker(timeline):
    html, tid = timeline
    key = ID_PATTERNS["hl_key"].format(tid=tid) + "-bg"
    assert html.count('<script id="alto-bg-head">') == 1 and html.count('id="alto-bg-ui"') == 1
    head = html[:html.index("</head>")]
    assert 'id="alto-bg-head"' in head and f'KEY = "{key}"' in head.replace("KEY=", "KEY = ") or json.dumps(key) in head
    # ahead of the tag the mobile runway is appended to, so that patch stays in one piece
    assert head.index('id="alto-bg-head"') < head.index('<meta name="theme-color"')
    assert 'id="bg-toggle"' not in html.split('id="alto-bg-ui"')[0]      # drawn by script, not baked
    assert "html.alto-bg #page-bg::before" in html


def test_every_rule_of_the_photo_css_is_inert_without_the_class():
    css = re.sub(r"/\*.*?\*/", "", bg.CSS, flags=re.S)
    sel = [s.strip() for blk in re.findall(r"([^{}]+)\{", css) for s in blk.split(",")]
    sel = [s for s in sel if s]
    assert sel and all(re.match(r"html\.(printing\.)?alto-bg", s) for s in sel), \
        [s for s in sel if not re.match(r"html\.(printing\.)?alto-bg", s)]


def test_a_share_keeps_its_own_choice_apart_from_the_masters(timeline):
    from alto.build.reidentify import reidentify
    html, tid = timeline
    shared = reidentify(html, "abc123")
    assert f"alto-hl-{tid}-bg" not in shared and "alto-hl-s-abc123-bg" in shared


def test_the_homepage_and_reports_share_one_choice_of_their_own():
    for page in (build_home([]), build_reports([], "")):
        assert page.count('id="alto-bg-head"') == 1 and page.count('id="alto-bg-ui"') == 1
        assert '"alto-bg-home-v1"' in page
        assert "#bg-toggle" in page.split("alto-runway")[1][:2500], "the phone runway must treat the tab as fixed chrome"


def test_the_mobile_runway_treats_the_tab_and_the_picker_as_fixed_chrome(timeline):
    html, _ = timeline
    run = html[html.index('id="alto-runway"'):]
    run = run[:run.index("</style>")]
    assert "#bg-panel, #bg-toggle" in run
    assert "#ef-panel, #bg-panel, #account-scrim" in run
    assert "#bg-panel > .bg-head" in run


def test_a_choice_on_a_page_with_no_web_address_changes_nothing():
    """A copy downloaded for offline use opens from a file: it cannot reach the
    photographs, so it keeps the Alto wallpaper."""
    assert "function web(){ return /^https?:/i.test(document.baseURI || location.href); }" in bg.HEAD_JS
    assert "if(!c || !web()){" in bg.HEAD_JS


def test_a_page_nobody_chose_for_writes_nothing_and_leaves_the_status_bar_alone():
    js = bg.HEAD_JS
    assert "if(!c && !(k in m)) return;" in js            # no gate memory written
    assert "if(!c && !touched) return;" in js             # theme-color untouched


def test_the_gate_opens_on_the_photographs_colour():
    from alto.build.private_shell import shell
    s = shell("v1", "s1")
    assert "alto-bgq-v1" in s and "'pv/' + KEY" in s
    assert "root.style.background = ''" in s


def test_the_page_stamp_changes_with_the_catalogue():
    from alto.build.fingerprint import _TIMELINE_SOURCES
    assert "backgrounds.py" in _TIMELINE_SOURCES and "backgrounds_catalog.py" in _TIMELINE_SOURCES


# ── the site ────────────────────────────────────────────────────────────────

def test_a_deploy_carries_the_photographs_and_lets_browsers_keep_them(tmp_path):
    from alto import publish_static as ps
    heads = ps._headers("csp", "ccsp")
    rule = next(h for h in heads if h["source"] == "/bg/**")
    assert {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"} in rule["headers"]
    assert heads.index(rule) > 0 and heads[0]["source"] == "**"      # after the no-cache default, so it wins
    assert (ASSETS / "t").is_dir() and bg.BG_BASE == f"/bg/v{bg.BG_V}/"


def test_the_photographs_travel_with_every_install():
    toml = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    mcpb = (ROOT / "packaging" / "build_mcpb.py").read_text(encoding="utf-8")
    assert '"assets/backgrounds/*.jpg"' in toml and '"assets/backgrounds/t/*.jpg"' in toml
    assert '("alto/assets/backgrounds", "*.jpg")' in mcpb and '("alto/assets/backgrounds/t", "*.jpg")' in mcpb


# ── sync (alto-cloud.js) ────────────────────────────────────────────────────

def test_the_account_carries_the_choices_and_the_newest_wins():
    js = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
    assert "const HBG_KEY = 'alto-bg-home-v1';" in js
    assert "BG_KEY = `alto-hl-${tid}-bg`;" in js                      # a late setTid() names it too
    assert "k === HBG_KEY || (BG_KEY && k === BG_KEY)" in js          # a pick triggers a sync
    assert js.count("window.dispatchEvent(new Event('alto-bg'))") == 2


# ── in a browser ────────────────────────────────────────────────────────────

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None
needs_browser = pytest.mark.skipif(pw is None, reason="Playwright is not installed")


@pytest.fixture(params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            try:                                    # no bundled Chromium: the installed Chrome will do
                if request.param != "chromium":
                    raise e
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


_SITES = {}


def site_dir_of(base):
    return _SITES[base]


@pytest.fixture(scope="module")
def site(timeline, tmp_path_factory):
    """A tiny site over http (a file: page keeps the default on purpose)."""
    d = tmp_path_factory.mktemp("site")
    (d / "t.html").write_text(timeline[0], encoding="utf-8")
    (d / "home.html").write_text(build_home([]), encoding="utf-8")
    import shutil
    shutil.copytree(ASSETS, d / "bg" / f"v{bg.BG_V}")
    # the sync layer, with a Firebase project spliced in (the SDK itself is stubbed per test)
    from alto.cloud import emit_cloud_js
    (d / "alto-cloud.js").write_text(emit_cloud_js({
        "apiKey": "k", "authDomain": "p.firebaseapp.com", "projectId": "p", "storageBucket": "",
        "messagingSenderId": "", "appId": "a"}), encoding="utf-8")
    (d / "sync.html").write_text('<!doctype html><html><head><meta charset="utf-8"></head><body>'
                                 '<script type="module" src="/alto-cloud.js" data-tid="civ"></script></body></html>',
                                 encoding="utf-8")
    (d / "sync-home.html").write_text('<!doctype html><html><head><meta charset="utf-8"></head><body>'
                                      '<script type="module" src="/alto-cloud.js"></script></body></html>',
                                      encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    srv = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _SITES[f"http://127.0.0.1:{srv.server_address[1]}"] = str(d)
    yield f"http://127.0.0.1:{srv.server_address[1]}", timeline[1]
    srv.shutdown()


STATE = """()=>({on:document.documentElement.classList.contains('alto-bg'), id:window._altoBgId,
  img:getComputedStyle(document.documentElement).getPropertyValue('--alto-bg').trim(),
  meta:(document.getElementById('meta-theme')||{}).content})"""


@needs_browser
def test_choosing_a_photograph_sticks_follows_the_theme_and_can_be_undone(browser, site):
    base, tid = site
    pg = browser.new_page(viewport={"width": 1500, "height": 900})
    pg.goto(base + "/t.html"); pg.wait_for_timeout(2500)
    start = pg.evaluate(STATE)
    assert not start["on"] and start["id"] == ""
    assert pg.evaluate("[...document.querySelectorAll('#tab-rail > *')].map(e=>e.id).pop()") == "bg-toggle"
    pg.click("#bg-toggle"); pg.wait_for_timeout(400)
    assert pg.evaluate("document.getElementById('bg-panel').classList.contains('open')")
    assert pg.evaluate("document.querySelectorAll('.bg-tile').length") == len(SCENES) + len(COLOURS) + 1 + len(PATTERNS) + 1
    pg.click('.bg-tile[data-bg="aurora-lofoten"]'); pg.wait_for_timeout(500)
    s = pg.evaluate(STATE)
    assert s["on"] and s["id"] == "aurora-lofoten" and "/bg/v2/aurora-lofoten-l.jpg" in s["img"]
    assert json.loads(pg.evaluate(f"localStorage.getItem('alto-hl-{tid}-bg')"))["v"] == "aurora-lofoten"
    assert "Jules Henze" in pg.evaluate("document.querySelector('.bg-foot').textContent")      # the light picture's
    # the photograph itself loads
    assert pg.evaluate("new Promise(r=>{const i=new Image();i.onload=()=>r(i.naturalWidth);i.onerror=()=>r(0);i.src='/bg/v2/aurora-lofoten-l.jpg'})") > 1000
    # it survives a reload, and the status bar follows the theme
    pg.reload(); pg.wait_for_timeout(2500)
    assert pg.evaluate(STATE)["id"] == "aurora-lofoten"
    light = pg.evaluate(STATE)["meta"]
    pg.click("#mode-toggle"); pg.wait_for_timeout(600)
    dark = pg.evaluate(STATE)
    assert light != dark["meta"] and re.fullmatch(r"#[0-9a-f]{6}", dark["meta"])
    # the same choice, the other theme's picture
    assert "/bg/v2/aurora-lofoten-d.jpg" in dark["img"] and "Johannes Groll" in pg.evaluate("document.querySelector('.bg-foot').textContent")
    # back to the Alto wallpaper: nothing of the choice is left on the page
    pg.click("#bg-toggle"); pg.wait_for_timeout(300)
    pg.click(".bg-tile.bg-def"); pg.wait_for_timeout(500)
    s = pg.evaluate(STATE)
    assert not s["on"] and s["id"] == "" and s["img"] == "" and s["meta"] == "#6b4326"
    assert not re.search(r"--alto-(bg|top|q|veil|bright|blur|t|mask)\b", pg.evaluate("document.documentElement.style.cssText"))
    pg.close()


@needs_browser
def test_colours_patterns_and_a_colour_of_your_own_can_be_chosen_and_follow_the_theme(browser, site):
    base, tid = site
    pg = browser.new_page(viewport={"width": 1500, "height": 900})
    pg.goto(base + "/t.html"); pg.wait_for_timeout(2500)
    bgval = lambda: pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--alto-bg').trim()")
    for cid, kind in (("c-ocean", "linear-gradient"), ("p-dots", "radial-gradient"), ("p-waves", "data:image/svg+xml"),
                      ("p-paper", "feTurbulence"), ("p-hex", "data:image/svg+xml")):
        pg.evaluate("id=>window._altoBg.choose(id)", cid); pg.wait_for_timeout(200)
        v = bgval()
        assert pg.evaluate(STATE)["on"] and (kind in v or kind in __import__("urllib.parse").parse.unquote(v)), (cid, v[:120])
        assert pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--alto-blur').trim()") == "0px"
    # the same pattern, the other theme's ground
    pg.evaluate("window._altoBg.choose('c-sunrise')")
    light = bgval()
    pg.evaluate("document.documentElement.classList.add('dark')"); pg.wait_for_timeout(200)
    dark = bgval()
    assert light != dark and "#6a2f17" in dark and "#fde4d4" in light
    # a colour of the user's own: pale in light, deep in dark; anything else is ignored
    pg.evaluate("window._altoBg.choose('c:d94a6b')"); pg.wait_for_timeout(200)
    assert pg.evaluate(STATE)["on"] and pg.evaluate(STATE)["id"] == "c:d94a6b"
    dk = bgval()
    pg.evaluate("document.documentElement.classList.remove('dark')"); pg.wait_for_timeout(200)
    lt = bgval()
    lum = lambda hx: sum(int(hx[i:i + 2], 16) * w for i, w in ((1, .2126), (3, .7152), (5, .0722))) / 255
    first = lambda v: re.search(r"#[0-9a-f]{6}", v).group(0)
    assert lum(first(lt)) > 0.7 and lum(first(dk)) < 0.3, (lt, dk)
    for bad in ("c:zzzzzz", "c:d94a6b;}body{display:none", "c:12345", "url(javascript:1)", "tokyo-tower-x"):
        pg.evaluate("id=>window._altoBg.apply(id)", bad); pg.wait_for_timeout(100)
        assert not pg.evaluate(STATE)["on"], bad
    # and the picker offers them
    pg.click("#bg-toggle"); pg.wait_for_timeout(300)
    assert pg.evaluate("[...document.querySelectorAll('#bg-panel .bg-h')].map(e=>e.textContent)") == ["Colors", "Patterns", "Space", "Nature", "City"]
    assert pg.evaluate("!!document.querySelector('#bg-panel input[type=color]')")
    pg.evaluate("(()=>{const i=document.querySelector('#bg-panel input[type=color]'); i.value='#3366cc'; i.dispatchEvent(new Event('input',{bubbles:true}))})()")
    pg.wait_for_timeout(300)
    assert pg.evaluate(STATE)["id"] == "c:3366cc" and pg.evaluate("document.querySelector('.bg-custom').classList.contains('active')")
    pg.close()


@needs_browser
def test_the_picker_shows_the_pictures_of_the_theme_in_use(browser, site):
    base, _ = site
    pg = browser.new_page(viewport={"width": 1500, "height": 900})
    pg.goto(base + "/t.html"); pg.wait_for_timeout(2500)
    pg.click("#bg-toggle"); pg.wait_for_timeout(300)
    src = lambda: pg.evaluate("document.querySelector('.bg-tile[data-bg=\"tokyo-tower\"] img').getAttribute('src')")
    name = lambda: pg.evaluate("document.querySelector('.bg-tile[data-bg=\"tokyo-tower\"] .bg-name').textContent")
    assert src().endswith("/t/tokyo-tower-l.jpg")
    pg.evaluate("document.documentElement.classList.add('dark')"); pg.wait_for_timeout(300)
    assert src().endswith("/t/tokyo-tower-d.jpg")
    assert name() == next(sc for sc in SCENES if sc["id"] == "tokyo-tower")["d"]["name"]
    pg.close()


@needs_browser
def test_a_photographs_subject_lands_clear_of_the_top_bars_whatever_the_window(browser, site):
    """The photograph starts below the title bar and the unit bar, and is placed so what it is a
    picture OF (the catalogue's x/y) lands in the open area, in both themes and at every size."""
    base, _ = site
    for w, h in ((1500, 900), (1180, 720), (1920, 1080)):
        pg = browser.new_page(viewport={"width": w, "height": h})
        pg.goto(base + "/t.html"); pg.wait_for_timeout(2500)
        probe = """(args)=>{ const [id]=args, B=window._altoBg, root=document.documentElement; B.choose(id);
          const st=getComputedStyle(root), m=/ ([-\\d.]+)px ([-\\d.]+)px \\/ ([\\d.]+)px ([\\d.]+)px/.exec(st.getPropertyValue('--alto-bg'));
          const c=B.get(id), v=B.dark()?c.d:c.l, pb=document.getElementById('page-bg'), q=pb.getBoundingClientRect(), z=q.height/pb.clientHeight;
          const T=parseFloat(st.getPropertyValue('--alto-t'));
          const bars=Math.max(...['title-bar','nav'].map(i=>{const e=document.getElementById(i);return e?e.getBoundingClientRect().bottom:0}));
          const oy=parseFloat(m[2]), ih=parseFloat(m[4]), iw=parseFloat(m[3]), ox=parseFloat(m[1]);
          const subjY=((T-40)+oy+v.y*ih)*z+q.top, subjX=(-40+ox+v.x*iw)*z+q.left;
          return {T:T*z+q.top, bars, subjY, subjX, h:innerHeight, w:innerWidth, covers: ox<=0 && oy<=0 && (ox+iw)>=pb.clientWidth+80-1 && (oy+ih)>=(pb.clientHeight-T+80)-1}; }"""
        for dark in (False, True):
            pg.evaluate("document.documentElement.classList.toggle('dark', %s)" % ("true" if dark else "false")); pg.wait_for_timeout(150)
            for sc in SCENES:
                r = pg.evaluate(probe, [sc["id"]])
                assert r["T"] >= r["bars"] - 1.5, (sc["id"], dark, w, r)                  # starts below the bars
                assert r["bars"] < r["subjY"] < r["h"], (sc["id"], dark, w, r)            # the subject is in the open area
                assert 0 < r["subjX"] < r["w"], (sc["id"], dark, w, r)
                assert r["covers"], (sc["id"], dark, w, r)                               # and the picture still fills it
        pg.close()


@needs_browser
def test_a_detail_page_shows_the_photograph_in_full_and_an_enlarged_card_leaves_no_bare_strip(browser, site):
    """The detail page used to be dark/pale glass with a 50px blur over the wallpaper (a smudge of the
    photograph), and enlarging the first card panned the board down while the unit-colour slab only
    held still sideways: a darker strip of bare photograph opened under the bars."""
    base, _ = site
    pg = browser.new_page(viewport={"width": 1180, "height": 720})
    pg.goto(base + "/t.html"); pg.wait_for_timeout(2500)
    pg.evaluate("window._altoBg.choose('aurora-lofoten')"); pg.wait_for_timeout(600)
    first = "(()=>{const n=document.querySelector('#world .node'); return n.id.replace(/^node-/,'')})()"
    for dark in (False, True):
        pg.evaluate("document.documentElement.classList.toggle('dark', %s)" % ("true" if dark else "false")); pg.wait_for_timeout(300)
        # an enlarged first card: the slab still reaches up to the bars
        pg.evaluate("id=>enterFocus(id)", pg.evaluate(first)); pg.wait_for_timeout(1800)
        r = pg.evaluate("""()=>{const g=document.getElementById('glass-slab').getBoundingClientRect(),
          nav=document.getElementById('nav').getBoundingClientRect(), w=document.getElementById('world');
          return {slab:g.top, nav:nav.bottom, pan:getComputedStyle(w).translate}}""")
        assert r["slab"] <= r["nav"] + 3 and r["pan"] != "0px 0px", (dark, r)      # (the board is panned; the slab did not follow)
        pg.evaluate("exitFocus()"); pg.wait_for_timeout(900)
        # the detail page is the photograph, with no tint or frost of its own
        pg.evaluate("(()=>{const n=document.querySelector('#world .node'); (n.querySelector('.node-card')||n).click()})()"); pg.wait_for_timeout(900)
        d = pg.evaluate("""()=>{const e=document.getElementById('detail-page'), c=getComputedStyle(e);
          return {open:document.documentElement.classList.contains('detail-open'), bg:c.backgroundColor, bgi:c.backgroundImage,
                  bf:c.backdropFilter||c.webkitBackdropFilter||'none'}}""")
        assert d["open"] and d["bg"] in ("rgba(0, 0, 0, 0)", "transparent") and d["bgi"] == "none" and d["bf"] == "none", (dark, d)
        pg.evaluate("document.documentElement.classList.contains('detail-open') && (window.closeDetail ? closeDetail() : document.querySelector('#back-to-overview-bar, .detail-back, #detail-back')?.click())")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
    pg.close()


def test_the_top_bar_hover_lines_are_as_fine_as_the_toggles():
    """A toggle's hover line is one drawn pixel; the clef/wordmark/name lines hug a shape that is itself
    only a stroke or two wide, so any more than a hair read as a bold outline."""
    from alto.build import hover_lines
    assert hover_lines.LINE <= 0.5 and hover_lines.TLINE <= 0.3


@needs_browser
def test_each_timeline_and_the_homepage_choose_separately(browser, site):
    base, tid = site
    pg = browser.new_page(viewport={"width": 1500, "height": 900})
    pg.goto(base + "/t.html"); pg.wait_for_timeout(2000)
    pg.evaluate("window._altoBg.choose('tokyo-tower')")
    pg.goto(base + "/home.html"); pg.wait_for_timeout(2000)
    assert pg.evaluate(STATE)["id"] == ""                         # the homepage is not that timeline
    pg.evaluate("window._altoBg.choose('moraine-lake')")
    assert pg.evaluate("localStorage.getItem('alto-bg-home-v1')").count("moraine-lake") == 1
    pg.goto(base + "/t.html"); pg.wait_for_timeout(2000)
    assert pg.evaluate(STATE)["id"] == "tokyo-tower"
    pg.close()


@needs_browser
def test_a_page_opened_from_a_file_keeps_the_alto_wallpaper(browser, timeline, tmp_path):
    f = tmp_path / "offline.html"
    f.write_text(timeline[0], encoding="utf-8")
    pg = browser.new_page()
    pg.add_init_script("localStorage.setItem('alto-hl-%s-bg', JSON.stringify({v:'tokyo-tower',t:1}))" % timeline[1])
    pg.goto(f.as_uri()); pg.wait_for_timeout(1500)
    assert not pg.evaluate(STATE)["on"]
    pg.close()


@needs_browser
def test_a_phone_gets_a_tile_and_a_sheet(browser, site):
    base, _ = site
    if browser.browser_type.name != "webkit":
        pytest.skip("phone emulation is checked in WebKit")
    ctx = browser.new_context(
        viewport={"width": 390, "height": 664}, device_scale_factor=3, is_mobile=True, has_touch=True,
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                   "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
    pg = ctx.new_page()
    pg.goto(base + "/t.html"); pg.wait_for_timeout(3000)
    r = pg.evaluate("(()=>{const r=document.getElementById('bg-toggle').getBoundingClientRect();return [r.left,r.top]})()")
    info = pg.evaluate("document.getElementById('tutorial-toggle').getBoundingClientRect().top")
    assert r[0] == 0 and r[1] < info, (r, info)               # above INFO, on the left edge
    pg.tap("#bg-toggle"); pg.wait_for_timeout(600)
    assert pg.evaluate("document.getElementById('bg-panel').classList.contains('open')")
    pg.tap('.bg-tile[data-bg="paris-dusk"]'); pg.wait_for_timeout(400)
    pg.tap("#bg-close"); pg.wait_for_timeout(500)
    s = pg.evaluate(STATE)
    assert s["on"] and s["id"] == "paris-dusk"
    assert not pg.evaluate("document.getElementById('bg-panel').classList.contains('open')")
    ctx.close()


# A stand-in for the Firebase SDK, so alto-cloud.js runs for real against an in-memory Firestore.
_STUBS = {
    "firebase-app.js": "export function initializeApp(c){ return {c}; }",
    "firebase-auth.js": """
export function getAuth(){ return {}; }
export class GoogleAuthProvider {}
export async function signInWithPopup(){} export async function signInWithRedirect(){}
export async function getRedirectResult(){ return null; } export async function signOut(){}
export const browserLocalPersistence = {}; export async function setPersistence(){}
export function onAuthStateChanged(a, cb){ setTimeout(()=>cb({uid:'u1',displayName:'T',email:'t@example.com',photoURL:''}),0); return ()=>{}; }
""",
    "firebase-firestore.js": """
const fs = window.__fs; const ls = [];
const snap = (ref) => { const d = fs.docs[ref.path]; return {exists:()=>!!d, data:()=>d?JSON.parse(JSON.stringify(d)):undefined, id:ref.id, ref, metadata:{hasPendingWrites:false}}; };
const kids = (c) => Object.keys(fs.docs).filter(k=>k.startsWith(c.path+'/') && k.split('/').length===c.path.split('/').length+1);
const fire = (L) => { if(L.ref.kind==='col'){ const ks=kids(L.ref); L.cb({metadata:{hasPendingWrites:false}, forEach:f=>ks.forEach(k=>f({id:k.split('/').pop(), data:()=>fs.docs[k], ref:{path:k}}))}); } else L.cb(snap(L.ref)); };
const notify = (path) => ls.forEach(L=>{ if((L.ref.kind==='doc'&&L.ref.path===path)||(L.ref.kind==='col'&&path.startsWith(L.ref.path+'/'))) setTimeout(()=>fire(L),0); });
export function getFirestore(){ return {}; }
export function doc(db, ...s){ return {path:s.join('/'), id:s[s.length-1], kind:'doc'}; }
export function collection(db, ...s){ return {path:s.join('/'), kind:'col'}; }
export async function getDoc(ref){ return snap(ref); }
export async function getDocs(c){ const ks=kids(c); return {docs:ks.map(k=>({id:k.split('/').pop(), data:()=>fs.docs[k], ref:{path:k}}))}; }
export async function setDoc(ref, data, o){ const cur=fs.docs[ref.path]||{}; fs.docs[ref.path] = (o&&o.merge) ? Object.assign({},cur,data) : Object.assign({},data); fs.writes.push([ref.path, JSON.parse(JSON.stringify(data))]); notify(ref.path); }
export async function deleteDoc(ref){ delete fs.docs[ref.path]; notify(ref.path); }
export function onSnapshot(ref, cb){ const L={ref,cb}; ls.push(L); setTimeout(()=>fire(L),0); return ()=>{ const i=ls.indexOf(L); if(i>=0) ls.splice(i,1); }; }
export function serverTimestamp(){ return Date.now(); }
export class Bytes { static fromUint8Array(a){ const b=new Bytes(); b.a=a; return b; } toUint8Array(){ return this.a; } }
""",
}


def _sync_page(browser, base, page, docs=None, local=None):
    pg = browser.new_page()
    pg.route("https://www.gstatic.com/firebasejs/**",
             lambda r: r.fulfill(status=200, content_type="text/javascript",
                                 body=_STUBS[r.request.url.rsplit("/", 1)[1]]))
    pg.add_init_script("window.__fs={docs:%s,writes:[]};" % json.dumps(docs or {}))
    pg.add_init_script("window.__bgev=0; addEventListener('alto-bg',()=>{window.__bgev++});")
    for k, v in (local or {}).items():
        pg.add_init_script("try{localStorage.getItem(%r)===null&&localStorage.setItem(%r,%r)}catch(e){}" % (k, k, v))
    pg.goto(base + "/" + page); pg.wait_for_timeout(2500)
    return pg


@needs_browser
def test_a_timelines_choice_reaches_the_account_and_the_newest_choice_wins(browser, site):
    base, _ = site
    key = "alto-hl-civ-bg"
    tl = "users/u1/tl/civ"
    # a choice made here goes up (and a '' — the Alto wallpaper — is a choice too)
    pg = _sync_page(browser, base, "sync.html", local={key: json.dumps({"v": "tokyo-tower", "t": 100})})
    assert pg.evaluate(f"window.__fs.docs['{tl}']")["bg"] == "tokyo-tower"
    assert pg.evaluate(f"window.__fs.docs['{tl}']")["bgAt"] == 100
    pg.close()
    pg = _sync_page(browser, base, "sync.html", docs={tl: {"bg": "paris-dusk", "bgAt": 50}},
                    local={key: json.dumps({"v": "", "t": 300})})
    d = pg.evaluate(f"window.__fs.docs['{tl}']")
    assert d["bg"] == "" and d["bgAt"] == 300
    pg.close()
    # a newer choice made on another device comes down, and the page is told
    pg = _sync_page(browser, base, "sync.html", docs={tl: {"bg": "yosemite", "bgAt": 500}},
                    local={key: json.dumps({"v": "tokyo-tower", "t": 100})})
    assert json.loads(pg.evaluate(f"localStorage.getItem('{key}')")) == {"v": "yosemite", "t": 500}
    assert pg.evaluate("window.__bgev") >= 1
    pg.close()
    # nobody chose anywhere: no field is written, no event is raised
    pg = _sync_page(browser, base, "sync.html")
    assert all("bg" not in w[1] and "bgAt" not in w[1] for w in pg.evaluate("window.__fs.writes"))
    assert pg.evaluate("window.__bgev") == 0
    assert pg.evaluate(f"localStorage.getItem('{key}')") is None
    pg.close()


@needs_browser
def test_the_homepage_choice_is_the_accounts_and_ordinary_sync_is_untouched(browser, site):
    base, _ = site
    pg = _sync_page(browser, base, "sync-home.html",
                    docs={"users/u1": {"homeBg": "dubai-reflection", "homeBgAt": 900}},
                    local={"alto-bg-home-v1": json.dumps({"v": "orion-nebula", "t": 100})})
    assert json.loads(pg.evaluate("localStorage.getItem('alto-bg-home-v1')")) == {"v": "dubai-reflection", "t": 900}
    pg.close()
    pg = _sync_page(browser, base, "sync-home.html", local={"alto-bg-home-v1": json.dumps({"v": "orion-nebula", "t": 100})})
    d = pg.evaluate("window.__fs.docs['users/u1']")
    assert d["homeBg"] == "orion-nebula" and d["homeBgAt"] == 100
    pg.close()
    # the notes sync as ever, beside a background choice
    hl = json.dumps([{"id": "h1", "quote": "abc", "color": "yellow", "note": "n", "mod": 5}])
    pg = _sync_page(browser, base, "sync.html", local={"alto-hl-civ": hl, "alto-hl-civ-bg": json.dumps({"v": "yosemite", "t": 10})})
    d = pg.evaluate("window.__fs.docs['users/u1/tl/civ']")
    assert json.loads(d["highlights"])[0]["id"] == "h1" and d["bg"] == "yosemite"
    pg.close()


@needs_browser
def test_a_pick_made_while_signed_in_syncs_and_a_late_timeline_name_is_followed(browser, site):
    base, _ = site
    pg = _sync_page(browser, base, "sync.html")
    pg.evaluate("localStorage.setItem('alto-hl-civ-bg', JSON.stringify({v:'chicago-dusk', t:Date.now()}))")
    pg.wait_for_timeout(1500)
    assert pg.evaluate("window.__fs.docs['users/u1/tl/civ']")["bg"] == "chicago-dusk"
    pg.close()
    # the private shell loads this file before it knows the timeline, then names it
    pg = _sync_page(browser, base, "sync-home.html")
    pg.evaluate("window.AltoCloud.setTid('civ-pro')"); pg.wait_for_timeout(600)
    pg.evaluate("localStorage.setItem('alto-hl-civ-pro-bg', JSON.stringify({v:'hong-kong', t:Date.now()}))")
    pg.wait_for_timeout(1500)
    assert pg.evaluate("window.__fs.docs['users/u1/tl/civ-pro']")["bg"] == "hong-kong"
    pg.close()


@needs_browser
def test_a_shared_copy_shown_in_a_frame_lets_its_viewer_choose(browser, site, timeline):
    """A share is a srcdoc frame (about:srcdoc), re-stamped as s-{key}: its viewer's
    choice is their own, kept under the share's key, never the owner's."""
    from alto.build.reidentify import reidentify
    base, tid = site
    shared = reidentify(timeline[0], "abc123")
    import html as _h
    pg = browser.new_page(viewport={"width": 1500, "height": 900})
    pg.add_init_script("localStorage.setItem('alto-hl-%s-bg', JSON.stringify({v:'dubai-reflection', t:1}))" % tid)
    pg.goto(base + "/home.html")                         # an origin to frame under
    pg.evaluate("""(h)=>{document.body.innerHTML='';const f=document.createElement('iframe');f.id='stage';
      f.style.cssText='position:fixed;inset:0;width:100%;height:100%;border:0';f.srcdoc=h;document.body.appendChild(f);}""", shared)
    pg.wait_for_timeout(3500)
    fr = pg.frame_locator("#stage")
    state = lambda: next(f for f in pg.frames if f.url == "about:srcdoc").evaluate(STATE)
    assert not state()["on"], "the owner's own choice must not leak into the share"
    fr.locator("#bg-toggle").click(); pg.wait_for_timeout(400)
    fr.locator('.bg-tile[data-bg="tokyo-tower"]').click(); pg.wait_for_timeout(500)
    assert state()["on"] and state()["id"] == "tokyo-tower"
    assert pg.evaluate("localStorage.getItem('alto-hl-s-abc123-bg')") and json.loads(
        pg.evaluate("localStorage.getItem('alto-hl-%s-bg')" % tid))["v"] == "dubai-reflection"
    pg.close()


@needs_browser
def test_a_private_timeline_opens_on_its_photographs_colour(browser, site, timeline, tmp_path_factory):
    """The gate a private timeline paints while it opens is the Alto wallpaper, or
    the colour of the photograph its owner chose when the page last drew it."""
    from alto.build.private_shell import shell
    base, _ = site
    d = Path(site_dir_of(base))
    (d / "pv" / "abc").mkdir(parents=True, exist_ok=True)
    (d / "pv" / "abc" / "index.html").write_text(shell("v1", "s1"), encoding="utf-8")
    rec = ("window.__rec=[];(function t(){const r=document.documentElement;if(r){const s=r.className+'|'+r.style.background;"
           "const l=__rec[__rec.length-1];if(!l||l!==s)__rec.push(s)}requestAnimationFrame(t)})();")
    for dark, want in ((False, "rgb(17, 34, 51)"), (True, "rgb(68, 85, 102)")):
        pg = browser.new_page()
        pg.route("https://www.gstatic.com/**", lambda r: r.abort())          # sign-in never arrives: the gate stays up
        pg.add_init_script(rec)
        pg.add_init_script("localStorage.setItem('alto-account-v1',JSON.stringify({uid:'u1'}));"
                           "localStorage.setItem('alto-theme-v1','%s');"
                           "localStorage.setItem('alto-bgq-v1',JSON.stringify({'pv/abc':['#112233','#445566']}))"
                           % ("dark" if dark else "light"))
        pg.goto(base + "/pv/abc/"); pg.wait_for_timeout(700)
        seen = pg.evaluate("window.__rec")
        assert any("alto-quiet" in s and s.endswith("|" + want) for s in seen), seen
        pg.close()
    pg = browser.new_page()                                   # nothing remembered: the Alto wallpaper
    pg.route("https://www.gstatic.com/**", lambda r: r.abort())
    pg.add_init_script(rec)
    pg.add_init_script("localStorage.setItem('alto-account-v1',JSON.stringify({uid:'u1'}))")
    pg.goto(base + "/pv/abc/"); pg.wait_for_timeout(700)
    seen = pg.evaluate("window.__rec")
    assert any("alto-quiet" in s and s.endswith("|") for s in seen), seen
    pg.close()
