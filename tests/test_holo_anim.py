"""Holographic's animated backgrounds (alto/build/holo_anim.py; Luke, 2026-11-05: "each holographic background should have its own animation"): A falling signal on
Signal rain, B scan sweep on Grid horizon, C slow lightspeed on Lightspeed; and Art's second sheet, approved with "make rain a little calmer": D neon rain on Neon rain,
E amber haze on Amber haze, F targeting on Targeting. All six. Transform and opacity only; Reduce Motion stops all; print hides them; a phone has none;
the code is in the hosted Holographic script, the page holds none of it. The browser parts are skipped when Playwright is not installed."""
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

from alto.build import backgrounds_import as bi, holo, holo_anim, holo_backgrounds as hb, holo_video, retro      # noqa: E402
from alto.build.builder import build_timeline, load_brief                                          # noqa: E402
from alto.build.blocks import ID_PATTERNS                                                          # noqa: E402
from tests.range_server import serve                                                              # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
KIND = {"h-signal-rain": "rain", "h-grid-horizon": "sweep", "h-lightspeed": "drift", "h-neon-rain": "neon", "h-amber-haze": "haze", "h-targeting": "target"}
COUNT = {"rain": 3, "sweep": 1, "drift": 2, "neon": 4, "haze": 3, "target": 3}


def _outline():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0], d["brief"]["timeline_id"]


def test_each_animation_is_on_the_background_it_was_shown_over_and_all_ids_exist():
    assert holo_anim.IDS == KIND
    ids = {i for i, _, _ in hb.HOLO_BGS}
    assert set(KIND) == ids, "every Holographic background has its own animation"


def test_the_animation_uses_transform_and_opacity_only():
    frames = re.findall(r"@keyframes ha-[\w-]+\{(.*?)\}\}", holo_anim.CSS)
    assert len(frames) == 13, frames
    props = {p for f in frames for p in re.findall(r"([a-z-]+):", f)}
    assert props == {"transform", "opacity"}, props
    assert "will-change:transform" in holo_anim.CSS


def test_reduce_motion_print_and_phones_are_in_the_rules():
    c = holo_anim.CSS
    assert "prefers-reduced-motion:no-preference" in c and "min-width:641px" in c and ":not(.mobile)" in c
    assert re.search(r"@media print\{#alto-ha\{display:none !important\}\}", c)
    assert "html.hp-hid #alto-ha *{animation-play-state:paused}" in c


def test_it_rides_in_the_hosted_script_and_the_page_holds_none_of_it():
    page, _ = _outline()
    for needle in ("alto-ha", "ha-sweep", "ha-fall1", "ha-drift", "hasync", "ha-nfall", "ha-flick", "ha-breathe", "ha-ping", "ha-turn1", "ha-dnear"):
        assert needle in holo.ASSET and needle not in page, needle


def _make_site(d, css_only=False):
    """The page and the hosted scripts in folder d (and the clip under /hvid/), served with byte ranges (WebKit will not play a video from a server without them).
    css_only: the hosted script names no clip, so Neon rain draws its CSS animation."""
    page, tid = _outline()
    (d / "t.html").write_text(page, encoding="utf-8")
    (d / "holo").mkdir()
    (d / "retro").mkdir()
    n, t = holo.holo_asset()
    if css_only:
        t = re.sub(r'"vid":\{[^}]*\}', '"vid":{}', t)
    (d / "holo" / n).write_text(t, encoding="utf-8")
    n, t = retro.retro_asset()
    (d / "retro" / n).write_text(t, encoding="utf-8")
    lib, js = bi.site_file()
    (d / lib).write_text(js, encoding="utf-8")
    (d / holo_video.FOLDER).mkdir()
    for name, b in holo_video.files():
        (d / holo_video.FOLDER / name).write_bytes(b)
    srv, url = serve(d)
    return srv, url, ID_PATTERNS["hl_key"].format(tid=tid)


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    srv, url, key = _make_site(tmp_path_factory.mktemp("holoanim"))
    yield url, key
    srv.shutdown()
    srv.server_close()


@pytest.fixture(scope="module")
def css_site(tmp_path_factory):
    """Neon rain without its clip: the CSS layer, which is also what a page falls back to."""
    if pw is None:
        pytest.skip("Playwright is not installed")
    srv, url, key = _make_site(tmp_path_factory.mktemp("holoanimcss"), css_only=True)
    yield url, key
    srv.shutdown()
    srv.server_close()


@pytest.fixture(params=["webkit", "chromium"])
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


def _open(browser, site, bg, style="holo", phone=False, reduce=False, wait=1500, no_clip=False, mode="all"):
    """mode: the QA key alto-holo-anim (holo_anim.MODE); "all" is the design reference these tests pin, None = what ships."""
    url, key = site
    ctx = browser.new_context(viewport={"width": 390 if phone else 1400, "height": 844 if phone else 860}, has_touch=phone, is_mobile=phone,
                              user_agent=IPHONE if phone else None, reduced_motion="reduce" if reduce else "no-preference")
    if no_clip:
        ctx.route("**/hvid/**", lambda r: r.abort())
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url + "/t.html")
    pg.wait_for_timeout(300)
    pg.evaluate("localStorage.clear()")
    pg.evaluate("([k,b,s,m])=>{ localStorage.setItem(k+'-style', s); if(b) localStorage.setItem(k+'-bg', JSON.stringify({v:b,t:Date.now()})); if(m) localStorage.setItem('alto-holo-anim', m); }", [key, bg, style, mode])
    pg.reload()
    pg.wait_for_timeout(wait)
    return pg, ctx, errors


RUNNING = "document.getAnimations().filter(a=>a.playState==='running' && a.effect && a.effect.target && a.effect.target.closest && a.effect.target.closest('#alto-ha')).length"


CLIP = bool(holo_video.paths())     # a kind with a clip file plays it (Neon rain); its CSS animation is the fallback


@pytest.mark.parametrize("bg,kind,count", [(b, k, COUNT[k]) for b, k in KIND.items()])
def test_each_background_runs_its_own_animation_behind_the_content(browser, site, bg, kind, count):
    pg, ctx, errors = _open(browser, site, bg)
    assert pg.evaluate("document.querySelector('#alto-ha').className") == "ha ha-" + kind
    if kind in holo_video.paths() and pg.evaluate("!!document.querySelector('#alto-ha video')") and pg.evaluate("document.querySelector('#alto-ha video.on')"):
        count = 0                                                      # played by the video, not by the compositor
    assert pg.evaluate(RUNNING) == count
    assert pg.evaluate("getComputedStyle(document.getElementById('alto-ha')).display") == "block"
    assert pg.evaluate("document.body.firstElementChild.id") == "alto-ha"
    # under the content: a card or a bar at a point is what is hit, never the layer, and the layer takes no pointer
    assert pg.evaluate("getComputedStyle(document.getElementById('alto-ha')).pointerEvents") == "none"
    assert pg.evaluate("document.elementFromPoint(700, 400).closest('#alto-ha')") is None
    props = pg.evaluate("[...new Set(document.getAnimations().filter(a=>a.effect.target.closest('#alto-ha')).flatMap(a=>a.effect.getKeyframes().flatMap(k=>Object.keys(k))))].filter(k=>!['offset','easing','composite','computedOffset'].includes(k)).sort()")
    assert set(props) <= {"transform", "opacity"}, props
    assert not errors, errors
    ctx.close()


def test_no_background_or_classic_has_no_layer_and_switching_adds_and_removes_it(browser, site):
    pg, ctx, errors = _open(browser, site, "", style="holo")
    assert pg.evaluate("!!document.getElementById('alto-ha')") is False
    pg.evaluate("window._altoBg.choose('h-grid-horizon')")
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.querySelector('#alto-ha').className") == "ha ha-sweep"
    pg.evaluate("window._altoBg.choose('h-lightspeed')")
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.querySelector('#alto-ha').className") == "ha ha-drift" and pg.evaluate(RUNNING) == 2
    pg.evaluate("window._altoStyle.set('classic')")
    pg.wait_for_timeout(500)
    assert pg.evaluate("!!document.getElementById('alto-ha')") is False
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(700)
    assert pg.evaluate("!!document.getElementById('alto-ha')") is True
    assert not errors, errors
    ctx.close()


@pytest.mark.parametrize("bg", list(KIND))
def test_reduce_motion_stops_all_of_them(browser, site, bg):
    pg, ctx, errors = _open(browser, site, bg, reduce=True)
    assert pg.evaluate("!!document.getElementById('alto-ha')") is False and pg.evaluate("document.getAnimations().filter(a=>a.effect.target.closest && a.effect.target.closest('#alto-ha')).length") == 0
    ctx.close()


def test_reduce_motion_switched_on_while_open_removes_the_layer(browser, site):
    pg, ctx, errors = _open(browser, site, "h-signal-rain")
    assert pg.evaluate(RUNNING) == 3
    pg.emulate_media(reduced_motion="reduce")
    pg.wait_for_timeout(500)
    assert pg.evaluate("!!document.getElementById('alto-ha')") is False
    ctx.close()


@pytest.mark.parametrize("bg", list(KIND))
def test_print_hides_them(browser, site, bg):
    pg, ctx, errors = _open(browser, site, bg)
    pg.emulate_media(media="print")
    assert pg.evaluate("getComputedStyle(document.getElementById('alto-ha')).display") == "none"
    ctx.close()


@pytest.mark.parametrize("bg", list(KIND))
def test_a_phone_has_none(browser, site, bg):
    pg, ctx, errors = _open(browser, site, bg, phone=True)
    assert pg.evaluate("!!document.getElementById('alto-ha')") is False
    assert not errors, errors
    ctx.close()


def test_a_hidden_tab_pauses_them(browser, site):
    pg, ctx, errors = _open(browser, site, "h-grid-horizon")
    pg.evaluate("document.documentElement.classList.add('hp-hid')")
    assert pg.evaluate("document.getAnimations().filter(a=>a.effect.target.closest && a.effect.target.closest('#alto-ha') && a.playState==='running').length") == 0
    ctx.close()


# ── the second sheet (neon rain, amber haze, targeting) ──

def test_the_rain_is_calmer_than_the_sheets_demo_and_the_flicker_is_gentle():
    """Luke: "make rain a little calmer": the demo's near and far sheets passed in 2.6 s and 4.8 s with 22 and 30 streaks; these are slower and sparser. The sign flicker is a
    soft dip, never a strobe: no step under 120 ms and at most two dips in any one second (WCAG 2.3.1 allows three)."""
    css = holo_anim.CSS
    near, far = (float(x) for x in re.findall(r"\.ha-neon \.r[nf] i\{background:var\(--ha-r[nf]\);animation:ha-nfall ([\d.]+)s", css))
    assert near >= 3.5 and far >= 6 and far > near
    from urllib.parse import unquote
    tiles = re.findall(r"--ha-r[nf]:(url\(.*?\))[;}]", css)
    counts = [unquote(t).count("<path") for t in tiles]
    assert len(counts) == 2 and counts[0] <= 16 and counts[1] <= 22, counts
    kf = re.search(r"@keyframes ha-flick\{(.*?)\}\}", css).group(1)
    steps = [(float(p.split(",")[-1]), float(v)) for p, v in re.findall(r"([\d.,%]+)\{opacity:([\d.]+)\}", kf.replace("%", ""))]
    assert max(v for _, v in steps) <= .85 and "steps(" not in css.split("ha-flick")[0].split(".ha-neon .sg")[-1]
    times = [t for t, _ in steps]
    assert min(b - a for a, b in zip(times, times[1:])) / 100 * holo_anim.LOOP >= .12        # the shortest ramp, on a sign (12 s a dip)
    assert sum(1 for (_, a), (_, b) in zip(steps, steps[1:]) if a < .3 <= b) <= 2


def test_the_two_signs_stand_on_the_scenes_own_signs_and_the_sun_and_display_on_theirs():
    sg = holo_anim._signs()
    assert [(round(x * 16), round(y * 10)) for x, y, _, _ in (sg[2], sg[4])] == [(819, 600), (1187, 798)]
    assert hb.neon_rain()  # the picture they were found in
    c = holo_anim.CSS
    assert "left:51.19%;top:60.00%" in c and "left:74.19%;top:79.80%" in c
    # amber haze's sun and targeting's display sit where the pictures draw them (amber: cx .62 cy .62 r .35; targeting 1150,520 of 1600,1000)
    assert re.search(r"\.ha-haze \.sun\{left:37\.13%;top:22\.2%;width:49\.75%;height:79\.6%", c)
    assert "left:71.875%" in c and "top:35%" in c and "top:14%" in c        # the display's middle: r1 top 52% - 34%/2, r2 52% - 76%/2


@pytest.mark.parametrize("w,h", [(1400, 860), (1000, 900), (2200, 800)])
def test_the_scene_box_lies_exactly_over_the_backgrounds_picture(browser, site, w, h):
    """The picture is #page-bg::before (40px past the window on three sides, `cover`, bottom-centred) on a page zoomed by html{zoom}: the box must be the same rectangle."""
    pg, ctx, errors = _open(browser, site, "h-amber-haze")
    pg.set_viewport_size({"width": w, "height": h})
    pg.wait_for_timeout(500)
    r = pg.evaluate("""(()=>{const b=document.querySelector('#alto-ha .ha-scene').getBoundingClientRect(), z=parseFloat(getComputedStyle(document.documentElement).zoom)||1,
      cs=getComputedStyle(document.getElementById('page-bg'),'::before'); return [b.left,b.top,b.width,b.height,z,parseFloat(cs.width)*z,parseFloat(cs.height)*z,parseFloat(cs.left)*z,parseFloat(cs.top)*z]})()""")
    pw_, ph_ = r[5], r[6]                                     # the picture's area in window pixels
    s = max(pw_ / 1600, ph_ / 1000)
    left, bottom = r[7] + (pw_ - 1600 * s) / 2, r[8] + ph_
    assert abs(r[2] - 1600 * s) < 1.5 and abs(r[3] - 1000 * s) < 1.5, r
    assert abs(r[0] - left) < 1.5 and abs(r[1] + r[3] - bottom) < 1.5, r
    ctx.close()


def test_the_sign_covers_land_on_the_pictures_signs(browser, css_site):
    pg, ctx, errors = _open(browser, css_site, "h-neon-rain")
    got = pg.evaluate("[...document.querySelectorAll('#alto-ha .sg')].map(e=>{const b=e.getBoundingClientRect(),s=document.querySelector('#alto-ha .ha-scene').getBoundingClientRect();return [(b.left-s.left)/s.width*1600,(b.top-s.top)/s.height*1000,b.width/s.width*1600,b.height/s.height*1000]})")
    assert [round(g[0]) for g in got] == [819, 1187] and [round(g[1]) for g in got] == [600, 798] and all(g[3] > 130 for g in got), got
    assert not errors, errors
    ctx.close()


@pytest.mark.parametrize("w,h", [(2560, 1000), (1400, 860), (700, 1200)])
def test_the_rain_sheet_covers_every_corner(browser, css_site, w, h):
    pg, ctx, errors = _open(browser, css_site, "h-neon-rain")
    pg.set_viewport_size({"width": w, "height": h})
    pg.wait_for_timeout(500)
    bad = pg.evaluate("""[...document.querySelectorAll('#alto-ha .rn, #alto-ha .rf')].map(e=>{const b=e.getBoundingClientRect(), a=12*Math.PI/180, c=Math.cos(a), s=Math.sin(a), d=c*c-s*s;
      // the rotated sheet's bounding box -> its own width and height, then the four window corners in the sheet's frame
      const W=(b.width*c-b.height*s)/d, H=(b.height*c-b.width*s)/d, cx=b.left+b.width/2, cy=b.top+b.height/2;
      return [[0,0],[innerWidth,0],[0,innerHeight],[innerWidth,innerHeight]].filter(([x,y])=>{const dx=x-cx, dy=y-cy, u=dx*c+dy*s, v=-dx*s+dy*c; return Math.abs(u)>W/2||Math.abs(v)>H/2}).length}).reduce((a,b)=>a+b,0)""")
    assert bad == 0
    ctx.close()


def test_every_new_layer_stays_under_the_content_and_takes_no_pointer(browser, site):
    for bg in ("h-neon-rain", "h-amber-haze", "h-targeting"):
        pg, ctx, errors = _open(browser, site, bg)
        assert pg.evaluate("[...document.querySelectorAll('#alto-ha *')].every(e=>getComputedStyle(e).pointerEvents==='none')")
        assert pg.evaluate("document.elementFromPoint(700, 400).closest('#alto-ha')") is None
        assert not errors, errors
        ctx.close()


# ── Targeting: sizes without aspect-ratio (WebKit drew the turning ring at 80%), and the picture without its own dashed rings while the layer runs ──

def test_targeting_rings_and_ping_have_explicit_sizes_not_aspect_ratio():
    t = re.search(r"\.ha-target \.ping\{(.*?)\}", holo_anim.CSS).group(1) + re.search(r"\.ha-target \.ring\{(.*?)\}", holo_anim.CSS).group(1)
    assert "aspect-ratio" not in t
    assert "width:21.25%;height:34%" in holo_anim.CSS and "width:47.5%;height:76%" in holo_anim.CSS
    assert "transform-origin" not in re.search(r"\.ha-target \.pa\{.*?\}", holo_anim.CSS).group(0)     # the ping swells about a zero-size anchor


def test_the_turning_rings_and_ping_are_the_size_of_the_pictures_rings(browser, site):
    pg, ctx, errors = _open(browser, site, "h-targeting")
    for w, h in ((1400, 860), (2200, 800)):
        pg.set_viewport_size({"width": w, "height": h})
        pg.wait_for_timeout(500)
        got = pg.evaluate("""(()=>{document.getAnimations().forEach(a=>{a.pause(); a.currentTime=0});     // a ring turns and the ping swells: read them at rest
          const s=document.querySelector('#alto-ha .ha-scene').getBoundingClientRect(), u=s.width/1600;
          const m=c=>{const b=document.querySelector('#alto-ha '+c).getBoundingClientRect(); return [b.width/u, b.height/u, (b.left+b.width/2-s.left)/u, (b.top+b.height/2-s.top)/u]};
          return {r1:m('.r1'), r2:m('.r2'), ping:m('.ping')}})()""")
        for k in ("r1", "r2", "ping"):            # the display's middle is (1150, 520) of the picture: WebKit once put a ring 28px low (translateY(-50%) under the page zoom)
            assert abs(got[k][2] - 1150) < 3 and abs(got[k][3] - 520) < 3, (w, h, k, got)
        # the scene's own rings: 2 x 170, 2 x 380 and the ping's 2 x 520 (at its end size; it starts at .17 of it)
        for k, d in (("r1", 340), ("r2", 760)):
            assert abs(got[k][0] - d) < 3 and abs(got[k][1] - d) < 3, (w, h, got)       # square, and not letterboxed short as WebKit's aspect-ratio did
        assert abs(got["ping"][0] - 1040 * .17) < 4 and abs(got["ping"][1] - 1040 * .17) < 4, (w, h, got)
        # and while they move (WebKit once scaled the ping about a point 28px off): the ping's and the rings' middles stay on the display's middle
        for ms in (400, 1500, 3000, 20000):
            mid = pg.evaluate("""t=>{document.getAnimations().forEach(a=>{a.pause();a.currentTime=t}); const s=document.querySelector('#alto-ha .ha-scene').getBoundingClientRect(), u=s.width/1600;
              return ['.ping','.r1','.r2'].map(c=>{const b=document.querySelector('#alto-ha '+c).getBoundingClientRect(); return [(b.left+b.width/2-s.left)/u, (b.top+b.height/2-s.top)/u]})}""", ms)
            assert all(abs(x - 1150) < 3 and abs(y - 520) < 3 for x, y in mid), (w, h, ms, mid)
    assert not errors, errors
    ctx.close()


def _scene_has_dashes(pg):
    return pg.evaluate("getComputedStyle(document.getElementById('page-bg'),'::before').backgroundImage.includes('stroke-dasharray')")


def test_the_picture_has_no_dashed_rings_only_while_the_targeting_layer_runs(browser, site):
    pg, ctx, errors = _open(browser, site, "h-targeting")
    assert pg.evaluate("document.documentElement.classList.contains('ha-nd')") and not _scene_has_dashes(pg)
    pg.emulate_media(media="print")
    assert _scene_has_dashes(pg)                                 # print: no layer, today's scene
    pg.emulate_media(media="screen")
    pg.emulate_media(reduced_motion="reduce")
    pg.wait_for_timeout(500)
    assert not pg.evaluate("document.documentElement.classList.contains('ha-nd')") and _scene_has_dashes(pg)
    pg.emulate_media(reduced_motion="no-preference")
    pg.wait_for_timeout(500)
    assert not _scene_has_dashes(pg)
    pg.evaluate("window._altoBg.choose('h-neon-rain')")
    pg.wait_for_timeout(500)
    assert not pg.evaluate("document.documentElement.classList.contains('ha-nd')")
    pg.evaluate("window._altoBg.choose('h-targeting')")
    pg.wait_for_timeout(500)
    assert not _scene_has_dashes(pg)
    pg.evaluate("window._altoStyle.set('classic')")
    pg.wait_for_timeout(500)
    assert not pg.evaluate("document.documentElement.classList.contains('ha-nd')")
    assert not errors, errors
    ctx.close()


def test_reduce_motion_and_a_phone_keep_the_scene_with_its_rings(browser, site):
    pg, ctx, errors = _open(browser, site, "h-targeting", reduce=True)
    assert _scene_has_dashes(pg) and not pg.evaluate("document.documentElement.classList.contains('ha-nd')")
    ctx.close()
    pg, ctx, errors = _open(browser, site, "h-targeting", phone=True)
    assert _scene_has_dashes(pg) and not pg.evaluate("document.documentElement.classList.contains('ha-nd')")
    ctx.close()


def test_the_scene_without_dashes_is_the_same_scene_otherwise():
    from urllib.parse import unquote
    a, b = unquote(hb.targeting()[1]["b"]), unquote(hb.targeting(False)[1]["b"])
    assert a.count("<circle") == 5 and b.count("<circle") == 3 and "stroke-dasharray" not in b
    assert a.split(" center bottom")[1] == b.split(" center bottom")[1]
    assert hb.targeting()[1]["b"] == hb.client_entries()["h-targeting"]["d"]["b"], "the picture everyone else sees is unchanged"


# ── Neon rain as a looping video (holo_video.py; Luke: "a lofi background music animation that repeats ... even 10 second loop is fine, just make transition smooth") ──

def test_neon_rain_is_periodic_over_its_loop_so_the_last_frame_runs_into_the_first():
    css = holo_anim.CSS
    loop = holo_anim.LOOP
    assert 10 <= loop <= 12
    per = [float(x) for x in re.findall(r"animation:ha-nfall ([\d.]+)s", css)] + [float(x) for x in re.findall(r"\.ha-neon \.sg:nth-of-type\(\d\)\{[^}]*animation-duration:([\d.]+)s", css)]
    assert len(per) == 4 and all(abs(loop / p - round(loop / p)) < 1e-9 for p in per), (loop, per)
    # a rain pass moves exactly one tile (300px), so after a whole number of passes the sheet is where it began
    assert re.search(r"@keyframes ha-nfall\{to\{transform:translateY\(300px\)\}\}", css) and "500' height='300'" in holo_anim._neon_tiles()
    assert "ha-flick 12s" in css and holo_anim.LOOP == 12


def test_the_clip_is_hosted_off_the_page_by_content_hash_and_named_only_by_the_hosted_script():
    if not holo_video.paths():
        pytest.skip("no clip file")
    (name, data), = holo_video.files()
    assert holo_video.NAME_RE.match(name) and data[4:8] == b"ftyp" and len(data) < 6_000_000, (name, len(data))
    assert holo_video.paths() == {"neon": "/hvid/" + name}
    assert name in holo.ASSET and "hvid" not in _outline()[0] and name not in _outline()[0], "the page holds no video and no path"
    from alto import publish_static as ps
    assert holo_video.FOLDER in ps.HOSTED_REF_RE.pattern
    rules = [h for h in ps._headers("x", "y", hv_files=[name]) if h["source"] == "/hvid/" + name]
    assert len(rules) == 1 and "immutable" in rules[0]["headers"][0]["value"]


def _can_h264(pg):
    return bool(pg.evaluate("document.createElement('video').canPlayType('video/mp4; codecs=\"avc1.640028\"')"))


def test_neon_rain_plays_as_a_muted_looping_inline_video_that_fills_the_scene_box(browser, site):
    if not holo_video.paths():
        pytest.skip("no clip file")
    pg, ctx, errors = _open(browser, site, "h-neon-rain", wait=3500)
    if not _can_h264(pg):                                     # a Chromium build without the proprietary codecs: the CSS layer takes over (next test); real Chrome and Safari have it
        assert pg.evaluate(RUNNING) == 4 and not pg.evaluate("!!document.querySelector('#alto-ha video.on')")
        ctx.close()
        return
    v = pg.evaluate("""(()=>{const v=document.querySelector('#alto-ha video'), s=document.querySelector('#alto-ha .ha-scene').getBoundingClientRect(), b=v.getBoundingClientRect();
      return {muted:v.muted, loop:v.loop, inline:v.playsInline, auto:v.autoplay, paused:v.paused, t:v.currentTime, dur:v.duration, w:v.videoWidth, h:v.videoHeight, on:v.classList.contains('on'),
              op:getComputedStyle(v).opacity, src:v.currentSrc, box:[b.left-s.left,b.top-s.top,b.width-s.width,b.height-s.height], nodes:document.querySelectorAll('#alto-ha .rn,#alto-ha .rf,#alto-ha .sg').length}})()""")
    assert v["muted"] and v["loop"] and v["inline"] and v["auto"] and not v["paused"] and v["t"] > 0.5 and v["on"] and v["op"] == "1", v
    assert abs(v["dur"] - holo_anim.LOOP) < .05 and v["w"] / v["h"] == 1.6, v
    assert "/hvid/neon-rain-" in v["src"] and all(abs(x) < 1.5 for x in v["box"]) and v["nodes"] == 0, v
    assert pg.evaluate(RUNNING) == 0, "no CSS animation runs behind the clip"
    # it is the loop: it is still playing, and has wrapped, after a loop's worth of time
    t1 = pg.evaluate("document.querySelector('#alto-ha video').currentTime")
    pg.wait_for_timeout(1500)
    assert pg.evaluate("document.querySelector('#alto-ha video').currentTime") != t1
    assert not errors, errors
    ctx.close()


def test_a_clip_that_cannot_load_falls_back_to_the_css_animation(browser, site):
    pg, ctx, errors = _open(browser, site, "h-neon-rain", no_clip=True, wait=2000)
    assert pg.evaluate("!!document.querySelector('#alto-ha video')") is False
    assert pg.evaluate(RUNNING) == 4 and pg.evaluate("document.querySelectorAll('#alto-ha .rn,#alto-ha .rf,#alto-ha .sg').length") == 4
    assert not errors, errors
    ctx.close()


def test_reduce_motion_fetches_no_clip_and_a_phone_none_either(browser, site):
    for kw in ({"reduce": True}, {"phone": True}):
        pg, ctx, errors = _open(browser, site, "h-neon-rain", **kw)
        assert pg.evaluate("!!document.getElementById('alto-ha')") is False
        assert pg.evaluate("performance.getEntriesByType('resource').filter(e=>e.name.includes('/hvid/')).length") == 0
        ctx.close()


def test_a_hidden_tab_pauses_the_clip_and_showing_it_again_plays_it(browser, site):
    if not holo_video.paths():
        pytest.skip("no clip file")
    pg, ctx, errors = _open(browser, site, "h-neon-rain", wait=3000)
    if not _can_h264(pg):
        ctx.close()
        return
    pg.evaluate("document.documentElement.classList.add('hp-hid')")
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.querySelector('#alto-ha video').paused") is True
    pg.evaluate("document.documentElement.classList.remove('hp-hid')")
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.querySelector('#alto-ha video').paused") is False
    ctx.close()


# ---- what ships (holo_anim.MODE, Board B-1105-190000): still by default; Neon rain's clip behind the flag; never a CSS loop ----

HA_NET = "performance.getEntriesByType('resource').filter(e=>e.name.includes('/hvid/')).length"


def test_the_shipped_mode_is_still_and_the_flag_names_only_known_modes():
    assert holo_anim.MODE == "still" and holo_anim.MODES == ("still", "video", "all")
    assert '"mode":"still"' in holo.ASSET
    assert "ha-nfall" not in holo.css(), "the layer's rules are not in the page's Holographic rules: they go in with a layer"


@pytest.mark.parametrize("bg", list(KIND))
def test_shipped_every_background_is_still_no_layer_no_rules_no_clip(browser, site, bg):
    pg, ctx, errors = _open(browser, site, bg, mode=None, wait=1200)
    assert pg.evaluate("[!!document.getElementById('alto-ha'), !!document.getElementById('alto-ha-css'), document.documentElement.classList.contains('ha-nd')]") == [False, False, False]
    assert pg.evaluate(HA_NET) == 0
    assert pg.evaluate("document.getAnimations().length") == 0 or pg.evaluate(RUNNING) == 0
    assert not errors, errors
    ctx.close()


def test_video_mode_plays_only_neon_rains_clip_and_leaves_the_rest_still(browser, site):
    for bg in KIND:
        pg, ctx, errors = _open(browser, site, bg, mode="video", wait=2500 if bg == "h-neon-rain" else 1000)
        has = pg.evaluate("!!document.getElementById('alto-ha')")
        if KIND[bg] in holo_video.paths():
            if _can_h264(pg):
                assert has and pg.evaluate("!!document.querySelector('#alto-ha video.on')"), bg
            assert pg.evaluate(RUNNING) == 0, "never a CSS loop"
        else:
            assert not has and pg.evaluate(HA_NET) == 0, bg
        assert not errors, errors
        ctx.close()


def test_video_mode_a_clip_that_cannot_load_leaves_the_still_background(browser, site):
    pg, ctx, errors = _open(browser, site, "h-neon-rain", mode="video", no_clip=True, wait=2000)
    assert pg.evaluate("!!document.getElementById('alto-ha')") is False and pg.evaluate(RUNNING) == 0
    assert not errors, errors
    ctx.close()


def test_no_layer_work_before_the_page_has_loaded(browser, site):
    url, key = site
    ctx = browser.new_context(viewport={"width": 1400, "height": 860})
    pg = ctx.new_page()
    pg.goto(url + "/t.html")
    pg.evaluate("([k])=>{ localStorage.setItem(k+'-style','holo'); localStorage.setItem(k+'-bg', JSON.stringify({v:'h-signal-rain',t:Date.now()})); localStorage.setItem('alto-holo-anim','all'); }", [key])
    # record whether the layer existed before window 'load' fired
    pg.add_init_script("window.__haPre=null; addEventListener('load', function(){ window.__haPre=!!document.getElementById('alto-ha'); }, {capture:true});")
    pg.reload()
    pg.wait_for_timeout(1200)
    assert pg.evaluate("window.__haPre") is False
    assert pg.evaluate("!!document.getElementById('alto-ha')") is True
    ctx.close()
