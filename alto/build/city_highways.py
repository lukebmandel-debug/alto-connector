"""Highways of the Mind Palace city: Interstates, expressways, parkways and freeways as first-class NAMED ROUTE LINES,
drawn like the transit lines (palace_transit*.py) but with their own look (palace_highway_js.py).

Three steps, each usable alone:

  read(els, proj, W, H)   raw OSM (palace_map's merged elements) -> the real highways in real map px:
                          {"v": 1, "roads": [...], "x": [...interchanges]}; palace_map stores it as m["highways"].
  attach(g, m=None)       after the grid (v1 or v2 engine): each road routed over the drawn domains' lattices (the
                          grade-separated router of palace_transit_route.octi_route: runs along the domain's axes and
                          45 degrees, few rounded bends, never more than STRAY_MAX blocks from the real road, a river
                          crossed only where the real road crosses it), its interchanges standing on lattice nodes in
                          ride order, bridges/tunnels where it crosses water -> g["hw"] (the page's M.hw).
  report(g, m)            the highway checks, in city_report's (status, msg, data) form.

RULES (C3.md has the reasons and the numbers)
  * Which ways: every highway=motorway; a highway=trunk only when it is expressway-like: motorroad=yes or
    expressway=yes, or a name / official / alt name with a highway word (Expressway, Freeway, Parkway, Highway,
    Turnpike, ...), or membership of a route=road relation whose name has one or whose network is a parkway.
    A trunk that is a city street (London's A-roads, DC's K Street) is NOT a highway: it stays a street of the grid.
  * Which road: ways are grouped by their primary ref (Interstate before US before state before the rest; suffixes
    Express/Alt/Truck/Business dropped, so I 395 Express rides with I 395); a way with only a name joins the ref
    its name carries elsewhere; an anonymous motorway joins the one road it touches. A road made only of
    "... Bridge" ways with no ref is left to the engine's bridges.
  * One line per carriageway pair: each connected piece of a road is reduced to its longest path (two Dijkstras),
    so the two directions of a dual carriageway draw once; a side piece longer than BRANCH_MIN that leaves the
    main path by more than BRANCH_OFF is a branch; pieces whose ends are within GAP_JOIN are joined.
  * Interchanges: the link ramps (motorway_link / trunk_link) that touch a road; ramps touching it within X_MERGE
    along the road are one interchange; named by the exit (motorway_junction ref/name) and the crossing street or
    highway the ramps reach; a road ending on a street ends at an interchange named for it.
  * Over/under: a highway joins the street graph ONLY at its interchanges (Directions' drive option); it is drawn
    over the streets it crosses.
"""
import math
import re

from alto.palace_map import douglas_peucker, _liang_barsky

KINDS = ("motorway", "trunk")
LINKS = ("motorway_link", "trunk_link")
HW_WORDS = re.compile(r"\b(expressway|expwy|expy|freeway|fwy|parkway|pkwy|highway|hwy|turnpike|tpke|thruway|motorway|"
                      r"autoroute|autopista|autobahn|autostrada|tangenziale|p[ée]riph[ée]rique|ronda|interstate)\b", re.I)
NAME_KEYS = ("name", "alt_name", "official_name", "old_name")
SUFFIX = re.compile(r"\s+(express|alt|alternate|truck|business|bus|byp|bypass|spur|hov|toll)\b.*$", re.I)
US_STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC "
                "ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY SR".split())

MIN_LEN = 350.0         # m: a road whose drawn pieces are shorter than this in all is not a highway of the page
GAP_JOIN = 220.0        # m: two pieces of one road whose ends are this near are one piece
BRANCH_MIN = 450.0      # m: a side piece at least this long ...
BRANCH_OFF = 140.0      # m: ... leaving the main path by more than this is a branch of the road
SIMPL = 2.0             # m: Douglas-Peucker of the real pieces
X_MERGE = 380.0         # m along the road: link ramps touching it this near are one interchange
JN_NEAR = 260.0         # m: an exit node (motorway_junction) this near an interchange names it
SAMPLE = 25.0           # m: the real track handed to the router, one sample per SAMPLE
SHIELD_BLK = 9.0        # blocks between two shields along a drawn line
TRIM = 3.0              # blocks: a highway is drawn only this far beyond the drawn city (blocks or streets)
FILL_D = 2.5            # blocks: a stretch of the real road this far from every drawn run is drawn from its real shape
STOP_MIN = 0.7          # blocks: an interchange this near the previous one along a part shares its node


# ── refs, names, networks ───────────────────────────────────────────────────────────────────────────────────────────
def refs_of(tg):
    out = []
    for r in re.split(r"[;,]", (tg or {}).get("ref") or ""):
        r = SUFFIX.sub("", r.strip())
        if r and r not in out:
            out.append(r)
    return out


def _rank(r):
    mt = re.match(r"^([A-Za-z]+)[ -]?(\d+)([A-Za-z]*)$", r)
    if not mt:
        return (3, 0, r)
    p = mt.group(1).upper()
    return ({"I": 0, "US": 1}.get(p, 2 if p in US_STATES else 3), int(mt.group(2)), r)


def label(ref):
    """'I 95' -> 'I-95', 'NY 9A' -> 'NY-9A'; 'FDR', 'A501', 'B-10' unchanged."""
    mt = re.match(r"^([A-Za-z]+) (\S+)$", ref or "")
    return "%s-%s" % (mt.group(1), mt.group(2)) if mt else (ref or "")


def network(ref, rel_net=None):
    """The shield kind: 'i' Interstate, 'us' US route, 'st' a state / provincial road, 'o' anything else."""
    rn = (rel_net or "")
    if rn.startswith("US:I"):
        return "i"
    if rn.startswith("US:US"):
        return "us"
    if rn.startswith("US:") and len(rn.split(":")) == 2:
        return "st"
    p = (re.match(r"^([A-Za-z]+)", ref or "") or [None, ""])[1] if ref else ""
    p = p.upper()
    return "i" if p == "I" else "us" if p == "US" else "st" if p in US_STATES else "o"


def hw_name(tg, rels=()):
    """The way's highway name: its own name, alt / official / old name with a highway word, else a road relation's;
    a tunnel or bridge keeps its own name (Holland Tunnel, not Interstate 78)."""
    own = (tg or {}).get("name") or ""
    if own and re.search(r"\b(tunnel|bridge)\b", own, re.I):
        return own
    for k in NAME_KEYS:
        v = (tg or {}).get(k) or ""
        if v and HW_WORDS.search(v):
            return v
    for r in rels:
        if r.get("name") and HW_WORDS.search(r["name"]):
            return r["name"]
    return ""


def qualifies(tg, rels=()):
    hw = (tg or {}).get("highway")
    if hw == "motorway":
        return True
    if hw != "trunk":
        return False
    if tg.get("motorroad") == "yes" or tg.get("expressway") == "yes":
        return True
    if hw_name(tg, rels):
        return True
    return any("parkway" in (r.get("net") or "").lower() for r in rels)


# ── geometry helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _plen(p):
    return sum(_d(p[i], p[i + 1]) for i in range(len(p) - 1))


def _pairs(f):
    return [(f[i], f[i + 1]) for i in range(0, len(f) - 1, 2)]


def _flat(pts):
    return [round(v, 1) for p in pts for v in p]


def _seg_foot(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy or 1e-12
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    q = (a[0] + t * dx, a[1] + t * dy)
    return _d(p, q), t, q


def _project(p, pts):
    """(distance, arclength s, foot point) of p onto the polyline pts."""
    best, s0 = None, 0.0
    for i in range(len(pts) - 1):
        L = _d(pts[i], pts[i + 1])
        d, t, q = _seg_foot(p, pts[i], pts[i + 1])
        if best is None or d < best[0]:
            best = (d, s0 + t * L, q)
        s0 += L
    return best or (1e18, 0.0, p)


def _at(pts, s):
    for i in range(len(pts) - 1):
        L = _d(pts[i], pts[i + 1])
        if s <= L or i == len(pts) - 2:
            t = 0.0 if L < 1e-9 else max(0.0, min(1.0, s / L))
            return (pts[i][0] + t * (pts[i + 1][0] - pts[i][0]), pts[i][1] + t * (pts[i + 1][1] - pts[i][1]))
        s -= L
    return pts[-1]


def _samples(pts, step):
    out, s, L = [], 0.0, _plen(pts)
    while s < L:
        out.append(_at(pts, s))
        s += step
    out.append(pts[-1])
    return out


def _clip(pts, flags, W, H):
    """Pieces of a polyline (with a flag per segment) inside the page box."""
    pieces, cur, cf = [], None, None
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        r = _liang_barsky(x0, y0, x1, y1, W, H)
        if r is None:
            if cur:
                pieces.append((cur, cf))
            cur = None
            continue
        t0, t1 = r
        a = (x0 + t0 * (x1 - x0), y0 + t0 * (y1 - y0))
        b = (x0 + t1 * (x1 - x0), y0 + t1 * (y1 - y0))
        if cur is not None and t0 > 1e-12:
            pieces.append((cur, cf))
            cur = None
        if cur is None:
            cur, cf = [a], []
        cur.append(b)
        cf.append(flags[i])
        if t1 < 1.0:
            pieces.append((cur, cf))
            cur = None
    if cur:
        pieces.append((cur, cf))
    return [(p, f) for p, f in pieces if len(p) >= 2 and _plen(p) > 1.0]


def _simplify(pts, flags, tol):
    """Douglas-Peucker run by run of equal flags (a bridge keeps its ends)."""
    out, of = [pts[0]], []
    i = 0
    while i < len(flags):
        j = i
        while j + 1 < len(flags) and flags[j + 1] == flags[i]:
            j += 1
        run = douglas_peucker(pts[i:j + 2], tol)
        out.extend(run[1:])
        of.extend([flags[i]] * (len(run) - 1))
        i = j + 1
    return out, of


# ── reading ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _vk(p):
    return (round(p[0], 1), round(p[1], 1))


def _geom(e, proj):
    return [proj((g["lat"], g["lon"])) for g in (e.get("geometry") or ()) if g]


class _UF:
    def __init__(self):
        self.p = {}

    def f(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def u(self, a, b):
        a, b = self.f(a), self.f(b)
        if a != b:
            self.p[b] = a


def _dijkstra(adj, srcs):
    import heapq
    dist, prev, h = {}, {}, []
    for s in srcs:
        dist[s] = 0.0
        h.append((0.0, s))
    heapq.heapify(h)
    while h:
        d, u = heapq.heappop(h)
        if d > dist.get(u, 1e18):
            continue
        for v, (L, _w) in adj[u].items():
            nd = d + L
            if nd < dist.get(v, 1e18):
                dist[v], prev[v] = nd, u
                heapq.heappush(h, (nd, v))
    return dist, prev


def _path(prev, a, b):
    out = [b]
    while out[-1] != a:
        out.append(prev[out[-1]])
    return out[::-1]


def _pieces(ways):
    """One road's ways [(pts, flag, wi)] -> its drawn pieces [(pts, flags, way indices)]: the longest path of each
    connected piece (one line for both carriageways) and its long branches."""
    adj = {}
    for pts, fl, wi in ways:
        for a, b in zip(pts, pts[1:]):
            ka, kb = _vk(a), _vk(b)
            if ka == kb:
                continue
            L = _d(a, b)
            adj.setdefault(ka, {})[kb] = (L, (fl, wi))
            adj.setdefault(kb, {})[ka] = (L, (fl, wi))
    seen, out = set(), []
    for n0 in adj:
        if n0 in seen:
            continue
        comp, st = [], [n0]
        seen.add(n0)
        while st:
            u = st.pop()
            comp.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    st.append(v)
        d0, _ = _dijkstra(adj, [n0])
        a = max(d0, key=d0.get)
        da, pa = _dijkstra(adj, [a])
        b = max(da, key=da.get)
        main = _path(pa, a, b)
        paths = [main]
        on = set(main)
        for _k in range(4):                       # branches: the farthest node that stands well off every path
            thin = _Bucket(_thin(paths), BRANCH_OFF)
            dist, prev = _dijkstra(adj, list(on))
            cand = [u for u in comp if u not in on and dist.get(u, 0) > BRANCH_MIN and not thin.near(u, BRANCH_OFF)]
            if not cand:
                break
            u = max(cand, key=lambda v: dist[v])
            pth = [u]
            while pth[-1] not in on:
                pth.append(prev[pth[-1]])
            pth = pth[::-1]
            off = [p for p in pth if not thin.near(p, BRANCH_OFF)]
            if len(off) < 2 or _plen(off) < BRANCH_MIN:
                break
            paths.append(pth)
            on |= set(pth)
        for pth in paths:
            fl = [adj[pth[i]][pth[i + 1]][1] for i in range(len(pth) - 1)]
            out.append((list(pth), [f for f, _w in fl], [w for _f, w in fl]))
    return out


class _Bucket:
    def __init__(self, pts, cell):
        self.c, self.b = max(1.0, cell), {}
        for p in pts:
            self.b.setdefault((int(p[0] // self.c), int(p[1] // self.c)), []).append(p)

    def near(self, p, r):
        cx, cy = int(p[0] // self.c), int(p[1] // self.c)
        k = int(r // self.c) + 1
        for i in range(-k, k + 1):
            for j in range(-k, k + 1):
                for q in self.b.get((cx + i, cy + j), ()):
                    if _d(p, q) <= r:
                        return True
        return False


def _thin(paths, step=60.0):
    out = []
    for p in paths:
        out.extend(_samples(p, step))
    return out


def _join(parts):
    """Pieces of one road whose ends meet within GAP_JOIN, joined end to end (never doubling back)."""
    parts = [list(p) for p in parts]
    changed = True
    while changed and len(parts) > 1:
        changed = False
        best = None
        for i in range(len(parts)):
            for j in range(len(parts)):
                if i >= j:
                    continue
                P, Q = parts[i][0], parts[j][0]
                for ri in (0, 1):
                    for rj in (0, 1):
                        a = P[-1] if ri == 0 else P[0]
                        b = Q[0] if rj == 0 else Q[-1]
                        dd = _d(a, b)
                        ta = _ang_of(P[-2], P[-1]) if ri == 0 else _ang_of(P[1], P[0])
                        tb = _ang_of(Q[0], Q[1]) if rj == 0 else _ang_of(Q[-1], Q[-2])
                        if abs((math.degrees(tb - ta) + 180) % 360 - 180) > 100:
                            continue
                        if dd < GAP_JOIN and (best is None or dd < best[0]):
                            best = (dd, i, j, ri, rj)
        if best:
            _dd, i, j, ri, rj = best
            P, PF, PW = parts[i]
            Q, QF, QW = parts[j]
            if ri:
                P, PF, PW = P[::-1], PF[::-1], PW[::-1]
            if rj:
                Q, QF, QW = Q[::-1], QF[::-1], QW[::-1]
            parts[i] = (P + Q, PF + [PF[-1] if PF else "0"] + QF, PW + [PW[-1] if PW else -1] + QW)
            del parts[j]
            changed = True
    return parts


PAIR_D = 170.0          # m: a piece of a road running this near a longer piece of it is its other carriageway


def _ang_of(a, b):
    return math.atan2(b[1] - a[1], b[0] - a[0])


def _pair(pieces):
    """The two carriageways of a dual highway (separate pieces in OSM) -> one line between them: a shorter piece that
    runs within PAIR_D of a longer one for most of its length pulls the longer one's vertices half-way toward it; the
    part of it beyond the longer one (an overhang) stays a piece of its own."""
    pieces = sorted(pieces, key=lambda p: -_plen(p[0]))
    out = []
    for pts, fl, wi in pieces:
        took = False
        for k, (Q, QF, QW) in enumerate(out):
            qb = _Bucket(Q, PAIR_D)
            sp = _samples(pts, 20.0)
            near = [qb.near(p, PAIR_D) or _project(p, Q)[0] < PAIR_D for p in sp]
            if sum(near) < 0.5 * len(near):
                continue
            Q2 = []
            for q in Q:
                d, _s, f = _project(q, pts)
                Q2.append(((q[0] + f[0]) / 2, (q[1] + f[1]) / 2) if d < PAIR_D else q)
            out[k] = (Q2, QF, QW)
            # the overhang: runs of this piece that stand off the longer one
            run, rf, rw = [], [], []
            for i, p in enumerate(pts):
                off = _project(p, Q)[0] >= PAIR_D
                if off:
                    if not run and i > 0:
                        run.append(pts[i - 1])
                    run.append(p)
                    if i < len(fl) and len(run) > 1:
                        pass
                    if i > 0:
                        rf.append(fl[i - 1])
                        rw.append(wi[i - 1])
                elif run:
                    run.append(p)
                    rf.append(fl[i - 1])
                    rw.append(wi[i - 1])
                    if _plen(run) > BRANCH_MIN:
                        out.append((run, rf[-(len(run) - 1):], rw[-(len(run) - 1):]))
                    run, rf, rw = [], [], []
            if run and len(run) > 1 and _plen(run) > BRANCH_MIN:
                out.append((run, rf[-(len(run) - 1):], rw[-(len(run) - 1):]))
            took = True
            break
        if not took:
            out.append((list(pts), list(fl), list(wi)))
    return out


def read(els, proj, W, H):
    """Raw OSM elements (dict (type, id) -> element, or an iterable of elements) -> the real highways:
      {"v": 1, "roads": [{id, ref, refs, net, n, names, parts: [{p: flat real px, f: "0bt..." a flag per segment,
                          w: [way names index per segment]}], dir: [[word, toward], ...]}],
       "x": [{r: road id, part, s (m along it), x, y, n, ex: [exit refs], cross: [street names], hw: [road ids], end?}]}"""
    E = list(els.values()) if isinstance(els, dict) else list(els)
    rels_of, rel_list = {}, []
    for e in E:
        tg = e.get("tags") or {}
        if e.get("type") == "relation" and tg.get("type") == "route" and tg.get("route") == "road":
            r = {"net": tg.get("network") or "", "ref": tg.get("ref") or "", "name": tg.get("name") or ""}
            rel_list.append(r)
            for mb in e.get("members") or ():
                if mb.get("type") == "way":
                    rels_of.setdefault(mb.get("ref"), []).append(r)
    ways, links, streets, junctions = [], [], [], []
    for e in E:
        tg = e.get("tags") or {}
        t = e.get("type")
        if t == "node" and tg.get("highway") == "motorway_junction":
            if "lat" in e:
                junctions.append((proj((e["lat"], e["lon"])), tg.get("ref") or "", tg.get("name") or ""))
            continue
        if t != "way" or tg.get("area") == "yes":
            continue
        hw = tg.get("highway")
        if not hw:
            continue
        pts = _geom(e, proj)
        if len(pts) < 2:
            continue
        rels = rels_of.get(e.get("id"), ())
        if hw in KINDS and qualifies(tg, rels):
            fl = "t" if tg.get("tunnel") not in (None, "no") else "b" if tg.get("bridge") not in (None, "no") else "0"
            ways.append({"pts": pts, "tg": tg, "rels": rels, "refs": refs_of(tg), "nm": hw_name(tg, rels) or tg.get("name") or "",
                         "f": fl, "id": e.get("id")})
        elif hw in LINKS:
            links.append({"pts": pts, "tg": tg})
        elif tg.get("name"):
            streets.append({"pts": pts, "n": tg["name"]})
    # group the ways into roads
    name_ref = {}
    for w in ways:
        if w["refs"] and w["nm"]:
            p = min(w["refs"], key=_rank)
            name_ref.setdefault(w["nm"], {}).setdefault(p, 0)
            name_ref[w["nm"]][p] += 1
    for w in ways:
        if w["refs"]:
            w["key"] = ("r", min(w["refs"], key=_rank))
        elif w["nm"] and w["nm"] in name_ref:
            w["key"] = ("r", max(name_ref[w["nm"]], key=name_ref[w["nm"]].get))
        elif w["nm"]:
            w["key"] = ("n", w["nm"])
        else:
            w["key"] = None
    vk_key = {}
    for w in ways:
        if w["key"]:
            for p in (w["pts"][0], w["pts"][-1]):
                vk_key.setdefault(_vk(p), set()).add(w["key"])
    for _round in range(4):                    # anonymous motorways: join the one road they touch
        for w in ways:
            if w["key"] is None:
                ks = set()
                for p in (w["pts"][0], w["pts"][-1]):
                    ks |= vk_key.get(_vk(p), set())
                if len(ks) == 1:
                    w["key"] = next(iter(ks))
                    for p in (w["pts"][0], w["pts"][-1]):
                        vk_key.setdefault(_vk(p), set()).add(w["key"])
    groups = {}
    for w in ways:
        if w["key"]:
            groups.setdefault(w["key"], []).append(w)
    roads, rid_of = [], {}
    for key, ws in sorted(groups.items(), key=lambda kv: (kv[0][0], _rank(kv[0][1]) if kv[0][0] == "r" else (9, 0, kv[0][1]))):
        names = {}
        for w in ws:
            if w["nm"]:
                names[w["nm"]] = names.get(w["nm"], 0.0) + _plen(w["pts"])
        if all("bridge" in (w["tg"].get("name") or "").lower() for w in ws) and key[0] == "n":
            continue                              # a bridge alone: the engine's bridges draw it
        nm_list = sorted(names, key=lambda n: (not HW_WORDS.search(n), -names[n]))
        widx = {n: i for i, n in enumerate(nm_list)}
        pieces = _pieces([(w["pts"], w["f"], widx.get(w["nm"], -1)) for w in ws])
        pieces = _join(_pair(pieces))
        parts = []
        for pts, fl, wi in pieces:
            for cp, cf in _clip(pts, list(zip(fl, wi)), W, H):
                flags = [f for f, _w in cf]
                wis = [w_ for _f, w_ in cf]
                sp, sf = _simplify(cp, ["%s%d" % (a, b) for a, b in zip(flags, wis)], SIMPL)
                if _plen(sp) < 60:
                    continue
                parts.append({"p": _flat(sp), "f": "".join(x[0] for x in sf), "w": [int(x[1:]) for x in sf]})
        if not parts or sum(_plen(_pairs(p["p"])) for p in parts) < MIN_LEN:
            continue
        refs = []
        for w in ws:
            for r in w["refs"]:
                if r not in refs:
                    refs.append(r)
        refs.sort(key=_rank)
        ref = key[1] if key[0] == "r" else ""
        rel_net = next((r["net"] for w in ws for r in w["rels"] if r["ref"] and ref.endswith(" " + r["ref"])), None)
        rid = "hw%d" % len(roads)
        rid_of[key] = rid
        road = {"id": rid, "ref": label(ref), "refs": [label(r) for r in refs[:3]], "net": network(ref, rel_net) if ref else "o",
                "n": (nm_list[0] if nm_list else label(ref)), "names": nm_list[:8], "parts": parts,
                "cls": "mw" if any(w["tg"].get("highway") == "motorway" for w in ws) else "tk"}
        road["dir"] = _directions(road, ws, ref)
        road["_ws"] = ws
        roads.append(road)
    xs = _interchanges(roads, rid_of, links, streets, junctions)
    for r in roads:
        r.pop("_ws", None)
    return {"v": 1, "roads": roads, "x": xs}


def _directions(road, ws, ref):
    """[[word, toward], [word, toward]]: the two directions of travel, named by compass (an Interstate by its number's
    parity, as signed), each with the most-signed destination of its carriageway."""
    P = [_pairs(p["p"]) for p in road["parts"]]
    main = max(P, key=_plen)
    ax = (main[-1][0] - main[0][0], main[-1][1] - main[0][1])
    ns = abs(ax[1]) >= abs(ax[0])
    mt = re.match(r"^I (\d+)", ref or "")
    if mt:
        ns = int(mt.group(1)) % 2 == 1
    if ns:
        fw = "south" if ax[1] > 0 else "north"           # page y grows southward
    else:
        fw = "east" if ax[0] > 0 else "west"
    bw = {"north": "south", "south": "north", "east": "west", "west": "east"}[fw]
    dest = {fw: {}, bw: {}}
    for w in ws:
        ds = w["tg"].get("destination") or ""
        if not ds or w["tg"].get("oneway") not in ("yes", "1", "-1"):
            continue
        a, b = w["pts"][0], w["pts"][-1]
        if w["tg"].get("oneway") == "-1":
            a, b = b, a
        dot = (b[0] - a[0]) * ax[0] + (b[1] - a[1]) * ax[1]
        k = fw if dot > 0 else bw
        for d_ in ds.split(";")[:2]:
            d_ = d_.strip()
            if d_:
                dest[k][d_] = dest[k].get(d_, 0.0) + _plen(w["pts"])
    return [[k, (max(dest[k], key=dest[k].get) if dest[k] else "")] for k in (fw, bw)]


def _interchanges(roads, rid_of, links, streets, junctions):
    """The link ramps that touch each road -> its interchanges (see the module rules)."""
    vroad = {}                                   # vertex -> road ids
    for r in roads:
        for w in r["_ws"]:
            for p in w["pts"]:
                vroad.setdefault(_vk(p), set()).add(r["id"])
    vst = {}
    for s in streets:
        for p in s["pts"]:
            vst.setdefault(_vk(p), set()).add(s["n"])
    uf = _UF()
    vlink = {}
    for i, l_ in enumerate(links):
        uf.f(i)
        for p in l_["pts"]:
            k = _vk(p)
            if k in vlink:
                uf.u(vlink[k], i)
            else:
                vlink[k] = i
    comps = {}
    for i in range(len(links)):
        comps.setdefault(uf.f(i), []).append(i)
    by_id = {r["id"]: r for r in roads}
    parts_pts = {r["id"]: [_pairs(p["p"]) for p in r["parts"]] for r in roads}
    recs = []
    for li in comps.values():
        touch, cross, dests = {}, {}, {}
        for i in li:
            tg = links[i]["tg"]
            for d_ in (tg.get("destination:street") or "").split(";"):
                if d_.strip():
                    dests[d_.strip()] = dests.get(d_.strip(), 0) + 1
            for p in links[i]["pts"]:
                k = _vk(p)
                for rid in vroad.get(k, ()):
                    touch.setdefault(rid, []).append(p)
                for n in vst.get(k, ()):
                    cross[n] = cross.get(n, 0) + 1
        for rid, pts in touch.items():
            others = [o for o in touch if o != rid]
            own = set(by_id[rid]["names"])
            cr = sorted((n for n in cross if n not in own), key=lambda n: -cross[n])
            ds = sorted((n for n in dests if n not in own), key=lambda n: -dests[n])
            for p in pts:
                recs.append({"r": rid, "p": p, "cross": cr or ds, "hw": others})
    # a road that ends on a street (no ramp): it ends at an interchange named for that street
    for r in roads:
        own = set(r["names"])
        for w in r["_ws"]:
            for p in (w["pts"][0], w["pts"][-1]):
                k = _vk(p)
                ns = [n for n in vst.get(k, ()) if n not in own]
                if ns and len(vroad.get(k, ())) == 1 and k not in vlink:
                    recs.append({"r": r["id"], "p": p, "cross": ns, "hw": [], "end": 1})
    # onto the road's drawn parts, clustered along them
    xs = []
    for r in roads:
        mine = []
        for rc in recs:
            if rc["r"] != r["id"]:
                continue
            best = None
            for pi, pp in enumerate(parts_pts[r["id"]]):
                d, s, q = _project(rc["p"], pp)
                if best is None or d < best[0]:
                    best = (d, pi, s, q)
            if best and best[0] < 400:
                mine.append(dict(rc, part=best[1], s=best[2]))
        mine.sort(key=lambda c: (c["part"], c["s"]))
        cl = []
        for c in mine:
            if cl and cl[-1][-1]["part"] == c["part"] and c["s"] - cl[-1][-1]["s"] < X_MERGE:
                cl[-1].append(c)
            else:
                cl.append([c])
        for group in cl:
            part = group[0]["part"]
            s = sum(c["s"] for c in group) / len(group)
            pp = parts_pts[r["id"]][part]
            x, y = _at(pp, s)
            cross, hw = {}, []
            for c in group:
                for k_, n in enumerate(c["cross"][:3]):
                    cross[n] = cross.get(n, 0) + 3 - k_
                for o in c["hw"]:
                    if o not in hw:
                        hw.append(o)
            cr = sorted(cross, key=lambda n: -cross[n])
            ex = []
            for (jp, jref, jname) in junctions:
                if jref and _d(jp, (x, y)) < JN_NEAR + X_MERGE / 2 and _project(jp, pp)[0] < 80:
                    if abs(_project(jp, pp)[1] - s) < X_MERGE and jref not in ex:
                        ex.append(jref)
            nm = (cr[0] if cr else "") or (by_id[hw[0]]["ref"] or by_id[hw[0]]["n"] if hw else "")
            rec = {"r": r["id"], "part": part, "s": round(s, 1), "x": round(x, 1), "y": round(y, 1), "n": nm,
                   "ex": ex[:3], "cross": cr[:3], "hw": hw}
            if all(c.get("end") for c in group):
                rec["end"] = 1
            xs.append(rec)
    return xs


def query_lines(b):
    """The Overpass statements palace_map.build_query adds for the highways (b: the bbox clause): the exit nodes and
    the road route relations (members only). Motorway/trunk ways and the streets the ramps touch are already in the
    query."""
    return ["node[highway=motorway_junction]%s;" % b, "out body;",
            "rel[type=route][route=road]%s;" % b, "out body;"]


# ── on the page ─────────────────────────────────────────────────────────────────────────────────────────────────────
class _Lat:
    """A domain's lattice as the router sees it (page / local / xg / yg), rebuilt from the stored map."""

    def __init__(self, a, o, xg, yg):
        self.a, self.o, self.xg, self.yg = a, o, xg, yg
        r = math.radians(a)
        self._c, self._s = math.cos(r), math.sin(r)

    def page(self, lx, ly):
        return (lx * self._c - ly * self._s + self.o[0], lx * self._s + ly * self._c + self.o[1])

    def local(self, x, y):
        x, y = x - self.o[0], y - self.o[1]
        return (x * self._c + y * self._s, -x * self._s + y * self._c)


class _DomRec:
    def __init__(self, id_, poly, clip, mapping):
        self.id, self.poly, self.clip, self.mapping = id_, poly, clip, mapping


def city_map(g):
    """palace_transit_route.CityMap of a finished map: its v2 domains (g["doms"]) or the v1 even grid (g["grid"])."""
    from .palace_grid import mapping_from
    from .palace_transit_route import CityMap
    doms = []
    if g.get("doms"):
        for d in g["doms"]:
            cw, ch = d["cwch"]
            xg = [d["xg"][0] + k * cw for k in range(int(d["xg"][1]))]
            yg = [d["yg"][0] + k * ch for k in range(int(d["yg"][1]))]
            lat = _Lat(d.get("a") or 0.0, tuple(d.get("o") or (0.0, 0.0)), xg, yg)
            clip = [tuple(p) for p in d["clip"]] if d.get("clip") else None
            doms.append((_DomRec(d["id"], [tuple(p) for p in d.get("poly") or []] or None, clip,
                                 mapping_from(d["mapping"])), lat))
    elif g.get("grid"):
        t = g["grid"]
        lat = _Lat(0.0, (0.0, 0.0), list(t["xg"]), list(t["yg"]))
        doms.append((_DomRec(0, None, None, mapping_from(t)), lat))
    else:
        return None
    return CityMap(doms)


def _chain(es):
    """Undirected edges -> polylines (node lists), walked from the ends and the branch points."""
    adj = {}
    for u, v in es:
        adj.setdefault(u, set()).add(v)
        adj.setdefault(v, set()).add(u)
    used, out = set(), []
    starts = [u for u in adj if len(adj[u]) != 2] or list(adj)[:1]
    for s in starts + list(adj):
        for v in sorted(adj[s]):
            e = (s, v) if s < v else (v, s)
            if e in used:
                continue
            path, a, b = [s], s, v
            while True:
                used.add((a, b) if a < b else (b, a))
                path.append(b)
                if len(adj[b]) != 2:
                    break
                nx = [w for w in adj[b] if ((b, w) if b < w else (w, b)) not in used]
                if not nx:
                    break
                a, b = b, nx[0]
            out.append(path)
    return out


def _straight(path):
    out = [path[0]]
    for i in range(1, len(path) - 1):
        a, b, c = out[-1], path[i], path[i + 1]
        cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cr) > 1e-3 * max(1.0, _d(a, b) * _d(b, c)):
            out.append(b)
    out.append(path[-1])
    return out


def _order(polys):
    """The polylines of a road in one sequence (each turned so it continues the previous one)."""
    if not polys:
        return []
    left = sorted(polys, key=lambda p: -_plen(p))
    seq = [left.pop(0)]
    while left:
        best = None
        for i, p in enumerate(left):
            for rev in (0, 1):
                q = p[::-1] if rev else p
                for end in (0, 1):
                    dd = _d(seq[-1][-1], q[0]) if end else _d(seq[0][0], q[-1])
                    if best is None or dd < best[0]:
                        best = (dd, i, rev, end)
        _dd, i, rev, end = best
        q = left.pop(i)
        q = q[::-1] if rev else q
        if end:
            seq.append(q)
        else:
            seq.insert(0, q)
    return seq


def _spans(poly, samples, flag, blk, rivers, avoid=()):
    """Tunnel ('t') runs of a drawn polyline: where the nearest mapped real sample is a tunnel. Bridge ('b') runs: where
    the line crosses a river band (its width and a margin), unless that stretch is a tunnel (`avoid`): a page bridge is
    a bridge over water (a viaduct over streets is just the highway passing over them)."""
    pts = _samples(poly, max(8.0, blk / 6))
    on = []
    tb = _Bucket([s for s in samples if s[2] == "t"], blk) if flag == "t" else None
    av = _Bucket([p for f in avoid for p in _pairs(f)], blk / 2) if avoid else None
    for p in pts:
        if flag == "t":
            on.append(tb.near(p, 1.2 * blk))
            continue
        hit = False
        if not (av and av.near(p, blk / 2)):
            for rv in rivers or ():
                rp = _pairs(rv["p"])
                half = rv.get("w", 60) / 2 + 14
                if any(_seg_foot(p, rp[i], rp[i + 1])[0] < half for i in range(len(rp) - 1)):
                    hit = True
                    break
        on.append(hit)
    runs, cur = [], []
    for p, o in zip(pts, on):
        if o:
            cur.append(p)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return [_flat(_straight(r)) for r in runs if len(r) >= 2 and _plen(r) > (blk / 2 if flag == "t" else blk / 4)]


def _octi_fill(cmap, seg):
    """A stretch drawn from the real shape, made of runs along its domain's axes and 45 degrees (palace_transit_route's
    tunnel shape, one axis run and one 45-degree run per smoothed piece, the corner on the side nearer the real road)."""
    from .palace_transit_route import octi2_in
    f = octi2_in(cmap)
    out = [seg[0]]
    for a, b in zip(seg, seg[1:]):
        out.extend(f(tuple(a), tuple(b), lambda u, v: 1.0)[1:])
    return _straight(out)


def _off_turns(polys, x, y, slide=26.0):
    """An interchange standing on a turn of its road slides along the longer run beside it, off the page's rounding."""
    for p in polys:
        for i in range(1, len(p) - 1):
            if _d(p[i], (x, y)) < 0.5:
                a, b = _ang_of(p[i - 1], p[i]), _ang_of(p[i], p[i + 1])
                if abs((math.degrees(b - a) + 180) % 360 - 180) < 8:
                    return (x, y)
                q = p[i - 1] if _d(p[i - 1], p[i]) > _d(p[i], p[i + 1]) else p[i + 1]
                L = _d(q, p[i])
                t = min(slide, L / 2) / L
                return (p[i][0] + t * (q[0] - p[i][0]), p[i][1] + t * (q[1] - p[i][1]))
    return (x, y)


def _drawn_city(g, blk):
    """A bucket of points over everything the page draws as city (blocks, polygon blocks, streets)."""
    pts = []
    for t in g.get("tiles") or ():
        pts += [(t[0], t[1]), (t[2], t[3]), ((t[0] + t[2]) / 2, (t[1] + t[3]) / 2)]
    for q in g.get("tq") or ():
        pts += _pairs(q)
    for s_ in g.get("streets") or ():
        pp = _pairs(s_.get("p") or [])
        if len(pp) >= 2:
            pts += _samples(pp, blk / 2)
    return _Bucket(pts, blk)


def _trim(poly, near, step):
    """The runs of a drawn polyline that stay near the drawn city (its own vertices kept exactly)."""
    runs, cur = [], []
    for a, b in zip(poly, poly[1:]):
        n = max(1, int(_d(a, b) // step))
        for k in range(n + 1):
            t = k / n
            p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            if near(p):
                if not cur or _d(cur[-1], p) > 1e-6:
                    cur.append(p)
            else:
                if len(cur) >= 2:
                    runs.append(cur)
                cur = []
    if len(cur) >= 2:
        runs.append(cur)
    return [_straight(r) for r in runs if _plen(r) > 2 * step]


def _dedup(polys, blk):
    """Drop a drawn polyline that runs within 0.6 block of a longer one of the same road for most of its length."""
    polys = sorted(polys, key=lambda p: -_plen(p))
    keep = []
    for p in polys:
        sp = _samples(p, blk / 4)
        if keep:
            b = _Bucket([q for k in keep for q in _samples(k, blk / 6)], 0.6 * blk)
            if sum(1 for q in sp if b.near(q, 0.6 * blk)) >= 0.7 * len(sp):
                continue
        keep.append(p)
    return keep


def _dir_at(polys, x, y):
    best = None
    for p in polys:
        for a, b in zip(p, p[1:]):
            d = _seg_foot((x, y), a, b)[0]
            if _d(a, b) > 1 and (best is None or d < best[0]):
                best = (d, _ang_of(a, b))
    return best[1] if best else None


def _streets_at(g, x, y, r=6.0, along=None):
    """Names of the drawn streets through (x, y); with `along` (the highway's heading there) only those that cross it
    (more than 25 degrees off), never the street the highway rides."""
    out = []
    for s in g.get("streets", []):
        p = s.get("p") or []
        if not s.get("n"):
            continue
        for i in range(0, len(p) - 3, 2):
            a, b = (p[i], p[i + 1]), (p[i + 2], p[i + 3])
            if _seg_foot((x, y), a, b)[0] <= r:
                if along is not None and _d(a, b) > 1:
                    t = abs((math.degrees(_ang_of(a, b) - along) + 90) % 180 - 90)
                    if t < 25:
                        continue
                out.append(s["n"])
                break
    return out


def attach(g, m=None):
    """Route the real highways (g["highways"] as palace_map read them, else m["highways"]) over the finished map's
    drawn domains -> g["hw"] (and returns it). Idempotent: a map that has g["hw"] is left alone."""
    if g.get("hw") is not None:
        g.pop("highways", None)
        return g["hw"]
    H = g.pop("highways", None) or (m or {}).get("highways")
    if not H or not H.get("roads"):
        return None
    cmap = city_map(g)
    if cmap is None:
        return None
    from .palace_transit_route import octi_route
    blk = cmap.blk
    rivers = [rv for rv in g.get("river") or () if rv.get("p")]
    out_roads, out_x = [], []
    xs_of = {}
    for x in H.get("x") or ():
        xs_of.setdefault((x["r"], x["part"]), []).append(x)
    for road in H["roads"]:
        polys, samples, kept_x, free = [], [], [], False
        for pi, part in enumerate(road["parts"]):
            rp = _pairs(part["p"])
            # the real track on the page, every SAMPLE m, with its flag
            q, s0 = [], 0.0
            for i in range(len(rp) - 1):
                L = _d(rp[i], rp[i + 1])
                n = max(1, int(L // SAMPLE))
                for k in range(n):
                    t = k / n
                    pxy = cmap(rp[i][0] + t * (rp[i + 1][0] - rp[i][0]), rp[i][1] + t * (rp[i + 1][1] - rp[i][1]))
                    q.append((pxy[0], pxy[1], part["f"][i] if i < len(part["f"]) else "0", part["w"][i] if i < len(part["w"]) else -1))
            pe = cmap(*rp[-1])
            q.append((pe[0], pe[1], part["f"][-1] if part["f"] else "0", part["w"][-1] if part["w"] else -1))
            samples.extend(q)
            real = [(a, b) for a, b, _f, _w in q]
            xs = sorted(xs_of.get((road["id"], pi), []), key=lambda x: x["s"])
            stops, sx = [real[0]], [None]
            for x in xs:
                p = cmap(x["x"], x["y"])
                if _d(p, stops[-1]) < STOP_MIN * blk:
                    if sx[-1] is None and len(stops) == 1:
                        stops[-1], sx[-1] = p, x        # the road begins at this interchange
                    continue
                stops.append(p)
                sx.append(x)
            if _d(real[-1], stops[-1]) >= STOP_MIN * blk:
                stops.append(real[-1])
                sx.append(None)
            elif sx[-1] is None:
                stops[-1] = real[-1]
            anc = {}
            es = set()
            if len(stops) >= 2 and _plen(real) > blk * 0.8:
                try:
                    es, kept, _info = octi_route(cmap, real, stops, [list(range(len(stops)))], anchors=anc, rivers=rivers)
                except Exception:                 # a road the router cannot draw keeps its smoothed real shape
                    es = set()
            if es:
                for path in _chain(es):
                    polys.append(_straight(path))
                for si, x in enumerate(sx):
                    if x is not None and si in anc:
                        kept_x.append((x, anc[si]))
            elif _plen(real) > blk:
                free = True
                polys.append(douglas_peucker(real, blk / 4))
                for si, x in enumerate(sx):
                    if x is not None:
                        d, s, f = _project(stops[si], polys[-1])
                        kept_x.append((x, f))
        if not polys:
            continue
        polys = _order(_dedup(polys, blk))
        # where no lattice carries the road (a park or a free domain, the page edge) it keeps its smoothed real shape,
        # joined onto the drawn line at both ends
        fx = []
        drawn = _Bucket([q for p in polys for q in _samples(p, blk / 4)], blk)
        trk = [(a, b) for a, b, _f, _w in samples]
        run = []
        for k, p in enumerate(trk + [None]):
            off = p is not None and not drawn.near(p, FILL_D * blk)
            if off:
                run.append(p)
                continue
            if len(run) >= 2 and _plen(run) > 2 * blk:
                seg = douglas_peucker(run, blk / 2)
                for end in (0, -1):
                    best = None
                    for pl in polys:
                        d, _s, f = _project(seg[end], pl)
                        if best is None or d < best[0]:
                            best = (d, f)
                    if best and best[0] < (FILL_D + 1.0) * blk:
                        seg = [best[1]] + seg if end == 0 else seg + [best[1]]
                fx.append(len(polys))
                polys.append(_octi_fill(cmap, seg))
            run = []
        # over blank paper (no block, no street within TRIM blocks: beyond the drawn city) a highway is not drawn
        city = _drawn_city(g, blk)
        kept, rec_fx = [], []
        for i, p in enumerate(polys):
            for q in _trim(p, lambda pt: city.near(pt, TRIM * blk), blk / 4):
                if i in fx:
                    rec_fx.append(len(kept))
                kept.append(q)
        polys = kept
        if not polys:
            continue
        kept_x = [(x, n) for x, n in kept_x if min(_project(n, p)[0] for p in polys) < 2.0]
        rec = {"id": road["id"], "ref": road["ref"], "refs": road["refs"], "net": road["net"], "n": road["n"],
               "names": road["names"], "cls": road["cls"], "dir": road["dir"], "p": [_flat(p) for p in polys]}
        if free:
            rec["free"] = 1
        if rec_fx:
            rec["fx"] = rec_fx
        rec["tn"] = [s for p in polys for s in _spans(p, samples, "t", blk, ())]
        rec["br"] = [s for p in polys for s in _spans(p, samples, "b", blk, rivers, rec["tn"])]
        sh = []                                       # shields: every SHIELD_BLK blocks, named by the nearest real way
        for p in polys:
            L = _plen(p)
            s = min(L / 2, 2.5 * blk)
            while s < L - blk:
                x, y = _at(p, s)
                near = min(samples, key=lambda q_: (q_[0] - x) ** 2 + (q_[1] - y) ** 2)
                sh.append([round(x, 1), round(y, 1), near[3]])
                s += SHIELD_BLK * blk
        rec["sh"] = sh
        rec["len"] = round(sum(_plen(p) for p in polys))
        out_roads.append(rec)
        seen_node = {}
        for x, node in kept_x:
            key = (round(node[0]), round(node[1]))
            if key in seen_node:                      # two ramp groups on one node: one interchange, exits merged
                prev = seen_node[key]
                for e in x.get("ex") or []:
                    if e not in prev["ex"] and len(prev["ex"]) < 2:
                        prev["ex"].append(e)
                continue
            on = [n for n in _streets_at(g, node[0], node[1], along=_dir_at(polys, node[0], node[1]))
                  if n not in road["names"]]
            want = [n for n in x.get("cross") or [] if n in on]
            at = (want or on or [""])[0]
            nm = at or x.get("n") or ""
            ex = list((x.get("ex") or [])[:2])
            nx, ny = _off_turns(polys, node[0], node[1])
            out_x.append({"r": road["id"], "x": round(nx, 1), "y": round(ny, 1),
                          "n": nm or (("Exit " + ex[0]) if ex else road["ref"] or road["n"]),
                          "ex": ex, "hw": x.get("hw") or [], "on": 1 if on else 0, **({"end": 1} if x.get("end") else {})})
            seen_node[key] = out_x[-1]
    # a street the engine drew for a highway (a k=0 street with its name) gives way to the highway line
    hw_names = {n for r in out_roads for n in r["names"]}
    before = len(g.get("streets", []))
    g["streets"] = [s for s in g.get("streets", []) if not (s.get("k") == 0 and s.get("n") in hw_names
                                                               and not s.get("sm") and not s.get("L"))]
    # interchange order along each road (ride order of the drawn line)
    for r in out_roads:
        mine = [x for x in out_x if x["r"] == r["id"]]
        line = [p for f in r["p"] for p in _pairs(f)]
        for x in mine:
            x["_s"] = _project((x["x"], x["y"]), line)[1] if len(line) > 1 else 0.0
    out_x.sort(key=lambda x: (x["r"], x.get("_s", 0)))
    for x in out_x:
        x.pop("_s", None)
    g["hw"] = {"v": 1, "roads": out_roads, "x": out_x, "dropped_streets": before - len(g["streets"])}
    return g["hw"]


# ── checks (city_report form: (status, msg, data)) ─────────────────────────────────────────────────────────────────
def _turns(f, tol=8.0, deg=10.0):
    p = douglas_peucker(_pairs(f), tol)
    n = 0
    for i in range(1, len(p) - 1):
        a = math.atan2(p[i][1] - p[i - 1][1], p[i][0] - p[i - 1][0])
        b = math.atan2(p[i + 1][1] - p[i][1], p[i + 1][0] - p[i][0])
        t = abs((math.degrees(b - a) + 180) % 360 - 180)
        if t > deg:
            n += 1
    return n


def _octi_ok(g, cmap, f):
    """Share of a drawn line's length that runs along its domain's axes, index diagonals or 45 degrees."""
    ok = tot = 0.0
    for a, b in zip(_pairs(f), _pairs(f)[1:]):
        L = _d(a, b)
        if L < 1:
            continue
        d = cmap.dom_page((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        (ax, ay), (bx, by) = d.lat.local(*a), d.lat.local(*b)
        ang = math.degrees(math.atan2(by - ay, bx - ax)) % 90
        diag = math.degrees(math.atan2(d.ch, d.cw))
        good = min(ang, 90 - ang) < 1.5 or abs(ang - 45) < 1.5 or abs(ang - diag) < 1.5 or abs(ang - (90 - diag)) < 1.5
        ok += L if (good or cmap.edge(a[0], a[1], 3) and cmap.edge(b[0], b[1], 3)) else 0
        tot += L
    return ok / tot if tot else 1.0


def measure(g, m):
    """Per road: turns, max / p90 stray from the mapped real road (blocks), octilinear share, interchanges (drawn,
    on a crossing drawn street, in real order), river crossings drawn vs real and on a bridge / tunnel."""
    hw = g.get("hw") or {}
    H = (m or {}).get("highways") or {}
    cmap = city_map(g)
    if not hw.get("roads") or cmap is None:
        return {}
    blk = cmap.blk
    real = {r["id"]: r for r in H.get("roads") or ()}
    rx = {}
    for x in H.get("x") or ():
        rx.setdefault(x["r"], []).append(x)
    rivers = [rv for rv in g.get("river") or () if rv.get("p")]
    out = {}
    for r in hw["roads"]:
        st = {"ref": r["ref"], "n": r["n"], "turns": sum(_turns(f) for i, f in enumerate(r["p"]) if i not in set(r.get("fx") or ())),
              "parts": len(r["p"]),
              "len_blocks": round(r["len"] / blk, 1)}
        rr = real.get(r["id"])
        if rr:
            track = []
            for part in rr["parts"]:
                track.extend(cmap(*p) for p in _samples(_pairs(part["p"]), SAMPLE * 2))
            ds = []
            for f in [f for i, f in enumerate(r["p"]) if i not in set(r.get("fx") or ())]:
                for p in _samples(_pairs(f), blk / 4):
                    ds.append(min(_d(p, q) for q in track))
            ds.sort()
            st["stray"] = round(ds[-1] / blk, 2) if ds else 0.0
            st["stray90"] = round(ds[int(0.9 * (len(ds) - 1))] / blk, 2) if ds else 0.0
            # river crossings: drawn vs the mapped real road
            def crossings(polys):
                n = 0
                for f in polys:
                    pp = _pairs(f)
                    for rv in rivers:
                        rp = _pairs(rv["p"])
                        for a, b in zip(pp, pp[1:]):
                            for c, d in zip(rp, rp[1:]):
                                if _xing(a, b, c, d):
                                    n += 1
                return n
            st["river_x"] = crossings(r["p"])
            st["river_x_real"] = crossings([_flat([cmap(*p) for p in _samples(_pairs(pt["p"]), SAMPLE)]) for pt in rr["parts"]])
        lat_p = [f for i, f in enumerate(r["p"]) if i not in set(r.get("fx") or ()) and _plen(_pairs(f)) > blk]
        tot = sum(_plen(_pairs(f)) for f in lat_p)
        st["octi"] = round(sum(_octi_ok(g, cmap, f) * _plen(_pairs(f)) for f in lat_p) / tot, 3) \
            if lat_p and not r.get("free") else None
        st["fill_blocks"] = round(sum(_plen(_pairs(r["p"][i])) for i in r.get("fx") or ()) / blk, 1)
        mine = [x for x in hw.get("x") or () if x["r"] == r["id"]]
        line = [p for f in r["p"] for p in _pairs(f)]
        st["x"] = len(mine)
        st["x_real"] = len(rx.get(r["id"], []))
        st["x_on_street"] = sum(1 for x in mine if x.get("on"))
        st["x_off_line"] = sum(1 for x in mine if min((_seg_foot((x["x"], x["y"]), a, b)[0]
                                                       for f in r["p"] for a, b in zip(_pairs(f), _pairs(f)[1:])), default=1e9) > 3.6)
        st["bridges"] = len(r.get("br") or ())
        st["tunnels"] = len(r.get("tn") or ())
        out[r["id"]] = st
        _ = line
    return out


def _xing(a, b, c, d):
    def cr(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    d1, d2, d3, d4 = cr(c, d, a), cr(c, d, b), cr(a, b, c), cr(a, b, d)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def report(g, m):
    """(status, msg, data) for city_report's plan: ("highways", lambda: city_highways.report(g, m)).
    fail: a road drawn off its domain's axes/45 degrees (octi < 0.9), straying more than 2.5 blocks, an interchange
    off its line or the real road's river crossings not drawn; warn: an interchange not on a crossing drawn street,
    more than 3 turns per 10 blocks."""
    hw = g.get("hw") or {}
    if not hw.get("roads"):
        n = len(((m or {}).get("highways") or {}).get("roads") or ())
        return ("warn" if n else "ok"), ("%d real highways, none drawn" % n if n else "no highways"), {}
    st = measure(g, m)
    probs, warns = [], []
    for rid, s in st.items():
        nm = s["ref"] or s["n"]
        if s.get("octi") is not None and s["octi"] < 0.9:
            probs.append("%s off its axes (%.0f%% octilinear)" % (nm, 100 * s["octi"]))
        if s.get("stray", 0) > 2.5:
            probs.append("%s strays %.1f blocks" % (nm, s["stray"]))
        if s["x_off_line"]:
            probs.append("%s: %d interchanges off the line" % (nm, s["x_off_line"]))
        if s.get("river_x_real") and s.get("river_x", 0) < s["river_x_real"] and s["bridges"] + s["tunnels"] == 0:
            probs.append("%s crosses water %d times for real, drawn without a bridge" % (nm, s["river_x_real"]))
        if s["x"] and s["x_on_street"] < s["x"]:
            warns.append("%s: %d of %d interchanges not on a crossing street" % (nm, s["x"] - s["x_on_street"], s["x"]))
        if s["len_blocks"] > 0 and s["turns"] > 3 + 0.3 * s["len_blocks"]:
            warns.append("%s: %d turns over %.0f blocks" % (nm, s["turns"], s["len_blocks"]))
    num = ", ".join("%s %d turns stray %.1f x %d/%d" % (s["ref"] or s["n"], s["turns"], s.get("stray", 0), s["x"], s["x_real"])
                    for s in st.values())
    status = "fail" if probs else "warn" if warns else "ok"
    return status, "%d highways, %d problems, %d warnings (%s)" % (len(st), len(probs), len(warns), num), \
        {"problems": probs[:12], "warnings": warns[:12], "roads": st}
