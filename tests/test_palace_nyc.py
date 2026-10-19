"""New York in the Mind Palace: its landmark buildings have art of their own (not Philadelphia's), City Hall is New York's,
a page carries only the landmark art its city uses, and an airport's board links the user's palace of a city made since it
was set up. Offline: nothing here touches the network, Firebase or any ALTO_* setting."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import city_presets, palace, palace_landmarks as pl, palace_skyline as sky, palace_towers as pt  # noqa: E402

NYC_TOWERS = {"esb": ("Empire State Building", 443, 102), "owtc": ("One WTC", 541, 94), "chry": ("Chrysler Building", 319, 77),
              "wool": ("Woolworth Building", 241, 57), "flat": ("Flatiron Building", 87, 22), "ovan": ("One Vanderbilt", 427, 73),
              "rock": ("30 Rock", 259, 70), "muni": ("Municipal Building", 177, 40), "p432": ("432 Park Avenue", 426, 85), "boa": ("Bank of America Tower", 366, 55)}


@pytest.mark.parametrize("key,spec", NYC_TOWERS.items())
def test_each_new_york_tower_has_its_own_art_at_its_real_height(key, spec):
    name, hm, floors = spec
    assert pl.art_key({"n": name}) == key
    assert pl.ART[key]["hm"] == hm                      # drawn to its real height, at the one scale every building shares
    assert pt.FLOORS[key] == floors and pt.tower_key(name) == key
    assert pl.ART[key]["svg"] and key in json.loads(re.search(r"var TALL=(\[.*?\]), S=", pl.LANDMARK_JS).group(1))


def test_new_york_city_hall_is_not_philadelphias():
    assert pl.art_key({"n": "City Hall", "art": "nych"}) == "nych"
    assert pl.art_key({"n": "New York City Hall"}) == "nych"
    assert pl.art_key({"n": "Philadelphia City Hall"}) == "city" and pl.art_key({"n": "City Hall"}) == "city"
    assert pl.art_key({"n": "Boston City Hall"}) == "gen"            # nobody else's City Hall wears Philadelphia's
    assert pl.ART["nych"]["svg"] != pl.ART["city"]["svg"] and pl.ART["nych"]["hm"] < 60 < pl.ART["city"]["hm"]
    ch = [b for b in city_presets.buildings_for(city_presets.get("New York City")) if b["name"] == "New York City Hall"][0]
    assert ch["art"] == "nych"                                       # the preset's own art reaches the landmark record
    assert sky.art_hints(ch) == {"art": "nych"}


@pytest.mark.parametrize("name,key", [("Grand Central", "gct"), ("Grand Central Terminal", "gct"), ("Penn Station", "penn"),
                                      ("Pennsylvania Station", "penn"), ("United Nations", "un"),
                                      ("Penn Center Suburban Station", "sub"), ("30th Street Station", "stn")])
def test_the_low_landmarks_and_philadelphias_neighbours_keep_their_own_art(name, key):
    assert pl.art_key({"n": name}) == key


def test_a_page_carries_only_the_art_its_city_uses():
    m = {"landmarks": [{"n": "Empire State Building"}, {"n": "City Hall", "art": "nych"}, {"n": "Grand Central"}]}
    js = pl.trim_js(pl.LANDMARK_JS, m)
    art = json.loads(re.search(r"var ART=(\{.*?\}), GRAD=", js, re.S).group(1))
    assert {"esb", "nych", "gct", "gen"} <= set(art)
    assert "city" not in art and "lff" not in art and "cbp" not in art and any(k.startswith("g-") for k in art) and any(k.startswith("ct-") for k in art)
    assert art["esb"] == pl.ART["esb"]                               # the same bytes whatever else is dropped
    assert len(js) < len(pl.LANDMARK_JS) - 40000
    assert pl.trim_js(pl.LANDMARK_JS, {}) != "" and pl.trim_js("no art here", m) == "no art here"


def test_philadelphias_page_keeps_its_own_art():
    m = {"landmarks": [{"n": "City Hall"}, {"n": "Independence Hall"}, {"n": "Lincoln Financial Field"}]}
    art = json.loads(re.search(r"var ART=(\{.*?\}), GRAD=", pl.trim_js(pl.LANDMARK_JS, m), re.S).group(1))
    assert {"city", "ind", "lff"} <= set(art) and "esb" not in art


# ── the airport's board ─────────────────────────────────────────────────────
class _Store:
    def __init__(self, docs):
        self.docs, self.puts = docs, []

    def list_timelines(self, uid):
        return [{"timeline_id": t} for t in self.docs]

    def get_timeline(self, uid, tid):
        return self.docs.get(tid)

    def put_timeline(self, uid, tid, doc):
        self.puts.append(tid)
        self.docs[tid] = doc


def _phl(dests):
    return {"brief": {"palace": {"place": "Philadelphia", "portals": [
        {"id": "portal1", "name": "Philadelphia International Airport", "kind": "airport", "stations": ["X"], "destinations": dests}]}}}


@pytest.fixture
def mcp(monkeypatch):
    pytest.importorskip("mcp")
    from alto import mcp_server as ms
    monkeypatch.setattr(ms, "uid", lambda: "u1")
    return ms


def _board(doc):
    return doc["brief"]["palace"]["portals"][0]["destinations"]


def test_a_palace_made_after_the_board_links_its_city(mcp, monkeypatch):
    torts = {"private_key": "k123", "brief": {"palace": {"place": "New York City", "data_z": "x"}}}
    st = _Store({"civ-pro-palace": _phl([{"city": "New York City", "code": "JFK", "preset": True}, {"city": "Boston", "code": "BOS", "preset": True}]),
                 "torts-palace": torts})
    monkeypatch.setattr(mcp, "get_store", lambda: st)
    doc = mcp._refresh_portal_destinations(st.docs["civ-pro-palace"], "civ-pro-palace")
    nyc = _board(doc)[0]
    assert nyc["city"] == "New York City" and nyc["timeline"] == "torts-palace" and nyc["url"] == "../k123/" and "preset" not in nyc
    assert _board(doc)[1] == {"city": "Boston", "code": "BOS", "preset": True}      # the rest of the board is untouched
    assert st.puts == ["civ-pro-palace"]


def test_a_palace_not_on_the_board_is_added_first_and_a_linked_board_asks_for_nothing(mcp, monkeypatch):
    st = _Store({"civ-pro-palace": _phl([{"city": "Boston", "code": "BOS", "preset": True}]),
                 "chi": {"private_key": "kc", "brief": {"palace": {"place": "Chicago", "data_z": "x"}}}})
    monkeypatch.setattr(mcp, "get_store", lambda: st)
    doc = mcp._refresh_portal_destinations(st.docs["civ-pro-palace"], "civ-pro-palace")
    assert [d["city"] for d in _board(doc)] == ["Chicago", "Boston"] and _board(doc)[0]["timeline"] == "chi"
    linked = _phl([{"city": "Chicago", "code": "ORD", "timeline": "chi", "url": "../kc/"}])
    calls = []
    monkeypatch.setattr(mcp, "_own_palaces", lambda *a: calls.append(a) or [])
    assert mcp._refresh_portal_destinations(linked, "civ-pro-palace") is linked and calls == []
    assert mcp._refresh_portal_destinations({"brief": {"palace": {"portals": []}}}, "t") == {"brief": {"palace": {"portals": []}}}


def test_a_board_with_nothing_new_is_not_stored_again(mcp, monkeypatch):
    st = _Store({"civ-pro-palace": _phl([{"city": "Boston", "code": "BOS", "preset": True}])})
    monkeypatch.setattr(mcp, "get_store", lambda: st)
    mcp._refresh_portal_destinations(st.docs["civ-pro-palace"], "civ-pro-palace")
    assert st.puts == []
