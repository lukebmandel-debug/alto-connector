"""Both Bass panels on the home page (v1.9.235; Luke L-1116-184239 "the right side of bass window is cut off"): the side panel and the Edit with Bass panel stay inside the
window with 20px gutters, keep their close button visible, never overlap a fixed control, and their fields fill the panel. Headless WebKit, local servers, no network."""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parent.parent

SCRIPT = textwrap.dedent('''
    import sys, json, http.server, threading
    sys.path.insert(0, %(root)r)
    from alto.build import pages, bass_hosted_ext, holo, retro
    ASSETS = {}
    for sub, asset in (("holo", holo.holo_asset), ("retro", retro.retro_asset)):
        n, t = asset(); ASSETS["/%%s/%%s" %% (sub, n)] = t
    PAGES = [{"key": "k%%d" %% i, "project": "Project %%d" %% (i // 4), "title": "Tile %%d" %% i, "heading": "Tile %%d" %% i, "tid": "t%%d" %% i, "added": 1.7e12 - i, "viewedAt": 1.7e12 - i, "fmt": "timeline", "units": [{"label": "U", "color": "#7c5cff"}]} for i in range(8)]
    import playwright.sync_api as pw
    OUT = %(shots)r
    home = pages.build_home([]); bundle = bass_hosted_ext.bundle()
    class Api(http.server.BaseHTTPRequestHandler):
        def log_message(s, *a): pass
        def _h(s, code, body=b""):
            s.send_response(code); s.send_header("Access-Control-Allow-Origin", "*"); s.send_header("Access-Control-Allow-Headers", "*"); s.send_header("Content-Type", "application/json"); s.send_header("Content-Length", str(len(body))); s.end_headers(); s.wfile.write(body)
        def do_OPTIONS(s): s._h(204)
        def do_POST(s):
            req = json.loads(s.rfile.read(int(s.headers["Content-Length"])).decode()); a = req.get("action")
            out = {"ok": True, "status": "ok", "credits": 400, "label": "400 credits", "available": True, "title": "A long timeline title for the panel", "can_undo": False} if a in ("balance", "edit_open") else {}
            s._h(200, json.dumps(out).encode())
    api = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Api); threading.Thread(target=api.serve_forever, daemon=True).start()
    class Site(http.server.BaseHTTPRequestHandler):
        def log_message(s, *a): pass
        def do_GET(s):
            path = s.path.split("?")[0].split("#")[0]; body = ASSETS.get(path)
            b = (body if body is not None else home).encode(); s.send_response(200); s.send_header("Content-Type", "text/javascript" if body is not None else "text/html"); s.send_header("Content-Length", str(len(b))); s.end_headers(); s.wfile.write(b)
    site = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site); threading.Thread(target=site.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%%d/" %% site.server_address[1]
    FAKE = "window.AltoCloud = {user: {uid: 'u', getIdToken: () => Promise.resolve('t')}, known: true, enabled: true}; window.__altoExtUrl = 'http://127.0.0.1:%%d/';" %% api.server_address[1]
    MEASURE = """(sel) => {
      const P = document.querySelector(sel); if(!P) return {nopanel: true};
      const R = e => e.getBoundingClientRect(), p = R(P), vw = innerWidth, vh = innerHeight;
      const close = P.querySelector('.bs-h .bs-ib:last-child, .be-x'), c = close && R(close);
      const fixed = [];
      document.querySelectorAll('body *').forEach(e => {
        if(P.contains(e) || e.contains(P) || e.closest('.bs-root,.be-root')) return;
        const cs = getComputedStyle(e); if(cs.position !== 'fixed' || cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0 || cs.pointerEvents === 'none') return;
        const r = R(e); if(r.width < 4 || r.height < 4 || r.width > vw * .8) return;
        const dx = Math.max(r.left - p.right, p.left - r.right), dy = Math.max(r.top - p.bottom, p.top - r.bottom);
        fixed.push({id: e.id || e.className.toString().slice(0, 30), gap: Math.max(dx, dy)});
      });
      const fields = [...P.querySelectorAll('.bs-inp, .be-ta')].map(f => [R(f).left - p.left, p.right - R(f).right]);
      const kids = [...P.querySelectorAll('.bs-b > *, .be-win > *')].map(k => R(k).right - p.right).filter(v => v > 0.5);
      const gapTo = e => { const r = R(e), dx = Math.max(r.left - p.right, p.left - r.right), dy = Math.max(r.top - p.bottom, p.top - r.bottom); return Math.max(dx, dy); };
      const row = [...document.querySelectorAll('.home-sort, .hr-chip')].filter(e => e.offsetParent).map(e => [e.className.toString().slice(0, 20), gapTo(e)]);
      window.scrollTo(0, 1e6);
      const foot = [...document.querySelectorAll('#home-legal a')].filter(e => e.offsetParent).map(e => { const r = R(e); const dx = Math.max(r.left - p.right, p.left - r.right), dy = Math.max(r.top - p.bottom, p.top - r.bottom); return [e.textContent.slice(0, 14), Math.max(dx, dy), r.bottom <= vh + 1]; });
      const plate = getComputedStyle(P).backgroundColor, tiles = document.querySelectorAll('#projects-wrap .proj, #projects-wrap [class*=tile]').length;
      const rgba = c => { const m = c.match(/[\\d.]+/g).map(Number); return [m[0], m[1], m[2], m.length > 3 ? m[3] : 1]; };
      const over = (f, b) => [0, 1, 2].map(i => f[i] * f[3] + b[i] * (1 - f[3]));
      const lum = c => { const l = c.map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * l[0] + .7152 * l[1] + .0722 * l[2]; };
      const cr = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
      const clip = e => e ? e.scrollWidth > e.clientWidth + 1 : false;
      const head = P.querySelector('.bs-h');
      const header = head ? {title: (P.querySelector('.bs-name') || {}).textContent, chip: (P.querySelector('.bs-chip') || {}).textContent || '', chip_short: head.classList.contains('bs-short'), chip_wrap: head.classList.contains('bs-wrap'),
        clipped: [head, P.querySelector('.bs-name'), P.querySelector('.bs-chip')].filter(clip).length, ellipsis: [...head.querySelectorAll('*')].filter(e => getComputedStyle(e).textOverflow === 'ellipsis').length,
        chip_inside: !P.querySelector('.bs-chip') || (R(P.querySelector('.bs-chip')).right <= p.right + .5 && R(P.querySelector('.bs-chip')).left >= p.left - .5)} : null;
      const be = P.querySelector('.be-t'), editHeader = be ? {title: be.textContent, clipped: clip(be), x_inside: R(P.querySelector('.be-x')).right <= p.right + .5} : null;
      const link = P.querySelector('.bs-ul > b'); let linkContrast = null;
      if(link){ const bg = over(rgba(getComputedStyle(P.querySelector('.bs-ul')).backgroundColor), over(rgba(getComputedStyle(P).backgroundColor), [10, 12, 20])); linkContrast = cr(over(rgba(getComputedStyle(link).color), bg), bg); }
      return {header, editHeader, linkContrast, row, foot, plate, tiles, panel: [p.left, p.top, p.right, p.bottom], vw, vh, close: c && [c.left, c.top, c.right, c.bottom, c.width, c.height], fixed, fields, overflow_kids: kids,
              scroll_x: document.documentElement.scrollWidth > vw + 1};
    }"""
    UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    res = []
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        for style, theme, w, h in %(cases)r:
            for which in ("side", "edit"):
                mob = w < 700
                ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=mob, has_touch=mob, user_agent=UA if mob else None, device_scale_factor=2)
                pg = ctx.new_page()
                pg.add_init_script(FAKE + ";try{localStorage.setItem('alto-bg-home-v1-style','%%s');localStorage.setItem('alto-theme-v1','%%s');localStorage.setItem('alto-bass-ack-u','1')}catch(e){}" %% (style, theme))
                pg.goto(base + ("#bass-edit=my-timeline" if which == "edit" else "")); pg.wait_for_timeout(900)
                pg.evaluate("p => drawPrivate(p)", PAGES); pg.wait_for_timeout(300)
                retro_on = pg.evaluate("document.documentElement.classList.contains('alto-retro')")
                pg.evaluate("w => (0, eval)(w)", bundle); pg.wait_for_timeout(500)
                if which == "side":
                    pg.evaluate("window._altoBass.open('panel')")
                pg.wait_for_timeout(900)
                m = pg.evaluate(MEASURE, ".bs-panel" if which == "side" else ".be-win"); m["case"] = [style, theme, w, h, which]; m["retro_on"] = retro_on
                if OUT and (style, theme, w) in (("retro", "dark", 1000), ("classic", "light", 1440), ("holo", "dark", 390)):
                    pg.screenshot(path="%%s/%%s-%%s-%%s-%%d.png" %% (OUT, which, style, theme, w))
                res.append(m); ctx.close()
        b.close()
    print("JSON:" + json.dumps(res))
''')

CASES = [(s, t, w, h) for s, t in (("holo", "dark"), ("classic", "light"), ("classic", "dark"), ("retro", "dark"))
         for (w, h) in ((1440, 900), (1024, 768), (1000, 800), (390, 844), (320, 568))]


@pytest.fixture(scope="module")
def panels():
    import os
    r = subprocess.run([sys.executable, "-c", SCRIPT % {"root": str(ROOT), "cases": CASES, "shots": os.environ.get("PANEL_SHOTS", "")}],
                       capture_output=True, text=True, timeout=1500)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads([ln for ln in r.stdout.splitlines() if ln.startswith("JSON:")][-1][5:])


def test_both_panels_open_and_stay_inside_the_window_with_20px_gutters(panels):
    for m in panels:
        assert not m.get("nopanel"), m["case"]
        l, t, r, b = m["panel"]
        assert l >= 19.5 and m["vw"] - r >= 19.5, (m["case"], m["panel"], m["vw"])
        assert t >= 0 and b <= m["vh"] + 0.5, (m["case"], m["panel"])
        assert not m["scroll_x"], m["case"]


def test_the_close_button_is_always_fully_visible_and_a_44pt_target_on_a_phone(panels):
    for m in panels:
        c = m["close"]
        assert c, m["case"]
        l, t, r, b, w, h = c
        assert l >= 0 and r <= m["vw"] and t >= 0 and b <= m["vh"], (m["case"], c)
        assert r <= m["panel"][2] + 0.5, (m["case"], c, m["panel"])
        if m["vw"] <= 640:
            assert w >= 40 and h >= 40, (m["case"], c)


def test_neither_panel_overlaps_a_fixed_control_and_the_fields_fill_the_panel(panels):
    for m in panels:
        for f in m["fixed"]:
            assert f["gap"] >= 0, (m["case"], f)
        for left, right in m["fields"]:
            assert 0 <= left <= 24 and 0 <= right <= 24, (m["case"], m["fields"])       # the text box fills the panel (its own padding only)
        assert not m["overflow_kids"], (m["case"], m["overflow_kids"])


def test_the_home_is_populated_retro_is_really_on_and_the_panel_clears_the_sort_row_and_the_footer(panels):
    for m in panels:
        if m["case"][0] == "retro":
            assert m["retro_on"], m["case"]
        if m["case"][4] != "side" or m["case"][2] <= 640:
            continue
        assert m["row"], (m["case"], "the PRIVATE / sort row is not on screen")
        for name, gap in m["row"]:
            assert gap >= 8, (m["case"], name, gap)                                   # below the row, or clear of it by 8px
        assert m["foot"], (m["case"], "the footer links are not on screen")
        for name, gap, shown in m["foot"]:
            assert gap >= 12, (m["case"], name, gap)                                  # the map credit and the legal links are never hidden
        a = [float(x) for x in m["plate"].replace("rgba(", "").replace("rgb(", "").replace(")", "").split(",")]
        assert len(a) == 3 or a[3] == 1, (m["case"], m["plate"])                      # a solid plate


def test_the_panel_header_is_never_cut_off_the_title_and_the_credits_always_show_in_full(panels):
    for m in panels:
        h, e = m["header"], m["editHeader"]
        if m["case"][4] == "side":
            assert h and h["title"] == "Bass", (m["case"], h)
            assert h["clipped"] == 0 and h["ellipsis"] == 0 and h["chip_inside"], (m["case"], h)
            assert "400" in h["chip"], (m["case"], h)                                 # the number is there in full (the pill may say "400 credits")
        else:
            assert e and e["title"] == "Edit with Bass" and not e["clipped"] and e["x_inside"], (m["case"], e)


def test_the_choose_link_reads_at_4_5_to_1_in_every_style(panels):
    seen = 0
    for m in panels:
        if m["linkContrast"] is not None:
            seen += 1
            assert m["linkContrast"] >= 4.5, (m["case"], m["linkContrast"])
    assert seen >= 20, seen
