"""City engine v2: the seam-angle rule and seams on synthetic two-domain cities (design section 2)."""
import math

import pytest

from alto.build import city_seams as cs
from alto.build.city_types import Domain
from alto.build.city_lines import CW, CH


def test_tilt_snaps_45_and_rounds():
    assert cs.tilt(9.3, 55.8) == (pytest.approx(-43.5), -45.0)       # Kensington: 46.5 apart -> 45
    raw, snap = cs.tilt(9.3, 46.8)
    assert raw == pytest.approx(37.5) and snap == 37.5                # Southwest Philadelphia
    assert cs.tilt(27.7, 4.1)[1] == -23.5                              # Manhattan / Greenwich Village


def test_fold_is_exact():
    # A's columns (90) hinge into C's rows (37.5): the fold line mirrors one onto the other
    fold = cs.fold_angle(90.0, 37.5)
    assert fold == pytest.approx(-26.25)
    s = cs.solve_phi(fold, 90.0, 37.5, CW)
    assert s["t"] == 0 and s["r"] == pytest.approx(1.0, abs=1e-12) and s["ratio"] == pytest.approx(1.0, abs=1e-12)
    assert s["phi"] == pytest.approx(-26.25) and s["err"] == pytest.approx(0.0, abs=1e-12)


def test_45_degree_seam_is_exact_by_swapping_roles():
    # A's rows (0 deg, spacing CH) cross a seam at A's own 45 deg; B's family is perpendicular to the seam
    s = cs.solve_phi(-45.0, 0.0, 45.0, CH)
    assert s["t"] == 0 and s["phi"] == pytest.approx(-45.0)
    assert s["r"] == pytest.approx(math.sqrt(2)) and s["g"] == pytest.approx(170 * math.sqrt(2))
    assert s["nominal"] == CW and s["ratio"] == pytest.approx(1.0017, abs=1e-4)


def test_shear_seam_trades_angle_for_block_width():
    # Baltimore Ave: real seam -17.6 rel A; at the real angle the child blocks would be 13.9% narrow
    assert cs.spacing_ratio(-17.6, 90.0, 37.5) == pytest.approx(0.8604, abs=1e-4)
    s = cs.solve_phi(-17.6, 90.0, 37.5, CW)
    assert 0 < s["t"] < 1
    assert s["ratio"] == pytest.approx(0.90, abs=1e-6)                 # exactly at the tolerance
    assert -26.25 < s["phi"] < -17.6 and s["err"] == pytest.approx(abs(s["phi"] + 17.6))
    earlier = cs.solve_phi(-17.6, 90.0, 37.5, CW, tol=0.10 + 1e-3)
    assert earlier["t"] < s["t"]                                       # smallest t
    strict = cs.solve_phi(-17.6, 90.0, 37.5, CW, tol=0.0)
    assert strict["t"] == 1 and strict["phi"] == pytest.approx(-26.25) and strict["ratio"] == pytest.approx(1.0)


def test_t_join_turns_toward_the_smaller_turn():
    u = (math.cos(math.radians(-20)), math.sin(math.radians(-20)))
    p = cs.t_join((0, -300), (0, 0), u, 40)
    assert p[2][0] < 0                    # going down onto a seam rising to the east: lead runs west (down the slope)
    assert math.dist(p[1], p[2]) == pytest.approx(40)


# ── synthetic two-domain city ────────────────────────────────────────────────
def _clipline(p0, p1, poly):
    r = cs._seg_interval(p0, p1, poly)
    if not r:
        return None
    a, b = r
    return [p0[0] + (p1[0] - p0[0]) * a, p0[1] + (p1[1] - p0[1]) * a, p0[0] + (p1[0] - p0[0]) * b, p0[1] + (p1[1] - p0[1]) * b]


def synth(psi, delta, hinge_fam="v", gap_v=150.0, gap_h=106.25, size=3600.0):
    """Parent: theta 0, columns every gap_v, rows every gap_h, north of a seam through the centre at psi deg.
    The parent's hinge family (columns, or rows) kinks on the seam and runs on in the child's family nearest to
    its own direction; the child's other family is unnamed-ish cross streets every gap_h."""
    S0 = (size / 2, size * 0.6)                # the parent (north) is the larger domain
    u = cs._unit(psi); n = (-u[1], u[0])
    box = [(0, 0), (size, 0), (size, size), (0, size)]
    up = cs.clip_half(box, n, cs._dot(n, S0), "le" if cs._dot(n, (S0[0], 0)) < cs._dot(n, S0) else "ge")
    dn = cs.clip_half(box, n, cs._dot(n, S0), "ge" if cs._dot(n, (S0[0], 0)) < cs._dot(n, S0) else "le")
    P = Domain(id=0, kind="grid", theta=0.0, poly=up, streets=[])
    Q = Domain(id=1, kind="grid", theta=math.radians(delta), poly=dn, streets=[])
    dq_h, dq_v = delta, delta + 90.0
    big = 3 * size
    def far(p, d): return (p[0] + big * math.cos(math.radians(d)), p[1] + big * math.sin(math.radians(d)))
    # parent lines
    for k in range(-30, 31):
        for fam in ("v", "h"):
            off = k * (gap_v if fam == "v" else gap_h) + S0[0 if fam == "v" else 1] + 37.0
            a = (off, -big) if fam == "v" else (-big, off)
            b = (off, big) if fam == "v" else (big, off)
            seg = _clipline(a, b, up)
            if not seg or math.dist(seg[:2], seg[2:]) < 200:
                continue
            name = ("Col %d" if fam == "v" else "Row %d") % k
            P.streets.append({"n": name, "k": 3, "p": seg})
            if fam == hinge_fam:
                # its continuation in the child: from the seam point, in the child family nearest its direction
                dc = dq_h                       # it runs on as the child's rows (as the numbered streets do in C)
                q = cs._isect((1, 0) if fam == "v" else (0, 1), off, n, cs._dot(n, S0))
                # pick the sense that goes into the child polygon
                for dd in (dc, dc + 180):
                    t = far(q, dd)
                    s2 = _clipline(q, t, dn)
                    if s2 and math.dist(s2[:2], s2[2:]) > 200:
                        Q.streets.append({"n": name, "k": 3, "p": s2})
                        break
    # child's other family: cross streets every gap_h across the child polygon
    dcross = dq_v
    nc = (-math.sin(math.radians(dcross)), math.cos(math.radians(dcross)))
    for k in range(-60, 61):
        c = k * gap_h + 11.0
        p0 = (S0[0] + nc[0] * c - big * math.cos(math.radians(dcross)), S0[1] + nc[1] * c - big * math.sin(math.radians(dcross)))
        p1 = far(p0, dcross); p1 = (p0[0] + 2 * big * math.cos(math.radians(dcross)), p0[1] + 2 * big * math.sin(math.radians(dcross)))
        seg = _clipline(p0, p1, dn)
        if seg and math.dist(seg[:2], seg[2:]) > 400:
            Q.streets.append({"n": "Cross %d" % k, "k": 3, "p": seg})
    return P, Q


def _run(psi, delta, hinge_fam, sigma=1.6, tol=cs.R_TOL):
    P, Q = synth(psi, delta, hinge_fam)
    sl, lines, lay = cs.plan([P, Q], sigma=sigma, tol=tol)
    assert len(sl) == 1
    return P, Q, sl[0], lines, lay


def _check_hinge_exact(sm, lay):
    hp = next(pt for pt in sm.info["parts"] if pt["kind"] == "hinge")
    rep = lay.report[(sm.a, sm.b)]
    assert rep["hinge_resid_px"] < 1e-6
    assert len(sm.hinge) >= 8
    pg = hp["page"]
    for h in sm.hinge:                                 # every kink point lies on the page seam line
        assert abs(cs._dot(pg["n"], h["at"]) - pg["c"]) < 1e-6
    # the parent line through Q_k and the child line through Q_k
    mpA, mpB = lay.maps[sm.a], lay.maps[sm.b]
    for h in sm.hinge:
        la = mpA.to_local(*h["at"]); lb = mpB.to_local(*h["at"])
        ga = mpA.loc.gv if h["fa"] == "v" else mpA.loc.gh
        gb = mpB.loc.gv if h["fb"] == "v" else mpB.loc.gh
        assert (la[0] if h["fa"] == "v" else la[1]) == pytest.approx(h["a"] * ga, abs=1e-6)
        assert (lb[0] if h["fb"] == "v" else lb[1]) == pytest.approx(h["b"] * gb, abs=1e-6)
    return rep


def test_synthetic_fold_seam():
    P, Q, sm, lines, lay = _run(-26.25, 37.5, "v")
    assert sm.kind == "hinge" and sm.a == 0 and sm.b == 1
    rep = _check_hinge_exact(sm, lay)
    assert rep["t"] == 0 and sm.phi == pytest.approx(-26.25, abs=0.05)
    assert sm.ratio == pytest.approx(1.0, abs=0.003) and Q.roles == "hv"   # the child's rows (the hinge streets) get CW
    assert sm.info["hinge_sign"] in (1, -1) and sm.info["equalise"]["mismatch"] == 0


def test_synthetic_45_seam():
    P, Q, sm, lines, lay = _run(-45.0, 45.0, "h")
    rep = _check_hinge_exact(sm, lay)
    assert rep["t"] == 0 and sm.phi == pytest.approx(-45.0, abs=0.05)
    assert sm.ratio == pytest.approx(1.0017, abs=0.003)
    assert abs(sm.info["tilt"]) == 45.0


def test_synthetic_shear_seam():
    P, Q, sm, lines, lay = _run(-17.6, 37.5, "v")
    rep = _check_hinge_exact(sm, lay)
    assert 0 < rep["t"] < 1
    assert sm.ratio == pytest.approx(0.90, abs=1e-6)
    assert -26.3 < sm.phi < -17.5 and sm.err == pytest.approx(abs(sm.phi - rep["phi_real"]), abs=1e-9)
    strict = _run(-17.6, 37.5, "v", tol=0.0)[2]
    assert strict.phi == pytest.approx(-26.25, abs=0.05) and strict.ratio == pytest.approx(1.0, abs=1e-6)


def test_synthetic_line_ends():
    P, Q, sm, lines, lay = _run(-26.25, 37.5, "v")
    pa, pb = cs.paths(lay, 0), cs.paths(lay, 1)
    ha = sum(e == "hinge" for p in pa for e in p["ends"])
    hb = sum(e == "hinge" for p in pb for e in p["ends"])
    assert ha == hb == len(sm.hinge)
    tees = [p for p in pa if "tee" in p["ends"]]
    assert tees, "the parent's rows end on the seam with a T"
    hp = sm.info["parts"][0]["page"]
    for p in tees + [p for p in pb if "tee" in p["ends"]]:
        e = p["ends"].index("tee")
        q = p["p"][-2] if e == 1 else p["p"][1]
        lead = p["p"][-1] if e == 1 else p["p"][0]
        assert abs(cs._dot(hp["n"], q) - hp["c"]) < 1e-6               # ends ON the seam
        assert abs(cs._dot(hp["n"], lead) - hp["c"]) < 1e-6            # and the lead runs along it
    # no line of either side crosses the seam segment (touching it at an end is the join)
    a, b = (sm.segs[0][0], sm.segs[0][1]), (sm.segs[0][2], sm.segs[0][3])

    def cross(p, q):
        def o(u, v, w):              # signed distance of w from the line u-v, px
            return ((v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])) / max(1e-9, math.dist(u, v))
        d1, d2, d3, d4 = o(a, b, p), o(a, b, q), o(p, q, a), o(p, q, b)
        return min(abs(d1), abs(d2)) > 1e-6 and d1 * d2 < 0 and d3 * d4 < 0
    for ps in (pa, pb):
        for p in ps:
            assert not any(cross(u, v) for u, v in zip(p["p"], p["p"][1:])), p
