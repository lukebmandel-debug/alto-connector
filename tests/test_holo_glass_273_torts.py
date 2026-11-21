"""v1.9.273 round 3 (Board B-1120-LOOK273-R2): Luke's Torts top bar (a local fixture shaped like it: tests/torts_fixture.py): nine kind-glyph chips with counts, the ELEMENT and AUTHORITIES
labels, the square x and the title tab. On the released v1.9.254 those were square boxes and plain text; on 273 every one is the S1 glass pill. Holo only, headless WebKit, offline and silent."""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "tools", ROOT / "tests"):
    sys.path.insert(0, str(p))

JS = """() => { const info = (e) => { const c = getComputedStyle(e), r = e.getBoundingClientRect();
    return {t: (e.textContent || '').trim().slice(0, 24), glass: /gradient/.test(c.backgroundImage), blur: /blur/.test(c.backdropFilter || c.webkitBackdropFilter || ''), rad: c.borderRadius, w: r.width, h: r.height,
            hasSvg: !!e.querySelector('svg'), cls: e.className || e.id}; };
  const vis = (e) => { const r = e.getBoundingClientRect(), c = getComputedStyle(e); return r.width > 4 && r.height > 4 && c.display !== 'none' && c.visibility !== 'hidden'; };
  const all = (q) => [...document.querySelectorAll(q)].filter(vis).map(info);
  const kids = [...document.querySelectorAll('#nav .nav-btn, #nav .nav-group-label, #ct-chips, #title-text')].filter(vis).map(info);
  return {cls: document.documentElement.className, chips: all('#nav .nav-btn'), labels: all('#nav .nav-group-label'), x: all('#ct-chips'), title: all('#title-text'), kids}; }"""


def _page(style, vw=1440, vh=900, mob=False, js=None, long_names=False):
    import phone_matrix as pm
    import torts_fixture as tf
    try:
        pw = pm._playwright()
    except ImportError:
        pytest.skip("Playwright is not installed")
    s = pm.serve({"torts": tf.page(long_names=long_names)}, {}, {})

    async def go():
        async with pw.async_playwright() as p:
            b = await p.webkit.launch()
            ctx = await b.new_context(viewport={"width": vw, "height": vh}, is_mobile=mob, has_touch=mob, user_agent=pm.UA if mob else None, color_scheme="dark")
            pg = await ctx.new_page()
            await pg.goto(f"http://127.0.0.1:{s.server_address[1]}/torts.html?style={style}", wait_until="load", timeout=45000)
            await pg.wait_for_timeout(3500)
            r = await pg.evaluate(js or JS)
            await b.close()
            return r
    try:
        return asyncio.run(go())
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise
    finally:
        s.shutdown()


def test_torts_shaped_top_bar_is_s1_glass_in_holo():
    r = _page("holo")
    assert "ct-on" in r["cls"] and "alto-holo" in r["cls"], r["cls"]      # the clear-top state Luke's bar is in (it squares the labels and plates in Holo's base rules)
    assert len(r["chips"]) >= 10, len(r["chips"])                          # nine element chips + the Cases chip, each with a kind glyph
    assert sum(1 for c in r["chips"] if c["hasSvg"]) >= 9
    assert {l["t"].upper() for l in r["labels"]} >= {"ELEMENT", "AUTHORITIES"}
    for grp in ("chips", "labels", "x", "title"):
        assert r[grp], grp
        for c in r[grp]:
            assert c["glass"] and c["blur"], (grp, c, "not the S1 plate")
            assert c["rad"] not in ("0px", "") and not c["rad"].startswith("0px "), (grp, c, "square")
            if c["w"] > c["h"] * 1.4:
                assert c["rad"] != "50%", (grp, c, "a wide control is a circle")
    for c in r["kids"]:                                                     # the tab stub / anything else hanging in the bars: nothing in them is left a bare square box
        assert c["glass"] and c["blur"], ("a top-bar piece is not glass", c)


@pytest.mark.parametrize("style", ["classic", "retro"])
def test_torts_variant_other_styles_unchanged(style):
    r = _page(style)
    for grp in ("chips", "labels"):
        for c in r[grp]:
            assert not (c["glass"] and c["blur"] and c["rad"] == "999px"), (style, grp, c, "Holo glass leaked")


JS_NAMES = """() => { const out = {}; const px = (v) => parseFloat(v) || 0;
  for (const q of ['#timeline-label-bar', '#tlb-prev', '#tlb-next']) {
    const e = document.querySelector(q); if (!e) continue; const c = getComputedStyle(e), r = e.getBoundingClientRect();
    out[q] = {glass: /gradient/.test(c.backgroundImage), blur: /blur/.test(c.backdropFilter || c.webkitBackdropFilter || ''), rad: px(c.borderTopLeftRadius), w: r.width, h: r.height, l: r.left, r: r.right}; }
  // each name's group = chevron (8px box + 5px gap) + text; its centre against the centre of the half (upright) or of its own pill (on its side)
  const bar = out['#timeline-label-bar'], mid = bar ? (bar.l + bar.r) / 2 : 0;
  for (const side of ['prev', 'next']) {
    const lab = document.querySelector('#tlb-' + side); if (!lab) continue; const t = lab.querySelector('.nb-t') || lab.querySelector('.wrap-pill'); if (!t) continue;
    const tr = t.getBoundingClientRect(), L = side === 'prev' ? tr.left - 13 : tr.left, R = side === 'prev' ? tr.right : tr.right + 13;
    const cs = getComputedStyle(t); out[side + 'Group'] = {h: tr.height, lh: px(cs.lineHeight) || px(cs.fontSize) * 1.2, ws: cs.whiteSpace, l: L, r: R, tw: tr.width, scroll: t.scrollWidth, client: t.clientWidth, text: (t.textContent || '').trim().slice(0, 18)}; }
  out.mid = mid; return out; }"""


def _centred(r, upright):
    for side in ("prev", "next"):
        g = r[side + "Group"]
        if upright:
            lo, hi = (r["#timeline-label-bar"]["l"], r["mid"]) if side == "prev" else (r["mid"], r["#timeline-label-bar"]["r"])
        else:
            lo, hi = r["#tlb-" + side]["l"], r["#tlb-" + side]["r"]
        off = (g["l"] + g["r"]) / 2 - (lo + hi) / 2
        assert abs(off) <= 2, (side, "name is not centred", round(off, 2), g, lo, hi)
        assert g["l"] >= lo - 1 and g["r"] <= hi + 1, (side, "name spills out of its half", g, lo, hi)
    if upright:
        a, b = r["#tlb-prev"], r["#tlb-next"]
        assert abs(a["w"] - b["w"]) <= 2, ("the halves are unequal", a["w"], b["w"])


@pytest.mark.parametrize("long_names", [False, True])
@pytest.mark.parametrize("vw,vh", [(390, 844), (844, 390)])
def test_phone_prev_next_names_are_s1_glass_pills_and_centred(vw, vh, long_names):
    r = _page("holo", vw, vh, True, JS_NAMES, long_names)
    assert r["#tlb-prev"]["h"] >= 44 and r["#tlb-next"]["h"] >= 44, r        # the touch rows keep 44pt
    upright = vh > vw
    if upright:                                                               # ONE foot pill (S1), two equal halves
        bar = r["#timeline-label-bar"]
        assert bar["glass"] and bar["blur"] and bar["rad"] >= 22 and bar["h"] >= 44, bar
    else:                                                                     # on its side: each control is its own S1 pill
        for side in ("prev", "next"):
            v = r["#tlb-" + side]
            assert v["glass"] and v["blur"] and v["rad"] >= 22, (side, v)
    _centred(r, upright)
    if vh > vw:                                                               # round 6: one line each, the same height, never wrapped
        p_, n_ = r["prevGroup"], r["nextGroup"]
        assert p_["ws"] == "nowrap" and n_["ws"] == "nowrap", (p_, n_)
        assert p_["h"] <= p_["lh"] * 1.5 and n_["h"] <= n_["lh"] * 1.5 and abs(p_["h"] - n_["h"]) <= 1, ("a name is not one line", p_, n_)
    if long_names:                                                            # a long title is cut (ellipsis) and still centred
        assert any(r[s + "Group"]["scroll"] > r[s + "Group"]["client"] or r[s + "Group"]["tw"] < 250 for s in ("prev", "next")), r


@pytest.mark.parametrize("vw,vh", [(390, 844), (844, 390)])
def test_phone_prev_next_other_styles_unchanged(vw, vh):
    r = _page("classic", vw, vh, True, JS_NAMES)
    for k in ("#tlb-prev", "#tlb-next"):
        v = r[k]
        assert not (v["glass"] and v["blur"] and v["rad"] >= 22), (k, v)
