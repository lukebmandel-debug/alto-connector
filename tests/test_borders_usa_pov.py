"""The Atlas draws the borders as the US recognises them (Board L-1119-BORDERS): Natural Earth's USA point of view, 1:110m base tier and 1:50m continents."""
import glob
import gzip
import json
import os

import pytest

from alto.build import world_geo as wg, world_plan as wp

W = wg.DIR


def _tier(name):
    with gzip.open(os.path.join(W, name + ".json.gz")) as f:
        return json.load(f)


def _rings(tier):
    q = tier["q"]
    for cid, rs in tier["c"].items():
        for flat in rs:
            x, y, pts = flat[0], flat[1], [(flat[0] / q, flat[1] / q)]
            for i in range(2, len(flat), 2):
                x += flat[i]
                y += flat[i + 1]
                pts.append((x / q, y / q))
            yield cid, pts


def _inside(x, y, ring):
    c, j = False, len(ring) - 1
    for i in range(len(ring)):
        (xi, yi), (xj, yj) = ring[i], ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def _owner(tiers, lon, lat):
    x, y = wg.project(lon, lat)
    for t in tiers:
        for cid, ring in _rings(t):
            if _inside(x, y, ring) and abs(_area(ring)) > 0:
                return cid
    return None


def _area(p):
    return 0.5 * sum(p[i][0] * p[i - 1][1] - p[i - 1][0] * p[i][1] for i in range(len(p)))


BASE = _tier("base")
CONT = [_tier(os.path.basename(f)[:-8]) for f in sorted(glob.glob(os.path.join(W, "cont-*.json.gz")))]

# (place, lon, lat, the country that holds it): the disputed areas as the US recognises them, then the cases the USA file itself splits.
DISPUTED = [("Crimea (Simferopol)", 34.10, 44.95, "UKR"), ("Sevastopol area (Bakhchysarai)", 33.90, 44.75, "UKR"), ("Donetsk", 37.80, 48.00, "UKR"),
            ("Luhansk", 39.30, 48.57, "UKR"), ("Zaporizhzhia oblast (Melitopol)", 35.37, 46.84, "UKR"), ("Kherson oblast (Nova Kakhovka)", 33.37, 46.76, "UKR"),
            ("Abkhazia (Sukhumi)", 41.02, 43.00, "GEO"), ("South Ossetia (Tskhinvali)", 43.97, 42.22, "GEO"),
            ("Northern Cyprus (Kyrenia)", 33.32, 35.34, "CYP"), ("Transnistria (Tiraspol)", 29.63, 46.84, "MDA"),
            ("Somaliland (Hargeisa)", 44.06, 9.56, "SOM"), ("Kosovo (Pristina)", 21.17, 42.66, "KOS")]
SPLIT = [("Golan (Katzrin)", 35.69, 32.99), ("Kashmir (Srinagar)", 74.8, 34.08),
         ("Taiwan (Taipei)", 121.56, 25.04)]


@pytest.mark.parametrize("name,lon,lat,want", DISPUTED)
def test_disputed_areas_follow_the_us(name, lon, lat, want):
    assert _owner([BASE], lon, lat) == want, ("110m tier", name)
    assert _owner(CONT, lon, lat) == want, ("50m tier", name)


def test_split_cases_encoded_outcome():
    """What the USA file encodes, pinned: Golan Israel (the US recognises it since 2019), Kashmir and Taiwan as in the file. (Western Sahara is not
    the file's: the US holds it Moroccan since 10 Dec 2020, see test_western_sahara_is_morocco.)"""
    got = {n: _owner(CONT, lon, lat) for n, lon, lat in SPLIT}
    assert got == {"Golan (Katzrin)": "ISR", "Kashmir (Srinagar)": "IND", "Taiwan (Taipei)": "TWN"}, got


def test_countries_and_cities_follow():
    C = wg.gazetteer()["countries"]
    assert not {"SOL", "CYN", "KAS"} & set(C) and "KOS" in C and "UKR" in C
    for city in ("Simferopol", "Sevastopol", "Yalta"):
        assert wp.resolve(city + ", Ukraine")["c"] == "UKR", city
        assert wp._city("RUS", city) is None
    assert wp._city("SOM", "Hargeisa") and wp._city("CYP", "Kyrenia")
    assert wp.resolve("Somaliland")["c"] == "SOM" and wp.resolve("Northern Cyprus")["c"] == "CYP"


def test_province_files_have_no_crimea_under_russia():
    with gzip.open(os.path.join(W, "a1p-RUS.json.gz")) as f:
        assert "Crimea" not in [s[0] for s in json.load(f)["s"]]


def test_stored_timeline_with_an_old_country_code_keeps_its_places():
    """A world brief stored before this edition (country SOL / CYN) still validates and plans, under the country that holds the place now."""
    world = {"level": "country", "places": {"n1": {"c": "SOL", "s": "Woqooyi Galbeed", "city": "Hargeisa", "lon": 44.06, "lat": 9.56, "label": "Hargeisa, Somalia"},
                                              "n2": {"c": "RUS", "s": "Moskva", "city": "Moscow", "lon": 37.6, "lat": 55.75, "label": "Moscow, Russia"}}}
    wp.validate(world)
    fixed = wp._legacy(world)
    assert fixed["places"]["n1"]["c"] == "SOM" and fixed["places"]["n2"] == world["places"]["n2"] and world["places"]["n1"]["c"] == "SOL"


def test_country_names_stay_as_they_were():
    """The US edition names a few countries otherwise ("Dem. Rep. Korea"); the map and the name search keep the names they had, and a folded-in
    statelet (South Ossetia) does not rename its state (Georgia)."""
    C = wg.gazetteer()["countries"]
    assert (C["GEO"]["n"], C["KOR"]["n"], C["PRK"]["n"], C["COD"]["n"], C["UKR"]["n"]) == ("Georgia", "South Korea", "North Korea", "Dem. Rep. Congo", "Ukraine")


def test_western_sahara_is_morocco():
    """US_POSITION_MERGES: no SAH anywhere, Laayoune and Dakhla in Morocco, no line left inside Morocco where the border ran (27.67 N, 8.7 to 13.1 W) in either
    map tier, and a brief stored with SAH validates and plans as MAR."""
    assert "SAH" not in wg.gazetteer()["countries"] and all(c != "SAH" for c in BASE["c"]) and all(c != "SAH" for t in CONT for c in t["c"])
    assert wp._city("MAR", "Laayoune") and wp._city("MAR", "Ad Dakhla") and wp.resolve("Western Sahara")["c"] == "MAR"
    for tiers in ([BASE], CONT):
        assert _owner(tiers, -14.0, 24.0) == "MAR" and _owner(tiers, -13.2, 27.15) == "MAR"
        for lon in (-9.5, -10.5, -11.5, -12.5):                                              # a vertex or edge of any ring near the old border would be a leftover line
            x, y = wg.project(lon, 27.67)
            for t in tiers:
                for cid, ring in _rings(t):
                    if cid != "MAR":
                        continue
                    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                        dx, dy = x2 - x1, y2 - y1
                        u = 0 if not (dx or dy) else max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
                        assert ((x - x1 - u * dx) ** 2 + (y - y1 - u * dy) ** 2) ** .5 > 1.5, ("a MAR edge near the old Western Sahara border", lon)
    world = {"level": "country", "places": {"n1": {"c": "SAH", "s": "Laayoune-Sakia El Hamra", "city": "Laayoune", "lon": -13.2, "lat": 27.15, "label": "Laayoune"}}}
    wp.validate(world)
    assert wp._legacy(world)["places"]["n1"]["c"] == "MAR"


def _mid(ring):
    return sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)


def _in_kurils(pt):
    cs = [wg.project(lo, la) for lo in (145.2, 149.0) for la in (43.2, 45.6)]
    return min(c[0] for c in cs) <= pt[0] <= max(c[0] for c in cs) and min(c[1] for c in cs) <= pt[1] <= max(c[1] for c in cs)


def test_southern_kurils_are_japan():
    """US_POSITION_TRANSFERS (RUS -> JPN, a box round Iturup, Kunashir, Shikotan, Habomai): in both map tiers the islands' rings are Japan's and none is Russia's,
    and Urup, the first island north of the box, stays Russian. (The 1:50m and 1:110m files draw the three big islands; the Habomai islets are under their line.)"""
    for tiers, want in (([BASE], 2), (CONT, 3)):
        rings = [(cid, r) for t in tiers for cid, r in _rings(t) if _in_kurils(_mid(r))]
        assert sum(1 for cid, _ in rings if cid == "JPN") >= want and not [cid for cid, _ in rings if cid == "RUS"], [c for c, _ in rings]
    assert _owner(CONT, 147.8, 45.0) == "JPN" and _owner(CONT, 150.0, 45.9) == "RUS"


def test_southern_kurils_are_in_no_russian_province_and_are_hokkaido():
    for iso, ok in (("RUS", False), ("JPN", True)):
        with gzip.open(os.path.join(W, f"a1p-{iso}.json.gz")) as f:
            d = json.load(f)
        hit = [name for name, rs in d["s"] for flat in rs if _in_kurils((lambda pts: (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)))(
            list(_rings({"q": d["q"], "c": {name: [flat]}}))[0][1]))]
        assert bool(hit) == ok and (not ok or set(hit) == {"Hokkaido"}), (iso, hit)


def test_golan_is_israel_in_both_tiers():
    assert _owner([BASE], 35.75, 33.0) in ("ISR", None) and _owner(CONT, 35.69, 32.99) == "ISR"
