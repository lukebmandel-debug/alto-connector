"""The Star chart's flight planner (alto/build/solar_fly.py, FLY_PLAN_JS) in
Python, line for line — used only by the tests, which hold the two equal under
node (tests/test_solar_fly.py). Nothing in the build calls this.

A route is a list of LEGS, each a curve in the frame of one body (or in the
fixed frame), laid end to end along one progress s = E(tau / D) over the
flight time tau (E: the incomplete-beta family of the engine's _altoEase). The
bodies' clock T(tau) is the flight's own (the page's orbits are driven by it
while the craft flies), so where a body will be at the end of a leg is known
exactly, and every leg that ends on a body ends where that body WILL be then.
The routing rules are in solar_fly.py's docstring."""
from __future__ import annotations

import math

from alto.build.solar_fly import FLY

TAU = 2 * math.pi


# ── the bodies, as solar_draw.py moves them ─────────────────────────────────

def bodies(S):
    B = {}
    many = len(S.get("systems") or []) > 1
    for si, s in enumerate(S.get("systems") or []):
        def add(i, p, per, role, reach, ring=0, q=None):
            n = S["nodes"].get(i)
            if not n:
                return
            B[i] = {"id": i, "p": p, "x": n["x"], "y": n["y"], "per": float(per or 0), "si": si,
                    "d": n["d"], "role": role, "reach": reach, "ring": ring, "kids": [],
                    "orb": n.get("orbit") if q else None, "r": (q or {}).get("r", 0), "a0": (q or {}).get("a0", 0),
                    "look": n.get("look") or ""}
            if p and p in B:
                B[p]["kids"].append(i)
        add(s["sun"], "", 0, "sun", s["R"])
        for pl in s.get("planets") or []:
            add(pl["id"], s["sun"], pl["period"], "planet", max(pl.get("e") or 0, pl["d"] / 2), pl["ring"], pl)
            for m in pl.get("moons") or []:
                sats = m.get("sats") or []
                mr = max((q.get("r") or 0) + q["d"] / 2 for q in sats) if sats else 0
                add(m["id"], pl["id"], m["period"], "moon", max(m.get("ext") or 0, mr, m["d"] / 2), 0, m)
                for q in sats:
                    add(q["id"], m["id"], q["period"], "sat", q["d"] / 2, 0, q)
    core = S.get("core")
    if core and len(S.get("systems") or []) > 1:          # the galactic core: still, between the systems, not a node
        B[CORE] = {"id": CORE, "p": "", "x": core["x"], "y": core["y"], "per": 0.0, "si": -1, "d": 2 * core["r"],
                   "role": "core", "reach": core["r"], "ring": 0, "kids": [], "orb": None, "r": 0, "a0": 0, "look": "blackhole"}
    return {"B": B, "many": many, "spin": S.get("spin") or -1}


CORE = "#core"


def pos(W, i, T):
    B = W["B"]
    b = B[i]
    if not b["p"]:
        return (b["x"], b["y"])
    p = B[b["p"]]
    px, py = pos(W, b["p"], T)
    dx, dy = b["x"] - p["x"], b["y"] - p["y"]
    a = 0.0
    if b["per"] > 0:
        a = W["spin"] * TAU * T / b["per"] + (W["spin"] * TAU * T / (540 + 60 * b["si"]) if W["many"] else 0.0)
    if b["orb"]:                                       # a comet: on its ellipse (solar.orbit_offset), from its plan home
        ox, oy = _orbit_offset(b["r"], b["a0"] + a, b["orb"])
        hx, hy = _orbit_offset(b["r"], b["a0"], b["orb"])
        return (px + dx + (ox - hx), py + dy + (oy - hy))
    c, s = math.cos(a), math.sin(a)
    return (px + dx * c - dy * s, py + dx * s + dy * c)


def _orbit_offset(r, ang, orb):
    """solar.py's orbit_offset: R(rot)·(A cos ψ, B sin ψ), A, B = r(1 ± c)."""
    e = orb["e"]
    q = math.sqrt(max(0.0, 1 - e * e))
    c = (1 - q) / (1 + q)
    A, Bb = r * (1 + c), r * (1 - c)
    m = ang - orb["rot"]
    psi = m
    if orb.get("k"):
        for _ in range(12):
            psi -= (psi - e * math.sin(psi) - m) / (1 - e * math.cos(psi))
    x, y = A * math.cos(psi), Bb * math.sin(psi)
    cr, sr = math.cos(orb["rot"]), math.sin(orb["rot"])
    return (x * cr - y * sr, x * sr + y * cr)


def chain(W, i):
    out = []
    while i:
        out.append(i)
        i = W["B"][i]["p"]
    return out


# ── the curve and the clock ─────────────────────────────────────────────────

def _curve():
    a, b = FLY["EASE"]
    M, c, s = 1000, [0.0], 0.0
    for i in range(M):
        x = (i + 0.5) / M
        s += math.pow(x, a - 1) * math.pow(1 - x, b - 1)
        c.append(s)
    return [v / s for v in c]


CURVE = _curve()


def ease(x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    f = x * 1000
    i = int(math.floor(f))
    return CURVE[i] + (CURVE[i + 1] - CURVE[i]) * (f - i)


def ease_d(x):
    i = min(999, max(0, int(math.floor(x * 1000))))
    return (CURVE[i + 1] - CURVE[i]) * 1000


def ease_inv(s):
    if s <= 0:
        return 0.0
    if s >= 1:
        return 1.0
    lo, hi = 0, 1000
    while hi - lo > 1:
        m = (lo + hi) >> 1
        if CURVE[m] <= s:
            lo = m
        else:
            hi = m
    d = CURVE[hi] - CURVE[lo]
    return (lo + ((s - CURVE[lo]) / d if d > 0 else 0)) / 1000


def clock(c, tau):
    """The bodies' clock T at flight time tau: from rate r0 up to 1 over ru,
    1, then down to rest over the last ru (the orbits stop as the craft lands)."""
    D, ru, r0, T0 = c["D"], c["ru"], c["r0"], c["T0"]
    if c.get("still"):                                 # the orbits are switched off: they stay put
        return T0
    t = min(max(tau, 0.0), D)
    if t <= ru:
        x = t / ru
        return T0 + r0 * t + (1 - r0) * ru * (x * x * x - x * x * x * x / 2)
    A1 = r0 * ru + (1 - r0) * ru * 0.5
    if t <= D - ru:
        return T0 + A1 + (t - ru)
    y = (D - t) / ru
    return T0 + A1 + (D - 2 * ru) + ru * (0.5 - (y * y * y - y * y * y * y / 2))


def clock_rate(c, tau):
    D, ru, r0 = c["D"], c["ru"], c["r0"]
    if c.get("still"):
        return 0.0
    t = min(max(tau, 0.0), D)
    if t <= ru:
        x = t / ru
        return r0 + (1 - r0) * x * x * (3 - 2 * x)
    if t <= D - ru:
        return 1.0
    y = (D - t) / ru
    return y * y * (3 - 2 * y)


# ── a leg's own curve, in its frame ─────────────────────────────────────────

def _sweep(a0, a1, spin, lo):
    """The angle (> 0) turned in the orbits' sense from a0 to a1, at least lo."""
    return lo + ((spin * (a1 - a0) - lo) % TAU)


def _polar_r(L, w):
    r0, r1, k = L["r0"], L["r1"], L["prof"]
    if k == "conic":
        return 2 * r0 * r1 / ((r0 + r1) - (r0 - r1) * math.cos(math.pi * w))
    if k == "cos":
        return r0 + (r1 - r0) * (1 - math.cos(math.pi * w)) / 2
    if k == "phase":
        return r0 + (r1 - r0) * w - L["dip"] * math.sin(math.pi * w)
    return r0 + (r1 - r0) * w                       # spiral


def _arc_table(L):
    """Every leg is flown at an even pace along its own curve (in its frame):
    u (its share of the time) → w (its parameter), by arc length."""
    N = FLY["ARC_N"]
    g, prev = [0.0], _raw(L, 0.0)
    for j in range(1, N + 1):
        cur = _raw(L, j / N)
        g.append(g[-1] + math.hypot(cur[0] - prev[0], cur[1] - prev[1]))
        prev = cur
    tot = g[-1]
    return [v / tot for v in g] if tot > 1e-9 else None


def _warp(L, u):
    G = L.get("g")
    if not G or u <= 0 or u >= 1:
        return min(max(u, 0.0), 1.0)
    N = len(G) - 1
    lo, hi = 0, N
    while hi - lo > 1:
        m = (lo + hi) >> 1
        if G[m] <= u:
            lo = m
        else:
            hi = m
    d = G[hi] - G[lo]
    return (lo + ((u - G[lo]) / d if d > 0 else 0)) / N


def _hyp_F(e, M):
    F = math.asinh(M / e)
    for _ in range(10):
        F -= (e * math.sinh(F) - F - M) / (e * math.cosh(F) - 1)
    return F


def _raw(L, w):
    """The leg's curve at its own parameter w (0..1), in its frame."""
    k = L["k"]
    if k == "bez":
        P = L["P"]
        v = 1 - w
        b0, b1, b2, b3 = v * v * v, 3 * v * v * w, 3 * v * w * w, w * w * w
        return (b0 * P[0] + b1 * P[2] + b2 * P[4] + b3 * P[6], b0 * P[1] + b1 * P[3] + b2 * P[5] + b3 * P[7])
    if k == "fly":
        e, a, Mm = L["e"], L["a"], L["Mm"]
        F = _hyp_F(e, -Mm + 2 * Mm * w)
        x = a * (e - math.cosh(F))
        y = a * math.sqrt(e * e - 1) * math.sinh(F) * L["sense"]
        Px, Py = L["pv"]
        return (x * Px - y * Py, x * Py + y * Px)
    r = _polar_r(L, w)
    ang = L["a0"] + L["spin"] * L["phi"] * w
    return (r * math.cos(ang), r * math.sin(ang))


def nominal(L, u):
    if "g" not in L:
        L["g"] = _arc_table(L)
    return _raw(L, _warp(L, u))


# ── small vector help ───────────────────────────────────────────────────────

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _unit(v, fb=(1.0, 0.0)):
    n = math.hypot(v[0], v[1])
    return (v[0] / n, v[1] / n) if n > 1e-9 else fb


def _polar(rel):
    return math.hypot(rel[0], rel[1]), math.atan2(rel[1], rel[0])


# ── the route's skeleton ────────────────────────────────────────────────────

def steps(W, A, Bt, T_mid):
    """What each leg does (solar_fly.py, routing rules)."""
    B = W["B"]
    ca, cb = chain(W, A), chain(W, Bt)
    st = []
    if ca[-1] != cb[-1]:                                   # another system: assists, escape, capture
        pa = ca[-2] if len(ca) >= 2 else ""
        if len(ca) >= 2:                                   # out of A's planet's family first
            st.append(["esc", pa])
        last = pa or ca[-1]
        for I in assists(W, ca[-1], pa, cb[-1], T_mid):
            st.append(["xfer", ca[-1], I])
            st.append(["fly", I])
            last = I
        if _by_core(W, pos(W, last, T_mid), cb[-1]):                    # a swing round the galactic core on the way
            st.append(["bez", CORE])
            st.append(["fly", CORE])
        st.append(["bez", cb[-1]])
        _down(st, cb, len(cb) - 1)
        return st
    L = next(x for x in ca if x in cb)
    ia, ib = ca.index(L), cb.index(L)
    a1 = ca[ia - 1] if ia >= 1 else ""
    b1 = cb[ib - 1] if ib >= 1 else ""
    if ia >= 2:
        st.append(["esc", a1])
    if not a1:                                             # down from L itself
        r = math.hypot(B[b1]["x"] - B[L]["x"], B[b1]["y"] - B[L]["y"])
        if r < FLY["HOP_R"]:
            st.append(["hop", L, b1])
        else:
            st.append(["park", L, b1])
            st.append(["inj", L, b1])
        _down(st, cb, ib - 1)
        return st
    if not b1:                                             # up to L
        st.append(["ret", L])
        return st
    if B[L]["role"] == "sun" and abs(B[a1]["ring"] - B[b1]["ring"]) >= FLY["FAR_RINGS"]:
        mid = middle(W, L, a1, b1, T_mid)
        if mid:
            st.append(["xfer", L, mid])
            st.append(["fly", mid])
    st.append(["xfer", L, b1])
    _down(st, cb, ib - 1)
    return st


def _by_core(W, a, s2):
    """The core is on the way from a (where the craft leaves its system's
    last swing-by): ahead (within CORE_AHEAD of the way), with room to turn
    (CORE_MIN from a, half that on to the other system's edge), and going
    round it adds at most CORE_DETOUR."""
    B = W["B"]
    if CORE not in B:
        return False
    b, c = (B[s2]["x"], B[s2]["y"]), (B[CORE]["x"], B[CORE]["y"])
    d, dc = math.hypot(b[0] - a[0], b[1] - a[1]), math.hypot(c[0] - a[0], c[1] - a[1])
    if dc < FLY["CORE_MIN"] or d < 1e-6:
        return False
    if math.hypot(b[0] - c[0], b[1] - c[1]) - B[s2]["reach"] - FLY["SYS_PAD"] < FLY["CORE_MIN"] / 2:
        return False                                   # and room on to the other system's edge
    cosang = ((c[0] - a[0]) * (b[0] - a[0]) + (c[1] - a[1]) * (b[1] - a[1])) / (dc * d)
    return cosang >= math.cos(FLY["CORE_AHEAD"]) and dc + math.hypot(b[0] - c[0], b[1] - c[1]) <= FLY["CORE_DETOUR"] * d


def _down(st, cb, k):
    """From cb[k] (just reached; the sun of another system when k is its top)
    down B's chain: each level one capture."""
    if k == len(cb) - 1 and st and st[-1][0] == "bez":
        if k == 0:
            st.append(["ret", cb[0]])
            return
        st.append(["xfer", cb[k], cb[k - 1]])
        k -= 1
    while k >= 1:
        st.append(["xfer", cb[k], cb[k - 1]])
        k -= 1


def middle(W, sun, a1, b1, T_mid):
    """The planet between A's ring and B's to swing by: the one that turns
    the craft least round the sun on the way (rings strictly between)."""
    B, spin = W["B"], W["spin"]
    lo, hi = sorted((B[a1]["ring"], B[b1]["ring"]))
    o = pos(W, sun, T_mid)
    ang = lambda i: math.atan2(pos(W, i, T_mid)[1] - o[1], pos(W, i, T_mid)[0] - o[0])
    best, bc = "", 1e9
    for i in B[sun]["kids"]:
        if lo < B[i]["ring"] < hi:
            c = _sweep(ang(a1), ang(i), spin, FLY["PHI_MIN"]) + _sweep(ang(i), ang(b1), spin, FLY["PHI_MIN"])
            c -= FLY["BH_BONUS"] if B[i]["look"] == "blackhole" else 0.0      # a black hole: the swing-by of choice
            if c < bc - 1e-9:
                best, bc = i, c
    return best


def assists(W, sun1, pa, sun2, T_mid):
    """1-3 planets of the home system to swing by on the way out: each
    farther out than the last (from A's planet; from the sun, any), lying
    roughly toward the other system, and the next one a short way on round
    the sun the orbits' way (no lap of the system to reach it)."""
    B, spin = W["B"], W["spin"]
    o = (B[sun1]["x"], B[sun1]["y"])
    th = math.atan2(B[sun2]["y"] - o[1], B[sun2]["x"] - o[0])
    ang = lambda i: math.atan2(pos(W, i, T_mid)[1] - o[1], pos(W, i, T_mid)[0] - o[0])
    ring, at = (B[pa]["ring"], ang(pa)) if pa else (0, None)
    out = []
    while len(out) < FLY["ASSIST_MAX"]:
        best, bc = "", 1e9
        for i in B[sun1]["kids"]:
            if B[i]["ring"] <= ring:
                continue
            a = ang(i)
            dev = abs(((a - th + math.pi) % TAU) - math.pi)
            sw = _sweep(at, a, spin, FLY["PHI_MIN"]) if at is not None else 0.0
            if dev > FLY["ASSIST_DEV"] or sw > FLY["ASSIST_SWEEP"]:
                continue
            c = sw + 0.5 * dev - (FLY["BH_BONUS"] if B[i]["look"] == "blackhole" else 0.0)
            if c < bc - 1e-9:
                best, bc = i, c
        if not best:
            break
        out.append(best)
        ring, at = B[best]["ring"], ang(best)
    return out


# ── the legs ────────────────────────────────────────────────────────────────

def _target(st, j, to):
    """The body the route heads for after step j (directions only)."""
    for q in st[j + 1:]:
        if q[0] in ("xfer", "park", "inj", "hop"):
            return q[2]
        if q[0] in ("fly", "bez", "ret"):
            return q[1]
    return to


def _cap_point(W, Y, T, din, spin):
    """Where to come in round body Y, its reach out: the point of that circle
    where going round it the orbits' way is going the way the craft arrives
    (din) — so the capture turns on from the way it was going."""
    o = pos(W, Y, T)
    rho = W["B"][Y]["reach"] + FLY["CAP_PAD"]
    a = math.atan2(din[1], din[0]) - spin * math.pi / 2
    return (o[0] + rho * math.cos(a), o[1] + rho * math.sin(a))


def _hyper(W, I, din, dout):
    """A flyby of I turning din toward dout (the turn clamped): its hyperbola."""
    dot = max(-1.0, min(1.0, din[0] * dout[0] + din[1] * dout[1]))
    sg = 1.0 if din[0] * dout[1] - din[1] * dout[0] >= 0 else -1.0
    tn = FLY["TURN_CORE"] if I == CORE else FLY["TURN"]          # round the core: as much as the way needs
    th = min(max(math.acos(dot), tn[0]), tn[1])
    c, s = math.cos(sg * th), math.sin(sg * th)
    do = (din[0] * c - din[1] * s, din[0] * s + din[1] * c)
    e = 1 / math.sin(th / 2)
    q = W["B"][I]["d"] / 2 + FLY["FLY_Q"]
    a = q / (e - 1)
    pv = _unit((din[0] - do[0], din[1] - do[1]))
    sense = 1.0 if -pv[1] * (din[0] + do[0]) + pv[0] * (din[1] + do[1]) >= 0 else -1.0
    Fm = math.acosh((q * FLY["SOI_K"] / a + 1) / e)
    return {"e": e, "a": a, "Mm": e * math.sinh(Fm) - Fm, "pv": [pv[0], pv[1]], "sense": sense}


def _conic(W, L, cur, F, T0, ep, T1, lo):
    """A transfer round F from the craft (cur, at T0) to world point ep (at T1)."""
    L.pop("g", None)
    r0, a0 = _polar(_sub(cur, pos(W, F, T0)))
    r1, a1 = _polar(_sub(ep, pos(W, F, T1)))
    if r1 < 1e-6:
        L.update(prof="cos", r0=r0, r1=0.0, a0=a0, phi=FLY["RET_PHI"])
    elif abs(r1 - r0) < FLY["PHASE_K"] * max(r0, r1):
        L.update(prof="phase", r0=r0, r1=r1, a0=a0, dip=FLY["DIP"] * min(r0, r1),
                 phi=_sweep(a0, a1, W["spin"], FLY["PHASE_PHI"]))
    else:
        L.update(prof="conic" if r0 > 1e-6 else "cos", r0=r0, r1=r1, a0=a0,
                 phi=_sweep(a0, a1, W["spin"], lo))


def _end(W, L, F, T):
    n = nominal(L, 1.0)
    o = pos(W, F, T) if F else (0.0, 0.0)
    return (o[0] + n[0], o[1] + n[1])


def build(W, R, st):
    """Every leg, from the craft's start, on the shares R["S"] of the flight."""
    B, spin, c = W["B"], W["spin"], R["c"]
    legs, cur, vdir, hyp = [], R["p0"], R["v0dir"], None
    if vdir is None and B[R["from"]]["p"]:               # leaving a body: along its own motion
        a, b = pos(W, R["from"], clock(c, 0.0)), pos(W, R["from"], clock(c, 0.0) + 0.01)
        vdir = _unit(_sub(b, a), None) if math.hypot(*_sub(b, a)) > 1e-9 else None
    tau = lambda s: R["D"] * ease_inv(s)
    for j, q in enumerate(st):
        s0, s1 = R["S"][j], R["S"][j + 1]
        T0, T1 = clock(c, tau(s0)), clock(c, tau(s1))
        k = q[0]
        L = {"k": k, "s0": s0, "s1": s1, "spin": spin, "f": ""}
        nxt = st[j + 1] if j + 1 < len(st) else None
        if k == "esc":
            F = q[1]
            L["f"] = F
            r0, a0 = _polar(_sub(cur, pos(W, F, T0)))
            wn, of = pos(W, _target(st, j, R["to"]), T1), pos(W, F, T1)
            a1 = math.atan2(wn[1] - of[1], wn[0] - of[0]) - spin * math.pi / 2
            L.update(prof="spiral", r0=r0, r1=B[F]["reach"] + FLY["ESC_PAD"], a0=a0,
                     phi=_sweep(a0, a1, spin, FLY["ESC_PHI"]))
        elif k in ("xfer", "inj", "hop"):
            F, Y = q[1], q[2]
            L["f"] = F
            if nxt and nxt[0] == "fly":                    # end where the flyby begins
                o_i = pos(W, Y, T1)
                _conic(W, L, cur, F, T0, o_i, T1, FLY["PHI_MIN"])
                pre = _end(W, L, F, T1)
                p9 = nominal(L, 0.995)
                o9 = pos(W, F, T1)
                din = _unit(_sub(pre, (o9[0] + p9[0], o9[1] + p9[1])), _unit(_sub(o_i, cur)))
                s2 = R["S"][j + 2]
                wn = pos(W, _target(st, j + 1, R["to"]), clock(c, tau(s2)))
                hyp = _hyper(W, Y, din, _unit(_sub(wn, o_i)))
                hl = dict(hyp, k="fly")
                ent = nominal(hl, 0.0)
                ep = (o_i[0] + ent[0], o_i[1] + ent[1])
            elif nxt and nxt[0] == "xfer" and nxt[1] == Y:  # come in round Y, then on down
                o_y = pos(W, Y, T1)
                _conic(W, L, cur, F, T0, o_y, T1, FLY["PHI_MIN"])
                pre = _end(W, L, F, T1)
                p9, o9 = nominal(L, 0.995), pos(W, F, clock(c, tau(s0 + (s1 - s0) * 0.995)))
                din = _unit(_sub(pre, (o9[0] + p9[0], o9[1] + p9[1])), _unit(_sub(o_y, cur)))
                ep = _cap_point(W, Y, T1, din, spin)
            else:
                ep = pos(W, Y, T1)
            if k == "hop" and math.hypot(*_sub(cur, pos(W, F, T0))) < 1.0:
                r1, a1 = _polar(_sub(ep, pos(W, F, T1)))
                L.update(prof="cos", r0=0.0, r1=r1, a0=a1 - spin * FLY["HOP_PHI"], phi=FLY["HOP_PHI"])
            else:
                _conic(W, L, cur, F, T0, ep, T1, FLY["PHI_MIN"])
        elif k == "park":
            F, X = q[1], q[2]
            L["f"] = F
            Ti = clock(c, tau(R["S"][j + 2]))              # the injection's end
            rx, ax = _polar(_sub(pos(W, X, Ti), pos(W, F, Ti)))
            r0, a0c = _polar(_sub(cur, pos(W, F, T0)))
            a_end = ax + math.pi
            if r0 < 1.0:
                L.update(prof="spiral", r0=r0, r1=B[F]["d"] / 2 + FLY["PARK_GAP"],
                         a0=a_end - spin * FLY["PARK_PHI"], phi=FLY["PARK_PHI"])
            else:
                L.update(prof="spiral", r0=r0, r1=B[F]["d"] / 2 + FLY["PARK_GAP"], a0=a0c,
                         phi=_sweep(a0c, a_end, spin, FLY["PHI_MIN"]))
        elif k == "ret":
            F = q[1]
            L["f"] = F
            r0, a0 = _polar(_sub(cur, pos(W, F, T0)))
            L.update(prof="cos", r0=r0, r1=0.0, a0=a0, phi=FLY["RET_PHI"])
        elif k == "fly":
            L["f"] = q[1]
            L.update(hyp)
        elif k == "bez" and nxt and nxt[0] == "fly":         # out to a swing round the core
            oc = pos(W, q[1], T1)
            wn = pos(W, _target(st, j + 1, R["to"]), clock(c, tau(R["S"][j + 2])))
            hyp = _hyper(W, q[1], _unit(_sub(oc, cur)), _unit(_sub(wn, oc)))
            hl = dict(hyp, k="fly")
            e0, e1 = nominal(hl, 0.0), nominal(hl, 0.002)
            p3 = (oc[0] + e0[0], oc[1] + e0[1])
            L["P"] = _bez(cur, p3, vdir, _unit(_sub(e1, e0)))
        elif k == "bez":
            sun2 = q[1]
            o2 = pos(W, sun2, T1)
            tc = math.atan2(cur[1] - o2[1], cur[0] - o2[0])
            rr = B[sun2]["reach"] + FLY["SYS_PAD"]
            # where to meet the other system's edge: on its near side, so that
            # from there the capture turns about half an orbit to B's planet
            nb = st[j + 1][2] if j + 1 < len(st) and st[j + 1][0] == "xfer" else ""
            al = tc + spin * FLY["CAP_ROT"]
            if nb:
                aT = math.atan2(*reversed(_sub(pos(W, nb, clock(c, R["D"])), o2)))
                best = None
                for m in range(15):
                    dl = -1.2 + 0.2 * m
                    a = tc + spin * dl
                    pa3 = (o2[0] + rr * math.cos(a), o2[1] + rr * math.sin(a))
                    ch = _unit(_sub(pa3, cur))
                    ta = a + spin * math.pi / 2
                    if ch[0] * math.cos(ta) + ch[1] * math.sin(ta) < math.cos(FLY["BEZ_TURN"]):
                        continue                               # it would come in backwards
                    cst = abs(_sweep(a, aT, spin, FLY["PHI_MIN"]) - FLY["CAP_SWEEP"]) + 0.3 * abs(dl - FLY["CAP_ROT"])
                    if best is None or cst < best[0] - 1e-9:
                        best = (cst, a)
                al = best[1] if best else al
            p3 = (o2[0] + rr * math.cos(al), o2[1] + rr * math.sin(al))
            t3 = (math.cos(al + spin * math.pi / 2), math.sin(al + spin * math.pi / 2))
            L["P"] = _bez(cur, p3, vdir, t3)
        legs.append(L)
        end = _end(W, L, L["f"], T1)
        # the way it leaves (the next curve may start along it)
        T9 = clock(c, tau(s0 + (s1 - s0) * 0.995))
        n9 = nominal(L, 0.995)
        o9 = pos(W, L["f"], T9) if L["f"] else (0.0, 0.0)
        dv = _sub(end, (o9[0] + n9[0], o9[1] + n9[1]))
        vdir = _unit(dv) if math.hypot(dv[0], dv[1]) > 1e-6 else None
        cur = end
    return legs


def _bez(cur, p3, vdir, t3):
    """A cruise from cur (going vdir) to p3 (arriving along t3): never setting
    off more than BEZ_TURN away from where it is going."""
    ch = _unit(_sub(p3, cur))
    t0v = _unit(vdir, ch) if vdir else ch
    cr, dt = ch[0] * t0v[1] - ch[1] * t0v[0], ch[0] * t0v[0] + ch[1] * t0v[1]
    if dt < math.cos(FLY["BEZ_TURN"]):
        g = FLY["BEZ_TURN"] * (1.0 if cr >= 0 else -1.0)
        t0v = (ch[0] * math.cos(g) - ch[1] * math.sin(g), ch[0] * math.sin(g) + ch[1] * math.cos(g))
    ln = math.hypot(p3[0] - cur[0], p3[1] - cur[1]) / 3
    return [cur[0], cur[1], cur[0] + t0v[0] * ln, cur[1] + t0v[1] * ln,
            p3[0] - t3[0] * ln, p3[1] - t3[1] * ln, p3[0], p3[1]]


def _length(L):
    n, tot, prev = 16, 0.0, nominal(L, 0.0)
    for j in range(1, n + 1):
        cur = nominal(L, j / n)
        tot += math.hypot(cur[0] - prev[0], cur[1] - prev[1])
        prev = cur
    return tot


def _shares(lens):
    n = len(lens)
    tot = sum(lens) or 1.0
    lo = min(FLY["MIN_SHARE"], 1.0 / n)
    w = [max(lo, v / tot) for v in lens]
    k = sum(w)
    S, acc = [0.0], 0.0
    for v in w:
        acc += v / k
        S.append(acc)
    S[-1] = 1.0
    return S


def _dur(total):
    return min(FLY["D_MAX"], max(FLY["D_MIN"], FLY["D_BASE"] + total * FLY["D_PER_PX"]))


def _clock(o, D):
    return {"T0": float(o.get("T0") or 0), "r0": float(o.get("r0") or 0), "D": D, "ru": min(FLY["RAMP"], D / 3),
            "still": bool(o.get("still"))}


# ── the flight ──────────────────────────────────────────────────────────────

def plan(S, A, Bt, o=None):
    """A route from body A (or, re-planning, the craft at o["start"]) to body
    Bt, starting at bodies' clock o["T0"], the orbits running at rate o["r0"]."""
    o = o or {}
    W = bodies(S)
    if A not in W["B"] or Bt not in W["B"] or A == Bt or CORE in (A, Bt):
        return None
    T0 = float(o.get("T0") or 0)
    st = steps(W, A, Bt, T0 + FLY["T_MID"])
    if not st:
        return None
    sv = o.get("start")
    p0 = (sv[0], sv[1]) if sv else pos(W, A, T0)
    R = {"to": Bt, "from": A, "p0": p0, "v0dir": None}
    if sv and math.hypot(sv[2], sv[3]) > 1e-6:
        R["v0dir"] = _unit((sv[2], sv[3]))
    d0 = math.hypot(*_sub(pos(W, Bt, T0), p0))
    R["D"] = _dur(d0 * 1.4)
    R["S"] = [j / len(st) for j in range(len(st) + 1)]
    R["c"] = _clock(o, R["D"])
    for _ in range(FLY["ITER"]):
        legs = build(W, R, st)
        lens = [_length(L) for L in legs]
        R["S"] = _shares(lens)
        R["D"] = _dur(sum(lens))
        R["c"] = _clock(o, R["D"])
    # a short coast, when it lets the transfers turn nearer a half orbit
    best = None
    for cst in FLY["COAST"]:
        R2 = dict(R, D=R["D"] + cst)
        if R2["D"] > FLY["D_MAX"] + 1e-9:
            continue
        R2["c"] = _clock(o, R2["D"])
        legs = build(W, R2, st)
        cost = cst * FLY["COAST_W"] + sum(abs(L["phi"] - math.pi) / math.pi for L in legs
                                          if L.get("prof") == "conic")
        if best is None or cost < best[0] - 1e-9:
            best = (cost, R2, legs)
    R, legs = best[1], best[2]
    R["legs"] = legs
    R["steps"] = st
    _blends(W, R)
    if sv:
        v_nom = _vel(W, R, 0.0, +1)
        R["carry"] = [sv[2] - v_nom[0], sv[3] - v_nom[1], min(FLY["CARRY"], R["D"] / 3)]
    R["keys"] = cam_keys(W, R, o)
    return R


def _leg_xy(W, R, L, t, s, blend=True):
    u = min(max((s - L["s0"]) / (L["s1"] - L["s0"]), 0.0), 1.0)
    T = clock(R["c"], t)
    ox, oy = pos(W, L["f"], T) if L["f"] else (0.0, 0.0)
    nx, ny = nominal(L, u)
    x, y = ox + nx, oy + ny
    H = L.get("H")
    if blend and H and u < H[4]:
        q = u / H[4]
        h00, h10 = 2 * q * q * q - 3 * q * q + 1, q * q * q - 2 * q * q + q
        x += h00 * H[0] + h10 * H[4] * H[2]
        y += h00 * H[1] + h10 * H[4] * H[3]
    return (x, y)


def _leg_of(R, s):
    for L in R["legs"]:
        if s <= L["s1"]:
            return L
    return R["legs"][-1]


def at(W, R, tau, blend=True):
    """The craft at flight time tau (plan coordinates)."""
    D = R["D"]
    t = min(max(tau, 0.0), D)
    s = ease(t / D)
    x, y = _leg_xy(W, R, _leg_of(R, s), t, s, blend)
    C = R.get("carry")
    if C and t < C[2]:
        k = t * (1 - t / C[2]) ** 2
        x += C[0] * k
        y += C[1] * k
    return (x, y)


def _vel(W, R, t, side):
    h = FLY["H"]
    if side > 0:
        a, b = at(W, R, t), at(W, R, t + h)
    else:
        a, b = at(W, R, t - h), at(W, R, t)
    return ((b[0] - a[0]) / h, (b[1] - a[1]) / h)


def _blends(W, R):
    """Each leg after the first takes in the craft's velocity where it joins:
    a cubic Hermite term over the leg's first BLEND of u, zero after."""
    D = R["D"]
    for i in range(1, len(R["legs"])):
        L = R["legs"][i]
        t = D * ease_inv(L["s0"])
        h = FLY["H"]
        p_in = at(W, R, t)
        a, b = at(W, R, t - h), p_in
        v_in = ((b[0] - a[0]) / h, (b[1] - a[1]) / h)
        n0 = _leg_xy(W, R, L, t, L["s0"], False)
        n1 = _leg_xy(W, R, L, t + h, ease((t + h) / D), False)
        v_n = ((n1[0] - n0[0]) / h, (n1[1] - n0[1]) / h)
        dudt = ease_d(t / D) / D / (L["s1"] - L["s0"])
        ub = FLY["BLEND"]
        hx, hy = p_in[0] - n0[0], p_in[1] - n0[1]
        if dudt > 1e-6:
            gx, gy = (v_in[0] - v_n[0]) / dudt, (v_in[1] - v_n[1]) / dudt
        else:
            gx, gy = 0.0, 0.0
        cap = FLY["BLEND_CAP"] * max(_length(L), 40.0) / ub
        m = math.hypot(gx, gy)
        if m > cap:
            gx, gy = gx * cap / m, gy * cap / m
        L["H"] = [hx, hy, gx, gy, ub]


# ── the camera ──────────────────────────────────────────────────────────────

def cam_keys(W, R, o):
    """Camera keys [tau, cx, cy, ln scale] (plan coordinates; scale 1 = full
    size): what the next stretch of flight covers, framed — and the target
    too, as the craft nears it — smoothed so the view never lurches."""
    D = R["D"]
    vw, vh = (o.get("view") or [1500, 950])[:2]
    K, win = FLY["CAM_K"], FLY["CAM_WIN"]
    end = pos(W, R["to"], clock(R["c"], D))
    raw = []
    for k in range(K + 1):
        t = D * k / K
        xs, ys = [], []
        for j in range(7):
            p = at(W, R, t + win[0] + (win[1] - win[0]) * j / 6)
            xs.append(p[0])
            ys.append(p[1])
        if t >= D - FLY["CAM_SEE"]:
            xs.append(end[0])
            ys.append(end[1])
        bw, bh = max(xs) - min(xs) + FLY["CAM_PAD"], max(ys) - min(ys) + FLY["CAM_PAD"]
        sc = min(1.0, vw * FLY["CAM_FILL"] / bw, vh * FLY["CAM_FILL"] / bh)
        raw.append([t, (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, math.log(max(FLY["CAM_MIN"], sc))])
    for _ in range(2):
        sm = []
        for k in range(K + 1):
            a, b = max(0, k - 2), min(K, k + 2)
            n = b - a + 1
            sm.append([raw[k][0]] + [sum(raw[i][j] for i in range(a, b + 1)) / n for j in (1, 2, 3)])
        raw = sm
    return raw


def _catmull(P, k, f, j):
    n = len(P) - 1
    p0, p1, p2, p3 = P[max(0, k - 1)][j], P[k][j], P[min(n, k + 1)][j], P[min(n, k + 2)][j]
    return 0.5 * ((2 * p1) + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f
                  + (-p0 + 3 * p1 - 3 * p2 + p3) * f * f * f)


def _ss(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def cam(W, R, tau, o):
    """The camera at tau, [cx, cy, scale]: from the view the flight began in
    (o["cam"]) through the keys to the target at full size, at rest at both
    ends."""
    D, P = R["D"], R["keys"]
    t = min(max(tau, 0.0), D)
    K = len(P) - 1
    x = t / D * K
    k = min(K - 1, int(math.floor(x)))
    f = x - k
    cx, cy, ls = _catmull(P, k, f, 1), _catmull(P, k, f, 2), _catmull(P, k, f, 3)
    c0 = o.get("cam") or [P[0][1], P[0][2], 1.0]
    l0 = math.log(max(FLY["CAM_MIN"], min(1.0, c0[2])))
    end = pos(W, R["to"], clock(R["c"], D))
    tp = min(FLY["CAM_PIN"], D / 3)
    a = _ss(t / tp)
    cx, cy, ls = c0[0] + (cx - c0[0]) * a, c0[1] + (cy - c0[1]) * a, l0 + (ls - l0) * a
    b = _ss((t - (D - tp)) / tp)
    cx, cy, ls = cx + (end[0] - cx) * b, cy + (end[1] - cy) * b, ls * (1 - b)
    return [cx, cy, min(1.0, math.exp(ls))]
