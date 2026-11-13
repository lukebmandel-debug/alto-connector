"""A phone held on its side (chunk 5 of ORG/phone-ui-audit-1111.md; Art sheet 1111b option 5-C, locked by Luke 2026-11-11): rows C1, C3, W2, F5, H1.

One 44 pt header row (clef, previous name, title, next name, wordmark: all kept) and the one-card view's card as a two-page spread (unit, kind, title and the chips left; the text right, scrolling
inside its page), 16 pt clear of the safe edges and of the two corner controls; the whole view's, the Atlas's and the homepage's headers on the same footing. Portrait is not touched.

Static checks always; WebKit checks (headless, offline, silent: no cloud env, no account, nothing played) when Playwright is installed. WebKit has no Safari bars and no safe areas, so the bars' box is
the viewport height (874 x 292 is the real box on the 402 pt phone, 250 the least it leaves) and the island's insets are injected (62 pt on 874, 48 on 812) the way tests/test_phone_shell.py does.
The real iPhone rows stay in ORG/notes-testing/alto-phone-landscape/SIM-RECHECK.md."""
import asyncio
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from alto.build import phone_minimal, palace_world  # noqa: E402


def test_landscape_rules_live_in_one_media_query_and_the_shorthand_is_expanded():
    css = phone_minimal._land()
    assert css.startswith("@media (orientation:landscape) and (max-height:480px){") and css.endswith("}")
    assert css.count("@media") == 1
    assert not re.search(r"\b(LC|LH)\b|@@", css)
    assert phone_minimal.LAND_MQ in phone_minimal.ASSET
    assert "--ls-l" not in phone_minimal._expand(phone_minimal.CSS), "nothing of it is outside the query: the portrait CSS is the CSS it was"


def test_atlas_insets_for_a_phone_on_its_side_are_there():
    src = Path(palace_world.__file__).read_text(encoding="utf-8")
    assert "function sideways()" in src and "sideways()&&!S.globe" in src


def test_home_header_backing_is_touch_and_landscape_only():
    from alto.build import pages
    html = pages.build_home([])
    i = html.index("a phone on its side (Safari's bars leave")
    assert "(min-width:641px) and (orientation:landscape) and (max-height:480px) and (pointer:coarse)" in html[i:i + 700]


# ── WebKit ──
def _pw():
    import phone_matrix as pm
    try:
        pm._playwright()
    except ImportError:
        pytest.skip("Playwright is not installed")
    return pm


G = r"""() => { const de=document.documentElement, vw=innerWidth, vh=innerHeight, $=s=>document.querySelector(s);
 const R=e=>{ if(!e) return null; const r=e.getBoundingClientRect(); return [r.left,r.top,r.right,r.bottom].map(v=>Math.round(v*10)/10); };
 const vis=e=>{ if(!e) return false; const c=getComputedStyle(e),r=e.getBoundingClientRect(); return c.display!=='none'&&c.visibility!=='hidden'&&r.width>1&&r.height>1; };
 const o={vw,vh,cls:de.className}; const nav=$('#nav'), bar=$('#timeline-label-bar'), card=$('.node.mobile-featured .node-card'), d=card&&card.querySelector('.node-desc');
 o.nav=R(nav); o.bar=R(bar); o.clef=R($('#nav .brand-mark')); o.word=R($('#nav svg.brand-word')); o.title=R($('#nav .title')); o.prev=R($('#tlb-prev')); o.next=R($('#tlb-next'));
 o.prevT=($('#tlb-prev')||{}).textContent; o.nextT=($('#tlb-next')||{}).textContent; o.titleT=($('#nav .title')||{}).textContent;
 o.prevVis=vis($('#tlb-prev')); o.nextVis=vis($('#tlb-next')); o.clefVis=vis($('#nav .brand-mark')); o.wordVis=vis($('#nav svg.brand-word')); o.titleVis=vis($('#nav .title'));
 // the previous / next names as drawn (the text's own box, not its slot)
 const tb=e=>{ if(!e) return null; const r=document.createRange(); r.selectNodeContents(e); const q=r.getBoundingClientRect(); return q.width?[q.left,q.top,q.right,q.bottom].map(v=>Math.round(v*10)/10):null; };
 o.prevTx=tb($('#tlb-prev')); o.nextTx=tb($('#tlb-next')); o.unitTx=tb($('.node.mobile-featured .node-unit'));
 o.find=R($('#pmin-find')); o.menu=R($('#hamburger-tab')); o.card=R(card); o.af=R($('#af-btn')); o.afOn=!!($('#af-btn')&&$('#af-btn').classList.contains('on'));
 if(card){ o.grid=getComputedStyle(card).display; for(const k of ['node-unit','node-tag','node-title','node-footer','node-desc','node-order']){ const e=card.querySelector('.'+k); o[k]=vis(e)?R(e):null; }
   o.sp=R($('.node.mobile-featured .sp-tag')); }
 if(d) o.desc={sh:d.scrollHeight,ch:d.clientHeight,oy:getComputedStyle(d).overflowY};
 o.navBg=nav?getComputedStyle(nav).backgroundColor:null; o.barBg=bar?getComputedStyle(bar).backgroundColor:null; o.htmlBg=getComputedStyle(de).backgroundColor;
 const ix=$('#ph-ix'); o.ix=vis(ix)?R(ix):null; o.sw=R($('#summary-wrap'));
 o.chips=[...document.querySelectorAll('#world .phase-label-float')].filter(vis).map(R).slice(0,4);
 o.scrollW=de.scrollWidth; return o; }"""
LONG = ("A contract forms on mutual assent to a bargain, supported by consideration. Assent is judged by the words and acts, not by what a party later says he meant. " * 5)


@pytest.fixture(scope="module")
def site():
    pm = _pw()
    pages, plans, art = pm.build_pages()
    s = pm.serve(pages, plans, art)
    yield pm, f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


def _inset(n):
    return ("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');"
            "s.textContent='#sh-probe{padding-left:%dpx!important;padding-right:%dpx!important}';document.head.appendChild(s);});" % (n, n))


async def _shoot(site, cfgs):
    """cfgs: {key: (page, query, w, h, inset, long_text)} -> {key: metrics}; one browser, one page per cell."""
    pm, base = site
    out = {}
    async with pm._playwright().async_playwright() as p:
        b = await p.webkit.launch()
        for key, (page, q, w, h, inset, long_text) in cfgs.items():
            ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True, user_agent=pm.UA)
            if inset:
                await ctx.add_init_script(_inset(inset))
            pg = await ctx.new_page()
            await pg.goto(f"{base}/{page}.html?{q}", wait_until="load", timeout=45000)
            for _ in range(60):          # settled: the hosted layer is in, and the shell has run when there is one
                if await pg.evaluate("document.documentElement.classList.contains('pmin')&&(/sh-off/.test(document.documentElement.className)||document.documentElement.classList.contains('sh'))"):
                    break
                await pg.wait_for_timeout(150)
            await pg.wait_for_timeout(1800 if "style=" in q else 900)
            if long_text:
                await pg.evaluate("t=>{const d=document.querySelector('.node.mobile-featured .node-desc'); if(d) d.textContent=t;}", long_text)
                await pg.wait_for_timeout(300)
            out[key] = await pg.evaluate(G)
            await ctx.close()
        await b.close()
    return out


def _run(site, cfgs):
    try:
        return asyncio.run(_shoot(site, cfgs))
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise


SIZES = [(874, 292, 62), (874, 250, 62), (812, 250, 48)]
STYLES = ["classic", "retro", "holo"]


def _qs(style, shell=True, view="card"):
    return "&".join(x for x in (f"view={view}", "" if style == "classic" else f"style={style}", "" if shell else "shell=0") if x)


@pytest.fixture(scope="module")
def cells(site):
    cfgs = {}
    for w, h, i in SIZES:
        for st in STYLES:
            cfgs[("tl", st, w, h, "on")] = ("timeline", _qs(st), w, h, i, None)
    for st in STYLES:
        cfgs[("tl", st, 874, 250, "off")] = ("timeline", _qs(st, shell=False), 874, 250, 0, None)
        cfgs[("ol", st, 874, 250, "on")] = ("outline-long", _qs(st), 874, 250, 62, None)
    cfgs[("long", "classic", 874, 250, "on")] = ("timeline", _qs("classic"), 874, 250, 62, LONG)
    cfgs[("long", "retro", 812, 250, "on")] = ("timeline", _qs("retro"), 812, 250, 48, LONG)
    for st in ("classic", "retro"):
        cfgs[("port", st, 402, 874, "on")] = ("timeline", _qs(st), 402, 874, 0, None)
    return _run(site, cfgs)


def _inter(a, b, pad=0.5):
    return bool(a and b and min(a[2], b[2]) - max(a[0], b[0]) > pad and min(a[3], b[3]) - max(a[1], b[1]) > pad)


LAND_KEYS = ([("tl", st, w, h, "on") for w, h, _ in SIZES for st in STYLES] + [("tl", st, 874, 250, "off") for st in STYLES]
             + [("ol", st, 874, 250, "on") for st in STYLES])


def _insets(key):
    return (62 if key[2] == 874 else 48) if key[4] == "on" else 0


@pytest.mark.parametrize("key", LAND_KEYS, ids=lambda k: "-".join(map(str, k)))
def test_one_44pt_header_row_with_every_piece_kept_and_clear_of_the_island(cells, key):
    m, I = cells[key], _insets(key)
    assert m["nav"][1] == 0 and abs(m["nav"][3] - 44) <= 1, m["nav"]
    assert m["bar"][1] == 0 and abs(m["bar"][3] - 44) <= 1, m["bar"]
    for k in ("clefVis", "wordVis", "titleVis", "prevVis", "nextVis"):
        assert m[k], (k, m)
    assert m["prevT"].strip() and m["nextT"].strip() and m["titleT"].strip()
    parts = {"clef": m["clef"], "title": m["title"], "prevname": m["prevTx"], "nextname": m["nextTx"], "word": m["word"]}
    for k, r in parts.items():
        assert r, k
        assert r[0] >= I - 0.5 and r[2] <= m["vw"] - I + 0.5, (k, r)          # nothing under the island
        assert r[1] >= 0 and r[3] <= 44.5, (k, r)                              # inside the one row
    assert m["clef"][0] >= I + 14 and m["word"][2] <= m["vw"] - I - 14
    names = list(parts)
    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            assert not _inter(parts[names[a]], parts[names[b]]), (names[a], names[b], parts)
    assert m["scrollW"] <= m["vw"] + 1


@pytest.mark.parametrize("key", LAND_KEYS, ids=lambda k: "-".join(map(str, k)))
def test_the_card_is_a_spread_inside_the_box_clear_of_the_edges_and_the_corner_controls(cells, key):
    m, I = cells[key], _insets(key)
    c = m["card"]
    assert m["grid"] == "grid"
    assert c[0] >= I + 16 and c[2] <= m["vw"] - I - 16, c                      # 16 pt from the safe edges
    assert c[1] >= 44 + 4 and c[3] <= m["vh"] - 8 + 0.5, (c, m["vh"])         # under the row, in the bars' box
    for k in ("find", "menu"):
        assert m[k] and not _inter(c, m[k]), (k, m[k], c)
    d = m["node-desc"]
    assert d and d[0] > c[0] + (c[2] - c[0]) * .3                              # two pages: the text on the right
    for k in ("node-unit", "node-tag", "node-title", "node-footer"):
        assert m[k], k
    for k in ("node-tag", "node-title", "node-footer"):
        assert m[k][2] <= d[0] + 1, (k, m[k], d)
    assert m["node-order"] and m["node-order"][0] >= d[0]
    assert 300 <= d[2] - d[0] <= 460, d                                        # about 60 characters a line at 14 px, not a 100-character line
    for k in ("node-unit", "node-title", "node-footer", "node-desc"):
        r = m[k]
        assert r[0] >= c[0] and r[2] <= c[2] + 0.5 and r[1] >= c[1] - 0.5 and r[3] <= c[3] + 0.5, (k, r, c)


@pytest.mark.parametrize("key", LAND_KEYS, ids=lambda k: "-".join(map(str, k)))
def test_c3_the_focus_button_sits_in_the_cards_corner_on_nothing_else(cells, key):
    m = cells[key]
    af, c = m["af"], m["card"]
    assert m["afOn"] and af, "the focus button is shown on an enlarged card"
    assert af[0] >= c[0] and af[2] <= c[2] and af[1] >= c[1] and af[3] <= c[3], (af, c)        # in the card's corner
    assert af[0] > m["node-title"][2] and af[0] > (c[0] + c[2]) / 2, (af, c)
    for k in ("clef", "title", "prev", "next", "word", "find", "menu", "node-order", "unitTx", "node-desc", "sp"):
        if m.get(k):
            assert not _inter(af, m[k], 1), (k, af, m[k])
    assert af[2] - af[0] >= 34 - .5 and af[3] - af[1] >= 34 - .5            # still a 34 pt button


@pytest.mark.parametrize("st", STYLES)
def test_the_row_is_the_pages_own_glass_never_a_painted_band(cells, st):
    m = cells[("tl", st, 874, 250, "on")]

    def alpha(c):
        p = re.findall(r"[\d.]+", c or "")
        return float(p[3]) if len(p) > 3 else 1.0
    assert alpha(m["barBg"]) == 0, "the prev / next bar paints nothing of its own (one backing, the nav's)"
    assert alpha(m["navBg"]) < 1 or m["navBg"] == m["htmlBg"] or st == "holo", m      # (the nav's own look: glass, nothing in Retro, Holo's own ground)


@pytest.mark.parametrize("st", ["classic", "retro"])
def test_portrait_is_untouched(cells, st):
    m = cells[("port", st, 402, 874, "on")]
    assert abs(m["nav"][3] - 52) <= 1.5, m["nav"]
    assert abs(m["bar"][3] - (874 - 14)) <= 1.5 and (abs(m["bar"][3] - m["bar"][1] - 44) <= 1.5 or abs(m["bar"][3] - m["bar"][1] - 52) <= 1.5), m["bar"]   # the names are a 44 pt (52 when a name wraps) glass pill at the foot (phone navbar B), no longer a strip under the header
    assert m["grid"] != "grid" and m["desc"]["oy"] == "auto"
    assert m["card"][0] >= 8 and m["card"][2] <= 402 - 8


def test_long_text_scrolls_inside_its_page_and_the_card_does_not_grow(cells):
    for key in (("long", "classic", 874, 250, "on"), ("long", "retro", 812, 250, "on")):
        m, ref = cells[key], cells[("tl", key[1], key[2], 250, "on")]
        assert m["card"] == ref["card"], (m["card"], ref["card"])
        assert m["desc"]["oy"] == "auto" and m["desc"]["sh"] > m["desc"]["ch"] + 20, m["desc"]
        assert m["node-desc"][3] <= m["card"][3] + .5
        assert m["af"] == ref["af"]


def test_a_long_unit_label_wraps_inside_the_card_and_the_chips_stay_on_the_card(cells):
    m = cells[("ol", "classic", 874, 250, "on")]
    c = m["card"]
    assert m["node-footer"][3] <= c[3] + .5 and m["node-unit"][3] <= m["node-tag"][1] + 1
    assert m["node-title"][3] <= m["node-footer"][1] + 1, m


def test_pm_off_keeps_the_old_look(site):
    m = _run(site, {"a": ("timeline", "view=card&pm=0", 874, 250, 0, None)})["a"]
    assert m["nav"] and abs(m["nav"][3] - 52) <= 1.5 and "pmin" not in m["cls"]


def test_a_turn_to_landscape_settles_at_the_second_resize(site):
    """The phone sends its resizes at +78 and +418 ms after orientationchange: the card and the row are right after the last, and a turn back is portrait again."""
    pm, base = site

    async def go():
        async with pm._playwright().async_playwright() as p:
            b = await p.webkit.launch()
            ctx = await b.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, user_agent=pm.UA)
            await ctx.add_init_script(_inset(62))
            pg = await ctx.new_page()
            await pg.goto(f"{base}/timeline.html?view=card", wait_until="load", timeout=45000)
            await pg.wait_for_timeout(2500)
            await pg.set_viewport_size({"width": 874, "height": 402})
            await pg.wait_for_timeout(78)
            await pg.set_viewport_size({"width": 874, "height": 292})
            await pg.wait_for_timeout(340)
            await pg.wait_for_timeout(900)
            land = await pg.evaluate(G)
            await pg.set_viewport_size({"width": 402, "height": 874})
            await pg.wait_for_timeout(1500)
            back = await pg.evaluate(G)
            await b.close()
            return land, back
    try:
        land, back = asyncio.run(go())
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise
    assert abs(land["nav"][3] - 44) <= 1 and land["card"][3] <= land["vh"] - 8 + .5 and land["card"][0] >= 62 + 16, land
    assert abs(back["nav"][3] - 52) <= 1.5 and back["grid"] != "grid", "back in portrait the header and the card are the portrait's again"


@pytest.fixture(scope="module")
def whole(site):
    cfgs = {(st, w): ("timeline", _qs(st, view="whole"), w, 250, 62 if w == 874 else 48, None) for st in STYLES for w in (874, 812)}
    return _run(site, cfgs)


@pytest.mark.parametrize("st", STYLES)
@pytest.mark.parametrize("w", [874, 812])
def test_w2_the_whole_view_starts_under_the_44pt_row_and_the_index_under_its_foot(whole, st, w):
    m = whole[(st, w)]
    assert abs(m["nav"][3] - 44) <= 1 and m["clefVis"] and m["wordVis"] and m["titleVis"]
    assert m["sw"] and m["sw"][1] >= 43, m["sw"]                       # the header rule (the index and the first unit's header take their top from it)
    if m["ix"]:
        assert m["ix"][1] >= 44, m["ix"]
    for r in m["chips"]:
        assert r[1] >= 43, (r, "a unit chip under the header")
