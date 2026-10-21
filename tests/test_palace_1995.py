"""1.9.95 (the lead's part): the river trail on one bank, streets that stop past the bank, the stadium / arena / Convention Center / City Hall art,
the X on the guns bar, the key's text size, hover intent on lines, the airport's request buttons, the back button named for the format."""
import math

from alto.build import palace, palace_banks, palace_landmarks, palace_skyline, palace_airport, key_toggle, search, palace_transit_js


def test_streets_stop_past_the_green_bank_not_at_the_water():
    assert palace_banks.BANK_GAP >= 33                                    # the bank strip is 32 px wide beyond the water's edge
    m = {"river": [{"n": "R", "w": 100, "p": [500, 0, 500, 1000]}], "streets": [{"n": "A", "k": 1, "p": [0, 300, 1000, 300]}]}
    palace_banks.clip_streets(m)
    ends = sorted(p[-2] for s in m["streets"] for p in [s["p"]] if p[-2] < 500) + sorted(p[0] for s in m["streets"] for p in [s["p"]] if p[0] > 500)
    assert ends[0] <= 500 - 50 - 33 and ends[1] >= 500 + 50 + 33


def test_river_trail_is_one_unbroken_line_on_the_one_real_bank(monkeypatch):
    # a straight river running north (+y down the page) with the real trail on its +side in three named pieces, one piece mapped to the wrong side
    monkeypatch.setattr(palace_banks, "_page", lambda m: (lambda x, y: (x, y)))
    river = {"n": "Schuylkill River", "w": 100, "p": [v for k in range(41) for v in (500, 4000 - 100 * k)]}
    # pieces east of the river line (x > 500); the river runs south->north, so its +side (x*-ty + y*tx >= 0) is the east bank
    trails = [{"n": "Schuylkill River Trail", "p": [560, 3600, 560, 2800, 560, 2400]},
              {"n": "Schuylkill Banks Boardwalk", "p": [440, 2300, 440, 2000]},          # this piece drawn on the WEST side: the real river says east
              {"n": "Schuylkill River Trail – Christian to Crescent", "p": [560, 1800, 560, 600]},
              {"n": "Schuylkill Trail Connector", "p": [560, 300, 700, 300]}]
    big = {"n": "Schuylkill River", "p": [v for k in range(41) for v in (500, 4000 - 100 * k)]}
    out = palace_banks.trails_on_page({"river": [river]}, trails, [big])
    assert len(out) == 1 and out[0]["n"] == "Schuylkill River Trail"
    xs = out[0]["p"][0::2]
    assert len(set(round(x) for x in xs)) == 1 and xs[0] > 500                       # one bank only, the east one
    ys = out[0]["p"][1::2]
    assert min(ys) <= 640 and max(ys) >= 3560                                         # from the first piece to the last, gaps bridged


def test_stadiums_arena_convention_center_and_city_hall_art():
    assert palace_landmarks.art_key({"n": "Lincoln Financial Field"}) == "lff"
    assert palace_landmarks.art_key({"n": "Citizens Bank Park"}) == "cbp"
    assert palace_landmarks.art_key({"n": "Xfinity Mobile Arena"}) == "arena"
    for k in ("lff", "cbp", "arena", "stad", "conv"):
        art = palace_landmarks.ART[k]
        assert art["svg"] and "NaN" not in art["svg"]
    assert 'clip-path="url(#pit-lff-{s})"' in palace_landmarks.ART["lff"]["svg"] and "lz-pitch" in palace_landmarks.ART["lff"]["svg"]
    assert "lz-dirt" in palace_landmarks.ART["cbp"]["svg"]                           # the diamond
    assert abs(palace_landmarks.ART["lff"]["fd"] - 285) < 1 and abs(palace_landmarks.ART["cbp"]["fd"] - 263) < 1
    ch = palace_landmarks.ART["city"]
    assert ch["sq"] > 1
    sx, sy = palace_skyline.scale_of(ch)
    box = [1000, 2000, 1480, 2640]
    x, y, w, h = palace_skyline.card(box, ch)
    assert abs(w - h) < 1e-6                                                          # a square card ...
    assert abs((x + w / 2) - 1240) < 1e-6 and abs((y + h / 2) - 2320) < 1e-6          # ... in the middle of its blocks, both ways
    js = palace_landmarks._JS
    assert "a.sq" in js


def test_ui_bits_of_the_lead():
    from alto.build import palace_fleet_fx, palace_fleet_css                  # (the guns bar moved into the hosted fleet script in 1.9.99)
    fx = palace_fleet_fx.__dict__.get("FLEET_JS") or "".join(str(v) for v in vars(palace_fleet_fx).values() if isinstance(v, str))
    assert "fx-x" in fx + str(vars(palace_fleet_css)) and "fxBar(false)" in fx
    assert "kp-sz" in key_toggle.KEY_JS and "--kp-s" in key_toggle.KEY_CSS
    assert "HOVER_DWELL" in palace_transit_js.TRANSIT_JS and "S.dwT" in palace_transit_js.TRANSIT_JS
    assert "pa-copy" in palace_airport.AIRPORT_JS and "copyText" in palace_airport.AIRPORT_JS and "execCommand('copy')" in palace_airport.AIRPORT_JS
    assert "Mind Palace" in search._FORMAT_NAME_JS and "building" in search._FORMAT_NAME_JS and "#desk-back .db-label" in search._FORMAT_NAME_JS


def test_a_ground_bigger_than_its_block_is_drawn_to_stand_inside_it_front_to_back():
    box = [15288, 26046, 15768, 26366]
    for k in ("lff", "cbp", "arena", "stad"):
        art = palace_landmarks.ART[k]
        assert art.get("fit")
        x, y, w, h = palace_skyline.card(box, art, {"box": box})
        assert y >= box[1] and y + h <= box[3] + 1e-6                                 # never over the card of the block behind or in front
    assert "a.fit" in palace_landmarks._JS
