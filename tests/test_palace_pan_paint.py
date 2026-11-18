"""Memory Map pans and zooms without the per-tile stroke re-transform (Luke 2026-11-18: "still slow and glitchy to move around scrolling on the mouse").

Root cause, measured in WebKit on the New York preset (1440x900, DPR 2): every path with `vector-effect:non-scaling-stroke` is transformed
again for every tile WebKit paints, whether it is seen or not. The board had 3,316 invisible street hit lines, the parks' outlines and the
landmark art drawn that way, so a pan that exposed new map spent 200-300 ms a frame painting (p95 243 ms, 51 frames over 50 ms in a
2.4 s wheel pan). The board's big layers now take their screen width from --nss (one screen px in map units, set with --pz at each settle),
and the hit layers are not painted at all (visibility:hidden still hit-tests with pointer-events:stroke). Pixel-identical at rest.

Offline; nothing here touches the network, Firebase or any ALTO_* setting."""
import copy
import glob
import math
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace, palace_place as pp  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from test_palace import BBOX, bundle, city_map  # noqa: E402

# the board's layers that used to be non-scaling, and their widths in screen px
SRC = (ROOT / "alto" / "build" / "palace.py").read_text("utf-8")
WIDTHS = {"pl-hit": 14, "pl-route-hit": 18, "pl-pk": 1.5, "pl-glass": 1.5}
LZ = ("lz-f", "lz-sd", "lz-tp", "lz-ln", "lz-mu", "lz-col-l", "lz-hi", "lz-seal", "lz-mark")


def _rules(css, cls):
    """Every rule body whose selector names .cls, in order."""
    return [(sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)
            if re.search(r"\." + re.escape(cls) + r"(?![\w-])", sel)]


def _board_wins(css, cls):
    """The last #palace-svg rule for .cls sets vector-effect:none and a --nss width (it outranks the .pal-svg rule: an id)."""
    own = [(s, b) for s, b in _rules(css, cls) if "#palace-svg" in s and "vector-effect" in b]
    return bool(own) and "vector-effect:none" in own[-1][1].replace(" ", "") and "--nss" in own[-1][1]


def test_the_boards_big_layers_are_not_non_scaling_strokes():
    css = palace.PALACE_CSS
    for cls in list(WIDTHS) + list(LZ):
        assert _board_wins(css, cls), f".{cls} on the desktop board still paints as a non-scaling stroke"
    assert re.search(r"#palace-svg :is\([^)]*\.pl-hits[^)]*\)\{visibility:hidden;\}", css), "the street hit lines are painted"
    assert "svgD.style.setProperty('--nss'" in palace.PALACE_JS


def test_the_widths_are_the_ones_the_non_scaling_rules_had():
    css = palace.PALACE_CSS
    for cls, w in WIDTHS.items():
        own = [b for s, b in _rules(css, cls) if "#palace-svg" in s and "--nss" in b][-1]
        assert re.search(r"calc\(var\(--nss,1\) \* %spx\)" % re.escape(str(w)), own), (cls, own)
        old = [b for s, b in _rules(SRC, cls) if re.search(r"\.pal-svg \.%s$" % re.escape(cls), s) and "non-scaling-stroke" in b]
        assert old and re.search(r"stroke-width:%s(px)?;" % re.escape(str(w)), old[0]), (cls, old)


def test_the_phone_map_keeps_its_own_rules():
    """The phone's map (#palace-svg-m) is untouched: only the desktop board (#palace-svg) is overridden."""
    css = palace.PALACE_CSS
    assert ".pal-svg .pl-hit{fill:none;stroke:transparent;stroke-width:14;pointer-events:stroke;vector-effect:non-scaling-stroke;}" in css
    assert not re.search(r"#palace-svg-m[^{]*\{[^}]*--nss", css)


# ── in WebKit: the cost it measures, on a synthetic city full of long streets ──
pw = pytest.importorskip("playwright.sync_api")

N = 70          # streets each way
W = H = 7000    # map units


def _big_city():
    m = city_map()
    m.update(W=W, H=H, water=[], rivers=[], rails=[], stations=[], landmarks=[], majors=[])
    rnd = 1
    streets = []
    for i in range(N):
        for horiz in (0, 1):
            pts = []
            for j in range(0, 141):
                t = j * W / 140
                rnd = (rnd * 16807) % 2147483647
                wob = (rnd % 9) - 4
                c = (i + .5) * W / N + wob
                pts += [t, c] if horiz else [c, t]
            streets.append({"n": f"{'Row' if horiz else 'Col'} {i} Street", "k": 4, "p": pts})
    m["streets"] = streets
    m["parks"] = [{"n": f"Park {k}", "r": [[x, y, x + 300, y, x + 300, y + 260, x, y + 260]]}
                  for k, (x, y) in enumerate((a * 900 + 200, b * 900 + 300) for a in range(7) for b in range(7))]
    return m


@pytest.fixture(scope="module")
def page_file(tmp_path_factory):
    d = bundle()
    m = _big_city()
    lat = BBOX[0] + H / 110574
    lon = BBOX[1] + W / (math.cos(math.radians(BBOX[0])) * 111320)
    m["bbox"] = [BBOX[0], BBOX[1], lat, lon]
    d["brief"]["palace"]["bbox"] = m["bbox"]
    step = (lon - BBOX[1]) / 3
    d["brief"]["palace"]["districts"] = [{"unit": i, "name": f"District {i}", "bounds": [BBOX[0], BBOX[1] + i * step, lat, BBOX[1] + (i + 1) * step]}
                                         for i in range(3)]
    d["brief"]["palace"]["data_z"] = palace.pack({"map": m, "blocks": pp.lots(m)})
    out, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    f = tmp_path_factory.mktemp("pan-paint") / "page.html"
    f.write_text(out, "utf-8")
    return f


def _webkit(p):
    try:
        return p.webkit.launch()
    except Exception as e:                                   # noqa: BLE001
        # an already installed build of another Playwright release (never a download)
        for exe in sorted(glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/webkit-*/pw_run.sh")), reverse=True):
            try:
                return p.webkit.launch(executable_path=exe)
            except Exception:                                # noqa: BLE001
                continue
        pytest.skip(f"no WebKit build: {str(e).splitlines()[0][:120]}")


# The cost of one 300 px scroll into map not painted before (jump far away, let it paint, then step), median of 8.
STEP = r"""async (css) => {
  const cv = document.getElementById('canvas'), st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
  const fr = () => new Promise(r => requestAnimationFrame(() => r(performance.now()))), sl = ms => new Promise(r => setTimeout(r, ms));
  await sl(400); const W = cv.scrollWidth - cv.clientWidth, H = cv.scrollHeight - cv.clientHeight; let seed = 7, v = [];
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < 8; i++) { cv.scrollLeft = W * (.15 + .7 * rnd()); cv.scrollTop = H * (.15 + .7 * rnd()); await sl(450);
    const t0 = await fr(); cv.scrollTop += 300; v.push(await fr() - t0); }
  st.remove(); v.sort((a, b) => a - b); return (v[3] + v[4]) / 2; }"""
# what the board's layers were before (non-scaling strokes, painted hit lines)
OLD = ("#palace-svg .pl-hit,#palace-svg .pl-pk{vector-effect:non-scaling-stroke !important;}"
       "#palace-svg .pl-hit{stroke-width:14px !important;} #palace-svg .pl-pk{stroke-width:1.5px !important;}"
       "#palace-svg :is(.pl-hits,.pl-tr-hits,.pl-route-hits){visibility:visible !important;}")


def test_in_webkit_a_pan_into_new_map_paints_without_the_stroke_re_transform(page_file):
    with pw.sync_playwright() as p:
        b = _webkit(p)
        try:
            pg = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(page_file.as_uri())
            pg.wait_for_timeout(2500)
            for _ in range(3):                              # in to street level, where the map is many screens across
                pg.click("#pal-ctl [data-z=in]")
                pg.wait_for_timeout(700)
            pg.mouse.move(5, 450)
            info = pg.evaluate("""() => { const h = document.querySelector('#palace-svg .pl-hit'), cs = getComputedStyle(h);
                return {n: document.querySelectorAll('#palace-svg .pl-hit').length, ve: cs.vectorEffect || cs.getPropertyValue('vector-effect'),
                        vis: cs.visibility, w: parseFloat(cs.strokeWidth) * h.getScreenCTM().a}; }""")
            assert info["n"] >= 2 * N and info["ve"] == "none" and info["vis"] == "hidden", info
            assert abs(info["w"] - 14) < .2, info            # still a 14 screen-px band to point at
            # the hit lines still answer the pointer though they are not painted
            hit = pg.evaluate("""() => { let tried = 0, hit = 0; for (const e of document.querySelectorAll('#palace-svg .pl-hit')) {
                const p = e.getPointAtLength(e.getTotalLength() / 2), m = e.getScreenCTM(), x = p.x * m.a + m.e, y = p.y * m.d + m.f;
                if (x < 60 || y < 60 || x > 1380 || y > 840) continue; tried++; const t = document.elementFromPoint(x, y);
                if (t && t.closest && t.closest('.pl-hit')) hit++; if (tried >= 12) break; } return [tried, hit]; }""")
            assert hit[0] >= 4 and hit[1] >= hit[0] - 1, hit
            old = pg.evaluate(STEP, OLD)
            new = pg.evaluate(STEP, "")
            old2 = pg.evaluate(STEP, OLD)
            assert not errs, errs
            print(f"pan step into new map: {new:.0f} ms, old strokes {old:.0f}/{old2:.0f} ms")
            assert new < .6 * min(old, old2), f"a 300 px pan step into new map: {new:.0f} ms, with the old strokes {old:.0f}/{old2:.0f} ms"
        finally:
            b.close()
