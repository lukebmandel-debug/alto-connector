"""Where the lattice meets a river (1.9.97): palace_banks.clip_streets cuts the streets at the band, tidy_streets then takes out what no
real river has (ticks, slivers along the bank, a thin cell open to the water, a loop round a bend, cells that touch nothing) and carries a
street that stopped short of the water on to the bank. Synthetic rivers, no network."""
import math

from alto.build import palace_banks as pb


def _slack(m, x, y):
    return pb._Riv(m, reach=2000).near(x, y)[0]


def _river(p, w=100):
    return {"n": "R", "w": w, "p": p}


def _mk(streets, river):
    return {"river": [river], "streets": [dict({"k": 1}, **s) for s in streets]}


def _by(m, n):
    return [s for s in m["streets"] if s.get("n") == n]


def _lattice(x0, x1, y0, y1, step=(240, 320)):
    """A lattice of long streets: the glue that keeps a test street from being an 'island' of its own."""
    out = []
    for i, x in enumerate(range(x0, x1 + 1, step[0])):
        out.append({"n": f"V{i}", "p": [x, y0, x, y1]})
    for j, y in enumerate(range(y0, y1 + 1, step[1])):
        out.append({"n": f"H{j}", "p": [x0, y, x1, y]})
    return out


def test_a_street_that_stops_short_of_the_water_ends_at_the_bank():
    river = _river([1000, 0, 1000, 4000])
    st = [{"n": "V", "p": [0, 0, 0, 4000]}, {"n": "V2", "p": [240, 0, 240, 4000]}, {"n": "V3", "p": [480, 0, 480, 4000]},
          {"n": "A", "p": [0, 800, 1000, 800]}, {"n": "B", "p": [0, 1200, 700, 1200]}, {"n": "C", "p": [0, 1600, 1900, 1600]}]
    m = _mk(st, river)
    pb.clip_streets(m)
    b = _by(m, "B")[0]
    assert b["p"][-2] > 880 and abs(_slack(m, b["p"][-2], b["p"][-1]) - pb.BANK_GAP) < 4          # B ran 250 px short: now it ends at the green strip's edge
    assert b["p"][-1] == 1200 and b["p"][1] == 1200                                                 # straight on, still the same street
    assert pb.LAST_STATS["extended"] == 1
    for n in ("A", "C"):                                                                            # the others were cut by the band as before
        for s in _by(m, n):
            for i in range(0, len(s["p"]), 2):
                assert _slack(m, s["p"][i], s["p"][i + 1]) >= pb.BANK_GAP - 2


def test_a_street_that_would_graze_the_bank_is_not_carried_on_to_it():
    river = _river([1000, 0, 1000, 4000])
    st = _lattice(0, 480, 0, 4000) + [{"n": "Z", "p": [240, 0, 800, 1538]},                          # 20 degrees off the bank's line: would meet it at a graze
                                      {"n": "G", "p": [240, 2000, 800, 2560]}]                       # 45 degrees: meets it well
    m = _mk(st, river)
    pb.clip_streets(m)
    assert _by(m, "Z")[0]["p"][-2:] == [800, 1538]
    g = _by(m, "G")[0]
    assert g["p"][-2] > 900 and abs(_slack(m, g["p"][-2], g["p"][-1]) - pb.BANK_GAP) < 4


def test_a_tick_and_a_thin_cell_next_to_the_bank_are_taken_out():
    river = _river([0, 3000, 2000, 3000])                                                           # a river along y = 3000: the band is 2950..3050
    st = _lattice(0, 1200, 0, 2240) + [{"n": "H2400", "p": [0, 2400, 1200, 2400]}]
    st += [{"n": "V1", "p": [200, 2400, 200, 3400]}, {"n": "V2", "p": [440, 2400, 440, 3400]},    # two streets run down to the water and on across it
           {"n": "THIN", "p": [200, 2840, 440, 2840]},                                              # the cell between them, cut thin by the band: a U open to the water
           {"n": "TICK", "p": [700, 2860, 700, 2916]}]                                              # a tick beside the bank
    m = _mk(st, river)
    pb.clip_streets(m)
    assert not _by(m, "THIN") and not _by(m, "TICK")
    for n in ("V1", "V2"):                                                                           # the streets themselves still arrive at the bank, square
        ps = _by(m, n)
        assert any(abs(s["p"][-1] - (3000 - 50 - pb.BANK_GAP)) < 3 for s in ps)
    assert pb.LAST_STATS["dropped"] >= 2


def test_a_street_that_meets_the_water_twice_in_a_short_run_is_dropped():
    river = _river([100, 0, 100, 1000, 500, 1000, 500, 0])                                          # a hairpin
    st = [{"n": "L", "p": [-300, -3000, -300, 3000]}, {"n": "R", "p": [900, -3000, 900, 3000]},
          {"n": "X", "p": [-300, 400, 900, 400]}]                                                    # across the hairpin's neck: bank to bank in 230 px
    m = _mk(st, river)
    pb.clip_streets(m)
    xs = _by(m, "X")
    assert len(xs) == 2 and all(s["p"][0] <= -300 + 1 or s["p"][-2] >= 900 - 1 for s in xs)         # only the two outer pieces, each still reaching its bank
    assert all(max(s["p"][0::2]) < 100 or min(s["p"][0::2]) > 500 for s in xs)


def test_streets_that_touch_nothing_are_islands_but_only_in_the_zone():
    river = _river([1000, 0, 1000, 8000])
    st = _lattice(0, 480, 0, 8000) + [{"n": "ISL", "p": [600, 3000, 600, 3250]},                      # a lone piece by the water, touching nothing
                                      {"n": "SOLO", "p": [-4000, 100, -3600, 100]}]                    # a lone piece far from any river: left alone
    m = _mk(st, river)
    pb.clip_streets(m)
    assert not _by(m, "ISL") and len(_by(m, "SOLO")) == 1


def test_a_bridge_is_never_touched_and_a_street_resting_on_it_stays():
    river = _river([1000, 0, 1000, 8000])
    st = _lattice(0, 480, 0, 8000) + [{"n": "BR", "o": 1, "p": [700, 2000, 1300, 2000]},
                                      {"n": "RAMP", "p": [700, 2000, 700, 2300]}]                      # a short street standing on the bridge's end
    m = _mk(st, river)
    pb.clip_streets(m)
    assert _by(m, "BR")[0]["p"] == [700, 2000, 1300, 2000]
    assert _by(m, "RAMP")


def test_a_long_street_along_the_bank_is_a_riverfront_street_a_short_one_is_a_sliver():
    river = _river([1000, 0, 1000, 8000])
    st = _lattice(0, 480, 0, 8000) + [{"n": "FRONT", "p": [900, 1000, 900, 4000]},                    # 3000 px beside the strip, 50 px from it
                                      {"n": "SLIV", "p": [900, 5000, 900, 5300]},
                                      {"n": "JOIN", "p": [480, 5000, 900, 5000]},
                                      {"n": "JOIN2", "p": [480, 5300, 900, 5300]},
                                      {"n": "JOIN3", "p": [480, 1000, 900, 1000]}, {"n": "JOIN4", "p": [480, 4000, 900, 4000]}]
    m = _mk(st, river)
    pb.clip_streets(m)
    assert _by(m, "FRONT") and not _by(m, "SLIV")


def test_a_page_that_has_no_river_or_no_streets_is_left_alone():
    assert pb.clip_streets({"streets": [{"n": "A", "p": [0, 0, 100, 0]}]}) == 0
    m = {"river": [_river([0, 0, 0, 1000])], "streets": []}
    assert pb.clip_streets(m) == 0 and m["streets"] == []


def test_a_closing_street_near_the_water_goes_but_a_through_street_is_never_broken():
    river = _river([0, 3000, 2000, 3000])
    base = _lattice(0, 1200, 0, 2240) + [{"n": "H2400", "p": [0, 2400, 1200, 2400]}]
    rails = [{"n": "V1", "p": [200, 2400, 200, 3400]}, {"n": "V2", "p": [440, 2400, 440, 3400]}]
    # a cell closed by a street that ends on its two rails, 190 px above the band's strip: a U open to the water
    m = _mk(base + rails + [{"n": "CLOSE", "p": [200, 2700, 440, 2700]}], river)
    pb.clip_streets(m)
    assert not _by(m, "CLOSE")
    # the same cross street running on both ways is a street of the city, not the cell's lid: it stays whole
    m = _mk(base + rails + [{"n": "THRU", "p": [0, 2700, 1200, 2700]}], river)
    pb.clip_streets(m)
    assert _by(m, "THRU") and _by(m, "THRU")[0]["p"] == [0, 2700, 1200, 2700]
