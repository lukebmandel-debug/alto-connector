"""The Memory Blueprint opens on All floors, and moving around there is smooth (Luke B-1126-BLUEPRINT: "make the default on memory blueprint to start off
showing all levels. I also find moving around on all levels to be glitchy").

The cause of the glitch: every frame of a pan or zoom set the svg's viewBox, so WebKit laid out the whole plan again (All floors draws ~3,000 shapes) and the
room names were rebuilt. Now a gesture moves the drawn plan by a CSS transform and the viewBox is committed once, when the gesture settles, with no jump.
Real HTTP, WebKit (Luke uses Safari). Skipped without Playwright."""
import pytest

from tests.test_blueprint_enlarge import DESKTOP, PHONE, _open, browser, needs_all, site  # noqa: F401  (fixtures)

pytestmark = needs_all

ON = "document.querySelector('#bldg-root .bl-tab.on').dataset.level"

GESTURE = """async(zoom)=>{const svg=document.querySelector('#bldg-root svg.bl-svg'), r=svg.getBoundingClientRect(), cx=r.left+r.width*.4, cy=r.top+r.height*.6;
 const els=[...svg.querySelectorAll('path,polygon,rect')].filter(e=>{const q=e.getBoundingClientRect(); return q.width>20&&q.left>0&&q.right<innerWidth&&q.top>0&&q.bottom<innerHeight;}).slice(0,40);
 const vb0=svg.getAttribute('viewBox'), seen=new Set(); let moved=0;
 for(let i=0;i<12;i++){ svg.dispatchEvent(new WheelEvent('wheel',{deltaY:zoom?-8:20,deltaX:zoom?0:13,ctrlKey:zoom,clientX:cx,clientY:cy,bubbles:true,cancelable:true}));
   seen.add(svg.getAttribute('viewBox')); if(svg.style.transform) moved++; await new Promise(r=>requestAnimationFrame(r)); }
 const live=els.map(e=>e.getBoundingClientRect());
 await new Promise(r=>setTimeout(r,700));
 const done=els.map(e=>e.getBoundingClientRect()); let jump=0;
 live.forEach((q,i)=>{ jump=Math.max(jump,Math.abs(q.left-done[i].left),Math.abs(q.top-done[i].top),Math.abs(q.width-done[i].width)); });
 return {n:els.length, vbDuring:[...seen], vb0:vb0, vb1:svg.getAttribute('viewBox'), moved:moved, after:svg.style.transform, jump:jump}; }"""


@pytest.mark.parametrize("dev", ["d1440", "p390"])
def test_the_blueprint_opens_on_all_floors(browser, site, dev):
    ctx, pg, errors = _open(browser, site, ctx_kw={"viewport": DESKTOP["d1440"]} if dev == "d1440" else PHONE)
    try:
        assert pg.evaluate(ON) == "all"
        assert pg.evaluate("document.querySelectorAll('#bldg-root .bl-cellbg[data-fade], #bldg-root [data-fade]').length") > 1   # every floor is drawn
        pg.evaluate("AltoBuilding.selectLevel([...document.querySelectorAll('#bldg-root .bl-tab:not([data-level=outside]):not([data-level=all])')][0].dataset.level)")
        assert pg.evaluate(ON) != "all"   # a floor of its own is still one tap away
        assert not errors
    finally:
        ctx.close()


@pytest.mark.parametrize("zoom", [False, True])
@pytest.mark.parametrize("dev", ["d1440", "p390"])
def test_a_gesture_on_all_floors_moves_one_picture_and_lands_without_a_jump(browser, site, dev, zoom):
    ctx, pg, errors = _open(browser, site, ctx_kw={"viewport": DESKTOP["d1440"]} if dev == "d1440" else PHONE)
    try:
        r = pg.evaluate(GESTURE, zoom)
        assert r["n"] >= 10
        assert len(r["vbDuring"]) <= 2, f"the viewBox (a whole-plan layout) changed {len(r['vbDuring']) - 1} times in 12 frames"   # (one commit allowed: a loaded machine's long frame may settle it once)
        assert r["moved"] >= 6 and r["after"] == "" and r["vb1"] != r["vb0"], r   # moved by a transform, committed once it settled
        assert r["jump"] < 1, f"the plan jumped {r['jump']} px when the gesture settled"
        assert not errors
    finally:
        ctx.close()


def test_a_floor_the_reader_picked_reopens_next_time(browser, site):
    ctx, pg, errors = _open(browser, site, ctx_kw={"viewport": DESKTOP["d1440"]})
    try:
        lv = pg.evaluate("[...document.querySelectorAll('#bldg-root .bl-tab:not([data-level=outside]):not([data-level=all])')][0].dataset.level")
        pg.click(f"#bldg-root .bl-tab[data-level='{lv}']")
        pg.reload(); pg.wait_for_selector("#bldg-root .bl-tab.on")
        assert pg.evaluate(ON) == lv   # the reader's own choice wins over the All-floors default
        pg.click("#bldg-root .bl-tab[data-level='all']")
        pg.reload(); pg.wait_for_selector("#bldg-root .bl-tab.on")
        assert pg.evaluate(ON) == "all"
        assert not errors
    finally:
        ctx.close()
