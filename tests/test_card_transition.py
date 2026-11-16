"""Phone card view, card to card (Luke, 2026-11-01, Art's spec alto-art-1101-5800-a; phone yes L-1101-233159; Board Art look 13 Nov: text must never sit
on text): the two cards travel side by side over 160ms ease-out, one screen apart, the new one in from the side you travel toward and the old one out; translate
only; none under prefers-reduced-motion; a newer move cancels the running one, so a run of quick taps never queues."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import build_timeline, load_brief   # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


def _page(n=12):
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
    base, nodes, k = d["nodes"], [], 0
    while len(nodes) < n:
        for b in base:
            if len(nodes) < n:
                c = copy.deepcopy(b)
                c["id"], c["title"] = f"{b['id']}-{k}", f"{b['title']} {k}"
                nodes.append(c)
        k += 1
    d["nodes"], d["connections"] = nodes, []
    brief, ns, conns = load_brief(d)
    return build_timeline(brief, ns, conns)[0]


@pytest.fixture(scope="module")
def page_file(tmp_path_factory):
    f = tmp_path_factory.mktemp("cardt") / "t.html"
    f.write_text(_page(), encoding="utf-8")
    return f


@pytest.fixture(params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


_IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"


def _open(browser, f, **kw):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, user_agent=_IPHONE, **kw)
    pg = ctx.new_page()
    pg.goto(f.as_uri())
    pg.wait_for_timeout(900)
    assert pg.evaluate("document.documentElement.classList.contains('mobile')")
    return pg


OURS = "document.getAnimations().filter(a=>{const t=a.effect.getTiming();return (t.duration===160||t.duration===80)&&t.easing==='ease-out'})"   # the page has its own CSS transitions
INFO = """()=>document.getAnimations().filter(a=>{const t=a.effect.getTiming();return (t.duration===160||t.duration===80)&&t.easing==='ease-out'}).map(a=>({d:a.effect.getTiming().duration, e:a.effect.getTiming().easing,
  p:[...new Set(a.effect.getKeyframes().flatMap(k=>Object.keys(k)).filter(k=>!['offset','easing','composite','computedOffset'].includes(k)))].sort(),
  k:a.effect.getKeyframes().map(k=>k.translate||null)}))"""


def test_the_new_card_slides_in_from_the_side_it_travels_toward(browser, page_file):
    pg = _open(browser, page_file)
    pg.evaluate("featureNode(NODE_ORDER[3])")
    pg.wait_for_timeout(400)
    pg.evaluate("featureNode(NODE_ORDER[4])")
    a = pg.evaluate(INFO)
    new = [x for x in a if x["p"] == ["translate"] and x["k"][0] != "0px" and x["k"][-1] == "0px" and "-11" not in x["k"][0]]
    old = [x for x in a if x["p"] == ["translate"] and x["k"][0] == "0px" and x["k"][-1] in ("-390px", "390px")]
    assert len(new) == 1 and len(old) == 1, a
    assert new[0]["d"] == 160 and new[0]["e"] == "ease-out" and old[0]["d"] == 160, a
    assert new[0]["k"][0] == "390px" and old[0]["k"][-1] == "-390px", a      # next: in from the right, the old card out to the left
    assert pg.evaluate("document.querySelectorAll('.node.ct-ghost').length") == 1
    assert pg.evaluate("document.querySelectorAll('.node.mobile-featured:not(.ct-ghost)').length") == 1
    pg.wait_for_timeout(300)
    assert pg.evaluate("%s.length" % OURS) == 0 and pg.evaluate("document.querySelectorAll('.ct-ghost').length") == 0
    pg.evaluate("featureNode(NODE_ORDER[3])")                             # previous: in from the left
    assert [x for x in pg.evaluate(INFO) if x["p"] == ["translate"] and x["k"][-1] == "0px" and x["k"][0] == "-390px"][0]["k"][0] == "-390px"
    pg.wait_for_timeout(300)
    pg.evaluate("window._ctAxis='y'; featureNode(NODE_ORDER[4])")        # a vertical move comes from below
    assert any(x["k"][0] == "0px 844px" for x in pg.evaluate(INFO))
    pg.context.close()


def test_no_motion_for_the_first_card_the_same_card_or_reduced_motion(browser, page_file):
    pg = _open(browser, page_file)
    pg.evaluate("window._featuredNodeId = null; featureNode(NODE_ORDER[2])")
    assert pg.evaluate("%s.length" % OURS) == 0            # nothing to travel from (the page itself opens on a card, so clear it first)
    pg.evaluate("featureNode(NODE_ORDER[2])")
    assert pg.evaluate("%s.length" % OURS) == 0
    pg.evaluate("featureNode(NODE_ORDER[3], false)")
    assert pg.evaluate("%s.length" % OURS) == 0
    pg.context.close()
    pg = _open(browser, page_file, reduced_motion="reduce")
    pg.evaluate("featureNode(NODE_ORDER[2]); featureNode(NODE_ORDER[3])")
    assert pg.evaluate("%s.length" % OURS) == 0 and pg.evaluate("document.querySelectorAll('.ct-ghost').length") == 0
    assert pg.evaluate("window._featuredNodeId") == pg.evaluate("NODE_ORDER[3]")
    pg.context.close()


def test_a_run_of_quick_taps_never_queues_and_lands_on_the_latest_card(browser, page_file):
    pg = _open(browser, page_file)
    pg.evaluate("featureNode(NODE_ORDER[0])")
    r = pg.evaluate("""()=>{let max=0,gh=0;for(let i=1;i<9;i++){featureNode(NODE_ORDER[i]);max=Math.max(max,document.getAnimations().filter(a=>{const t=a.effect.getTiming();return (t.duration===160||t.duration===80)&&t.easing==='ease-out'}).length);
      gh=Math.max(gh,document.querySelectorAll('.ct-ghost').length)} return {max,gh,id:window._featuredNodeId,last:NODE_ORDER[8],
      feat:document.querySelectorAll('.node.mobile-featured:not(.ct-ghost)').length}}""")
    assert r["max"] <= 3 and r["gh"] <= 1, r                              # new card, old card, and the one unit label at most
    assert r["id"] == r["last"] and r["feat"] == 1, r
    pg.wait_for_timeout(300)
    assert pg.evaluate("%s.length" % OURS) == 0 and pg.evaluate("document.querySelectorAll('.ct-ghost').length") == 0
    pg.context.close()


def test_the_ghost_is_inert_and_carries_no_ids(browser, page_file):
    pg = _open(browser, page_file)
    pg.evaluate("featureNode(NODE_ORDER[3]); featureNode(NODE_ORDER[4])")
    r = pg.evaluate("""()=>{const g=document.querySelector('.ct-ghost');return {ids:g.querySelectorAll('[id]').length+(g.id?1:0),pe:g.style.pointerEvents,aria:g.getAttribute('aria-hidden'),
      dup:document.querySelectorAll('[id]').length-new Set([...document.querySelectorAll('[id]')].map(e=>e.id)).size}}""")
    assert r == {"ids": 0, "pe": "none", "aria": "true", "dup": 0}, r
    pg.context.close()


def test_the_unit_label_above_the_card_does_not_jump_or_double(browser, page_file):
    """Art (alto-art-1101-6100-a): cards differ in height, so the unit label above each re-centred instantly and showed doubled mid-fade. Within one unit a
    single copy stays and glides to the new card's height; across units each label simply goes with its card."""
    pg = _open(browser, page_file)
    pg.wait_for_timeout(600)
    pg.evaluate("featureNode(NODE_ORDER[3])")
    pg.wait_for_timeout(500)
    pg.evaluate("featureNode(NODE_ORDER[4])")                              # same unit (Consideration)
    r = pg.evaluate("""()=>({ct:document.querySelectorAll('.ct-unit').length,
      vis:[...document.querySelectorAll('.node.mobile-featured .node-unit')].filter(u=>u.style.visibility!=='hidden').length})""")
    assert r["ct"] == 1, r
    assert r["vis"] == 0, r                                               # the real labels are hidden while the one copy glides
    pg.wait_for_timeout(300)
    r = pg.evaluate("""()=>({ct:document.querySelectorAll('.ct-unit').length,
      hid:[...document.querySelectorAll('.node-unit')].filter(u=>u.style.visibility==='hidden').length,
      stray:document.querySelectorAll('.ct-unit,.ct-ghost').length})""")
    assert r == {"ct": 0, "hid": 0, "stray": 0}, r
    pg.evaluate("featureNode(NODE_ORDER[1])")                              # across units: no separate label
    assert pg.evaluate("document.querySelectorAll('.ct-unit').length") == 0
    pg.wait_for_timeout(300)
    pg.evaluate("featureNode(NODE_ORDER[3]); featureNode(NODE_ORDER[4]); featureNode(NODE_ORDER[5])")   # interrupted: nothing left hidden
    pg.wait_for_timeout(350)
    assert pg.evaluate("[...document.querySelectorAll('.node-unit')].filter(u=>u.style.visibility==='hidden').length+document.querySelectorAll('.ct-unit,.ct-ghost').length") == 0
    pg.context.close()


# ── text never sits on text (Board Art, 13 Nov), WebKit phone, all three styles ────────────────────────────────────────────────────────────────────────────
import asyncio  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))

SAMPLE = """async (pcts) => {
  const next = NODE_ORDER[NODE_ORDER.indexOf(window._featuredNodeId) + 1];
  window.featureNode(next, true);
  const rects = el => { const out = [], w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) { const n = w.currentNode; if (!n.textContent.trim() || !n.parentElement || n.parentElement.closest('.node-unit,.ct-unit')) continue;
      const r = document.createRange(); r.selectNodeContents(n); for (const q of r.getClientRects()) if (q.width > 1 && q.height > 1) out.push([q.left, q.top, q.right, q.bottom]); }
    return out; };
  const ours = document.getAnimations().filter(a => { const t = a.effect.getTiming(); return t.duration === 160; });
  const res = [];
  for (const p of pcts) {
    ours.forEach(a => { a.pause(); a.currentTime = 160 * p; });
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    const g = document.querySelector('.ct-ghost'), f = document.querySelector('.node.mobile-featured:not(.ct-ghost)');
    const A = g ? rects(g) : [], B = f ? rects(f) : [];
    let hit = 0; for (const a of A) for (const b of B) if (Math.min(a[2], b[2]) - Math.max(a[0], b[0]) > 0.5 && Math.min(a[3], b[3]) - Math.max(a[1], b[1]) > 0.5) hit++;
    const af = document.getElementById('af-btn'), ab = af && af.getBoundingClientRect(), lab = [...document.querySelectorAll('.ct-unit,.node-unit')].filter(u => u.getClientRects().length && getComputedStyle(u).visibility !== 'hidden' || u.classList.contains('ct-unit'));
    const over = !!(ab && +getComputedStyle(af).opacity > 0.05 && lab.some(u => { const q = u.getBoundingClientRect(); return Math.min(ab.right, q.right) - Math.max(ab.left, q.left) > 1 && Math.min(ab.bottom, q.bottom) - Math.max(ab.top, q.top) > 1; }));
    res.push({p, ghost: A.length, card: B.length, hit, over});
  }
  return {n: ours.length, res};
}"""


@pytest.fixture(scope="module")
def site():
    try:
        import phone_matrix as pm
        pm._playwright()
    except ImportError:
        pytest.skip("Playwright is not installed")
    from alto.build import palace_assets
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
    html = build_timeline(*load_brief(d))[0]
    man = {f: "/%s/%s" % (f, n) for f, n, _t in palace_assets.assets() if f in ("retro", "holo")}
    i, j = html.rfind("</body>"), html.find('<script id="alto-shell-js">')
    html = html[:i] + pm.LOADER % json.dumps(man) + html[i:]
    html = html[:j] + pm.SEED + html[j:] if j >= 0 else html
    s = pm.serve({"timeline": html}, {}, {})
    yield pm, f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


@pytest.mark.parametrize("style,theme", [("classic", "light"), ("retro", "light"), ("holo", "dark")])
def test_mid_slide_the_two_cards_text_boxes_never_intersect(site, style, theme):
    pm, base = site

    async def run():
        async with pm._playwright().async_playwright() as p:
            b = await p.webkit.launch()
            ctx = await b.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, user_agent=pm.UA)
            await ctx.add_init_script("try{localStorage.setItem('alto-theme-v1',%r)}catch(e){}" % theme)
            pg = await ctx.new_page()
            await pg.goto(f"{base}/timeline.html?view=card" + ("" if style == "classic" else f"&style={style}"), wait_until="load", timeout=45000)
            await pg.wait_for_timeout(2600 if style != "classic" else 1200)
            r = await pg.evaluate(SAMPLE, [0, .25, .5, .75, 1])
            await b.close()
            return r
    try:
        r = asyncio.run(run())
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise
    assert r["n"] >= 2, r
    for x in r["res"]:
        assert x["card"] > 0, r
        if x["p"] < 1:
            assert x["ghost"] > 0, r                       # the old card is still there to be checked against
        assert x["hit"] == 0, r
        assert not x["over"], r                           # the enlarge icon is never over the gliding unit label
