import os
from tests.test_blueprint_enlarge import site, browser, _open, ALL_SIZES, STYLES
def test_shots(browser, site):
    if browser.browser_type.name != "webkit": return
    out = os.environ["SHOT_OUT"]
    for style in STYLES:
        for size, nm in (("phone", "p390"), ("phone-land", "844x390")):
            ctx, pg, errors = _open(browser, site, style, ALL_SIZES[size])
            pg.locator('#bldg-root .bl-tab[data-level="all"]').click(force=True)
            pg.wait_for_timeout(2200)
            pg.screenshot(path=f"{out}/allfloors-{style}-{nm}.png")
            pg.evaluate("""()=>{ const s=document.querySelector('#bldg-root svg.bl-svg'), b=s.getBoundingClientRect(); s.dispatchEvent(new WheelEvent('wheel',{deltaY:%d,clientX:b.left+b.width/2,clientY:b.top+b.height/2,bubbles:true,cancelable:true})); }""" % (300 if size=='phone' else 160))
            pg.wait_for_timeout(1500)
            pg.screenshot(path=f"{out}/allfloors-{style}-{nm}-scrolled.png")
            pg.evaluate("""()=>{ const s=document.querySelector('#bldg-root svg.bl-svg'), b=s.getBoundingClientRect(); s.dispatchEvent(new WheelEvent('wheel',{deltaY:%d,clientX:b.left+b.width/2,clientY:b.top+b.height/2,bubbles:true,cancelable:true})); }""" % (-300 if size=='phone' else -160))
            pg.wait_for_timeout(1200)
            if size == "phone":
                b = pg.evaluate("""()=>{ let best=null,n=-1; const pills=[...document.querySelectorAll('#bldg-root .bl-pill[data-node]')];
                  document.querySelectorAll('#bldg-root .bl-cellbg[data-fade]').forEach(e=>{ const c=pills.filter(p=>p.dataset.lv===e.getAttribute('data-fade')).length; if(c>n){n=c;best=e.getBoundingClientRect();} });
                  return [best.left-6,best.top-6,best.width+12,best.height+12,n]; }""")
                pg.screenshot(path=f"{out}/allfloors-crowded-{style}-p390.png", clip=dict(x=max(b[0],0), y=max(b[1],0), width=b[2], height=b[3]))
            ctx.close()
