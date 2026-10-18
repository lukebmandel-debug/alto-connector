"""The accuracy block of a street-blob building (palace_street.py has the record format: ty yr er st ss hs fr by pe fe pw pc rd cf ar hr wp ex).

  party_walls(rings)            -> per footprint (edge bitmask, set of neighbour indices): which ring edges lie along another footprint (row-house party walls)
  front_edges(rings, roads, pe) -> per footprint the index of the edge facing the nearest road (-1 unknown)
  side_flags(ring, fe, pe)      -> pw bits (1 left, 2 right, 4 rear, 8 free-standing) seen from the street
  CityIndex(frame, opa, lif)    -> joins city records to a footprint: by address (addr:housenumber + addr:street, normalised) then by point-in-polygon
  opa_typology(bc, bcn, cat)    -> (ty, stories or 0, half-story flag) of an OPA building code
  osm_typology(tags, ...)       -> ty from OSM building=* / amenity + footprint, height, shared walls
  era_of(year), pitch_of(tags), enrich(...) -> the props of the block
Everything is pure Python and deterministic (same input, same bytes).
"""
from __future__ import annotations

import math
import re

Q = 0.1
TY = {n: i for i, n in enumerate(("unknown", "rowhouse", "twin", "detached", "lowrise_apts", "midrise", "highrise", "storefront_row", "civic", "industrial", "religious",
                                  "parking", "office", "hotel", "school", "hospital", "mixed_use"))}
HS_OSM, HS_CITY, HS_OVERTURE, HS_STORIES, HS_GUESS = 1, 2, 3, 4, 5
SS_OSM, SS_CITY, SS_OVERTURE, SS_HEIGHT = 1, 2, 3, 4
CF_PARCEL, CF_ADDR, CF_YEAR, CF_HEIGHT, CF_COLOUR, CF_MATERIAL, CF_ROOF, CF_STORIES = 1, 2, 4, 8, 16, 32, 64, 128
PW_LEFT, PW_RIGHT, PW_REAR, PW_FREE = 1, 2, 4, 8


# ── eras ────────────────────────────────────────────────────────────────────
def era_of(year) -> int:
    if not year:
        return 0
    return 1 if year < 1830 else 2 if year < 1900 else 3 if year <= 1945 else 4 if year < 1980 else 5


# ── roofs ───────────────────────────────────────────────────────────────────
_FLAT = {"flat"}
_LOW = {"skillion", "shed", "lean_to", "saltbox", "sawtooth"}
_STEEP = {"gabled", "hipped", "half-hipped", "gambrel", "pyramidal", "side_hipped", "cross_gabled", "hip", "gable", "round", "butterfly"}
_MANSARD = {"mansard"}
_DOME = {"dome", "onion", "cone", "conical", "spire", "pyramid"}


def pitch_of(t) -> int:
    rs = str(t.get("roof:shape") or "").strip().lower()
    ang = _f(t.get("roof:angle"))
    if ang:
        return 1 if ang < 3 else 2 if ang < 20 else 3
    if rs in _FLAT:
        return 1
    if rs in _LOW:
        return 2
    if rs in _STEEP:
        rh, h = _f(t.get("roof:height")), _f(t.get("height"))
        return 2 if (rh and h and rh < 1.2) else 3
    if rs in _MANSARD:
        return 4
    if rs in _DOME:
        return 5
    return 0


def _f(v):
    try:
        return float(str(v).replace(",", ".").split()[0].rstrip("m'"))
    except (TypeError, ValueError, IndexError):
        return None


# ── typology ────────────────────────────────────────────────────────────────
_STY = re.compile(r"(\d+(?:\.5)?)(\+)?(?:-(\d+))?\s*STY")


def _stories(s):
    """(stories, half, exact) of '... 3 STY ...' / '3.5 STY' / '5+ STY' / '10-14 STY'."""
    m = _STY.search(s or "")
    if not m:
        return 0, False, False
    a = float(m.group(1))
    if m.group(3):
        return int(round((a + float(m.group(3))) / 2)), False, False
    return int(a), a != int(a), not m.group(2)


def opa_typology(bc: str, bcn: str = "", cat: str = ""):
    """(ty, stories, half, exact) from an OPA building code; ty 0 when the code says nothing (vacant land, parking space, storage unit)."""
    b, n, c = (bc or "").upper(), (bcn or "").upper(), (cat or "").upper()
    st, half, exact = _stories(b)
    ty = 0
    if not b or b.startswith("VACANT") or "STORAGE UNIT" in b or "PARKING SPACE" in b or "AIR RIGHTS" in b:
        ty = 0
    elif "HSE WORSHIP" in b or "CHURCH" in b or "WORSHIP" in n:
        ty = TY["religious"]
    elif "SCHOOL" in b or "COLLEGE" in b or "UNIV" in b or "SCHOOL" in n or "EDUCATION" in n:
        ty = TY["school"]
    elif "HOSP" in b or "HOSPITAL" in n or "MEDICAL" in n:
        ty = TY["hospital"]
    elif "HOTEL" in b or "MOTEL" in b or "HOTEL" in n:
        ty = TY["hotel"]
    elif b.startswith("OFF BLD") or "OFFICE" in n:                    # (before parking: "OFF BLD N/PKG" is an office WITHOUT parking)
        ty = TY["office"]
    elif b.startswith(("PKG", "PD PKG", "NON PD PKG", "GAR NO COMM", "GAR W/COMM", "PRIV GAR", "PARKING")) or "GARAGE" in n:
        ty = TY["parking"]
    elif b.startswith("IND") or "WAREHOUSE" in b or "MFG" in b or "INDUSTRIAL" in c:
        ty = TY["industrial"]
    elif b.startswith("MISC") or "GOV" in n or "MUSEUM" in b or "RR STA" in b or "LIBRARY" in b or "AMUS" in b:
        ty = TY["civic"]
    elif b.startswith("ROW W/OFF STR") or b.startswith("STR/OFF+APT") or "MIXED" in c:
        ty = TY["mixed_use"] if not (b.startswith("ROW") and st and st <= 4) else TY["storefront_row"]
    elif b.startswith("STR") or b.startswith("STORE") or b.startswith("SUB STR") or "REST'RNT" in b or "GAS STAT" in b or "AUTO" in b or b.startswith("COM CONDO"):
        ty = TY["storefront_row"] if (st and st <= 4) or not st else TY["office"]
    elif b.startswith("ROW"):
        ty = TY["rowhouse"]
    elif b.startswith("TWIN") or b.startswith("SEMI/DET") or "TWIN" in n:
        ty = TY["twin"]
    elif b.startswith("DET") or "DETACHED" in n or "SINGLE" in n and "ROW" not in n:
        ty = TY["detached"]
    elif b.startswith("APT") or b.startswith("RES CONDO") or "CONDO" in b or "APART" in n:
        ty = TY["lowrise_apts"] if (st and st <= 4 and "+" not in b) else TY["midrise"]
    elif "SINGLE FAMILY" in c:
        ty = TY["rowhouse"]
    elif "MULTI FAMILY" in c:
        ty = TY["lowrise_apts"]
    elif "COMMERCIAL" in c:
        ty = TY["storefront_row"]
    return ty, st, half, exact


_CIVIC = {"civic", "government", "public", "museum", "train_station", "transportation", "courthouse", "library", "fire_station", "stadium", "townhall", "post_office",
          "police", "prison", "bridge"}
_RELIG = {"church", "cathedral", "chapel", "synagogue", "mosque", "temple", "religious", "shrine", "monastery", "basilica"}
_INDUS = {"industrial", "warehouse", "factory", "manufacture", "storage_tank", "hangar", "service", "silo", "transformer_tower", "shed", "barn"}
_PARK = {"parking", "garage", "garages", "carport"}
_SCHOOL = {"school", "university", "college", "kindergarten", "dormitory"}
_HOUSE = {"house", "detached", "residential", "yes", "terrace", "semidetached_house", "townhouse", "row_house", "bungalow", "cabin", "farm"}


def osm_typology(t: dict, area_m2: float, height_m: float, stories: int, shared: int, twin_pair: bool, philly: bool) -> int:
    """ty from OSM + the footprint (shared: how many neighbours touch it; twin_pair: it and its only neighbour touch nobody else)."""
    k = str(t.get("building") or "yes").lower()
    am = str(t.get("amenity") or "").lower()
    tall = height_m >= 40 or stories >= 12
    if k in _RELIG or am == "place_of_worship":
        return TY["religious"]
    if k == "hospital" or am in ("hospital", "clinic"):
        return TY["hospital"]
    if k in _SCHOOL or am in ("school", "university", "college"):
        return TY["school"]
    if k == "hotel" or t.get("tourism") == "hotel":
        return TY["hotel"]
    if k in _PARK or am == "parking":
        return TY["parking"]
    if k in _INDUS:
        return TY["industrial"]
    if k in _CIVIC or am in ("townhall", "courthouse", "library", "fire_station", "police", "post_office", "arts_centre", "theatre", "community_centre") \
            or t.get("tourism") in ("museum", "gallery") or (t.get("historic") and t.get("historic") != "no" and k in ("yes", "building") and area_m2 > 250):
        return TY["civic"]
    if k == "office" or (t.get("office") and k in ("yes", "commercial")):
        return TY["highrise"] if tall else TY["office"]
    if tall:
        return TY["highrise"]
    if k in ("apartments", "condominium", "residential") and (stories >= 5 or height_m >= 18):
        return TY["midrise"]
    if k in ("apartments", "condominium"):
        return TY["lowrise_apts"]
    if k in ("retail", "commercial", "shop", "kiosk", "supermarket", "mixed_use"):
        return TY["mixed_use"] if k == "mixed_use" or stories >= 5 else TY["storefront_row"]
    if k == "semidetached_house":
        return TY["twin"]
    if k in ("terrace", "townhouse", "row_house"):
        return TY["rowhouse"]
    if k in _HOUSE:
        if shared >= 2 and area_m2 < 400:
            return TY["rowhouse"]
        if shared == 1 and area_m2 < 400:
            return TY["twin"] if twin_pair else TY["rowhouse"]
        if k in ("house", "detached", "bungalow", "cabin", "farm") and shared == 0:
            return TY["detached"]
        if stories >= 5 or height_m >= 18:
            return TY["midrise"]
        if philly and k == "yes" and shared == 0 and area_m2 < 250 and height_m and height_m < 12:
            return TY["detached"]
    return 0


# ── geometry (integer units, the street frame) ──────────────────────────────
def _segd2(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if not L else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    X, Y = ax + t * dx - px, ay + t * dy - py
    return X * X + Y * Y, ax + t * dx, ay + t * dy


def signed_area(pts) -> float:
    a = 0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2


TOL = 5            # units (0.5 m): an edge within this of a neighbour's edge is shared
GRID = 300         # units (30 m)


def party_walls(rings):
    """[(bitmask, {neighbour index})] per ring (rings: lists of (x, y) units). An edge is a party wall when at least 2 of 3 points along it (20/50/80 %) lie within TOL
    of a NEAR-PARALLEL edge of another footprint."""
    idx: dict = {}
    for bi, pts in enumerate(rings):
        n = len(pts)
        for i in range(n):
            (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
            for gx in range((min(ax, bx) - TOL) // GRID, (max(ax, bx) + TOL) // GRID + 1):
                for gy in range((min(ay, by) - TOL) // GRID, (max(ay, by) + TOL) // GRID + 1):
                    idx.setdefault((gx, gy), []).append((bi, ax, ay, bx, by))
    out = []
    t2 = TOL * TOL
    for bi, pts in enumerate(rings):
        n, mask, nb = len(pts), 0, set()
        for i in range(min(n, 31)):
            (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
            dx, dy = bx - ax, by - ay
            L = math.hypot(dx, dy)
            if L < 10:                                     # under 1 m: a corner jog, not a wall
                continue
            hits, who = 0, set()
            for f in (0.2, 0.5, 0.8):
                px, py = ax + dx * f, ay + dy * f
                hit = None
                for (oj, cx, cy, ex, ey) in idx.get((int(px) // GRID, int(py) // GRID), ()):
                    if oj == bi:
                        continue
                    ox, oy = ex - cx, ey - cy
                    ol = math.hypot(ox, oy)
                    if ol < 1 or abs(dx * oy - dy * ox) > 0.26 * L * ol:      # not parallel (> ~15 deg)
                        continue
                    if _segd2(px, py, cx, cy, ex, ey)[0] <= t2:
                        hit = oj
                        break
                if hit is not None:
                    hits += 1
                    who.add(hit)
            if hits >= 2:
                mask |= 1 << i
                nb |= who
        out.append((mask, nb))
    return out


ROADS = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street", "pedestrian", "service", "motorway_link", "trunk_link",
         "primary_link", "secondary_link", "tertiary_link", "road"}
RGRID = 500        # units (50 m)
FRONT_MAX = 600    # units (60 m): no road nearer = front unknown


def front_edges(rings, roads, masks):
    """Per ring the index of the edge facing the street: among the edges not shared (all edges when every one is), the one whose midpoint is nearest a road segment lying
    on its OUTER side; a longer edge wins within 1 m. roads: [(ax, ay, bx, by)] units. -1 when no road lies within FRONT_MAX."""
    idx: dict = {}
    for s in roads:
        ax, ay, bx, by = s
        for gx in range(min(ax, bx) // RGRID, max(ax, bx) // RGRID + 1):
            for gy in range(min(ay, by) // RGRID, max(ay, by) // RGRID + 1):
                idx.setdefault((gx, gy), []).append(s)
    out = []
    for bi, pts in enumerate(rings):
        n = len(pts)
        ccw = signed_area(pts) > 0
        m = masks[bi] if bi < len(masks) else 0
        cand = [i for i in range(n) if not (i < 31 and (m >> i) & 1)] or list(range(n))
        best, bd, bl = -1, None, 0
        for i in cand:
            (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
            dx, dy = bx - ax, by - ay
            L = math.hypot(dx, dy)
            if L < 15:
                continue
            nx, ny = (dy / L, -dx / L) if ccw else (-dy / L, dx / L)          # outward normal
            mx, my = (ax + bx) / 2, (ay + by) / 2
            gx0, gy0 = int(mx) // RGRID, int(my) // RGRID
            near = None
            seen = set()
            for gx in (gx0 - 1, gx0, gx0 + 1):
                for gy in (gy0 - 1, gy0, gy0 + 1):
                    for s in idx.get((gx, gy), ()):
                        if id(s) in seen:
                            continue
                        seen.add(id(s))
                        d2, qx, qy = _segd2(mx, my, *s)
                        vx, vy = qx - mx, qy - my
                        d = math.sqrt(d2)
                        if d > FRONT_MAX or (vx * nx + vy * ny) < 0.5 * d:
                            continue
                        if near is None or d < near:
                            near = d
            if near is None:
                continue
            if bd is None or near < bd - 10 or (abs(near - bd) <= 10 and L > bl):
                best, bd, bl = i, near, L
        out.append(best)
    return out


def side_flags(pts, fe: int, mask: int) -> int:
    """pw: standing in the street facing edge fe — 1 a shared wall on the left, 2 on the right, 4 at the rear, 8 nothing shared."""
    if not mask:
        return PW_FREE
    if fe < 0:
        return 0
    n = len(pts)
    ccw = signed_area(pts) > 0
    (ax, ay), (bx, by) = pts[fe], pts[(fe + 1) % n]
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy) or 1
    ux, uy = dx / L, dy / L
    nx, ny = (uy, -ux) if ccw else (-uy, ux)                   # outward
    fx, fy = -nx, -ny                                          # the viewer faces the building
    lx, ly = -fy, fx                                           # the viewer's left
    mx, my = (ax + bx) / 2, (ay + by) / 2
    pw = 0
    for i in range(min(n, 31)):
        if i == fe or not (mask >> i) & 1:
            continue
        (cx, cy), (ex, ey) = pts[i], pts[(i + 1) % n]
        ex_, ey_ = ex - cx, ey - cy
        el = math.hypot(ex_, ey_) or 1
        ox, oy = (cx + ex) / 2 - mx, (cy + ey) / 2 - my
        if abs((ex_ * ux + ey_ * uy) / el) > 0.7 and (ox * fx + oy * fy) > 0:
            pw |= PW_REAR
        elif ox * lx + oy * ly > 0:
            pw |= PW_LEFT
        else:
            pw |= PW_RIGHT
    return pw


# ── addresses ───────────────────────────────────────────────────────────────
_DIRS = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W", "N": "N", "S": "S", "E": "E", "W": "W"}
_SUF = {"STREET": "ST", "ST": "ST", "AVENUE": "AVE", "AVE": "AVE", "PLACE": "PL", "PL": "PL", "BOULEVARD": "BLVD", "BLVD": "BLVD", "ROAD": "RD", "RD": "RD",
        "DRIVE": "DR", "DR": "DR", "LANE": "LN", "LN": "LN", "TERRACE": "TER", "TER": "TER", "COURT": "CT", "CT": "CT", "SQUARE": "SQ", "SQ": "SQ", "ALLEY": "ALY",
        "ALY": "ALY", "WAY": "WAY", "PARKWAY": "PKWY", "PKWY": "PKWY", "WALK": "WALK", "ROW": "ROW", "MALL": "MALL", "PIKE": "PIKE", "CIRCLE": "CIR", "CIR": "CIR"}


def norm_street(s: str):
    """('S', '15TH', 'ST') of 'South 15th Street'; ('', 'JOHN F KENNEDY', 'BLVD') of 'John F. Kennedy Boulevard'."""
    w = re.sub(r"[^A-Z0-9 ]", " ", str(s or "").upper()).split()
    d = suf = ""
    if len(w) > 1 and w[0] in _DIRS:
        d, w = _DIRS[w[0]], w[1:]
    if len(w) > 1 and w[-1] in _SUF:
        suf, w = _SUF[w[-1]], w[:-1]
    return d, " ".join(w), suf


def house_numbers(v):
    """The house numbers of addr:housenumber '1301-1319' / '1301;1303' / '1301A' (a range gives its two ends)."""
    return [int(x) for x in re.findall(r"\d+", str(v or ""))[:4] if len(x) < 6]


class CityIndex:
    """OPA parcel points and L&I footprint centroids in the street frame, for joins by address and by point-in-polygon."""

    def __init__(self, xy, opa=(), lif=()):
        self.opa, self.lif = list(opa or ()), list(lif or ())
        self.addr: dict = {}
        self.addr_nd: dict = {}
        self.og, self.lg = {}, {}
        self.opt = []
        for i, r in enumerate(self.opa):
            X, Y = xy(r["lat"], r["lon"])
            self.opt.append((X, Y))
            self.og.setdefault((X // GRID, Y // GRID), []).append(i)
            try:
                hn = int(re.match(r"\d+", r.get("hn") or "").group(0))
            except (AttributeError, ValueError):
                continue
            nm = re.sub(r"[^A-Z0-9 ]", " ", (r.get("name") or "").upper()).split()
            k = (hn, r.get("dir") or "", " ".join(nm), (r.get("suf") or "").upper())
            self.addr.setdefault(k, []).append(i)
            self.addr_nd.setdefault((hn, k[2], k[3]), set()).add(k[1])
        self.lpt = []
        for i, r in enumerate(self.lif):
            X, Y = xy(r["lat"], r["lon"])
            self.lpt.append((X, Y))
            self.lg.setdefault((X // GRID, Y // GRID), []).append(i)

    def _inside(self, grid, pts_of, ring, pip):
        x0, x1 = min(p[0] for p in ring), max(p[0] for p in ring)
        y0, y1 = min(p[1] for p in ring), max(p[1] for p in ring)
        out = []
        for gx in range(x0 // GRID, x1 // GRID + 1):
            for gy in range(y0 // GRID, y1 // GRID + 1):
                for i in grid.get((gx, gy), ()):
                    X, Y = pts_of[i]
                    if x0 <= X <= x1 and y0 <= Y <= y1 and pip(X, Y, ring):
                        out.append(i)
        return sorted(out)

    def by_address(self, tags, cx, cy, max_units=1500):
        """OPA rows whose address is the footprint's (within 150 m of its centre)."""
        d, name, suf = norm_street(tags.get("addr:street"))
        if not name:
            return []
        out = []
        for hn in house_numbers(tags.get("addr:housenumber"))[:1]:
            dirs = [d] if d else sorted(self.addr_nd.get((hn, name, suf), ()))
            if len(dirs) != 1:
                continue
            for i in self.addr.get((hn, dirs[0], name, suf), ()):
                X, Y = self.opt[i]
                if (X - cx) ** 2 + (Y - cy) ** 2 <= max_units ** 2:
                    out.append(i)
        return out

    def opa_in(self, ring, pip):
        return self._inside(self.og, self.opt, ring, pip)

    def lif_in(self, ring, pip):
        return self._inside(self.lg, self.lpt, ring, pip)


def pick_opa(rows):
    """The one record that speaks for a building with several parcels/units inside (condos, a block of row houses split badly): the most common typed building code; its
    year = the most common recorded year; stories = the largest exact count."""
    typed = [r for r in rows if opa_typology(r.get("bc"), r.get("bcn"), r.get("cat"))[0]]
    if not typed:
        return None
    cnt: dict = {}
    for r in typed:
        cnt[r["bc"]] = cnt.get(r["bc"], 0) + 1
    bc = sorted(cnt, key=lambda k: (-cnt[k], k))[0]
    best = dict(sorted((r for r in typed if r["bc"] == bc), key=lambda r: (-(r.get("fr") or 0), r["lat"], r["lon"]))[0])
    yrs: dict = {}
    for r in typed:
        if r.get("yr"):
            yrs[(r["yr"], r.get("yre", 0))] = yrs.get((r["yr"], r.get("yre", 0)), 0) + 1
    if yrs:
        (best["yr"], best["yre"]) = sorted(yrs, key=lambda k: (-yrs[k], k[1], k[0]))[0]
    best["st"] = max([r.get("st") or 0 for r in typed])
    best["n"] = len(rows)
    return best


RESIDENTIAL = {1, 2, 3, 4, 5, 6, 7, 16}
GENERIC_KINDS = {"yes", "residential", "building", ""}


def choose_typology(opa_ty: int, osm_ty: int, kind: str) -> int:
    """The city record's typology, except where OSM names a SPECIFIC kind that disagrees with it (a parcel record speaks for a lot that may hold a landmark, a tower or
    a church beside a garage): OSM wins then, but inside the residential family the city's code (row / twin / detached / apartments) is the finer one."""
    if not opa_ty:
        return osm_ty
    if not osm_ty or str(kind or "").lower() in GENERIC_KINDS:
        return opa_ty
    if opa_ty in RESIDENTIAL and osm_ty in RESIDENTIAL:
        return opa_ty
    return osm_ty


def storey_m(ty: int, era: int) -> float:
    """Floor-to-floor height used to turn a height into a story count: tall old floors, civic halls."""
    if ty in (8, 10, 14, 15):
        return 4.5
    if era in (1, 2):
        return 3.9
    return 3.3
