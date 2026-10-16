"""City engine v2: line selection and layout on real Philadelphia data (design 1.4 hand-specified domains):
the seam A-west|C on Baltimore Ave and A-east|B on Kensington Ave."""
import gzip
import json
import math
from pathlib import Path

import pytest

from alto.build import city_lines as cl
from alto.build import city_seams as cs
from alto.build.city_types import Domain

FIX = Path(__file__).resolve().parent / "fixtures" / "cities"
TH = {"A": 9.3, "B": 55.8, "C": 46.8}            # measured modes (design 1.4)
# design 1.4 polygons (lat, lon)
B_LL = [(39.969, -75.114), (39.962, -75.128), (39.985, -75.128), (40.003, -75.102), (40.005, -75.090),
        (39.998, -75.083), (39.983, -75.083)]
C_LL = [(39.904, -75.233), (39.907, -75.245), (39.940, -75.245), (39.945, -75.231), (39.945, -75.210),
        (39.933, -75.210), (39.925, -75.219), (39.906, -75.226)]


def load(name):
    p = FIX / ("%s.json.gz" % name)
    if not p.exists():
        pytest.skip("no fixture %s" % p.name)
    return json.load(gzip.open(p, "rt"))


def px(m, lat, lon):
    s, w, n, e = m["bbox"]
    return ((lon - w) / (e - w) * m["W"], (n - lat) / (n - s) * m["H"])


def _cd(a, b):
    d = abs(a - b) % 90
    return min(d, 90 - d)


def phil_domains(m, band=450.0):
    """A-east (east of the Schuylkill), A-west, B, C. The small domains own what lies in their design-1.4 ring;
    within `band` px of a ring a piece goes to whichever side's axes it fits (so the numbered streets switch at
    their bend, not at the coarse ring)."""
    riv = sorted(p for r in m.get("rivers", []) if "Schuylkill" in (r.get("n") or "")
                 for p in zip(r["p"][0::2], r["p"][1::2]))
    by = {}
    for x, y in riv:
        by.setdefault(int(y // 200), []).append(x)
    ks = sorted(by)

    def rx(y):
        k = min(ks, key=lambda q: abs(q - y / 200))
        v = sorted(by[k])
        return v[len(v) // 2]
    W, H = m["W"], m["H"]
    ys = [y * 200.0 for y in range(0, int(H // 200) + 1)]
    east = [(rx(y), y) for y in ys] + [(W, H), (W, 0.0)]
    # A-west: West Philadelphia between Market St (39.962) and C, out to the Schuylkill (not the NW, not Eastwick)
    y_n, y_s = px(m, 39.962, -75.2)[1], px(m, 39.925, -75.2)[1]
    west = [px(m, *p) for p in ((39.962, -75.245), (39.940, -75.245), (39.945, -75.231), (39.945, -75.210),
                                (39.933, -75.210), (39.925, -75.219))]
    west += [(rx(y), y) for y in sorted((y for y in ys if y_n < y < y_s), reverse=True)] + [(rx(y_n), y_n)]
    west = [west[0]] + west[1:6] + [(rx(y_s), y_s)] + west[6:]
    rings = {"B": [px(m, *p) for p in B_LL], "C": [px(m, *p) for p in C_LL], "A-west": west, "A-east": east}
    side = {"B": "A-east", "C": "A-west"}
    own = {k: [] for k in rings}
    for st in m["streets"]:
        pts = list(zip(st["p"][0::2], st["p"][1::2]))
        cur, co = [], None
        for a, b in zip(pts, pts[1:]):
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            big = "A-west" if mid[0] < rx(mid[1]) else "A-east"
            small = "C" if big == "A-west" else "B"
            cand = [k for k in (small, big) if cs._inside(mid, rings[k])]
            near = [k for k in (small, big) if k not in cand and cs._ring_d(mid, rings[k]) < band]
            o = cand[0] if cand else None
            if (cand or near) and len(set(cand + near)) > 1 and math.dist(a, b) > 15:
                ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
                fs, fb = _cd(ang, TH[small[0]]), _cd(ang, TH["A"])
                if min(fs, fb) < 8:
                    o = small if fs < fb else big
            if o != co and cur:
                if co:
                    own[co].append({**st, "p": [v for q in cur for v in q]})
                cur = []
            if not cur:
                cur = [a]
            cur.append(b); co = o
        if cur and co:
            own[co].append({**st, "p": [v for q in cur for v in q]})
    ids = {"A-east": 0, "A-west": 1, "B": 2, "C": 3}
    return [Domain(id=ids[k], kind="grid", theta=math.radians(TH[k[0]]), poly=rings[k], streets=own[k]) for k in ids]


@pytest.fixture(scope="module")
def phil():
    m = load("philadelphia")
    doms = phil_domains(m)
    sl, lines, lay = cs.plan(doms, majors=m.get("majors") or (), aspect=False)   # E3's fixed 240 x 170 block
    return m, doms, sl, lines, lay


def _seam(sl, a, b):
    return next(s for s in sl if (s.a, s.b) == (a, b))


def test_baltimore_seam(phil):
    m, doms, sl, lines, lay = phil
    sm = _seam(sl, 1, 3)
    q = cs.seam_quality(lay, sm)
    assert sm.kind == "hinge" and sm.avenue == "Baltimore Avenue"
    assert q["pairs"] >= 7 and {"46th Street", "50th Street", "52nd Street"} <= set(q["names"])
    assert q["phi_true"] == pytest.approx(-17.6, abs=2.0)               # the real seam angle (rel A)
    assert q["err_true"] <= 4.5 and -26.3 <= sm.phi <= -15.0            # drawn ANGLED, between real and fold
    assert abs(sm.ratio - 1) <= cs.R_TOL + 1e-9
    assert q["report"]["hinge_resid_px"] < 1e-6 and q["order_inversions"] == 0
    assert sm.info["tilt"] == pytest.approx(37.5, abs=1.0)
    assert q["kinks"]["max"] <= 2.0 and q["near_seam"]["median"] <= 1.0
    assert doms[3].roles == "hv"                                         # C's rows (the numbered streets) get CW


def test_kensington_seam(phil):
    m, doms, sl, lines, lay = phil
    sm = _seam(sl, 0, 2)
    q = cs.seam_quality(lay, sm)
    assert sm.kind == "hinge" and sm.avenue == "Kensington Avenue"
    assert abs(sm.info["tilt"]) == 45.0 and q["pairs"] >= 8
    assert q["phi_true"] == pytest.approx(-44.8, abs=1.5) and q["err_true"] <= 5.0
    assert abs(sm.ratio - 1) <= cs.R_TOL + 1e-9 and q["order_inversions"] == 0
    assert q["report"]["hinge_resid_px"] < 1e-6


def test_lines_only_from_own_streets(phil):
    m, doms, sl, lines, lay = phil
    names_c = {l["n"] for l in lines[3]["v"] + lines[3]["h"] if l.get("n")}
    names_aw = {l["n"] for l in lines[1]["v"] + lines[1]["h"] if l.get("n")}
    assert "Woodland Avenue" in names_c and "Market Street" in names_aw
    assert "Market Street" not in names_c
    # every selected line of a domain comes from that domain's streets
    for d in doms:
        own = {cl.norm(s["n"]) for s in d.streets if s.get("n")}
        assert all(l["n"] in own for o in "vh" for l in lines[d.id][o] if l.get("n"))
    # even real spacing: median kept gap within 15% of the target in every family of every domain
    for d in doms:
        for o in "vh":
            assert 0.85 <= lines[d.id]["stats"][o]["gap_median"] <= 1.15, (d.id, o, lines[d.id]["stats"][o])


def test_regions_do_not_overlap_at_the_seam(phil):
    m, doms, sl, lines, lay = phil
    sm = _seam(sl, 1, 3)
    for h in sm.hinge:                    # just off the seam on C's side is C's, not A-west's
        at = h["at"]
        hp = sm.info["parts"][0]["page"] if sm.info["parts"][0]["kind"] == "hinge" else \
            next(p["page"] for p in sm.info["parts"] if p["kind"] == "hinge")
        cpg = lay.maps[1](*cl.centroid(doms[3].poly))
        sg = 1 if cs._dot(hp["n"], cpg) - hp["c"] > 0 else -1
        p = (at[0] + sg * 30 * hp["n"][0], at[1] + sg * 30 * hp["n"][1])
        tiny = [(p[0] - 1, p[1] - 1), (p[0] + 1, p[1] - 1), (p[0] + 1, p[1] + 1), (p[0] - 1, p[1] + 1)]
        assert lay.clip(3, tiny) and not lay.clip(1, tiny)


def test_select_spacing_dp():
    # dense optional rows (70 m) thin to the target (126 m); must lines are kept even when close
    streets = [{"n": "Row %d" % i, "k": 4, "p": [0, 1000 + 70 * i, 3000, 1000 + 70 * i]} for i in range(30)]
    streets += [{"n": "%dth Street" % (10 + i), "k": 4, "p": [500 + 178 * i, 900, 500 + 178 * i, 3200]} for i in range(12)]
    d = Domain(id=0, kind="grid", theta=0.0, poly=[(0, 0), (3000, 0), (3000, 4000), (0, 4000)], streets=streets)
    out = cl.select(d, sigma=240 / 178.0)
    assert len(out["v"]) == 12                                           # numbered: all kept
    gaps = [b["pos"] - a["pos"] for a, b in zip(out["h"], out["h"][1:])]
    assert 120 <= sorted(gaps)[len(gaps) // 2] <= 145                     # rows every other one: 140 m
    assert out["stats"]["h"]["dropped"] >= 12
