"""1.9.97: tiny people run and scream when the battleship brings a building down (palace_panic.py)."""
import gzip
import re

from alto.build import palace, palace_fleet_asset, palace_panic

JS = palace_panic.PANIC_JS


def _code(js):
    return re.sub(r"/\*.*?\*/", "", js, flags=re.S)


def test_the_module_is_wired_in_with_a_few_hooks_and_the_old_fx_line_is_untouched():
    assert JS in palace_fleet_asset.FLEET_ASSET and JS not in palace.PALACE_JS          # 1.9.99: hosted with the fleet, not in the page
    p = palace_fleet_asset.FLEET_JS
    assert "function fxRuin(el_, tagEl){ if(el_ && window._palCon) window._palCon.run(el_, tagEl); }" in p        # (test_palace_1995_build asserts this line)
    assert "window._palPanic.go({svg:H.svg, el:el, pin:pin, Z:H.Z, graph:H.graph, nearest:H.nearest, route:H.route, dk:H.dk()}, el_, tagEl)" in p
    assert "if(!on && window._palPanic) window._palPanic.stop();" in p                                          # Esc / stand down
    assert "'class':'pl-fx pl-panic'" in JS                                                                     # stackLayers keeps .pl-fx on top, never clickable


def test_it_is_small_enough_for_the_private_page():
    assert len(gzip.compress(JS.encode(), 9)) < 3700          # the page is within a few KB of Firestore's cap (about 3.1 KB of it once inside the page's own gzip)


def test_the_crowd_is_8_to_16_figures_of_two_shapes_plus_a_few_bubbles():
    c = _code(JS)
    assert "runs.length?8:(W>120?15:11)" in c                                       # 8 while another crowd runs, else 11 / 15 (a tower)
    assert "bubs.length<7" in c and "'AAAH!','RUN!','HELP!'" in c                    # text-only speech scraps, a few variants
    assert c.count("el('circle'") == 1 and c.count("el('path'") == 1                 # a head and one stroked path per figure
    assert "runs.length>=3" in c                                                    # never more than three crowds at once


def test_it_runs_along_the_streets_by_the_pages_own_graph():
    c = _code(JS)
    assert "C.route(sn, best)" in c and "g.NG[" in c                                  # route() between street corners, found in the node grid
    assert "g.Y[k]>=Y-8" in c                                                       # it leaves by the street in front, not behind the ruin
    assert "straight out and away" in JS                                            # a fallback where there is no street


def test_a_third_trip_and_two_look_back_and_three_stay_to_watch():
    c = _code(JS)
    assert "i===1||i===4" in c and "look:1" in c and "R()<.34" in c
    assert "w:i===2||i===5||i===8" in c and "1-sm((t-17000)/2700)" in c              # watchers fade out with the rebuild (palace_construct's 20 s)
    assert "END=20000" in c


def test_safari_safe_drawing_in_screen_pixels():
    c = _code(JS)
    assert "C.pin(layer, 'pl-pp'" in c and "C.pin(layer,'pl-pb'" in c               # sized by --tw, like every pinned thing
    assert "<mask" not in c and "filter" not in c and "feGaussian" not in c
    assert not re.search(r"[\d\)]\s*px|'px'|\"px\"", c)                              # no CSS px in transforms
    assert "style.transform" not in c and ".animate(" not in c and "style." not in c  # attribute transforms from one rAF loop
    assert "requestAnimationFrame(loop)" in c and "freeze:function(ms)" in c


def test_it_respects_reduced_motion_and_cleans_up():
    c = _code(JS)
    assert "prefers-reduced-motion: reduce" in c
    assert "!r.layer.isConnected || t>=END" in c                                     # gone with its svg, and at the end
    assert "if(r.key===el_) r.kill();" in c                                          # a building shelled again never doubles its crowd
    assert "removeChild(layer)" in c


def test_the_scream_is_called_only_if_the_sound_module_is_there():
    assert "window._palSnd && window._palSnd.scream && window._palSnd.scream(1)" in JS
