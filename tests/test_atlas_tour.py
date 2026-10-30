"""A Memory Atlas Tour stop hands off instead of popping (Luke, 2026-10-28: "I don't like how the nodes pop up on tour. It feels too jumpy
and too far removed from the point of origin"; Art's option B, notes atlas-build (b)): the card a stop leaves folds into its own pin, the
glide is speed-capped, and the next card grows out of its marker before the map stops, its origin on the pin. Chromium and WebKit."""
from tests.test_world_palace_render import ENL, _open, _settle, browser, html, origin  # noqa: F401

HOP = r"""(([a, b]) => new Promise(res => { AltoWorld.select(a, {instant: true}); setTimeout(() => {
  var R = {ghost0: null, before: null, origin: null}, t0 = performance.now(), landed = false;
  AltoWorld.on('land', () => { if(!landed){ landed = true; R.before = !!document.querySelector('#wpal-root .wp-enl[data-id="' + b + '"]'); } });
  AltoWorld.select(b);
  R.ghost0 = !!document.querySelector('#wpal-root .wp-ghost');                       // the old card is still there, folding
  (function f(){ var e = document.querySelector('#wpal-root .wp-enl[data-id="' + b + '"]'), p = document.querySelector('#wpal-root .wp-pin.wp-on');
    if(e && p && R.origin == null){ var o = getComputedStyle(e).transformOrigin.split(' ').map(parseFloat), q = /translate\(([-\d.]+)px, ([-\d.]+)px\)/.exec(p.style.transform);
      R.origin = Math.hypot(o[0] - +q[1], o[1] - +q[2]); }                           // (the map's own px: the page may be zoomed)
    if(performance.now() - t0 < 2200) requestAnimationFrame(f); else res(R); })(); }, 300); }))"""


def test_a_tour_stop_hands_off_from_pin_to_pin(browser, origin):  # noqa: F811
    page, errors = _open(browser, origin)
    try:
        r = page.evaluate(HOP, ["gj", "erie"])
        assert r["ghost0"]                                        # the origin is never deleted at once
        assert r["before"]                                        # the next card is growing before the map stops
        assert r["origin"] is not None and r["origin"] < 3        # out of its own marker
        _settle(page, 300)
        assert page.evaluate(ENL) == "erie" and not page.evaluate("!!document.querySelector('#wpal-root .wp-ghost')")
        assert not errors, errors
    finally:
        page.close()


def test_a_card_to_card_hop_in_one_place_folds_and_grows(browser, origin):  # noqa: F811
    page, errors = _open(browser, origin)
    try:
        page.evaluate("AltoWorld.select('pj')")
        _settle(page)
        page.evaluate("AltoWorld.select('pj2')")                 # a card of the cluster that is open: no flight
        assert page.evaluate("!!document.querySelector('#wpal-root .wp-ghost')")
        _settle(page, 900)
        assert page.evaluate(ENL) == "pj2"
        assert not errors, errors
    finally:
        page.close()
