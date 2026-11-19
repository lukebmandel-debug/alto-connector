"""New Jersey is named Hell on New York's Memory Map, in the giant letters Philadelphia's far bank already wears (Luke, 2026-11-19), and
no banner's letters are drawn over by ground, pins or names. Offline; nothing here touches the network, Firebase or any ALTO_* setting."""
import copy
import gzip
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import city_boroughs, city_presets, palace, palace_areas  # noqa: E402
from alto.build.builder import load_brief  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "cities"
NJ_TOWNS = ("Jersey City", "Hoboken")                       # towns keep their names: only the STATE is renamed


@pytest.fixture(scope="module")
def nyc():
    from alto.build import city_gate
    m = json.loads(gzip.decompress((FIX / "manhattan.json.gz").read_bytes()))
    pre = city_presets.get("nyc")
    return palace.set_up(m["place"], list(m["bbox"]), districts=city_gate._districts(m["bbox"]), plan=m, preset="nyc", offline=True, fill=False,
                         cache_dir=None, majors=pre.get("majors"), diagonals=pre.get("diagonals") or [], parks=pre.get("parks") or [],
                         areas=pre.get("areas"), layout=pre.get("layout"), channels=pre.get("channels"), river_names=pre.get("river_names"))


def _page(pal):
    nodes = [{"id": "b%03d" % i, "act": 0, "tag": "Room", "title": "Room %d" % i, "desc": "A room."} for i in range(6)]
    brief = {"title": "t", "subject": "s", "timeline_id": "t", "mode": "palace", "node_noun": "Room", "period_noun": "Wing", "accent": "#5b8def",
             "acts": [{"label": "S1", "short": "S1", "color": "#4a9eff"}], "palace": copy.deepcopy(pal)}
    b, nd, _cn = load_brief({"brief": brief, "nodes": nodes, "connections": []})
    s = palace.palace_data(b, nd)
    return json.JSONDecoder().raw_decode(s[s.index("=") + 1:])[0]


def _page_map(pal):
    return _page(pal)["m"]


def _names(m):
    return [a["n"] for a in (m.get("areas") or [])] + [f["n"] for f in (m.get("far") or [])]


def _hits(box, x, y, name, em=11):
    """Does the name at (x, y) (centred, ~`em` px tall at 1:1 -- the label is far smaller than a letter) touch the letters' box?"""
    w = len(name) * em * .6 / 2
    return not (x + w < box[0] or x - w > box[2] or y + em < box[1] or y - em > box[3])


def test_new_york_names_the_state_hell_in_giant_letters(nyc):
    m = _page_map(nyc)
    assert [b["n"] for b in m["banners"]] == ["Hell"]
    assert "New Jersey" not in _names(m) and "NJ" not in _names(m)


def test_the_letters_stand_on_the_far_shore_and_clear_of_every_name(nyc):
    m = _page_map(nyc)
    (b,) = m["banners"]
    x0, y0, x1, y1 = b["box"]
    assert 0 <= x0 and x1 < m["W"] and 0 <= y0 and y1 < m["H"]
    x0, y0, x1, y1 = b["box"]
    pts = [(x0 + (x1 - x0) * i / 12, y0 + (y1 - y0) * j / 5) for i in range(13) for j in range(6)]
    assert not [p for p in pts if palace_areas._wet(m["sea"], *p)], "a letter stands in the water"      # on the dry far shore, not in the Hudson
    boxes = [(a["x"], a["y"], a["n"]) for a in m["areas"]] + [(f["x"], f["y"], f["n"]) for f in m["far"]]
    assert not [n for x, y, n in boxes if _hits(b["box"], x, y, n)], "a name stands over the letters"


def test_existing_hell_names_and_nj_towns_are_unchanged(nyc):
    m = _page_map(nyc)
    assert "Hell's Kitchen" in _names(m)
    labels = {l[0] for l in city_boroughs.LABELS}
    assert set(NJ_TOWNS) <= labels                                       # the towns keep their names in the full map's label list
    assert [a for a in city_presets.get("nyc")["areas"] if a["name"] == "Hell's Kitchen"]


def test_a_map_with_its_own_banners_keeps_them_and_other_cities_are_untouched(nyc):
    pal = copy.deepcopy(nyc)
    pal["banners"] = [{"name": "Wall", "river": "Hudson", "size": 400}]
    assert [b["n"] for b in _page_map(pal)["banners"]] == ["Wall"]
    far, banners = palace_areas.hell_for({"layout": "grid", "far": [{"n": "New Jersey", "x": 1, "y": 2}]}, None)
    assert far == [{"n": "New Jersey", "x": 1, "y": 2}] and banners is None      # only New York's own layout is renamed


def test_no_building_stands_in_the_letters(nyc):
    """A pin's dot and its leader line ran down over Philadelphia's first "l": a card's building is never placed where a banner's letters are."""
    d0 = _page(nyc)
    key = next(iter(d0["at"].values()))
    blocks = {str(b["id"]): b for b in palace.unpack(nyc["data_z"])["blocks"]}
    bl = blocks[key.split(".")[0]]
    lot = bl["lots"][int(key.split(".")[1])]
    pal = copy.deepcopy(nyc)
    pal["banners"] = [{"name": "Hell", "x": lot[0] + lot[2] / 2, "y": lot[1] + lot[3] / 2, "size": 500}]
    d = _page(pal)
    (bn,) = d["m"]["banners"]
    x0, y0, x1, y1 = bn["box"]
    assert x0 < lot[0] < x1 and y0 < lot[1] < y1                                   # the letters do stand where the building was
    for k in d["at"].values():
        q = blocks[k.split(".")[0]]["lots"][int(k.split(".")[1])]
        cx, cy = q[0] + q[2] / 2, q[1] + q[3] / 2
        assert not (x0 <= cx <= x1 and y0 <= cy <= y1), "a building stands in the letters"


def test_banner_letters_are_opaque_in_every_style():
    css = (ROOT / "alto" / "build" / "palace.py").read_text()
    rules = re.findall(r"[^{}\n]*\.pl-banner[^{}]*\{[^{}]*\}", css)
    assert rules
    for rule in rules:
        assert "rgba" not in rule, rule                      # a see-through fill showed the far bank's ground through the "e"


def test_the_towns_across_the_river_keep_their_names_and_stay_clear_of_the_letters(nyc):
    m = palace.unpack(nyc["data_z"])["map"]
    far0, b0 = palace_areas.hell_for(m, None)
    (q0,) = palace_areas.banners_layout(m, b0)
    cx, cy = (q0["box"][0] + q0["box"][2]) / 2, (q0["box"][1] + q0["box"][3]) / 2
    towns = [{"n": "Hoboken", "x": cx, "y": cy, "r": 3}, {"n": "Jersey City", "x": cx + 300, "y": cy + 200, "r": 3}]   # right where the word would stand
    m2 = dict(m, far=list(m["far"]) + towns)
    far, b = palace_areas.hell_for(m2, None)
    assert {"Hoboken", "Jersey City"} <= {f["n"] for f in far}                       # only the state's own name is dropped
    (q,) = palace_areas.banners_layout(m2, b)
    assert not [t["n"] for t in towns if _hits(q["box"], t["x"], t["y"], t["n"])]


def test_the_label_fitter_treats_the_letters_as_an_obstacle():
    """A neighbourhood or street name that would land on the giant letters is hidden by the fitter (text on text) -- on the desktop and the phone map."""
    src = (ROOT / "alto" / "build" / "palace.py").read_text()
    m = re.search(r"querySelectorAll\('([^']*\.pl-lmb \.lm-card[^']*)'\)", src)
    assert m and ".pl-banner" in m.group(1).split(",")


def test_tile_names_keep_off_the_letters():
    """The close-in neighbourhood names come from the tiles, not the fitter: a name whose text would stand on a banner's box is not drawn."""
    from alto.build import palace_tiles
    assert "bns.some" in palace_tiles.TILES_JS and "M0.banners" in palace_tiles.TILES_JS
