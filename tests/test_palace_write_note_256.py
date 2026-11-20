"""1.9.256 (Board B-1119-SHOTS249-GO): on the New project sheet's Write-it-yourself tab, a palace kind (Map, Blueprint, Atlas) shows one plain line above
the button, and the button keeps reading "Build it with Claude". Nothing else shows it. WebKit, three styles, 1440 and 390 wide, no text on text."""
import functools
import http.server
import threading

import pytest

import test_study_plan as T

pw = T.pw
LINE = "Palaces are set up with Claude for now; you can fine-tune by hand after."


def _srv(tmp_path):
    from alto.build import retro, holo
    (tmp_path / "h.html").write_text(T._home([]), encoding="utf-8")
    for pkg, asset in (("retro", retro.retro_asset), ("holo", holo.holo_asset)):
        (tmp_path / pkg).mkdir()
        n, t = asset()
        (tmp_path / pkg / n).write_text(t, encoding="utf-8")
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(type("H", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}), directory=str(tmp_path)))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_address[1]}/h.html"


def test_both_copies_of_the_page_carry_the_line_once():
    a = (T.ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8")
    b = (T.ROOT / "engine" / "home_template.html").read_text(encoding="utf-8")
    assert a == b and a.count(LINE) == 1


@pytest.mark.parametrize("style", ["classic", "holo", "retro"])
@pytest.mark.parametrize("w, h, mobile", [(1440, 900, False), (390, 844, True)])
def test_the_palace_line_shows_only_for_palaces_on_the_write_tab(tmp_path, style, w, h, mobile):
    if pw is None:
        pytest.skip("Playwright is not installed")
    s, url = _srv(tmp_path)
    init = T.NOW + "try{localStorage.setItem('alto-bg-home-v1-style','%s')}catch(e){}" % style
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        ctx, pg, errs = T._open(b, url, w=w, h=h, mobile=mobile, init=init)
        pg.evaluate("document.getElementById('nt-scrim').classList.add('open')")
        vis = lambda: pg.evaluate("(()=>{const n=document.getElementById('nt-palnote');return n.offsetParent!==null&&getComputedStyle(n).display!=='none'&&n.getBoundingClientRect().height>0})()")
        for tab in ("claude", "self"):
            for kind, mode in (("outline", None), ("timeline", None), ("solar", None), ("palace", "city"), ("palace", "building"), ("palace", "atlas")):
                pg.evaluate("ntPick('%s'); %s; ntTab('%s')" % (kind, "ntMode('palace','%s')" % mode if mode else "0", tab))
                want = tab == "self" and kind == "palace"
                assert vis() == want, (style, w, tab, kind, mode)
                if want:
                    pg.evaluate("document.getElementById('nt-palnote').scrollIntoView({block:'center'})"); pg.wait_for_timeout(100)      # (a phone's Build button is sticky at the foot: look at the line where a reader scrolls it)
                    assert pg.evaluate("document.getElementById('nt-make').textContent") == "Build it with Claude"
                    assert pg.evaluate("document.getElementById('nt-palnote').textContent") == LINE
                    r = pg.evaluate("""()=>{const q=id=>document.getElementById(id).getBoundingClientRect(),n=q('nt-palnote');
                      return {n:[n.left,n.top,n.right,n.bottom],others:['nt-make','nt-msg','nt-title','nt-project'].map(i=>{const e=document.getElementById(i),b=q(i);return [i,e.offsetParent===null?0:1,b.left,b.top,b.right,b.bottom]}),
                      sw:document.getElementById('nt-modal').scrollWidth,cw:document.getElementById('nt-modal').clientWidth,vw:innerWidth,nl:Math.round(n.left),nr:Math.round(n.right)}}""")
                    for o in r["others"]:
                        if o[1]:
                            assert r["n"][2] <= o[2] or r["n"][0] >= o[4] or r["n"][3] <= o[3] + 0.5 or r["n"][1] >= o[5] - 0.5, (style, w, r["n"], o)     # no text on text
                    assert r["n"][3] <= next(o for o in r["others"] if o[0] == "nt-make")[3] + 0.5 and r["sw"] <= r["cw"] + 1, (style, w, r)      # above the button, nothing sideways
        pg.evaluate("ntTab('self'); ntPick('timeline')")
        assert pg.evaluate("document.getElementById('nt-make').textContent") == "Start writing" and not vis()
        assert not errs, errs
        ctx.close()
        b.close()
    s.shutdown()
