"""1.9.95: a building the battleship shells is rebuilt as a construction site (palace_construct.py), not stretched back up."""
import re

from alto.build import palace, palace_construct, palace_fleet_asset

JS = palace_construct.CONSTRUCT_JS


def test_the_module_is_wired_into_the_page_and_the_old_stretch_is_gone():
    # 1.9.99: the rebuild is part of the hosted fleet script (palace_fleet_asset.py), not of the page
    fj = palace_fleet_asset.FLEET_JS
    assert palace_construct.CONSTRUCT_JS in palace_fleet_asset.FLEET_ASSET and palace_construct.CONSTRUCT_CSS in palace_fleet_asset.FLEET_CSS_ALL
    assert palace_construct.CONSTRUCT_JS not in palace.PALACE_JS and palace_construct.CONSTRUCT_CSS not in palace.PALACE_CSS
    assert "function fxRuin(el_, tagEl){ if(el_ && window._palCon) window._palCon.run(el_, tagEl); }" in fj
    assert "scaleY(" not in fj.split("function fxRuin")[1].split("function fxTarget")[0]       # never stretch the building
    assert "_storeys" not in palace.PALACE_JS and "_storeys" not in fj


def test_the_node_building_keeps_its_footprint_for_the_rebuild():
    js = palace.PALACE_JS
    assert "res.C=C; return res;" in js and "s._nb={C:b.C, H:H, id:id};" in js


def test_the_sequence_has_every_stage_in_order_over_twenty_seconds():
    t = palace_construct.CONSTRUCT_JS
    m = re.search(r"var T=\{(.*?)\};", t, re.S).group(1)
    nums = {k: [int(x) for x in re.findall(r"\d+", v)] for k, v in re.findall(r"(\w+):(\[[^\]]*\]|\d+)", m)}
    assert nums["end"] == [20000]
    assert nums["coll"][0] < nums["rubOut"][0] < nums["found"][1]                    # rubble first, then the foundation
    assert nums["found"][0] < nums["mast"][0] < nums["frame"][0] < nums["clad"][0]    # crane up, steel frame, then glass
    assert nums["clad"][1] - 300 <= nums["roof"][0] < nums["roof"][1] < nums["propsOut"][1] <= nums["end"][0]   # roof last, props away before the swap
    assert nums["scaf"][0] > nums["frame"][0] and nums["scafOut"][0] >= nums["clad"][1] - 300
    for k in ("gFound", "gFrame", "gClad", "gScaf", "gProps"):
        assert k in t
    for word in ("hoarding", "rebar", "tower crane", "hoist", "scaffold", "foundation"):
        assert word in t.lower()


def test_each_storey_is_its_own_clipped_copy_and_never_scaled():
    assert "clipPath" in JS and "clip-path" in JS and "cloneNode(true)" in JS
    assert "scaleY" not in JS and "scale(" in JS                                      # (the jib grows out of the mast on x only)
    assert "[[cx-1500" in JS or "cx-1500" in JS                                       # a landmark: horizontal bands
    assert "faces.forEach" in JS                                                      # a node: each wall's storey parallelogram
    assert "roof=mkGroup" in JS                                                       # the roof (a tower's crown) is its own group, lowered last


def test_safari_safe_drawing():
    assert "<mask" not in JS and "mask=" not in JS and "filter:" not in JS and "feGaussian" not in JS    # no SVG mask on paths, no filters
    assert not re.search(r"[\d\)]\s*px|'px'|\"px\"", re.sub(r"/\*.*?\*/", "", JS, flags=re.S))   # no CSS px in transforms
    assert "style.transform" not in JS and ".animate(" not in JS                      # attribute transforms from one rAF loop
    assert "requestAnimationFrame(loop)" in JS and "freeze:function(ms)" in JS        # one loop; QA can freeze any instant


def test_the_real_art_is_put_away_and_restored_and_the_tag_stays_hidden_while_ruined():
    assert "k.style.display='none'" in JS and "k.style.display=''" in JS
    assert "tagEl.classList.add('nb-ruin')" in JS and "tagEl.classList.remove('nb-ruin')" in JS
    assert ".node.nb-ruin .node-card{opacity:0 !important;pointer-events:none;}" in palace_fleet_asset.FLEET_CSS_ALL
    assert "if(t>=T.end){ r.kill(); continue; }" in JS and "if(!r.S.host.isConnected){ r.kill(); continue; }" in JS
    assert "if(el_._con) el_._con.kill();" in JS                                      # a second hit restarts, never doubles
    assert ".nb-pr,.nb-pr *{pointer-events:none !important;}" in palace_construct.CONSTRUCT_CSS


def test_the_ends_of_the_sequence_are_the_real_building_so_nothing_pops():
    # the first frame is a whole copy of the art, the last is a whole copy cross-faded in before the layer is removed (checked pixel for pixel in QA: _qa/w95/b95_swap.py)
    assert "gFull" in JS and "xfade:[18600,19700]" in JS and "setO(gFull, 1-st)" in JS and "setO(gFull, x); setO(gBuilt, 1-x);" in JS
    assert "gCladL" in JS and "isLine(k)" in JS                                          # floor lines / sheen are cut between storey lines, drawn over all the glass
    assert "setProperty('opacity', tk, 'important')" in JS                              # the number tag fades out and back, never pops
