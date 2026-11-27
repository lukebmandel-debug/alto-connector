"""Phone audit 2026-11-26, B9 + B14 (Memory Blueprint on a phone, one floor): no tag under the name card, the tabs, the title or the bottom tiles, none on another
and none off the page (a tag with no free place is a dot by its room); the credits line and the Key sheet clear of FIND and MENU, the sheet with a 44pt close;
a turned phone opens the label as its pill; the card's Part label backed and in one row with its close button. Real HTTP, WebKit. Skipped without Playwright."""
import pytest

from tests.test_blueprint_enlarge import CHROME, ONE_FLOOR, PHONE, _open, browser, needs_all, site  # noqa: F401  (fixtures)

pytestmark = needs_all

FLOOR = """(chrome)=>{const vw=innerWidth,vh=innerHeight, meet=(a,b,m)=>Math.min(a.right,b.right)-Math.max(a.left,b.left)>(m||1)&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>(m||1);
 const pills=[...document.querySelectorAll('#bldg-root .bl-pill:not(.bl-off)')].map(p=>({n:p.textContent.trim().slice(0,6),r:p.getBoundingClientRect(),dot:p.classList.contains('bl-dot')})).filter(p=>p.r.width>1);
 const ov=[]; for(let i=0;i<pills.length;i++) for(let j=i+1;j<pills.length;j++) if(meet(pills[i].r,pills[j].r)) ov.push(pills[i].n+'/'+pills[j].n);
 const ch=chrome.filter(c=>!/bl-foot/.test(c.id)), under=[]; pills.forEach(p=>ch.forEach(c=>{ if(meet(p.r,{left:c.l,top:c.t,right:c.r,bottom:c.b})) under.push(p.n+'@'+c.id); }));
 const off=pills.filter(p=>p.r.left<0||p.r.right>vw||p.r.top<0||p.r.bottom>vh).map(p=>p.n);
 const f=document.querySelector('#bldg-root .bl-foot'), tiles=chrome.filter(c=>c.t>vh/2&&(c.r-c.l)<vw*.45&&!/^bl-/.test(c.id)); let footHit=[];
 if(f){ const rg=document.createRange(); rg.selectNodeContents(f); [...rg.getClientRects()].forEach(q=>tiles.forEach(c=>{ if(meet(q,{left:c.l,top:c.t,right:c.r,bottom:c.b})) footHit.push(c.id); })); }
 return {n:pills.length, dots:pills.filter(p=>p.dot).length, overlap:ov, underChrome:under, offPage:off, footUnderTiles:[...new Set(footHit)], tiles:tiles.map(c=>c.id)};}"""
SHEET = """(chrome)=>{const s=document.querySelector('#bldg-root .bl-credits'); if(!s||s.hidden) return 'not open'; const r=s.getBoundingClientRect(), x=s.querySelector('.bl-x'), xr=x.getBoundingClientRect(), vh=innerHeight;
 const meet=(a,b)=>Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1;
 const hit=chrome.filter(c=>c.t>vh/2&&!/^bl-/.test(c.id)&&meet(r,{left:c.l,top:c.t,right:c.r,bottom:c.b})).map(c=>c.id);
 return {underTiles:hit, close:[Math.round(xr.width),Math.round(xr.height)], closeInSheet:xr.top>=r.top-1&&xr.right<=r.right+1};}"""
POP = """()=>{const w=document.querySelector('#bldg-root .bl-enl:not(.bl-out)'); if(!w) return 'no popover'; const u=w.querySelector('.node-unit'), x=w.querySelector('.bl-enlx'), c=w.querySelector('.node-card');
 if(!u) return 'no unit'; const ur=u.getBoundingClientRect(), xr=x.getBoundingClientRect(), cr=c.getBoundingClientRect(), bg=getComputedStyle(u).backgroundColor;
 return {unit:u.textContent.trim(), backed:!/rgba\\(0, 0, 0, 0\\)|transparent/.test(bg), dCentre:Math.round(((ur.top+ur.bottom)-(xr.top+xr.bottom))/2), meetsClose:ur.right>xr.left, aboveCard:ur.bottom<=cr.top+1};}"""
SIZES = {"p390": PHONE, "p375": dict(PHONE, viewport={"width": 375, "height": 667}), "l844": dict(PHONE, viewport={"width": 844, "height": 390})}


@pytest.mark.parametrize("size", list(SIZES))
@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_a_phones_floor_keeps_its_tags_sheet_and_card_label_clear(browser, site, style, size):
    if browser.browser_type.name != "webkit":
        pytest.skip("WebKit (Luke uses Safari)")
    ctx, pg, errors = _open(browser, site, style, SIZES[size])
    try:
        pg.evaluate(ONE_FLOOR); pg.wait_for_timeout(1500)
        f = pg.evaluate(FLOOR, pg.evaluate(CHROME))
        assert f["n"] >= 30 and f["overlap"] == [] and f["underChrome"] == [] and f["offPage"] == [], f
        assert f["footUnderTiles"] == [], f
        if size == "l844":
            assert pg.evaluate("document.querySelector('#bldg-root .bl-head').classList.contains('bl-min')")   # a turned phone: the label is its pill
            assert f["dots"] <= 6, f   # the plan has the screen, so nearly every tag keeps its number
        pg.locator("#bldg-root .bl-foot").click(force=True); pg.wait_for_timeout(400)
        s = pg.evaluate(SHEET, pg.evaluate(CHROME))
        assert s["underTiles"] == [] and s["close"][0] >= 44 and s["close"][1] >= 44 and s["closeInSheet"], s
        pg.locator("#bldg-root .bl-credits .bl-x").click(); pg.wait_for_timeout(200)
        assert pg.evaluate("document.querySelector('#bldg-root .bl-credits').hidden")
        pid = pg.evaluate("[...document.querySelectorAll('#bldg-root .bl-pill:not(.bl-off):not(.bl-dot)')].find(p=>{const r=p.getBoundingClientRect(); return r.top>innerHeight*.35&&r.top<innerHeight*.7;}).dataset.node")
        pg.evaluate("id=>AltoBuilding.enlarge(id)", pid); pg.wait_for_timeout(900)
        p = pg.evaluate(POP)
        assert p["backed"] and abs(p["dCentre"]) <= 1 and not p["meetsClose"] and p["aboveCard"], p
        assert not errors
    finally:
        ctx.close()
