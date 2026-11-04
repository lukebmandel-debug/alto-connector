"""The Memory Atlas's three control groups are ONE icon row at the bottom centre on a desktop (Luke, L-1104-122629, option C of Art's sheet
atlas-one-control): Start Tour (which becomes the Tour player in the same spot), flat map | globe, the whole world, zoom. Every icon has a
tooltip; where you are (back / name / next, the minimap switch) is a small label bar just above the row. A phone is unchanged. Chromium and
WebKit, the page and browsers of test_world_palace_render.py."""
import pytest

from tests.test_world_palace_render import ENL, _open, _settle, browser, html, origin  # noqa: F401

ROW = "(() => { var r = document.querySelector('#wpal-root .wp-row').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })()"
# the page's own bottom controls (Account, search, list, info, dark, edit pill: outside the map's root), as rectangles
SHARED = """(() => { var out = []; [].forEach.call(document.body.querySelectorAll('*'), e => {
  if (e.closest('#wpal-root') || e.closest('svg')) return; var s = getComputedStyle(e); if (s.position !== 'fixed' || s.display === 'none' || s.visibility === 'hidden') return;
  var r = e.getBoundingClientRect(); if (r.width > 0 && r.height > 0 && r.top > innerHeight - 120 && r.width < 400) out.push([e.id || e.className, r.left, r.top, r.right, r.bottom]); });
  return out; })()"""


def _clear(a, b, gap=0):
    return a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1]


def _flat(page):
    page.evaluate("AltoWorld.globe(false)")
    _settle(page, 600)


def test_one_row_at_the_bottom_centre_and_the_old_groups_are_gone(browser, origin):  # noqa: F811
    page, errors = _open(browser, origin)
    try:
        r = page.evaluate(ROW)
        assert abs((r[0] + r[2]) / 2 - 640) <= 2 and r[3] >= 800 - 30, r                       # centred, on the bottom edge
        for sel in ("#wpal-root .wp-ctl", "#wpal-root .wp-tour"):                               # the old bars are not drawn as bars
            assert page.evaluate(f"getComputedStyle(document.querySelector('{sel}')).display") == "contents", sel
        # nothing of the old top-right group is up there any more: every Tour / World / zoom / flat-globe control sits inside the row
        out = page.evaluate("""(() => { var r = document.querySelector('#wpal-root .wp-row').getBoundingClientRect();
          return [].filter.call(document.querySelectorAll('#wpal-root .wp-row button'), b => { var q = b.getBoundingClientRect();
            return q.width && (q.top < r.top - 1 || q.bottom > r.bottom + 1 || q.left < r.left - 1 || q.right > r.right + 1); }).length; })()""")
        assert out == 0
        top = page.evaluate("[].filter.call(document.querySelectorAll('#wpal-root .wp-btn'), b => { var q = b.getBoundingClientRect(); return q.width && q.top < 120; }).length")
        assert top == 0                                                                         # nothing left at the top
        assert page.evaluate("getComputedStyle(document.querySelector('#wpal-root .wp-nav')).display") != "none"     # the breadcrumb is kept
        assert not errors, errors
    finally:
        page.close()


def test_start_tour_turns_into_the_player_in_place(browser, origin):  # noqa: F811
    page, errors = _open(browser, origin)
    try:
        page.evaluate("AltoWorld.tourMode(false)")
        r0 = page.evaluate(ROW)
        tt = "document.querySelector('#wpal-root .wp-tt')"
        assert page.evaluate(f"getComputedStyle({tt}).display") != "none"
        assert "Start Tour" in page.evaluate(f"getComputedStyle({tt}, '::before').content")
        assert page.evaluate("document.querySelector('#wpal-root .wp-tour').hidden")
        page.click("#wpal-root .wp-tt")                                                         # Start Tour
        _settle(page, 900)
        assert page.evaluate("AltoWorld.tourMode()")
        assert not page.evaluate("document.querySelector('#wpal-root .wp-tour').hidden")
        assert page.evaluate(f"getComputedStyle({tt}).display") == "none"                       # the button is the player now
        r1 = page.evaluate(ROW)
        assert abs((r1[0] + r1[2]) / 2 - (r0[0] + r0[2]) / 2) <= 2 and abs(r1[3] - r0[3]) <= 1, (r0, r1)   # same centre line, same bottom
        pv = page.evaluate("document.querySelector('#wpal-root .wp-tour button[aria-label=\"Previous stop\"]').getBoundingClientRect().left")
        assert r1[0] < pv < r1[0] + 20 and page.evaluate("document.querySelector('#wpal-root .wp-tour .c').textContent").startswith("Tour")
        page.click("#wpal-root .wp-tour .x")                                                    # End the Tour: back to Start Tour
        _settle(page, 500)
        assert not page.evaluate("AltoWorld.tourMode()") and page.evaluate(f"getComputedStyle({tt}).display") != "none"
        assert not errors, errors
    finally:
        page.close()


def test_every_icon_has_a_tooltip_and_works(browser, origin):  # noqa: F811
    page, errors = _open(browser, origin)
    try:
        page.evaluate("AltoWorld.tourMode(false)")
        _flat(page)
        bare = page.evaluate("[].filter.call(document.querySelectorAll('#wpal-root .wp-row button, #wpal-root .wp-nav button'), b => !b.title).length")
        assert bare == 0                                                                        # every icon says what it does
        k0 = page.evaluate("AltoWorld.view().k")
        page.click("#wpal-root .wp-row button[aria-label='Zoom in']")
        _settle(page, 700)
        k1 = page.evaluate("AltoWorld.view().k")
        assert k1 > k0 * 1.3
        page.click("#wpal-root .wp-row button[aria-label='Zoom out']")
        _settle(page, 700)
        assert page.evaluate("AltoWorld.view().k") < k1 / 1.3
        page.evaluate("AltoWorld.select('erie')")                                               # Whole world: the card goes, the map frames the world
        _settle(page)
        assert page.evaluate(ENL) == "erie"
        page.click("#wpal-root .wp-row .wp-ctl > .wp-btn:nth-child(2)")
        _settle(page)
        assert page.evaluate(ENL) is None
        assert page.evaluate("document.querySelector('#wpal-root .wp-nav .wp-at').textContent") == "Whole world"
        if page.evaluate("AltoWorld.globe(true)"):                                              # map | globe (where there is WebGL)
            _settle(page, 600)
            page.click("#wpal-root .wp-row .wp-seg [aria-label='Flat map']")
            assert not page.evaluate("AltoWorld.globe()")
            page.click("#wpal-root .wp-row .wp-seg [aria-label=Globe]")
            assert page.evaluate("AltoWorld.globe()")
        assert not errors, errors
    finally:
        page.close()


def test_the_whole_world_breadcrumb_is_a_label_above_the_row(browser, origin):  # noqa: F811
    page, errors = _open(browser, origin)
    try:
        page.evaluate("AltoWorld.tourMode(false)")
        nav = "(() => { var r = document.querySelector('#wpal-root .wp-nav').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })()"
        n, r = page.evaluate(nav), page.evaluate(ROW)
        assert n[3] <= r[1] + 1 and r[1] - n[3] < 30 and abs((n[0] + n[2]) / 2 - 640) <= 2, (n, r)    # just above the bar, centred
        assert page.evaluate("document.querySelector('#wpal-root .wp-nav .wp-at').textContent") == "Whole world"
        assert page.evaluate("document.querySelector('#wpal-root .wp-nav .wp-up').title") and page.evaluate("document.querySelector('#wpal-root .wp-nav .wp-nx').title")
        page.evaluate("AltoWorld.select('erie1')")
        _settle(page)
        assert "›" in page.evaluate("document.querySelector('#wpal-root .wp-nav .wp-at').textContent")
        page.click("#wpal-root .wp-nav .wp-up")                                                 # still back / next
        _settle(page)
        assert page.evaluate(ENL) == "erie"
        assert not errors, errors
    finally:
        page.close()


@pytest.mark.parametrize("width", [1280, 1024])
def test_the_row_does_not_collide_with_the_shared_controls(browser, origin, width):  # noqa: F811
    page = browser.new_page(viewport={"width": width, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        shared = page.evaluate(SHARED)
        assert len(shared) >= 3, shared                                                         # Account and the right-hand cluster are really there
        for tour in (False, True):                                                              # roaming (narrowest) and the player (widest)
            page.evaluate(f"AltoWorld.tourMode({str(tour).lower()})")
            page.evaluate("AltoWorld.select('erie1')") if tour else None
            _settle(page, 900)
            r = page.evaluate(ROW)
            nav = page.evaluate("(() => { var r = document.querySelector('#wpal-root .wp-nav').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })()")
            assert r[0] >= 0 and r[2] <= width, r
            for s in shared:
                assert _clear(r, s[1:], 6), (tour, "row", r, s)
                assert _clear(nav, s[1:], 6), (tour, "label", nav, s)
        assert not errors, errors
    finally:
        page.close()


def test_a_phone_keeps_every_control_where_it_was(browser, origin):  # noqa: F811
    ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, user_agent=ua, has_touch=True)
    page = ctx.new_page()
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        _settle(page, 900)
        assert page.evaluate("getComputedStyle(document.querySelector('#wpal-root .wp-row')).display") == "contents"
        assert page.evaluate("getComputedStyle(document.querySelector('#wpal-root .wp-seg') || document.body).display") != "inline-flex"   # no desktop row piece
        g = page.evaluate("""(() => { var q = s => { var r = document.querySelector(s).getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)]; };
          return {ctl: q('#wpal-root .wp-ctl'), tour: q('#wpal-root .wp-tour'), tt: document.querySelector('#wpal-root .wp-tt').textContent,
                  wb: document.querySelector('#wpal-root .wp-ctl > .wp-btn:nth-child(2)').textContent, vw: innerWidth, vh: innerHeight}; })()""")
        assert g["tt"] == "Tour" and g["wb"].startswith("⤢"), g                                 # the same words, not the desktop's icons
        assert page.evaluate("getComputedStyle(document.querySelector('#wpal-root .wp-ctl')).position") == "absolute"      # still its own bar (Alto's phone view takes it in)
        assert g["tour"][3] == 844 - 68, g                                                      # the Tour strip still 68px up
        assert page.evaluate("getComputedStyle(document.querySelector('#wpal-root .wp-nav')).display") == "none"
        assert page.evaluate("getComputedStyle(document.querySelector('#wpal-root .wp-tt'), '::before').content") in ("none", "normal")
    finally:
        ctx.close()
        page.close()
