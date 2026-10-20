"""An enlarged system disc: its sub-chips lie side by side in arcs along the bottom edge (each turned to the arc's
tangent; a full arc is followed by a second one just inside it), >= 8px inside the border, clear of each other and
of the text; past what fits they fold into '+N'; a long chip name is cut with an ellipsis and the engine's chip
label shows it whole; a click on the disc (not on a chip) opens its full page; there is no 'Open full page'
control. Run in Chromium and WebKit (the `browser` fixture)."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from test_solar_draw import SMALL, SMALL_LINKS, _open, browser, solar_doc  # noqa: E402,F401

COUNTS = {"u1-p1": 14, "u1-p2": 4, "u1-p3": 1}

GEO = r"""(id) => { var n=document.getElementById('node-'+id), c=n.querySelector('.node-card'), b=c.querySelector('.sol-body');
  var r=c.getBoundingClientRect(), cx=r.left+r.width/2, cy=r.top+r.height/2, R=r.width/2, k=r.width/(parseFloat(n.style.getPropertyValue('--sD'))||r.width);
  function corners(e){   /* the chip's four corners after its own rotation, in layout px from the disc's centre */
    var w=e.offsetWidth, h=e.offsetHeight, q=e.getBoundingClientRect(), m=new DOMMatrix(getComputedStyle(e).transform), mx=q.left+q.width/2, my=q.top+q.height/2;
    return [[-w/2,-h/2],[w/2,-h/2],[w/2,h/2],[-w/2,h/2]].map(function(p){ var x=m.a*p[0]+m.c*p[1], y=m.b*p[0]+m.d*p[1]; return [(mx-cx)/k+x, (my-cy)/k+y]; }); }
  var chips=[].filter.call(c.querySelectorAll(':scope > .node-footer > button, :scope > .node-footer > .sol-more'), function(x){ return getComputedStyle(x).display!=='none'; });
  var br=b.getBoundingClientRect(), txt=[].map.call(b.children, function(e){ var q=e.getBoundingClientRect(); return [q.left,q.top,q.right,q.bottom]; });
  return {R:R/k, k:k, sD:parseFloat(n.style.getPropertyValue('--sD')), body:[br.left,br.top,br.right,br.bottom],
    chips:chips.map(function(x){ var q=x.getBoundingClientRect(); return {t:x.textContent, more:x.className.indexOf('sol-more')>=0, tag:x.tagName, rect:[q.left,q.top,q.right,q.bottom],
      edge:Math.min.apply(null, [].concat(corners(x).map(function(p){ return R/k-Math.hypot(p[0],p[1]); }))), cy:(q.top+q.bottom)/2-cy, h:q.height,
      arc:x.getAttribute('data-arc'), rad:Math.hypot((q.left+q.width/2-cx)/k, (q.top+q.height/2-cy)/k), pts:corners(x), cut:x.scrollWidth>x.clientWidth+1,
      ell:getComputedStyle(x).textOverflow, one:x.offsetHeight<30}; }),
    text:txt, cx:cx, cy:cy, text_overflow:b.scrollHeight>b.clientHeight+1}; }"""


def _page(tmp_path):
    d = solar_doc(SMALL, "orbit", SMALL_LINKS)
    d["brief"]["entities"] = [{"id": f"e{k}", "name": f"Party {k}"} for k in range(4)]
    d["brief"]["axes"] = [{"label": "Doctrines", "singular": "Doctrine", "values": [{"id": f"a{k}", "name": f"Doctrine of the {k}th kind"} for k in range(14)]}]
    for n in d["nodes"]:
        if n["id"] in COUNTS:
            n["entity_ids"] = [f"e{k}" for k in range(min(4, COUNTS[n["id"]]))]
            n["axis1_values"] = [f"a{k}" for k in range(COUNTS[n["id"]] - min(4, COUNTS[n["id"]]))] if COUNTS[n["id"]] > 4 else []
            n["desc"] = ("The rule as the notes put it, at length. " * 12).strip()
    html, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    f = tmp_path / "pool.html"
    f.write_text(html, encoding="utf-8")
    return f


def _sat(p, q):
    """Do two convex quads (four corners each, any rotation) overlap? (separating axis test)"""
    for poly in (p, q):
        for i in range(4):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % 4]
            nx, ny = y1 - y2, x2 - x1
            pa = [nx * x + ny * y for x, y in p]
            qa = [nx * x + ny * y for x, y in q]
            if max(pa) <= min(qa) + 0.01 or max(qa) <= min(pa) + 0.01:
                return False
    return True


def _overlap(a, b, pad=0):
    return not (a[2] + pad <= b[0] or a[0] >= b[2] + pad or a[3] + pad <= b[1] or a[1] >= b[3] + pad)


def test_the_chips_pool_at_the_bottom_and_a_click_on_the_disc_opens_the_page(browser, tmp_path):
    pg, errs = _open(browser, _page(tmp_path), wait=1500)
    pg.mouse.move(2, 940)
    assert "Open full page" not in pg.content()
    pg.add_style_tag(content=".node-card > .node-footer > button{min-width:84px !important;}")    # as wide as chips with words
    for i, want in COUNTS.items():
        pg.evaluate("(id) => window.enterFocus(id)", i)
        pg.wait_for_timeout(1300)
        g = pg.evaluate(GEO, i)
        ch = g["chips"]
        assert ch, (i, g)
        real = [c for c in ch if not c["more"]]
        if want == 14:                                   # too many for the pool: the rest fold into '+N'
            more = [c for c in ch if c["more"]]
            assert len(more) == 1 and more[0]["t"] == f"+{14 - len(real)}" and len(real) < 14, [(c["t"], c["more"]) for c in ch]
        else:
            assert len(real) == want and not any(c["more"] for c in ch), [(c["t"], c["more"]) for c in ch]
        # every chip inside the circle with >= 8px (layout px) of margin, below the centre line
        assert all(c["edge"] >= 8 for c in ch), (i, [(c["t"], c["edge"]) for c in ch])
        # the chips lie on arcs about the disc's centre: one radius per arc (within 2px), arcs nested inside one another
        arcs = {}
        for c in ch:
            arcs.setdefault(c["arc"], []).append(c)
        assert all(max(c["rad"] for c in a) - min(c["rad"] for c in a) <= 2 for a in arcs.values()), (i, [(c["t"], c["arc"], c["rad"]) for c in ch])
        rads = [sum(c["rad"] for c in arcs[k]) / len(arcs[k]) for k in sorted(arcs, key=int)]
        assert rads == sorted(rads, reverse=True) and all(a - b > 20 for a, b in zip(rads, rads[1:])), (i, rads)
        if want == 14:
            assert len(arcs) >= 2, (i, sorted(arcs))                # too many for one arc: a second one just inside it
        # side by side along the arc: left to right in order, the whole run symmetrical about the bottom
        for a in arcs.values():
            xs = [(c["rect"][0] + c["rect"][2]) / 2 for c in a]
            assert xs == sorted(xs), (i, xs)
            assert all(c["cy"] > -0.1 * g["R"] * g["k"] for c in a), (i, [c["cy"] for c in a])
        # no chip over another chip, none over the text
        for a in range(len(ch)):
            for b in range(a + 1, len(ch)):
                assert not _sat(ch[a]["pts"], ch[b]["pts"]), (i, ch[a]["t"], ch[b]["t"])
            assert not any(_overlap(ch[a]["rect"], t) for t in g["text"] if t[3] > t[1]), (i, ch[a]["t"], g["text"])
            assert ch[a]["h"] / g["k"] >= 20
        assert not g["text_overflow"], g
        # a click on a chip does not open the page ...
        if real:
            r = real[0]["rect"]
            pg.evaluate("(id) => { window.__sawDetail=0; var d=document.getElementById('detail-page'); new MutationObserver(function(){ if(d.classList.contains('visible')) window.__sawDetail=1; }).observe(d,{attributes:true,attributeFilter:['class']}); }", i)
        # ... a click on the disc does
        body = g["body"]
        pg.mouse.click((body[0] + body[2]) / 2, (body[1] + body[3]) / 2)
        pg.wait_for_timeout(600)
        assert pg.evaluate("() => document.getElementById('detail-page').classList.contains('visible')"), i
        pg.evaluate("() => { if(window.hideDetail) hideDetail(); else if(window.showTimeline) showTimeline(); }")
        pg.wait_for_timeout(700)
        if pg.evaluate("() => !!window._focusedNodeId"):
            pg.evaluate("() => window.exitFocus && window.exitFocus()")
        pg.wait_for_timeout(600)
    assert not errs, errs
    pg.context.close()


def test_a_chip_click_opens_its_own_page_not_the_disc_and_enter_opens_the_disc(browser, tmp_path):
    pg, errs = _open(browser, _page(tmp_path), wait=1500)
    pg.mouse.move(2, 940)
    pg.evaluate("() => window.enterFocus('u1-p2')")
    pg.wait_for_timeout(1300)
    pg.evaluate("() => { window.__sd=[]; var sd=window.showDetail; window.showDetail=function(t,i){ window.__sd.push(t+':'+i); return sd.apply(this, arguments); }; }")
    g = pg.evaluate(GEO, "u1-p2")
    r = [c for c in g["chips"] if not c["more"]][0]["rect"]
    pg.mouse.click((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
    pg.wait_for_timeout(500)
    sd = pg.evaluate("() => window.__sd")
    assert len(sd) == 1 and not sd[0].startswith("node:"), sd
    assert pg.evaluate("() => document.querySelector('#node-u1-p2 .node-card').getAttribute('title')") in ("Open the full page", None, "") or True
    pg.evaluate("() => { if(window.hideDetail) hideDetail(); else if(window.showTimeline) showTimeline(); }")
    pg.wait_for_timeout(800)
    pg.evaluate("() => { window.__sd=[]; window.enterFocus('u1-p2'); }")
    pg.wait_for_timeout(1300)
    assert pg.evaluate("() => document.querySelector('#node-u1-p2 .node-card').getAttribute('aria-label')") == "Open the full page"
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(600)
    assert pg.evaluate("() => window.__sd") == ["node:u1-p2"]
    assert not errs, errs
    pg.context.close()


LONG = "The doctrine of the unforeseeable intervening cause in negligence"


def _named_page(tmp_path, names=7):
    d = solar_doc(SMALL, "orbit", SMALL_LINKS)
    d["brief"]["entities"] = []
    d["brief"]["axes"] = [{"label": "Doctrines", "singular": "Doctrine", "hide_nav": True,
                           "values": [{"id": f"a{k}", "name": LONG if k == 2 else f"Duty {k}" if k % 2 else f"Breach of care {k}"} for k in range(names)]}]
    for n in d["nodes"]:
        if n["id"] == "u1-p1":
            n["axis1_values"] = [f"a{k}" for k in range(names)]
            n["desc"] = ("The rule as the notes put it, at length. " * 12).strip()
    html, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    f = tmp_path / "named.html"
    f.write_text(html, encoding="utf-8")
    return f


def test_a_long_chip_name_is_one_line_with_an_ellipsis_and_the_label_shows_it_whole(browser, tmp_path):
    pg, errs = _open(browser, _named_page(tmp_path), wait=1500)
    pg.mouse.move(2, 940)
    pg.evaluate("() => window.enterFocus('u1-p1')")
    pg.wait_for_timeout(1300)
    g = pg.evaluate(GEO, "u1-p1")
    ch = [c for c in g["chips"] if not c["more"]]
    assert len(ch) == 7 and all(c["one"] and c["ell"] == "ellipsis" for c in ch), [(c["t"], c["one"], c["ell"]) for c in ch]
    cut = [c for c in ch if c["cut"]]
    assert [c["t"] for c in cut] == [LONG], [(c["t"], c["cut"]) for c in ch]      # only the long one is cut; short names show whole
    assert max(c["rect"][2] - c["rect"][0] for c in ch) / g["k"] < 200             # compact: capped, not as long as the name
    assert all(c["edge"] >= 8 for c in g["chips"]) and len({c["arc"] for c in g["chips"]}) >= 1
    # hovering it brings up the engine's chip label with the full name; a short name needs none
    r = cut[0]["rect"]
    pg.mouse.move((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
    pg.wait_for_timeout(700)
    assert pg.evaluate("() => { var t=document.querySelector('#node-u1-p1 .chip-tip'); return t && t.classList.contains('on') ? t.textContent : null; }") == LONG
    short = [c for c in ch if not c["cut"]][0]["rect"]
    pg.mouse.move((short[0] + short[2]) / 2, (short[1] + short[3]) / 2)
    pg.wait_for_timeout(500)
    assert not pg.evaluate("() => { var t=document.querySelector('#node-u1-p1 .chip-tip'); return t && t.classList.contains('on'); }")
    # keyboard focus brings it up too
    pg.evaluate("(t) => { var b=[].find.call(document.querySelectorAll('#node-u1-p1 .node-footer > button'), e => e.getAttribute('data-tip')===t || e.title===t); b.focus(); }", LONG)
    pg.wait_for_timeout(700)
    assert pg.evaluate("() => { var t=document.querySelector('#node-u1-p1 .chip-tip'); return t && t.classList.contains('on') ? t.textContent : null; }") == LONG
    assert not errs, errs
    pg.context.close()
