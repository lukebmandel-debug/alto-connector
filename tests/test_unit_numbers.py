"""Unit numbers, Roman or arabic, chosen per timeline (alto/build/unit_numbers.py; Luke, 2026-11-13: "let the user
choose between roman numeral units and numbered units").

Never chosen, every format keeps today's look (Roman band numerals, arabic card and outline numbers). Chosen, every
unit number of every format follows it, at the unit level only ("X.a.1" / "10.a.1"). The choice is made in the Scene
panel (desktop and phone) or by set_units(unit_numbers=...) (tests/test_units_sources_nodes_tools.py), kept per timeline
like the background and synced with the owner's account (users/{uid}/tl/{tid} {un, unAt}; the rules side is in
tests/security/firestore_rules.test.mjs). A share link shows the owner's choice and cannot change it. Switching moves no
card. The browser parts need Playwright (the pw12 venv) and run in WebKit first (Luke uses Safari), then Chromium."""
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
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace_assets, reidentify, unit_numbers as un      # noqa: E402
from alto.build.blocks import ID_PATTERNS                                 # noqa: E402
from alto.build.brief import BriefError, validate_brief                   # noqa: E402
from alto.build.builder import build_timeline, load_brief                 # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
          "Version/17.0 Mobile/15E148 Safari/604.1")
SHARE_KEY = "czckq4utebcx5rvgdptrgt"
CLOUD = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")


def _sample(name, **brief):
    d = json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8"))
    d["brief"].update(brief)
    return d


def _page(name, **brief):
    return build_timeline(*load_brief(_sample(name, **brief)))[0]


def _tid(html):
    return re.search(r"var COURSE_ID = '([^']*)';", html).group(1)


# ── the page and the brief ──────────────────────────────────────────────────

def test_the_brief_takes_only_its_two_choices():
    for v in ("roman", "numbers", ""):
        validate_brief(load_brief(_sample("contracts", unit_numbers=v))[0])
    for bad in ("Roman", "arabic", "1"):
        with pytest.raises(BriefError, match="unit_numbers"):
            validate_brief(load_brief(_sample("contracts", unit_numbers=bad))[0])
    with pytest.raises(BriefError, match="unit_numbers_at"):
        validate_brief(load_brief(_sample("contracts", unit_numbers="roman", unit_numbers_at=-1))[0])


def test_a_page_never_chosen_carries_no_choice_and_its_key_is_the_timelines_own():
    html = _page("contracts")
    key = ID_PATTERNS["hl_key"].format(tid=_tid(html)) + "-un"
    assert html.count('<script id="alto-un-head">') == 1 and html.count(un.OWNER_EMPTY) == 1
    assert 'var K="%s", B=null,' % key in html
    # ahead of the engine: the head script runs before anything draws a number
    assert html.index('id="alto-un-head"') < html.index("const PHASE_META")
    assert html.count('<script id="alto-un-ui">') == 1


def test_the_brief_choice_is_baked_in_with_its_time():
    html = _page("outline", unit_numbers="roman", unit_numbers_at=1762380000000)
    assert 'B={"v": "roman", "t": 1762380000000}' in html


def test_a_share_is_restamped_and_carries_the_owners_choice():
    html = _page("contracts")
    share = reidentify.reidentify(html, SHARE_KEY)
    assert 'var K="alto-hl-s-%s-un"' % SHARE_KEY in share          # its own key, never the master's
    assert un.stamp_owner(share, {"v": "numbers", "t": 5}).count('window._ALTO_UN_OWNER={"v": "numbers", "t": 5};') == 1
    for bad in ({"v": "x", "t": 5}, {"v": "roman", "t": -1}, {"v": "roman"}, None, "roman"):
        assert un.stamp_owner(share, bad).count("window._ALTO_UN_OWNER=null;") == 1
    # the browser's copy of the stamp (alto-cloud.js _sharePush) replaces the same block
    assert '<script id="alto-un-owner">[\\s\\S]*?<\\/script>' in CLOUD
    assert un.OWNER_BLOCK.pattern == '<script id="alto-un-owner">[\\s\\S]*?</script>'


def test_the_account_sync_keeps_the_choice_like_the_background():
    """SECURITY: alto-cloud.js writes {un, unAt} into the owner's own users/{uid}/tl/{tid} only, checks the shape
    both ways ('roman' | 'numbers', a time no later than a day ahead), and a share (s-<key>) has no key at all."""
    assert "const SHARE_TID = /^s-[a-km-np-z2-9]{22}$/;" in CLOUD
    assert "(tid && !SHARE_TID.test(tid)) ? `alto-hl-${tid}-un` : null" in CLOUD
    assert "await setDoc(mainRef, { un: ls.v, unAt: Number(ls.t)," in CLOUD
    assert "o.t < Date.now() + 864e5" in CLOUD
    assert "|| (UN_KEY && k === UN_KEY))) requestSync('local-change');" in CLOUD
    # the share key alphabet matches the one keys are minted from
    alpha = re.search(r"KEY_ALPHABET = '([^']+)'", CLOUD).group(1)
    assert all(re.fullmatch(r"[a-km-np-z2-9]", c) for c in alpha) and len(alpha) == 32


def test_the_rules_keep_a_timelines_settings_its_owners_alone():
    """SECURITY: un/unAt live on users/{uid}/tl/{tid}, whose every read and write the rules give to its owner only
    (writes also need the allowlist); there is no field-level grant anywhere that could open one setting wider."""
    rules = re.sub(r"//[^\n]*", "", (ROOT / "firestore.rules").read_text(encoding="utf-8"))
    assert (ROOT / "firestore.rules").read_bytes() == (ROOT / "alto" / "firestore.rules").read_bytes()
    assert re.search(r"ownCollection\(coll\)\s*\{\s*return coll in \['tl',", rules)
    blk = rules[rules.index("match /{coll}/{id} {"):]
    blk = blk[:blk.index("\n      }")]
    assert "allow read: if isUser(uid) && ownCollection(coll);" in blk
    assert "allow create, update: if isUser(uid) && ownCollection(coll) && allowlisted();" in blk
    assert "un" not in re.findall(r"\b(un|unAt)\b", rules)


# ── in a browser ────────────────────────────────────────────────────────────

def _city():
    import test_world_palace as _wld
    b = {"title": "City", "timeline_id": "cityx", "mode": "palace", "columns": 5, "node_noun": "Concept",
         "period_noun": "Unit", "acts": [{"label": "A", "color": "#5b6cff"}, {"label": "B", "color": "#9b5de5"}]}
    b, ns, cs = load_brief({"brief": b, "nodes": json.loads(json.dumps(_wld.NODES))})
    return build_timeline(b, ns, cs)[0]


PAGES = {}


@pytest.fixture(scope="module")
def site():
    if pw is None:
        pytest.skip("Playwright is not installed")
    import test_building_palace_tools as _bld
    import test_solar_draw as _sol
    import test_world_palace as _wld
    PAGES.update({"timeline": _page("contracts"), "outline": _page("outline"), "lanes": _page("lanes"),
                  "city": _city(), "atlas": _wld.built()[0], "blueprint": _bld.built()[0], "system": _sol._page()})
    owner = _page("contracts")
    PAGES["share"] = un.stamp_owner(reidentify.reidentify(owner, SHARE_KEY), {"v": "numbers", "t": 10})

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            name = path.strip("/").removesuffix(".html")
            hit = (("text/html", PAGES[name]) if path.endswith(".html") and name in PAGES
                   else ("text/javascript", "") if path == "/alto-cloud.js" else palace_assets.find(path))
            body = hit[1] if hit else "no"
            body = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(scope="module", params=["webkit", "chromium"])
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


GRAB = r"""() => { const pos = {}; document.querySelectorAll('#world .node[id^="node-"]').forEach(e => { const b = e.getBoundingClientRect();
  pos[e.id] = [Math.round(b.left * 10) / 10, Math.round(b.top * 10) / 10]; });
  const t = s => [...document.querySelectorAll(s)].map(e => e.textContent);
  return {pos, numerals: t('.phase-numeral'), orders: t('#world .node-order'), un: t('.un-n'), mode: window._altoUN.cur(),
          attr: document.documentElement.getAttribute('data-un')}; }"""


def _open(browser, site, name, phone=False, choice=None, motion="no-preference"):
    ctx = browser.new_context(viewport={"width": 390, "height": 844} if phone else {"width": 1440, "height": 900},
                              has_touch=phone, is_mobile=phone and browser.browser_type.name != "firefox",
                              device_scale_factor=2 if phone else 1, user_agent=IPHONE if phone else None,
                              reduced_motion=motion)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{site}/{name}.html")
    pg.wait_for_timeout(200)
    pg.evaluate("localStorage.clear()")
    if choice:
        pg.evaluate("v => localStorage.setItem(window._altoUN.key, JSON.stringify({v: v, t: Date.now()}))", choice)
    pg.reload()
    pg.wait_for_timeout(2200)
    return pg, ctx, errors


def _real(errors):
    return [e for e in errors if "ResizeObserver" not in e]


ROMAN = re.compile(r"^[IVXLCDM]+$")
ARABIC = re.compile(r"^\d+$")


def _heads(texts):
    return [re.match(r"^([^.\-]+)", t).group(1) for t in texts if t]


def test_the_helpers_write_every_number_both_ways(browser, site):
    pg, ctx, errors = _open(browser, site, "timeline")
    r = pg.evaluate("""() => { const U = window._altoUN;
      return [U.roman(28), U.to('10.a.1', 'roman'), U.to('X.a.1', 'numbers'), U.to('XXVIII.c.2-1b', 'numbers'),
              U.to('3.4-2', 'roman'), U.to('Mar 3', 'roman'), U.arabic('x.a.1'), U.arabic('IV'), U.arabic('c'),
              U.p('10.a.1'), U.u(4, 'roman'), U.u(4, 'numbers')]; }""")
    assert r == ["XXVIII", "X.a.1", "10.a.1", "28.c.2-1b", "III.4-2", "Mar 3", "10.a.1", "4", "c", "10.a.1", "IV", "4"]
    assert not _real(errors)
    ctx.close()


@pytest.mark.parametrize("name", ["timeline", "outline", "lanes", "city", "atlas", "blueprint", "system"])
def test_never_chosen_every_format_keeps_its_look(browser, site, name):
    pg, ctx, errors = _open(browser, site, name)
    r = pg.evaluate(GRAB)
    assert r["mode"] == "" and r["attr"] is None
    assert all(ROMAN.match(t) for t in r["numerals"]), r["numerals"]
    assert all(ARABIC.match(h) for h in _heads(r["orders"])), r["orders"][:6]
    assert not _real(errors), errors
    ctx.close()


@pytest.mark.parametrize("phone", [False, True], ids=["desktop", "phone"])
@pytest.mark.parametrize("choice", ["roman", "numbers"])
@pytest.mark.parametrize("name", ["timeline", "outline", "lanes", "city", "atlas", "blueprint", "system"])
def test_a_choice_writes_every_unit_number_of_every_format_its_way(browser, site, name, choice, phone):
    pg, ctx, errors = _open(browser, site, name, phone=phone, choice=choice)
    r = pg.evaluate(GRAB)
    want = ROMAN if choice == "roman" else ARABIC
    assert r["mode"] == choice and r["attr"] == choice
    assert r["orders"] and all(want.match(h) for h in _heads(r["orders"])), r["orders"][:6]
    assert all(want.match(t) for t in r["numerals"] + r["un"]), (r["numerals"], r["un"])
    # the levels under the unit never change: the same marks as the page's own (arabic) numbers
    canon = pg.evaluate("() => [...document.querySelectorAll('#world .node[id^=\"node-\"]')].map(e => NODE_ORDER_MAP[e.id.slice(5)] || '')")
    shown = pg.evaluate("() => [...document.querySelectorAll('#world .node[id^=\"node-\"]')].map(e => { const o = e.querySelector('.node-order'); return o ? o.textContent : ''; })")
    for c, s in zip(canon, shown):
        if c and s and not re.match(r"^[a-z\d]+$", s):        # (a System's moon shows its own last mark only)
            assert re.sub(r"^[^.\-]+", "", c) == re.sub(r"^[^.\-]+", "", s), (c, s)
    assert not _real(errors), errors
    ctx.close()


@pytest.mark.parametrize("phone", [False, True], ids=["desktop", "phone"])
@pytest.mark.parametrize("name", ["timeline", "outline", "lanes", "city", "atlas", "blueprint"])
def test_switching_moves_no_card_and_needs_no_reload(browser, site, name, phone):
    pg, ctx, errors = _open(browser, site, name, phone=phone, motion="reduce")
    first = pg.evaluate(GRAB)
    for v in ("roman", "numbers", "roman"):
        assert pg.evaluate("v => window._altoUN.set(v)", v)
        pg.wait_for_timeout(250)
        r = pg.evaluate(GRAB)
        assert r["mode"] == v
        assert r["pos"] == first["pos"], [k for k in r["pos"] if r["pos"][k] != first["pos"].get(k)][:5]
        assert all((ROMAN if v == "roman" else ARABIC).match(h) for h in _heads(r["orders"]))
    # the band numerals' collision box is the wider of the two spellings, so it is the same whichever is shown
    boxes = pg.evaluate("""() => [...document.querySelectorAll('.phase-numeral')].filter(e => e.offsetWidth).map(e => {
      const w = window._altoUN.wide(e), t = e.textContent, n = /\\d/.test(t) ? +t : null;
      const a = [], keep = t; [window._altoUN.to(t, 'roman'), window._altoUN.to(t, 'numbers')].forEach(s => { e.textContent = s; a.push(e.offsetWidth); });
      e.textContent = keep; return [w, Math.max.apply(null, a)]; })""")
    assert all(w == m for w, m in boxes), boxes
    assert not _real(errors), errors
    ctx.close()


def _open_panel(pg, phone):
    if phone:
        pg.evaluate("(document.getElementById('drawer-scene-btn') || document.getElementById('bg-toggle')).click()")
    else:
        pg.click("#bg-toggle")
    pg.wait_for_timeout(700)
    assert pg.evaluate("document.getElementById('bg-panel').classList.contains('open')")


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("phone", [False, True], ids=["desktop", "phone"])
def test_the_scene_panel_switch_changes_and_keeps_the_choice(browser, site, phone, style):
    pg, ctx, errors = _open(browser, site, "outline", phone=phone)
    if style != "classic":
        pg.evaluate("s => localStorage.setItem(window._altoUN.key.replace(/-un$/, '-style'), s)", style)
        pg.reload()
        pg.wait_for_timeout(2200)
    _open_panel(pg, phone)
    row = pg.evaluate("""() => { const r = document.getElementById('bg-units'), b = r && r.getBoundingClientRect(), p = document.getElementById('bg-panel').getBoundingClientRect();
      return r && {w: b.width, h: b.height, inside: b.left >= p.left - .5 && b.right <= p.right + .5, labels: [...r.querySelectorAll('.bg-segb')].map(e => e.textContent), heights: [...r.querySelectorAll('.bg-segb')].map(e => e.getBoundingClientRect().height),
                   on: [...r.querySelectorAll('.bg-segb.on')].length, shown: getComputedStyle(r).display !== 'none'}; }""")
    assert row and row["shown"] and row["w"] > 100 and row["inside"], row
    assert row["labels"] == ["III", "3"] and row["on"] == 1   # (1.9.274, Luke: "much more simple": one row, a small III | 3 switch; round 2: III shown selected until a choice is made)
    assert pg.evaluate("window._altoUN.cur()") == "" and pg.evaluate("localStorage.getItem(window._altoUN.key)") is None   # ...and nothing is stored by showing it
    assert all(h >= 44 for h in row["heights"]) or not phone, row
    pg.evaluate("document.querySelector('#bg-units .bg-segb[data-un=numbers]').click()")
    pg.wait_for_timeout(200)
    r = pg.evaluate(GRAB)
    assert r["mode"] == "numbers" and all(ARABIC.match(t) for t in r["numerals"])
    assert pg.evaluate("document.querySelector('#bg-units .bg-segb.on').getAttribute('data-un')") == "numbers"
    stored = json.loads(pg.evaluate("localStorage.getItem(window._altoUN.key)"))
    assert stored["v"] == "numbers" and stored["t"] > 0
    pg.reload()
    pg.wait_for_timeout(2200)
    assert pg.evaluate(GRAB)["mode"] == "numbers"
    assert not _real(errors), errors
    ctx.close()


@pytest.mark.parametrize("phone", [False, True], ids=["desktop", "phone"])
def test_a_share_shows_the_owners_choice_and_cannot_change_it(browser, site, phone):
    pg, ctx, errors = _open(browser, site, "share", phone=phone)
    # a viewer's own stored value for the share's key is never read
    pg.evaluate("localStorage.setItem('alto-hl-s-%s-un', JSON.stringify({v: 'roman', t: Date.now() + 1000}))" % SHARE_KEY)
    pg.reload()
    pg.wait_for_timeout(2200)
    r = pg.evaluate(GRAB)
    assert r["mode"] == "numbers" and all(ARABIC.match(t) for t in r["numerals"]) and all(ARABIC.match(h) for h in _heads(r["orders"]))
    assert pg.evaluate("window._altoUN.share") is True
    assert pg.evaluate("window._altoUN.set('roman')") is False and pg.evaluate(GRAB)["mode"] == "numbers"
    _open_panel(pg, phone)
    btns = pg.evaluate("[...document.querySelectorAll('#bg-units .bg-segb')].map(b => [b.getAttribute('data-un'), b.disabled, b.classList.contains('on')])")
    assert btns == [["roman", True, False], ["numbers", True, True]]
    pg.evaluate("document.querySelector('#bg-units .bg-segb[data-un=roman]').click()")
    pg.wait_for_timeout(200)
    assert pg.evaluate(GRAB)["mode"] == "numbers"
    assert "Set by the owner" in pg.evaluate("document.getElementById('bg-units').textContent")
    assert not _real(errors), errors
    ctx.close()


def test_a_brief_choice_shows_until_the_owner_picks_a_newer_one(browser, site):
    PAGES["briefed"] = _page("contracts", unit_numbers="numbers", unit_numbers_at=1000)
    pg, ctx, errors = _open(browser, site, "briefed")
    assert pg.evaluate(GRAB)["mode"] == "numbers"
    pg.evaluate("window._altoUN.set('roman')")
    pg.reload()
    pg.wait_for_timeout(1500)
    assert pg.evaluate(GRAB)["mode"] == "roman"            # newer than the brief's
    ctx.close()


# ── the account sync (the real alto-cloud.js on the Firestore stand-in of test_backgrounds) ────────────────

@pytest.fixture(scope="module")
def cloud_site(tmp_path_factory):
    from alto.cloud import emit_cloud_js
    d = tmp_path_factory.mktemp("unsite")
    (d / "alto-cloud.js").write_text(emit_cloud_js({"apiKey": "k", "authDomain": "p.firebaseapp.com", "projectId": "p",
                                                    "storageBucket": "", "messagingSenderId": "", "appId": "a"}), encoding="utf-8")
    for tid in ("civ", "s-" + SHARE_KEY):
        (d / f"{tid}.html").write_text('<!doctype html><html><head><meta charset="utf-8"></head><body>'
                                       f'<script type="module" src="/alto-cloud.js" data-tid="{tid}"></script></body></html>', encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}"
    s.shutdown()


def _sync(browser, base, tid="civ", docs=None, local=None):
    from test_backgrounds import _STUBS
    key, tl = f"alto-hl-{tid}-un", f"users/u1/tl/{tid}"
    pg = browser.new_page()
    pg.route("https://www.gstatic.com/firebasejs/**", lambda r: r.fulfill(
        status=200, content_type="text/javascript", body=_STUBS[r.request.url.rsplit("/", 1)[1]]))
    pg.add_init_script("window.__fs={docs:%s,writes:[]};" % json.dumps(docs or {}))
    if local is not None:
        pg.add_init_script("try{localStorage.getItem(%r)===null&&localStorage.setItem(%r,%r)}catch(e){}" % (key, key, local))
    pg.goto(f"{base}/{tid}.html")
    pg.wait_for_timeout(2500)
    out = (pg.evaluate("window.__fs.docs[%r]||{}" % tl), pg.evaluate("localStorage.getItem(%r)" % key))
    pg.close()
    return out


def test_the_choice_syncs_with_the_owners_account_both_ways(browser, cloud_site):
    d, _ = _sync(browser, cloud_site, local=json.dumps({"v": "numbers", "t": 100}))
    assert d["un"] == "numbers" and d["unAt"] == 100
    _, ls = _sync(browser, cloud_site, docs={"users/u1/tl/civ": {"un": "roman", "unAt": 500}})
    assert json.loads(ls) == {"v": "roman", "t": 500}


@pytest.mark.parametrize("bad", [{"v": "x" * 5000, "t": 100}, {"v": "Roman", "t": 100}, {"v": 7, "t": 100},
                                 {"v": "roman", "t": 4102444800000}, {"v": "roman", "t": -5}])
def test_a_bad_local_value_is_never_pushed(browser, cloud_site, bad):
    d, _ = _sync(browser, cloud_site, local=json.dumps(bad))
    assert "un" not in d and "unAt" not in d


@pytest.mark.parametrize("bad", [{"un": "y" * 5000, "unAt": 500}, {"un": "roman", "unAt": 4102444800000}, {"un": 3, "unAt": 500}])
def test_a_bad_remote_value_is_never_stored(browser, cloud_site, bad):
    _, ls = _sync(browser, cloud_site, docs={"users/u1/tl/civ": bad})
    assert ls is None


def test_a_share_page_never_syncs_a_choice(browser, cloud_site):
    """SECURITY: a share link's page (s-<key>) neither pushes nor pulls unit numbers."""
    tid = "s-" + SHARE_KEY
    d, _ = _sync(browser, cloud_site, tid=tid, local=json.dumps({"v": "numbers", "t": 100}))
    assert "un" not in d and "unAt" not in d
    _, ls = _sync(browser, cloud_site, tid=tid, docs={f"users/u1/tl/{tid}": {"un": "roman", "unAt": 500}})
    assert ls is None


# ── v1.9.236: the Unit numbers picker, Luke's pick B (L-1116-1905): two real-label chips, same setting, 44pt, and the Classic contrast fixes ──

def _lum(rgb):
    c = [v / 255 for v in rgb[:3]]
    c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]


def _worst_glyph_contrast(pg, sel, which=0):
    """Art's method: the element's text drawn, then drawn transparent; the pixels that differ are its glyphs, each judged against what is behind it."""
    import io
    PIL = pytest.importorskip("PIL.Image")
    box = pg.evaluate("([s, i]) => { const e = [...document.querySelectorAll(s)][i]; e.scrollIntoView({block: 'center'}); const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; }", [sel, which])
    pg.wait_for_timeout(150)
    box = pg.evaluate("([s, i]) => { const r = [...document.querySelectorAll(s)][i].getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; }", [sel, which])
    a = PIL.open(io.BytesIO(pg.screenshot(clip=box))).convert("RGB")
    pg.evaluate("([s, i]) => { const st = document.createElement('style'); st.id = '__tr'; st.textContent = s + ',' + s + ' *{color:transparent !important;-webkit-text-fill-color:transparent !important;text-shadow:none !important}'; document.head.appendChild(st); }", [sel, which])
    pg.evaluate("([s, i]) => { const e = [...document.querySelectorAll(s)][i]; e.setAttribute('data-tr', '1'); }", [sel, which])
    b = PIL.open(io.BytesIO(pg.screenshot(clip=box))).convert("RGB")
    pg.evaluate("() => { document.getElementById('__tr').remove(); document.querySelectorAll('[data-tr]').forEach(e => e.removeAttribute('data-tr')); }")
    pa, pb = a.load(), b.load()
    diffs = [(abs(pa[x, y][0] - pb[x, y][0]) + abs(pa[x, y][1] - pb[x, y][1]) + abs(pa[x, y][2] - pb[x, y][2]), x, y) for y in range(a.height) for x in range(a.width)]
    top = max(d[0] for d in diffs)
    if top < 40:
        return None
    worst = 99
    for d, x, y in diffs:
        if d >= top * .75:                                     # a glyph's core pixels, not its anti-aliased edge
            la, lb = _lum(pa[x, y]), _lum(pb[x, y])
            worst = min(worst, (max(la, lb) + .05) / (min(la, lb) + .05))
    return worst


def _ink_mid(pg, sel, which=0):
    """The rendered ink of the element's glyphs (drawn minus drawn-transparent, as _worst_glyph_contrast does): its vertical centre and the box's, in screen px."""
    import io
    PIL = pytest.importorskip("PIL.Image")
    pg.evaluate("([s, i]) => [...document.querySelectorAll(s)][i].scrollIntoView({block: 'center'})", [sel, which])
    pg.wait_for_timeout(150)
    box = pg.evaluate("([s, i]) => { const r = [...document.querySelectorAll(s)][i].getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; }", [sel, which])
    a = PIL.open(io.BytesIO(pg.screenshot(clip=box))).convert("RGB")
    pg.evaluate("([s]) => { const st = document.createElement('style'); st.id = '__tr'; st.textContent = s + ',' + s + ' *{color:transparent !important;-webkit-text-fill-color:transparent !important;text-shadow:none !important}'; document.head.appendChild(st); }", [sel])
    b = PIL.open(io.BytesIO(pg.screenshot(clip=box))).convert("RGB")
    pg.evaluate("() => document.getElementById('__tr').remove()")
    k = a.width / box["width"]                                   # (screenshot px per CSS px)
    pa, pb = a.load(), b.load()
    ys = [y for y in range(a.height) for x in range(a.width) if sum(abs(pa[x, y][c] - pb[x, y][c]) for c in range(3)) > 120]
    assert ys, ("no ink", sel)
    return ((min(ys) + max(ys) + 1) / 2 / k, box["height"] / 2)


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("phone", [False, True], ids=["desktop", "phone"])
def test_the_unit_switch_is_one_small_row_with_two_segments(browser, site, phone, style):
    """1.9.274 (Luke: "the current unit numbers toggle is too complicated, please make it much more simple"): one row, the label
    on the left and a III | 3 switch on the right, the selected segment filled, no sample sentence or "Part" text; the setting
    and how it is stored are the old ones. (Replaces the two 1.9.236/243 chip tests that asserted the preview chips.)"""
    pg, ctx, errors = _open(browser, site, "system", phone=phone)
    if style != "classic":
        pg.evaluate("s => localStorage.setItem(window._altoUN.key.replace(/-un$/, '-style'), s)", style)
        pg.reload()
        pg.wait_for_timeout(2200)
    _open_panel(pg, phone)
    if style == "retro":                                      # (the System page's own style switch: the key above only reaches the hosted layer)
        pg.evaluate("window._altoSolarStyles && window._altoSolarStyles.set('retro')")
        pg.wait_for_timeout(1500)
        assert pg.evaluate("document.documentElement.classList.contains('alto-retro') || document.documentElement.classList.contains('sk-retro')")
    pg.add_style_tag(content="*,*::before,*::after{animation:none !important;transition:none !important}")
    info = pg.evaluate("""() => { const r = document.getElementById('bg-units'), rb = r.getBoundingClientRect(), p = document.getElementById('bg-panel').getBoundingClientRect();
      const segs = [...r.querySelectorAll('.bg-segb')], h = r.querySelector('.bg-h').getBoundingClientRect(), g = r.querySelector('.bg-solar-seg').getBoundingClientRect();
      return {rows: document.querySelectorAll('#bg-units').length, text: r.textContent, head: r.querySelector('.bg-h').textContent, u: segs.map(b => b.getAttribute('data-un')), t: segs.map(b => b.textContent),
              title: segs.map(b => b.title), aria: segs.map(b => b.getAttribute('aria-label')), h: segs.map(b => b.getBoundingClientRect().height), w: segs.map(b => b.getBoundingClientRect().width),
              rowh: rb.height, inside: rb.left >= p.left - .5 && rb.right <= p.right + .5, labelLeft: h.right <= g.left + .5, oneLine: Math.abs((h.top + h.bottom) / 2 - (g.top + g.bottom) / 2) < 3,
              kids: [...r.children].map(e => e.className)}; }""")
    assert info["rows"] == 1 and info["inside"] and info["head"] == "Unit numbers" and info["labelLeft"] and info["oneLine"], info
    assert info["u"] == ["roman", "numbers"] and info["t"] == ["III", "3"] and info["kids"] == ["bg-h", "bg-solar-seg"], info    # two segments, no sub-labels, no note
    assert not re.search(r"Part|Unit \d|Unit I|ROMAN|PLAIN|\u00b7", info["text"]) and info["text"] == "Unit numbersIII3", info["text"]       # no sample sentence
    assert info["title"] == ["Roman", "Plain"] and info["aria"] == ["Unit numbers: Roman", "Unit numbers: Plain"], info                # tooltip + accessible name
    others = pg.evaluate("""() => ['#bg-style', '#bg-motion'].map(id => document.querySelector(id + ' .bg-segb')).filter(e => e && e.getBoundingClientRect().height > 0).map(e => e.getBoundingClientRect().height)""")
    if phone:
        assert all(h >= 44 and w >= 44 for h, w in zip(info["h"], info["w"])), ("44pt", info)
        assert others and all(abs(h - o) <= 2 for h in info["h"] for o in others), ("same as the Style/Motion rows", info["h"], others)
    else:
        assert all(h >= 24 for h in info["h"]), (info["h"], info["w"])   # (the desktop panel is drawn at about 85%, so 30px reads 25px)
        hug = pg.evaluate("""() => { const p = document.getElementById('bg-panel'), pr = p.getBoundingClientRect(), k = pr.height / p.offsetHeight, cs = getComputedStyle(p);
          const last = [...p.querySelectorAll('.bg-body > .bg-sec')].filter(e => e.getBoundingClientRect().height > 0).pop().getBoundingClientRect();
          return {gap: pr.bottom - last.bottom, pad: parseFloat(cs.paddingBottom) * k}; }""")
        assert abs(hug["gap"] - hug["pad"]) <= 2, ("the panel hugs its content", hug)
    for i in (0, 1):                                           # the numerals are lining: both glyph sets centred on the segment
        mid, box = _ink_mid(pg, "#bg-units .bg-segb", i)
        assert abs(mid - box) <= 1, ("ink centre", info["t"][i], mid, box)
    pg.evaluate("document.querySelector('#bg-units .bg-segb[data-un=roman]').click()")
    pg.wait_for_timeout(200)
    assert pg.evaluate(GRAB)["mode"] == "numbers"
    assert "Set by the owner" in pg.evaluate("document.getElementById('bg-units').textContent")
    assert not _real(errors), errors
    ctx.close()


def test_a_brief_choice_shows_until_the_owner_picks_a_newer_one(browser, site):
    PAGES["briefed"] = _page("contracts", unit_numbers="numbers", unit_numbers_at=1000)
    pg, ctx, errors = _open(browser, site, "briefed")
    assert pg.evaluate(GRAB)["mode"] == "numbers"
    pg.evaluate("window._altoUN.set('roman')")
    pg.reload()
    pg.wait_for_timeout(1500)
    assert pg.evaluate(GRAB)["mode"] == "roman"            # newer than the brief's
    ctx.close()


# ── the account sync (the real alto-cloud.js on the Firestore stand-in of test_backgrounds) ────────────────

@pytest.fixture(scope="module")
def cloud_site(tmp_path_factory):
    from alto.cloud import emit_cloud_js
    d = tmp_path_factory.mktemp("unsite")
    (d / "alto-cloud.js").write_text(emit_cloud_js({"apiKey": "k", "authDomain": "p.firebaseapp.com", "projectId": "p",
                                                    "storageBucket": "", "messagingSenderId": "", "appId": "a"}), encoding="utf-8")
    for tid in ("civ", "s-" + SHARE_KEY):
        (d / f"{tid}.html").write_text('<!doctype html><html><head><meta charset="utf-8"></head><body>'
                                       f'<script type="module" src="/alto-cloud.js" data-tid="{tid}"></script></body></html>', encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}"
    s.shutdown()


def _sync(browser, base, tid="civ", docs=None, local=None):
    from test_backgrounds import _STUBS
    key, tl = f"alto-hl-{tid}-un", f"users/u1/tl/{tid}"
    pg = browser.new_page()
    pg.route("https://www.gstatic.com/firebasejs/**", lambda r: r.fulfill(
        status=200, content_type="text/javascript", body=_STUBS[r.request.url.rsplit("/", 1)[1]]))
    pg.add_init_script("window.__fs={docs:%s,writes:[]};" % json.dumps(docs or {}))
    if local is not None:
        pg.add_init_script("try{localStorage.getItem(%r)===null&&localStorage.setItem(%r,%r)}catch(e){}" % (key, key, local))
    pg.goto(f"{base}/{tid}.html")
    pg.wait_for_timeout(2500)
    out = (pg.evaluate("window.__fs.docs[%r]||{}" % tl), pg.evaluate("localStorage.getItem(%r)" % key))
    pg.close()
    return out


def test_the_choice_syncs_with_the_owners_account_both_ways(browser, cloud_site):
    d, _ = _sync(browser, cloud_site, local=json.dumps({"v": "numbers", "t": 100}))
    assert d["un"] == "numbers" and d["unAt"] == 100
    _, ls = _sync(browser, cloud_site, docs={"users/u1/tl/civ": {"un": "roman", "unAt": 500}})
    assert json.loads(ls) == {"v": "roman", "t": 500}


@pytest.mark.parametrize("bad", [{"v": "x" * 5000, "t": 100}, {"v": "Roman", "t": 100}, {"v": 7, "t": 100},
                                 {"v": "roman", "t": 4102444800000}, {"v": "roman", "t": -5}])
def test_a_bad_local_value_is_never_pushed(browser, cloud_site, bad):
    d, _ = _sync(browser, cloud_site, local=json.dumps(bad))
    assert "un" not in d and "unAt" not in d


@pytest.mark.parametrize("bad", [{"un": "y" * 5000, "unAt": 500}, {"un": "roman", "unAt": 4102444800000}, {"un": 3, "unAt": 500}])
def test_a_bad_remote_value_is_never_stored(browser, cloud_site, bad):
    _, ls = _sync(browser, cloud_site, docs={"users/u1/tl/civ": bad})
    assert ls is None


def test_a_share_page_never_syncs_a_choice(browser, cloud_site):
    """SECURITY: a share link's page (s-<key>) neither pushes nor pulls unit numbers."""
    tid = "s-" + SHARE_KEY
    d, _ = _sync(browser, cloud_site, tid=tid, local=json.dumps({"v": "numbers", "t": 100}))
    assert "un" not in d and "unAt" not in d
    _, ls = _sync(browser, cloud_site, tid=tid, docs={f"users/u1/tl/{tid}": {"un": "roman", "unAt": 500}})
    assert ls is None


# ── v1.9.236: the Unit numbers picker, Luke's pick B (L-1116-1905): two real-label chips, same setting, 44pt, and the Classic contrast fixes ──

def _lum(rgb):
    c = [v / 255 for v in rgb[:3]]
    c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]


def _worst_glyph_contrast(pg, sel, which=0):
    """Art's method: the element's text drawn, then drawn transparent; the pixels that differ are its glyphs, each judged against what is behind it."""
    import io
    PIL = pytest.importorskip("PIL.Image")
    box = pg.evaluate("([s, i]) => { const e = [...document.querySelectorAll(s)][i]; e.scrollIntoView({block: 'center'}); const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; }", [sel, which])
    pg.wait_for_timeout(150)
    box = pg.evaluate("([s, i]) => { const r = [...document.querySelectorAll(s)][i].getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; }", [sel, which])
    a = PIL.open(io.BytesIO(pg.screenshot(clip=box))).convert("RGB")
    pg.evaluate("([s, i]) => { const st = document.createElement('style'); st.id = '__tr'; st.textContent = s + ',' + s + ' *{color:transparent !important;-webkit-text-fill-color:transparent !important;text-shadow:none !important}'; document.head.appendChild(st); }", [sel, which])
    pg.evaluate("([s, i]) => { const e = [...document.querySelectorAll(s)][i]; e.setAttribute('data-tr', '1'); }", [sel, which])
    b = PIL.open(io.BytesIO(pg.screenshot(clip=box))).convert("RGB")
    pg.evaluate("() => { document.getElementById('__tr').remove(); document.querySelectorAll('[data-tr]').forEach(e => e.removeAttribute('data-tr')); }")
    pa, pb = a.load(), b.load()
    diffs = [(abs(pa[x, y][0] - pb[x, y][0]) + abs(pa[x, y][1] - pb[x, y][1]) + abs(pa[x, y][2] - pb[x, y][2]), x, y) for y in range(a.height) for x in range(a.width)]
    top = max(d[0] for d in diffs)
    if top < 40:
        return None
    worst = 99
    for d, x, y in diffs:
        if d >= top * .75:                                     # a glyph's core pixels, not its anti-aliased edge
            la, lb = _lum(pa[x, y]), _lum(pb[x, y])
            worst = min(worst, (max(la, lb) + .05) / (min(la, lb) + .05))
    return worst


def _ink_mid(pg, sel, which=0):
    """The rendered ink of the element's glyphs (drawn minus drawn-transparent, as _worst_glyph_contrast does): its vertical centre and the box's, in screen px."""
    import io
    PIL = pytest.importorskip("PIL.Image")
    pg.evaluate("([s, i]) => [...document.querySelectorAll(s)][i].scrollIntoView({block: 'center'})", [sel, which])
    pg.wait_for_timeout(150)
    box = pg.evaluate("([s, i]) => { const r = [...document.querySelectorAll(s)][i].getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; }", [sel, which])
    a = PIL.open(io.BytesIO(pg.screenshot(clip=box))).convert("RGB")
    pg.evaluate("([s]) => { const st = document.createElement('style'); st.id = '__tr'; st.textContent = s + ',' + s + ' *{color:transparent !important;-webkit-text-fill-color:transparent !important;text-shadow:none !important}'; document.head.appendChild(st); }", [sel])
    b = PIL.open(io.BytesIO(pg.screenshot(clip=box))).convert("RGB")
    pg.evaluate("() => document.getElementById('__tr').remove()")
    k = a.width / box["width"]                                   # (screenshot px per CSS px)
    pa, pb = a.load(), b.load()
    ys = [y for y in range(a.height) for x in range(a.width) if sum(abs(pa[x, y][c] - pb[x, y][c]) for c in range(3)) > 120]
    assert ys, ("no ink", sel)
    return ((min(ys) + max(ys) + 1) / 2 / k, box["height"] / 2)


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("phone", [False, True], ids=["desktop", "phone"])
def test_the_unit_switch_is_one_small_row_with_two_segments(browser, site, phone, style):
    """1.9.274 (Luke: "the current unit numbers toggle is too complicated, please make it much more simple"): one row, the label
    on the left and a III | 3 switch on the right, the selected segment filled, no sample sentence or "Part" text; the setting
    and how it is stored are the old ones. (Replaces the two 1.9.236/243 chip tests that asserted the preview chips.)"""
    pg, ctx, errors = _open(browser, site, "system", phone=phone)
    if style != "classic":
        pg.evaluate("s => localStorage.setItem(window._altoUN.key.replace(/-un$/, '-style'), s)", style)
        pg.reload()
        pg.wait_for_timeout(2200)
    _open_panel(pg, phone)
    if style == "retro":                                      # (the System page's own style switch: the key above only reaches the hosted layer)
        pg.evaluate("window._altoSolarStyles && window._altoSolarStyles.set('retro')")
        pg.wait_for_timeout(1500)
        assert pg.evaluate("document.documentElement.classList.contains('alto-retro') || document.documentElement.classList.contains('sk-retro')")
    pg.add_style_tag(content="*,*::before,*::after{animation:none !important;transition:none !important}")
    info = pg.evaluate("""() => { const r = document.getElementById('bg-units'), rb = r.getBoundingClientRect(), p = document.getElementById('bg-panel').getBoundingClientRect();
      const segs = [...r.querySelectorAll('.bg-segb')], h = r.querySelector('.bg-h').getBoundingClientRect(), g = r.querySelector('.bg-solar-seg').getBoundingClientRect();
      return {rows: document.querySelectorAll('#bg-units').length, text: r.textContent, head: r.querySelector('.bg-h').textContent, u: segs.map(b => b.getAttribute('data-un')), t: segs.map(b => b.textContent),
              title: segs.map(b => b.title), aria: segs.map(b => b.getAttribute('aria-label')), h: segs.map(b => b.getBoundingClientRect().height), w: segs.map(b => b.getBoundingClientRect().width),
              rowh: rb.height, inside: rb.left >= p.left - .5 && rb.right <= p.right + .5, labelLeft: h.right <= g.left + .5, oneLine: Math.abs((h.top + h.bottom) / 2 - (g.top + g.bottom) / 2) < 3,
              kids: [...r.children].map(e => e.className)}; }""")
    assert info["rows"] == 1 and info["inside"] and info["head"] == "Unit numbers" and info["labelLeft"] and info["oneLine"], info
    assert info["u"] == ["roman", "numbers"] and info["t"] == ["III", "3"] and info["kids"] == ["bg-h", "bg-solar-seg"], info    # two segments, no sub-labels, no note
    assert not re.search(r"Part|Unit \d|Unit I|ROMAN|PLAIN|\u00b7", info["text"]) and info["text"] == "Unit numbersIII3", info["text"]       # no sample sentence
    assert info["title"] == ["Roman", "Plain"] and info["aria"] == ["Unit numbers: Roman", "Unit numbers: Plain"], info                # tooltip + accessible name
    sib = pg.evaluate("""() => [...document.querySelectorAll('#bg-panel .bg-segb')].filter(b => !b.closest('#bg-units')).map(b => b.getBoundingClientRect().height).filter(h => h > 0)""")
    if phone:
        assert all(h >= 44 and w >= 44 for h, w in zip(info["h"], info["w"])), ("44pt", info)
        assert info["rowh"] >= 44, info
    else:
        assert all(h >= 24 for h in info["h"]), (info["h"], info["w"])   # (the desktop panel is drawn at about 85%, so 30px reads 25px)
    if sib and phone:                                          # the row is as tall as the sheet's other switch rows (the Style and Motion segments)
        assert abs(info["rowh"] - min(sib)) <= 2 or info["rowh"] >= min(sib), (info["rowh"], sib)
    cr = pg.evaluate("""() => { const b = document.querySelector('#bg-units .bg-segb.on'), cs = getComputedStyle(b), p = s => /(\\d+(?:\\.\\d+)?)[, ]+(\\d+(?:\\.\\d+)?)[, ]+(\\d+(?:\\.\\d+)?)/.exec(s).slice(1, 4).map(Number);
      return [p(cs.color), p(cs.backgroundColor)]; }""")
    l1, l2 = _lum(cr[0]), _lum(cr[1])
    assert (max(l1, l2) + .05) / (min(l1, l2) + .05) >= 4.5, ("the selected segment's text on its fill", style, cr)     # Retro: dark ink on gold, not white (2.07:1)
    assert pg.evaluate("[...document.querySelectorAll('#bg-units .bg-segb.on')].map(b => b.getAttribute('data-un'))") == ["roman"]      # a fresh profile: III is shown selected...
    assert pg.evaluate("localStorage.getItem(window._altoUN.key)") is None and pg.evaluate("window._altoUN.cur()") == ""             # ...and nothing is stored by showing it
    pg.evaluate("document.querySelector('#bg-units .bg-segb[data-un=roman]').click()")
    pg.wait_for_timeout(250)
    assert pg.evaluate("[...document.querySelectorAll('#bg-units .bg-segb.on')].map(b => b.getAttribute('data-un'))") == ["roman"]
    for v, rx in (("numbers", ARABIC), ("roman", ROMAN)):
        pg.evaluate(f"document.querySelector('#bg-units .bg-segb[data-un={v}]').click()")       # the same setting, stored the same way
        pg.wait_for_timeout(250)
        g = pg.evaluate(GRAB)
        assert g["mode"] == v and all(rx.match(t) for t in g["numerals"] if t), g
        stored = json.loads(pg.evaluate("localStorage.getItem(window._altoUN.key)"))
        assert set(stored) == {"v", "t"} and stored["v"] == v and stored["t"] > 0
        assert pg.evaluate("[...document.querySelectorAll('#bg-units .bg-segb.on')].map(b => b.getAttribute('data-un'))") == [v]   # the selected one, and only it, is filled
        assert pg.evaluate("[...document.querySelectorAll('#bg-units .bg-segb')].map(b => b.getAttribute('aria-pressed'))") == (["false", "true"] if v == "numbers" else ["true", "false"])
    on = pg.evaluate("""() => { const b = document.querySelector('#bg-units .bg-segb.on'), o = document.querySelector('#bg-units .bg-segb:not(.on)');
      return [getComputedStyle(b).backgroundColor, getComputedStyle(o).backgroundColor]; }""")
    assert on[0] != on[1] and on[0] not in ("rgba(0, 0, 0, 0)", "transparent"), on                 # filled vs not
    for sel in ("#bg-units .bg-h", "#bg-units .bg-segb.on", "#bg-units .bg-segb:not(.on)"):
        w = _worst_glyph_contrast(pg, sel)
        assert w is None or w >= 4.5, (style, phone, sel, round(w, 2))
    assert not _real(errors), errors
    ctx.close()


# ── v1.9.243: on a phone the open Scene panel covers the page: nothing of the page is on top of it or reads through it ──

@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_the_phone_scene_panel_has_no_page_text_over_or_under_it(browser, site, style):
    pg, ctx, errors = _open(browser, site, "system", phone=True)
    if style != "classic":
        pg.evaluate("s => localStorage.setItem(window._altoUN.key.replace(/-un$/, '-style'), s)", style)
        pg.reload()
        pg.wait_for_timeout(2200)
    _open_panel(pg, True)
    if style == "retro":
        pg.evaluate("window._altoSolarStyles && window._altoSolarStyles.set('retro')")
        pg.wait_for_timeout(1500)
    pg.add_style_tag(content="*,*::before,*::after{animation:none !important;transition:none !important}")
    pg.wait_for_timeout(300)
    r = pg.evaluate("""() => { const p = document.getElementById('bg-panel'), bad = [];
      for (let y = 8; y < innerHeight - 8; y += 24) for (let x = 8; x < innerWidth - 8; x += 24) {
        const e = document.elementFromPoint(x, y); if (e && !p.contains(e) && e !== p) bad.push([x, y, e.id || e.tagName]); }
      const cs = getComputedStyle(p), m = /rgba?\\(([^)]*)\\)/.exec(cs.backgroundColor), a = m ? (m[1].split(',')[3] === undefined ? 1 : +m[1].split(',')[3]) : 0;
      return {bad: bad.slice(0, 6), n: bad.length, alpha: a, blur: cs.backdropFilter || cs.webkitBackdropFilter}; }""")
    assert r["n"] == 0, r
    assert r["alpha"] >= .9, r     # opaque enough that the page cannot be read through it
    assert not _real(errors), errors
    ctx.close()
