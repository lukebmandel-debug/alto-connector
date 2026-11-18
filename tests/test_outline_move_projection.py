"""Moving a card or a branch of an outline in edit mode shows, while it is held, the page as the drop will leave it
(Luke, 2026-11-17: "When i move a branch, I should be able to see a projection of where everything will land, same
with node. Its still jumping stuff to places that make no sense").
Held ON another card it goes into the outline there: under it, before it or after it, the card it is held on wearing
the mark and the words by the pointer saying which; the outline on screen is the one the drop leaves, to the px.
Held on open board it stays where it is held; it is never sent somewhere the pointer is not. Escape, or letting go
where it was picked up, changes nothing; undo puts everything back; the page does not scroll.
Skipped when Playwright or its browsers are not installed."""
import pytest

from test_outline_branch_drag import GEO, LINES, _branch, _edit, _grab, _open, _ops, _touching, url  # noqa: F401

BOX = "(i)=>{var r=document.querySelector('#node-'+i+' .node-card').getBoundingClientRect(); return [r.left,r.top,r.width,r.height];}"
# every card's box as it is DRAWN, in the outline's own px (a card held on open board is drawn by a translate)
DRAWN = """() => { var out={}; document.querySelectorAll('#world .node').forEach(function(el){
  var c=el.querySelector('.node-card'); if(!c||!el.offsetWidth) return; var m=/^(-?[\\d.]+)px(?:\\s+(-?[\\d.]+)px)?/.exec(el.style.translate||'');
  out[el.id.slice(5)]={l:parseFloat(el.style.left)-c.offsetWidth/2+(m?+m[1]:0), t:parseFloat(el.style.top)-c.offsetHeight/2+(m?+(m[2]||0):0), w:c.offsetWidth, h:c.offsetHeight}; }); return out; }"""
HELD = """() => ({tip: (document.getElementById('aed-rztip')||{}).textContent || '',
  marks: [].map.call(document.querySelectorAll('#world .aed-mark'), function(m){ return m.className.replace('aed-mark aed-mark-', '') + '@' + m.parentNode.id.slice(5); }),
  land: [].map.call(document.querySelectorAll('#world .node.aed-land'), function(e){ return e.id.slice(5); }),
  tg: [].map.call(document.querySelectorAll('#world .node.aed-tg'), function(e){ return e.id.slice(5); })})"""
OUTL = "(i)=>{var O=window._ALTO_OUTLINE; return {p: O.parent[i]||'', sibs: (O.kids[O.parent[i]]||[]).slice(), num: NODE_ORDER_MAP[i], all: JSON.stringify([O.kids, O.parent])};}"
SCROLL = "(()=>{var c=document.getElementById('canvas'); return [window.scrollX, window.scrollY, c.scrollLeft, c.scrollTop, (document.scrollingElement||{}).scrollTop||0];})()"


@pytest.fixture(params=["webkit", "chromium"])
def page(request, url):
    return _edit(_open(request, url, request.param))


def _carry(pg, i, tgt, fx, fy, shift=False):
    """Press card i and carry it to the point (fx, fy: fractions of its box) of card tgt. Left held."""
    x, y, k = _grab(pg, i)
    pg.mouse.move(x, y)
    pg.wait_for_timeout(350)
    if shift:
        pg.keyboard.down("Shift")
    pg.mouse.down()
    pg.mouse.move(x + 10, y + 8)
    pg.wait_for_timeout(80)
    b = pg.evaluate(BOX, tgt)
    tx, ty = b[0] + b[2] * fx, b[1] + b[3] * fy
    for s in range(1, 9):
        pg.mouse.move(x + (tx - x) * s / 8, y + (ty - y) * s / 8)
        pg.wait_for_timeout(40)
    pg.wait_for_timeout(550)
    return tx, ty


def _drop(pg, shift=False):
    pg.mouse.up()
    if shift:
        pg.keyboard.up("Shift")
    pg.wait_for_timeout(900)


def _same_px(a, b, tol=1):
    return [k for k in a if k not in b or abs(a[k]["l"] - b[k]["l"]) > tol or abs(a[k]["t"] - b[k]["t"]) > tol]


# (what is moved, the card it is held on, where on that card, what the drop is, its parent after, the card it follows)
MOVES = [
    ("x64", "x2", .5, .5, "under", "x2", "x66"),                        # a card (nothing under it): under another
    ("x64", "x63", .5, .08, "before", "x1", None),                      # before the card beside it
    ("x63", "x64", .5, .92, "after", "x1", "x64"),                      # after it
    ("x1", "x2", .5, .5, "under", "x2", "x66"),                         # a branch (2 cards under it): under another
    ("x1", "x2", .5, .92, "after", "definiteness", "x2"),               # after its sibling
    ("x2", "x1", .5, .08, "before", "definiteness", None),              # before it
    ("definiteness", "preliminary-negotiations", .5, .5, "under", "preliminary-negotiations", "x3"),   # 7 cards, to another branch
    ("x7", "mirror-image", .5, .92, "after", "acceptance", "mirror-image"),                              # across branches, a place in the order
]


@pytest.mark.parametrize("card,on,fx,fy,what,parent,follows", MOVES)
def test_the_projection_while_held_is_the_outline_the_drop_leaves(page, card, on, fx, fy, what, parent, follows):
    g0, o0, sc0, sub = page.evaluate(GEO), page.evaluate(OUTL, card), None, _branch(page, card)
    _carry(page, card, on, fx, fy)
    sc0 = page.evaluate(SCROLL)
    h, proj, op = page.evaluate(HELD), page.evaluate(GEO), page.evaluate(OUTL, card)
    # clear which of the three it is: the words, the mark on the card it is held on, the held cards ringed where they land
    assert h["tip"].startswith("Goes %s “" % what) and h["tg"] == [on], h
    assert h["marks"] == [("in" if what == "under" else "v") + "@" + on] or h["marks"] == ["h@" + on], h
    assert sorted(h["land"]) == sorted(sub), h
    assert (", with the %d card" % (len(sub) - 1) in h["tip"]) == (len(sub) > 1), h["tip"]
    assert op["p"] == parent and op["num"] and ("as " + page.evaluate("(i)=>window._altoP ? window._altoP(NODE_ORDER_MAP[i]) : NODE_ORDER_MAP[i]", card)) in h["tip"]
    assert _ops(page) == {}                                               # shown, not stored
    assert _touching(proj) == []
    _drop(page)
    g1, o1 = page.evaluate(GEO), page.evaluate(OUTL, card)
    assert _same_px(proj, g1, 0) == [] and _same_px(g1, proj, 0) == []    # every card where the projection had it
    assert o1["all"] == op["all"] and o1["p"] == parent and o1["num"] == op["num"]
    i = o1["sibs"].index(card)
    assert (o1["sibs"][i - 1] if i else None) == follows, o1["sibs"]
    assert page.evaluate(SCROLL) == sc0                                   # the page did not scroll or jump
    assert page.evaluate(LINES) == [] and _touching(g1) == []
    assert not page.evaluate("document.querySelectorAll('#world .aed-mark, #world .node.aed-land, #world .node.aed-tg, #world .node.aed-moving').length")
    page.mouse.move(5, 450)
    page.wait_for_timeout(500)
    assert page.evaluate(CALM) == 0                                        # a normal board: nothing dimmed, no line picked out
    assert any(k.startswith(("rp|", "so|")) for k in _ops(page))
    page.mouse.move(5, 450)
    page.keyboard.press("Meta+z" if page.evaluate("/Mac/.test(navigator.platform)") else "Control+z")
    page.wait_for_timeout(800)
    assert _same_px(g0, page.evaluate(GEO), 0) == [] and page.evaluate(OUTL, card)["all"] == o0["all"]      # one step of undo, exactly
    assert not [k for k, o in _ops(page).items() if o["v"] not in (None, o.get("b"))]


def _same_place(a, b):
    """Cards not in the same place, by where the page put them (the card under the pointer is drawn a little larger:
    its left edge is not its place; its centre and top are)."""
    return [k for k in a if k not in b or abs(a[k]["l"] + a[k]["w"] / 2 - b[k]["l"] - b[k]["w"] / 2) > 0.01 or abs(a[k]["t"] - b[k]["t"]) > 1]


# the connectors as drawn: every line of the board, by the cards it joins
EDGES = "(()=>[].map.call(document.querySelectorAll('#canvas svg path[data-edge]'), function(p){ return p.getAttribute('data-edge') + ' ' + (p.getAttribute('data-d0') || p.getAttribute('d')); }).sort())()"
CALM = "document.querySelectorAll('#world .node-card.dimmed, #world .node-card.rel-dimmed, #world .node-card.ent-dimmed, #world .node.dimmed, #world .node.rel-dimmed').length"


@pytest.mark.parametrize("card,on,fx,fy", [("x1", "x2", .5, .5), ("x64", "x63", .5, .08), ("x7", "mirror-image", .5, .92)])
def test_the_dropped_board_is_the_board_the_page_draws_afresh(page, card, on, fx, fy):
    """Board, 2026-11-17: the dropped layout routes its connectors as the page builds them afresh, and looks like a
    normal board. The lines and cards after the drop are the ones a reload of the page (the stored change laid over
    it, everything laid out and routed from nothing) draws, and no card is dimmed with the pointer away."""
    _carry(page, card, on, fx, fy)
    held = page.evaluate(GEO)
    _drop(page)
    page.mouse.move(5, 450)
    page.wait_for_timeout(600)
    g1, e1 = page.evaluate(GEO), page.evaluate(EDGES)
    assert _same_place(held, g1) == [] and page.evaluate(CALM) == 0 and page.evaluate(LINES) == []
    page.wait_for_timeout(900)                                            # (the change reaches the account)
    page.reload()
    page.wait_for_timeout(1800)
    _edit(page)
    page.mouse.move(5, 450)
    page.wait_for_timeout(600)
    assert _same_place(g1, page.evaluate(GEO)) == []
    e2 = page.evaluate(EDGES)
    assert e2 == e1, [x for x in e1 if x not in e2][:4]


def test_escape_and_letting_go_where_it_was_picked_up_change_nothing(page):
    g0, o0 = page.evaluate(GEO), page.evaluate(OUTL, "x1")
    _carry(page, "x1", "x2", .5, .5)
    assert page.evaluate(HELD)["tip"].startswith("Goes under") and _same_px(g0, page.evaluate(GEO)) != []
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    page.mouse.up()
    page.wait_for_timeout(600)
    assert _same_px(g0, page.evaluate(GEO), 0) == [] and page.evaluate(OUTL, "x1")["all"] == o0["all"] and _ops(page) == {}
    assert page.evaluate("document.documentElement.classList.contains('alto-editing')")
    # carried over another card and back to where it was: nothing
    x, y, k = _grab(page, "x1")
    tx, ty = _carry(page, "x1", "x2", .5, .5)
    for s in range(1, 9):
        page.mouse.move(tx + (x + 2 - tx) * s / 8, ty + (y + 2 - ty) * s / 8)
        page.wait_for_timeout(40)
    page.wait_for_timeout(500)
    assert "back where it was" in page.evaluate(HELD)["tip"]
    _drop(page)
    assert _same_px(g0, page.evaluate(GEO), 0) == [] and page.evaluate(OUTL, "x1")["all"] == o0["all"] and _ops(page) == {}


def test_what_it_is_held_on_does_not_flip_as_the_cards_step_aside(page):
    """The cards move under a still pointer as the projection is drawn: what the pointer is on is read against the
    outline as it was picked up, so the drop it shows stays the same while the pointer barely moves."""
    tx, ty = _carry(page, "x2", "x1", .5, .08)
    tip, proj = page.evaluate(HELD)["tip"], page.evaluate(GEO)
    assert tip.startswith("Goes before")
    for dx, dy in ((2, 1), (-2, -1), (3, 2), (0, 0), (-3, 1), (1, -2)):
        page.mouse.move(tx + dx, ty + dy)
        page.wait_for_timeout(120)
        assert page.evaluate(HELD)["tip"] == tip and _same_px(proj, page.evaluate(GEO), 0) == []
    page.keyboard.press("Escape")
    page.mouse.up()


def test_shift_held_places_it_freely_and_a_unit_top_is_never_put_under_a_card(page):
    o0 = page.evaluate(OUTL, "x1")
    _carry(page, "x1", "x2", .5, .5, shift=True)
    h = page.evaluate(HELD)
    assert h["tip"].startswith("Moving this card") and h["marks"] == [] and h["tg"] == [], h
    page.keyboard.press("Escape")
    _drop(page, shift=True)
    assert page.evaluate(OUTL, "x1")["all"] == o0["all"]
    _carry(page, "consideration", "reliance", .5, .5)                    # a unit's top card has no place in another's order
    h = page.evaluate(HELD)
    assert not h["tip"].startswith("Goes") and h["marks"] == [], h
    page.keyboard.press("Escape")
    page.mouse.up()


# the drags Luke's report was reproduced with (v1.9.235): each landed hundreds of px from where it was held
JUMPS = [("definiteness", 300, 0), ("definiteness", 620, 30), ("x2", 300, -200), ("acceptance", -500, -200), ("x7", 300, 100), ("reliance-damages", 760, 60)]


@pytest.mark.parametrize("card,wx,wy", JUMPS)
def test_held_on_open_board_it_lands_where_it_is_held_or_goes_back_never_elsewhere(page, card, wx, wy):
    g0, sub = page.evaluate(GEO), _branch(page, card)
    x, y, k = _grab(page, card)
    page.mouse.move(x, y)
    page.wait_for_timeout(350)
    page.mouse.down()
    for s in range(1, 9):
        page.mouse.move(x + wx * k * s / 8, y + wy * k * s / 8)
        page.wait_for_timeout(40)
    page.wait_for_timeout(500)
    h, drawn, sc0 = page.evaluate(HELD), page.evaluate(DRAWN), page.evaluate(SCROLL)
    if h["tip"].startswith("Goes "):                                      # (the pointer ended on a card: that is the test above)
        page.keyboard.press("Escape")
        page.mouse.up()
        pytest.skip("on a card")
    _drop(page)
    g1 = page.evaluate(GEO)
    dx, dy = g1[card]["l"] - g0[card]["l"], g1[card]["t"] - g0[card]["t"]
    assert page.evaluate(SCROLL) == sc0
    if "go back" in h["tip"]:
        assert (dx, dy) == (0, 0) and _same_px(g0, g1, 0) == [] and _ops(page) == {}
        return
    # where it was held: its x to the px (or the page's edge), and no more than a card lower; never above, never aside
    assert abs(dx - wx) <= 1 or "page ends here" in h["tip"] or ("free spot" in h["tip"] and abs(dx - wx) <= 150), (dx, dy, h["tip"])
    assert -1 <= dy - wy <= 240 or ("free spot" in h["tip"] and abs(dy - wy) <= 150), (dx, dy, h["tip"])
    assert all(abs(g1[m]["l"] - g0[m]["l"] - dx) <= 1 and abs(g1[m]["t"] - g0[m]["t"] - dy) <= 1 for m in sub)       # one piece
    assert _same_px(drawn, g1) == []                                      # as it was drawn while held, every card
    rest = [m for m in g0 if m not in sub and (g1[m]["l"], g1[m]["t"]) != (g0[m]["l"], g0[m]["t"])]
    assert all(g1[m]["l"] == g0[m]["l"] and g1[m]["t"] > g0[m]["t"] for m in rest)                                # room is made downward only
    assert _touching(g1) == [] and page.evaluate(LINES) == []
    page.mouse.move(5, 450)
    page.keyboard.press("Meta+z" if page.evaluate("/Mac/.test(navigator.platform)") else "Control+z")
    page.wait_for_timeout(800)
    assert _same_px(g0, page.evaluate(GEO), 0) == []


def test_a_finger_picks_a_card_up_by_pressing_and_holding_and_a_swipe_still_pans(request, url):
    """Touch (a tablet): the card is picked up after a moment's hold, then follows the finger like the mouse; a swipe
    across a card starts no move."""
    pg = _open(request, url, "chromium")
    _edit(pg)
    x, y, k = _grab(pg, "x1")
    b = pg.evaluate(BOX, "x2")
    ev = """([type, x, y]) => { var el = document.elementFromPoint(x, y) || document.body;
      el.dispatchEvent(new PointerEvent(type, {bubbles: true, cancelable: true, composed: true, pointerId: 7, pointerType: 'touch', isPrimary: true, button: 0, buttons: type === 'pointerup' ? 0 : 1, clientX: x, clientY: y})); }"""
    pg.evaluate(ev, ["pointerdown", x, y])
    pg.evaluate(ev, ["pointermove", x + 60, y + 30])                      # a swipe: no move begins
    pg.wait_for_timeout(500)
    assert not pg.evaluate("document.documentElement.classList.contains('alto-dragging')")
    pg.evaluate(ev, ["pointerup", x + 60, y + 30])
    pg.evaluate(ev, ["pointerdown", x, y])
    pg.wait_for_timeout(520)                                              # held still
    assert pg.evaluate("document.documentElement.classList.contains('alto-dragging')")
    tx, ty = b[0] + b[2] * .5, b[1] + b[3] * .5
    for s in range(1, 7):
        pg.evaluate(ev, ["pointermove", x + (tx - x) * s / 6, y + (ty - y) * s / 6])
        pg.wait_for_timeout(60)
    pg.wait_for_timeout(500)
    h, proj = pg.evaluate(HELD), pg.evaluate(GEO)
    assert h["tip"].startswith("Goes under") and h["tg"] == ["x2"], h
    pg.evaluate(ev, ["pointerup", tx, ty])
    pg.wait_for_timeout(900)
    assert pg.evaluate(OUTL, "x1")["p"] == "x2" and _same_px(proj, pg.evaluate(GEO), 0) == []
