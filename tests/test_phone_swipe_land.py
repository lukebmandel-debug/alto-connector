"""Swiping between detail pages on a phone: the page that slides in is the page that stays (sim1111h A0; Luke 2026-11-11: "pay special attention to swiping between
detail pages in mobile to make sure its smooth when the next one lands", "by smooth i mean the text shouldn't jump and the background shouldn't jump").

Before: the page under the finger was a hand-built Classic preview (`.det-peek`) that Retro, Holo and a phone on its side never restyled; the real page was swapped in 240 ms after
the finger lifted, 20 ms after the 0.22 s slide stopped, and the header's names, the "Back to" pill and the unit tint snapped with it. Now the preview is a copy of the real page
as the real renderer draws it, the real page takes its place the moment the finger lifts (so the slide moves the page that stays), and the tint cross-fades inside the slide.

Each cell drives a real finger swipe (touch events a frame apart) in WebKit, samples every frame from the lift to 500 ms after the page lands, and asserts:
  * the title's and the first body line's boxes do not move once the page has landed (1 px of anti-alias noise);
  * what is painted behind them does not change once it has landed (the paint stack's computed styles each frame, and the pixels of two screenshots: landed, and 500 ms on);
  * no frame, from the lift on, shows the page in another style than the one it ends in (font, case, colour, layout, section skin);
  * the header's names, the pill and the tint are final by the landing.
Headless, offline, silent: no cloud env, no account, nothing played. The real iPhone rows stay with Testing (ORG/sim-main)."""
import asyncio
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))


def _pw():
    import phone_matrix as pm
    try:
        pm._playwright()
    except ImportError:
        pytest.skip("Playwright is not installed")
    return pm


@pytest.fixture(scope="module")
def site():
    pm = _pw()
    from alto.build.builder import build_timeline, load_brief
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


# one frame's record of the page that is coming in (found by its title, wherever it is drawn: the preview, or the real page)
SAMPLER = r"""(target) => { const S = window.__S = {frames:[], on:true, target:target};
 const R = r => r ? [r.left, r.top, r.width, r.height].map(v => Math.round(v*10)/10) : null;
 const tr = e => { if(!e) return null; const g = document.createRange(); g.selectNodeContents(e); const q = g.getClientRects(); return q.length ? q : null; };
 const cs = (e, ks) => { if(!e) return null; const c = getComputedStyle(e); return ks.map(k => c[k]).join('|'); };
 const norm = s => (s||'').replace(/\s+/g,' ').trim().toLowerCase();
 function paint(x, y){ return document.elementsFromPoint(x, y).slice(0, 14).map(e => { const c = getComputedStyle(e), b = getComputedStyle(e, '::before');
   return [e.tagName + (e.id ? '#' + e.id : ''), c.backgroundColor, c.backgroundImage.slice(0, 90), c.opacity, c.boxShadow.slice(0, 60), b.content !== 'none' ? b.backgroundColor + b.backgroundImage.slice(0, 60) : ''].join('~'); }).join(' > '); }
 function frame(){ if(!S.on) return; const f = {t: performance.now()};
   const names = [...document.querySelectorAll('.detail-name')].filter(n => norm(n.textContent) === S.target && n.getClientRects().length);
   f.n = names.length; const nm = names[names.length - 1];
   if(nm){ const pg = nm.closest('#detail-page,.det-peek'), pr = pg.getBoundingClientRect(), q = tr(nm), u = q && q[0];
     let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for(const r of (q||[])){ x0 = Math.min(x0, r.left); y0 = Math.min(y0, r.top); x1 = Math.max(x1, r.right); y1 = Math.max(y1, r.bottom); }
     const sec = pg.querySelector('.detail-section'), p = sec && (sec.querySelector('p,.ol-row,li') || sec), lq = tr(p), l0 = lq && [...lq].find(r => r.width > 20), hd = pg.querySelector('.detail-header');
     f.host = pg.classList.contains('det-peek') ? 'peek' : 'page'; f.px = Math.round(pr.left*10)/10; f.ptop = Math.round(pr.top*10)/10; f.pw = Math.round(pr.width*10)/10;
     f.title = q ? [x0, y0, x1 - x0, y1 - y0].map(v => Math.round(v*10)/10) : null; f.line = R(l0);
     f.style = [cs(nm, ['fontSize','fontWeight','fontFamily','color','textTransform','letterSpacing','textAlign','lineHeight']), cs(p, ['fontSize','color','lineHeight','fontFamily']),
       cs(sec, ['backgroundColor','borderLeftWidth','borderLeftColor','borderTopWidth','boxShadow','paddingLeft','paddingTop','borderRadius']), cs(hd, ['flexDirection','alignItems','textAlign','borderBottomWidth']),
       cs(pg, ['backgroundColor','backgroundImage','paddingLeft','paddingTop','paddingRight']), cs(pg.querySelector('.detail-symbol'), ['width','height','fontSize','color']), cs(pg.querySelector('#detail-content'), ['maxWidth','paddingLeft','columnCount','display'])].join(' || ');
     if(f.title && f.line){ f.bg = paint(f.title[0] + 3, f.title[1] + 3) + ' ## ' + paint(f.line[0] + 3, f.line[1] + 3); } }
   const de = document.documentElement, nav = document.getElementById('nav'), bp = document.getElementById('alto-back-prev');
   f.head = [(document.getElementById('tlb-prev')||{}).textContent, (document.getElementById('tlb-next')||{}).textContent, (document.getElementById('nav-label')||{}).textContent,
     bp && !bp.hasAttribute('hidden') ? norm(bp.textContent) : '-'].join(' | ');
   const dp = document.getElementById('detail-page'); f.tr = dp ? dp.style.transition : '';
   f.tint = de.style.getPropertyValue('--header-tint') + ' / ' + (nav ? getComputedStyle(nav).backgroundColor : '');
   S.frames.push(f); requestAnimationFrame(frame); }
 requestAnimationFrame(frame); }"""

# a finger: down, across by `dx` over `n` frames, up; resolves with the time it lifted
SWIPE = r"""async ([x, y, dx, n]) => { const raf = () => new Promise(r => requestAnimationFrame(r));
 const tg = document.elementFromPoint(x, y);
 const ev = (type, cx) => { const a = {identifier:1, target:tg, clientX:cx, clientY:y, pageX:cx, pageY:y, screenX:cx, screenY:y};
   const e = new Event(type, {bubbles:true, cancelable:true}); Object.defineProperty(e, 'touches', {value: type === 'touchend' ? [] : [a]});
   Object.defineProperty(e, 'targetTouches', {value: type === 'touchend' ? [] : [a]}); Object.defineProperty(e, 'changedTouches', {value:[a]}); tg.dispatchEvent(e); };
 ev('touchstart', x); await raf();
 for(let i = 1; i <= n; i++){ ev('touchmove', x + dx * i / n); await raf(); }
 window.__S && (window.__S.lift = performance.now()); ev('touchend', x + dx); return performance.now(); }"""

LANDED = r"""() => new Promise(done => { const S = window.__S; let still = 0, last = null; (function w(){ const f = S.frames[S.frames.length - 1];
   if(f && f.px != null && f.host === 'page' && last != null && Math.abs(f.px - last) < .05 && !document.querySelector('.det-peek')) still++; else still = 0; last = f ? f.px : null;
   if(still >= 2 || performance.now() - S.lift > 1500) return done(performance.now()); requestAnimationFrame(w); })(); })"""

CELLS = [(st, th, w, h) for (w, h) in ((402, 874), (874, 292)) for st, th in (("classic", "light"), ("retro", "light"), ("holo", "light"), ("holo", "dark"))]


async def _swipe(site, style, theme, w, h, dx=None, shots=True, start=None, quick=False):
    pm, base = site
    out = {}
    async with pm._playwright().async_playwright() as p:
        b = await p.webkit.launch()
        ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True, user_agent=pm.UA)
        await ctx.add_init_script("try{localStorage.setItem('alto-theme-v1',%r)}catch(e){}" % theme)
        pg = await ctx.new_page()
        await pg.goto(f"{base}/timeline.html?view=card" + ("" if style == "classic" else f"&style={style}"), wait_until="load", timeout=45000)
        await pg.wait_for_timeout(2600 if style != "classic" else 1200)
        await pg.evaluate("t=>{ const de=document.documentElement; if(de.classList.contains('dark')!==(t==='dark') && typeof toggleMode==='function') toggleMode(); de.classList.toggle('dark', t==='dark'); }", theme)
        out["cls"] = await pg.evaluate("document.documentElement.className")
        # the page whose neighbour has the longest name: the title that wraps when the style sets it in capitals
        i = await pg.evaluate("(s)=>{ let bi=1,bl=-1; if(s==='unit') bi=NODE_ORDER.indexOf(ACT_SEQS[0][ACT_SEQS[0].length-1]); else if(s!=null) bi=s; else for(let k=0;k<NODE_ORDER.length-1;k++){ const n=NODES.find(x=>x.id===NODE_ORDER[k+1]); if(n&&n.title.length>bl){ bl=n.title.length; bi=k; } }"
                              " showDetail('node', NODE_ORDER[bi]); return bi; }", start)
        await pg.wait_for_timeout(900)
        dxv = dx if dx is not None else -round(w * .45)
        target = await pg.evaluate("([i,d])=>{ const n=NODES.find(x=>x.id===NODE_ORDER[i+(d<0?1:-1)]); return n.title.replace(/\\s+/g,' ').trim().toLowerCase(); }", [i, dxv])
        out["target"] = target
        out["before"] = await pg.evaluate("[window._currentDetailId, (document.getElementById('tlb-next')||{}).textContent, location.hash, history.length]")
        await pg.evaluate(SAMPLER, target)
        y = round(h * .55)
        await pg.evaluate(SWIPE, [round(w * .62) if dxv < 0 else round(w * .38), y, dxv, 3 if quick else 9])
        if shots:
            await pg.evaluate(LANDED)
            s1 = await pg.screenshot()
            await pg.wait_for_timeout(520)
            s2 = await pg.screenshot()
            out["shots"] = (s1, s2)
        else:
            await pg.wait_for_timeout(900)
        out["S"] = await pg.evaluate("(()=>{ const S=window.__S; S.on=false; return {lift:S.lift, frames:S.frames}; })()")
        out["after"] = await pg.evaluate("[window._currentDetailId, (document.getElementById('tlb-next')||{}).textContent, location.hash, history.length, document.querySelectorAll('#detail-page').length, document.querySelectorAll('.det-peek').length,"
                                         " document.getElementById('detail-page').style.transform, NODE_ORDER.indexOf(window._currentDetailId)]")
        out["i"] = i
        await ctx.close()
        await b.close()
    return out


def _run(coro):
    try:
        return asyncio.run(coro)
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip(f"no WebKit: {e}")
        raise


def _tail_ms(tr, dist, last):
    """`transform 0.22s <curve>` over `dist` px: the ms the curve spends inside the last `last` px."""
    import re
    dur = float(re.search(r"([\d.]+)s", tr).group(1)) * 1000
    q = re.search(r"cubic-bezier\(([^)]+)\)", tr)
    x1, y1, x2, y2 = [float(v) for v in q.group(1).split(",")] if q else {"ease": (.25, .1, .25, 1), "ease-out": (0, 0, .58, 1), "ease-in-out": (.42, 0, .58, 1), "linear": (0, 0, 1, 1)}[tr.split()[-1]]
    bz = lambda u, a, b: 3 * (1 - u) ** 2 * u * a + 3 * (1 - u) * u * u * b + u ** 3
    want, lo, hi = 1 - last / dist, 0.0, 1.0
    for _ in range(50):                      # y is monotone in u for these curves
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if bz(mid, y1, y2) < want else (lo, mid)
    return round(dur * (1 - bz(lo, x1, x2)), 1)


def measure(o):
    """-> the numbers the asserts (and the report) use, from one swipe's frames."""
    fr = [f for f in o["S"]["frames"] if f["t"] >= o["S"]["lift"]]
    seen = [f for f in fr if f.get("title") and f.get("line")]
    assert len(seen) >= 12, f"the incoming page was drawn in only {len(seen)} of {len(fr)} frames after the lift"
    fin = seen[-1]
    every = [f for f in o["S"]["frames"] if f.get("title") and f.get("line")]      # the drag too: the preview under the finger is already the page
    landed = next(k for k, f in enumerate(seen) if all(abs(g["px"] - fin["px"]) < .6 for g in seen[k:]))
    post = seen[landed:]
    held = [f for f in every if f["t"] < o["S"]["lift"]] + post
    dev = lambda a, b: max(abs(x - y) for x, y in zip(a, b))
    m = {"frames": len(seen), "land_ms": round(seen[landed]["t"] - o["S"]["lift"]), "span_ms": round(seen[-1]["t"] - seen[landed]["t"]),
         "title_post": max(dev(f["title"], fin["title"]) for f in post), "line_post": max(dev(f["line"], fin["line"]) for f in post),
         "bg_post": sum(1 for f in post if f["bg"] != fin["bg"]), "style_bad": sum(1 for f in every if f["style"] != fin["style"]),
         "head_post": sum(1 for f in post if f["head"] != fin["head"]), "tint_post": sum(1 for f in post if f["tint"] != fin["tint"]),
         # the page's own layout, the slide taken out: the title and first line against the page's left edge, every frame from the lift
         # (x against the page's left edge is compared where the page is not in flight, under the finger and once landed: while the 0.22 s slide runs the page's box and the
         #  text's box are read a moment apart, and at 4 px a millisecond they disagree by a few px; y, width and height are compared on every frame)
         "title_rel": max(dev(f["title"][1:], fin["title"][1:]) for f in every), "title_relx": max(abs((f["title"][0] - f["px"]) - (fin["title"][0] - fin["px"])) for f in held),
         "line_rel": max(dev(f["line"][1:], fin["line"][1:]) for f in every), "line_relx": max(abs((f["line"][0] - f["px"]) - (fin["line"][0] - fin["px"])) for f in held),
         "late_ms": max([round(f["t"] - seen[landed]["t"]) for f in post if f["style"] != fin["style"] or f["head"] != fin["head"] or f["tint"] != fin["tint"] or f["bg"] != fin["bg"]
                         or dev(f["title"], fin["title"]) > 1 or dev(f["line"], fin["line"]) > 1] or [0]),
         "fin": fin}
    # (sim1112b S3) the approach: how the page comes to rest. A frame within 6 px of its place that is not yet there is the page creeping in; the slide's last
    # moving frame should be followed by the final position itself
    off = [abs(f["px"] - fin["px"]) for f in seen]
    exact = next(k for k in range(len(seen)) if all(v < .05 for v in off[k:]))
    far = max([k for k in range(exact) if off[k] > 6] or [0])
    m.update({"creep": [round(v, 1) for v in off[:exact] if v <= 6], "settle_ms": round(seen[exact]["t"] - seen[far]["t"]), "exact_ms": round(seen[exact]["t"] - o["S"]["lift"]),
              "px_post": max(off[exact:])})
    # ... and from the slide's own curve, which no frame timing blurs: how long the transition spends inside the last 6 px of this slide
    tr = next((f["tr"] for f in fr if f.get("tr") and "transform" in f["tr"]), "")
    m["curve"], m["tail_ms"] = tr, _tail_ms(tr, max(off), 6) if tr else None
    if o.get("shots"):
        from PIL import Image, ImageChops
        a, b = (Image.open(io.BytesIO(s)).convert("RGB") for s in o["shots"])
        worst, boxes = 0, 0
        for x, y, w_, h_ in (fin["title"], fin["line"]):          # (a phone on its side: the first body line can be under the fold; then only the title's pixels are compared)
            crop = (max(0, int(x) - 12), max(0, int(y) - 12), min(a.size[0], int(x + w_) + 12), min(a.size[1], int(y + h_) + 12))
            if crop[2] - crop[0] < 8 or crop[3] - crop[1] < 8:
                continue
            boxes += 1
            worst = max(worst, max(hi for _lo, hi in ImageChops.difference(a.crop(crop), b.crop(crop)).getextrema()))
        m["pixel_post"], m["pixel_boxes"] = worst, boxes
    return m


@pytest.fixture(scope="module")
def swipes(site):
    return {}


def _cell(site, swipes, key):
    if key not in swipes:
        o = _run(_swipe(site, *key))
        swipes[key] = (o, measure(o))
    return swipes[key]


@pytest.mark.parametrize("style, theme, w, h", CELLS)
def test_the_page_that_slides_in_is_the_page_that_stays(site, swipes, style, theme, w, h):
    o, m = _cell(site, swipes, (style, theme, w, h))
    if style != "classic":
        assert f"alto-{style}" in o["cls"], o["cls"]
    if style == "classic":          # (Retro and Holographic are dark only: 2026-11-13 for Holo on a phone)
        assert ("dark" in o["cls"].split()) == (theme == "dark"), o["cls"]
    else:
        assert "dark" in o["cls"].split(), o["cls"]
    assert o["after"][7] == o["i"] + 1, "the swipe went to the next page"
    tag = f"{style} {theme} {w}x{h}: {{}} (landed {m['land_ms']} ms after the lift, {m['frames']} frames)"
    assert m["title_post"] <= 1, tag.format(f"the title moved {m['title_post']} px after landing")
    assert m["line_post"] <= 1, tag.format(f"the first body line moved {m['line_post']} px after landing")
    assert m["bg_post"] == 0, tag.format(f"what is painted behind the text changed in {m['bg_post']} frames after landing")
    assert m["pixel_boxes"] >= 1 and m["pixel_post"] <= 2, tag.format(f"the pixels behind the text changed by {m['pixel_post']} levels between landing and 500 ms on")
    assert m["style_bad"] == 0, tag.format(f"{m['style_bad']} frames drew the page in another style than the one it ends in")
    assert m["title_rel"] <= 1 and m["line_rel"] <= 1 and m["title_relx"] <= 1 and m["line_relx"] <= 1, tag.format(
        f"the page's layout changed under the slide: title {m['title_rel']} / {m['title_relx']} px, first line {m['line_rel']} / {m['line_relx']} px")
    assert m["head_post"] == 0, tag.format("the header's names or the pill changed after landing")
    assert m["tint_post"] == 0, tag.format("the header's tint changed after landing")
    assert m["span_ms"] >= 480, "sampled to 500 ms after landing"
    assert o["after"][4] == 1 and o["after"][5] == 0 and o["after"][6] in ("", "none"), f"one detail page left, no preview, no transform: {o['after'][4:7]}"


@pytest.mark.parametrize("style, theme, w, h", CELLS)
def test_the_slide_ends_on_the_final_position_with_no_trailing_ease(site, swipes, style, theme, w, h):
    """sim1112b S3 (Retro upright on the iPhone: "the last 1 pt eases in over ~200 ms (5, 3, 1, 0 px)"; Luke's bar is "even 1-2 px"). The slide was `ease`, which comes
    to rest asymptotically: its last 6 px took 40 ms and more (frames at 3.7, 0.9, 0). Now it arrives still moving (the last 6 px inside one frame), and where it
    stops is the final position, exactly, for good."""
    o, m = _cell(site, swipes, (style, theme, w, h))
    tag = f"{style} {theme} {w}x{h}: {{}} (on its place {m['exact_ms']} ms after the lift)"
    print("S3", style, theme, f"{w}x{h}", m["curve"], "-> last 6 px in", m["tail_ms"], "ms; frames caught inside them:", m["creep"], "; after its place:", m["px_post"], "px")
    assert m["tail_ms"] is not None and m["tail_ms"] <= 17, tag.format(f"the slide's curve ({m['curve']}) spends {m['tail_ms']} ms in its last 6 px: more than a frame, a trailing ease")
    assert len(m["creep"]) <= 2 and m["settle_ms"] <= 55, tag.format(f"the page crept in: frames inside the last 6 px at {m['creep']} px, {m['settle_ms']} ms from the last frame further out to its place")
    assert m["px_post"] == 0, tag.format(f"the page moved {m['px_post']} px after it reached its place")
    assert m["title_post"] <= .5 and m["line_post"] <= .5, tag.format(f"the text moved after landing: title {m['title_post']} px, first line {m['line_post']} px")


def test_a_swipe_that_is_let_go_early_changes_nothing(site):
    """The preview is the real page drawn quietly: a drag that springs back leaves the page, the header, the address and the browser's history as they were."""
    # The engine turns the page on a lift past 30% of the width OR a flick faster than 0.4 px/ms. 60 px over the helper's 9 moves (10 frames, ~150-167 ms) was
    # 0.36-0.40 px/ms, on the flick line: one early frame (147 ms, 0.408) made it a flick and the page rightly turned. 40 px is ~0.25 px/ms, a clear let-go.
    o = _run(_swipe(site, "classic", "light", 402, 874, dx=-40, shots=False))
    assert o["after"][0] == o["before"][0] and o["after"][1] == o["before"][1] and o["after"][2] == o["before"][2] and o["after"][3] == o["before"][3], (o["before"], o["after"])
    assert o["after"][4] == 1 and o["after"][5] == 0 and o["after"][6] in ("", "none")
    fr = [f for f in o["S"]["frames"] if f.get("title")]
    assert fr and all(f["host"] == "peek" for f in fr), "the next page showed only as the preview"
    assert len({f["head"] for f in o["S"]["frames"]}) == 1 and len({f["tint"] for f in o["S"]["frames"]}) == 1, "the header did not flicker while the preview was drawn"


def test_a_backward_swipe_lands_the_same_way(site):
    o = _run(_swipe(site, "holo", "light", 402, 874, dx=180, shots=False, start=3))
    m = measure(o)
    assert o["after"][7] == 2 and m["style_bad"] == 0 and m["title_post"] <= 1 and m["line_post"] <= 1 and m["bg_post"] == 0 and m["head_post"] == 0, {k: v for k, v in m.items() if k != "fin"}


def test_the_unit_tint_cross_fades_inside_the_slide(site):
    """Across a unit's edge the header's tint changes: it moves through in-between colours while the page slides and is the new unit's by the landing (it used to snap after it)."""
    o = _run(_swipe(site, "classic", "light", 402, 874, shots=False, start="unit"))
    m = measure(o)
    fr = [f for f in o["S"]["frames"] if f["t"] >= o["S"]["lift"] - 60]
    tints = []
    for f in fr:
        if not tints or tints[-1] != f["tint"]:
            tints.append(f["tint"])
    assert tints[0] != tints[-1], "the two pages are in units of different colours"
    assert len(tints) >= 5, f"the tint stepped through {len(tints)} values: a snap, not a fade"
    assert m["tint_post"] == 0 and m["head_post"] == 0 and m["title_post"] <= 1 and m["bg_post"] == 0, {k: v for k, v in m.items() if k != "fin"}


def test_a_second_swipe_straight_after_the_first_is_not_lost(site):
    """sim1111h: a second swipe within ~0.2 s of the first was ignored (its touch cancelled the first one's pending page change). The page changes at the lift now."""
    pm, base = site

    async def go():
        async with pm._playwright().async_playwright() as p:
            b = await p.webkit.launch()
            ctx = await b.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, user_agent=pm.UA)
            pg = await ctx.new_page()
            await pg.goto(f"{base}/timeline.html?view=card", wait_until="load", timeout=45000)
            await pg.wait_for_timeout(1200)
            await pg.evaluate("showDetail('node', NODE_ORDER[1])")
            await pg.wait_for_timeout(700)
            await pg.evaluate(SWIPE, [250, 480, -180, 3])
            await pg.wait_for_timeout(60)
            await pg.evaluate(SWIPE, [250, 480, -180, 3])
            await pg.wait_for_timeout(700)
            r = await pg.evaluate("[NODE_ORDER.indexOf(window._currentDetailId), document.querySelectorAll('#detail-page').length, document.querySelectorAll('.det-peek').length, document.getElementById('detail-page').style.transform]")
            await ctx.close()
            await b.close()
            return r
    r = _run(go())
    assert r == [3, 1, 0, ""], r


# ── the seam (Art look rel-223, 2026-11-12: "a ~16 px vertical strip of bare background shows between the outgoing page and the incoming one ... reads as a coloured band") ──
# The two pages were drawn a 16 px gutter apart (the template's _DET_GAP), and the gutter showed the ground with no frost on it: a flat band of another colour riding across the
# screen. The incoming page now butts against the outgoing page's edge: no gap on any frame, and no overlap (two frosts on top of each other would draw a band of their own).
# Each cell holds a finger mid-drag for a screenshot, then lifts it and samples both pages' boxes on every frame of the slide.
# (12 Nov: WebKit answers a sliding page's box at the moment it is asked, not at the frame's time, so two boxes read one after the other are two moments apart: when the shell's
# re-run landed in the same frame, the layout it forced between the two reads took about 1 ms and the pages, moving 1.5 px a ms, measured 1 to 4.5 px apart on one frame in about
# thirty swipes, on 9d10f730 too. Every frame is read twice, v then w: the gap lies between the two estimates, one read late on each side, see seam_measure)
SEAM_SAMPLER = r"""() => { const S = window.__G = {frames:[], on:true};
 const read = () => [...document.querySelectorAll('#detail-page,.det-peek')].map(e => { const r = e.getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; })
     .filter(r => r[1] > 0 && r[0] < innerWidth).sort((a, b) => a[0] - b[0]);
 (function frame(){ if(!S.on) return; const v = read(), w = read();
   S.frames.push({t: performance.now(), v: v, w: w}); requestAnimationFrame(frame); })(); }"""
# the finger goes down and across and stays down (the lift is SEAM_LIFT)
SEAM_DRAG = r"""async ([x, y, dx, n]) => { const raf = () => new Promise(r => requestAnimationFrame(r));
 const tg = document.elementFromPoint(x, y); window.__T = {tg:tg, y:y, x:x + dx};
 const ev = window.__T.ev = (type, cx) => { const a = {identifier:1, target:tg, clientX:cx, clientY:y, pageX:cx, pageY:y, screenX:cx, screenY:y};
   const e = new Event(type, {bubbles:true, cancelable:true}); Object.defineProperty(e, 'touches', {value: type === 'touchend' ? [] : [a]});
   Object.defineProperty(e, 'targetTouches', {value: type === 'touchend' ? [] : [a]}); Object.defineProperty(e, 'changedTouches', {value:[a]}); tg.dispatchEvent(e); };
 ev('touchstart', x); await raf();
 for(let i = 1; i <= n; i++){ ev('touchmove', x + dx * i / n); await raf(); }
 await raf(); const f = window.__G.frames; return f[f.length - 1].v; }"""
SEAM_LIFT = "() => { window.__G.lift = performance.now(); window.__T.ev('touchend', window.__T.x); }"


async def _seam(site, style, theme, w, h):
    pm, base = site
    async with pm._playwright().async_playwright() as p:
        b = await p.webkit.launch()
        ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True, user_agent=pm.UA)
        await ctx.add_init_script("try{localStorage.setItem('alto-theme-v1',%r)}catch(e){}" % theme)
        pg = await ctx.new_page()
        await pg.goto(f"{base}/timeline.html?view=card" + ("" if style == "classic" else f"&style={style}"), wait_until="load", timeout=45000)
        await pg.wait_for_timeout(2600 if style != "classic" else 1200)
        await pg.evaluate("t=>{ const de=document.documentElement; if(de.classList.contains('dark')!==(t==='dark') && typeof toggleMode==='function') toggleMode(); de.classList.toggle('dark', t==='dark'); }", theme)
        await pg.evaluate("showDetail('node', NODE_ORDER[1])")
        await pg.wait_for_timeout(900)
        out = {"cls": await pg.evaluate("document.documentElement.className"),
               "pad": await pg.evaluate("(()=>{ const c=getComputedStyle(document.getElementById('detail-page')); return Math.min(parseFloat(c.paddingLeft), parseFloat(c.paddingRight)); })()")}
        await pg.evaluate(SEAM_SAMPLER)
        out["held"] = await pg.evaluate(SEAM_DRAG, [round(w * .62), round(h * .55), -round(w * .45), 9])
        out["png"] = await pg.screenshot()
        await pg.evaluate(SEAM_LIFT)
        await pg.wait_for_timeout(700)
        out["G"] = await pg.evaluate("(()=>{ const S=window.__G; S.on=false; return {lift:S.lift, frames:S.frames}; })()")
        out["after"] = await pg.evaluate("[NODE_ORDER.indexOf(window._currentDetailId), document.querySelectorAll('#detail-page').length, document.querySelectorAll('.det-peek').length, document.getElementById('detail-page').style.transform]")
        await ctx.close()
        await b.close()
    return out


def seam_measure(o, w, h):
    """-> the seam's numbers: the gap between the two pages' boxes on every frame that shows both (+ a gap, - an overlap), and the mid-drag screenshot's pixels across the seam."""
    from PIL import Image
    both = [f for f in o["G"]["frames"] if len(f["v"]) >= 2 and len(f.get("w", f["v"])) >= 2]

    def gap(f):          # the two estimates of one frame's gap (each has one edge read later than the other, on opposite sides): the one nearer nothing. A real gutter or overlap is in both
        a, b = f["v"][1][0] - f["v"][0][1], f.get("w", f["v"])[1][0] - f.get("w", f["v"])[0][1]
        c, d = f.get("w", f["v"])[1][0] - f["v"][0][1], f["v"][1][0] - f.get("w", f["v"])[0][1]
        return min((a, b, c, d), key=abs)
    gaps = [gap(f) for f in both]
    slide = [gap(f) for f in both if f["t"] >= o["G"]["lift"]]
    assert len(o["held"]) == 2, f"two pages under the finger: {o['held']}"
    x = o["held"][0][1]                                    # the outgoing page's right edge, the finger held
    top, bot = max(o["held"][0][2], o["held"][1][2]), min(h, o["held"][0][3], o["held"][1][3])
    im = Image.open(io.BytesIO(o["png"])).convert("RGB")
    k = im.size[0] / w
    # the rows of the page that carry no chrome (under the header rows, above the corner tiles), and the pages' own side margins to each side of the seam (no text in them),
    # with whatever lies between the two pages
    y0, y1 = int(top + (bot - top) * .25), int(top + (bot - top) * .7)
    reach = int(min(o["pad"], 18)) - 6
    assert reach >= 6, f"the page has a side margin to sample: {o['pad']}"
    step = drift = 0
    for y in range(y0, y1, 3):
        row = [im.getpixel((int((x + d) * k), int(y * k))) for d in range(-reach, reach + 1 + max(0, round(o["held"][1][0] - x)))]
        step = max(step, max(max(abs(p - q) for p, q in zip(a, c)) for a, c in zip(row, row[1:])))
        drift = max(drift, max(max(abs(p - q) for p, q in zip(row[0], c)) for c in row))
    return {"frames": len(both), "slide_frames": len(slide), "gap_max": round(max(gaps), 2), "gap_min": round(min(gaps), 2), "slide_gap_max": round(max(slide), 2) if slide else None,
            "slide_gap_min": round(min(slide), 2) if slide else None, "held_gap": round(o["held"][1][0] - o["held"][0][1], 2), "seam_x": round(x, 1), "px_step": step, "px_drift": drift}


@pytest.mark.parametrize("style, theme, w, h", CELLS)
def test_no_gap_and_no_band_between_the_two_pages_mid_swipe(site, style, theme, w, h):
    o = _run(_seam(site, style, theme, w, h))
    if style != "classic":
        assert f"alto-{style}" in o["cls"], o["cls"]
    m = seam_measure(o, w, h)
    print("SEAM", style, theme, f"{w}x{h}", json.dumps(m))
    tag = f"{style} {theme} {w}x{h}: {{}} " + json.dumps(m).replace("{", "(").replace("}", ")")
    assert m["frames"] >= 12 and m["slide_frames"] >= 4, tag.format("both pages were sampled through the drag and the slide")
    assert abs(m["held_gap"]) <= .5, tag.format(f"under the finger the incoming page is {m['held_gap']} px from the outgoing page's edge")
    assert m["gap_max"] <= .5, tag.format(f"a {m['gap_max']} px strip of bare ground opened between the pages")
    assert m["gap_min"] >= -.5, tag.format(f"the pages overlapped by {-m['gap_min']} px (the frost drawn twice)")
    assert m["px_step"] <= SEAM_STEP and m["px_drift"] <= SEAM_DRIFT, tag.format(f"the seam's columns are a band: a step of {m['px_step']} levels between neighbours, {m['px_drift']} across it")
    assert o["after"][0] == 2 and o["after"][1:] == [1, 0, ""], f"and the swipe landed: {o['after']}"


# levels of colour: between neighbouring columns, and from one side of the seam to the other. The 16 px gutter measured 34 / 35 in Classic light upright and 31 / 31 on its side;
# butted, every cell is 0-2, but for Holo dark upright (4 / 15: the soft glow of the incoming page's section markers, which starts 15 px inside its edge).
SEAM_STEP, SEAM_DRIFT = 6, 16
