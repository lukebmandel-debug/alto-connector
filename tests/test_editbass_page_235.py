"""Edit with Bass, page side (v1.9.235): the link's bytes, the #bass-edit hash, and the editing bar's geometry (headless WebKit, local servers, no network, fake uid)."""
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
URL = "https://us-central1-demo-project.cloudfunctions.net/altoext"


# -- link bytes (no browser) ---------------------------------------------------------------------------------------------------------
def _shell(env, monkeypatch):
    for k in ("ALTO_EXT_URL",):
        monkeypatch.delenv(k, raising=False)
    if env:
        monkeypatch.setenv("ALTO_EXT_URL", URL)
    from alto.build import private_shell
    return private_shell.shell("v", "s")


def test_the_link_is_in_the_luke_alto_shell_only(monkeypatch):
    on, off = _shell(True, monkeypatch), _shell(False, monkeypatch)
    assert 'href="/#bass-edit=' in on and "Edit with Bass" in on and "ee-clef" in on
    assert "bass" not in off.lower()                                        # a default build: zero bytes of it, no word
    assert on.startswith(off[:200]) and len(on) > len(off)


def test_share_public_connector_and_default_pages_carry_none_of_it(monkeypatch):
    from alto.build import share_shell as _ss  # noqa: F401
    from alto.build import private_shell, single_file, pages
    from alto.build.builder import build_timeline, load_brief
    from alto.cloud import emit_cloud_js
    samples = json.loads((ROOT / "samples" / "outline_brief.json").read_text("utf-8"))
    b, nodes, conns = load_brief({"brief": samples["brief"], "nodes": samples["nodes"], "connections": samples.get("connections", [])})
    html, _ = build_timeline(b, nodes, conns)
    monkeypatch.setenv("ALTO_EXT_URL", URL)                                  # even WITH the luke-alto switch on:
    assert "bass" not in single_file.bundle(b, html).lower()                 # the public / offline single file
    page_on = single_file.private_page(b, html, "x")
    assert "bass" not in page_on.lower()                                     # the stored private page itself (the link is added when the shell writes it)
    assert "bass" not in _shellless_share(monkeypatch).lower()               # the share shell
    monkeypatch.delenv("ALTO_EXT_URL")
    assert single_file.private_page(b, html, "x") == page_on                 # stored page bytes: identical with and without the switch
    assert "bass" not in pages.build_home([]).lower()


def _shellless_share(monkeypatch):
    from alto.build.share_shell import shell as share
    return share("v")


def test_page_bytes_the_stored_page_is_unchanged_and_the_served_page_grows_by_the_link_only(monkeypatch, tmp_path):
    from alto.build import private_shell
    from alto.build.builder import build_timeline, load_brief
    from alto.build.single_file import private_page
    samples = json.loads((ROOT / "samples" / "outline_brief.json").read_text("utf-8"))
    b, nodes, conns = load_brief({"brief": samples["brief"], "nodes": samples["nodes"], "connections": samples.get("connections", [])})
    html, _ = build_timeline(b, nodes, conns)
    page = private_page(b, html, "x")
    grown = _apply_link(monkeypatch, page, tmp_path)
    delta = len(grown) - len(page)
    assert 0 < delta < 3000, delta
    assert private_shell.stored_bytes(page) + delta < private_shell.MAX_PAGE_BYTES        # the 976 KB budget
    assert grown.count("ee-clef") >= 4 and re.findall(r'href="(/#bass-edit=[a-z0-9-]+)"', grown)


NODE = Path.home() / ".local/node/bin/node"


def _apply_link(monkeypatch, page, tmp_path):
    """Run the REAL editLink() of the luke-alto shell on a page (node), return the page it would write."""
    monkeypatch.setenv("ALTO_EXT_URL", URL)
    from alto.build import private_shell
    shell = private_shell.shell("v", "s")
    js = re.findall(r"<script>(.*?)</script>\n<script type", shell, re.S)[0]
    fn = js[js.index("function editLink"):js.index("function render")]
    (tmp_path / "p.html").write_text(page, "utf-8")
    (tmp_path / "e.js").write_text(fn + "\nconst fs=require('fs');fs.writeFileSync(process.argv[3],editLink(fs.readFileSync(process.argv[2],'utf8')));", "utf-8")
    subprocess.check_call([str(NODE), str(tmp_path / "e.js"), str(tmp_path / "p.html"), str(tmp_path / "o.html")])
    return (tmp_path / "o.html").read_text("utf-8")


pytest.importorskip("playwright.sync_api")

GEOMETRY = textwrap.dedent('''
    import sys, json, http.server, socketserver, threading
    from pathlib import Path
    sys.path.insert(0, %(root)r)
    import playwright.sync_api as pw
    page = Path(%(page)r).read_text("utf-8")
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(s, *a): pass
        def do_GET(s):
            b = page.encode("utf-8"); s.send_response(200); s.send_header("Content-Type", "text/html"); s.send_header("Content-Length", str(len(b))); s.end_headers(); s.wfile.write(b)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%%d/index.html" %% srv.server_address[1]
    FAKE = "(() => { const base = {user: {uid: 'u'}, known: true, enabled: true, putEdits: () => Promise.resolve(), getEdits: () => Promise.resolve(null)}; window.AltoCloud = new Proxy(base, {get: (t, k) => k in t ? t[k] : () => Promise.resolve(null)}); })()"
    MEASURE = """() => {
      const bar = document.getElementById('alto-edit-exit'); if(!bar) return {nobar: true};
      const R = e => e.getBoundingClientRect(), b = R(bar), out = [];
      const chip = bar.querySelector('.ee-clef'), cr = chip && R(chip);
      const fixedAnc = e => { for(let n = e; n && n.nodeType === 1; n = n.parentElement){ if(getComputedStyle(n).position === 'fixed') return true; } return false; };
      document.querySelectorAll('button, a, [role=button], input, [id$=-btn], #tab-rail > *').forEach(e => {
        if(bar.contains(e) || e.contains(bar) || !fixedAnc(e)) return;
        const cs = getComputedStyle(e); if(cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0 || cs.pointerEvents === 'none') return;
        const r = R(e); if(r.width < 10 || r.height < 10 || r.width > innerWidth * .8) return;
        const dx = Math.max(r.left - b.right, b.left - r.right), dy = Math.max(r.top - b.bottom, b.top - r.bottom);
        out.push({id: (e.id || e.className.toString().slice(0, 30)) + '|' + (e.textContent || '').trim().slice(0, 12), gap: Math.max(dx, dy)});
      });
      const word = bar.querySelector('.ee-t'), wcs = getComputedStyle(word);
      return {bar: [b.left, b.top, b.right, b.bottom], vw: innerWidth, chip: cr && [cr.width, cr.height], chip_layout: chip && [chip.offsetWidth, chip.offsetHeight], hit: chip && (() => { const hitAt = (x, y) => { const e = document.elementFromPoint(x, y); return !!e && (e === chip || chip.contains(e)); }; const cx = cr.left + cr.width / 2, cy = cr.top + cr.height / 2; let up = 0, dn = 0, lf = 0, rt = 0; while(hitAt(cx, cy - up - 1) && up < 80) up++; while(hitAt(cx, cy + dn + 1) && dn < 80) dn++; while(hitAt(cx - lf - 1, cy) && lf < 80) lf++; while(hitAt(cx + rt + 1, cy) && rt < 80) rt++; return [lf + rt + 1, up + dn + 1]; })(), chip_hit: chip && (() => { const a = getComputedStyle(chip, '::after'); return [parseFloat(a.height)]; })(),
              word_px: parseFloat(wcs.fontSize), label: {tag: word.tagName, tabindex: word.getAttribute('tabindex'), role: word.getAttribute('role'), onclick: !!word.onclick, cursor: wcs.cursor, in_control: !!word.closest('button, a')}, word_before: getComputedStyle(word, '::before').content, fixed: out, children: [...bar.children].map(c => c.className + ':' + Math.round(R(c).right - R(c).left)),
              overflow: bar.scrollWidth > bar.clientWidth + 1, others: [...bar.querySelectorAll('button')].map(x => [x.className, Math.round(R(x).width), Math.round(R(x).height)]),
              hits: [...bar.querySelectorAll('button, a')].filter(x => x.offsetParent !== null && R(x).width > 0).map(x => {
                const r = R(x), cx = r.left + r.width / 2, cy = r.top + r.height / 2, on = (px, py) => { const e = document.elementFromPoint(px, py); return !!e && (e === x || x.contains(e)); };
                let up = 0, dn = 0, lf = 0, rt = 0; while(on(cx, cy - up - 1) && up < 80) up++; while(on(cx, cy + dn + 1) && dn < 80) dn++; while(on(cx - lf - 1, cy) && lf < 80) lf++; while(on(cx + rt + 1, cy) && rt < 80) rt++;
                return {name: x.className.toString().split(' ').filter(c => /^ee-/.test(c)).join('.'), box: [cx - lf, cy - up, cx + rt + 1, cy + dn + 1], centre_hits_self: on(cx, cy), drawn: [r.width, r.height]}; })};
    }"""
    UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    res = []
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        for style, theme, w, h in %(cases)r:
            mob = w < 700
            ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=mob, has_touch=mob, user_agent=UA if mob else None, device_scale_factor=2)
            pg = ctx.new_page()
            pg.add_init_script(FAKE + ";try{localStorage.setItem('alto-bg-home-v1-style','%%s');localStorage.setItem('alto-theme-v1','%%s')}catch(e){}" %% (style, theme))
            pg.goto(base); pg.wait_for_timeout(1500)
            pg.evaluate("window._altoManual && window._altoManual.enter()"); pg.wait_for_timeout(700)
            m = pg.evaluate(MEASURE); m["case"] = [style, theme, w, h]; res.append(m); ctx.close()
        b.close()
    print("JSON:" + json.dumps(res))
''')

CASES = [(s, t, w, h) for s, t in (("holo", "dark"), ("classic", "light"), ("classic", "dark"), ("retro", "dark")) for (w, h) in ((1440, 900), (390, 844), (320, 568))]


@pytest.fixture(scope="module")
def geometry(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("geo")
    mp = pytest.MonkeyPatch()
    from alto.build.builder import build_timeline, load_brief
    from alto.build.single_file import private_page
    samples = json.loads((ROOT / "samples" / "outline_brief.json").read_text("utf-8"))
    b, nodes, conns = load_brief({"brief": samples["brief"], "nodes": samples["nodes"], "connections": samples.get("connections", [])})
    html, _ = build_timeline(b, nodes, conns)
    mp.delenv("ALTO_EXT_URL", raising=False)
    page = _apply_link(mp, private_page(b, html, "x"), tmp)
    mp.undo()
    (tmp / "page.html").write_text(page, "utf-8")
    r = subprocess.run([sys.executable, "-c", GEOMETRY % {"root": str(ROOT), "page": str(tmp / "page.html"), "cases": CASES}], capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads([ln for ln in r.stdout.splitlines() if ln.startswith("JSON:")][-1][5:])
    Path(os.environ.get("GEO_DUMP", os.devnull)).write_text(json.dumps(out), "utf-8")
    return out


def test_the_edit_bar_has_the_clef_chip_44_by_36_and_keeps_3px_from_every_fixed_control(geometry):
    for m in geometry:
        assert not m.get("nobar"), m
        assert abs(m["chip_layout"][0] - 44) <= 1 and abs(m["chip_layout"][1] - 36) <= 1, (m["case"], m["chip_layout"])          # the drawn chip, as laid out
        if m["case"][2] <= 640:                                                   # a phone: what a FINGER hits, after every transform and scale, is at least 44 x 44
            assert m["hit"][0] >= 43.5 and m["hit"][1] >= 43.5, (m["case"], "rendered chip", m["chip"], "hit area", m["hit"])
        assert not m["overflow"], m["case"]
        assert m["case"][2] > 640 or m["fixed"], (m["case"], "no fixed controls were found to check against")
        for f in m["fixed"]:
            assert f["gap"] >= 3, (m["case"], f)                            # never overlapping INFO, MARK or any fixed corner control


def test_the_word_editing_goes_only_at_340_wide_or_less(geometry):
    for m in geometry:
        w = m["case"][2]
        if w <= 340:
            assert m["word_px"] == 0 and "\u270e" in m["word_before"], m["case"]
        else:
            assert m["word_px"] > 0, m["case"]


# -- the hash ------------------------------------------------------------------------------------------------------------------------------
HASH = textwrap.dedent('''
    import sys, json, http.server, socketserver, threading, urllib.parse
    sys.path.insert(0, %(root)r)
    from alto.build import pages, bass_hosted_ext
    import playwright.sync_api as pw
    home = pages.build_home([]); bundle = bass_hosted_ext.bundle(); acts = []
    OWNED = {"my-timeline"}
    class Api(http.server.BaseHTTPRequestHandler):
        def log_message(s, *a): pass
        def _h(s, code, body=b""):
            s.send_response(code); s.send_header("Access-Control-Allow-Origin", "*"); s.send_header("Access-Control-Allow-Headers", "*"); s.send_header("Content-Type", "application/json"); s.send_header("Content-Length", str(len(body))); s.end_headers(); s.wfile.write(body)
        def do_OPTIONS(s): s._h(204)
        def do_POST(s):
            req = json.loads(s.rfile.read(int(s.headers["Content-Length"])).decode()); a = req.get("action"); acts.append(a)
            if a == "edit_open": out = {"ok": True, "status": "ok", "title": "My timeline", "can_undo": False} if req["args"].get("timeline_id") in OWNED else {}
            elif a == "balance": out = {"ok": True, "status": "ok", "credits": 100}
            else: out = {}
            s._h(200, json.dumps(out).encode())
    api = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Api); threading.Thread(target=api.serve_forever, daemon=True).start()
    class Site(http.server.BaseHTTPRequestHandler):
        def log_message(s, *a): pass
        def do_GET(s):
            b = home.encode(); s.send_response(200); s.send_header("Content-Type", "text/html"); s.send_header("Content-Length", str(len(b))); s.end_headers(); s.wfile.write(b)
    site = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site); threading.Thread(target=site.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%%d/" %% site.server_address[1]
    FAKE = "window.AltoCloud = {user: {uid: 'u', getIdToken: () => Promise.resolve('t')}, known: true, enabled: true}; window.__altoExtUrl = 'http://127.0.0.1:%%d/';" %% api.server_address[1]
    res = {}
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        def run(h):
            acts.clear(); ctx = b.new_context(viewport={"width": 1200, "height": 800}); pg = ctx.new_page(); pg.add_init_script(FAKE)
            pg.goto(base + h); pg.wait_for_timeout(700); pg.evaluate("w => (0, eval)(w)", bundle); pg.wait_for_timeout(800)
            r = {"panel": pg.evaluate("!!document.getElementById('bass-edit-root')"), "hash": pg.evaluate("location.hash"), "acts": list(acts),
                 "dom": pg.evaluate("document.documentElement.outerHTML.replace(/\\\\s+/g, ' ')"), "text": pg.evaluate("(document.getElementById('bass-edit-root')||{textContent:''}).textContent")}
            ctx.close(); return r
        res["base"] = run("")
        res["owned"] = run("#bass-edit=my-timeline")
        res["other"] = run("#bass-edit=other-one")
        for i, h in enumerate(["#bass-edit=<img src=x onerror=alert(1)>", "#bass-edit=<script>alert(1)</script>", "#bass-edit=../../x", "#bass-edit=" + "a" * 300, "#bass-edit=MY-TIMELINE",
                               "#bass-edit=my-timeline%%0a", "#bass-edit=1abc", "#bass-edit=", "#bass-edit=my-timeline&x=1", "#bass-edit=my timeline"]):
            res["bad%%d" %% i] = run(h)
        b.close()
    print("JSON:" + json.dumps(res))
''')


@pytest.fixture(scope="module")
def hashes():
    r = subprocess.run([sys.executable, "-c", HASH % {"root": str(ROOT)}], capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads([ln for ln in r.stdout.splitlines() if ln.startswith("JSON:")][-1][5:])


def test_a_good_id_the_owner_owns_opens_the_panel_clears_the_hash_and_spends_nothing(hashes):
    o = hashes["owned"]
    assert o["panel"] and o["hash"] == "" and "My timeline" in o["text"] and o["acts"] == ["edit_open", "balance"]


def test_a_malicious_or_malformed_hash_is_ignored_never_rendered_cleared_and_sends_nothing(hashes):
    base = hashes["base"]["dom"]
    for k, r in hashes.items():
        if not k.startswith("bad"):
            continue
        assert not r["panel"] and r["hash"] == "" and r["acts"] == [], (k, r["acts"], r["hash"])
        assert r["dom"] == base, k                                          # the same DOM as with no hash


def test_a_non_owner_id_shows_no_message_and_the_same_home_as_with_no_hash(hashes):
    r = hashes["other"]
    assert not r["panel"] and r["dom"] == hashes["base"]["dom"] and r["acts"] == ["edit_open"]


def test_no_hash_ever_runs_a_preview_or_an_apply(hashes):
    for r in hashes.values():
        assert not [a for a in r["acts"] if a in ("edit_preview", "edit_apply", "edit_undo")]


def test_every_edit_bar_control_has_a_44_by_44_tap_box_that_overlaps_no_other_and_the_centre_hits_itself(geometry):
    for m in geometry:
        if m["case"][2] > 640:
            continue
        hits = m["hits"]
        assert len(hits) >= 4, (m["case"], [h["name"] for h in hits])                 # undo, redo, the clef chip, Done (the pencil is a label, not a control)
        for h in hits:
            l, t, r, b = h["box"]
            assert r - l >= 43.5 and b - t >= 43.5, (m["case"], h["name"], h["box"])
            assert h["centre_hits_self"], (m["case"], h["name"])
        for i, a in enumerate(hits):
            for c in hits[i + 1:]:
                ox = min(a["box"][2], c["box"][2]) - max(a["box"][0], c["box"][0])
                oy = min(a["box"][3], c["box"][3]) - max(a["box"][1], c["box"][1])
                assert not (ox > 0.5 and oy > 0.5), (m["case"], a["name"], c["name"], ox, oy)


def test_the_pencil_label_is_not_interactive_so_it_needs_no_tap_box(geometry):
    for m in geometry:
        lb = m["label"]
        assert lb["tag"] == "SPAN" and lb["tabindex"] is None and lb["role"] is None and not lb["onclick"] and not lb["in_control"], (m["case"], lb)
        assert lb["cursor"] in ("auto", "default"), (m["case"], lb)
