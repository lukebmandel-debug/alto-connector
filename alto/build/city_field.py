"""City engine v2, step 1: the street orientation field (ENGINE-DESIGN.md section 1.1-1.2).

Pure python (no numpy), no I/O, no global state. Input is the compact map of `palace_map.build_map`
(`m["streets"] = [{n, k, p: [x, y, ...], t?}]`, real px, x east, y south).

    f = field(m)            # rasters + modes
    lab = labels(f)         # per cell: None (empty), -1 (incoherent / off every mode), or a mode index

Angles are screen degrees (y down: positive is clockwise). A *lattice* angle is taken modulo 90, because
a street grid looks the same turned by 90 degrees: every segment votes with the angle 4*theta, so the two
perpendicular families of one grid vote for the same lattice angle.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field as _dc_field

CELL = 200.0        # raster cell in metres (times m["scale"] px)
SIGMA = 2.5         # Gaussian smoothing, in cells
DENS = 0.8          # a smoothed cell with less than DENS * C px of street per cell is empty
COH = 0.35          # coherence a cell needs to vote for / be labelled with a mode
TOL = 7.5           # a coherent cell within TOL degrees of a mode gets that mode
PEAK = 0.004        # a histogram peak must carry this share of all votes
PEAK_WIN = 6        # ... and be the maximum within +-PEAK_WIN degrees
MODE_SEP = 8.0      # a peak within MODE_SEP degrees of a stronger one is dropped
REFINE = 5.0        # a peak is refined to the circular mean of the cells within REFINE degrees
KMAX = 4            # street classes used (0 motorway .. 4 residential); 5 (named service) is ignored


def lat_dist(a, b):
    """Distance of two lattice angles (degrees, period 90) -> 0..45."""
    d = abs(a - b) % 90.0
    return min(d, 90.0 - d)


def wrap45(a):
    """A lattice angle in degrees reduced to (-45, 45]."""
    a = a % 90.0
    return a - 90.0 if a > 45.0 else a


def seg_angle(ax, ay, bx, by):
    """Lattice angle (degrees mod 90) of a segment."""
    return math.degrees(math.atan2(by - ay, bx - ax)) % 90.0


def street_segments(m, kmax=KMAX, tunnels=False):
    """Yield (street index, ax, ay, bx, by) for the segments of the streets of class <= kmax."""
    for i, s in enumerate(m.get("streets") or []):
        if s.get("k", 9) > kmax or (s.get("t") and not tunnels):
            continue
        p = s.get("p") or []
        for j in range(0, len(p) - 3, 2):
            yield i, p[j], p[j + 1], p[j + 2], p[j + 3]


@dataclass
class Field:
    C: float                 # cell size, real px
    nx: int
    ny: int
    S: list                  # raw street length per cell  [ny][nx]
    X: list                  # raw sum L cos 4 theta
    Y: list                  # raw sum L sin 4 theta
    ang: list                # smoothed lattice angle (deg, 0..90) or None (empty)
    coh: list                # smoothed coherence 0..1
    modes: list = _dc_field(default_factory=list)    # lattice angles (deg, 0..90), strongest first
    shares: list = _dc_field(default_factory=list)   # histogram share of each mode's peak
    W: float = 0.0
    H: float = 0.0
    scale: float = 1.0

    def cell_of(self, x, y):
        """(cx, cy) of a real px point (may be outside the raster)."""
        return int(math.floor(x / self.C)), int(math.floor(y / self.C))

    def inside(self, cx, cy):
        return 0 <= cx < self.nx and 0 <= cy < self.ny

    def raw_angle(self, cx, cy):
        """(lattice angle, coherence) of the raw, unsmoothed street in one cell; (None, 0) when empty."""
        s = self.S[cy][cx]
        if s <= 0:
            return None, 0.0
        X, Y = self.X[cy][cx], self.Y[cy][cx]
        return math.degrees(math.atan2(Y, X) / 4.0) % 90.0, math.hypot(X, Y) / s


def _rasters(m, C, nx, ny, kmax):
    S = [[0.0] * nx for _ in range(ny)]
    X = [[0.0] * nx for _ in range(ny)]
    Y = [[0.0] * nx for _ in range(ny)]
    for _, ax, ay, bx, by in street_segments(m, kmax):
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-6:
            continue
        th = math.atan2(by - ay, bx - ax)
        c4, s4 = math.cos(4 * th), math.sin(4 * th)
        n = max(1, int(L // (C / 2)))
        Ln = L / n
        for k in range(n):
            t = (k + .5) / n
            cx = int((ax + (bx - ax) * t) // C)
            cy = int((ay + (by - ay) * t) // C)
            if 0 <= cx < nx and 0 <= cy < ny:
                S[cy][cx] += Ln
                X[cy][cx] += Ln * c4
                Y[cy][cx] += Ln * s4
    return S, X, Y


def _smooth(A, nx, ny, sig):
    K = int(2 * sig)
    w = [math.exp(-d * d / (2 * sig * sig)) for d in range(-K, K + 1)]
    B = [[0.0] * nx for _ in range(ny)]
    for y in range(ny):
        row, out = A[y], B[y]
        for x in range(nx):
            v = row[x]
            if v:
                for d in range(max(-K, -x), min(K, nx - 1 - x) + 1):
                    out[x + d] += w[d + K] * v
    Cc = [[0.0] * nx for _ in range(ny)]
    for y in range(ny):
        row = B[y]
        for d in range(max(-K, -y), min(K, ny - 1 - y) + 1):
            wd, out = w[d + K], Cc[y + d]
            for x in range(nx):
                v = row[x]
                if v:
                    out[x] += wd * v
    return Cc, sum(w) ** 2


def find_modes(ang, coh, nx, ny, coh_min=COH, peak=PEAK, win=PEAK_WIN, sep=MODE_SEP, refine=REFINE):
    """Circular histogram (period 90, 1 degree bins, Gaussian votes sigma 2) of the coherent cells
    -> (modes, shares), strongest first."""
    vals = [ang[y][x] for y in range(ny) for x in range(nx)
            if ang[y][x] is not None and coh[y][x] >= coh_min]
    h = [0.0] * 90
    for a in vals:
        for b in range(90):
            d = abs(a - b) % 90.0
            d = min(d, 90.0 - d)
            if d < 9:
                h[b] += math.exp(-d * d / 8.0)
    tot = sum(h) or 1.0
    peaks = [b for b in range(90)
             if h[b] > 0 and h[b] >= max(h[(b + d) % 90] for d in range(-win, win + 1)) and h[b] / tot > peak]
    peaks.sort(key=lambda b: -h[b])
    modes, shares = [], []
    for b in peaks:
        sx = sy = 0.0
        for a in vals:
            if lat_dist(a, b) <= refine:
                r = math.radians(4 * a)
                sx += math.cos(r)
                sy += math.sin(r)
        mo = round(math.degrees(math.atan2(sy, sx)) / 4.0 % 90.0, 1) if (sx or sy) else float(b)
        if all(lat_dist(mo, o) >= sep for o in modes):
            modes.append(mo)
            shares.append(round(h[b] / tot, 4))
    return modes, shares


def field(m, cell=CELL, sigma=SIGMA, dens=DENS, coh_min=COH, kmax=KMAX):
    """The orientation field of a map -> Field (rasters, smoothed angle/coherence, modes)."""
    scale = float(m.get("scale") or 1.0)
    C = cell * scale
    W, H = float(m.get("W") or 0), float(m.get("H") or 0)
    if not W or not H:
        xs, ys = [], []
        for _, ax, ay, bx, by in street_segments(m, kmax):
            xs += [ax, bx]
            ys += [ay, by]
        W, H = (max(xs) if xs else C), (max(ys) if ys else C)
    nx, ny = int(W // C) + 1, int(H // C) + 1
    S, X, Y = _rasters(m, C, nx, ny, kmax)
    S2, ws = _smooth(S, nx, ny, sigma)
    X2, _ = _smooth(X, nx, ny, sigma)
    Y2, _ = _smooth(Y, nx, ny, sigma)
    ang = [[None] * nx for _ in range(ny)]
    coh = [[0.0] * nx for _ in range(ny)]
    for y in range(ny):
        for x in range(nx):
            s = S2[y][x]
            if s / ws >= C * dens:
                ang[y][x] = math.degrees(math.atan2(Y2[y][x], X2[y][x]) / 4.0) % 90.0
                coh[y][x] = math.hypot(X2[y][x], Y2[y][x]) / s
    modes, shares = find_modes(ang, coh, nx, ny, coh_min)
    return Field(C=C, nx=nx, ny=ny, S=S, X=X, Y=Y, ang=ang, coh=coh, modes=modes, shares=shares,
                 W=W, H=H, scale=scale)


def labels(f, tol=TOL, coh_min=COH):
    """Initial per-cell labels: None (empty), -1 (incoherent or off every mode), else the mode index."""
    out = [[None] * f.nx for _ in range(f.ny)]
    for y in range(f.ny):
        for x in range(f.nx):
            a = f.ang[y][x]
            if a is None:
                continue
            if f.coh[y][x] < coh_min or not f.modes:
                out[y][x] = -1
                continue
            i = min(range(len(f.modes)), key=lambda k: lat_dist(a, f.modes[k]))
            out[y][x] = i if lat_dist(a, f.modes[i]) <= tol else -1
    return out
