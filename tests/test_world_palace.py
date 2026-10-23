"""The World Palace end to end (no browser): geodata, place names, the memory route, the capital rule, the brief, the page, hosting, the tool,
the homepage picker, the guide. Luke's design, 2026-10-22 (the CEO notes' world-palace/SPEC.md)."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import mcp_server as srv  # noqa: E402
from alto.build import palace_assets, palace_world as pw, world_geo as wg, world_plan as wp  # noqa: E402
from alto.build.brief import BriefError, validate_brief, world_view  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.cloud.meta import fmt_of  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

GUIDE = (ROOT / "alto" / "interview_guide.md").read_text(encoding="utf-8")
HOME = (ROOT / "engine" / "home_template.html").read_text(encoding="utf-8")

# two units: the first an outline's unit hub over four concepts (one with cards under it), the second three plain top cards
NODES = [{"id": "hub", "act": 0, "title": "Jurisdiction", "tag": "", "desc": "d"},
         {"id": "pj", "act": 0, "parent": "hub", "title": "Pennoyer v. Neff", "tag": "", "desc": "d"},
         {"id": "pj1", "act": 0, "parent": "pj", "title": "Presence", "tag": "", "desc": "d"},
         {"id": "pj2", "act": 0, "parent": "pj", "title": "Consent", "tag": "", "desc": "d"},
         {"id": "ms", "act": 0, "parent": "hub", "title": "Minimum contacts", "tag": "", "desc": "d"},
         {"id": "gj", "act": 0, "parent": "hub", "title": "General jurisdiction", "tag": "", "desc": "d"},
         {"id": "sj", "act": 0, "parent": "hub", "title": "Specific jurisdiction", "tag": "", "desc": "d"},
         {"id": "erie", "act": 1, "title": "Erie & Co", "tag": "", "desc": "d"},
         {"id": "erie1", "act": 1, "parent": "erie", "title": "Rules of Decision Act", "tag": "", "desc": "d"},
         {"id": "hanna", "act": 1, "title": "Hanna", "tag": "", "desc": "d"},
         {"id": "byrd", "act": 1, "title": "Byrd", "tag": "", "desc": "d"}]


def brief(**kw):
    b = {"title": "Civ Pro", "timeline_id": "civpro", "mode": "palace", "palace_view": "world", "columns": 5, "node_noun": "Concept",
         "period_noun": "Unit", "acts": [{"label": "Personal Jurisdiction", "color": "#5b6cff"}, {"label": "Erie", "color": "#9b5de5"}]}
    b.update(kw)
    return b


def loaded(**kw):
    return load_brief({"brief": brief(**kw), "nodes": json.loads(json.dumps(NODES))})


def built(**kw):
    b, ns, cs = loaded(**kw)
    return build_timeline(b, ns, cs)


def data_of(html):
    return json.loads(re.search(r"window\._ALTO_WORLD=(\{.*?\});", html).group(1).replace("<\\/", "</"))


# ── geodata ──────────────────────────────────────────────────────────────────

def test_equal_earth_puts_the_world_in_2000_units():
    assert wg.project(0, 0) == (0.0, -0.0) or wg.project(0, 0) == (0.0, 0.0)
    assert abs(wg.project(180, 0)[0] - 1000) < 1e-6 and abs(wg.project(-180, 0)[0] + 1000) < 1e-6
    assert wg.project(0, 60)[1] < 0 < wg.project(0, -60)[1]                  # north is up
    assert abs(wg.project(10, 40)[0] + wg.project(-10, 40)[0]) < 1e-9


def test_the_map_is_hosted_tiers_named_by_their_hash():
    files = dict(wg.hosted())
    names = sorted(files)
    assert any(n.startswith("base-") for n in names) and sum(n.startswith("cont-") for n in names) >= 6
    assert any(n.startswith("a1-USA-") for n in names) and not any(n.startswith("gazetteer") for n in names)
    for n in files:
        assert re.fullmatch(r"(base|cont-[a-z-]+|a1-[A-Z]{3})-[0-9a-f]{10}\.json", n), n
    base = json.loads(files[next(n for n in names if n.startswith("base-"))])
    assert {"USA", "FRA", "DEU", "BRA", "JPN"} <= set(base["c"]) and base["q"] == 10
    assert len(files[next(n for n in names if n.startswith("base-"))]) < 120_000           # the whole world, at a glance, is small
    m = wg.manifest()
    assert m["base"].startswith("/world/base-") and m["cont"]["europe"].startswith("/world/cont-europe-") and m["a1"]["USA"]


def test_the_renderer_and_every_tier_are_published():
    got = {(f, n) for f, n, _ in palace_assets.assets()}
    assert ("world", pw.WORLD_PATH.rsplit("/", 1)[1]) in got
    for n, _ in wg.hosted():
        assert ("world", n) in got
    ct, text = palace_assets.find(wg.manifest()["base"])
    assert ct.startswith("application/json") and json.loads(text)["c"]
    ct, js = palace_assets.find(pw.WORLD_PATH)
    assert ct.startswith("text/javascript") and "window.AltoWorld" in js and wg.manifest()["base"] in js


# ── place names ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,country,state,city", [
    ("USA", "USA", "", ""), ("United States", "USA", "", ""), ("France", "FRA", "", ""), ("Netherlands", "NLD", "", ""),
    ("UK", "GBR", "", ""), ("Oregon", "USA", "Oregon", ""), ("Portland, Oregon", "USA", "Oregon", "Portland"),
    ("New York", "USA", "New York", "New York"), ("Washington, D.C.", "USA", "District of Columbia", "Washington, D.C."),
    ("Paris", "FRA", "Île-de-France", "Paris"), ("England", "GBR", "England", ""),
])
def test_a_place_is_a_country_a_state_or_a_city(text, country, state, city):
    p = wp.resolve(text)
    assert (p["c"], p["s"], p["city"]) == (country, state, city)


def test_a_country_pin_is_its_seat_of_government():
    caps = {c: wg.gazetteer()["countries"][c]["cap"][0] for c in ("USA", "ZAF", "NLD", "CHE", "BOL", "CIV")}
    assert caps == {"USA": "Washington, D.C.", "ZAF": "Pretoria", "NLD": "Amsterdam", "CHE": "Bern", "BOL": "La Paz", "CIV": "Abidjan"}


def test_an_unknown_place_is_refused_with_suggestions():
    with pytest.raises(wp.PlaceError) as e:
        wp.resolve("Germny")
    assert "Germany" in e.value.suggestions
    with pytest.raises(wp.PlaceError):
        wp.resolve("")


# ── the route and the pins ───────────────────────────────────────────────────

def test_the_route_gives_each_unit_a_region_round_the_world():
    b, ns, _ = loaded()
    p = wp.plan(b, ns)
    assert [u["reg"] for u in p["units"]] == [["North America"], ["South America"]]
    assert p["units"][0]["hub"] == "hub" and p["units"][0]["tops"] == ["pj", "ms", "gj", "sj"]      # the hub's concepts are the countries
    assert "hub" not in p["places"] and p["units"][1]["tops"] == ["erie", "hanna", "byrd"]
    countries = [p["places"][t]["c"] for u in p["units"] for t in u["tops"]]
    assert len(set(countries)) == len(countries)                                                    # nobody shares while there is room
    assert set(countries[:4]) == {"USA", "CAN", "MEX", "GRL"}                                      # the region's largest countries
    assert p["cl"] == {"pj": ["pj2"]}                                    # cards under a country go on its cities; Greenland has one to give
    assert wp.plan(*loaded()[:2]) == p                                                              # deterministic


def test_a_lone_state_pins_at_the_capital_two_states_stand_on_their_own():
    one = {"pj": {**wp.resolve("Oregon"), "r": 1}}
    b, ns, _ = loaded(world={"places": one})
    p = wp.plan(b, ns)
    dc = wg.project(-77.0114, 38.9015)
    assert p["places"]["pj"]["c"] == "USA" and abs(p["places"]["pj"]["x"] - dc[0]) < .05 and p["places"]["pj"]["r"] == 1
    assert p["places"]["pj"]["named"].startswith("Oregon") and p["multi"] == []
    two = {**one, "ms": {**wp.resolve("Texas"), "r": 1}}
    b, ns, _ = loaded(world={"places": two})
    p = wp.plan(b, ns)
    assert p["multi"] == ["USA"] and p["places"]["pj"]["k"] == "sub" and p["places"]["pj"]["label"].startswith("Oregon")
    assert abs(p["places"]["ms"]["x"] - wg.project(-97.7447, 30.2689)[0]) < .05


def test_the_notes_pull_a_unit_to_their_region_and_the_user_may_name_one():
    b, ns, _ = loaded(world={"places": {"erie": wp.resolve("Germany")}})
    assert wp.plan(b, ns)["units"][1]["reg"] == ["Western Europe"]
    b, ns, _ = loaded(world={"regions": ["", "East Asia"]})
    p = wp.plan(b, ns)
    assert p["units"][1]["reg"] == ["East and Southeast Asia"] and p["places"]["erie"]["c"] in ("CHN", "IDN", "MNG")


def test_the_cards_under_a_country_stand_on_its_major_cities_largest_first():
    # Luke, 2026-10-23: "Automatically assign major cities to other nodes within a country"
    b, ns, _ = loaded(world={"places": {"erie": wp.resolve("Peru")}})
    p = wp.plan(b, ns)
    assert p["places"]["erie1"]["k"] == "city" and p["places"]["erie1"]["label"] == "Arequipa"      # Lima is the capital, Callao beside it
    assert p["units"][1]["stops"][:2] == ["erie", "erie1"] and "erie" not in p["cl"]
    assert p["places"]["pj1"]["label"] == "Qaanaaq" and p["cl"]["pj"] == ["pj2"]                   # the cities run out: the rest cluster
    assert not p["multi"]                                                                           # (the route's own cities draw no state lines)


def test_two_concepts_in_one_country_never_share_a_city():
    b, ns, _ = loaded(world={"places": {"pj": wp.resolve("Oregon"), "ms": wp.resolve("Texas")}})
    p = wp.plan(b, ns)
    towns = [q["label"] for q in p["places"].values() if q["k"] == "city"]
    assert len(towns) == len(set(towns)) and p["places"]["pj1"]["c"] == "USA" and p["places"]["pj2"]["c"] == "USA"


def test_the_cluster_and_deep_levels():
    b, ns, _ = loaded(world={"level": "cluster"})
    p = wp.plan(b, ns)
    assert p["cl"] == {"pj": ["pj1", "pj2"], "erie": ["erie1"]} and not any(q["k"] == "city" for q in p["places"].values())
    assert wp.plan(*loaded(world={"level": "deep"})[:2])["places"] == wp.plan(*loaded()[:2])["places"]     # "deep" is the default's old name


def test_the_renderer_enlarges_hops_and_follows_the_engine():
    js = pw.WORLD_ASSET
    for seam in ("A.hop=function", "wp-enl", "giveBack()", "search-flash", "ent-dimmed", "CONNECTIONS", "alto-editing", "_featuredNodeId"):
        assert seam in js, seam
    assert "html.detail-open #wpal-root{visibility:hidden" in js                    # a card's page never shows the map through it
    assert "html.alto-bg:not(.alto-bg-map) #wpal-root{background:none;}" in js       # a picked background is the sea
    assert "html.alto-retro #wpal-root .wp-enl .node-card" in js                     # the enlarged card in Retro
    assert "#wpal-root .wp-pin.n{width:auto" in js                                   # a number never spills out of its pin
    assert "window._altoKeyToggle(key,'alto-world-key'" in js and "window._altoKeyToggle=function" in js     # Alto's floating key toggle
    from alto.build import retro
    assert "X #wpal-root .wp-btn.r:not(#_){border-radius:0;}" in retro.FORMAT_CSS                  # round controls square in Retro (1.9.160)


# ── the brief ────────────────────────────────────────────────────────────────

def test_world_is_a_palace_view_and_its_places_need_it():
    b, ns, _ = loaded()
    assert world_view(b) and validate_brief(b) is not None
    b.palace_view, b.world = "city", {"level": "country"}
    with pytest.raises(BriefError, match="palace_view 'world'"):
        validate_brief(b)
    b.palace_view, b.world = "world", {"level": "global"}
    with pytest.raises(BriefError, match="world.level"):
        validate_brief(b)
    b.world = {"places": {"pj": {"c": "XXX"}}}
    with pytest.raises(BriefError, match="not a resolved place"):
        validate_brief(b)
    b.world = {"regions": ["Atlantis"]}
    with pytest.raises(BriefError, match="not a region"):
        validate_brief(b)


# ── the page ─────────────────────────────────────────────────────────────────

def test_the_page_carries_a_loader_and_the_places_not_the_map():
    html, report = built(world={"places": {"pj": {**wp.resolve("Oregon"), "r": 1}}})
    assert "window._ALTO_WORLD=" in html and "function altoLoadWorld()" in html and pw.WORLD_PATH in html
    assert "window._altoPalace=function" not in html and "wp-arc" not in html                 # no city, and the renderer is hosted
    assert "window._ALTO_PALACE={" in html                                                     # the numbers still come from the palace stub
    d = data_of(html)
    assert d["u"][0]["hub"] == "hub" and d["nodes"]["pj"]["r"] == 1 and d["nodes"]["pj"]["n"] == "1.1-1"
    assert d["nodes"]["erie"]["t"] in ("Erie & Co", "Erie &amp; Co") and d["acts"][1] == {"n": "Erie", "c": "#9b5de5"}
    assert d["nodes"]["pj1"]["k"] == "city" and d["nodes"]["pj1"]["c"] == "USA" and "x" in d["nodes"]["pj1"] and d["names"]["USA"]
    assert fmt_of(html) == "world" and report["warnings"] is not None


def test_the_page_grows_by_a_few_kilobytes_only():
    plain, _ = built(mode="linear", palace_view="city")
    html, _ = built()
    assert 0 < len(html) - len(plain) < 14_000, len(html) - len(plain)
    assert len(html) < len(built(palace_view="city")[0])


def test_the_city_and_building_pages_are_untouched_by_the_world_branch():
    city, _ = built(palace_view="city")
    assert "_ALTO_WORLD" not in city and "altoLoadWorld" not in city and "wpal" not in city


# ── the tool ─────────────────────────────────────────────────────────────────

@pytest.fixture
def local_store(tmp_path):
    srv.set_store(LocalStore(tmp_path))
    yield
    srv.set_store(None)


def _timeline():
    pid = srv.create_project("Civ Pro", "x", "studying")["project_id"]
    r = srv.create_timeline(pid, {k: v for k, v in brief().items() if k != "timeline_id"})
    assert "error" not in r, r
    tid = r["timeline_id"]
    srv.record_materials_consent(tid, [{"name": "n.pdf", "kind": "notes"}], True)
    assert "error" not in srv.add_nodes(tid, json.loads(json.dumps(NODES)))
    return tid


def test_set_up_world_places_reports_and_builds(local_store):
    tid = _timeline()
    r = srv.set_up_world(tid, places=[{"node": "pj", "place": "Oregon", "notes": True}])
    assert r["ok"] and r["units"][0]["regions"] == ["North America"] and r["units"][0]["region_card"] == "Jurisdiction"
    stop = r["units"][0]["stops"][0]
    assert stop["node"] == "pj" and stop["place"] == "United States" and stop["from_notes"]
    r = srv.set_up_world(tid, places=[{"node": "ms", "place": "Texas"}], regions=["", "Western Europe"])
    assert r["own_pins"] == ["United States"] and r["units"][1]["regions"] == ["Western Europe"]
    assert srv.set_up_world(tid, clear=["ms"])["own_pins"] == []
    doc = srv.get_store().get_timeline(srv.uid(), tid)
    assert doc["brief"]["world"]["places"]["pj"]["r"] == 1 and "ms" not in doc["brief"]["world"]["places"]
    assert "error" not in srv.build_timeline(tid)


def test_set_up_world_refuses_clearly(local_store):
    tid = _timeline()
    r = srv.set_up_world(tid, places=[{"node": "pj", "place": "Narnia"}, {"node": "nope", "place": "France"}])
    assert r["error"] == "unknown_places" and len(r["problems"]) == 2
    assert srv.set_up_world(tid, regions=["Atlantis"])["error"] == "invalid_region"
    assert srv.set_up_world(tid, level="galactic")["error"] == "invalid_level"


# ── the homepage, the guide ─────────────────────────────────────────────────

def test_the_homepage_offers_the_world_and_sends_the_user_to_claude():
    assert 'data-mode="world"' in HOME and "World</button>" in HOME and 'data-for="world"' in HOME
    assert "palace_view \\'world\\'" in HOME and "set_up_world" in HOME
    assert "ntModes.palace === 'world' ? 'world'" in HOME and "ntKind === 'world'" in HOME
    assert (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8") == HOME
    assert "world" not in __import__("alto.build.starter", fromlist=["KINDS"]).KINDS     # the world needs Claude, never a browser starter


def test_the_guide_says_places_come_from_the_notes():
    assert "### §D-World. World Palace" in GUIDE and "set_up_world" in GUIDE
    assert "Do not guess a place from a subject" in " ".join(GUIDE.split())
    assert "Washington, D.C." in GUIDE and "6f. World Palace only" in GUIDE
