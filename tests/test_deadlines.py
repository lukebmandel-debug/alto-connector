"""Deadline boxes: an authority value's `deadlines` draw a big box at the top of its detail page (Classic, Retro, Holo; phone;
ink print). The brief side (validation, escaping, no box when empty) and the page side (WebKit)."""
import copy
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from alto.build import holo, phone as _phone, retro   # noqa: E402
from alto.build.brief import BriefError   # noqa: E402
from alto.build.builder import build_timeline, load_brief   # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"

D1446 = [{"period": "30 days", "what": "Notice of removal", "trigger": "after receipt of the initial pleading",
          "quote": "The notice of removal of a civil action or proceeding shall be filed within 30 days after the receipt by the defendant",
          "cite": "§ 1446(b)(1)"},
         {"period": "1 year", "what": "Removal on diversity", "trigger": "after commencement of the action",
          "quote": "may not be removed more than 1 year after commencement of the action", "cite": "§ 1446(c)(1)"}]
RULE = [{"period": "21 days", "what": "Serve an answer", "trigger": "after being served with the summons and complaint",
         "quote": "A defendant must serve an answer within 21 days after being served with the summons and complaint",
         "cite": "Rule 12(a)(1)(A)(i)"}]
MANY = [{"period": p, "what": w, "trigger": t, "quote": q, "cite": c} for p, w, t, q, c in [
    ("21 days", "Amend once as a matter of course", "after serving it", "21 days after serving it, or if the pleading is one to which a responsive pleading is required, 21 days after service of a responsive pleading or 21 days after service of a motion under Rule 12(b), (e), or (f)", "Rule 15(a)(1)"),
    ("7 days", "Respond to a motion", "after it is served", "a response is due within 7 days", "Rule 6(c)(2)"),
    ("90 days", "Serve the defendant", "after the complaint is filed", "If a defendant is not served within 90 days after the complaint is filed, the court must dismiss", "Rule 4(m)"),
    ("28 days", "Move to alter or amend", "after entry of the judgment", "no later than 28 days after the entry of the judgment", "Rule 59(e)")]]


def _doc(slot_values=None):
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    vals = slot_values or [
        {"id": "usc-1446", "name": "28 U.S.C. § 1446", "sections": [{"h": "Summary", "t": "How a case is removed."}], "deadlines": D1446},
        {"id": "frcp-12", "name": "Fed. R. Civ. P. 12", "sections": [{"h": "Summary", "t": "Defenses."}], "deadlines": RULE},
        {"id": "frcp-many", "name": "Several limits", "sections": [{"h": "Summary", "t": "Many."}], "deadlines": MANY},
        {"id": "none", "name": "No limits", "sections": [{"h": "Summary", "t": "Nothing."}]}]
    d["brief"]["axes"].append({"label": "Statutes & Rules", "singular": "Section", "hide_nav": True, "values": vals})
    return d


def _build(d):
    return build_timeline(*load_brief(d))[0]


def test_the_box_is_in_the_page_and_the_css_only_when_a_value_has_deadlines():
    h = _build(_doc())
    assert "dl-box" in h and ".dl-box{" in h and "30 days" in h and "§ 1446(b)(1)" in h
    plain = _build(_doc([{"id": "x", "name": "X", "sections": [{"h": "Summary", "t": "y"}]}]))
    assert "dl-box" not in plain and "dl-per" not in plain
    empty = _build(_doc([{"id": "x", "name": "X", "sections": [{"h": "Summary", "t": "y"}], "deadlines": []}]))
    assert "dl-box" not in empty


def test_the_box_is_the_first_section_of_the_page():
    h = _build(_doc())
    i = h.index("usc-1446")
    reg = h[i:i + 20000]
    assert reg.index("Deadlines") < reg.index("How a case is removed")


def test_text_with_markup_is_text():
    evil = [{"period": "5 <b>days</b>", "what": 'Say "this" & <script>alert(1)</script>', "trigger": "a < b & c > d",
             "quote": '"x" <img src=x onerror=alert(1)> & y, within 5 days', "cite": "§ 1 <i>(a)</i>"}]
    h = _build(_doc([{"id": "v", "name": "V", "sections": [{"h": "Summary", "t": "s"}], "deadlines": evil}]))
    box = h[h.index('class=\\"dl-box') if 'class=\\"dl-box' in h else h.index('class="dl-box'):][:1500]
    assert "<script>alert" not in box and "onerror=alert" not in box.replace("&amp;", "")
    assert "<img" not in box and "<b>" not in box and "<i>" not in box


@pytest.mark.parametrize("bad", [
    "nope", [1], [{"period": "1 day", "what": "w", "quote": "q", "cite": "c", "extra": "x"}],
    [{"period": "", "what": "w", "quote": "q", "cite": "c"}],
    [{"period": "1 day", "what": "w", "quote": "", "cite": "c"}],
    [{"period": 1, "what": "w", "quote": "q", "cite": "c"}],
    [{"period": "x" * 41, "what": "w", "quote": "q", "cite": "c"}],
    [{"period": "1 day", "what": "w", "quote": "q" * 2001, "cite": "c"}],
    [{"period": "1 day", "what": "w", "quote": "q", "cite": "c"}] * 13])
def test_a_bad_deadlines_list_is_refused(bad):
    d = _doc([{"id": "v", "name": "V", "sections": [{"h": "Summary", "t": "s"}], "deadlines": bad}])
    from alto.build.brief import validate_brief
    with pytest.raises(BriefError):
        b, _, _ = load_brief(d)
        validate_brief(b)


def test_an_edit_fold_keeps_deadlines_and_the_tool_documents_them():
    from alto.edits import fold
    from test_manual_edit import Store
    st = Store(_doc())
    st.edits = {"v": 1, "ops": {"ne|theme|new-one": {"b": None, "t": 1, "v": {"name": "New One"}}}}
    fold(st, "u", "t1")
    vals = [v for a in st.doc["brief"]["axes"] if a["label"] == "Statutes & Rules" for v in a["values"]]
    assert [v for v in vals if v["id"] == "usc-1446"][0]["deadlines"] == D1446
    from alto import mcp_server
    assert "deadlines" in mcp_server.set_axis_values.__doc__


# ── the page, in WebKit ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("deadlines")
    (d / "t.html").write_text(_build(_doc()), encoding="utf-8")
    for mod, sub in ((holo, "holo"), (retro, "retro"), (_phone, "phone")):
        nm, tx = (mod.holo_asset if sub == "holo" else mod.retro_asset if sub == "retro" else mod.phone_asset)()
        (d / sub).mkdir()
        (d / sub / nm).write_text(tx, encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(scope="module")
def webkit():
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no webkit: {e}")
        yield b
        b.close()


def open_page(webkit, site, style, vid, phone=False):
    if phone:
        ctx = webkit.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, user_agent=UA)
    else:
        ctx = webkit.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.goto(site + "/t.html", wait_until="load")
    pg.evaluate("(s)=>{localStorage.clear(); localStorage.setItem('alto-bg-home-v1-style', s)}", style)
    pg.goto(site + "/t.html", wait_until="load")
    pg.wait_for_timeout(500)
    if style != "classic":
        pg.evaluate("(s)=>window._altoStyle && window._altoStyle.set(s)", style)
        pg.wait_for_timeout(400)
    pg.evaluate("(v)=>showDetail(typeof ENVS!=='undefined'&&ENVS[v]?'env':'theme', v)", vid)
    pg.wait_for_timeout(700)
    return ctx, pg


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("phone", [False, True])
@pytest.mark.parametrize("vid", ["usc-1446", "frcp-many"])
def test_the_box_comes_first_and_clear_of_the_edges_and_itself(webkit, site, style, phone, vid):
    ctx, pg = open_page(webkit, site, style, vid, phone)
    r = pg.evaluate("""()=>{
      const dc=document.getElementById('detail-content'), secs=[...dc.querySelectorAll('.detail-section')];
      const box=dc.querySelector('.dl-box'); if(!box) return {err:'no box'};
      const b=box.getBoundingClientRect(), vw=document.documentElement.clientWidth;
      const overlaps=[]; box.querySelectorAll('.dl-row').forEach(r=>{
        const k=[...r.querySelectorAll('.dl-per,.dl-what,.dl-trg,.dl-q,.dl-cite')].map(e=>e.getBoundingClientRect());
        for(let i=0;i<k.length;i++)for(let j=i+1;j<k.length;j++){const a=k[i],c=k[j];
          if(a.left<c.right-1&&c.left<a.right-1&&a.top<c.bottom-1&&c.top<a.bottom-1) overlaps.push([i,j]);}
        k.forEach(a=>{ if(a.left<b.left-1||a.right>b.right+1) overlaps.push(['out',a.left,a.right]); }); });
      return {first: secs[0]===box.closest('.detail-section'), left:b.left, right:vw-b.right, scrollX:document.documentElement.scrollWidth-vw,
              rows:box.querySelectorAll('.dl-row').length, overlaps, style:document.documentElement.className};}""")
    assert not r.get("err"), r
    assert r["first"], r
    assert not r["overlaps"], r
    assert r["scrollX"] <= 0, r
    assert r["left"] >= 20 and r["right"] >= 20, r
    assert r["rows"] == (2 if vid == "usc-1446" else 4)
    if style != "classic":
        assert ("alto-" + style) in r["style"], r
    ctx.close()


def test_no_box_for_a_value_without_deadlines(webkit, site):
    ctx, pg = open_page(webkit, site, "classic", "none")
    assert pg.evaluate("document.querySelectorAll('#detail-content .dl-box').length") == 0
    assert "Nothing" in pg.evaluate("document.getElementById('detail-content').innerText")
    ctx.close()


def test_the_box_prints_in_ink(webkit, site):
    ctx, pg = open_page(webkit, site, "classic", "usc-1446")
    pg.evaluate("document.documentElement.classList.add('printing','print-current')")
    pg.emulate_media(media="print")
    r = pg.evaluate("""()=>{const b=document.querySelector('#detail-content .dl-box'), cs=getComputedStyle(b), r=b.getBoundingClientRect();
      return {w:r.width,h:r.height,border:cs.borderTopColor,bw:cs.borderTopWidth,bg:cs.backgroundColor,txt:getComputedStyle(b.querySelector('.dl-per')).color};}""")
    assert r["w"] > 100 and r["h"] > 50 and r["bw"] == "2px" and r["border"] == "rgb(0, 0, 0)" and r["txt"] == "rgb(0, 0, 0)", r
    assert r["bg"] in ("rgba(0, 0, 0, 0)", "transparent"), r
    ctx.close()


def test_the_box_fits_the_printable_width_in_chromium(site, webkit):
    box = {}

    def run():                                  # (its own thread: a second sync Playwright cannot share the fixture's loop)
        with pw.sync_playwright() as p:
            try:
                c = p.chromium.launch()
            except Exception as e:
                box["skip"] = str(e)
                return
            pg = c.new_page(viewport={"width": 1440, "height": 900})
            pg.goto(site + "/t.html")
            pg.wait_for_timeout(500)
            pg.evaluate("showDetail(typeof ENVS!=='undefined'&&ENVS['frcp-many']?'env':'theme','frcp-many')")
            pg.evaluate("document.documentElement.classList.add('printing','print-current')")
            pg.emulate_media(media="print")
            pg.set_viewport_size({"width": 720, "height": 900})
            pg.wait_for_timeout(200)
            box["right"] = pg.evaluate("document.querySelector('#detail-content .dl-box').getBoundingClientRect().right")
            c.close()
    t = threading.Thread(target=run)
    t.start()
    t.join()
    if "skip" in box:
        pytest.skip(f"no chromium: {box['skip']}")
    assert box["right"] <= 720, box


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_descriptions_line_up_down_the_box_at_d1440(webkit, site, style):
    ctx, pg = open_page(webkit, site, style, "frcp-many")
    xs = pg.evaluate("[...document.querySelectorAll('#detail-content .dl-tx')].map(e=>e.getBoundingClientRect().left)")
    assert len(xs) == 4 and max(xs) - min(xs) <= 1, xs
    ctx.close()


@pytest.mark.parametrize("period,quote", [
    ("1 year", "more than one year after"), ("30 days", "within thirty (30) days"), ("21 days", "twenty-one days after"),
    ("1 day", "within 3 days and 1 day"), ("90 days", "ninety days"), ("2 years", "a 2-year bar"), ("6 months", "six months")])
def test_a_period_the_quote_states_is_accepted_in_any_wording(period, quote):
    from alto.build.brief import validate_brief
    d = _doc([{"id": "v", "name": "V", "sections": [{"h": "S", "t": "s"}],
               "deadlines": [{"period": period, "what": "w", "quote": quote, "cite": "c"}]}])
    validate_brief(load_brief(d)[0])


@pytest.mark.parametrize("period,quote", [
    ("30 days", "within 20 days"), ("1 year", "within 1 month"), ("21 days", "within 12 days"),
    ("7 days", "a reasonable time"), ("14 days", "within 21 days after serving")])
def test_a_period_the_quote_does_not_state_is_refused(period, quote):
    from alto.build.brief import validate_brief
    d = _doc([{"id": "v", "name": "V", "sections": [{"h": "S", "t": "s"}],
               "deadlines": [{"period": period, "what": "w", "quote": quote, "cite": "c"}]}])
    with pytest.raises(BriefError, match="does not appear in the quote"):
        validate_brief(load_brief(d)[0])
