"""The Claude handoff fix pass (Board B-1118-HANDOFF1-ART): the update notice clear of the editing bar and the Add-a-section button, Holo glass
sheets (contrast measured), the Add-a-section popover 20px from every edge, no side tab beside a phone sheet. WebKit; shots: HANDOFF_AFTER=<dir>."""
import os
import sys
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import test_claude_handoff_browser_1118 as B  # noqa: E402

server = B.server
AFTER = os.environ.get("HANDOFF_AFTER", "")
STYLES = (("holo", "dark"), ("classic", "light"), ("retro", "dark"))
R = "e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }"


def _hit(a, b, gap=0):
    return a[0] < b[2] + gap and a[2] > b[0] - gap and a[1] < b[3] + gap and a[3] > b[1] - gap


def _note(pg):
    from alto.cloud import emit_cloud_js
    js = emit_cloud_js({})
    pg.evaluate("s => { window.__note = new Function(s + '; return _connectorNote;')(); }", js[js.index("const CONN_LATEST"):js.index("async function _connectorCheck")])
    pg.evaluate("window.__note('1.9.100')"); pg.wait_for_timeout(250)


def _edit(pg, phone):
    pg.evaluate("showDetail('node','definiteness')"); pg.wait_for_timeout(900)
    pill = ".alto-edit-pill.in-page .aep-manual" if phone else ".alto-edit-pill:not(.in-page) .aep-manual"
    if phone:
        pg.evaluate("() => { const t = document.querySelector('.alto-edit-pill.in-page'); if(t) t.scrollIntoView({block: 'center'}); }"); pg.wait_for_timeout(300)
    pg.locator(pill).first.click(); pg.wait_for_timeout(900)


@pytest.mark.parametrize("style,theme", STYLES)
@pytest.mark.parametrize("w,h", ((1440, 900), (390, 844)))
def test_the_update_notice_never_touches_the_editing_bar_or_add_a_section(server, style, theme, w, h):
    with pw.sync_playwright() as p:
        b = p.webkit.launch(); ctx, pg, errs = B._open(b, server, w, h, style, theme)
        _edit(pg, w < 700); _note(pg)
        for scroll in ("top", "bottom"):
            pg.evaluate("s => window.scrollTo(0, s === 'top' ? 0 : 1e6)", scroll)
            pg.evaluate("() => { const d = document.getElementById('detail-content'); if(d) d.scrollTop = 1e6; }" if scroll == "bottom" else "0"); pg.wait_for_timeout(250)
            note = pg.eval_on_selector("#alto-conn-note", R)
            bar = pg.eval_on_selector("#alto-edit-exit", R)
            assert not _hit(note, bar), (style, w, scroll, note, bar)
            for e in pg.query_selector_all("#detail-content .aed-add"):
                if e.is_visible():
                    assert not _hit(note, e.evaluate(R)), (style, w, scroll)
            assert note[0] >= 19.5 and note[2] <= w - 19.5 and note[3] <= h - 20 + .5, note
        if AFTER:
            pg.screenshot(path=f"{AFTER}/banner-{style}-{'p390' if w < 700 else 'd1440'}.png")
        assert not errs; ctx.close(); b.close()


def _lum(c):
    v = [x / 255 for x in c[:3]]; v = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in v]
    return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]


def _ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True); return (la + .05) / (lb + .05)


PAINT = """() => { const el = document.querySelector('#alto-handoff .ah-box'), cs = e => getComputedStyle(e), P = s => (s.match(/[\\d.]+/g) || []).map(Number);
  const bg = P(cs(el).backgroundColor), out = {bg, radius: cs(el).borderRadius, shadow: cs(el).boxShadow, pairs: []};
  for (const e of el.querySelectorAll('p,li,h2,label,.ah-b,textarea')) { const c = cs(e); let b = P(c.backgroundColor); if (b.length < 3 || (b[3] === 0)) b = bg;
    if (e.classList.contains('ah-b') && P(c.backgroundColor)[3] !== 0 && P(c.backgroundColor).length >= 3) b = P(c.backgroundColor);
    out.pairs.push([e.tagName + '.' + e.className, P(c.color), b, +c.opacity]); } return out; }"""


@pytest.mark.parametrize("w,h", ((1440, 900), (390, 844)))
def test_holo_sheets_wear_the_holo_glass_panel_with_readable_text(server, w, h):
    phone = w < 700
    with pw.sync_playwright() as p:
        b = p.webkit.launch(); ctx, pg, errs = B._open(b, server, w, h, "holo", "dark")
        _edit(pg, phone)
        if phone:
            pg.locator("#alto-edit-exit .ee-ask").click(); pg.wait_for_selector("#alto-handoff .ah-pick", timeout=5000)
        else:
            pg.wait_for_selector("#detail-content .aed-add", state="attached", timeout=8000)
            add = pg.locator("#detail-content .aed-add").first; add.scroll_into_view_if_needed(); add.click(); pg.wait_for_timeout(400)
            pg.locator("#aed-kinds .aed-askrow button").first.wait_for()
        pg.wait_for_timeout(300)
        if phone:                                                                              # chooser (phone) then the copied-prompt sheet
            ch = pg.evaluate(PAINT)
            assert ch["radius"] in ("0px", "0px 0px 0px 0px") and "rgb" in ch["shadow"] and (ch["bg"] + [1])[3] >= .9
            if AFTER: pg.screenshot(path=f"{AFTER}/holo-p390-chooser.png")
            pg.locator("#alto-handoff .ah-pick .ah-row", has_text="Add a quiz").click()
        else:
            pg.locator('#aed-kinds .aed-askrow button[data-ak="quiz"]').click()
        pg.wait_for_selector("#alto-handoff textarea", timeout=5000); pg.wait_for_timeout(350)
        s = pg.evaluate(PAINT)
        words = pg.evaluate("document.querySelector('#alto-handoff .ah-box').innerText")
        if phone: assert not any(k in words for k in ('⌘', 'Ctrl', 'key')), words
        else: assert '⌘V or Ctrl+V' in words
        assert (s['bg'] + [1])[3] == 1, s['bg']                                                          # solid: no page text reads through
        assert s["radius"] in ("0px", "0px 0px 0px 0px") and (s["bg"] + [1])[3] >= .9 and "rgb" in s["shadow"]       # square, rimmed glass, not the white card
        assert not (s["bg"][0] > 200 and s["bg"][1] > 200), s["bg"]
        for name, fg, bgc, op in s["pairs"]:
            assert op == 1 and _ratio(fg, bgc) >= 4.5, (name, fg, bgc, _ratio(fg, bgc))
        if AFTER: pg.screenshot(path=f"{AFTER}/holo-{'p390' if phone else 'd1440'}-copied-prompt.png")
        assert not errs; ctx.close(); b.close()


@pytest.mark.parametrize("style,theme", STYLES)
@pytest.mark.parametrize("w,h", ((1440, 900), (1000, 700)))
def test_the_add_a_section_popover_stays_20px_from_every_edge(server, style, theme, w, h):
    with pw.sync_playwright() as p:
        b = p.webkit.launch(); ctx, pg, errs = B._open(b, server, w, h, style, theme)
        _edit(pg, False)
        pg.wait_for_selector("#detail-content .aed-add", state="attached", timeout=8000)
        add = pg.locator("#detail-content .aed-add").first
        for where in ("center", "start", "end"):
            pg.evaluate("w => { const e = document.querySelector('#detail-content .aed-add'); e.scrollIntoView({block: w}); }", where); pg.wait_for_timeout(250)
            add.click(); pg.wait_for_timeout(400)
            r = pg.eval_on_selector("#aed-kinds", R)
            assert r[0] >= 19.5 and r[1] >= 19.5 and r[2] <= w - 19.5 and r[3] <= h - 19.5, (style, w, where, r)
            if AFTER and where == "start" and style == "classic" and w == 1440: pg.screenshot(path=f"{AFTER}/classic-d1440-add-popover.png")
            pg.evaluate("document.getElementById('aed-kinds').classList.remove('show')"); pg.wait_for_timeout(150)
        assert not errs; ctx.close(); b.close()


@pytest.mark.parametrize("style,theme", STYLES)
def test_no_side_tab_shows_beside_a_phone_sheet(server, style, theme):
    with pw.sync_playwright() as p:
        b = p.webkit.launch(); ctx, pg, errs = B._open(b, server, 390, 844, style, theme)
        _edit(pg, True)
        pg.locator("#alto-edit-exit .ee-ask").click(); pg.wait_for_selector("#alto-handoff .ah-pick", timeout=5000); pg.wait_for_timeout(300)
        vis = pg.evaluate("""() => [...document.querySelectorAll('#notes-toggle,#hamburger-tab,#minimap-toggle,#search-toggle,#tab-rail,#tab-rail *')].filter(e => {
          const cs = getComputedStyle(e), r = e.getBoundingClientRect(); return cs.visibility !== 'hidden' && cs.display !== 'none' && r.width > 0 && r.height > 0; }).map(e => e.id || e.className)""")
        seen = pg.evaluate("document.querySelectorAll('#notes-toggle,#hamburger-tab,#minimap-toggle,#search-toggle').length")
        assert seen >= 3, seen                                                                  # the tabs are there; they are just hidden
        assert vis == [], vis
        if AFTER and style == "holo": pg.screenshot(path=f"{AFTER}/p390-sheet-side-tabs-hidden-{style}.png")
        ctx.close(); b.close()


@pytest.mark.parametrize("style,theme", STYLES)
@pytest.mark.parametrize("w,h", ((1440, 900), (1280, 720)))
def test_the_popover_clears_the_top_bar_and_its_claude_group_scrolls_into_view(server, style, theme, w, h):
    """Board B-1121-HANDOFF-GO-COND U2: between the top bar's bottom (+12px) and the button; scrolls inside with a cue; the Claude group is reachable."""
    with pw.sync_playwright() as p:
        b = p.webkit.launch(); ctx, pg, errs = B._open(b, server, w, h, style, theme)
        _edit(pg, False)
        pg.wait_for_selector("#detail-content .aed-add", state="attached", timeout=8000)
        add = pg.locator("#detail-content .aed-add").first
        for where in ("center", "start", "end"):
            pg.evaluate("w => document.querySelector('#detail-content .aed-add').scrollIntoView({block: w})", where); pg.wait_for_timeout(250)
            add.click(); pg.wait_for_timeout(400)
            r = pg.eval_on_selector("#aed-kinds", R)
            chrome = pg.evaluate("""() => ['#title-bar', '#nav', '#node-nav-bar', '#desk-back', '.dbr-back'].flatMap(s => [...document.querySelectorAll(s)]).filter(x => { const q = x.getBoundingClientRect(), cs = getComputedStyle(x);
              return cs.display !== 'none' && cs.visibility !== 'hidden' && q.width > 0 && q.height > 0 && q.top < 160; }).map(x => { const q = x.getBoundingClientRect(); return [x.id || x.className, q.left, q.top, q.right, q.bottom]; })""")
            assert {c[0] for c in chrome} >= {"title-bar", "nav", "node-nav-bar"}, chrome                  # the whole top chrome was found: title row, chip row, nav strip
            for c in chrome:
                assert not _hit(r, c[1:]), (style, w, where, r, c)                                           # the popover intersects none of it
            assert r[1] >= max(c[4] for c in chrome) + 11.5, (style, w, where, r, chrome)                    # and sits 12px below the lowest
            assert r[0] >= 19.5 and r[2] <= w - 19.5 and r[3] <= h - 19.5, (style, w, where, r)
            btn = add.evaluate(R)
            assert r[3] <= btn[1] + .5 or r[1] >= btn[3] - .5, (style, w, where, r, btn)  # clear of its own button
            pg.evaluate("document.getElementById('aed-kinds').scrollTop = 1e6"); pg.wait_for_timeout(150)
            g = pg.eval_on_selector("#aed-kinds .aed-askrow button", R)
            assert g[1] >= r[1] - .5 and g[3] <= r[3] + .5, (style, w, where, g, r)       # the Claude group is in view once scrolled to the end
            cues = pg.evaluate("document.getElementById('aed-kinds').className")
            pg.evaluate("document.getElementById('aed-kinds').scrollTop = 0"); pg.wait_for_timeout(100)
            sc = pg.evaluate("(() => { const e = document.getElementById('aed-kinds'); return [e.scrollHeight > e.clientHeight + 2, e.className]; })()")
            if sc[0]: assert "aed-more-below" in sc[1], (style, w, where, sc)             # a scrolling popover shows its cue
            pg.evaluate("document.getElementById('aed-kinds').classList.remove('show')"); pg.wait_for_timeout(120)
        assert not errs; ctx.close(); b.close()
