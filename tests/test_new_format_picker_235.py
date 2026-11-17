"""v1.9.235 NEW dialog: ONE shared format picker above the tabs (headless WebKit, local server, no network, no account).
Rows: no Bass text in the default home; the choice reaches the Claude prompt and the Bass request and survives a tab change; name and description never
intersect; tabs and the action are on screen with no scrolling at d1440, 390 and 320 wide, with 20px gutters; the selected cue is >= 3:1 in every style;
Write it yourself is unchanged."""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_the_default_home_and_private_shell_carry_no_bass_text():
    sys.path.insert(0, str(ROOT))
    from alto.build import pages, private_shell
    assert "bass" not in pages.build_home([]).lower()
    assert "bass" not in private_shell.shell("v", "s").lower()


pytest.importorskip("playwright.sync_api")

SCRIPT = textwrap.dedent('''
    import sys, json, http.server, socketserver, threading, tempfile
    from pathlib import Path
    sys.path.insert(0, %(root)r)
    from alto.build import pages, holo, retro, bass_hosted_ext
    import playwright.sync_api as pw
    d = Path(tempfile.mkdtemp()); (d / "h.html").write_text(pages.build_home([]), encoding="utf-8")
    for sub, asset in (("holo", holo.holo_asset), ("retro", retro.retro_asset)):
        (d / sub).mkdir(); n, t = asset(); (d / sub / n).write_text(t, encoding="utf-8")
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(s, *a, **k): super().__init__(*a, directory=str(d), **k)
        def log_message(s, *a): pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H); srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%%d" %% srv.server_address[1]
    MEASURE = """() => {
      const q = s => [...document.querySelectorAll(s)], vis = e => e.offsetParent !== null;
      const r = e => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
      const inter = (a, b) => !(a[2] <= b[0] || b[2] <= a[0] || a[3] <= b[1] || b[3] <= a[1]);
      const tiles = q('#nt-fmt .nt-kinds:not(.nt-sck) .nt-kind').filter(vis);
      const overlaps = tiles.filter(t => { const n = t.querySelector('.nt-t'); return q('#' + 'nt-fmt').length && [...t.querySelectorAll('small')].some(sm => vis(sm) && inter(r(n), r(sm))); }).length;
      const m = document.getElementById('nt-modal'), mr = r(m), vw = innerWidth, vh = innerHeight;
      const inside = e => { const b = r(e); return b[0] >= 0 && b[2] <= vw && b[1] >= 0 && b[3] <= vh; };
      const rgba = c => { const m = c.match(/[\\\\d.]+/g).map(Number); return [m[0], m[1], m[2], m.length > 3 ? m[3] : 1]; };
      const over = (f, b) => [0, 1, 2].map(i => f[i] * f[3] + b[i] * (1 - f[3]));
      const lum = c => { const l = c.map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * l[0] + .7152 * l[1] + .0722 * l[2]; };
      const cr = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
      const body = over(rgba(getComputedStyle(document.body).backgroundColor), [128, 128, 128]);
      const plate = over(rgba(getComputedStyle(m).backgroundColor), body);
      const on = tiles.find(t => t.classList.contains('on')), off = tiles.find(t => !t.classList.contains('on'));
      let cue = null;
      if(on && off){
        const badge = rgba(getComputedStyle(on, '::after').backgroundColor), mark = rgba(getComputedStyle(on, '::after').color);
        const offbg = over(rgba(getComputedStyle(off).backgroundColor), plate);
        cue = { badge_vs_tile: cr(over(badge, plate), offbg), mark_vs_badge: cr(over(mark, plate), over(badge, plate)), content: getComputedStyle(on, '::after').content };
      }
      const cut = tiles.filter(t => { const sm = [...t.querySelectorAll('small')].find(vis), nt = t.querySelector('.nt-t'), a = sm && getComputedStyle(sm, '::after');
        return (sm && (a.textOverflow === 'ellipsis' || a.whiteSpace === 'nowrap' || sm.scrollWidth > sm.clientWidth + 1 || sm.scrollHeight > sm.clientHeight + 1)) || (nt && nt.scrollWidth > nt.clientWidth + 1); }).length;
      const rowsEq = (() => { const hs = tiles.map(t => r(t)[3] - r(t)[1]); return Math.max(...hs) - Math.min(...hs) <= 0.6; })();
      const act = document.getElementById('nt-claude'), bs = document.getElementById('nt-bass');
      return { tiles: tiles.length, overlaps, cut, rowsEq, vw, vh, left: mr[0], right: vw - mr[2], scroll: m.scrollHeight - m.clientHeight, top: m.scrollTop,
               tabs: q('#nt-tabs .nt-tab').filter(vis).map(inside), action: [act, bs].filter(e => e && vis(e)).map(inside), cancel: inside(document.getElementById('nt-cancel')),
               picker_above: r(document.getElementById('nt-fmt'))[3] <= r(document.getElementById('nt-tabs'))[1] + 1, cue };
    }"""
    out = []
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        for style, theme, size, bass in %(cases)r:
            w, h = size
            ctx = b.new_context(viewport={"width": w, "height": h}); pg = ctx.new_page()
            pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','%%s');localStorage.setItem('alto-theme-v1','%%s')}catch(e){}" %% (style, theme))
            pg.goto(base + "/h.html"); pg.wait_for_timeout(700)
            pg.evaluate("ntOpen('',true)"); pg.wait_for_timeout(600)
            if bass:
                pg.evaluate("w => (0, eval)(w)", bass_hosted_ext._wire()); pg.wait_for_timeout(200)
                pg.evaluate("ntTab('bass')"); pg.wait_for_timeout(200)
            else:
                pg.evaluate("ntTab('claude')"); pg.wait_for_timeout(200)
            m = pg.evaluate(MEASURE); m.update(case=[style, theme, w, h, bool(bass)])
            if not bass and (style, theme, w) == ("holo", "dark", 1440):
                pg.evaluate("window.openClaude = p => { window.__cp = p; }")
                pg.click('#nt-fmt .nt-kind[data-kind="solar"]'); pg.evaluate("ntTab('self')"); pg.evaluate("ntTab('claude')")
                m["persist"] = pg.evaluate("[ntKind, document.querySelector('#nt-fmt .nt-kind.on').dataset.kind]")
                pg.click('#nt-claude'); m["prompt"] = pg.evaluate("window.__cp")
            if not bass and (style, theme, w) == ("classic", "light", 1440):
                pg.evaluate("window.AltoCloud = {enabled: true, user: {}, createTimeline: a => { window.__ct = a; return new Promise(() => {}); }}")
                pg.evaluate("ntTab('self')")
                m["write_visible"] = pg.evaluate("['nt-prow','nt-title','nt-make','nt-cancel'].map(i => document.getElementById(i).offsetParent !== null)")
                pg.fill('#nt-project', 'P'); pg.fill('#nt-title', 'T'); pg.click('#nt-make')
                m["write_call"] = pg.evaluate("window.__ct")
                pg.evaluate("ntClose && ntClose()"); pg.evaluate("ntOpen('',true)"); pg.evaluate("ntTab('claude')")
                pg.click('#nt-fmt .nt-kind[data-kind="timeline"]'); pg.evaluate("ntTab('self')"); pg.fill('#nt-project', 'P'); pg.fill('#nt-title', 'T'); pg.click('#nt-make')
                m["write_call_timeline"] = pg.evaluate("window.__ct")
            if bass and (style, theme, w) == ("holo", "dark", 1440):
                pg.evaluate("window._altoBass = { open: (m, o) => { window.__bo = [m, o]; } }")
                pg.click('#nt-fmt .nt-kind[data-kind="solar"]'); pg.click('#nt-bass'); m["bass_open"] = pg.evaluate("window.__bo")
            out.append(m); ctx.close()
        b.close()
    print("JSON:" + json.dumps(out))
''')

STYLES = [("holo", "dark"), ("classic", "light"), ("classic", "dark"), ("retro", "dark")]
CASES = [(s, t, (w, h), bass) for s, t in STYLES for (w, h) in ((1440, 900), (390, 844), (320, 568)) for bass in (False, True)]


@pytest.fixture(scope="module")
def measured():
    r = subprocess.run([sys.executable, "-c", SCRIPT % {"root": str(ROOT), "cases": CASES}], capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-2000:]
    line = [ln for ln in r.stdout.splitlines() if ln.startswith("JSON:")][-1]
    return json.loads(line[5:])


def test_one_picker_above_the_tabs_and_name_and_description_never_intersect(measured):
    for m in measured:
        assert m["picker_above"] and m["tiles"] >= 4, m["case"]
        assert m["overlaps"] == 0, m["case"]


def test_tabs_and_action_are_on_screen_with_no_scrolling_and_phone_gutters_are_20px(measured):
    for m in measured:
        w = m["case"][2]
        assert m["top"] == 0 and all(m["tabs"]) and len(m["tabs"]) >= 2 and m["action"] and all(m["action"]) and m["cancel"], m["case"]
        if w <= 640:
            assert m["left"] >= 19.5 and m["right"] >= 19.5, m["case"]


def test_the_selected_format_has_a_cue_of_at_least_3_to_1_in_every_style(measured):
    for m in measured:
        c = m["cue"]
        assert c and "✓" in c["content"], m["case"]
        assert c["badge_vs_tile"] >= 3 and c["mark_vs_badge"] >= 3, (m["case"], c)


def test_the_choice_reaches_the_claude_prompt_the_bass_request_and_survives_tab_changes(measured):
    one = [m for m in measured if "prompt" in m][0]
    assert one["persist"] == ["solar", "solar"] and "System outline" in one["prompt"]
    b = [m for m in measured if "bass_open" in m][0]
    assert b["bass_open"] == ["wizard", {"fmt": "solar"}]


def test_write_it_yourself_is_unchanged(measured):
    w = [m for m in measured if "write_call" in m][0]
    assert all(w["write_visible"])
    assert w["write_call"] == {"title": "T", "project": "P", "kind": "outline"}
    assert w["write_call_timeline"]["kind"] == "timeline"


def test_every_tile_description_shows_in_full_and_the_tiles_are_one_height(measured):
    for m in measured:
        assert m["cut"] == 0, (m["case"], "a tile's name or description is cut off")
        assert m["rowsEq"], m["case"]
