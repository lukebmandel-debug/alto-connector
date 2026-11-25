"""Classic home card on a narrow phone (320-390px): nothing on a card overlaps -- title, the ⋯, the lock/share glyph,
the bottom buttons and the format plate (brief home-card-p320-1122); the buttons keep a 44px hit area."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_home_lockgap import CASES, browser, srv   # noqa: E402,F401  (the same three cards: private, shared, no plan)
from test_study_plan import NOW   # noqa: E402

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
JS = """()=>{const t=document.querySelector('.course-tile:not(.new-tile)'), out={};
 const add=(k,e)=>{if(!e) return; const q=e.getBoundingClientRect(); if(q.width>0&&q.height>0&&getComputedStyle(e).display!=='none') out[k]=[q.left,q.top,q.right,q.bottom];};
 const ti=t.querySelector('.tile-title'), rg=document.createRange(); rg.selectNodeContents(ti);
 const rr=[...rg.getClientRects()].filter(q=>q.width>0);
 if(rr.length) out.title=[Math.min(...rr.map(q=>q.left)),Math.min(...rr.map(q=>q.top)),Math.max(...rr.map(q=>q.right)),Math.max(...rr.map(q=>q.bottom))];
 add('more',t.querySelector('.tile-more')); add('lock',t.querySelector('.priv-sym')); add('plate',t.querySelector('.tile-emblem'));
 ['tile-reports','tile-share','tile-download'].forEach(c=>add(c,t.querySelector('.'+c)));
 const hit={}; t.querySelectorAll('.tile-reports,.tile-share,.tile-more').forEach(b=>{const a=getComputedStyle(b,'::after'), q=b.getBoundingClientRect();
   hit[b.className]=[q.width-2*parseFloat(a.left||0), q.height-2*parseFloat(a.top||0)];});
 const tr=t.getBoundingClientRect(); return {r:out, hit, tile:[tr.left,tr.top,tr.right,tr.bottom], vw:innerWidth, sw:document.documentElement.scrollWidth}}"""


def _measure(browser, srv, case, style, w):   # noqa: F811
    ctx = browser.new_context(viewport={"width": w, "height": 740}, is_mobile=True, has_touch=True, user_agent=UA)
    pg = ctx.new_page()
    pg.add_init_script(NOW + "try{localStorage.setItem('alto-bg-home-v1-style','%s')}catch(e){}" % style)
    pg.goto(srv + case + ".html")
    pg.wait_for_timeout(600)
    pg.evaluate("(s)=>window._altoStyle && window._altoStyle.set(s)", style)
    pg.wait_for_timeout(900)
    got = pg.evaluate(JS)
    ctx.close()
    return got


def _overlaps(r):
    ks, bad = list(r), []
    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            p, q = r[a], r[b]
            if min(p[2], q[2]) - max(p[0], q[0]) > 0.5 and min(p[3], q[3]) - max(p[1], q[1]) > 0.5:
                bad.append((a, b))
    return bad


@pytest.mark.parametrize("w", [320, 360, 390])
@pytest.mark.parametrize("case", list(CASES))
def test_classic_phone_card_has_no_overlaps(browser, srv, case, w):   # noqa: F811
    m = _measure(browser, srv, case, "classic", w)
    r = m["r"]
    assert {"title", "more", "lock", "plate", "tile-share"} <= set(r), r
    assert not _overlaps(r), (_overlaps(r), r)
    for k, v in r.items():                                   # wholly inside the card
        assert v[0] >= m["tile"][0] and v[2] <= m["tile"][2] + 0.5 and v[3] <= m["tile"][3] + 0.5, (k, v, m["tile"])
    for k, (hw, hh) in m["hit"].items():                     # 44px hit areas stay
        assert hw >= 34 and hh >= 44, (k, hw, hh)
    assert m["sw"] <= m["vw"]                                # no sideways scroll
