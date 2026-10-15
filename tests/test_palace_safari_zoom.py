"""Mind Palace under the page's CSS zoom, in every engine (the Safari "floating stops" bug, 1.9.70–1.9.73).

The page runs at html{zoom:.8–1} (engine_patches.py #alto-fit: innerWidth/1700, clamped). Safari (WebKit, measured on
WebKit 26.4) multiplies the px inside an SVG element's CSS `transform` by that zoom; Chrome does not. Stops were placed
with `transform:translate(var(--sx),var(--sy))` (--sx in px), so in Safari a stop at map x drew at x·zoom: rings strung
across empty map, up to ~1000 px off toward the city's far corner at zoom .8, their hit circles with them.

The rule these tests hold the palace to: nothing on the map takes its POSITION from a CSS transform. Positions are SVG
transform attributes / x,y in map units; constant-screen-size scaling is a unitless CSS scale on an inner group.
Chromium renders the old code correctly, so the guard that fails on it in Chromium is structural (the static CSS scan
and the computed-transform check); the WebKit test measures the real thing when a WebKit build can be launched and is
skipped otherwise. Offline; nothing here touches the network, Firebase or any ALTO_* setting."""
import copy
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build.builder import build_timeline, load_brief  # noqa: E402
from test_palace_transit import _bundle  # noqa: E402


@pytest.fixture(scope="module")
def html():
    out, _ = build_timeline(*load_brief(copy.deepcopy(_bundle())))
    return out


# ── static: the page's CSS never positions SVG content with a length in `transform` ──
_SVG_SEL = re.compile(r"\.pal-svg|#palace-svg|\.pl-[a-z]|\.tr-(stn|dot|lbl|ring|pulse)|\.dr-(mk|sc|cur|a|b|stop)\b|\.lm-")
_LENGTH = re.compile(r"(-?\d*\.?\d+)(px|em|rem|%|vw|vh)|var\(--s[xy]\)")


def _css(html):
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))


def _offending_rules(css):
    bad = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        sel = sel.strip()
        if sel.startswith("@") or re.match(r"^\d+%|^(from|to)$", sel) or not _SVG_SEL.search(sel):
            continue
        if re.search(r"(^|[^-#.\w])#?(world|pal-|pl-lmbar|aed-)", sel) and ".pal-svg" not in sel and "#palace-svg" not in sel:
            continue                                           # an HTML overlay (#pal-tr, #pl-lmbar …), not SVG content
        for m in re.finditer(r"(?:^|;)\s*transform\s*:\s*([^;]+)", body):
            v = m.group(1)
            if re.search(r"translate|matrix", v) and _LENGTH.search(v):
                bad.append(f"{sel} {{transform:{v}}}")
    return bad


def test_no_svg_content_is_positioned_by_a_length_in_a_css_transform(html):
    bad = _offending_rules(_css(html))
    assert not bad, "a px/% translate in a CSS transform on SVG content moves with the CSS zoom in Safari:\n" + "\n".join(bad)


def test_the_scan_catches_the_old_rules():
    old = (".pal-svg .pl-stn{transform:translate(var(--sx),var(--sy)) scale(var(--tw,1));}"
           ".pal-svg .pl-stt{transform:translate(calc(var(--tw,1) * 13px),calc(var(--tw,1) * -9px));}"
           ".pal-svg .dr-mk{transform:translate(var(--sx),var(--sy)) scale(calc(1 / var(--pz,1)));}"
           ".pal-svg .pl-lmb:hover .lm-art{transform:translateY(-3px);}"
           ".pal-svg .pl-sc{transform:scale(var(--tw,1));}#pal-chiprt{transform:translateX(-50%);}")
    assert len(_offending_rules(old)) == 4


def test_no_stop_or_marker_carries_a_css_px_position(html):
    assert not re.search(r"var\(--s[xy]\)|'--s[xy]:'|setProperty\('--s[xy]'", html)


# ── in a browser ──
pw = pytest.importorskip("playwright.sync_api")

# every element of the map: the translation of its computed transform must be its transform ATTRIBUTE's (0 without one);
# anything else is a CSS-sourced translation, which Safari scales by the CSS zoom
CSS_TRANSLATIONS = """() => { const out=[]; document.querySelectorAll('#palace-svg *').forEach(e => {
  const cs=getComputedStyle(e).transform; if(!cs || cs==='none') return; const m=new DOMMatrix(cs);
  let ax=0, ay=0; const tb=e.transform && e.transform.baseVal; if(tb && tb.numberOfItems){ const c=tb.consolidate().matrix; ax=c.e; ay=c.f; }
  if(Math.abs(m.e-ax)>0.01 || Math.abs(m.f-ay)>0.01) out.push([e.tagName, e.getAttribute('class'), cs, ax, ay]); }); return out; }"""

# each stop ring, stop hit circle and directions marker: drawn minus expected screen centre, in window px
OFFSETS = """async () => { const svg=document.getElementById('palace-svg'), ss=window._palTRx.stops(), D=window._palDir;
  window._palDirOpen({from:D.stPlace(0), to:D.stPlace(2)}); await new Promise(r=>setTimeout(r,300));
  const S0=D.state(); (S0.plans||[]).forEach((o,i)=>{ if(o.rides) S0.opt=i; }); D.draw();      /* the ride, not the walk */
  const m=svg.getScreenCTM(), P=(x,y)=>[m.a*x+m.c*y+m.e, m.b*x+m.d*y+m.f], out=[];
  const ctr=(n)=>{ const r=n.getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; };
  svg.querySelectorAll('.tr-stn').forEach(g => { const s=ss[+g.getAttribute('data-s')], e=P(s.x,s.y), c=ctr(g.querySelector('.tr-ring'));
    out.push(['stop '+s.n, c[0]-e[0], c[1]-e[1]]); });
  svg.querySelectorAll('.pl-stn-hit').forEach(g => { const s=ss[+g.getAttribute('data-s')], e=P(s.x,s.y), c=ctr(g.querySelector('circle'));
    out.push(['hit '+s.n, c[0]-e[0], c[1]-e[1]]); });
  const st=D.state(), opt=st.plans&&st.plans[st.opt], want=[['dr-a', st.from]];
  ((opt&&opt.legs)||[]).forEach(l => { if(l.k==='ride' && l.board) want.push(['dr-stop', l.board], ['dr-stop', l.alight]); });
  const seen={}; want.forEach(([k, at]) => { const gs=svg.querySelectorAll('.dr-mk.'+k), g=gs[seen[k]=(seen[k]||0)]; seen[k]++;
    if(!g || !at) { out.push(['missing '+k, 1e9, 1e9]); return; } const e=P(at.x,at.y), c=ctr(g.querySelector('circle')); out.push(['marker '+k, c[0]-e[0], c[1]-e[1]]); });
  if(want.length<3) out.push(['no ride leg', 1e9, 1e9]);
  D.close(); return {zoom:getComputedStyle(document.documentElement).zoom, out}; }"""


def _open(b, path, zoom=None, w=1500, h=900):
    pg = b.new_page(viewport={"width": w, "height": h})
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(path.as_uri())
    pg.wait_for_timeout(1800)
    if zoom is not None:                                     # the engine's own fit (resize) would undo it: set it last
        pg.evaluate("z => { document.documentElement.style.zoom = z; }", str(zoom))
        pg.wait_for_timeout(300)
    return pg


def _check_positions(pg, tol=0.6):
    r = pg.evaluate(OFFSETS)
    far = [(n, round(dx, 1), round(dy, 1)) for n, dx, dy in r["out"] if abs(dx) > tol or abs(dy) > tol]
    assert len(r["out"]) >= 2 * 4 + 2, r
    assert not far, (r["zoom"], far)
    return r


@pytest.fixture(scope="module")
def page_file(tmp_path_factory, html):
    f = tmp_path_factory.mktemp("palz") / "p.html"
    f.write_text(html, encoding="utf-8")
    return f


@pytest.fixture(scope="module")
def pwr():
    with pw.sync_playwright() as p:
        yield p


@pytest.fixture(scope="module")
def chromium(pwr):
    try:
        b = pwr.chromium.launch()
    except Exception as e:                                   # noqa: BLE001
        pytest.skip(f"no chromium: {e}")
    yield b
    b.close()


def test_no_map_element_takes_a_translation_from_css(chromium, page_file):
    pg = _open(chromium, page_file)
    pg.evaluate("() => { const D=window._palDir; window._palDirOpen({from:D.stPlace(0), to:D.stPlace(2)}); }")
    pg.wait_for_timeout(300)
    pg.evaluate("() => window._palTr.pickStop(1, false)")      # a stop lit / current: its dot's own CSS scale is on
    bad = pg.evaluate(CSS_TRANSLATIONS)
    assert not bad, bad
    assert pg.evaluate("document.querySelectorAll('#palace-svg .tr-stn').length") == 4
    assert not pg.errs, pg.errs
    pg.close()


@pytest.mark.parametrize("zoom", [None, 0.8, 0.88, 1])
def test_stops_hits_and_markers_sit_on_their_map_points_at_every_css_zoom(chromium, page_file, zoom):
    """Chromium draws even the old CSS-translated stops correctly — this pins the geometry; the guard is the test above."""
    pg = _open(chromium, page_file, zoom)
    _check_positions(pg)
    assert not pg.errs, pg.errs
    pg.close()


@pytest.mark.parametrize("w,h", [(1100, 800), (1500, 900)])
def test_in_webkit_stops_hits_and_markers_sit_on_their_map_points(pwr, page_file, w, h):
    """The real Safari engine. Skipped when this Playwright's WebKit build is not installed (no download is attempted)."""
    try:
        b = pwr.webkit.launch()
    except Exception as e:                                   # noqa: BLE001
        pytest.skip(f"no WebKit build for this Playwright: {str(e).splitlines()[0][:120]}")
    try:
        pg = _open(b, page_file, None, w, h)
        r = _check_positions(pg)
        assert float(r["zoom"]) < 1                            # the zoom that used to throw the stops off is on
        assert not pg.evaluate(CSS_TRANSLATIONS)
        assert not pg.errs, pg.errs
    finally:
        b.close()
