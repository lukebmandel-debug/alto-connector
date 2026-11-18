"""Holding a card or branch in outline edit mode (1440x900, every style): no connector runs through a card, on the
way or after the drop, and the plate that names the move never covers the held card's title (Board B-1117-OUT240D).
Skipped when Playwright or its browsers are not installed."""
import pytest

from test_outline_branch_drag import _edit, _grab, _open, url  # noqa: F401

# every connector's route, sampled every few px, against every card's drawn box (a held card is drawn by a translate);
# a point on a line starts and ends under its own two cards: only the other cards count
CROSS = """() => { var B={}; document.querySelectorAll('#world .node').forEach(function(el){
  var c=el.querySelector('.node-card'); if(!c||!el.offsetWidth) return; var m=/^(-?[\\d.]+)px(?:\\s+(-?[\\d.]+)px)?/.exec(el.style.translate||'');
  B[el.id.slice(5)]=[parseFloat(el.style.left)-c.offsetWidth/2+(m?+m[1]:0), parseFloat(el.style.top)-c.offsetHeight/2+(m?+(m[2]||0):0), c.offsetWidth, c.offsetHeight]; });
  var bad=[], I=6;
  document.querySelectorAll('#world > svg path').forEach(function(p){
    if(getComputedStyle(p).display==='none'||getComputedStyle(p).visibility==='hidden'||+getComputedStyle(p).opacity===0) return;
    var n=p.getTotalLength(), e=p.getAttribute('data-edge')||'';
    for(var s=0;s<=n;s+=4){ var q=p.getPointAtLength(s);
      for(var i in B){ if(i===e.split('|')[0]||i===e.split('|')[1]) continue; var b=B[i]; if(q.x>b[0]+I&&q.x<b[0]+b[2]-I&&q.y>b[1]+I&&q.y<b[1]+b[3]-I){ bad.push(e+' through '+i+' @'+Math.round(q.x)+','+Math.round(q.y)); s=n; break; } } }
  }); return bad; }"""
PLATE = """() => { var t=document.getElementById('aed-rztip'), h=document.querySelector('#world .node.aed-moving .node-card .node-title, #world .node.aed-moving .node-card h3, #world .node.aed-moving .node-card [class*=title]');
  if(!t||!h||!t.classList.contains('show')) return null; var a=t.getBoundingClientRect(), b=h.getBoundingClientRect();
  var c=document.querySelector('#world .node.aed-moving .node-card'), cr=c&&c.getBoundingClientRect();
  return {card: !!cr&&a.left<cr.right&&a.right>cr.left&&a.top<cr.bottom&&a.bottom>cr.top, hit: a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top, a:[a.left,a.top,a.right,a.bottom], b:[b.left,b.top,b.right,b.bottom], vw:innerWidth, vh:innerHeight}; }"""


@pytest.fixture(params=[("webkit", None), ("webkit", "retro"), ("webkit", "holo"), ("chromium", None)], ids=lambda p: f"{p[0]}-{p[1] or 'classic'}")
def pg(request, url):
    p = _open(request, url, request.param[0], request.param[1])
    p.set_viewport_size({"width": 1440, "height": 900})
    p.wait_for_timeout(500)
    return _edit(p)


def test_no_connector_crosses_a_card_while_held_or_after_the_drop_and_the_plate_clears_the_title(pg):
    rest = pg.evaluate(CROSS)           # (a settled outline runs some trunk lines behind the cards of other branches: its own design)
    x, y, k = _grab(pg, "definiteness")
    pg.mouse.move(x, y)
    pg.wait_for_timeout(600)
    pg.mouse.down()
    for s in range(1, 11):
        pg.mouse.move(x + 300 * k * s / 10, y)
        pg.wait_for_timeout(60)
    pg.wait_for_timeout(700)
    mid, plate = pg.evaluate(CROSS), pg.evaluate(PLATE)
    assert plate, "no plate or no title found"
    assert not plate["hit"] and not plate["card"], plate
    assert 20 <= plate["a"][0] and plate["a"][2] <= plate["vw"] - 20 and 20 <= plate["a"][1] and plate["a"][3] <= plate["vh"] - 20, plate
    pg.mouse.up()
    pg.wait_for_timeout(1200)
    after = pg.evaluate(CROSS)
    assert not mid, mid[:6]
    assert len(after) <= len(rest), (len(rest), len(after), after[:6])           # the drop leaves no stale line behind
    assert not pg.evaluate("document.documentElement.classList.contains('aed-lines-held')"), "the lines are still held back after the drop"

