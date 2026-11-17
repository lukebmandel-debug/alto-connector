"""Holographic's six animated backgrounds as video loops (alto/build/holo_video.py, holo_anim.py), on by default: the still poster (the page's own CSS background) first, the clip
fading in once it plays; Reduce Motion and Save-Data fetch no clip; a hidden tab pauses; the clip is fetched only once Holographic and that background are active; clips are hosted
off the page with byte ranges; the picker offers all six (desktop and phone) and picking each sets it. Browser parts skip without Playwright."""
import re
import sys
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import holo, holo_anim, holo_backgrounds as hb, holo_video                          # noqa: E402
from tests import test_holo_anim as T                                                              # noqa: E402
from tests.test_holo_anim import KIND, browser, _open, _can_h264, _make_site, _outline, pw         # noqa: E402,F401

HVID = "performance.getEntriesByType('resource').filter(e=>e.name.includes('/hvid/')).length"
STEM = holo_video.CLIPS


@pytest.fixture(scope="module")
def vsite(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    srv, url, key = _make_site(tmp_path_factory.mktemp("holovid"))
    yield url, key
    srv.shutdown()
    srv.server_close()


def test_all_six_have_a_clip_and_video_is_the_shipped_mode():
    assert holo_anim.MODE == "video" and set(holo_video.CLIPS) == set(KIND.values())
    assert set(holo_video.paths()) == set(KIND.values())
    for kind, path in holo_video.paths().items():
        assert holo_video.NAME_RE.match(path.split("/")[-1]) and path.startswith("/hvid/" + STEM[kind]), path
        assert 200_000 < (holo_video.VIDEO_DIR / (STEM[kind] + ".mp4")).stat().st_size < 4_500_000
    assert '"mode":"video"' in holo.ASSET and all(p in holo.ASSET for p in holo_video.paths().values())


def test_the_clips_are_hosted_assets_not_page_bytes():
    from alto.build.private_shell import stored_bytes
    page, _ = _outline()
    assert "/hvid/" not in page and "video/mp4" not in page and "<video" not in page
    assert stored_bytes(page) < 700_000


def test_the_clip_url_serves_byte_ranges(vsite):
    url, _ = vsite
    name = holo_video.paths()["target"]
    r = urllib.request.urlopen(urllib.request.Request(url + name, headers={"Range": "bytes=0-99"}))
    assert r.status == 206 and len(r.read()) == 100 and r.headers["Content-Range"].startswith("bytes 0-99/")


def _picker(pg, phone=False):
    pg.evaluate("document.getElementById('bg-panel').classList.contains('open') || document.getElementById('bg-toggle').click()")
    pg.wait_for_timeout(300)


@pytest.mark.parametrize("phone", [False, True])
def test_the_picker_lists_all_six_and_picking_each_sets_it(browser, vsite, phone):
    url, key = vsite
    ctx = browser.new_context(viewport={"width": 390 if phone else 1440, "height": 844 if phone else 900}, has_touch=phone, is_mobile=phone, user_agent=T.IPHONE if phone else None)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url + "/t.html")
    pg.wait_for_timeout(300)
    pg.evaluate("localStorage.clear()")
    pg.evaluate("([k])=>localStorage.setItem(k+'-style','holo')", [key])
    pg.reload()
    pg.wait_for_timeout(900)
    _picker(pg)
    tiles = pg.evaluate("[...document.querySelectorAll('#bg-panel .bg-tile')].map(t=>t.getAttribute('data-bg')).filter(t=>t&&t.startsWith('h-'))")
    assert sorted(tiles) == sorted(i for i, _, _ in hb.HOLO_BGS), tiles
    for bg in tiles:
        _picker(pg)
        pg.evaluate("id=>document.querySelector('#bg-panel .bg-tile[data-bg=\"'+id+'\"]').click()", bg)
        pg.wait_for_timeout(500)
        assert pg.evaluate("window._altoBg.read()") == bg and pg.evaluate("document.documentElement.classList.contains('alto-bg-h')"), bg
        assert pg.evaluate("getComputedStyle(document.getElementById('page-bg'), '::before').backgroundImage").startswith("url(\"data:image/svg+xml")
    assert not errors, errors
    ctx.close()


@pytest.mark.parametrize("phone", [False, True])
@pytest.mark.parametrize("bg", list(KIND))
def test_poster_first_then_the_clip_fades_in_and_loops(browser, vsite, bg, phone):
    pg, ctx, errors = _open(browser, vsite, bg, phone=phone, mode=None, wait=3500)
    assert pg.evaluate("!!document.querySelector('#alto-ha.hv')") and not pg.evaluate("document.getElementById('alto-ha').querySelector('.rn,.rf,.sun,.ring,.ping,.dust')")
    v = pg.evaluate("(()=>{const v=document.querySelector('#alto-ha video'); return {muted:v.muted, loop:v.loop, inline:v.playsInline, src:v.currentSrc, dur:v.duration, w:v.videoWidth, h:v.videoHeight, on:v.classList.contains('on'), op:getComputedStyle(v).opacity}})()")
    assert v["muted"] and v["loop"] and v["inline"] and STEM[KIND[bg]] in v["src"], v
    assert pg.evaluate("getComputedStyle(document.getElementById('page-bg'), '::before').backgroundImage").startswith("url(\"data:image/svg+xml"), "the poster is the page's own background"
    if _can_h264(pg):
        assert v["on"] and v["op"] == "1" and abs(v["dur"] - holo_anim.LOOP) < .05 and v["w"] / v["h"] == 1.6, v
        t1 = pg.evaluate("document.querySelector('#alto-ha video').currentTime")
        pg.wait_for_timeout(1200)
        assert pg.evaluate("document.querySelector('#alto-ha video').currentTime") != t1
    assert pg.evaluate("document.getAnimations().filter(a=>a instanceof CSSAnimation && a.effect.target.closest && a.effect.target.closest('#alto-ha')).length") == 0
    assert not errors, errors
    ctx.close()


@pytest.mark.parametrize("bg", list(KIND))
def test_the_poster_shows_with_no_blank_frame_while_the_clip_has_not_arrived(browser, vsite, bg):
    pg, ctx, errors = _open(browser, vsite, bg, mode=None, wait=1,)
    ctx.route("**/hvid/**", lambda r: r.abort())
    pg.reload()
    pg.wait_for_timeout(1500)
    assert pg.evaluate("getComputedStyle(document.getElementById('page-bg'), '::before').backgroundImage").startswith("url(\"data:image/svg+xml")
    assert not pg.evaluate("!!document.querySelector('#alto-ha video.on')")
    assert pg.evaluate("[...document.querySelectorAll('#alto-ha video')].every(v=>getComputedStyle(v).opacity==='0')")
    ctx.close()


@pytest.mark.parametrize("bg", list(KIND))
def test_reduce_motion_and_save_data_fetch_no_clip(browser, vsite, bg):
    pg, ctx, errors = _open(browser, vsite, bg, mode=None, reduce=True)
    assert pg.evaluate("!!document.getElementById('alto-ha')") is False and pg.evaluate(HVID) == 0
    ctx.close()
    url, key = vsite
    ctx = browser.new_context(viewport={"width": 1400, "height": 860})
    ctx.add_init_script("Object.defineProperty(navigator,'connection',{value:{saveData:true},configurable:true})")
    seen = []
    ctx.on("request", lambda r: seen.append(r.url) if "/hvid/" in r.url else None)
    pg = ctx.new_page()
    pg.goto(url + "/t.html")
    pg.evaluate("([k,b])=>{localStorage.clear(); localStorage.setItem(k+'-style','holo'); localStorage.setItem(k+'-bg', JSON.stringify({v:b,t:Date.now()}))}", [key, bg])
    pg.reload()
    pg.wait_for_timeout(1500)
    assert not seen and pg.evaluate("!!document.getElementById('alto-ha')") is False
    assert pg.evaluate("getComputedStyle(document.getElementById('page-bg'), '::before').backgroundImage").startswith("url(\"data:image/svg+xml")
    ctx.close()


@pytest.mark.parametrize("bg", list(KIND))
def test_a_hidden_tab_pauses_and_a_visible_one_resumes(browser, vsite, bg):
    pg, ctx, errors = _open(browser, vsite, bg, mode=None, wait=3000)
    if not _can_h264(pg):
        ctx.close()
        return
    pg.evaluate("Object.defineProperty(document,'hidden',{get:()=>true,configurable:true}); document.dispatchEvent(new Event('visibilitychange'))")
    pg.wait_for_timeout(400)
    assert pg.evaluate("document.querySelector('#alto-ha video').paused") is True
    pg.evaluate("Object.defineProperty(document,'hidden',{get:()=>false,configurable:true}); document.dispatchEvent(new Event('visibilitychange'))")
    pg.wait_for_timeout(600)
    assert pg.evaluate("document.querySelector('#alto-ha video').paused") is False
    ctx.close()


def test_no_clip_is_fetched_until_holographic_and_a_background_are_active(browser, vsite):
    pg, ctx, errors = _open(browser, vsite, "", style="classic", mode=None, wait=1500)
    assert pg.evaluate(HVID) == 0
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(800)
    assert pg.evaluate(HVID) == 0                      # Holographic without a background of its own choice: nothing
    pg.evaluate("window._altoBg.choose('h-lightspeed')")
    pg.wait_for_timeout(1500)
    assert pg.evaluate(HVID) >= 1
    ctx.close()
