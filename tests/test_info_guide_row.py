"""The info button of a timeline or outline page (a computer), and the guide it opens.
Luke, 2026-11-17: "this glitch happened to info toggle when i collapsed it again" — in Holographic the button came
back from its guide a square with no lens: the engine's open / shut animation writes the corners inline from
--info-r-open / --info-r-shut, and Holographic carried Retro's square values. And: "the info panel should rise above
the toggle" — the open guide ran down over Search and its own button. It now stands above the bottom-right row (the
homepage's way, v1.9.234), ends 8px or more clear of every fixed control and 20px from the window's edges, and
scrolls inside itself. A phone's guide is its own full-screen sheet: nothing shows on top of it.
Skipped when Playwright or its browsers are not installed."""
import pytest

from test_outline_branch_drag import FAKE, _open, url  # noqa: F401

BTN = """(()=>{var b=document.getElementById('info-btn'), i=document.getElementById('info-icon'), r=b.getBoundingClientRect(), q=i.getBoundingClientRect(), s=getComputedStyle(b);
  function box(e){ var r=e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height].map(function(v){ return Math.round(v * 10) / 10; }); }
  return {cls: b.className, box: box(b), icon: box(i), radius: s.borderRadius, bg: s.backgroundImage + '|' + s.backgroundColor, shadow: s.boxShadow, overflow: s.overflow, translate: s.translate,
    search: box(document.getElementById('search-btn')), searchT: getComputedStyle(document.getElementById('search-btn')).transform};})()"""
OPEN = """(()=>{var b=document.getElementById('info-btn'), p=b.getBoundingClientRect(), near=[], c=document.getElementById('info-content'), i=document.getElementById('info-icon').getBoundingClientRect();
  [].forEach.call(document.querySelectorAll('body *'), function(e){ if(e.closest('#info-btn')) return; var s=getComputedStyle(e);
    if(s.position!=='fixed' || s.display==='none' || s.visibility==='hidden' || +s.opacity===0 || s.pointerEvents==='none') return;
    var r=e.getBoundingClientRect(); if(r.width<8 || r.height<8 || (r.width>innerWidth*.9 && r.height>innerHeight*.9)) return;
    var g=Math.max(Math.max(r.left-p.right, p.left-r.right), Math.max(r.top-p.bottom, p.top-r.bottom)); if(g<8) near.push((e.id||e.className)+':'+Math.round(g)); });
  var ic=Math.max(Math.max(i.left-p.right, p.left-i.right), Math.max(i.top-p.bottom, p.top-i.bottom)), cr=c.getBoundingClientRect();
  return {panel:[p.left,p.top,p.right,p.bottom], win:[innerWidth,innerHeight], near:near, iconGap:ic, icon:[i.left,i.top,i.width,i.height], scroll:[c.scrollHeight,c.clientHeight],
    inside: cr.top>=p.top-1 && cr.bottom<=p.bottom+1 && cr.left>=p.left-1 && cr.right<=p.right+1, oy:getComputedStyle(c).overflowY};})()"""


@pytest.mark.parametrize("engine,style,w,h", [("webkit", "holo", 1000, 650), ("webkit", None, 1000, 650), ("webkit", "retro", 1000, 650),
                                              ("webkit", "holo", 1440, 900), ("webkit", None, 1440, 900), ("chromium", "holo", 1000, 650), ("chromium", None, 1440, 900)])
def test_the_open_guide_stands_above_the_row_and_shut_again_the_button_is_as_it_was(request, url, engine, style, w, h):
    pg = _open(request, url, engine, style)
    pg.set_viewport_size({"width": w, "height": h})
    pg.wait_for_timeout(900)
    before = pg.evaluate(BTN)
    assert before["cls"] == "" and abs(before["box"][2] - before["box"][3]) < 1
    pg.click("#info-icon")
    pg.wait_for_timeout(900)
    o = pg.evaluate(OPEN)
    assert pg.evaluate("document.getElementById('info-btn').classList.contains('expanded')")
    assert o["near"] == [], o                                             # 8px or more from every fixed control (Search, the key, the edit toggle, the rail, the bars)
    l, t, r, b = o["panel"]
    assert l >= 20 and t >= 20 and o["win"][0] - r >= 20 and o["win"][1] - b >= 20, o
    # its own button is still in the row, below the guide and clear of it, where it was (a click on it shuts the guide)
    assert o["iconGap"] >= 8 and abs(o["icon"][0] - before["icon"][0]) <= 3 and abs(o["icon"][1] - before["icon"][1]) <= 3, (o, before["icon"])
    assert abs(o["icon"][2] - before["icon"][2]) <= 3 and abs(o["icon"][2] - o["icon"][3]) <= 1
    assert o["inside"] and o["oy"] in ("auto", "scroll") and (o["scroll"][0] <= o["scroll"][1] or o["scroll"][1] > 100), o      # it scrolls inside itself
    assert pg.evaluate(BTN)["search"] == before["search"]                 # nothing steps aside for it
    pg.mouse.click(300, 400)
    pg.wait_for_timeout(900)
    pg.mouse.move(100, 300)
    pg.wait_for_timeout(500)
    after = pg.evaluate(BTN)
    assert after == before, {k: (before[k], after[k]) for k in before if before[k] != after[k]}
    # and again, by its own button
    pg.click("#info-icon")
    pg.wait_for_timeout(900)
    x, y, ww, hh = pg.evaluate(OPEN)["icon"]
    pg.mouse.click(x + ww / 2, y + hh / 2)
    pg.wait_for_timeout(900)
    pg.mouse.move(100, 300)
    pg.wait_for_timeout(500)
    assert pg.evaluate(BTN) == before


def test_holographic_gives_the_info_button_its_own_corners():
    from alto.build import holo
    assert "{--info-r-open:14px;--info-r-shut:999px;}" in holo.S1_CSS


@pytest.mark.parametrize("style", [None, "holo"])
def test_a_phones_guide_is_a_full_sheet_with_nothing_on_top_of_it(request, url, style):
    pw = pytest.importorskip("playwright.sync_api")
    p = pw.sync_playwright().start()
    request.addfinalizer(p.stop)
    try:
        b = p.webkit.launch()
    except Exception as e:
        pytest.skip(f"no webkit: {e}")
    request.addfinalizer(b.close)
    ctx = b.new_context(**{**p.devices["iPhone 13"], "viewport": {"width": 390, "height": 844}})
    ctx.add_init_script(FAKE)
    pg = ctx.new_page()
    pg.goto(url)
    pg.wait_for_timeout(1500)
    if style:
        pg.evaluate("window._altoStyle.set('%s')" % style)
        pg.wait_for_timeout(1200)
    assert pg.evaluate("getComputedStyle(document.getElementById('info-btn')).display") == "none"
    pg.evaluate("document.getElementById('tutorial-toggle').dispatchEvent(new Event('touchend', {bubbles: true, cancelable: true}))")
    pg.wait_for_timeout(900)
    r = pg.evaluate("""(()=>{var w=document.getElementById('tutorial-wrap'), r=w.getBoundingClientRect(), over=[];
      for(var x=20; x<innerWidth; x+=50) for(var y=20; y<innerHeight; y+=50){ var e=document.elementFromPoint(x, y); if(e && !w.contains(e)) over.push((e.id||e.className)+'@'+x+','+y); }
      return {box:[r.left, r.top, r.right, r.bottom], win:[innerWidth, innerHeight], over:over};})()""")
    assert r["box"][0] <= 0 and r["box"][1] <= 0 and r["box"][2] >= r["win"][0] and r["box"][3] >= r["win"][1] and r["over"] == [], r
