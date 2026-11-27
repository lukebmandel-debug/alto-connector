"""Phone audit 2026-11-26, B5 + B12 (Memory Atlas on a phone). B5: on a phone on its side the Tour stop's card is whole on the screen, clear of the Tour block,
its unit label in words, not a letter a line (the one-card view's landscape spread, phone_minimal, no longer styles a card the Atlas borrowed). B12: zoomed in or out, no place
name runs under a pin's number plate or count badge. Served as test_world_palace_render.py serves its page; WebKit only. Skipped without Playwright."""
import json

import pytest

from tests.test_world_palace_render import browser, html, origin  # noqa: F401  (the shared page and browsers)

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
COLL = """()=>{const meet=(a,b)=>Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1, bad=[];
 const L=[...document.querySelectorAll('#wpal-root .wp-lbl:not(.wp-off)')].filter(e=>getComputedStyle(e).visibility!=='hidden'&&+getComputedStyle(e).opacity>.5);
 const P=[...document.querySelectorAll('#wpal-root .wp-pin')].filter(e=>e.getBoundingClientRect().width>1&&getComputedStyle(e).visibility!=='hidden'&&+getComputedStyle(e).opacity>.5);
 L.forEach(l=>{ const lr=l.getBoundingClientRect(); [...l.children].concat([l]).forEach(()=>{}); P.forEach(p=>{ [p,...p.querySelectorAll('*')].forEach(q=>{ const r=q.getBoundingClientRect(); if(r.width>1&&meet(lr,r)) bad.push(l.textContent.trim().slice(0,18)+' ~ '+(p.textContent||'').trim().slice(0,8)); }); }); });
 return {labels:L.length, pins:P.length, hits:[...new Set(bad)]};}"""
TOUR = """()=>{const vw=innerWidth,vh=innerHeight, c=document.querySelector('#wpal-root .wp-enl, #wpal-root .wp-card.main'); if(!c) return 'no card'; const r=c.getBoundingClientRect();
 const u=c.querySelector('.node-unit'), ur=u&&u.getBoundingClientRect(), lh=u?parseFloat(getComputedStyle(u).fontSize)*1.6:0;
 const t=document.querySelector('#wpal-root .wp-tour'), tr=t&&t.getBoundingClientRect(), meet=(a,b)=>Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1;
 return {card:[Math.round(r.left),Math.round(r.top),Math.round(r.right),Math.round(r.bottom)], inView:r.left>=0&&r.top>=0&&r.right<=vw&&r.bottom<=vh, w:Math.round(r.width), unitTall:u?Math.round(ur.height/lh*10)/10:null, overTourBar:tr?meet(r,tr):null};}"""
ZOOM = """async(id)=>{const pin=[...document.querySelectorAll('#wpal-root .wp-pin')].find(p=>(p.getAttribute('aria-label')||p.title||'').includes(id)||p.dataset.id===id); const svg=document.querySelector('#wpal-root svg'); const pp=[...document.querySelectorAll('#wpal-root .wp-pin.wu1')].map(p=>p.getBoundingClientRect()).filter(q=>q.width>1); const r=pp.length?pp[0]:pin?pin.getBoundingClientRect():{left:innerWidth/2,top:innerHeight/2,width:0,height:0};
 for(let i=0;i<2;i++){ svg.dispatchEvent(new WheelEvent('wheel',{deltaY:25,ctrlKey:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2,bubbles:true,cancelable:true})); await new Promise(q=>setTimeout(q,30)); } return !!pin; }"""


def _phone(browser, origin, style, w, h):
    if browser.browser_type.name != "webkit":
        pytest.skip("WebKit (Luke uses Safari)")
    ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True, user_agent=UA)
    ctx.add_init_script("try{localStorage.setItem('alto-bg-v1-style',%s)}catch(e){}" % json.dumps(style))
    pg = ctx.new_page(); errors = []; pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(origin + "/index.html"); pg.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=30000)
    pg.wait_for_timeout(1200); pg.evaluate("s=>window._altoStyle&&window._altoStyle.set(s)", style); pg.wait_for_timeout(800)
    return ctx, pg, errors


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_a_tour_stops_card_on_a_turned_phone_is_whole_and_clear_of_the_tour_block(browser, origin, style):  # noqa: F811
    ctx, pg, errors = _phone(browser, origin, style, 844, 390)
    try:
        pg.evaluate("AltoWorld.tourMode(true)")
        for i in (0, 4, 8):
            pg.evaluate(f"AltoWorld.tour({i})"); pg.wait_for_timeout(2400)
            t = pg.evaluate(TOUR)
            assert t["inView"] and not t["overTourBar"] and t["unitTall"] < 2.5 and t["w"] >= 100, (i, t)
        assert not errors
    finally:
        ctx.close()


@pytest.mark.parametrize("size", [(390, 844), (375, 667), (844, 390)], ids=["p390", "p375", "l844"])
@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_no_place_name_runs_under_a_pins_plate_as_the_map_zooms(browser, origin, style, size):  # noqa: F811
    ctx, pg, errors = _phone(browser, origin, style, *size)
    try:
        pg.evaluate("AltoWorld.tourMode(true)"); pg.evaluate("AltoWorld.tour(8)"); pg.wait_for_timeout(2500)
        for z in range(8):
            pg.evaluate(ZOOM, "erie"); pg.wait_for_timeout(900)
            c = pg.evaluate(COLL)
            assert c["hits"] == [], (z, c)
        assert not errors
    finally:
        ctx.close()
